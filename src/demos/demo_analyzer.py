"""Parse CS2 demo files using demoparser2 and produce DataFrames."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from demoparser2 import DemoParser

from src.models.models import DemoAnalysis

logger = logging.getLogger(__name__)

# Aggregate stat fields available once per round in demoparser2
_AGGREGATE_FIELDS = [
    "kills_total",
    "deaths_total",
    "assists_total",
    "damage_total",
    "headshot_kills_total",
    "ace_rounds_total",
    "4k_rounds_total",
    "3k_rounds_total",
    "utility_damage_total",
    "enemies_flashed_total",
    "equipment_value_total",
    "money_saved_total",
    "kill_reward_total",
    "cash_earned_total",
    "alive_time_total",
    "objective_total",
]

# Extra player props to attach to player_death events
_KILL_PLAYER_EXTRA = [
    "X",
    "Y",
    "Z",
    "active_weapon_name",
    "health",
    "armor_value",
    "team_num",
    "last_place_name",
    "balance",
    "current_equip_value",
    "is_scoped",
]

# Extra player props for player_hurt events
_HURT_PLAYER_EXTRA = [
    "X",
    "Y",
    "health",
    "armor_value",
    "team_num",
]


class DemoAnalyzer:
    """Analyze a CS2 .dem file using demoparser2."""

    def __init__(self, demo_path: Path) -> None:
        self._path = demo_path
        self._parser = DemoParser(str(demo_path))

    def get_header(self) -> dict[str, str]:
        return self._parser.parse_header()

    def get_player_info(self) -> pd.DataFrame:
        return self._parser.parse_player_info()

    def get_convars(self) -> dict[str, str]:
        return {}

    def get_chat_messages(self) -> pd.DataFrame:
        try:
            return self._parser.parse_event("chat_message")
        except Exception:
            logger.debug("No chat messages in demo")
            return pd.DataFrame()

    def list_events(self) -> list[str]:
        try:
            return self._parser.list_game_events()
        except Exception:
            logger.debug("Failed to list game events")
            return []

    def get_raw_event(self, event_name: str) -> pd.DataFrame:
        try:
            return self._parser.parse_event(event_name)
        except Exception:
            logger.warning("Failed to parse event: %s", event_name)
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Core data
    # ------------------------------------------------------------------

    def get_scoreboard(self) -> pd.DataFrame:
        """Final aggregate stats per player (updated once per round by the engine)."""
        try:
            df = self._parser.parse_ticks(
                _AGGREGATE_FIELDS + ["team_num"],
            )
        except Exception:
            logger.warning("Failed to parse aggregate stats via ticks")
            return pd.DataFrame()

        if df.empty:
            return df

        # Keep the last tick per player (= final match stats)
        df = df.sort_values("tick").groupby("steamid").last().reset_index()
        df = df.rename(columns={"steamid": "steam_id", "name": "player_name"})
        return df

    def get_kills(self) -> pd.DataFrame:
        """All player_death events with extra context."""
        try:
            return self._parser.parse_event(
                "player_death",
                player=_KILL_PLAYER_EXTRA,
                other=["total_rounds_played"],
            )
        except Exception:
            logger.warning("Failed to parse player_death events")
            return pd.DataFrame()

    def get_damage(self) -> pd.DataFrame:
        """All player_hurt events with positions and round context."""
        try:
            return self._parser.parse_event(
                "player_hurt",
                player=_HURT_PLAYER_EXTRA,
                other=["total_rounds_played"],
            )
        except Exception:
            logger.warning("Failed to parse player_hurt events")
            return pd.DataFrame()

    def get_rounds(self) -> pd.DataFrame:
        """round_end events: winner, reason, round number."""
        try:
            return self._parser.parse_event(
                "round_end",
                other=["total_rounds_played"],
            )
        except Exception:
            logger.warning("Failed to parse round_end events")
            return pd.DataFrame()

    def get_bomb_events(self) -> pd.DataFrame:
        """bomb_planted and bomb_defused events."""
        try:
            results = self._parser.parse_events(
                ["bomb_planted", "bomb_defused"],
                other=["total_rounds_played"],
            )
            frames = []
            for event_name, df in results:
                if not df.empty:
                    df = df.copy()
                    df["event"] = event_name
                    frames.append(df)
            return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        except Exception:
            logger.warning("Failed to parse bomb events")
            return pd.DataFrame()

    def get_grenades(self) -> pd.DataFrame:
        """Full grenade trajectories: X/Y/Z per tick, thrower, type."""
        try:
            return self._parser.parse_grenades()
        except Exception:
            logger.warning("Failed to parse grenades")
            return pd.DataFrame()

    def get_player_blinds(self) -> pd.DataFrame:
        """player_blind events: who was blinded, by whom, duration."""
        try:
            return self._parser.parse_event(
                "player_blind",
                other=["total_rounds_played"],
            )
        except Exception:
            logger.warning("Failed to parse player_blind events")
            return pd.DataFrame()

    def get_economy(self) -> pd.DataFrame:
        """Per-round economy data from round_freeze_end ticks."""
        try:
            freeze_end = self._parser.parse_event("round_freeze_end")
            if freeze_end.empty:
                return pd.DataFrame()
            ticks = freeze_end["tick"].tolist()
            return self._parser.parse_ticks(
                [
                    "balance",
                    "current_equip_value",
                    "cash_spent_this_round",
                    "start_balance",
                    "round_start_equip_value",
                    "team_num",
                ],
                ticks=ticks,
            )
        except Exception:
            logger.warning("Failed to parse economy data")
            return pd.DataFrame()

    def get_player_states(
        self, ticks: list[int] | None = None
    ) -> pd.DataFrame:
        """Detailed per-tick player state. If *ticks* is None, samples round-start ticks."""
        props = [
            "X", "Y", "Z",
            "health", "armor_value",
            "active_weapon_name",
            "is_alive", "team_num",
            "is_scoped", "is_walking", "is_defusing",
            "is_airborne", "flash_duration",
            "last_place_name",
            "velocity_X", "velocity_Y", "velocity_Z",
            "balance", "current_equip_value",
            "pitch", "yaw",
        ]
        try:
            if ticks:
                return self._parser.parse_ticks(props, ticks=ticks)
            return self._parser.parse_ticks(props)
        except Exception:
            logger.warning("Failed to parse player state ticks")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Computed / aggregated
    # ------------------------------------------------------------------

    def get_round_stats(self) -> pd.DataFrame:
        """Kills, deaths, damage per round per player (computed from events)."""
        kills_df = self.get_kills()
        damage_df = self.get_damage()

        frames = []

        if not kills_df.empty and "total_rounds_played" in kills_df.columns:
            # Kills per round per attacker
            if "attacker_steamid" in kills_df.columns:
                k = (
                    kills_df.groupby(["total_rounds_played", "attacker_steamid"])
                    .size()
                    .reset_index(name="kills")
                )
                k = k.rename(columns={"attacker_steamid": "steamid"})
                frames.append(k)

            # Deaths per round per victim
            if "user_steamid" in kills_df.columns:
                d = (
                    kills_df.groupby(["total_rounds_played", "user_steamid"])
                    .size()
                    .reset_index(name="deaths")
                )
                d = d.rename(columns={"user_steamid": "steamid"})
                frames.append(d)

            # Headshot kills
            if "headshot" in kills_df.columns and "attacker_steamid" in kills_df.columns:
                hs = (
                    kills_df[kills_df["headshot"] == True]  # noqa: E712
                    .groupby(["total_rounds_played", "attacker_steamid"])
                    .size()
                    .reset_index(name="hs_kills")
                )
                hs = hs.rename(columns={"attacker_steamid": "steamid"})
                frames.append(hs)

        if not damage_df.empty and "total_rounds_played" in damage_df.columns:
            if "attacker_steamid" in damage_df.columns and "dmg_health" in damage_df.columns:
                dmg = (
                    damage_df.groupby(["total_rounds_played", "attacker_steamid"])["dmg_health"]
                    .sum()
                    .reset_index(name="damage")
                )
                dmg = dmg.rename(columns={"attacker_steamid": "steamid"})
                frames.append(dmg)

        if not frames:
            return pd.DataFrame()

        # Merge all
        from functools import reduce
        result = reduce(
            lambda left, right: pd.merge(
                left, right, on=["total_rounds_played", "steamid"], how="outer"
            ),
            frames,
        )
        return result.fillna(0).sort_values(["total_rounds_played", "steamid"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    # Full analysis
    # ------------------------------------------------------------------

    def get_full_analysis(self) -> DemoAnalysis:
        """Run all parsers and return a complete DemoAnalysis."""
        header = self.get_header()
        map_name = header.get("map_name", "")

        return DemoAnalysis(
            file_name=self._path.name,
            map_name=map_name,
            header=header,
            player_info=self.get_player_info(),
            scoreboard=self.get_scoreboard(),
            kills_df=self.get_kills(),
            damage_df=self.get_damage(),
            rounds_df=self.get_rounds(),
            bomb_events_df=self.get_bomb_events(),
            grenades_df=self.get_grenades(),
            player_blinds_df=self.get_player_blinds(),
            round_stats_df=self.get_round_stats(),
            chat_messages_df=self.get_chat_messages(),
            convars=self.get_convars(),
        )
