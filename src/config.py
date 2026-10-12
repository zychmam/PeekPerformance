"""Configuration management for PeekPerformance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_CONFIG_PATH = Path.home() / ".peek_performance" / "config.json"
_DEFAULT_DB_PATH = Path.home() / ".peek_performance" / "peekperformance.db"
_DEFAULT_DEMOS_DIR = Path.home() / ".peek_performance" / "demos"

@dataclass
class Config:
    """Application configuration."""

    db_path: str = str(_DEFAULT_DB_PATH)
    demos_dir: str = str(_DEFAULT_DEMOS_DIR)

    # -------------------------------------------------------------------
    # Persistence helpers
    # -------------------------------------------------------------------

    def save(self, path: Path | None = None) -> None:
        """Persist configuration to disk as JSON."""
        path = path or _DEFAULT_CONFIG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load local storage paths; ignore obsolete API and player settings."""
        path = path or _DEFAULT_CONFIG_PATH
        data: dict = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))

        return cls(
            db_path=data.get("db_path", str(_DEFAULT_DB_PATH)),
            demos_dir=data.get("demos_dir", str(_DEFAULT_DEMOS_DIR)),
        )

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _to_dict(self) -> dict:
        return {
            "db_path": self.db_path,
            "demos_dir": self.demos_dir,
        }
