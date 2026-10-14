"""Throw/effect links: identity when present, otherwise explicit limited matching."""

from collections import Counter

from src.demos.tactical_ids import action_id
from src.maps.resolver import resolve_region
from src.models.tactical import Status, UtilityContext

UTILITY_CONTEXT_VERSION = 1
WEAPONS = {
    "hegrenade": "HE",
    "flashbang": "Flash",
    "molotov": "Ogień",
    "incgrenade": "Ogień",
    "inferno": "Ogień",
    "smokegrenade": "Smoke",
}


def _side(row):
    return {2: "T", 3: "CT"}.get(row.get("user_team_num"))


def _origin(event, index, profile, tick_rate):
    row = event.data
    lookup = index.before(
        event.tick,
        player_id=str(row.get("user_steamid")),
        max_age_ticks=round(tick_rate),
        max_gap_ticks=round(2 * tick_rate),
    )
    origin = resolve_region(lookup.row, profile) if lookup.row else None
    return origin, ([str(lookup.row["event_id"])] if lookup.row else [])


def enrich_utility(record, evidence, profile, *, tick_rate, state_index):
    record.utility_contexts = []
    throws = [
        evidence[eid]
        for eid in record.event_ids
        if evidence[eid].source == "throws"
        and record.freeze_end_tick is not None
        and evidence[eid].tick >= record.freeze_end_tick
    ]
    effects = [
        evidence[eid]
        for eid in record.event_ids
        if evidence[eid].source == "utility_lifecycles"
        and record.freeze_end_tick is not None
        and evidence[eid].tick >= record.freeze_end_tick
    ]
    contexts = {}
    for event in throws:
        origin, refs = _origin(event, state_index, profile, tick_rate)
        item = UtilityContext(
            action_id("utility_context", record.number, event.id),
            str(event.data.get("user_steamid")) if event.data.get("user_steamid") else None,
            _side(event.data),
            str(event.data.get("kind") or "unknown"),
            throw_tick=event.tick,
            origin_area=origin,
            evidence_ids=[event.id, *refs],
        )
        contexts[event.id] = item
        item.origin_position = {axis: event.data.get("user_" + axis) for axis in ("X", "Y", "Z")}
    candidate_lists = []
    identity_matches = []
    for event in effects:
        row = event.data
        candidate = [
            throw
            for throw in throws
            if throw.data.get("user_steamid") is not None
            and throw.data.get("user_steamid") == row.get("user_steamid")
            and throw.data.get("kind") == row.get("kind")
            and 0 <= event.tick - throw.tick <= 20 * tick_rate
        ]
        exact = [
            throw
            for throw in candidate
            if row.get("entityid") is not None and throw.data.get("entityid") == row.get("entityid")
        ]
        candidate_lists.append(exact or candidate)
        identity_matches.append(bool(exact))
    usage = Counter(throw.id for candidates in candidate_lists for throw in candidates)
    for event, candidates, identity in zip(effects, candidate_lists, identity_matches, strict=True):
        unique = len(candidates) == 1 and usage[candidates[0].id] == 1
        item = (
            contexts[candidates[0].id]
            if unique
            else UtilityContext(
                action_id("utility_effect", record.number, event.id),
                str(event.data.get("user_steamid")) if event.data.get("user_steamid") else None,
                _side(event.data),
                str(event.data.get("kind") or "unknown"),
            )
        )
        item.effect_tick = event.tick
        item.effect_area = resolve_region(event.data, profile)
        item.effect_position = {axis: event.data.get(axis.lower()) for axis in ("X", "Y", "Z")}
        item.match_status = (
            ("entity_identity" if identity else "unique_temporal_limited")
            if unique
            else ("ambiguous" if candidates else "unknown")
        )
        item.candidates = [throw.id for throw in candidates]
        end = event.data.get("end_tick")
        # Estimated display expiry is deliberately excluded.
        if end is not None and event.data.get("end_source") in {"event", "instant_effect"}:
            item.end_tick = min(record.end_tick, int(end))
            item.end_source = event.data["end_source"]
        item.evidence_ids.append(event.id)
        if not unique:
            record.utility_contexts.append(item)
    record.utility_contexts.extend(contexts.values())
    # A measurable effect is assigned only to a unique active source. Effects
    # without a unique grenade remain contacts/blinds, never discarded.
    for eid in record.event_ids:
        event = evidence[eid]
        if event.source not in {"damage", "blinds"}:
            continue
        row = event.data
        kind = (
            "Flash"
            if event.source == "blinds"
            else WEAPONS.get(str(row.get("weapon", "")).removeprefix("weapon_"))
        )
        if not kind:
            continue
        candidates = [
            item
            for item in record.utility_contexts
            if item.kind == kind
            and item.player_id == str(row.get("attacker_steamid"))
            and item.effect_tick is not None
            and (
                item.effect_tick == event.tick
                if kind in {"Flash", "HE"}
                else item.end_tick is not None and item.effect_tick <= event.tick <= item.end_tick
            )
        ]
        if len(candidates) == 1:
            candidates[0].effect_ids.append(eid)
    sources = [record.availability.get(name) for name in ("throws", "utility_lifecycles")]
    complete = all(
        source and source.status in {Status.OBSERVED, Status.ABSENT} for source in sources
    )
    record.utility_context_status = (
        (Status.OBSERVED if complete else Status.PARTIAL)
        if record.utility_contexts
        else (Status.ABSENT if complete else Status.UNKNOWN)
    )
    for prep in (record.t_preparation, record.ct_setup):
        for utility in prep.utility:
            utility.area = resolve_region(utility.position, profile)
