"""Parse CS2 demo files using demoparser2 and produce DataFrames."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from demoparser2 import DemoParser

from src.models.models import DemoAnalysis

logger = logging.getLogger(__name__)

_ROUND_PROPS = ["total_rounds_played", "is_warmup_period"]
_UTILITY_WEAPONS = {"hegrenade", "inferno", "molotov", "incgrenade"}


def _live_events(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    if "is_warmup_period" in result:
        result = result[~result["is_warmup_period"].fillna(False).astype(bool)]
    return result


def normalize_rounds(
    rounds: pd.DataFrame, starts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Completed non-warmup rounds, numbered from 1 in chronological order.

    Engine counters differ at event boundaries; round identity uses tick windows.
    With starts available, exclude abandoned starts and post-round events. Without
    starts, the previous round end is the conservative lower boundary. Warmup and
    restart events must carry their parser flags. A repeated engine round 1
    starts a new match segment; weapon choice alone never identifies knife rounds.
    """
    result = _live_events(rounds)
    if result.empty or "tick" not in result:
        return result
    if "winner" in result:
        result = result[result["winner"].isin([2, 3, "2", "3", "T", "CT", "TERRORIST"])]
    if "reason" in result:
        result = result[~result["reason"].isin([0, 16, "Game_Commencing", "game_commencing"])]
    result = result.sort_values("tick").drop_duplicates("tick").reset_index(drop=True)
    if "raw_total_rounds_played" not in result and "total_rounds_played" in result:
        result["raw_total_rounds_played"] = result["total_rounds_played"]
    if "raw_total_rounds_played" in result:
        counters = pd.to_numeric(result["raw_total_rounds_played"], errors="coerce")
        restarts = result.index[counters.eq(1) & counters.shift().ge(1)]
        if len(restarts):
            # FACEIT pre-match knife rounds can be marked non-warmup. Retain the
            # final match segment after an explicit engine counter restart.
            result = result.loc[restarts[-1]:].reset_index(drop=True)
    result["total_rounds_played"] = range(1, len(result) + 1)
    if starts is not None and not starts.empty and "tick" in starts:
        start_ticks = _live_events(starts)["tick"].sort_values()
        result["start_tick"] = [
            start_ticks[start_ticks <= tick].max() for tick in result["tick"]
        ]
        result = result.dropna(subset=["start_tick"])
    elif "start_tick" not in result:
        result["start_tick"] = result["tick"].shift(fill_value=-1) + 1
    return result


def normalize_round_events(events: pd.DataFrame, rounds: pd.DataFrame) -> pd.DataFrame:
    """Assign events to completed round windows, including their end tick."""
    result = _live_events(events)
    if result.empty:
        return result
    if rounds.empty or "tick" not in result:
        return result.iloc[:0].copy()
    if "raw_total_rounds_played" not in result and "total_rounds_played" in result:
        result["raw_total_rounds_played"] = result["total_rounds_played"]
    labels = pd.Series(pd.NA, index=result.index, dtype="Int64")
    for row in rounds.itertuples():
        labels.loc[result["tick"].between(row.start_tick, row.tick)] = row.total_rounds_played
    result["total_rounds_played"] = labels
    return result.dropna(subset=["total_rounds_played"]).reset_index(drop=True)


def _steamid(value: object) -> str:
    return "" if pd.isna(value) or str(value) in {"", "0", "None", "nan"} else str(value)


def enemy_mask(events: pd.DataFrame) -> pd.Series:
    """Only identified opposing T/CT players earn offensive credit."""
    required = {"attacker_steamid", "user_steamid", "attacker_team_num", "user_team_num"}
    if not required.issubset(events.columns):
        return pd.Series(False, index=events.index)
    attacker = events["attacker_steamid"].map(_steamid)
    victim = events["user_steamid"].map(_steamid)
    return (
        attacker.ne("") & victim.ne("") & attacker.ne(victim)
        & events["attacker_team_num"].isin([2, 3])
        & events["user_team_num"].isin([2, 3])
        & events["attacker_team_num"].ne(events["user_team_num"])
    )


