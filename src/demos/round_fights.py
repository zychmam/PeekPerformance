"""Local contact episodes. Measured effects and contextual utility stay separate."""

from math import dist, isfinite

from src.demos.tactical_ids import action_id
from src.models.tactical import Episode, Fight, Status

FIGHTS_VERSION = 2
FIGHT_GAP_SECONDS = 5.0
LOCAL_RADIUS = 600.0


def point(data):
    values = [data.get(axis, data.get(axis.lower())) for axis in ("X", "Y", "Z")]
    try:
        return (
            tuple(float(v) for v in values)
            if all(v is not None and isfinite(float(v)) for v in values)
            else None
        )
    except (TypeError, ValueError):
        return None


def contact_point(contact, evidence):
    pos = contact.victim_position
    return point(evidence[pos.evidence_id].data) if pos.evidence_id else None


def _local(first, second, evidence):
    a, b = contact_point(first, evidence), contact_point(second, evidence)
    shared = bool({first.attacker_id, first.victim_id} & {second.attacker_id, second.victim_id})
    if {first.attacker_id, first.victim_id} == {second.attacker_id, second.victim_id}:
        return True  # Long-range duels remain exchanges when roles reverse.
    if a is not None and b is not None:
        return dist(a, b) <= LOCAL_RADIUS
    return shared


def enrich_fights(record, evidence, profile, *, tick_rate, resources):
    groups = []
    for contact in sorted(record.contacts, key=lambda c: (c.tick, c.id)):
        matching = [
            group
            for group in groups
            if any(
                0 <= contact.tick - previous.tick <= round(FIGHT_GAP_SECONDS * tick_rate)
                and _local(contact, previous, evidence)
                for previous in reversed(group)
            )
        ]
        if not matching:
            groups.append([contact])
        else:
            target = matching[0]
            target.append(contact)
            for other in matching[1:]:
                target.extend(other)
                groups.remove(other)
    record.fights = []
    for group in groups:
        group.sort(key=lambda c: (c.tick, c.id))
        refs = sorted({eid for contact in group for eid in contact.evidence_ids})
        participants = sorted(
            {pid for contact in group for pid in (contact.attacker_id, contact.victim_id)}
        )
        kills = sorted(
            (eid for eid in refs if evidence[eid].source == "kills"),
            key=lambda eid: (evidence[eid].tick, eid),
        )
        opening = (
            [eid for eid in kills if evidence[eid].tick == evidence[kills[0]].tick] if kills else []
        )
        areas = {c.victim_position.area for c in group if c.victim_position.area}
        area = next(iter(areas)) if len(areas) == 1 else None
        position_refs = {
            pos.evidence_id
            for c in group
            for pos in (c.attacker_position, c.victim_position)
            if pos.evidence_id
        }
        status = (
            Status.OBSERVED
            if all(contact_point(c, evidence) is not None for c in group)
            else Status.PARTIAL
        )
        eid = action_id("fight", record.number, *(c.id for c in group))
        episode = Episode(
            eid,
            "local_fight",
            group[0].tick,
            group[-1].tick,
            participants,
            sorted(set(refs) | position_refs),
            status=status,
            area=area,
        )
        before = resources.at(max(record.freeze_end_tick, group[0].tick - 1))
        after = resources.at(group[-1].tick)
        # Source HP and counts retain their sample timestamps. Damage totals
        # count normalized contacts once, never add kills as extra damage.
        before = {**before, "local_participants": participants}
        after = {
            **after,
            "local_participants": participants,
            "damage_by_side": {
                side: sum(c.actual_damage or 0 for c in group if c.attacker_side == side)
                for side in ("T", "CT")
            },
            "unknown_damage_contacts": sum(c.actual_damage is None for c in group),
            "deaths_by_side": {
                side: sum(evidence[k].data.get("user_team_num") == team for k in kills)
                for side, team in (("T", 2), ("CT", 3))
            },
        }
        linked = [
            asdict_link(link)
            for link in record.refrag_links
            if link.death_id in kills and link.response_kill_id in kills
        ]
        contextual, effects = [], []
        for utility in record.utility_contexts:
            measured = [ref for ref in utility.effect_ids if ref in refs]
            effects.extend(measured)
            pos = point(utility.effect_position)
            nearby = (area is not None and utility.effect_area == area) or (
                pos is not None
                and any(
                    contact_point(c, evidence) is not None
                    and dist(pos, contact_point(c, evidence)) <= LOCAL_RADIUS
                    for c in group
                )
            )
            if (
                utility.effect_tick is not None
                and nearby
                and (
                    group[0].tick - 8 * tick_rate <= utility.effect_tick <= group[-1].tick
                    or utility.end_tick is not None
                    and utility.effect_tick <= group[0].tick <= utility.end_tick
                )
            ):
                contextual.append(utility.id)
        record.fights.append(
            Fight(
                episode,
                area=area,
                opening_kill_id=opening[0] if len(opening) == 1 else None,
                round_opening=any(k in record.opening_kill_ids for k in kills),
                response_window_end=min(
                    record.end_tick, evidence[opening[0]].tick + round(5 * tick_rate)
                )
                if opening
                else None,
                utility_ids=sorted(
                    {
                        ref
                        for u in record.utility_contexts
                        if u.id in contextual
                        for ref in u.evidence_ids
                    }
                ),
                kill_ids=kills,
                damage_ids=[eid for eid in refs if evidence[eid].source == "damage"],
                refrags=linked,
                before=before,
                after=after,
                contact_ids=[c.id for c in group],
                opening_kill_ids=opening,
                utility_context_ids=contextual,
                utility_effect_ids=sorted(set(effects)),
            )
        )
    record.fights.sort(key=lambda f: (f.episode.start_tick, f.episode.id))
    record.fights_status = (
        record.contacts_status
        if record.fights
        else Status.ABSENT
        if record.contacts_status == Status.ABSENT
        else Status.UNKNOWN
    )


def asdict_link(link):
    return {
        "death_id": link.death_id,
        "response_kill_id": link.response_kill_id,
        "delay_ticks": link.delay_ticks,
        "evidence_ids": link.evidence_ids,
    }
