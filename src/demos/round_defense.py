"""CT presence and movement relative to recorded information, not inferred sight."""

from src.demos.round_attacks import bomb_site, target_sites
from src.demos.tactical_ids import action_id
from src.models.tactical import Episode, Retake, Rotation, Status

DEFENSE_VERSION = 2


def _coverage(record, pid, left, right):
    stays = sorted(
        (
            stay
            for stay in record.region_stays
            if stay.player_id == pid and stay.end_tick >= left and stay.start_tick <= right
        ),
        key=lambda s: s.start_tick,
    )
    if not stays or stays[0].start_tick > left or stays[-1].end_tick < right:
        return False
    if any(stay.area is None for stay in stays):
        return False
    return not any(
        gap["player_id"] == pid and gap["start_tick"] < right and gap["end_tick"] > left
        for gap in record.movement_gaps
    )


def enrich_defense(record, evidence, profile, *, tick_rate, movements, state_index):
    record.ct_activity, record.rotations = [], []
    record.rotation_eligibility = []
    if not profile or record.freeze_end_tick is None:
        record.rotations_status = Status.UNKNOWN
        record.retake = Retake(Status.UNKNOWN)
        return
    regions = profile.regions_by_id
    for stay in record.region_stays:
        if stay.side != "CT" or stay.end_tick - stay.start_tick < tick_rate or not stay.area:
            continue
        previous = next(
            (
                old
                for old in reversed(record.region_stays)
                if old.player_id == stay.player_id
                and old.area == stay.previous_area
                and old.end_tick <= stay.start_tick
            ),
            None,
        )
        kind = (
            "forward_presence"
            if stay.forward
            else (
                "withdrawal_from_forward"
                if previous and previous.forward
                else "positional_presence"
            )
        )
        utility = [
            u
            for u in record.utility_contexts
            if u.player_id == stay.player_id
            and u.throw_tick is not None
            and stay.start_tick <= u.throw_tick <= stay.end_tick
        ]
        contacts = [
            c
            for c in record.contacts
            if stay.start_tick <= c.tick <= stay.end_tick
            and stay.player_id in {c.attacker_id, c.victim_id}
        ]
        refs = sorted(
            set(
                stay.evidence_ids
                + [ref for u in utility for ref in u.evidence_ids]
                + [ref for c in contacts for ref in c.evidence_ids]
            )
        )
        record.ct_activity.append(
            Episode(
                action_id("ct_activity", record.number, stay.id),
                kind,
                stay.start_tick,
                stay.end_tick,
                [stay.player_id],
                refs,
                related_ids=[u.id for u in utility] + [c.id for c in contacts],
                status=stay.status,
                area=stay.area,
            )
        )
    plants = [
        evidence[eid]
        for eid in record.bomb_event_ids
        if evidence[eid].data.get("event") == "bomb_planted"
    ]
    triggers = []
    first_by_site = {}
    for contact in record.contacts:
        if contact.modality not in {"firearm", "mixed"}:
            continue
        targets = target_sites(regions.get(contact.victim_position.area)) | target_sites(
            regions.get(contact.attacker_position.area)
        )
        if len(targets) == 1:
            site = next(iter(targets))
            if site not in first_by_site or contact.tick < first_by_site[site].tick:
                first_by_site[site] = contact
    triggers.extend(
        (contact.tick, site, contact.evidence_ids[0], "damage_contact")
        for site, contact in first_by_site.items()
    )
    for attack in record.attacks:
        matches = [
            c
            for c in record.contacts
            if attack.episode.start_tick - 2 * tick_rate <= c.tick <= attack.episode.end_tick
            and attack.target_site
            in (
                target_sites(regions.get(c.victim_position.area))
                | target_sites(regions.get(c.attacker_position.area))
            )
        ]
        if matches:
            contact = min(matches, key=lambda c: (c.tick, c.id))
            triggers.append(
                (contact.tick, attack.target_site, contact.evidence_ids[0], "damage_contact")
            )
    for plant in plants:
        site = bomb_site(plant, profile, state_index, tick_rate)
        if site:
            triggers.append((plant.tick, site, plant.id, "plant"))
    triggers = sorted(set(triggers))
    for trigger, site, ref, kind in triggers:
        # A later named signal starts another opportunity, not overlapping delay.
        boundary = min(
            (tick for tick, target, _, _ in triggers if tick > trigger and target == site),
            default=record.end_tick,
        )
        for player in record.players:
            if player.side != "CT":
                continue
            pid = player.player_id
            sample = state_index.before(
                trigger,
                player_id=pid,
                max_age_ticks=round(tick_rate),
                max_gap_ticks=round(2 * tick_rate),
            ).row
            current = movements.at(pid, trigger - 1)
            anchor = current
            if current and current.defense_sector is None:
                anchor = next(
                    (
                        stay
                        for stay in reversed(record.region_stays)
                        if stay.player_id == pid
                        and stay.defense_sector is not None
                        and trigger - 5 * tick_rate <= stay.end_tick < current.start_tick
                        and _coverage(record, pid, stay.end_tick, trigger - 1)
                    ),
                    current,
                )
            eligible = (
                "unknown"
                if not sample or sample.get("is_alive") is None or not current
                else "dead"
                if not sample.get("is_alive")
                else "unknown"
                if anchor.defense_sector is None
                else "already_in_sector"
                if anchor.defense_sector == site
                else "eligible"
            )
            record.rotation_eligibility.append(
                {
                    "player_id": pid,
                    "trigger_tick": trigger,
                    "target_site": site,
                    "information_event_id": ref,
                    "status": eligible,
                    "evidence_ids": [str(sample["event_id"])] if sample else [],
                }
            )
            if eligible != "eligible":
                continue
            death = next(
                (
                    evidence[eid]
                    for eid in record.event_ids
                    if evidence[eid].source == "kills"
                    and str(evidence[eid].data.get("user_steamid")) == pid
                    and trigger <= evidence[eid].tick <= boundary
                ),
                None,
            )
            end = death.tick if death else boundary
            arrival = next(
                (
                    stay
                    for stay in record.region_stays
                    if stay.player_id == pid
                    and trigger <= stay.start_tick <= end
                    and stay.defense_sector == site
                ),
                None,
            )
            path_end = arrival.start_tick if arrival else end
            complete = _coverage(record, pid, trigger - 1, path_end)
            transitions = [
                tr
                for tr in record.region_transitions
                if tr.player_id == pid
                and trigger - 5 * tick_rate <= tr.arrival_tick <= path_end
                and regions[tr.from_area].defense_sector == anchor.defense_sector
                and regions[tr.to_area].defense_sector != anchor.defense_sector
            ]
            departure = transitions[-1] if transitions and arrival and complete else None
            # Starting movement within the same sector cannot be measured from
            # region changes; timestamps are explicitly sector-departure bounds.
            start = departure.departure_tick if departure else trigger
            refs = [ref, str(sample["event_id"])]
            if arrival:
                refs.extend(arrival.evidence_ids)
            if departure:
                refs.extend(departure.evidence_ids)
            if death:
                refs.append(death.id)
            outcome = (
                "arrived"
                if arrival and complete
                else "unknown"
                if not complete
                else "interrupted_by_death"
                if death
                else "no_observed_arrival"
            )
            record.rotations.append(
                Rotation(
                    Episode(
                        action_id("rotation", record.number, pid, ref),
                        "rotation" if outcome == "arrived" else "rotation_opportunity",
                        max(record.freeze_end_tick, min(trigger, start)),
                        path_end,
                        [pid],
                        sorted(set(refs)),
                        status=Status.OBSERVED if complete else Status.PARTIAL,
                        area=site,
                    ),
                    pid,
                    from_area=anchor.area,
                    to_area=arrival.area if arrival else None,
                    information_event_id=ref,
                    trigger_kind=kind,
                    arrival_tick=arrival.start_tick if arrival and complete else None,
                    reaction_seconds=(start - trigger) / tick_rate if departure else None,
                    already_moving=departure.arrival_tick < trigger if departure else None,
                    travel_seconds=(arrival.start_tick - start) / tick_rate if departure else None,
                    outcome=outcome,
                    target_site=site,
                )
            )
    record.rotations_status = (
        (Status.PARTIAL if record.movement_status != Status.OBSERVED else Status.OBSERVED)
        if record.rotations
        else (Status.ABSENT if record.movement_status == Status.OBSERVED else Status.UNKNOWN)
    )
    _retake(record, evidence, profile, plants, tick_rate=tick_rate, state_index=state_index)
    # Describe only an actual contact with an observed rotating defender.
    for attack in record.attacks:
        for action in attack.detached_actions:
            pid = action["player_id"]
            action["rotation_contact_ids"] = sorted(
                {
                    c.id
                    for rotation in record.rotations
                    if rotation.outcome == "arrived" and rotation.target_site == attack.target_site
                    for c in record.contacts
                    if rotation.episode.start_tick <= c.tick <= rotation.arrival_tick
                    and {c.attacker_id, c.victim_id} == {pid, rotation.player_id}
                    and any(
                        interval["start_tick"] <= c.tick <= interval["end_tick"]
                        for interval in action["intervals"]
                    )
                }
            )