def normalize_damage(damage: pd.DataFrame) -> pd.DataFrame:
    """Keep raw damage and add capped HP loss, enemy damage and damaging utility.

    All hurts consume HP, including self/world/team damage. The event's health
    is remaining HP; if unavailable, assume 100 at the round start and subtract
    all earlier hurts. Missing teams earn no enemy damage. Armor is excluded.
    """
    result = damage.copy()
    if result.empty:
        for column in ["actual_damage", "enemy_damage", "utility_damage"]:
            result[column] = pd.Series(dtype=float)
        result["is_enemy"] = pd.Series(dtype=bool)
        return result
    result = result.sort_values("tick", kind="stable").reset_index(drop=True)
    result["is_enemy"] = enemy_mask(result)
    hp: dict[tuple[object, str], float] = {}
    actual_values = []
    for row in result.to_dict("records"):
        key = (row.get("total_rounds_played", 0), _steamid(row.get("user_steamid")))
        raw = row.get("dmg_health", 0)
        raw = max(0.0, float(raw)) if pd.notna(raw) else 0.0
        before = hp.get(key, 100.0)
        remaining = row.get("health", row.get("user_health"))
        if pd.notna(remaining):
            after = max(0.0, float(remaining))
            actual = min(raw, max(0.0, before - after))
        else:
            actual = min(raw, before)
            after = before - actual
        hp[key] = after
        actual_values.append(actual)
    result["actual_damage"] = actual_values
    result["enemy_damage"] = result["actual_damage"].where(result["is_enemy"], 0.0)
    weapons = result.get("weapon", pd.Series("", index=result.index))
    weapons = weapons.fillna("").str.removeprefix("weapon_")
    result["utility_damage"] = result["enemy_damage"].where(weapons.isin(_UTILITY_WEAPONS), 0.0)
    return result

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
            events = self._parser.parse_event(
                "player_death",
                player=_KILL_PLAYER_EXTRA,
                other=_ROUND_PROPS,
            )
            return normalize_round_events(events, self.get_rounds())
        except Exception:
            logger.warning("Failed to parse player_death events")
            return pd.DataFrame()

    def get_damage(self) -> pd.DataFrame:
        """All player_hurt events with positions and round context."""
        try:
            events = self._parser.parse_event(
                "player_hurt",
                player=_HURT_PLAYER_EXTRA,
                other=_ROUND_PROPS,
            )
            return normalize_damage(normalize_round_events(events, self.get_rounds()))
        except Exception:
            logger.warning("Failed to parse player_hurt events")
            return pd.DataFrame()

    def get_rounds(self) -> pd.DataFrame:
        """round_end events: winner, reason, round number."""
        if hasattr(self, "_rounds"):
            return self._rounds.copy()
        try:
            rounds = self._parser.parse_event(
                "round_end",
                other=_ROUND_PROPS,
            )
        except Exception:
            logger.warning("Failed to parse round_end events")
            return pd.DataFrame()
        try:
            starts = self._parser.parse_event("round_start", other=_ROUND_PROPS)
        except Exception:
            logger.warning("Round starts unavailable; using completed round boundaries")
            starts = pd.DataFrame()
        self._rounds = normalize_rounds(rounds, starts)
        from src.demos.observations import round_clock

        try:
            freezes = self._parser.parse_event("round_freeze_end", other=_ROUND_PROPS)
        except Exception:
            freezes = pd.DataFrame()
        self._rounds = round_clock(self._rounds, freezes)
        return self._rounds.copy()

    def get_round_roster(self) -> pd.DataFrame:
        """Actual side assignments at each completed round's start."""
        rounds = self.get_rounds()
        if rounds.empty:
            return pd.DataFrame()
        try:
            roster = self._parser.parse_ticks(
                ["team_num"], ticks=rounds["start_tick"].astype(int).tolist(),
            )
            return normalize_round_events(roster, rounds)
        except Exception:
            logger.warning("Failed to parse round rosters")
            return pd.DataFrame()

    def get_bomb_events(self) -> pd.DataFrame:
        """bomb_planted and bomb_defused events."""
        try:
            results = self._parser.parse_events(
                ["bomb_planted", "bomb_defused"],
                other=_ROUND_PROPS,
            )
            frames = []
            for event_name, df in results:
                if not df.empty:
                    df = df.copy()
                    df["event"] = event_name
                    frames.append(df)
            events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            return normalize_round_events(events, self.get_rounds())
        except Exception:
            logger.warning("Failed to parse bomb events")
            return pd.DataFrame()

    def get_grenades(self) -> pd.DataFrame:
        """Full grenade trajectories: X/Y/Z per tick, thrower, type."""
        try:
            return self._parser.parse_grenades(grenades=False)
        except Exception:
            logger.warning("Failed to parse grenades")
            return pd.DataFrame()

    def get_player_blinds(self) -> pd.DataFrame:
        """player_blind events: who was blinded, by whom, duration."""
        try:
            events = self._parser.parse_event(
                "player_blind",
                player=["team_num"],
                other=_ROUND_PROPS,
            )
            events = normalize_round_events(events, self.get_rounds())
            events["is_enemy"] = enemy_mask(events)
            return events
        except Exception:
            logger.warning("Failed to parse player_blind events")
            return pd.DataFrame()

    def get_economy(self, *, freeze_ticks: list[int] | None = None,
                    strict: bool = False) -> pd.DataFrame:
        """Per-round economy data from round_freeze_end ticks."""
        try:
            if freeze_ticks is None:
                freeze_end = self._parser.parse_event("round_freeze_end")
                if freeze_end.empty:
                    return pd.DataFrame()
                freeze_ticks = freeze_end["tick"].tolist()
            if not freeze_ticks:
                return pd.DataFrame()
            return self._parser.parse_ticks(
                [
                    "balance",
                    "current_equip_value",
                    "cash_spent_this_round",
                    "start_balance",
                    "round_start_equip_value",
                    "team_num",
                ],
                ticks=freeze_ticks,
            )
        except Exception:
            if strict:
                raise
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
        """Enemy kills, all deaths and effective enemy HP damage per round."""
        return calculate_round_stats(
            self.get_kills(), self.get_damage(), self.get_rounds(), self.get_round_roster(),
        )

    # ------------------------------------------------------------------
    # Full analysis
    # ------------------------------------------------------------------

    def get_full_analysis(self) -> DemoAnalysis:
        """Run all parsers and return a complete DemoAnalysis."""
        from src.demos.rating_calculator import (
            compute_rating_from_events,
            round_stats_from_rating,
        )
        from src.demos.versions import ANALYSIS_VERSION

        header = self.get_header()
        map_name = header.get("map_name", "")

        analysis = DemoAnalysis(
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
            round_roster_df=self.get_round_roster(),
            analysis_version=ANALYSIS_VERSION,
            chat_messages_df=self.get_chat_messages(),
            convars=self.get_convars(),
        )
        _, per_round = compute_rating_from_events(
            analysis.player_info, analysis.kills_df, analysis.damage_df,
            analysis.rounds_df, analysis.bomb_events_df, roster=analysis.round_roster_df,
        )
        analysis.round_stats_df = round_stats_from_rating(per_round)
        return analysis


def calculate_round_stats(
    kills: pd.DataFrame, damage: pd.DataFrame, rounds: pd.DataFrame,
    roster: pd.DataFrame | None = None,
) -> pd.DataFrame:
    from src.demos.rating_calculator import compute_rating_from_events, round_stats_from_rating

    _, per_round = compute_rating_from_events(
        pd.DataFrame(), kills, damage, rounds, pd.DataFrame(), roster=roster,
    )
    return round_stats_from_rating(per_round)
