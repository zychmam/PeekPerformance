"""One canonical evidence namespace shared by foundations and tactical reports."""

import json
from hashlib import sha256

import pandas as pd

from src.demos.coach_data import build_coach_inputs
from src.demos.observations import source_records
from src.models.observations import RoundClock
from src.models.tactical import Evidence


def records(frame):
    safe = frame.copy()
    for col in safe:
        if str(col).lower().replace("_", "").endswith("steamid"):
            safe[col] = safe[col].astype("string")
    rows = json.loads(safe.to_json(orient="records"))
    return rows


def collect_evidence(analysis, spatial=None):
    observations = getattr(spatial, "observations", spatial)
    base = build_coach_inputs(analysis)
    frames = {name: base.frames[name] for name in ("kills", "damage", "bombs", "blinds")}
    for name in (
        "states",
        "utility",
        "shots",
        "smokes",
        "equipment",
        "economy",
        "throws",
        "utility_lifecycles",
    ):
        frames[name] = getattr(observations, name, pd.DataFrame())
    extra_bombs = getattr(observations, "bombs", pd.DataFrame()).copy()
    if not extra_bombs.empty:
        known = {(row.get("event"), row.get("tick")) for row in records(frames["bombs"])}
        extra_bombs = extra_bombs[
            [(row.get("event"), row.get("tick")) not in known for row in records(extra_bombs)]
        ]
    frames["bomb_updates"] = extra_bombs
    clocks = {}
    round_clocks = {}
    if observations is not None and {"total_rounds_played", "freeze_tick"}.issubset(
        observations.clock
    ):
        clocks = observations.clock.set_index("total_rounds_played").freeze_tick.to_dict()
        round_clocks = {
            int(row["total_rounds_played"]): RoundClock.from_row(row)
            for row in observations.clock.to_dict("records")
        }
    bounds = {
        int(r.total_rounds_played): (int(r.start_tick), int(r.tick))
        for r in analysis.rounds_df.itertuples()
    }
    evidence, by_round, state_index = {}, {rnd: [] for rnd in bounds}, {}
    for source, frame in frames.items():
        rows = source_records(frame)
        # Same canonical numeric representation before and after SQLite/JSON.
        for row in rows:
            for key, value in row.items():
                if isinstance(value, float) and value.is_integer():
                    row[key] = int(value)
        fingerprint = sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        for index, row in enumerate(rows):
            rnd, tick = row.get("total_rounds_played"), row.get("tick")
            if rnd not in bounds or tick is None or not bounds[rnd][0] <= tick <= bounds[rnd][1]:
                continue
            tick = int(tick)
            eid = row.get("event_id") or f"{analysis.content_hash}:{source}:{fingerprint}:{index}"
            evidence[eid] = Evidence(
                eid,
                source,
                int(rnd),
                tick,
                round_clocks[rnd].seconds(tick) if rnd in round_clocks else None,
                row,
            )
            by_round[int(rnd)].append(eid)
            if source == "states":
                state_index[(int(rnd), str(row.get("steamid")), tick)] = eid
    effects, throws = {}, {}
    for event in evidence.values():
        row = event.data
        if event.source == "utility":
            key = (
                row.get("source_event"),
                event.tick,
                row.get("entityid"),
                row.get("user_steamid"),
            )
            effects.setdefault(key, []).append(event.id)
        elif event.source == "throws":
            key = (event.tick, row.get("user_steamid"), row.get("weapon"))
            throws.setdefault(key, []).append(event.id)
    for event in evidence.values():
        if event.source != "utility_lifecycles":
            continue
        row = event.data
        effect_key = (
            row.get("source_event"),
            event.tick,
            row.get("entityid"),
            row.get("user_steamid"),
        )
        refs = effects.get(effect_key, [])
        raw = row.get("throw_observation")
        if raw is not None:
            throw_key = (raw.get("tick"), raw.get("user_steamid"), raw.get("weapon"))
            matched = throws.get(throw_key, [])
            if len(matched) == 1:
                refs = refs + matched
        row["evidence_ids"] = refs
        expiry = row.get("expiry_observation")
        if expiry is not None:
            # Expiry can fall after round end: retain raw provenance, not an in-round event.
            digest = sha256(json.dumps(expiry, sort_keys=True).encode()).hexdigest()
            row["expiry_source_id"] = f"{analysis.content_hash}:utility_expiry:{digest}"
    # Spatial assignment is a separate view; evidence always retains source data.
    if spatial is not None:
        frames["states"] = getattr(spatial, "states", frames["states"])
    return frames, clocks, bounds, evidence, by_round, state_index
