"""Compact, deterministic round foundations from already collected evidence."""

from dataclasses import asdict
from hashlib import sha256

import pandas as pd

from src.demos.demo_analyzer import enemy_mask
from src.demos.foundation_sources import (
    BOMB_EVENTS,
    ECONOMY_PROPS,
    EQUIPMENT_GROUPS,
    inventory_counts,
)
from src.demos.observations import observations_key
from src.demos.round_index import RoundIndex
from src.demos.tactical_evidence import collect_evidence, records
from src.models.observations import RoundClock
from src.models.tactical import (
    Availability,
    ContactReference,
    EquipmentObservation,
    Evidence,
    RoundFoundation,
    SetupSnapshot,
    SourceQuality,
    Status,
    _decode,
)

FOUNDATION_VERSION = 2
FIREARMS = {
    "ak47",
    "aug",
    "awp",
    "bizon",
    "cz75a",
    "deagle",
    "elite",
    "famas",
    "fiveseven",
    "g3sg1",
    "galilar",
    "glock",
    "hkp2000",
    "m249",
    "m4a1",
    "m4a1_silencer",
    "mac10",
    "mag7",
    "mp5sd",
    "mp7",
    "mp9",
    "negev",
    "nova",
    "p250",
    "p90",
    "sawedoff",
    "scar20",
    "sg556",
    "ssg08",
    "tec9",
    "ump45",
    "usp_silencer",
    "xm1014",
    "revolver",
}


def foundation_key(analysis):
    return sha256(
        f"{observations_key(analysis)}:foundations:{FOUNDATION_VERSION}".encode()
    ).hexdigest()


def _quality(read_status, rows, required=(), *, complete=True):
    raw_status = read_status
    read_status = (
        "not_listed"
        if read_status in {"absent", "not_listed"}
        else "error"
        if read_status.startswith("error:")
        else read_status
    )
    if read_status not in {"ok", "not_listed", "unsupported", "error", "not_loaded"}:
        read_status = "not_loaded"
    missing = [key for key in required if rows and any(row.get(key) is None for row in rows)]
    ok = read_status == "ok"
    if not ok:
        status = Status.PARTIAL if rows else Status.UNKNOWN
        reasons = [f"Source read: {raw_status}; completeness unknown."]
    elif missing or not complete:
        status, reasons = Status.PARTIAL, ["Missing fields, roster members or sampling coverage."]
    else:
        status, reasons = (Status.OBSERVED if rows else Status.ABSENT), []
    fields = {
        key: "unknown" if not rows else "partial" if key in missing else "observed"
        for key in required
    }
    return SourceQuality(read_status, Availability(status, reasons, missing), len(rows), fields)


def _contact(events, kind, *, complete=False):
    if not events:
        return ContactReference(kind=kind, status=Status.ABSENT if complete else Status.UNKNOWN)
    first = min(e.tick for e in events)
    return ContactReference(
        first,
        kind,
        sorted(e.id for e in events if e.tick == first),
        Status.OBSERVED if complete else Status.PARTIAL,
    )


def _setup(expected, team, states, tick, freeze, *, tick_rate=64, index=None, evidence=None):
    players, refs, missing, counts = [], [], [], {}
    for pid in sorted(expected):
        lookup = (
            index.latest(
                tick,
                player_id=pid,
                max_age_ticks=round(tick_rate),
                max_gap_ticks=round(2 * tick_rate),
            )
            if index is not None
            else None
        )
        if lookup is not None:
            sample = evidence[lookup.row["event_id"]] if lookup.row else None
        else:
            sample = next(
                (
                    s
                    for s in reversed(states.get(pid, []))
                    if freeze <= s.tick <= tick and s.data.get("team_num") == team
                ),
                None,
            )
        if sample is None or tick - sample.tick > tick_rate or sample.data.get("is_alive") is None:
            missing.append(pid)
            continue
        alive = bool(sample.data["is_alive"])
        location = None  # Spatial interpretation belongs to the profile-dependent stage.
        if alive and any(sample.data.get(axis) is None for axis in ("X", "Y", "Z")):
            missing.append(pid)
        if location:
            counts[location] = counts.get(location, 0) + 1
        refs.append(sample.id)
        players.append(
            {
                "player_id": pid,
                "alive": alive,
                "area": location,
                "place": sample.data.get("last_place_name"),
                "position": {axis: sample.data.get(axis) for axis in ("X", "Y", "Z")},
                "sample_tick": sample.tick,
                "sample_age_ticks": tick - sample.tick,
                "has_bomb": sample.data.get("has_bomb"),
            }
        )
    status = (
        Status.UNKNOWN
        if not players
        else Status.PARTIAL
        if missing or len(expected) != 5
        else Status.OBSERVED
    )
    return SetupSnapshot((tick - freeze) / tick_rate, tick, status, players, counts, missing, refs)


