"""Tests for the DemoManager file management layer."""

from __future__ import annotations

import gzip
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.demos.demo_manager import DemoManager


@pytest.fixture()
def dm(tmp_path: Path) -> DemoManager:
    return DemoManager(str(tmp_path / "demos"))


class TestSaveUploaded:
    def test_save_plain_dem(self, dm: DemoManager) -> None:
        data = b"FAKE_DEMO_DATA"
        path = dm.save_uploaded("match.dem", data)
        assert path.exists()
        assert path.name == "match.dem"
        assert path.read_bytes() == data

    def test_save_gz_decompresses(self, dm: DemoManager) -> None:
        raw = b"FAKE_DEMO_DATA"
        compressed = gzip.compress(raw)
        path = dm.save_uploaded("match.dem.gz", compressed)
        assert path.name == "match.dem"
        assert path.read_bytes() == raw


class TestListDemos:
    def test_empty_dir(self, dm: DemoManager) -> None:
        assert dm.list_demos() == []

    def test_lists_only_dem_files(self, dm: DemoManager) -> None:
        (dm.demos_dir / "a.dem").write_bytes(b"a")
        (dm.demos_dir / "b.txt").write_bytes(b"b")
        result = dm.list_demos()
        assert len(result) == 1
        assert result[0].name == "a.dem"


class TestDeleteDemo:
    def test_delete_existing(self, dm: DemoManager) -> None:
        p = dm.demos_dir / "match.dem"
        p.write_bytes(b"data")
        dm.delete_demo(p)
        assert not p.exists()

    def test_delete_outside_dir_is_noop(self, dm: DemoManager, tmp_path: Path) -> None:
        outsider = tmp_path / "other.dem"
        outsider.write_bytes(b"data")
        dm.delete_demo(outsider)
        assert outsider.exists()


class TestCleanup:
    def test_removes_old_files(self, dm: DemoManager) -> None:
        old = dm.demos_dir / "old.dem"
        old.write_bytes(b"data")
        # Patch st_mtime to make the file appear old
        real_stat = old.stat()
        old_mtime = time.time() - 40 * 86400
        import os
        os.utime(old, (old_mtime, old_mtime))
        removed = dm.cleanup_old_demos(max_age_days=30)
        assert removed == 1
        assert not old.exists()

    def test_keeps_recent_files(self, dm: DemoManager) -> None:
        recent = dm.demos_dir / "recent.dem"
        recent.write_bytes(b"data")
        removed = dm.cleanup_old_demos(max_age_days=30)
        assert removed == 0
        assert recent.exists()
