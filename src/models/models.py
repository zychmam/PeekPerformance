"""Data model for a parsed Counter-Strike 2 demo."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from src.demos.presentation import presentation_frame


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
    content_hash: str = ""
    stored_file_name: str = ""
    round_roster_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    analysis_version: int = 0

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
            "RoundRoster": self.round_roster_df,
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
                    presentation_frame(df, self.player_info).to_excel(
                        writer, sheet_name=sheet_name, index=False
                    )
        return buf.getvalue()

    def to_csv_zip(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for name, df in self._dataframes().items():
                if not df.empty:
                    zf.writestr(
                        f"{name}.csv",
                        presentation_frame(df, self.player_info).to_csv(index=False),
                    )
        return buf.getvalue()
