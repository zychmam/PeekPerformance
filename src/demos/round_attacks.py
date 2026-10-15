"""Observed attack attempts, not inferred tactical intentions or strategy labels."""

from math import dist

from src.demos.bomb_coverage import event_known
from src.demos.round_fights import LOCAL_RADIUS, point
from src.demos.tactical_ids import action_id
from src.models.tactical import Attack, Episode, Status

ATTACKS_VERSION = 4
WITHDRAWAL_SECONDS = 3.0


def target_sites(region):
    if region is None:
        return set()
    if region.kind == "site":
        return {region.site_id}
    return set(region.route_names) if region.kind == "approach" else set()


def concentration(members, tick, state_index, tick_rate):
    points = {}
    for pid in members:
        sample = state_index.latest(
            tick, player_id=pid, max_age_ticks=round(tick_rate), max_gap_ticks=round(2 * tick_rate)
        ).row
        if sample and sample.get("is_alive") == 1 and point(sample):
            points[pid] = point(sample)
    groups = []
    remaining = set(points)
    while remaining:
        group = {min(remaining)}
        remaining -= group
        while True:
            nearby = {
                pid
                for pid in remaining
                if any(dist(points[pid], points[other]) <= LOCAL_RADIUS for other in group)
            }
            if not nearby:
                break
            group |= nearby
            remaining -= nearby
        groups.append(sorted(group))
    groups.sort(key=lambda group: (-len(group), group))
    if not groups or len(groups[0]) < 2 or len(groups) > 1 and len(groups[0]) == len(groups[1]):
        return []
    return groups[0]


