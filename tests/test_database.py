"""Tests for the SQLite storage layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.models.models import MatchDetail, MatchPlayerStats, MatchSummary, PlayerProfile
from src.storage.database import Database


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    return Database(str(tmp_path / "test.db"))


class TestPlayerCRUD:
    def test_upsert_and_get(self, db: Database) -> None:
        player = PlayerProfile(
            steam_id="123",
            name="TestPlayer",
            leetify_rating=1.5,
            aim_rating=1.2,
            utility_rating=0.9,
            positioning_rating=1.1,
        )
        db.upsert_player(player)
        got = db.get_player("123")
        assert got is not None
        assert got.name == "TestPlayer"
        assert got.leetify_rating == 1.5

    def test_get_missing_returns_none(self, db: Database) -> None:
        assert db.get_player("missing") is None

    def test_list_players(self, db: Database) -> None:
        db.upsert_player(PlayerProfile(steam_id="1", name="Alice"))
        db.upsert_player(PlayerProfile(steam_id="2", name="Bob"))
        players = db.list_players()
        assert len(players) == 2
        assert players[0].name == "Alice"

    def test_delete_player(self, db: Database) -> None:
        db.upsert_player(PlayerProfile(steam_id="1", name="Alice"))
        db.delete_player("1")
        assert db.get_player("1") is None

    def test_upsert_updates_existing(self, db: Database) -> None:
        db.upsert_player(PlayerProfile(steam_id="1", name="Old"))
        db.upsert_player(PlayerProfile(steam_id="1", name="New"))
        got = db.get_player("1")
        assert got is not None
        assert got.name == "New"


class TestMatchCRUD:
    def test_upsert_and_get(self, db: Database) -> None:
        m = MatchSummary(
            game_id="g1",
            steam_id="s1",
            map_name="de_dust2",
            match_date="2024-01-01",
            score_own=16,
            score_enemy=10,
            result="win",
            kills=25,
            deaths=15,
            assists=3,
        )
        db.upsert_matches([m])
        matches = db.get_matches("s1")
        assert len(matches) == 1
        assert matches[0].map_name == "de_dust2"
        assert matches[0].kills == 25

    def test_get_all_matches(self, db: Database) -> None:
        db.upsert_matches([
            MatchSummary(
                game_id="g1", steam_id="s1", map_name="m1",
                match_date="2024-01-01", score_own=16, score_enemy=10, result="win",
            ),
            MatchSummary(
                game_id="g2", steam_id="s2", map_name="m2",
                match_date="2024-01-02", score_own=10, score_enemy=16, result="loss",
            ),
        ])
        assert len(db.get_all_matches()) == 2


class TestMatchDetailCRUD:
    def test_upsert_and_get(self, db: Database) -> None:
        detail = MatchDetail(
            game_id="g1",
            map_name="de_inferno",
            match_date="2024-01-01",
            score_team_a=16,
            score_team_b=12,
            rounds_played=28,
            players=[
                MatchPlayerStats(steam_id="s1", name="Alice", kills=20, deaths=15),
                MatchPlayerStats(steam_id="s2", name="Bob", kills=18, deaths=17),
            ],
        )
        db.upsert_match_detail(detail)
        got = db.get_match_detail("g1")
        assert got is not None
        assert got.map_name == "de_inferno"
        assert len(got.players) == 2
        assert got.players[0].name == "Alice"

    def test_get_missing_returns_none(self, db: Database) -> None:
        assert db.get_match_detail("missing") is None