def build_foundations(analysis, spatial, *, collected=None):
    frames, clocks, bounds, evidence, by_round, _ = collected or collect_evidence(analysis, spatial)
    source_reads = spatial.diagnostics.get("sources", {}) if spatial is not None else {}
    key = foundation_key(analysis)
    roster = records(analysis.round_roster_df)
    result = {}
    for rnd, (start, end) in bounds.items():
        freeze = clocks.get(rnd)
        freeze = int(freeze) if freeze is not None and freeze == freeze else None
        events = [evidence[eid] for eid in by_round[rnd]]
        grouped = {}
        for event in events:
            grouped.setdefault(event.source, []).append(event)
        for source in grouped:
            grouped[source].sort(key=lambda e: e.tick)
        people = [r for r in roster if r.get("total_rounds_played") == rnd]
        expected = {str(p["steamid"]) for p in people if p.get("team_num") in {2, 3}}
        coverage = (
            spatial.diagnostics.get("equipment_coverage", {}).get(
                str(rnd), spatial.diagnostics.get("equipment_coverage", {}).get(rnd, {})
            )
            if spatial is not None
            else {}
        )
        clock_rows = getattr(spatial, "clock", pd.DataFrame())
        clock_row = (
            clock_rows[clock_rows.total_rounds_played.eq(rnd)].iloc[0].to_dict()
            if not clock_rows.empty
            else {
                "total_rounds_played": rnd,
                "start_tick": start,
                "freeze_tick": freeze,
                "tick": end,
            }
        )
        round_clock = RoundClock.from_row(clock_row)
        coverage_ok = (
            len(expected) == 10
            and freeze is not None
            and all(
                pid in coverage
                and coverage[pid]["first_tick"] <= freeze
                and coverage[pid]["last_tick"] >= end - round_clock.ticks(1)
                and not coverage[pid].get("gaps")
                for pid in expected
            )
        )
        foundation = RoundFoundation(
            analysis.content_hash,
            rnd,
            key,
            {
                "start_tick": start,
                "freeze_tick": freeze,
                "end_tick": end,
                "tick_rate": round_clock.tick_rate,
                "time_basis": round_clock.time_source,
            },
            equipment_coverage=coverage,
        )
        equipment = grouped.get("equipment", [])
        econ = {
            str(e.data.get("steamid")): e for e in grouped.get("economy", []) if e.tick == freeze
        }
        for event in equipment:
            row = event.data
            pid = str(row.get("steamid"))
            economy = econ.get(pid) if event.tick == freeze else None
            obs = EquipmentObservation(
                pid,
                event.tick,
                row.get("team_num"),
                inventory_counts(row.get("inventory")),
                row.get("active_weapon_name"),
                row.get("armor_value"),
                row.get("has_helmet"),
                row.get("has_defuser"),
                {prop: economy.data.get(prop) for prop in ECONOMY_PROPS} if economy else {},
                [event.id, *([economy.id] if economy else [])],
            )
            (
                foundation.equipment_start if event.tick == freeze else foundation.equipment_changes
            ).append(obs)
        for group, props in EQUIPMENT_GROUPS.items():
            foundation.source_quality[f"equipment_{group}"] = _quality(
                source_reads.get(f"equipment_{group}", "not_loaded"),
                [e.data for e in equipment],
                ["team_num", *props],
                complete=coverage_ok,
            )
        foundation.source_quality["equipment_economy"] = _quality(
            source_reads.get("equipment_economy", "not_loaded"),
            [e.data for e in econ.values()],
            ["team_num", *ECONOMY_PROPS],
            complete=len(econ) == len(expected) == 10,
        )
        foundation.bomb_event_ids = [e.id for e in events if e.source in {"bombs", "bomb_updates"}]
        for event_name in BOMB_EVENTS:
            foundation.source_quality[event_name] = _quality(
                source_reads.get(event_name, "not_loaded"),
                [
                    e.data
                    for e in events
                    if e.id in foundation.bomb_event_ids and e.data.get("event") == event_name
                ],
                ("tick",),
            )
        for source, attribute in (
            ("shots", "shot_event_ids"),
            ("throws", "thrown_utility_ids"),
            ("utility_lifecycles", "utility_lifecycle_ids"),
        ):
            setattr(foundation, attribute, [e.id for e in grouped.get(source, [])])
            read = source_reads.get("weapon_fire", "not_loaded")
            if source == "utility_lifecycles":
                statuses = [
                    source_reads.get(name, "not_loaded")
                    for name in (
                        "smokegrenade_detonate",
                        "flashbang_detonate",
                        "hegrenade_detonate",
                        "inferno_startburn",
                    )
                ]
                read = "ok" if all(s == "ok" for s in statuses) else "partial"
            foundation.source_quality[source] = _quality(
                read,
                [e.data for e in grouped.get(source, [])],
                ("tick",),
            )
        damages = [
            e
            for e in grouped.get("damage", [])
            if freeze is not None and e.tick >= freeze and (e.data.get("enemy_damage") or 0) > 0
        ]
        firearm = [
            e for e in damages if str(e.data.get("weapon", "")).removeprefix("weapon_") in FIREARMS
        ]
        enemy_kills = frames["kills"][enemy_mask(frames["kills"])]
        kill_ids = set(enemy_kills.event_id) if "event_id" in enemy_kills else set()
        kills = [
            e
            for e in grouped.get("kills", [])
            if e.id in kill_ids and freeze is not None and e.tick >= freeze
        ]
        foundation.contact_references = {
            "first_enemy_damage": _contact(damages, "enemy_damage"),
            "first_firearm_damage": _contact(firearm, "firearm_damage"),
            "first_enemy_kill": _contact(kills, "enemy_kill"),
            "preparation_reference": _contact(damages + kills, "first_observed_enemy_contact"),
        }
        ref = foundation.contact_references["preparation_reference"]
        if ref.tick is not None and freeze is not None:
            states = {}
            for event in grouped.get("states", []):
                states.setdefault(str(event.data.get("steamid")), []).append(event)
            state_frame = pd.DataFrame(
                [
                    {**event.data, "tick": event.tick, "event_id": event.id}
                    for samples in states.values()
                    for event in samples
                ]
            )
            index = RoundIndex(state_frame)
            for side, team in (("T", 2), ("CT", 3)):
                side_people = {str(p["steamid"]) for p in people if p.get("team_num") == team}
                foundation.setup_before_contact[side] = _setup(
                    side_people,
                    team,
                    states,
                    ref.tick - 1,
                    freeze,
                    tick_rate=round_clock.tick_rate,
                    index=index,
                    evidence=evidence,
                )
        result[rnd] = foundation
    return result, evidence