def enrich_attacks(record, evidence, profile, *, tick_rate, movements, state_index):
    record.attacks, record.t_pressure = [], []
    if not profile or record.freeze_end_tick is None or not profile.supports("site_boundaries"):
        record.attacks_status = Status.UNKNOWN
        return
    regions = profile.regions_by_id
    sides = {p.player_id: p.side for p in record.players}
    plants = [
        evidence[eid]
        for eid in record.bomb_event_ids
        if evidence[eid].data.get("event") == "bomb_planted"
    ]
    stop = min((event.tick for event in plants), default=record.end_tick)
    kills = [
        evidence[eid]
        for eid in record.event_ids
        if evidence[eid].source == "kills" and evidence[eid].tick >= record.freeze_end_tick
    ]
    death_ticks = {}
    for event in kills:
        pid = str(event.data.get("user_steamid"))
        death_ticks[pid] = min(death_ticks.get(pid, event.tick), event.tick)
    # One-second sweep plus exact observed transitions and contacts; no reparse.
    ticks = set(range(record.freeze_end_tick, stop + 1, max(1, round(tick_rate)))) | {stop}
    ticks.update(
        stay.start_tick
        for stay in record.region_stays
        if stay.side == "T" and stay.start_tick <= stop
    )
    ticks.update(c.tick for c in record.contacts if c.tick <= stop)
    ticks.update(
        u.effect_tick
        for u in record.utility_contexts
        if u.effect_tick is not None and u.effect_tick <= stop
    )
    active = {}
    pressure_seen = set()
    last_seen = {}
    missing_since = {}

    def finish(site, tick, reason):
        attack = active.pop(site)
        attack.episode.end_tick = max(attack.episode.start_tick, tick)
        attack.end_reason = reason
        if reason == "gap":
            attack.episode.status = Status.PARTIAL
        record.attacks.append(attack)

    for tick in sorted(t for t in ticks if record.freeze_end_tick <= t <= stop):
        positions = {pid: movements.at(pid, tick) for pid, side in sides.items() if side == "T"}
        known = {
            pid: stay
            for pid, stay in positions.items()
            if stay and stay.area and death_ticks.get(pid, stop + 1) > tick
        }
        by_site = {}
        for pid, stay in known.items():
            for site in target_sites(regions.get(stay.area)):
                by_site.setdefault(site, []).append(pid)
        for site, attack in list(active.items()):
            members = [pid for pid in by_site.get(site, []) if pid in attack.episode.participants]
            alive_members = [pid for pid in attack.episode.participants if pid in known]
            deaths = [
                event
                for event in kills
                if str(event.data.get("user_steamid")) in attack.episode.participants
                and attack.episode.start_tick <= event.tick <= tick
            ]
            anchor = attack.main_group or attack.episode.participants
            living_anchor = [pid for pid in anchor if death_ticks.get(pid, stop + 1) > tick]
            required = min(2, len(living_anchor))
            holding = set(members) & set(living_anchor)
            if required and len(holding) >= required:
                last_seen[site] = tick
                missing_since.pop(site, None)
                attack.episode.end_tick = tick
                attack.episode.participants = sorted(
                    set(attack.episode.participants) | set(by_site.get(site, []))
                )
                continue
            dead_members = {str(d.data.get("user_steamid")) for d in deaths}
            if set(attack.episode.participants) - set(alive_members) - dead_members:
                missing_since.setdefault(site, tick)
                if tick - missing_since[site] >= tick_rate:
                    finish(site, last_seen[site], "gap")
            elif tick - last_seen[site] >= WITHDRAWAL_SECONDS * tick_rate:
                attack.episode.evidence_ids = sorted(
                    set(attack.episode.evidence_ids)
                    | {ref for pid in alive_members for ref in known[pid].evidence_ids}
                    | {death.id for death in deaths}
                )
                finish(site, last_seen[site], "stopped" if not alive_members else "withdrawn")
        for site, members in sorted(by_site.items()):
            if site in active:
                continue
            site_players = [pid for pid in members if regions[known[pid].area].kind == "site"]
            recent_contacts = [
                c
                for c in record.contacts
                if tick - 2 * tick_rate <= c.tick <= tick
                and ({c.attacker_id, c.victim_id} & set(members))
                and (
                    c.victim_position.area in {known[pid].area for pid in members}
                    or c.attacker_position.area in {known[pid].area for pid in members}
                )
            ]
            recent_utility = []
            for utility in record.utility_contexts:
                if (
                    utility.side != "T"
                    or utility.effect_tick is None
                    or not tick - 5 * tick_rate <= utility.effect_tick <= tick
                ):
                    continue
                position = point(utility.effect_position)
                nearby = utility.effect_area in {known[pid].area for pid in members}
                if not nearby and position:
                    for pid in members:
                        sample = state_index.latest(
                            tick,
                            player_id=pid,
                            max_age_ticks=round(tick_rate),
                            max_gap_ticks=round(2 * tick_rate),
                        ).row
                        p = point(sample) if sample else None
                        nearby |= p is not None and dist(p, position) <= LOCAL_RADIUS
                if nearby:
                    recent_utility.append(utility)
            moving = [
                tr
                for tr in record.region_transitions
                if tr.player_id in members
                and tick - 5 * tick_rate <= tr.arrival_tick <= tick
                and site in target_sites(regions.get(tr.to_area))
            ]
            # No frag or plant necessary; isolated utility/approach is pressure.
            coordinated = (
                len(members) >= 3
                and len({tr.player_id for tr in moving}) >= 2
                and len(recent_utility) >= 2
            )
            strong = (
                bool(site_players) or len(members) >= 2 and bool(recent_contacts) or coordinated
            )
            refs = sorted(
                {
                    ref
                    for pid in members
                    for ref in known[pid].evidence_ids
                    if evidence[ref].tick <= tick
                }
            )
            refs.extend(ref for c in recent_contacts for ref in c.evidence_ids)
            refs.extend(
                ref
                for utility in recent_utility
                for ref in utility.evidence_ids
                if evidence[ref].tick <= tick
            )
            if not strong:
                if site not in pressure_seen and refs:
                    record.t_pressure.append(
                        Episode(
                            action_id("pressure", record.number, site, tick),
                            "approach_presence",
                            tick,
                            tick,
                            sorted(members),
                            sorted(set(refs)),
                            status=Status.PARTIAL,
                            area=site,
                        )
                    )
                    pressure_seen.add(site)
                continue
            eid = action_id("attack", record.number, site, tick)
            active[site] = Attack(
                Episode(
                    eid,
                    "attack_attempt",
                    tick,
                    tick,
                    sorted(members),
                    sorted(set(refs)),
                    status=Status.PARTIAL
                    if record.movement_status != Status.OBSERVED
                    else Status.OBSERVED,
                    area=site,
                ),
                target_site=site,
                main_group=concentration(members, tick, state_index, tick_rate),
                start_seconds=(tick - record.freeze_end_tick) / tick_rate,
                start_basis="site_presence"
                if site_players
                else "group_contact"
                if recent_contacts
                else "group_movement_utility",
            )
            last_seen[site] = tick
    for site in list(active):
        finish(site, stop, "plant" if plants else "round_end")
    record.attacks.sort(key=lambda a: (a.episode.start_tick, a.target_site, a.episode.id))
    for i, attack in enumerate(record.attacks):
        start, end = attack.episode.start_tick, attack.episode.end_tick
        site = attack.target_site
        entries = [
            stay
            for stay in record.region_stays
            if stay.side == "T"
            and regions.get(stay.area)
            and regions[stay.area].kind == "site"
            and regions[stay.area].site_id == site
            and start <= stay.start_tick <= end
        ]
        attack.entry_ids = [stay.id for stay in entries]
        attack.first_entry_tick = min((stay.start_tick for stay in entries), default=None)
        first_per_player = {
            pid: min(s.start_tick for s in entries if s.player_id == pid)
            for pid in {s.player_id for s in entries}
        }
        attack.entry_spread_seconds = (
            (max(first_per_player.values()) - attack.first_entry_tick) / tick_rate
            if entries
            else None
        )
        attack.fight_ids = [
            fight.episode.id
            for fight in record.fights
            if start <= fight.episode.end_tick
            and fight.episode.start_tick <= end
            and set(attack.episode.participants) & set(fight.episode.participants)
        ]
        attack.utility_context_ids = [
            u.id
            for u in record.utility_contexts
            if u.side == "T"
            and u.throw_tick is not None
            and start - 8 * tick_rate <= u.throw_tick <= end
            and (
                u.effect_area is not None
                and site in target_sites(regions.get(u.effect_area))
                or u.player_id in attack.episode.participants
            )
        ]
        attack.entry_outcome = (
            "observed_presence"
            if entries
            else "not_observed"
            if attack.episode.status == Status.OBSERVED
            else "unknown"
        )
        planted = [
            p
            for p in plants
            if start <= p.tick <= end and bomb_site(p, profile, state_index, tick_rate) == site
        ]
        attack.plant_id = planted[0].id if planted else None
        attack.plant_outcome = (
            "planted"
            if planted
            else (
                "not_observed"
                if event_known(record, "bomb_planted")
                else "unknown"
            )
        )
        attack.round_outcome = record.winner_side
        attack.outcome = (
            "planted"
            if planted
            else "entered"
            if entries
            else attack.end_reason
            if attack.end_reason in {"stopped", "withdrawn"}
            else "unknown"
        )
        attack.previous_attack_id = record.attacks[i - 1].episode.id if i else None
        alive = next((s for s in reversed(record.alive_states) if s.tick <= start), None)
        attack.alive_t_at_start = (
            alive.t_alive if alive and alive.status == Status.OBSERVED else None
        )
        refs = set(attack.episode.evidence_ids)
        refs.update(ref for stay in entries for ref in stay.evidence_ids)
        refs.update(p.id for p in planted)
        refs.update(
            ref
            for fight in record.fights
            if fight.episode.id in attack.fight_ids
            for ref in fight.episode.evidence_ids
        )
        attack.episode.evidence_ids = sorted(refs)
        # Only confirmed stable-region periods, not an assumption of a pause in aim/movement.
        tempo_player = attack.main_group[0] if attack.main_group else attack.episode.participants[0]
        attack.tempo_reference_player_id = tempo_player
        attack.region_hold_seconds = sum(
            max(0, min(end, stay.end_tick) - max(start, stay.start_tick)) / tick_rate
            for stay in record.region_stays
            if stay.player_id == tempo_player and stay.end_tick - stay.start_tick >= 2 * tick_rate
        )
        samples = state_index.between(start, end, player_id=tempo_player)
        attack.pauses_seconds = sum(
            (b["tick"] - a["tick"]) / tick_rate
            for a, b in zip(samples, samples[1:], strict=False)
            if 0 < b["tick"] - a["tick"] <= tick_rate / 2
            and point(a)
            and point(b)
            and dist(point(a), point(b)) <= 32 * (b["tick"] - a["tick"]) / tick_rate
        )
    record.attacks_status = (
        (Status.PARTIAL if record.movement_status != Status.OBSERVED else Status.OBSERVED)
        if record.attacks
        else (
            Status.ABSENT
            if record.movement_status == Status.OBSERVED
            and record.contacts_status in {Status.OBSERVED, Status.ABSENT}
            else Status.UNKNOWN
        )
    )


