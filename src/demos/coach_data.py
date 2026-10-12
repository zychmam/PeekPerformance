"""Versioned, parser-free access to coaching evidence from a saved match.

This is an input contract, not a tactical detector. Empty legacy frames cannot
distinguish an absent event from a parser failure and therefore remain unknown.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

import pandas as pd

from src.demos.presentation import is_steam_id_column
from src.demos.versions import ANALYSIS_VERSION, METRICS_VERSION
from src.models.models import DemoAnalysis
from src.storage.database import Database

COACH_INPUT_VERSION = 1
_SOURCES = {
    "rounds": ("rounds_df", ("tick", "start_tick", "total_rounds_played", "winner")),
    "roster": ("round_roster_df", ("steamid", "team_num", "total_rounds_played")),
    "kills": ("kills_df", ("tick", "total_rounds_played", "attacker_steamid",
                            "user_steamid", "attacker_team_num", "user_team_num")),
    "damage": ("damage_df", ("tick", "total_rounds_played", "attacker_steamid",
                              "user_steamid", "enemy_damage", "actual_damage")),
    "bombs": ("bomb_events_df", ("tick", "total_rounds_played", "event")),
    "blinds": ("player_blinds_df", ("tick", "total_rounds_played", "attacker_steamid",
                                     "user_steamid", "blind_duration", "is_enemy")),
}


@dataclass(frozen=True)
class SourceAvailability:
    status: str  # present / partial / unknown / not_loaded
    rows: int
    missing_columns: tuple[str, ...] = ()
    null_columns: tuple[str, ...] = ()


@dataclass
class CoachInputs:
    demo_id: str
    map_name: str
    analysis_version: int
    metrics_version: int
    contract_version: int
    frames: dict[str, pd.DataFrame]
    availability: dict[str, SourceAvailability]
    limitations: tuple[str, ...]

    def event(self, event_id: str) -> dict:
        """Resolve an evidence ID in this snapshot; no source/demo file access."""
        for frame in self.frames.values():
            matches = frame[frame["event_id"].eq(event_id)]
            if not matches.empty:
                return matches.iloc[0].to_dict()
        raise KeyError(event_id)


def build_coach_inputs(analysis: DemoAnalysis) -> CoachInputs:
    """Create stable IDs in saved row order, before any filtering or sorting.

    IDs are scoped to demo, input version, source contents and contract version.
    JSON uses the same precision as storage, so IDs survive SQLite round trips.
    Replacing a source changes its namespace and invalidates old evidence IDs.
    """
    if not analysis.content_hash:
        raise ValueError("Coaching requires a demo content hash")
    if analysis.analysis_version != ANALYSIS_VERSION:
        raise ValueError("Saved demo inputs need an upgrade before coaching")
    frames = {}
    availability = {}
    for name, (attribute, required) in _SOURCES.items():
        source = getattr(analysis, attribute).copy().reset_index(drop=True)
        for column in source:
            if is_steam_id_column(column):
                source[column] = source[column].astype("string")
        missing = tuple(column for column in required if column not in source)
        nulls = tuple(column for column in required
                      if column in source and source[column].isna().any())
        status = "unknown" if source.empty else ("partial" if missing or nulls else "present")
        availability[name] = SourceAvailability(status, len(source), missing, nulls)
        # Canonical JSON ignores dtype changes introduced by SQLite (e.g. 1 -> 1.0).
        # read_json is intentionally avoided here to preserve exact SteamIDs.
        canonical = source.to_json(orient="records", double_precision=10)
        rows = json.loads(canonical)
        for row in rows:
            for key, value in row.items():
                if isinstance(value, float) and value.is_integer():
                    row[key] = int(value)
        serialized = json.dumps(rows, sort_keys=True, separators=(",", ":"))
        namespace = sha256(
            f"{analysis.content_hash}:{analysis.analysis_version}:"
            f"{COACH_INPUT_VERSION}:{name}:{serialized}".encode()
        ).hexdigest()
        frame = source
        if "event_id" not in frame:
            frame["event_id"] = [f"{name}:{namespace}:{i}" for i in range(len(frame))]
        frames[name] = frame
    availability["trajectories"] = SourceAvailability("not_loaded", 0)
    availability["player_states"] = SourceAvailability("not_loaded", 0)
    return CoachInputs(
        analysis.content_hash, analysis.map_name, analysis.analysis_version,
        METRICS_VERSION, COACH_INPUT_VERSION, frames, availability,
        (
            "Empty saved streams have unknown completeness; they are not verified zero counts.",
            "Present means required fields exist, not that parser completeness is proven.",
            "Cross-stream order within one tick is unknown; retain source order within streams.",
            "Time conversion currently assumes 64 ticks/s; freeze-end is not persisted.",
            "Roster records sides per round, not persistent team identities or reconnect history.",
            "Event positions are snapshots, not continuous paths or visibility evidence.",
            "Voice communications and player knowledge are unavailable.",
        ),
    )


def load_coach_inputs(db: Database, demo_id: str) -> CoachInputs:
    """Load one match for all players without parsing, API calls or metric changes."""
    analysis = db.get_demo_analysis(demo_id, include_auxiliary=False)
    if analysis is None:
        raise ValueError("Unknown demo")
    return build_coach_inputs(analysis)