def foundation_payload(foundation, evidence):
    refs = set(
        foundation.bomb_event_ids
        + foundation.shot_event_ids
        + foundation.utility_lifecycle_ids
        + foundation.thrown_utility_ids
    )
    for observation in foundation.equipment_start + foundation.equipment_changes:
        refs.update(observation.evidence_ids)
    for reference in foundation.contact_references.values():
        refs.update(reference.evidence_ids)
    for snapshot in foundation.setup_before_contact.values():
        refs.update(snapshot.evidence_ids)
    pending = list(refs)
    while pending:
        event = evidence[pending.pop()]
        for eid in event.data.get("evidence_ids", []):
            if eid not in refs:
                refs.add(eid)
                pending.append(eid)
    return {
        "foundation": asdict(foundation),
        "evidence": {eid: asdict(evidence[eid]) for eid in sorted(refs)},
    }


def decode_foundation(payload):
    value = payload["foundation"]
    if value.get("schema_version") != FOUNDATION_VERSION:
        raise ValueError("Unsupported foundation version")
    foundation = _decode(RoundFoundation, value)
    evidence = {eid: _decode(Evidence, row) for eid, row in payload["evidence"].items()}
    from src.models.tactical import _validate_references

    _validate_references(foundation, evidence, foundation.round_number)
    if any(
        e.round_number != foundation.round_number
        or not foundation.clock["start_tick"] <= e.tick <= foundation.clock["end_tick"]
        for e in evidence.values()
    ):
        raise ValueError("Cross-round foundation evidence")
    for event in evidence.values():
        _validate_references(event, evidence, foundation.round_number)
    return foundation, evidence


def equipment_at(foundation, player_id, tick, *, max_age_ticks=None):
    """Resolve a compressed state only inside continuously sampled coverage."""
    max_age_ticks = max_age_ticks or round(foundation.clock["tick_rate"])
    cov = foundation.equipment_coverage.get(str(player_id))
    if not cov or not cov["first_tick"] <= tick <= cov["last_tick"]:
        return None
    if any(start < tick < end for start, end in cov.get("gaps", [])):
        return None
    samples = [
        s
        for s in foundation.equipment_start + foundation.equipment_changes
        if s.player_id == str(player_id) and s.tick <= tick
    ]
    if not samples:
        return None
    state = max(samples, key=lambda s: s.tick)
    # Compression keeps unchanged observations; coverage bounds the sampling age.
    age_bound = min(tick - cov["first_tick"], cov.get("max_gap_ticks") or 0)
    if age_bound > max_age_ticks:
        return None
    return {
        "observation": state,
        "last_change_tick": state.tick,
        "sample_age_upper_bound_ticks": age_bound,
        "money_observed_at_tick": state.tick if state.economy else None,
    }
