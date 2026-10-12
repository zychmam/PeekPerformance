"""Regression checks against hand-counted events; no binary demo parsing is mocked as real."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.demos.demo_analyzer import (
    calculate_round_stats,
    normalize_damage,
    normalize_round_events,
    normalize_rounds,
)
from src.demos.rating_calculator import compute_rating_from_events
from src.models.models import DemoAnalysis
from src.storage.database import Database

REFERENCE = Path(__file__).parent / "reference" / "two_rounds.json"


@pytest.fixture()
def reference() -> dict:
    return json.loads(REFERENCE.read_text(encoding="utf-8"))


def _events(reference: dict, name: str) -> pd.DataFrame:
    """Expand readable fixture aliases into demoparser-shaped columns."""
    identifiers = {row["name"]: row["steamid"] for row in reference["player_info"]}
    rows = []
    for source in reference[name]:
        row = {key: value for key, value in source.items() if key not in {
            "attacker", "victim", "assister", "note",
            "expected_actual", "expected_enemy", "expected_utility",
        }}
        round_no = str(int(source["total_rounds_played"]) + 1)
        teams = reference["roster_teams"].get(round_no, reference["roster_teams"]["2"])
        for alias, prefix in (("attacker", "attacker"), ("victim", "user")):
            player = source[alias]
            row[f"{prefix}_steamid"] = identifiers.get(player, "0")
            row[f"{prefix}_name"] = player
            row[f"{prefix}_team_num"] = teams[player[0]] if player != "WORLD" else 0
        if name == "kills":
            row["assister_steamid"] = identifiers.get(source.get("assister", ""), "0")
            row.setdefault("assistedflash", False)
        rows.append(row)
    return pd.DataFrame(rows)


def _roster(reference: dict) -> pd.DataFrame:
    rows = []
    for round_no, teams in reference["roster_teams"].items():
        tick = reference["provenance"]["live_tick_intervals"][int(round_no) - 1][0]
        for player in reference["player_info"]:
            rows.append({**player, "tick": tick, "team_num": teams[player["name"][0]]})
    return pd.DataFrame(rows)


def _rounds(reference: dict) -> pd.DataFrame:
    return normalize_rounds(
        pd.DataFrame(reference["round_ends"]), pd.DataFrame(reference["round_starts"])
    )


def _rating(reference: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    return compute_rating_from_events(
        pd.DataFrame(reference["player_info"]),
        _events(reference, "kills"),
        _events(reference, "damage"),
        _rounds(reference),
        pd.DataFrame(reference["bomb_planted"]),
        roster=_roster(reference),
        tick_rate=reference["provenance"]["tick_rate"],
    )


def test_round_timeline_ignores_warmup_break_and_incomplete_round(reference: dict) -> None:
    rounds = _rounds(reference)
    assert rounds["total_rounds_played"].tolist() == [1, 2]
    assert rounds["start_tick"].tolist() == [100, 700]
    kills = normalize_round_events(_events(reference, "kills"), rounds)
    assert kills["tick"].tolist() == [200, 300, 450, 550, 850, 950, 1150]
    assert kills["total_rounds_played"].tolist() == [1, 1, 1, 1, 2, 2, 2]
    assert kills["raw_total_rounds_played"].tolist() == [0, 0, 0, 0, 1, 1, 1]


def test_hand_counted_hp_loss_enemy_and_utility_damage(reference: dict) -> None:
    raw = normalize_round_events(_events(reference, "damage"), _rounds(reference))
    damage = normalize_damage(raw).set_index("tick")
    expected = {row["tick"]: row for row in reference["damage"] if "expected_enemy" in row}
    assert set(damage.index) == set(expected)
    for tick, row in expected.items():
        assert damage.loc[tick, "dmg_health"] == row["dmg_health"]
        assert damage.loc[tick, "actual_damage"] == row["expected_actual"]
        assert damage.loc[tick, "enemy_damage"] == row["expected_enemy"]
        assert damage.loc[tick, "utility_damage"] == row["expected_utility"]


def test_hand_counted_summary_includes_inactive_players_and_side_switch(reference: dict) -> None:
    summary, round_swing = _rating(reference)
    assert len(summary) == 10
    assert len(round_swing) == 20
    assert set(summary["steamid"]) == {row["steamid"] for row in reference["player_info"]}
    indexed = summary.set_index("Gracz")
    for player, expected in reference["expected_summary"].items():
        for column, value in expected.items():
            assert indexed.loc[player, column] == pytest.approx(value, abs=0.005), (player, column)


def test_hand_calculated_kill_flash_trade_and_bomb_swing(reference: dict) -> None:
    _, swings = _rating(reference)
    indexed = swings.set_index(["Runda", "Gracz"])
    for round_no, expected in reference["expected_round_swing"].items():
        for player, swing in expected.items():
            assert indexed.loc[(int(round_no), player), "Swing"] == pytest.approx(swing, abs=0.005)


def test_round_statistics_and_rating_use_the_same_enemy_damage(reference: dict) -> None:
    rounds = _rounds(reference)
    stats = calculate_round_stats(
        _events(reference, "kills"), _events(reference, "damage"), rounds, roster=_roster(reference)
    )
    ids = {row["name"]: row["steamid"] for row in reference["player_info"]}
    total = stats.groupby("steamid")[["kills", "deaths", "damage"]].sum()
    for name, expected in reference["expected_summary"].items():
        assert total.loc[ids[name], "kills"] == expected["K"]
        assert total.loc[ids[name], "deaths"] == expected["D"]
        assert total.loc[ids[name], "damage"] == expected["ADR"] * 2


def test_reference_identifiers_survive_sqlite_round_trip(reference: dict, tmp_path: Path) -> None:
    database = Database(tmp_path / "reference.db")
    analysis = DemoAnalysis(
        file_name="synthetic-reference.dem",
        content_hash="synthetic-reference",
        player_info=pd.DataFrame(reference["player_info"]),
        kills_df=_events(reference, "kills"),
        damage_df=_events(reference, "damage"),
    )
    database.upsert_demo_analysis(analysis)
    restored = database.get_demo_analysis(analysis.content_hash)
    assert restored is not None
    assert restored.player_info["steamid"].tolist() == analysis.player_info["steamid"].tolist()
    assert (
        restored.kills_df["attacker_steamid"].tolist()
        == analysis.kills_df["attacker_steamid"].tolist()
    )
    assert (
        restored.damage_df["user_steamid"].tolist()
        == analysis.damage_df["user_steamid"].tolist()
    )
