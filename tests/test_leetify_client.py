"""Tests for the Leetify API client (using mocked HTTP responses)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.api.leetify_client import LeetifyAPIError, LeetifyClient
from src.config import Config


@pytest.fixture()
def client() -> LeetifyClient:
    cfg = Config(api_key="test-key", api_base_url="https://api.example.com")
    return LeetifyClient(cfg)


class TestGetPlayerProfile:
    @patch("src.api.leetify_client.requests.Session.get")
    def test_success(self, mock_get: MagicMock, client: LeetifyClient) -> None:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "meta": {"name": "TestPlayer", "avatarUrl": "https://img/avatar.jpg"},
                "games": {"csgo": {"skillLevel": {
                    "leetifyRating": 1.5,
                    "aim": 1.2,
                    "utility": 0.9,
                    "positioning": 1.1,
                }}},
                "ranks": [{"rank": 18000, "type": "premier"}],
            },
        )
        profile = client.get_player_profile("76561198096123254")
        assert profile.name == "TestPlayer"
        assert profile.leetify_rating == 1.5
        assert profile.rank == 18000

    @patch("src.api.leetify_client.requests.Session.get")
    def test_api_error(self, mock_get: MagicMock, client: LeetifyClient) -> None:
        mock_get.return_value = MagicMock(
            status_code=404,
            text="Not Found",
        )
        with pytest.raises(LeetifyAPIError) as exc_info:
            client.get_player_profile("bad_id")
        assert exc_info.value.status_code == 404


class TestGetPlayerMatches:
    @patch("src.api.leetify_client.requests.Session.get")
    def test_success(self, mock_get: MagicMock, client: LeetifyClient) -> None:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "matches": [
                    {
                        "gameId": "g1",
                        "mapName": "de_dust2",
                        "gameFinishedAt": "2024-01-15T12:00:00Z",
                        "teamAScore": 16,
                        "teamBScore": 10,
                        "ownTeamSteam64Ids": ["76561198096123254"],
                        "gameMode": "competitive",
                        "dataSource": "matchmaking",
                        "playerStats": {
                            "kills": 25,
                            "deaths": 18,
                            "assists": 4,
                            "leetifyRating": 1.3,
                            "hltvRating": 1.2,
                            "adr": 85.5,
                            "hsPercentage": 0.52,
                            "kdRatio": 1.39,
                        },
                    }
                ],
            },
        )
        matches = client.get_player_matches("76561198096123254")
        assert len(matches) == 1
        assert matches[0].map_name == "de_dust2"
        assert matches[0].result == "win"
        assert matches[0].kills == 25


class TestGetMatchDetail:
    @patch("src.api.leetify_client.requests.Session.get")
    def test_success(self, mock_get: MagicMock, client: LeetifyClient) -> None:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "mapName": "de_inferno",
                "gameFinishedAt": "2024-01-15T12:00:00Z",
                "scoreTeamA": 16,
                "scoreTeamB": 12,
                "gameMode": "competitive",
                "roundsPlayed": 28,
                "playerStats": [
                    {
                        "steam64Id": "123",
                        "name": "Alice",
                        "team": "A",
                        "kills": 20,
                        "deaths": 15,
                        "assists": 5,
                    },
                ],
            },
        )
        detail = client.get_match_detail("game-id-1")
        assert detail.map_name == "de_inferno"
        assert detail.rounds_played == 28
        assert len(detail.players) == 1
        assert detail.players[0].name == "Alice"
