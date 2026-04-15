"""Manage uploaded demo files on disk."""

from __future__ import annotations

import gzip
import shutil
import time
from pathlib import Path


class DemoManager:
    """Save, list, and clean up uploaded .dem files."""

    def __init__(self, demos_dir: str) -> None:
        self._dir = Path(demos_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def demos_dir(self) -> Path:
        return self._dir

    def save_uploaded(self, file_name: str, data: bytes) -> Path:
        """Save an uploaded file. Auto-decompresses .dem.gz to .dem."""
        if file_name.endswith(".gz"):
            decompressed = gzip.decompress(data)
            dest = self._dir / file_name.removesuffix(".gz")
            dest.write_bytes(decompressed)
        else:
            dest = self._dir / file_name
            dest.write_bytes(data)
        return dest

    def list_demos(self) -> list[Path]:
        """Return all .dem files in the demos directory, newest first."""
        demos = sorted(self._dir.glob("*.dem"), key=lambda p: p.stat().st_mtime, reverse=True)
        return demos

    def delete_demo(self, path: Path) -> None:
        if path.exists() and path.parent == self._dir:
            path.unlink()

    def cleanup_old_demos(self, max_age_days: int = 30) -> int:
        """Remove demos older than *max_age_days*. Returns number of removed files."""
        cutoff = time.time() - max_age_days * 86400
        removed = 0
        for p in self._dir.glob("*.dem"):
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed += 1
        return removed
