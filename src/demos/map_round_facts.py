"""Compact, source-backed M5 facts. No prose or trajectories in the aggregate input."""

from collections import Counter

from src.demos.map_action_facts import action_facts
from src.models.tactical import Status

ROUND_FACTS_VERSION = 7
KNOWN = {Status.OBSERVED, Status.ABSENT}


def _snapshot(snapshot, side, roster, profile):
    if snapshot is None:
        return None
    regions = profile.regions_by_id if profile else {}
    positions = []
    for pid in roster:
        player = next((p for p in snapshot.players if p["player_id"] == pid), None)
        region = regions.get(player.get("area")) if player else None
        positions.append(
            {
                "player_id": pid,
                "area": region.id if region else None,
                "alive": player.get("alive") if player else None,
                "sample_tick": player.get("sample_tick") if player else None,
                "direction": (
                    region.directions[0]
                    if len(region.directions) == 1
                    else region.site_id
                    if region.kind == "site"
                    else next(iter(region.route_names))
                    if region.kind == "approach" and len(region.route_names) == 1
                    else None
                )
                if region
                else None,
            }
        )
    complete = (
        snapshot.status == Status.OBSERVED
        and len(roster) == 5
        and all(p["alive"] is not None and (not p["alive"] or p["area"]) for p in positions)
    )
    directions = Counter(p["direction"] or "other" for p in positions if p["alive"])
    maximum = max(directions.values(), default=0)
    leaders = sorted(key for key, count in directions.items() if count == maximum)
    return {
        "tick": snapshot.tick,
        "seconds": snapshot.seconds,
        "side": side,
        "positions": positions,
        "complete": complete,
        "status": str(snapshot.status),
        "dominant_direction": leaders[0]
        if complete and len(leaders) == 1
        else "mixed"
        if complete and leaders
        else "no_alive"
        if complete
        else None,
        "direction_counts": dict(directions),
        "evidence_ids": snapshot.evidence_ids,
    }


def _equipment(record, roster):
    samples = record.foundation.equipment_start if record.foundation else []
    items = {
        pid: next(
            (s for s in samples if s.player_id == pid and s.tick == record.freeze_end_tick), None
        )
        for pid in roster
    }
    economy = {}
    for prop in ("current_equip_value", "cash_spent_this_round", "start_balance", "balance"):
        values = [
            s.economy.get(prop) for s in items.values() if s and s.economy.get(prop) is not None
        ]
        economy[prop] = {
            "total": sum(values) if len(values) == len(roster) == 5 else None,
            "known_players": len(values),
            "expected_players": len(roster),
        }
    return {
        "inventory_known_players": sum(
            s is not None and s.inventory is not None for s in items.values()
        ),
        "expected_players": len(roster),
        "economy": economy,
        "evidence_ids": sorted({eid for s in items.values() if s for eid in s.evidence_ids}),
    }


