"""SQLite-based local cache for harvested Leetify data."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from src.models.models import MatchDetail, MatchPlayerStats, MatchSummary, PlayerProfile

_SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    steam_id       TEXT PRIMARY KEY,
    name           TEXT NOT NULL DEFAULT '',
    leetify_rating REAL,
    aim_rating     REAL,
    utility_rating REAL,
    positioning_rating REAL,
    avatar_url     TEXT NOT NULL DEFAULT '',
    rank           INTEGER,
    rank_type      TEXT NOT NULL DEFAULT '',
    fetched_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    game_id      TEXT NOT NULL,
    steam_id     TEXT NOT NULL,
    map_name     TEXT NOT NULL DEFAULT '',
    match_date   TEXT NOT NULL DEFAULT '',
    score_own    INTEGER NOT NULL DEFAULT 0,
    score_enemy  INTEGER NOT NULL DEFAULT 0,
    result       TEXT NOT NULL DEFAULT '',
    game_mode    TEXT NOT NULL DEFAULT '',
    data_source  TEXT NOT NULL DEFAULT '',
    kills        INTEGER NOT NULL DEFAULT 0,
    deaths       INTEGER NOT NULL DEFAULT 0,
    assists      INTEGER NOT NULL DEFAULT 0,
    leetify_rating REAL,
    hltv_rating    REAL,
    adr            REAL,
    hs_percent     REAL,
    kd_ratio       REAL,
    PRIMARY KEY (game_id, steam_id)
);

CREATE TABLE IF NOT EXISTS match_details (
    game_id       TEXT PRIMARY KEY,
    data          TEXT NOT NULL,
    fetched_at    TEXT NOT NULL
);
"""


class Database:
    """Simple SQLite storage for caching Leetify data locally."""

    def __init__(self, db_path: str) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._init_schema()

    # ------------------------------------------------------------------
    # Context manager for connections
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # Players
    # ------------------------------------------------------------------

    def upsert_player(self, player: PlayerProfile) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO players (
                    steam_id, name, leetify_rating, aim_rating,
                    utility_rating, positioning_rating,
                    avatar_url, rank, rank_type, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(steam_id) DO UPDATE SET
                    name=excluded.name,
                    leetify_rating=excluded.leetify_rating,
                    aim_rating=excluded.aim_rating,
                    utility_rating=excluded.utility_rating,
                    positioning_rating=excluded.positioning_rating,
                    avatar_url=excluded.avatar_url,
                    rank=excluded.rank,
                    rank_type=excluded.rank_type,
                    fetched_at=excluded.fetched_at
                """,
                (
                    player.steam_id,
                    player.name,
                    player.leetify_rating,
                    player.aim_rating,
                    player.utility_rating,
                    player.positioning_rating,
                    player.avatar_url,
                    player.rank,
                    player.rank_type,
                    player.fetched_at,
                ),
            )

    def get_player(self, steam_id: str) -> PlayerProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM players WHERE steam_id = ?", (steam_id,)
            ).fetchone()
        if row is None:
            return None
        return PlayerProfile(**dict(row))

    def list_players(self) -> list[PlayerProfile]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM players ORDER BY name").fetchall()
        return [PlayerProfile(**dict(r)) for r in rows]

    def delete_player(self, steam_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM players WHERE steam_id = ?", (steam_id,))
            conn.execute("DELETE FROM matches WHERE steam_id = ?", (steam_id,))

    # ------------------------------------------------------------------
    # Matches
    # ------------------------------------------------------------------

    def upsert_matches(self, matches: list[MatchSummary]) -> None:
        with self._connect() as conn:
            for m in matches:
                conn.execute(
                    """
                    INSERT INTO matches (
                        game_id, steam_id, map_name, match_date,
                        score_own, score_enemy, result, game_mode, data_source,
                        kills, deaths, assists,
                        leetify_rating, hltv_rating, adr, hs_percent, kd_ratio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(game_id, steam_id) DO UPDATE SET
                        map_name=excluded.map_name,
                        match_date=excluded.match_date,
                        score_own=excluded.score_own,
                        score_enemy=excluded.score_enemy,
                        result=excluded.result,
                        game_mode=excluded.game_mode,
                        data_source=excluded.data_source,
                        kills=excluded.kills,
                        deaths=excluded.deaths,
                        assists=excluded.assists,
                        leetify_rating=excluded.leetify_rating,
                        hltv_rating=excluded.hltv_rating,
                        adr=excluded.adr,
                        hs_percent=excluded.hs_percent,
                        kd_ratio=excluded.kd_ratio
                    """,
                    (
                        m.game_id,
                        m.steam_id,
                        m.map_name,
                        m.match_date,
                        m.score_own,
                        m.score_enemy,
                        m.result,
                        m.game_mode,
                        m.data_source,
                        m.kills,
                        m.deaths,
                        m.assists,
                        m.leetify_rating,
                        m.hltv_rating,
                        m.adr,
                        m.hs_percent,
                        m.kd_ratio,
                    ),
                )

    def get_matches(self, steam_id: str) -> list[MatchSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM matches WHERE steam_id = ? ORDER BY match_date DESC",
                (steam_id,),
            ).fetchall()
        return [MatchSummary(**dict(r)) for r in rows]

    def get_all_matches(self) -> list[MatchSummary]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM matches ORDER BY match_date DESC"
            ).fetchall()
        return [MatchSummary(**dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Match details (stored as JSON blob)
    # ------------------------------------------------------------------

    def upsert_match_detail(self, detail: MatchDetail) -> None:
        with self._connect() as conn:
            data = asdict(detail)
            conn.execute(
                """
                INSERT INTO match_details (game_id, data, fetched_at)
                VALUES (?, ?, ?)
                ON CONFLICT(game_id) DO UPDATE SET
                    data=excluded.data,
                    fetched_at=excluded.fetched_at
                """,
                (detail.game_id, json.dumps(data), datetime.now(UTC).isoformat()),
            )

    def get_match_detail(self, game_id: str) -> MatchDetail | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM match_details WHERE game_id = ?", (game_id,)
            ).fetchone()
        if row is None:
            return None
        data = json.loads(row["data"])
        players = [MatchPlayerStats(**p) for p in data.pop("players", [])]
        return MatchDetail(**data, players=players)
