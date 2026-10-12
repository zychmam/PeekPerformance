"""Manually counted expectations from anonymized real-demo parser events.

These verify interpretation of exported events, not accuracy of the parser.
Opening/trade/flash examples define future detectors; no detector is claimed here.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.demos.demo_analyzer import normalize_damage, normalize_round_events, normalize_rounds
from src.demos.rating_calculator import compute_rating_from_events


@pytest.fixture()
def reference():
    return json.loads((Path(__file__).parent / "reference" / "anubis_coach_extract.json")
                      .read_text(encoding="utf-8"))


def test_real_round_restart_excludes_prematch_and_keeps_last_kill(reference):
    rounds = normalize_rounds(pd.DataFrame(reference["rounds"]))
    assert len(rounds) == 24
    assert rounds.iloc[0].start_tick == 4009
    assert rounds.iloc[0].tick == 8021
    assert rounds.iloc[12].start_tick == 68092
    pd.testing.assert_frame_equal(normalize_rounds(rounds), rounds)
    kills = normalize_round_events(pd.DataFrame(reference["kills"]), rounds)
    assert 2661 not in set(kills.tick)  # Pre-match knife kill.
    assert kills[kills.tick.eq(8021)].total_rounds_played.item() == 1
    assert kills[kills.tick.eq(70477)].total_rounds_played.item() == 13


def test_manual_pistol_damage_kills_and_side_change(reference):
    rounds = normalize_rounds(pd.DataFrame(reference["rounds"]))
    kills = pd.DataFrame(reference["kills"])
    damage = pd.DataFrame(reference["damage"])
    roster = normalize_round_events(pd.DataFrame(reference["round_roster"]), rounds)
    players = pd.DataFrame(reference["player_info"])
    _, per_round = compute_rating_from_events(
        players, kills, damage, rounds, pd.DataFrame(), roster=roster,
    )
    first = per_round[per_round.Runda.eq(1)].set_index("Gracz")
    # A1: 100 + 5 + 100 + 16 + 16 = 237 HP. A2: 95 + 100 + 15 + 36 = 246 HP.
    assert first.loc["A1", "damage"] == 237
    assert first.loc["A2", "damage"] == 246
    assert first.loc["A1", "kills"] == 2
    assert first.loc["A2", "kills"] == 3
    assert first.loc["A5", "deaths"] == 1
    # At 7337 B1 kills A5; A2 trades B1 at 7602: 265 ticks < 320.
    assert first.loc["A5", "kast"] == 1
    ids = players.set_index("name").steamid
    assert roster[(roster.steamid == ids["A2"]) & roster.total_rounds_played.eq(12)] \
        .team_num.item() == 3
    assert roster[(roster.steamid == ids["A2"]) & roster.total_rounds_played.eq(13)] \
        .team_num.item() == 2
    normalized = normalize_damage(normalize_round_events(damage, rounds)).set_index("tick")
    assert normalized.loc[7121, "actual_damage"] == 95  # 110 raw, target had 95 HP.
    assert normalized.loc[8021, "actual_damage"] == 36  # 125 raw, 36 HP left.


def test_restart_rule_does_not_guess_from_weapon_or_halftime():
    source = pd.DataFrame([
        {"tick": i * 100, "start_tick": (i - 1) * 100 + 1,
         "total_rounds_played": i, "winner": 2 if i <= 12 else 3}
        for i in range(1, 31)
    ])
    assert len(normalize_rounds(source)) == 30  # Includes overtime, no restart.
