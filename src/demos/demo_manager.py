"""Manage uploaded demo files on disk."""

from __future__ import annotations

import gzip
import hashlib
import time
from pathlib import Path

import zstandard


class DemoManager:
    """Save, list, and clean up uploaded .dem files."""

    def __init__(self, demos_dir: str) -> None:
        self._dir = Path(demos_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def demos_dir(self) -> Path:
        return self._dir

    def save_uploaded(self, file_name: str, data: bytes) -> Path:
        """Save demo content without overwriting a different match with the same name."""
        name = file_name.replace("\\", "/").rsplit("/", 1)[-1]
        if not name or name in {".", ".."}:
            raise ValueError("Invalid demo file name")
        raw = self.demo_bytes(name, data)
        name = name.removesuffix(".gz").removesuffix(".zst")
        if not name.endswith(".dem"):
            raise ValueError("Expected a .dem, .dem.gz or .dem.zst file")
        content_hash = hashlib.sha256(raw).hexdigest()
        dest = self._dir / name
        if dest.exists() and self.content_hash(dest) != content_hash:
            dest = self._dir / f"{Path(name).stem}-{content_hash}.dem"
        if not dest.exists():
            dest.write_bytes(raw)
        return dest

    @staticmethod
    def demo_bytes(file_name: str, data: bytes) -> bytes:
        """Hash and store decompressed content regardless of upload compression."""
        if file_name.endswith(".gz"):
            return gzip.decompress(data)
        if file_name.endswith(".zst"):
            return zstandard.ZstdDecompressor().stream_reader(data).read()
        return data

    @classmethod
    def upload_hash(cls, file_name: str, data: bytes) -> str:
        return hashlib.sha256(cls.demo_bytes(file_name, data)).hexdigest()

    @staticmethod
    def content_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def analysis_path(self, file_name: str, content_hash: str = "") -> Path | None:
        """Resolve only a local file whose bytes match the cached analysis."""
        if Path(file_name).name != file_name or "\\" in file_name:
            return None
        path = self._dir / file_name
        if not path.is_file():
            return None
        if content_hash and self.content_hash(path) != content_hash:
            return None
        return path

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
