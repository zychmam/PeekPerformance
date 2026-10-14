"""Recorded flash-effect windows; no inference of full blindness or screen alpha."""

import math

import pandas as pd


def recorded_flash_windows(blinds, round_number, freeze, end, tick_rate, deaths):
    """Return merged per-player windows and individual source events.

    Source times stay separate from the visual union: overlapping flashes do
    not add their durations. Missing/invalid duration stays unknown.
    """
    windows, events = {}, []
    if blinds.empty or not {"tick", "user_steamid"}.issubset(blinds):
        return windows, events
    part = blinds.copy()
    if "total_rounds_played" in part:
        part = part[part.total_rounds_played.eq(round_number)]
    part["tick"] = pd.to_numeric(part.tick, errors="coerce")
    part = part[part.tick.between(freeze, end)].sort_values("tick", kind="stable")
    for row in part.to_dict("records"):
        victim = str(row["user_steamid"])
        if victim in {"None", "nan", "<NA>", "", "0"}:
            continue
        tick = float(row["tick"])
        death = deaths.get(victim)
        if death is not None and tick >= death:
            continue
        try:
            duration = float(row.get("blind_duration"))
        except (TypeError, ValueError):
            duration = float("nan")
        valid = math.isfinite(duration) and duration > 0
        events.append(
            {
                "tick": tick,
                "victim": victim,
                "attacker": str(row.get("attacker_steamid", "")),
                "duration": duration if valid else None,
            }
        )
        if not valid:
            continue
        finish = min(tick + duration * tick_rate, end, death if death is not None else end)
        if finish <= tick:
            continue
        intervals = windows.setdefault(victim, [])
        start_seconds, end_seconds = (tick - freeze) / tick_rate, (finish - freeze) / tick_rate
        if intervals and start_seconds <= intervals[-1][1]:
            intervals[-1][1] = max(intervals[-1][1], end_seconds)
        else:
            intervals.append([start_seconds, end_seconds])
    return windows, events
