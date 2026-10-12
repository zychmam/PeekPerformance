"""Map-independent extraction; spatial interpretations belong to map profiles."""

from __future__ import annotations

import json
import math
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from src.demos.demo_analyzer import DemoAnalyzer, normalize_round_events
from src.demos.foundation_sources import extract_bomb_events, extract_equipment
from src.demos.replay_effects import extract_replay_effects
from src.demos.versions import ANALYSIS_VERSION
from src.models.observations import MatchObservations, observation_id

OBSERVATION_VERSION = 1
PARSER_VERSION = version("demoparser2")
DEFAULT_TICK_RATE = 64.0
SAMPLE_SECONDS = 0.1
EFFECTS = {
    "smokegrenade_detonate": "Smoke",
    "flashbang_detonate": "Flash",
    "hegrenade_detonate": "HE",
    "inferno_startburn": "Ogień",
}
DERIVED_LOCATION_COLUMNS = frozenset(
    {
        "zone",
        "place",
        "region_id",
        "location_status",
        "level",
        "location_method",
        "location_candidates",
        "profile_version",
        "semantic_fingerprint",
        "direction",
    }
)


def source_records(frame):
    """Canonical numeric and identifier representation shared with persisted evidence."""
    safe = frame.drop(columns=list(DERIVED_LOCATION_COLUMNS), errors="ignore").copy()
    for col in safe:
        if str(col).lower().replace("_", "").endswith("steamid"):
            safe[col] = safe[col].astype("string")
    rows = json.loads(safe.to_json(orient="records", double_precision=10))
    for row in rows:
        for key, value in row.items():
            if isinstance(value, float) and value.is_integer():
                row[key] = int(value)
    return rows


def tick_rate_metadata(header):
    """Only explicit frequency metadata is trusted; fallback is labelled."""
    for key in ("tick_rate", "tickrate"):
        try:
            rate = float(header[key])
            if math.isfinite(rate) and rate > 0:
                return rate, f"header.{key}"
        except (KeyError, TypeError, ValueError):
            pass
    try:
        interval = float(header["tick_interval"])
        if math.isfinite(interval) and interval > 0:
            return 1.0 / interval, "header.tick_interval"
    except (KeyError, TypeError, ValueError):
        pass
    return DEFAULT_TICK_RATE, "assumed_64"


