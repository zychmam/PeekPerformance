"""Regression for a fresh life after pre-freeze reset, with explicit clocks."""

import pandas as pd
import pytest

from src.demos.rating_calculator import compute_rating_from_events


def calculate(freeze=50, *, active_world=False, duplicate=False):
    rounds = pd.DataFrame([{
        "total_rounds_played": 1, "start_tick": 10, "tick": 100,
        "freeze_tick": freeze, "winner": 3,
    }])
    roster = pd.DataFrame([
        {"steamid": "a", "team_num": 3, "total_rounds_played": 1},
        {"steamid": "b", "team_num": 2, "total_rounds_played": 1},
    ])
    reset = dict(tick=20, attacker_steamid="b", user_steamid="b",
                 attacker_team_num=2, user_team_num=2, weapon="world")
    kill = dict(tick=50, attacker_steamid="a", user_steamid="b",
                attacker_team_num=3, user_team_num=2, weapon="ak47", headshot=True)
    kills = [reset, kill]
    if active_world:
        kills = [{**reset, "tick": 50}]
    if duplicate:
        kills.append({**kill, "tick": 60})
    damage = pd.DataFrame([
        {**reset, "dmg_health": 100},
        {**kill, "dmg_health": 140},
    ])
    summary, per_round = compute_rating_from_events(
        pd.DataFrame([{"steamid": "a", "name": "A"}, {"steamid": "b", "name": "B"}]),
        pd.DataFrame(kills), damage, rounds, pd.DataFrame(), roster=roster,
    )
    return summary.set_index("steamid"), per_round.set_index("steamid")


def test_prefreeze_reset_does_not_consume_life_or_hp():
    summary, rows = calculate()
    assert summary.loc["a", "K"] == 1
    assert summary.loc["a", "ADR"] == 100
    assert summary.loc["a", "HS%"] == 100
    assert summary.loc["a", "KAST%"] == 100
    assert summary.loc["b", "D"] == 1
    assert rows.loc["b", "survived"] == 0
    assert rows.loc["a", "Swing"] > 0
    assert set(rows.metrics_clock_status) == {"known"}


@pytest.mark.parametrize("freeze", [None, float("nan"), 9, 101])
def test_unknown_or_invalid_freeze_preserves_events_and_discloses_status(freeze):
    summary, rows = calculate(freeze)
    assert summary.loc["a", "K"] == 0  # No evidence of respawn, do not infer it.
    assert summary.loc["b", "D"] == 1
    assert set(rows.metrics_clock_status) == {"unknown"}


def test_world_death_in_active_round_counts_without_enemy_credit():
    summary, _ = calculate(active_world=True)
    assert summary.loc["b", "D"] == 1
    assert summary.K.sum() == 0


def test_second_active_death_is_not_a_second_life():
    summary, _ = calculate(duplicate=True)
    assert summary.loc["a", "K"] == 1
    assert summary.loc["b", "D"] == 1


def test_clock_matches_round_by_end_tick_despite_different_numbering():
    from src.demos.rating_window import active_round_events, metric_clock

    rounds = pd.DataFrame([{"total_rounds_played": 1, "start_tick": 10, "tick": 100}])
    clock = pd.DataFrame([{"total_rounds_played": 17, "tick": 100, "freeze_tick": 50}])
    known = metric_clock(rounds, clock)
    events = pd.DataFrame([{"tick": tick} for tick in [49, 50, 100, 101]])
    assert active_round_events(events, known).tick.tolist() == [50, 100]