def bomb_site(event, profile, state_index, tick_rate):
    # Numeric event site IDs are engine entity indices, not universal A/B enums.
    site = event.data.get("site")
    sites = {r.site_id for r in profile.regions if r.kind == "site"}
    if site in sites:
        return site
    lookup = state_index.before(
        event.tick,
        player_id=str(event.data.get("user_steamid")),
        max_age_ticks=round(tick_rate),
        max_gap_ticks=round(2 * tick_rate),
    )
    if lookup.row:
        from src.maps.resolver import resolve_region

        region = profile.regions_by_id.get(resolve_region(lookup.row, profile))
        return region.site_id if region and region.kind == "site" else None
    return None


def enrich_detached(record, evidence, profile, *, tick_rate, movements, state_index):
    if not profile:
        return
    regions = profile.regions_by_id
    t_ids = [p.player_id for p in record.players if p.side == "T"]
    for attack in record.attacks:
        start, end = attack.episode.start_tick, attack.episode.end_tick
        ticks = set(range(start, end + 1, max(1, round(tick_rate)))) | {end}
        ticks.update(
            s.start_tick
            for s in record.region_stays
            if s.side == "T" and start <= s.start_tick <= end
        )
        ticks = sorted(ticks)
        intervals = {pid: [] for pid in t_ids}
        joined = {}
        for left, right in zip(ticks, ticks[1:], strict=False):
            stays = {pid: movements.at(pid, left) for pid in t_ids}
            candidates = [
                pid
                for pid, stay in stays.items()
                if stay and attack.target_site in target_sites(regions.get(stay.area))
            ]
            main = concentration(candidates, left, state_index, tick_rate)
            if not main:
                continue
            for pid in main:
                if intervals[pid]:
                    joined.setdefault(pid, left)
            for pid, stay in stays.items():
                if not stay or not stay.area or pid in main or right > stay.end_tick:
                    continue
                own = intervals[pid]
                refs = list(stay.evidence_ids)
                refs.extend(ref for member in main for ref in stays[member].evidence_ids)
                if own and own[-1]["area"] == stay.area and own[-1]["end_tick"] == left:
                    own[-1]["end_tick"] = right
                    own[-1]["evidence_ids"] = sorted(set(own[-1]["evidence_ids"] + refs))
                else:
                    own.append(
                        {
                            "start_tick": left,
                            "end_tick": right,
                            "area": stay.area,
                            "evidence_ids": sorted(set(refs)),
                        }
                    )
        attack.detached_actions = []
        for pid, own in intervals.items():
            own = [item for item in own if item["end_tick"] - item["start_tick"] >= tick_rate]
            for item in own:
                contacts = [
                    c
                    for c in record.contacts
                    if item["start_tick"] <= c.tick <= item["end_tick"]
                    and pid in {c.attacker_id, c.victim_id}
                ]
                utility = [
                    u
                    for u in record.utility_contexts
                    if u.player_id == pid
                    and u.throw_tick is not None
                    and item["start_tick"] <= u.throw_tick <= item["end_tick"]
                ]
                item["contact_ids"] = [c.id for c in contacts]
                item["utility_context_ids"] = [u.id for u in utility]
                item["evidence_ids"] = sorted(
                    set(
                        item["evidence_ids"]
                        + [ref for c in contacts for ref in c.evidence_ids]
                        + [ref for u in utility for ref in u.evidence_ids]
                    )
                )
            if own:
                attack.detached_actions.append(
                    {
                        "player_id": pid,
                        "intervals": own,
                        "joined_tick": joined.get(pid),
                        "rotation_contact_ids": [],
                    }
                )
        attack.detached_players = [item["player_id"] for item in attack.detached_actions]
