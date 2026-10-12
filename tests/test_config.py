"""Local configuration no longer persists Leetify credentials."""

from __future__ import annotations

import json
from pathlib import Path

from src.config import Config


def test_save_and_load_storage_paths(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    config = Config(db_path=str(tmp_path / "data.db"), demos_dir=str(tmp_path / "demos"))
    config.save(path)
    assert Config.load(path) == config
    assert set(json.loads(path.read_text(encoding="utf-8"))) == {"db_path", "demos_dir"}


def test_old_api_settings_are_ignored_and_removed_on_save(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"db_path": "data.db", "api_key": "secret",
                                "tracked_steam_ids": ["123"]}), encoding="utf-8")
    config = Config.load(path)
    assert config.db_path == "data.db"
    config.save(path)
    assert "secret" not in path.read_text(encoding="utf-8")
    assert "tracked_steam_ids" not in path.read_text(encoding="utf-8")


def test_load_missing_file(tmp_path: Path) -> None:
    assert Config.load(tmp_path / "missing.json") == Config()
