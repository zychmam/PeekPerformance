"""Demo-only SQLite persistence and roster tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from src.models.models import DemoAnalysis
from src.storage.database import Database


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    return Database(str(tmp_path / "test.db"))


def _analysis(identity: str = "demo-a") -> DemoAnalysis:
    return DemoAnalysis(
        file_name="match.dem",
        content_hash=identity,
        stored_file_name=f"{identity}.dem",
        map_name="de_anubis",
        header={"map_name": "de_anubis"},
        player_info=pd.DataFrame([
            {"steamid": "76561198008873401", "name": "Alice"},
            {"steamid": "76561198008873402", "name": "Bob"},
        ]),
        kills_df=pd.DataFrame([{"attacker_steamid": "76561198008873401"}]),
    )


def test_demo_round_trip_and_roster(db: Database) -> None:
    analysis = _analysis()
    db.upsert_demo_analysis(analysis)
    got = db.get_demo_analysis(analysis.content_hash)
    assert got is not None
    assert got.map_name == "de_anubis"
    assert got.player_info["steamid"].tolist() == analysis.player_info["steamid"].tolist()
    assert len(got.kills_df) == 1
    assert db.list_demo_players(analysis.content_hash) == [
        {"steamid": "76561198008873401", "name": "Alice"},
        {"steamid": "76561198008873402", "name": "Bob"},
    ]
    assert len(db.list_demo_analyses()) == 1
    assert db.get_demo_analysis("match.dem") is None


def test_tracking_requires_a_parsed_demo_and_counts_matches(db: Database) -> None:
    with pytest.raises(ValueError, match="parsed demo"):
        db.track_player("76561198008873401")
    db.upsert_demo_analysis(_analysis())
    db.track_player("76561198008873401")
    db.track_player("76561198008873401")
    second = _analysis("demo-b")
    second.player_info.loc[0, "name"] = "Alice New"
    db.upsert_demo_analysis(second)
    tracked = db.list_tracked_players()
    assert len(tracked) == 1
    assert tracked[0]["steamid"] == "76561198008873401"
    assert tracked[0]["match_count"] == 2
    db.delete_demo_analysis("demo-a")
    assert db.list_tracked_players()[0]["match_count"] == 1
    db.untrack_player("76561198008873401")
    assert db.list_tracked_players() == []


def test_repeat_import_updates_one_demo_and_roster(db: Database) -> None:
    first = _analysis()
    db.upsert_demo_analysis(first)
    repeat = _analysis()
    repeat.map_name = "de_nuke"
    repeat.player_info = repeat.player_info.iloc[:1].copy()
    db.upsert_demo_analysis(repeat)
    assert len(db.list_demo_analyses()) == 1
    assert db.get_demo_analysis("demo-a").map_name == "de_nuke"
    assert len(db.list_demo_players("demo-a")) == 1


def test_old_api_tables_and_analyses_are_deleted_once(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE players (steam_id TEXT)")
        conn.execute("INSERT INTO players VALUES ('old')")
        conn.execute("CREATE TABLE matches (game_id TEXT)")
        conn.execute("INSERT INTO matches VALUES ('old-match')")
        conn.execute("CREATE TABLE demo_analyses (file_name TEXT)")
        conn.execute("INSERT INTO demo_analyses VALUES ('old.dem')")
    db = Database(str(path))
    assert db.list_demo_analyses() == []
    with sqlite3.connect(path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        assert "players" not in tables
        assert "matches" not in tables
        assert "demo_analyses" in tables
    db.upsert_demo_analysis(_analysis())
    assert len(Database(str(path)).list_demo_analyses()) == 1


def test_hash_is_required_for_persistence(db: Database) -> None:
    with pytest.raises(ValueError, match="content hash"):
        db.upsert_demo_analysis(DemoAnalysis(file_name="match.dem"))


def test_player_matches_use_materialized_rating_without_loading_events(db: Database) -> None:
    db.upsert_demo_analysis(_analysis("demo-a"))
    db.upsert_demo_analysis(_analysis("demo-b"))
    db.track_player("76561198008873401")
    summary = pd.DataFrame([
        {"steamid": "76561198008873401", "Rating": 1.23,
         "K": 19, "D": 14, "ADR": 83.5},
        {"steamid": "76561198008873402", "Rating": 0.87,
         "K": 11, "D": 18, "ADR": 61.0},
    ])
    db.save_demo_ratings("demo-a", summary, rating_version=1)
    rows = db.list_player_matches("76561198008873401", rating_version=1)
    assert len(rows) == 2
    first = next(row for row in rows if row["demo_id"] == "demo-a")
    assert first["rating"] == pytest.approx(1.23)
    assert (first["kills"], first["deaths"], first["adr"]) == (19, 14, 83.5)
    missing = next(row for row in rows if row["demo_id"] == "demo-b")
    assert missing["rating_version"] == 0
    assert missing["rating"] is None
    assert len(db.list_player_matches("76561198008873402", rating_version=1)) == 2
    stale = db.list_player_matches("76561198008873401", rating_version=2)
    assert next(row for row in stale if row["demo_id"] == "demo-a")["rating"] is None


def test_reset_discards_analyses_preserves_tracking_and_runs_once(tmp_path):
    path = tmp_path / "reset.db"
    db = Database(str(path))
    db.upsert_demo_analysis(_analysis())
    db.track_player("76561198008873401")
    source = tmp_path / "source.dem"
    source.write_bytes(b"demo preserved")
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version = 7")
    reset = Database(str(path))
    assert reset.list_demo_analyses() == []
    assert reset.list_tracked_players()[0]["steamid"] == "76561198008873401"
    assert source.read_bytes() == b"demo preserved"
    reset.upsert_demo_analysis(_analysis())
    assert len(Database(str(path)).list_demo_analyses()) == 1


def test_future_database_is_rejected_without_deleting_data(tmp_path):
    path = tmp_path / "future.db"
    db = Database(str(path))
    db.upsert_demo_analysis(_analysis())
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA user_version = 99")
    with pytest.raises(ValueError, match="newer"):
        Database(str(path))
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM demo_analyses").fetchone()[0] == 1
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 99
