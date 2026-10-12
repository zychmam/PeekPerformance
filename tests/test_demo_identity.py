"""Regression tests for exact player identity and content-addressed demo caching."""

from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
import zstandard

from src.demos.demo_manager import DemoManager
from src.gui import app
from src.models.models import DemoAnalysis
from src.storage.database import Database

STEAM_ID = "76561198008873401"


@pytest.mark.parametrize("column", ["steamid", "attacker_steamid", "user_steamid", "steam_id"])
@pytest.mark.parametrize("dtype", ["object", "Int64", "UInt64", "string"])
def test_steam_ids_remain_exact_with_missing_values(tmp_path: Path, column: str, dtype: str):
    values = [STEAM_ID, None] if dtype in {"object", "string"} else [int(STEAM_ID), None]
    frame = pd.DataFrame({column: pd.Series(values, dtype=dtype), "damage": [99, 0]})
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(DemoAnalysis(
        file_name="match.dem", content_hash="identity-round-trip", damage_df=frame,
    ))
    got = db.get_demo_analysis("identity-round-trip")
    assert got is not None
    assert got.damage_df[column].tolist() == [STEAM_ID, None]
    assert got.damage_df["damage"].tolist() == [99, 0]
    # Saving must not mutate parser dataframes used elsewhere in the app.
    assert frame[column].dtype == pd.Series(values, dtype=dtype).dtype


def test_json_integer_with_null_is_normalized_before_dataframe_inference():
    frame = Database._json_to_df(
        '[{"steamid":76561198008873401},{"steamid":null}]'
    )
    assert frame["steamid"].tolist() == [STEAM_ID, None]


def test_two_same_named_demos_have_independent_files_and_analyses(tmp_path: Path):
    dm = DemoManager(str(tmp_path / "demos"))
    db = Database(str(tmp_path / "cache.db"))
    first = dm.save_uploaded("match.dem", b"first match")
    second = dm.save_uploaded("match.dem", b"second match")
    for path, map_name in [(first, "de_nuke"), (second, "de_dust2")]:
        db.upsert_demo_analysis(DemoAnalysis(
            file_name="match.dem", map_name=map_name,
            content_hash=dm.content_hash(path), stored_file_name=path.name,
        ))
    assert first != second
    assert first.read_bytes() == b"first match"
    assert second.read_bytes() == b"second match"
    assert len(db.list_demo_analyses()) == 2
    assert db.get_demo_analysis(dm.content_hash(first)).map_name == "de_nuke"
    assert db.get_demo_analysis(dm.content_hash(second)).map_name == "de_dust2"
    assert db.get_demo_analysis("match.dem") is None  # Only content hashes select matches.
    db.delete_demo_analysis("match.dem")
    assert len(db.list_demo_analyses()) == 2
    db.delete_demo_analysis(dm.content_hash(first))
    assert len(db.list_demo_analyses()) == 1
    assert db.get_demo_analysis(dm.content_hash(second)).map_name == "de_dust2"


def test_gzip_and_renamed_identical_content_reuse_cache(tmp_path: Path):
    dm = DemoManager(str(tmp_path / "demos"))
    raw = b"same decompressed match"
    identity = dm.upload_hash("match.dem", raw)
    assert dm.upload_hash("renamed.dem.gz", gzip.compress(raw)) == identity
    zst_data = zstandard.ZstdCompressor().compress(raw)
    assert dm.upload_hash("renamed.dem.zst", zst_data) == identity
    first = dm.save_uploaded("match.dem", raw)
    assert dm.save_uploaded("match.dem.gz", gzip.compress(raw)) == first
    assert dm.save_uploaded("match.dem.zst", zst_data) == first
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(DemoAnalysis(file_name="match.dem", content_hash=identity))
    db.upsert_demo_analysis(DemoAnalysis(file_name="renamed.dem", content_hash=identity))
    assert len(db.list_demo_analyses()) == 1


def test_uploaded_path_cannot_escape_demo_directory(tmp_path: Path):
    dm = DemoManager(str(tmp_path / "demos"))
    path = dm.save_uploaded("../../match.dem", b"demo")
    assert path.parent == dm.demos_dir
    assert dm.analysis_path("../match.dem") is None
    assert dm.analysis_path("..\\match.dem") is None


def test_analysis_path_rejects_changed_source_file(tmp_path: Path):
    dm = DemoManager(str(tmp_path / "demos"))
    path = dm.save_uploaded("match.dem", b"match A")
    identity = dm.content_hash(path)
    assert dm.analysis_path(path.name, identity) == path
    path.write_bytes(b"match B")
    assert dm.analysis_path(path.name, identity) is None


def test_legacy_cache_is_removed_on_demo_only_migration(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    original = json.dumps([{"steamid": int(STEAM_ID)}])
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE demo_analyses (file_name TEXT PRIMARY KEY, player_info TEXT)"
        )
        connection.execute("INSERT INTO demo_analyses VALUES (?, ?)", ("match.dem", original))
    db = Database(str(db_path))
    assert db.get_demo_analysis("match.dem") is None
    assert db.list_demo_analyses() == []
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "demo_analyses_legacy" not in tables
        assert "demo_analyses" in tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
    # Opening the migrated database again preserves newly parsed demos.
    db = Database(str(db_path))
    db.upsert_demo_analysis(DemoAnalysis(file_name="match.dem", content_hash="new-content"))
    assert db.get_demo_analysis("new-content") is not None
    assert len(Database(str(db_path)).list_demo_analyses()) == 1


def test_upload_flow_keeps_same_named_matches_separate(tmp_path: Path):
    manager = DemoManager(str(tmp_path / "demos"))
    database = Database(str(tmp_path / "cache.db"))

    class FakeAnalyzer:
        def __init__(self, path: Path) -> None:
            self.path = path

        def get_full_analysis(self) -> DemoAnalysis:
            return DemoAnalysis(file_name=self.path.name)

    with (
        patch.object(app, "_get_demo_manager", return_value=manager),
        patch.object(app, "_get_db", return_value=database),
        patch.object(app, "DemoAnalyzer", FakeAnalyzer),
    ):
        first = app._analyze_demo("match.dem", b"first")
        second = app._analyze_demo("match.dem", b"second")

    assert first.content_hash != second.content_hash
    assert first.stored_file_name != second.stored_file_name
    assert len(database.list_demo_analyses()) == 2
    assert database.get_demo_analysis(first.content_hash).stored_file_name == "match.dem"
    restored_second = database.get_demo_analysis(second.content_hash)
    assert restored_second.stored_file_name == second.stored_file_name