def build_round_fact(record, evidence, profile, *, metadata=None, early_seconds=15):
    metadata = metadata or {}
    rate = record.foundation.clock["tick_rate"] if record.foundation else 64.0
    if record.foundation is None:
        rate = metadata.get("tick_rate", rate)

    def seconds(tick):
        return (
            (tick - record.freeze_end_tick) / rate if record.freeze_end_tick is not None else None
        )

    def source_known(source):
        return (
            record.availability.get(source) is not None
            and record.availability[source].status in KNOWN
        )

    all_alive_known = (
        source_known("kills")
        and record.alive_states
        and all(
            s.status == Status.OBSERVED and s.t_alive is not None and s.ct_alive is not None
            for s in record.alive_states
        )
    )
    sides = {}
    baseline = next(
        (
            s
            for s in record.alive_states
            if s.tick == record.freeze_end_tick and s.status == Status.OBSERVED
        ),
        None,
    )
    for side, prep in (("T", record.t_preparation), ("CT", record.ct_setup)):
        roster = sorted({p.player_id for p in record.players if p.side == side})
        first_contacts = []
        player_first_contacts = []
        contacts = [c for c in record.contacts if c.modality in {"firearm", "mixed"}]
        first_tick = min((c.tick for c in contacts), default=None)
        for contact in contacts:
            if contact.tick != first_tick:
                continue
            own_id = contact.attacker_id if contact.attacker_side == side else contact.victim_id
            position = (
                contact.attacker_position
                if contact.attacker_side == side
                else contact.victim_position
            )
            first_contacts.append(
                {
                    "tick": contact.tick,
                    "seconds": seconds(contact.tick),
                    "player_id": own_id,
                    "area": position.area,
                    "evidence_ids": list(
                        dict.fromkeys(
                            contact.evidence_ids
                            + ([position.evidence_id] if position.evidence_id else [])
                        )
                    ),
                }
            )
        for pid in roster:
            own = [c for c in contacts if pid in {c.attacker_id, c.victim_id}]
            own_first = min((c.tick for c in own), default=None)
            for contact in own:
                if contact.tick != own_first:
                    continue
                position = (
                    contact.attacker_position
                    if contact.attacker_id == pid
                    else contact.victim_position
                )
                player_first_contacts.append(
                    {
                        "tick": contact.tick,
                        "seconds": seconds(contact.tick),
                        "player_id": pid,
                        "area": position.area,
                        "evidence_ids": contact.evidence_ids
                        + ([position.evidence_id] if position.evidence_id else []),
                    }
                )
        openings = []
        for eid in record.opening_kill_ids:
            kill = evidence[eid]
            attacker = {2: "T", 3: "CT"}.get(kill.data.get("attacker_team_num"))
            role = "kill" if attacker == side else "death"
            pid = str(kill.data.get("attacker_steamid" if role == "kill" else "user_steamid"))
            contact = next((c for c in record.contacts if eid in c.evidence_ids), None)
            position = (
                (contact.attacker_position if role == "kill" else contact.victim_position)
                if contact
                else None
            )
            openings.append(
                {
                    "role": role,
                    "player_id": pid,
                    "area": position.area if position else None,
                    "tick": kill.tick,
                    "seconds": seconds(kill.tick),
                    "evidence_ids": [eid]
                    + ([position.evidence_id] if position and position.evidence_id else []),
                }
            )
        throws = []
        for u in record.utility_contexts:
            if (
                u.side != side
                or u.throw_tick is None
                or record.freeze_end_tick is None
                or not 0 <= u.throw_tick - record.freeze_end_tick <= early_seconds * rate
            ):
                continue
            region = profile.regions_by_id.get(u.origin_area) if profile else None
            throws.append(
                {
                    "player_id": u.player_id,
                    "kind": u.kind,
                    "tick": u.throw_tick,
                    "seconds": seconds(u.throw_tick),
                    "origin_area": u.origin_area,
                    "origin_kind": region.kind if region else None,
                    "effect_area": u.effect_area,
                    "match_status": u.match_status,
                    "evidence_ids": u.evidence_ids,
                }
            )
        refrags = []
        for link in record.refrag_links:
            event = evidence[link.response_kill_id]
            if {2: "T", 3: "CT"}.get(event.data.get("attacker_team_num")) != side:
                continue
            refrags.append(
                {
                    "player_id": str(event.data.get("attacker_steamid")),
                    "tick": event.tick,
                    "seconds": seconds(event.tick),
                    "delay_seconds": link.delay_ticks / rate,
                    "response_kill_id": link.response_kill_id,
                    "initial_death_id": link.death_id,
                    "traded_player_id": str(evidence[link.death_id].data.get("user_steamid")),
                    "evidence_ids": link.evidence_ids,
                }
            )
        advantage = (
            any(
                (s.t_alive > s.ct_alive if side == "T" else s.ct_alive > s.t_alive)
                for s in record.alive_states
            )
            if all_alive_known
            else None
        )
        first_advantage = (
            next(
                (
                    s
                    for s in record.alive_states
                    if (s.t_alive > s.ct_alive if side == "T" else s.ct_alive > s.t_alive)
                ),
                None,
            )
            if advantage
            else None
        )
        last_alive = record.alive_states[-1] if all_alive_known else None
        sides[side] = {
            "team_id": record.teams_by_side.get(side),
            "roster": roster,
            "start_alive": (baseline.t_alive if side == "T" else baseline.ct_alive)
            if baseline
            else None,
            "equipment": _equipment(record, roster),
            "snapshots": {
                str(s.seconds): _snapshot(s, side, roster, profile) for s in prep.snapshots
            },
            "before_contact": _snapshot(prep.setup_before_contact, side, roster, profile),
            "first_firearm_contacts": first_contacts,
            "contacts_known": record.contacts_status in KNOWN,
            "contacts_status": str(record.contacts_status),
            "player_first_firearm_contacts": player_first_contacts,
            "opening": openings,
            "opening_known": record.freeze_end_tick is not None and source_known("kills"),
            "early_throws": throws,
            "early_throws_known": record.freeze_end_tick is not None and source_known("throws"),
            "refrags": refrags,
            "refrags_known": record.refrags_status in KNOWN,
            "had_advantage": advantage,
            "first_advantage_tick": first_advantage.tick if first_advantage else None,
            "advantage_evidence_ids": sorted(
                {eid for s in record.alive_states for eid in s.evidence_ids}
            )
            if all_alive_known
            else [],
            "end_alive_ids": sorted(set(last_alive.alive_ids) & set(roster))
            if last_alive
            else None,
        }
    return {
        "version": ROUND_FACTS_VERSION,
        "number": record.number,
        "start_tick": record.start_tick,
        "freeze_tick": record.freeze_end_tick,
        "end_tick": record.end_tick,
        "tick_rate": rate,
        "winner_side": record.winner_side,
        "winner_team_id": record.winner_team_id,
        "sides": sides,
        "ct_sectors": record.ct_sectors_before_contact,
        "entries": [
            {
                "site": entry.area,
                "tick": entry.start_tick,
                "seconds": seconds(entry.start_tick),
                "players": entry.participants,
                "evidence_ids": entry.evidence_ids,
            }
            for entry in record.observed_entries
        ],
        "early_seconds": early_seconds,
        "metadata": {
            key: metadata.get(key)
            for key in ("raw_total_rounds_played", "is_warmup_period", "reset", "phase")
        },
        **action_facts(record, evidence, profile, seconds),
    }


