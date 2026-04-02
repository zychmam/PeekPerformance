"""Configuration management for LeetifyHarvester."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_CONFIG_PATH = Path.home() / ".leetify_harvester" / "config.json"
_DEFAULT_DB_PATH = Path.home() / ".leetify_harvester" / "harvester.db"

API_BASE_URL = "https://api-public.cs-prod.leetify.com"


@dataclass
class Config:
    """Application configuration."""

    api_key: str = ""
    db_path: str = str(_DEFAULT_DB_PATH)
    api_base_url: str = API_BASE_URL
    request_timeout: int = 30
    tracked_steam_ids: list[str] = field(default_factory=list)

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
        """Load configuration from disk, falling back to environment / defaults."""
        path = path or _DEFAULT_CONFIG_PATH
        data: dict = {}
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))

        # Environment variable overrides
        api_key = os.environ.get("LEETIFY_API_KEY", data.get("api_key", ""))
        return cls(
            api_key=api_key,
            db_path=data.get("db_path", str(_DEFAULT_DB_PATH)),
            api_base_url=data.get("api_base_url", API_BASE_URL),
            request_timeout=int(data.get("request_timeout", 30)),
            tracked_steam_ids=data.get("tracked_steam_ids", []),
        )

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _to_dict(self) -> dict:
        return {
            "api_key": self.api_key,
            "db_path": self.db_path,
            "api_base_url": self.api_base_url,
            "request_timeout": self.request_timeout,
            "tracked_steam_ids": self.tracked_steam_ids,
        }
