"""Tests for configuration management."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Config


class TestConfig:
    def test_defaults(self) -> None:
        cfg = Config()
        assert cfg.api_key == ""
        assert cfg.request_timeout == 30
        assert cfg.tracked_steam_ids == []

    def test_save_and_load(self, tmp_path: Path) -> None:
        path = tmp_path / "cfg.json"
        cfg = Config(api_key="my-key", request_timeout=60)
        cfg.save(path)

        loaded = Config.load(path)
        assert loaded.api_key == "my-key"
        assert loaded.request_timeout == 60

    def test_env_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = tmp_path / "cfg.json"
        Config(api_key="file-key").save(path)

        monkeypatch.setenv("LEETIFY_API_KEY", "env-key")
        loaded = Config.load(path)
        assert loaded.api_key == "env-key"

    def test_load_missing_file(self, tmp_path: Path) -> None:
        path = tmp_path / "nonexistent.json"
        cfg = Config.load(path)
        assert cfg.api_key == ""
