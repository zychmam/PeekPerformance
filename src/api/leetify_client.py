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
        data = self._get("/v3/profile", params={"id": steam_id})
        rating = data.get("rating", {})
        ranks = data.get("ranks", {})

        return PlayerProfile(
            steam_id=data.get("steam64_id", steam_id),
            name=data.get("name", ""),
            avatar_url="",
            leetify_rating=ranks.get("leetify"),
            aim_rating=rating.get("aim"),
            utility_rating=rating.get("utility"),
            positioning_rating=rating.get("positioning"),
            rank=ranks.get("faceit"),
            rank_type="faceit" if ranks.get("faceit") is not None else "",
        )

    def get_player_matches(self, steam_id: str) -> list[MatchSummary]:
        """Fetch the match list for a player."""
        data = self._get("/v3/profile/matches", params={"id": steam_id})

        matches: list[MatchSummary] = []
        for m in data if isinstance(data, list) else data.get("matches", []):
            # Determine own team from stats
            stats_list = m.get("stats", [])
            player_stats: dict = {}
            own_team: int | None = None
            for s in stats_list:
                if str(s.get("steam64_id", "")) == steam_id:
                    player_stats = s
                    own_team = s.get("initial_team_number")
                    break

            # Parse team scores
            team_scores = m.get("team_scores", [])
            score_by_team: dict[int, int] = {}
            for ts in team_scores:
                score_by_team[ts.get("team_number", 0)] = ts.get("score", 0)

            if own_team is not None:
                score_own = score_by_team.get(own_team, 0)
                score_enemy = sum(v for k, v in score_by_team.items() if k != own_team)
            elif len(team_scores) == 2:
                score_own = team_scores[0].get("score", 0)
                score_enemy = team_scores[1].get("score", 0)
            else:
                score_own, score_enemy = 0, 0

            if score_own > score_enemy:
                result = "win"
            elif score_own < score_enemy:
                result = "loss"
            else:
                result = "tie"

            hs_kills = player_stats.get("total_hs_kills", 0)
            total_kills = player_stats.get("total_kills", 0)
            hs_percent = (hs_kills / total_kills * 100) if total_kills > 0 else None

            matches.append(
                MatchSummary(
                    game_id=m.get("id", ""),
                    map_name=m.get("map_name", ""),
                    match_date=m.get("finished_at", ""),
                    score_own=score_own,
                    score_enemy=score_enemy,
                    result=result,
                    game_mode=m.get("data_source", ""),
                    data_source=m.get("data_source", ""),
                    steam_id=steam_id,
                    kills=player_stats.get("total_kills", 0),
                    deaths=player_stats.get("total_deaths", 0),
                    assists=player_stats.get("total_assists", 0),
                    leetify_rating=player_stats.get("leetify_rating"),
                    hltv_rating=None,
                    adr=player_stats.get("dpr"),
                    hs_percent=hs_percent,
                    kd_ratio=player_stats.get("kd_ratio"),
                )
            )
        return matches

    def get_match_detail(self, game_id: str) -> MatchDetail:
        """Fetch full match detail by Leetify game ID."""
        data = self._get(f"/v2/matches/{game_id}")

        # Parse team scores
        team_scores = data.get("team_scores", [])
        score_a = team_scores[0].get("score", 0) if len(team_scores) > 0 else 0
        score_b = team_scores[1].get("score", 0) if len(team_scores) > 1 else 0

        players: list[MatchPlayerStats] = []
        for p in data.get("stats", []):
            total_kills = p.get("total_kills", 0)
            hs_kills = p.get("total_hs_kills", 0)
            hs_percent = (hs_kills / total_kills * 100) if total_kills > 0 else None

            players.append(
                MatchPlayerStats(
                    steam_id=str(p.get("steam64_id", "")),
                    name=p.get("name", ""),
                    team=str(p.get("initial_team_number", "")),
                    kills=total_kills,
                    deaths=p.get("total_deaths", 0),
                    assists=p.get("total_assists", 0),
                    leetify_rating=p.get("leetify_rating"),
                    hltv_rating=None,
                    adr=p.get("dpr"),
                    hs_percent=hs_percent,
                    kd_ratio=p.get("kd_ratio"),
                    utility_damage=p.get("he_foes_damage_avg"),
                    flash_assists=p.get("flash_assist", 0),
                    first_kills=0,
                    first_deaths=0,
                )
            )

        rounds_played = players[0].kills + players[0].deaths if players else 0
        # Use rounds_count from first player if available
        for p in data.get("stats", []):
            if "rounds_count" in p:
                rounds_played = p["rounds_count"]
                break

        return MatchDetail(
            game_id=game_id,
            map_name=data.get("map_name", ""),
            match_date=data.get("finished_at", ""),
            score_team_a=score_a,
            score_team_b=score_b,
            game_mode=data.get("data_source", ""),
            data_source=data.get("data_source", ""),
            rounds_played=rounds_played,
            players=players,
        )

    def get_match_detail_raw(self, game_id: str) -> dict[str, Any]:
        """Fetch raw match detail dict (all fields) by Leetify game ID."""
        return self._get(f"/v2/matches/{game_id}")

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
