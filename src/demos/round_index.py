"""Round-local indexes. Sort observations once; never select future samples."""

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Mapping

import pandas as pd


@dataclass(frozen=True)
class SampleLookup:
    row: dict | None
    requested_tick: int
    sample_tick: int | None
    age_ticks: int | None
    status: str
    gap_before_ticks: int | None = None


class RoundIndex:
    """Index one round of source frames, grouped by source and player.

    Explicit coverage gaps are (last covered tick, next covered tick) pairs.
    Endpoints remain observed; their interior must not be carried forward.
    """

    def __init__(
        self,
        frames: Mapping[str, pd.DataFrame] | pd.DataFrame,
        round_number: int | None = None,
        *,
        gaps=None,
    ):
        if isinstance(frames, pd.DataFrame):
            frames = {"states": frames}
        self.round_number = round_number
        self.gaps = gaps or {}
        self._groups = {}
        for source, frame in frames.items():
            if "tick" not in frame:
                continue
            part = frame
            if round_number is not None and "total_rounds_played" in part:
                part = part[part.total_rounds_played.eq(round_number)]
            part = part.dropna(subset=["tick"]).sort_values("tick", kind="stable")
            rows = part.to_dict("records")
            self._groups[(source, None)] = ([int(r["tick"]) for r in rows], rows)
            player_column = next(
                (c for c in ("steamid", "player_id", "user_steamid") if c in part), None
            )
            if player_column:
                for player_id, group in part.groupby(player_column, sort=False):
                    rows = group.to_dict("records")
                    self._groups[(source, str(player_id))] = ([int(r["tick"]) for r in rows], rows)

    def between(
        self, start_tick: int, end_tick: int, *, source="states", player_id=None
    ) -> list[dict]:
        ticks, rows = self._groups.get(
            (source, None if player_id is None else str(player_id)), ([], [])
        )
        return rows[bisect_left(ticks, start_tick) : bisect_right(ticks, end_tick)]

    def latest(
        self,
        tick: int,
        *,
        player_id=None,
        source="states",
        max_age_ticks: int | None = None,
        max_gap_ticks: int | None = None,
    ) -> SampleLookup:
        key = (source, None if player_id is None else str(player_id))
        ticks, rows = self._groups.get(key, ([], []))
        i = bisect_right(ticks, tick) - 1
        if i < 0:
            return SampleLookup(None, tick, None, None, "missing")
        sample_tick, age = ticks[i], tick - ticks[i]
        gap = ticks[i] - ticks[i - 1] if i else None
        if max_age_ticks is not None and age > max_age_ticks:
            return SampleLookup(None, tick, sample_tick, age, "stale", gap)
        coverage_gaps = self.gaps.get(key, self.gaps.get(str(player_id), []))
        in_gap = any(left < tick < right for left, right in coverage_gaps)
        # A future sample can reveal a coverage gap, but can never be selected.
        if max_gap_ticks is not None and i + 1 < len(ticks):
            in_gap |= (
                sample_tick < tick < ticks[i + 1] and ticks[i + 1] - sample_tick > max_gap_ticks
            )
        if in_gap:
            return SampleLookup(None, tick, sample_tick, age, "gap", gap)
        return SampleLookup(dict(rows[i]), tick, sample_tick, age, "observed", gap)

    def before(self, tick: int, **kwargs) -> SampleLookup:
        """Strictly before an event; use latest() for inclusive selection."""
        return self.latest(tick - 1, **kwargs)