def observations_key(analysis):
    parts = [
        analysis.content_hash,
        analysis.analysis_version,
        OBSERVATION_VERSION,
        PARSER_VERSION,
        tick_rate_metadata(analysis.header),
        SAMPLE_SECONDS,
    ]
    for frame in (
        analysis.rounds_df,
        analysis.kills_df,
        analysis.damage_df,
        analysis.bomb_events_df,
        analysis.round_roster_df,
        analysis.player_blinds_df,
    ):
        parts.append(source_records(frame))
    return sha256(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def stamp_observation_ids(frame, demo_id, source):
    """Stamp before persistence partitions rows; duplicate event rows stay distinct."""
    frame = frame.copy()
    rows = source_records(frame.drop(columns="event_id", errors="ignore"))
    fingerprint = sha256(
        json.dumps(
            [OBSERVATION_VERSION, PARSER_VERSION, rows],
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    frame["event_id"] = [observation_id(demo_id, source, fingerprint, i) for i in range(len(frame))]
    return frame


def round_clock(rounds, freezes, tick_rate=DEFAULT_TICK_RATE, tick_rate_source="assumed_64"):
    clock = rounds.copy()
    freeze_ticks = freezes.get("tick", pd.Series(dtype=int))
    clock["freeze_tick"] = [
        freeze_ticks[freeze_ticks.between(row.start_tick, row.tick)].min()
        for row in clock.itertuples()
    ]
    clock["tick_rate"] = tick_rate
    clock["time_source"] = tick_rate_source
    return clock


def normalize_states(states, clock, tick_rate=DEFAULT_TICK_RATE):
    states = normalize_round_events(states, clock)
    if states.empty:
        return states
    states = states.drop(columns=list(DERIVED_LOCATION_COLUMNS), errors="ignore").copy()
    states["steamid"] = states.steamid.astype("string")
    # One sampled state per player/tick, unlike event streams where duplicates matter.
    states = states.drop_duplicates(["tick", "steamid"], keep="last")
    states = states.merge(
        clock[["total_rounds_played", "freeze_tick"]], on="total_rounds_played", how="left"
    )
    states["seconds"] = (states.tick - states.freeze_tick) / tick_rate
    states["has_bomb"] = (
        states.inventory.map(
            lambda items: (
                any(str(i) in ("C4 Explosive", "C4", "weapon_c4") for i in items)
                if isinstance(items, (list, tuple))
                else None
            )
        )
        if "inventory" in states
        else None
    )
    return (
        states.drop(columns="inventory", errors="ignore")
        .sort_values(["tick", "steamid"], kind="stable")
        .reset_index(drop=True)
    )


def _position_samples(parser, ticks, diagnostics):
    required = ["X", "Y", "Z", "health", "is_alive", "team_num"]
    optional = ["last_place_name", "inventory", "pitch", "yaw"]
    sources = diagnostics["sources"]
    try:
        states = parser.parse_ticks(required + optional, ticks=ticks)
        sources["inventory_orientation"] = "ok"
        for prop in optional:
            sources[f"states.{prop}"] = "ok" if prop in states else "unsupported"
        return states
    except Exception as exc:
        sources["inventory_orientation"] = f"unavailable: {type(exc).__name__}"
    states = parser.parse_ticks(required, ticks=ticks)
    for prop in optional:
        try:
            frame = parser.parse_ticks([prop], ticks=ticks)
            if prop not in frame or not {"tick", "steamid"}.issubset(frame):
                raise ValueError("Missing optional field")
            frame = frame.drop_duplicates(["tick", "steamid"], keep="last")
            states = states.merge(
                frame[["tick", "steamid", prop]], on=["tick", "steamid"], how="left"
            )
            sources[f"states.{prop}"] = "ok"
        except Exception as exc:
            sources[f"states.{prop}"] = f"error: {type(exc).__name__}"
    if "last_place_name" not in states:
        states["last_place_name"] = None
    return states


def extract_observations(analysis, path: Path):
    if analysis.analysis_version != ANALYSIS_VERSION:
        raise ValueError("Najpierw uaktualnij analizę meczu.")
    analyzer = DemoAnalyzer(path)
    header = analyzer.get_header()
    if header.get("map_name") != analysis.map_name:
        raise ValueError("Mapa pliku źródłowego nie zgadza się z analizą meczu.")
    rate, rate_source = tick_rate_metadata(header)
    interval = max(1, round(SAMPLE_SECONDS * rate))
    diagnostics = {
        "version": OBSERVATION_VERSION,
        "sample_ticks": interval,
        "parser_version": PARSER_VERSION,
        "demo_patch": header.get("patch_version"),
        "tick_rate": rate,
        "tick_rate_source": rate_source,
        "tick_rate_assumption": rate if rate_source == "assumed_64" else None,
        "sources": {},
    }
    parser = analyzer._parser
    try:
        freezes = parser.parse_event("round_freeze_end")
        diagnostics["sources"]["round_freeze_end"] = "ok"
    except Exception as exc:
        freezes = pd.DataFrame()
        diagnostics["sources"]["round_freeze_end"] = f"error: {type(exc).__name__}"
    clock = round_clock(analysis.rounds_df, freezes, rate, rate_source)
    ticks = set()
    ranges = [
        (int(row.freeze_tick), int(row.tick))
        for row in clock.dropna(subset=["freeze_tick"]).itertuples()
    ]
    for start, end in ranges:
        ticks.update(range(start, end + 1, interval))
        ticks.add(end)
    for source in (analysis.kills_df, analysis.damage_df):
        if "tick" in source:
            for tick in source.tick.dropna().astype(int):
                for candidate in (tick - 1, tick):
                    if any(start <= candidate <= end for start, end in ranges):
                        ticks.add(candidate)
    states = _position_samples(parser, sorted(ticks), diagnostics) if ticks else pd.DataFrame()
    if not states.empty:
        if not {"steamid", "tick", "X", "Y", "Z", "health", "is_alive", "team_num"}.issubset(
            states
        ):
            raise ValueError("Parser nie zwrócił wymaganych danych pozycji graczy.")
        states = normalize_states(states, clock, rate)
    diagnostics["sources"]["states"] = "ok" if ticks else "not_loaded"
    effects = []
    available_events = set(analyzer.list_events())
    for event_name, label in EFFECTS.items():
        if event_name not in available_events:
            diagnostics["sources"][event_name] = "not_listed"
            continue
        try:
            frame = normalize_round_events(
                parser.parse_event(event_name, player=["team_num"]), clock
            )
            diagnostics["sources"][event_name] = "ok"
            if not frame.empty:
                frame["kind"], frame["source_event"] = label, event_name
                effects.append(frame)
        except Exception as exc:
            diagnostics["sources"][event_name] = f"error: {type(exc).__name__}"
    utility = pd.concat(effects, ignore_index=True) if effects else pd.DataFrame()
    if not utility.empty:
        utility = utility.merge(
            clock[["total_rounds_played", "freeze_tick"]], on="total_rounds_played", how="left"
        )
        utility["seconds"] = (utility.tick - utility.freeze_tick) / rate
        utility = utility.sort_values("tick", kind="stable").reset_index(drop=True)
    extras = {}
    smokes, shots = extract_replay_effects(
        parser, clock, utility, available_events, diagnostics, extras=extras, tick_rate=rate
    )
    equipment, economy, coverage = extract_equipment(
        parser,
        sorted(ticks),
        clock,
        diagnostics,
        economy_reader=analyzer.get_economy,
        tick_rate=rate,
    )
    diagnostics["equipment_coverage"] = coverage
    diagnostics["missing_freezes"] = int(clock.freeze_tick.isna().sum())
    frames = {
        "clock": clock,
        "states": states,
        "utility": utility,
        "smokes": smokes,
        "shots": shots,
        "equipment": equipment,
        "economy": economy,
        "bombs": extract_bomb_events(parser, clock, available_events, diagnostics),
        "throws": extras["throws"],
        "utility_lifecycles": extras["utility_lifecycles"],
    }
    frames = {
        name: stamp_observation_ids(frame, analysis.content_hash, name)
        for name, frame in frames.items()
    }
    return MatchObservations(
        demo_id=analysis.content_hash,
        map_name=analysis.map_name,
        cache_key=observations_key(analysis),
        diagnostics=diagnostics,
        **frames,
    )