def comparable_rounds(facts):
    """No fixed halftime assumption. Unknown membership/reset history stays explicit."""
    result = []
    previous = None
    segment = 0
    for fact in sorted(facts, key=lambda f: f["number"]):
        identities = {side: value["team_id"] for side, value in fact["sides"].items()}
        complete_identity = (
            len(set(identities.values()) - {None}) == 2 and None not in identities.values()
        )
        raw, old_raw = (
            fact["metadata"].get("raw_total_rounds_played"),
            (previous["metadata"].get("raw_total_rounds_played") if previous else None),
        )
        boundary = (
            previous is None
            or fact["number"] != previous["number"] + 1
            or not complete_identity
            or identities != {side: data["team_id"] for side, data in previous["sides"].items()}
            or any(
                data["roster"] != previous["sides"][side]["roster"]
                for side, data in fact["sides"].items()
            )
            or fact["metadata"].get("reset") is True
            or fact["metadata"].get("is_warmup_period") is True
            or previous["metadata"].get("is_warmup_period") is True
            or raw is not None
            and old_raw is not None
            and raw <= old_raw
            or fact["metadata"].get("phase") != previous["metadata"].get("phase")
        )
        if boundary:
            segment += 1
        context = {
            "segment": segment,
            "previous_round": None if boundary else previous["number"],
            "reset_coverage": "explicit"
            if fact["metadata"].get("reset") is not None
            else "limited",
            "previous_result": {},
            "previous_survivors": {},
        }
        for side, data in fact["sides"].items():
            previous_winner = previous["winner_team_id"] if previous and not boundary else None
            context["previous_result"][side] = (
                ("win" if previous_winner == data["team_id"] else "loss")
                if (previous_winner is not None and data["team_id"] is not None)
                else None
            )
            context["previous_survivors"][side] = (
                previous["sides"][side]["end_alive_ids"] if previous and not boundary else None
            )
        result.append({**fact, "comparison": context})
        previous = fact
    return result
