"""Active round boundaries shared by metrics and their exported audit."""

from __future__ import annotations

import pandas as pd

from src.demos.demo_analyzer import normalize_round_events


def metric_clock(rounds: pd.DataFrame, clock: pd.DataFrame | None = None) -> pd.DataFrame:
    """Match clocks by end tick, never by possibly renumbered engine counters.

    An unavailable or invalid freeze boundary stays unknown. We retain the
    completed round window in that case rather than infer resets from weapons.
    """
    result = rounds.copy()
    if result.empty:
        result["freeze_tick"] = pd.Series(dtype=float)
        result["metrics_clock_status"] = pd.Series(dtype=str)
        return result
    source = clock if clock is not None else rounds
    freezes = (
        source.drop_duplicates("tick").set_index("tick")["freeze_tick"]
        if {"tick", "freeze_tick"}.issubset(source) else pd.Series(dtype=float)
    )
    result["freeze_tick"] = pd.to_numeric(result.tick.map(freezes), errors="coerce")
    valid = result.freeze_tick.between(result.start_tick, result.tick)
    result["freeze_tick"] = result.freeze_tick.where(valid)
    result["metrics_clock_status"] = valid.map({True: "known", False: "unknown"})
    return result


def active_round_events(events: pd.DataFrame, clock: pd.DataFrame) -> pd.DataFrame:
    """Include freeze and round-end ticks; preserve unknown-clock events."""
    result = normalize_round_events(events, clock)
    if result.empty:
        return result
    freezes = clock.set_index("total_rounds_played").freeze_tick
    boundary = result.total_rounds_played.map(freezes)
    return result[boundary.isna() | result.tick.ge(boundary)].reset_index(drop=True)
