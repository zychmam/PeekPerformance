"""Data models for Leetify match and player data."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class PlayerProfile:
    """A Leetify player profile summary."""

    steam_id: str
    name: str
    leetify_rating: float | None = None
    aim_rating: float | None = None
    utility_rating: float | None = None
    positioning_rating: float | None = None
    avatar_url: str = ""
    rank: int | None = None
    rank_type: str = ""
    fetched_at: str = ""

    def __post_init__(self) -> None:
        if not self.fetched_at:
            self.fetched_at = datetime.now(UTC).isoformat()


@dataclass
class MatchSummary:
    """Lightweight match information from a player's match list."""

    game_id: str
    map_name: str
    match_date: str
    score_own: int
    score_enemy: int
    result: str  # "win" | "loss" | "tie"
    game_mode: str = ""
    data_source: str = ""

    # Per-player stats within that match
    steam_id: str = ""
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    leetify_rating: float | None = None
    hltv_rating: float | None = None
    adr: float | None = None
    hs_percent: float | None = None
    kd_ratio: float | None = None


@dataclass
class MatchDetail:
    """Full match detail from /v2/matches/{gameId}."""

    game_id: str
    map_name: str
    match_date: str
    score_team_a: int
    score_team_b: int
    game_mode: str = ""
    data_source: str = ""
    rounds_played: int = 0
    players: list[MatchPlayerStats] = field(default_factory=list)


@dataclass
class MatchPlayerStats:
    """Per-player stats within a detailed match."""

    steam_id: str
    name: str
    team: str = ""
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    leetify_rating: float | None = None
    hltv_rating: float | None = None
    adr: float | None = None
    hs_percent: float | None = None
    kd_ratio: float | None = None
    utility_damage: float | None = None
    flash_assists: int = 0
    first_kills: int = 0
    first_deaths: int = 0


@dataclass
class DemoAnalysis:
    """Results of parsing a CS2 demo file via demoparser2."""

    file_name: str
    map_name: str = ""
    header: dict[str, Any] = field(default_factory=dict)
    player_info: pd.DataFrame = field(default_factory=pd.DataFrame)
    scoreboard: pd.DataFrame = field(default_factory=pd.DataFrame)
    kills_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    damage_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    rounds_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    bomb_events_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    grenades_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    player_blinds_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    round_stats_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    chat_messages_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    convars: dict[str, str] = field(default_factory=dict)
    analyzed_at: str = ""

    def __post_init__(self) -> None:
        if not self.analyzed_at:
            self.analyzed_at = datetime.now(UTC).isoformat()

    def _dataframes(self) -> dict[str, pd.DataFrame]:
        return {
            "Scoreboard": self.scoreboard,
            "Kills": self.kills_df,
            "Damage": self.damage_df,
            "Rounds": self.rounds_df,
            "BombEvents": self.bomb_events_df,
            "Grenades": self.grenades_df,
            "PlayerBlinds": self.player_blinds_df,
            "RoundStats": self.round_stats_df,
            "ChatMessages": self.chat_messages_df,
            "PlayerInfo": self.player_info,
        }

    def _dataframes_xlsx(self) -> dict[str, pd.DataFrame]:
        """Dataframes suitable for Excel — Grenades excluded (can exceed 1M rows)."""
        return {k: v for k, v in self._dataframes().items() if k != "Grenades"}

    def to_excel(self) -> bytes:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            for sheet_name, df in self._dataframes_xlsx().items():
                if not df.empty:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        return buf.getvalue()

    def to_csv_zip(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, df in self._dataframes().items():
                if not df.empty:
                    zf.writestr(f"{name}.csv", df.to_csv(index=False))
        return buf.getvalue()
