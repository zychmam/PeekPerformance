"""Leetify public API client.

Docs: https://api-public-docs.cs-prod.leetify.com/
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from src.config import Config
from src.models.models import (
    MatchDetail,
    MatchPlayerStats,
    MatchSummary,
    PlayerProfile,
)

logger = logging.getLogger(__name__)


class LeetifyAPIError(Exception):
    """Raised when the Leetify API returns an unexpected response."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        self.status_code = status_code
        super().__init__(f"Leetify API error {status_code}: {detail}")


class LeetifyClient:
    """Thin wrapper around the Leetify public REST API."""

    def __init__(self, config: Config) -> None:
        self._base = config.api_base_url.rstrip("/")
        self._timeout = config.request_timeout
        self._session = requests.Session()
        if config.api_key:
            self._session.headers["Authorization"] = f"Bearer {config.api_key}"

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_player_profile(self, steam_id: str) -> PlayerProfile:
        """Fetch a player profile by Steam64 ID."""
        data = self._get("/v3/profile", params={"steamId": steam_id})
        meta = data.get("meta", {})
        games = data.get("games", {})
        ratings = games.get("csgo", {}).get("skillLevel", {})
        rank_info = data.get("ranks", [{}])
        rank = rank_info[0] if rank_info else {}

        return PlayerProfile(
            steam_id=steam_id,
            name=meta.get("name", ""),
            avatar_url=meta.get("avatarUrl", ""),
            leetify_rating=ratings.get("leetifyRating"),
            aim_rating=ratings.get("aim"),
            utility_rating=ratings.get("utility"),
            positioning_rating=ratings.get("positioning"),
            rank=rank.get("rank"),
            rank_type=rank.get("type", ""),
        )

    def get_player_matches(self, steam_id: str) -> list[MatchSummary]:
        """Fetch the match list for a player."""
        data = self._get("/v3/profile/matches", params={"steamId": steam_id})

        matches: list[MatchSummary] = []
        for m in data if isinstance(data, list) else data.get("matches", []):
            own = m.get("ownTeamSteam64Ids", [])
            is_own = steam_id in [str(sid) for sid in own]

            score_a = m.get("teamAScore", m.get("scoreTeamA", 0))
            score_b = m.get("teamBScore", m.get("scoreTeamB", 0))

            if is_own:
                score_own, score_enemy = score_a, score_b
            else:
                score_own, score_enemy = score_b, score_a

            if score_own > score_enemy:
                result = "win"
            elif score_own < score_enemy:
                result = "loss"
            else:
                result = "tie"

            player_stats = m.get("playerStats", {})

            matches.append(
                MatchSummary(
                    game_id=m.get("gameId", m.get("id", "")),
                    map_name=m.get("mapName", ""),
                    match_date=m.get("gameFinishedAt", m.get("createdAt", "")),
                    score_own=score_own,
                    score_enemy=score_enemy,
                    result=result,
                    game_mode=m.get("gameMode", ""),
                    data_source=m.get("dataSource", ""),
                    steam_id=steam_id,
                    kills=player_stats.get("kills", 0),
                    deaths=player_stats.get("deaths", 0),
                    assists=player_stats.get("assists", 0),
                    leetify_rating=player_stats.get("leetifyRating"),
                    hltv_rating=player_stats.get("hltvRating"),
                    adr=player_stats.get("adr"),
                    hs_percent=player_stats.get("hsPercentage"),
                    kd_ratio=player_stats.get("kdRatio"),
                )
            )
        return matches

    def get_match_detail(self, game_id: str) -> MatchDetail:
        """Fetch full match detail by Leetify game ID."""
        data = self._get(f"/v2/matches/{game_id}")

        players: list[MatchPlayerStats] = []
        for p in data.get("playerStats", []):
            players.append(
                MatchPlayerStats(
                    steam_id=str(p.get("steam64Id", "")),
                    name=p.get("name", ""),
                    team=p.get("team", ""),
                    kills=p.get("kills", 0),
                    deaths=p.get("deaths", 0),
                    assists=p.get("assists", 0),
                    leetify_rating=p.get("leetifyRating"),
                    hltv_rating=p.get("hltvRating"),
                    adr=p.get("adr"),
                    hs_percent=p.get("hsPercentage"),
                    kd_ratio=p.get("kdRatio"),
                    utility_damage=p.get("utilityDamage"),
                    flash_assists=p.get("flashAssists", 0),
                    first_kills=p.get("firstKills", 0),
                    first_deaths=p.get("firstDeaths", 0),
                )
            )

        return MatchDetail(
            game_id=game_id,
            map_name=data.get("mapName", ""),
            match_date=data.get("gameFinishedAt", data.get("createdAt", "")),
            score_team_a=data.get("scoreTeamA", 0),
            score_team_b=data.get("scoreTeamB", 0),
            game_mode=data.get("gameMode", ""),
            data_source=data.get("dataSource", ""),
            rounds_played=data.get("roundsPlayed", 0),
            players=players,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base}{path}"
        logger.debug("GET %s params=%s", url, params)
        resp = self._session.get(url, params=params, timeout=self._timeout)
        if resp.status_code != 200:
            raise LeetifyAPIError(resp.status_code, resp.text[:300])
        return resp.json()
