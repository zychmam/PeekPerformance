"""Source flash windows preserve uncertainty and do not sum overlapping events."""

import pandas as pd
import pytest

from src.demos.viewer_blinds import recorded_flash_windows


def event(tick, duration, player="p", rnd=1):
    return {
        "tick": tick,
        "blind_duration": duration,
        "user_steamid": player,
        "attacker_steamid": player,
        "total_rounds_played": rnd,
    }


def test_overlap_is_union_and_keeps_both_source_events():
    windows, events = recorded_flash_windows(
        pd.DataFrame(
            [
                event(30, 2),
                event(20, 2),
                event(70, 1),
            ]
        ),
        1,
        10,
        100,
        10,
        {},
    )
    assert windows == {"p": [[1.0, 4.0], [6.0, 7.0]]}
    assert [e["tick"] for e in events] == [20, 30, 70]
    assert [e["duration"] for e in events] == [2, 2, 1]


def test_clip_to_death_round_and_exclude_prefreeze_other_round_dead_hits():
    windows, events = recorded_flash_windows(
        pd.DataFrame(
            [
                event(9, 5),
                event(20, 8),
                event(50, 2),
                event(60, 1, rnd=2),
                event(95, 5, player="other"),
            ]
        ),
        1,
        10,
        100,
        10,
        {"p": 45},
    )
    assert windows == {"p": [[1.0, 3.5]], "other": [[8.5, 9.0]]}
    assert [e["tick"] for e in events] == [20, 95]


@pytest.mark.parametrize("duration", [None, float("nan"), float("inf"), -1, 0, "bad"])
def test_invalid_duration_keeps_event_without_inventing_interval(duration):
    windows, events = recorded_flash_windows(
        pd.DataFrame([event(20, duration)]),
        1,
        10,
        100,
        10,
        {},
    )
    assert windows == {}
    assert events[0]["duration"] is None