def _retake(record, evidence, profile, plants, *, tick_rate, state_index):
    if not plants:
        source = record.availability.get("bombs")
        record.retake = Retake(
            Status.NOT_APPLICABLE
            if source and source.status in {Status.OBSERVED, Status.ABSENT}
            else Status.UNKNOWN
        )
        return
    plant = min(plants, key=lambda e: e.tick)
    site = bomb_site(plant, profile, state_index, tick_rate)
    if not site:
        record.retake = Retake(Status.UNKNOWN, plant_id=plant.id, outcome="unknown")
        return
    regions = profile.regions_by_id
    crossings = [
        tr
        for tr in record.region_transitions
        if tr.arrival_tick > plant.tick
        and regions[tr.to_area].kind == "site"
        and regions[tr.to_area].site_id == site
        and any(p.player_id == tr.player_id and p.side == "CT" for p in record.players)
    ]
    # An existing CT on the planted site may contest it without a new crossing.
    contacts = [
        c
        for c in record.contacts
        if c.tick >= plant.tick
        and c.modality in {"firearm", "mixed"}
        and any(
            position.area is not None
            and site in target_sites(regions.get(position.area))
            and (c.attacker_side == "CT" or regions[position.area].kind == "site")
            for side, position in (
                (c.attacker_side, c.attacker_position),
                (c.victim_side, c.victim_position),
            )
            if side == "CT"
        )
    ]
    defuses = [
        evidence[eid]
        for eid in record.bomb_event_ids
        if evidence[eid].tick >= plant.tick
        and evidence[eid].data.get("event") in {"bomb_begindefuse", "bomb_defused"}
    ]
    refs = [plant.id] + [ref for tr in crossings for ref in tr.evidence_ids]
    refs.extend(ref for c in contacts for ref in c.evidence_ids)
    refs.extend(event.id for event in defuses)
    participants = sorted(
        {tr.player_id for tr in crossings}
        | {c.attacker_id if c.attacker_side == "CT" else c.victim_id for c in contacts}
        | {
            str(event.data.get("user_steamid"))
            for event in defuses
            if event.data.get("user_steamid")
        }
    )
    confirmed = bool(crossings or contacts or defuses)
    complete = record.movement_status == Status.OBSERVED and record.contacts_status in {
        Status.OBSERVED,
        Status.ABSENT,
    }
    outcome = (
        (
            "won"
            if record.winner_side == "CT"
            else "lost"
            if record.winner_side == "T"
            else "unknown"
        )
        if confirmed
        else ("no_attempt" if complete else "unknown")
    )
    ticks = (
        [tr.arrival_tick for tr in crossings]
        + [c.tick for c in contacts]
        + [event.tick for event in defuses]
    )
    episode = (
        Episode(
            action_id("retake", record.number, plant.id),
            "retake_attempt",
            min(ticks),
            record.end_tick,
            participants,
            sorted(set(refs)),
            status=Status.OBSERVED,
            area=site,
        )
        if confirmed
        else None
    )
    defused = next(
        (event.id for event in defuses if event.data.get("event") == "bomb_defused"), None
    )
    record.retake = Retake(
        Status.OBSERVED if confirmed else Status.ABSENT if complete else Status.UNKNOWN,
        episode,
        plant.id,
        outcome,
        defused,
    )
