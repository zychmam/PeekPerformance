"""Versioned match metrics survive sessions and remain independent of the binary demo."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pandas as pd
import pytest

from src.demos import rating_service
from src.demos.demo_manager import DemoManager
from src.demos.match_view import player_rounds_table, player_summary_table
from src.demos.rating_calculator import RATING_VERSION
from src.demos.versions import ANALYSIS_VERSION
from src.models.models import DemoAnalysis
from src.storage.database import Database

SID = "76561198008873401"


def analysis_fixture() -> DemoAnalysis:
    return DemoAnalysis(
        file_name="match.dem", content_hash="match", analysis_version=ANALYSIS_VERSION,
        player_info=pd.DataFrame([{"steamid": SID, "name": "Alice"}]),
        scoreboard=pd.DataFrame([{
            "steam_id": SID, "kills_total": 99, "deaths_total": 99, "assists_total": 99,
        }]),
        rounds_df=pd.DataFrame([
            {"total_rounds_played": 1, "start_tick": 10, "tick": 100, "winner": 3},
            {"total_rounds_played": 2, "start_tick": 110, "tick": 200, "winner": 2},
        ]),
        round_roster_df=pd.DataFrame([
            {"steamid": SID, "total_rounds_played": 1, "team_num": 3},
            {"steamid": SID, "total_rounds_played": 2, "team_num": 2},
        ]),
    )


def test_full_metrics_survive_new_session_without_source_or_event_read(tmp_path) -> None:
    path = tmp_path / "cache.db"
    db = Database(str(path))
    analysis = analysis_fixture()
    db.upsert_demo_analysis(analysis)
    manager = DemoManager(str(tmp_path / "demos"))
    with patch.object(manager, "analysis_path", side_effect=AssertionError("binary opened")):
        first = rating_service.calculate_and_store_rating(db, manager, "match", "match.dem")
        reopened = Database(str(path))
        with patch.object(reopened, "get_demo_analysis", side_effect=AssertionError("events read")):
            second = rating_service.calculate_and_store_rating(
                reopened, manager, "match", "match.dem"
            )
    pd.testing.assert_frame_equal(first[0], second[0], check_dtype=False)
    pd.testing.assert_frame_equal(first[1], second[1], check_dtype=False)
    assert {"Kill", "Dmg", "Surv", "KAST", "HS%", "KAST%"}.issubset(second[0])
    assert second[1]["team_num"].tolist() == [3, 2]
    assert reopened.get_demo_analysis("match").round_roster_df["steamid"].tolist() == [SID, SID]


def test_metric_version_recomputes_from_saved_events_without_parser(tmp_path) -> None:
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(analysis_fixture())
    manager = DemoManager(str(tmp_path / "demos"))
    rating_service.calculate_and_store_rating(db, manager, "match", "match.dem")
    with (
        patch.object(rating_service, "RATING_VERSION", RATING_VERSION + 1),
        patch.object(manager, "analysis_path", side_effect=AssertionError("binary opened")),
        patch.object(rating_service, "compute_rating_from_events",
                     wraps=rating_service.compute_rating_from_events) as compute,
    ):
        rating_service.calculate_and_store_rating(db, manager, "match", "match.dem")
        rating_service.calculate_and_store_rating(db, manager, "match", "match.dem")
        assert compute.call_count == 1
    assert db.get_demo_metrics("match", ANALYSIS_VERSION, RATING_VERSION) is None
    assert db.get_demo_metrics("match", ANALYSIS_VERSION, RATING_VERSION + 1) is not None


def test_input_replacement_invalidates_full_and_compact_metrics(tmp_path) -> None:
    db = Database(str(tmp_path / "cache.db"))
    analysis = analysis_fixture()
    db.upsert_demo_analysis(analysis)
    rating_service.calculate_and_store_rating(
        db, DemoManager(str(tmp_path / "demos")), "match", "match.dem"
    )
    db.upsert_demo_analysis(analysis)
    assert db.get_demo_metrics("match", ANALYSIS_VERSION, RATING_VERSION) is None
    assert db.list_player_matches(SID, RATING_VERSION)[0]["rating"] is None


def test_old_version_reset_preserves_tracking_but_clears_metrics(tmp_path):
    path = tmp_path / "old.db"
    db = Database(str(path))
    db.upsert_demo_analysis(analysis_fixture())
    db.track_player(SID)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version = 4")
    reset = Database(str(path))
    assert reset.list_tracked_players()[0]["steamid"] == SID
    assert reset.list_player_matches(SID, 1) == []
    assert reset.get_demo_analysis("match") is None


def test_views_use_canonical_counts_and_saved_sides(tmp_path) -> None:
    db = Database(str(tmp_path / "cache.db"))
    analysis = analysis_fixture()
    db.upsert_demo_analysis(analysis)
    summary, per_round = rating_service.calculate_and_store_rating(
        db, DemoManager(str(tmp_path / "demos")), "match", "match.dem", analysis=analysis,
    )
    table = player_summary_table(analysis, summary)
    assert table.loc[0, "K/D/A"] == "0/0/0"  # Raw scoreboard intentionally says 99/99/99.
    assert summary.loc[0, "K"] == per_round["kills"].sum()
    assert summary.loc[0, "D"] == per_round["deaths"].sum()
    assert summary.loc[0, "A"] == per_round["assists"].sum()
    assert player_rounds_table(analysis, SID)["Strona gracza"].tolist() == ["CT", "T"]


def test_legacy_inputs_are_upgraded_once_and_tracking_survives(tmp_path) -> None:
    db = Database(str(tmp_path / "cache.db"))
    old = analysis_fixture()
    old.analysis_version = 0
    old.round_roster_df = pd.DataFrame()
    db.upsert_demo_analysis(old)
    db.track_player(SID)
    manager = DemoManager(str(tmp_path / "demos"))
    with (
        patch.object(manager, "analysis_path", return_value=tmp_path / "match.dem") as path,
        patch.object(rating_service, "DemoAnalyzer") as parser,
    ):
        parser.return_value.get_full_analysis.return_value = analysis_fixture()
        rating_service.calculate_and_store_rating(
            db, manager, "match", "match.dem", analysis=old,
        )
        rating_service.calculate_and_store_rating(db, manager, "match", "match.dem")
        assert parser.call_count == path.call_count == 1
    assert old.analysis_version == ANALYSIS_VERSION
    assert not old.round_roster_df.empty
    assert db.get_demo_analysis("match").analysis_version == ANALYSIS_VERSION
    assert db.list_tracked_players()[0]["steamid"] == SID
