"""Data models for Leetify match and player data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


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
