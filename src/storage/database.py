"""Local SQLite store for parsed CS2 demos and players selected from them."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from src.models.models import DemoAnalysis

_SCHEMA_VERSION = 8
_OLD_TABLES = (
    "demo_coach_round_inputs",
    "demo_coach_enrichment",
    "demo_spatial_context",
    "demo_metric_results",
    "demo_catalog",
    "demo_ratings",
    "demo_players",
    "tracked_players",
    "demo_analyses",
    "demo_analyses_legacy",
    "match_details_raw",
    "match_details",
    "matches",
    "players",
)
_CREATE_TABLES = (
    """CREATE TABLE IF NOT EXISTS coach_stage_manifests (
        demo_id TEXT NOT NULL REFERENCES demo_analyses(demo_id) ON DELETE CASCADE,
        stage TEXT NOT NULL, cache_key TEXT NOT NULL, manifest TEXT NOT NULL,
        PRIMARY KEY (demo_id, stage)
    )""",
    """CREATE TABLE IF NOT EXISTS coach_stage_rounds (
        demo_id TEXT NOT NULL, stage TEXT NOT NULL, round_number INTEGER NOT NULL,
        cache_key TEXT NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY (demo_id, stage, round_number),
        FOREIGN KEY (demo_id, stage) REFERENCES coach_stage_manifests(demo_id, stage)
            ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS demo_analyses (
        demo_id TEXT PRIMARY KEY,
        file_name TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        stored_file_name TEXT NOT NULL,
        map_name TEXT NOT NULL DEFAULT '',
        header TEXT NOT NULL DEFAULT '{}',
        player_info TEXT NOT NULL DEFAULT '[]',
        scoreboard TEXT NOT NULL DEFAULT '[]',
        kills TEXT NOT NULL DEFAULT '[]',
        damage TEXT NOT NULL DEFAULT '[]',
        rounds TEXT NOT NULL DEFAULT '[]',
        bomb_events TEXT NOT NULL DEFAULT '[]',
        grenades TEXT NOT NULL DEFAULT '[]',
        player_blinds TEXT NOT NULL DEFAULT '[]',
        round_stats TEXT NOT NULL DEFAULT '[]',
        chat_messages TEXT NOT NULL DEFAULT '[]',
        convars TEXT NOT NULL DEFAULT '{}',
        analyzed_at TEXT NOT NULL,
        rating_version INTEGER NOT NULL DEFAULT 0,
        round_roster TEXT NOT NULL DEFAULT '[]',
        analysis_version INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS demo_players (
        demo_id TEXT NOT NULL REFERENCES demo_analyses(demo_id) ON DELETE CASCADE,
        steamid TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (demo_id, steamid)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_demo_players_steamid ON demo_players(steamid)",
    """CREATE TABLE IF NOT EXISTS tracked_players (
        steamid TEXT PRIMARY KEY,
        added_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS demo_ratings (
        demo_id TEXT NOT NULL REFERENCES demo_analyses(demo_id) ON DELETE CASCADE,
        steamid TEXT NOT NULL,
        rating_version INTEGER NOT NULL,
        rating REAL NOT NULL,
        kills INTEGER NOT NULL,
        deaths INTEGER NOT NULL,
        adr REAL NOT NULL,
        PRIMARY KEY (demo_id, steamid)
    )""",
    """CREATE TABLE IF NOT EXISTS demo_catalog (
        demo_id TEXT PRIMARY KEY REFERENCES demo_analyses(demo_id) ON DELETE CASCADE,
        file_name TEXT NOT NULL,
        stored_file_name TEXT NOT NULL,
        map_name TEXT NOT NULL DEFAULT '',
        analyzed_at TEXT NOT NULL,
        rating_version INTEGER NOT NULL DEFAULT 0
    )""",
    "CREATE INDEX IF NOT EXISTS idx_demo_catalog_date ON demo_catalog(analyzed_at DESC)",
    """CREATE TABLE IF NOT EXISTS demo_metric_results (
        demo_id TEXT PRIMARY KEY REFERENCES demo_analyses(demo_id) ON DELETE CASCADE,
        analysis_version INTEGER NOT NULL,
        metrics_version INTEGER NOT NULL,
        summary TEXT NOT NULL,
        per_round TEXT NOT NULL
    )""",
)


class Database:
    """Persist each analyzed demo by decompressed SHA-256 content identity."""

    def __init__(self, db_path: str) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(path)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version > _SCHEMA_VERSION:
                raise ValueError("Database schema is newer than this application")
            if version < _SCHEMA_VERSION:
                # M1 discards historical analyses; player identities are independent.
                for name in ("coach_stage_rounds", "coach_stage_manifests", *_OLD_TABLES):
                    if name != "tracked_players":
                        conn.execute(f"DROP TABLE IF EXISTS {name}")
            for statement in _CREATE_TABLES:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")

    @staticmethod
    def _is_steam_id(column: str) -> bool:
        return str(column).lower().replace("_", "").endswith("steamid")

    @staticmethod
    def _df_to_json(df: pd.DataFrame) -> str:
        if df.empty:
            return "[]"
        safe = df.copy()
        for column in safe.columns:
            if Database._is_steam_id(column):
                safe[column] = safe[column].astype("string")
        return safe.to_json(orient="records")

    @staticmethod
    def _json_to_df(data: str) -> pd.DataFrame:
        if not data or data == "[]":
            return pd.DataFrame()
        records = json.loads(data)
        for record in records:
            for column, value in record.items():
                if Database._is_steam_id(column) and value is not None:
                    record[column] = str(value)
        return pd.DataFrame.from_records(records)

    @staticmethod
    def _roster(analysis: DemoAnalysis) -> list[tuple[str, str]]:
        if analysis.player_info.empty or "steamid" not in analysis.player_info:
            return []
        players: dict[str, str] = {}
        for row in analysis.player_info.to_dict("records"):
            value = row.get("steamid")
            if pd.isna(value) or str(value) in {"", "0"}:
                continue
            steamid = str(value)
            name = row.get("name")
            players[steamid] = "" if name is None or pd.isna(name) else str(name)
        return sorted(players.items())

    def upsert_demo_analysis(self, analysis: DemoAnalysis) -> None:
        if not analysis.content_hash:
            raise ValueError("A parsed demo must have a content hash before saving")
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO demo_analyses (
                    demo_id, file_name, content_hash, stored_file_name,
                    map_name, header, player_info, scoreboard,
                    kills, damage, rounds, bomb_events, grenades,
                    player_blinds, round_stats, chat_messages, convars, analyzed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(demo_id) DO UPDATE SET
                    file_name=excluded.file_name,
                    stored_file_name=excluded.stored_file_name,
                    map_name=excluded.map_name,
                    header=excluded.header,
                    player_info=excluded.player_info,
                    scoreboard=excluded.scoreboard,
                    kills=excluded.kills,
                    damage=excluded.damage,
                    rounds=excluded.rounds,
                    bomb_events=excluded.bomb_events,
                    grenades=excluded.grenades,
                    player_blinds=excluded.player_blinds,
                    round_stats=excluded.round_stats,
                    chat_messages=excluded.chat_messages,
                    convars=excluded.convars,
                    analyzed_at=excluded.analyzed_at""",
                (
                    analysis.content_hash,
                    analysis.file_name,
                    analysis.content_hash,
                    analysis.stored_file_name or analysis.file_name,
                    analysis.map_name,
                    json.dumps(analysis.header),
                    self._df_to_json(analysis.player_info),
                    self._df_to_json(analysis.scoreboard),
                    self._df_to_json(analysis.kills_df),
                    self._df_to_json(analysis.damage_df),
                    self._df_to_json(analysis.rounds_df),
                    self._df_to_json(analysis.bomb_events_df),
                    self._df_to_json(analysis.grenades_df),
                    self._df_to_json(analysis.player_blinds_df),
                    self._df_to_json(analysis.round_stats_df),
                    self._df_to_json(analysis.chat_messages_df),
                    json.dumps(analysis.convars),
                    analysis.analyzed_at,
                ),
            )
            conn.execute("DELETE FROM demo_players WHERE demo_id = ?", (analysis.content_hash,))
            conn.execute(
                "UPDATE demo_analyses SET round_roster = ?, analysis_version = ?, "
                "rating_version = 0 "
                "WHERE demo_id = ?",
                (
                    self._df_to_json(analysis.round_roster_df),
                    analysis.analysis_version,
                    analysis.content_hash,
                ),
            )
            conn.execute(
                "DELETE FROM demo_metric_results WHERE demo_id = ?", (analysis.content_hash,)
            )
            conn.execute(
                "DELETE FROM coach_stage_manifests WHERE demo_id = ?", (analysis.content_hash,)
            )
            conn.execute("DELETE FROM demo_ratings WHERE demo_id = ?", (analysis.content_hash,))
            conn.executemany(
                "INSERT INTO demo_players (demo_id, steamid, name) VALUES (?, ?, ?)",
                [
                    (analysis.content_hash, steamid, name)
                    for steamid, name in self._roster(analysis)
                ],
            )
            conn.execute(
                """INSERT INTO demo_catalog
                   (demo_id, file_name, stored_file_name, map_name, analyzed_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(demo_id) DO UPDATE SET
                       file_name=excluded.file_name,
                       stored_file_name=excluded.stored_file_name,
                       map_name=excluded.map_name,
                       analyzed_at=excluded.analyzed_at,
                       rating_version=0""",
                (
                    analysis.content_hash,
                    analysis.file_name,
                    analysis.stored_file_name or analysis.file_name,
                    analysis.map_name,
                    analysis.analyzed_at,
                ),
            )

    def get_demo_analysis(
        self,
        demo_id: str,
        *,
        include_auxiliary: bool = True,
    ) -> DemoAnalysis | None:
        """Read saved inputs; coaching can skip trajectories, chat and scoreboard."""
        columns = (
            "*"
            if include_auxiliary
            else (
                "file_name, content_hash, stored_file_name, map_name, header, player_info, "
                "kills, damage, rounds, bomb_events, player_blinds, round_stats, convars, "
                "analyzed_at, round_roster, analysis_version"
            )
        )
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {columns} FROM demo_analyses WHERE demo_id = ?", (demo_id,)
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        return DemoAnalysis(
            file_name=d["file_name"],
            content_hash=d["content_hash"],
            stored_file_name=d["stored_file_name"],
            map_name=d["map_name"],
            header=json.loads(d["header"]),
            player_info=self._json_to_df(d["player_info"]),
            scoreboard=self._json_to_df(d.get("scoreboard", "[]")),
            kills_df=self._json_to_df(d["kills"]),
            damage_df=self._json_to_df(d["damage"]),
            rounds_df=self._json_to_df(d["rounds"]),
            bomb_events_df=self._json_to_df(d["bomb_events"]),
            grenades_df=self._json_to_df(d.get("grenades", "[]")),
            player_blinds_df=self._json_to_df(d["player_blinds"]),
            round_stats_df=self._json_to_df(d["round_stats"]),
            chat_messages_df=self._json_to_df(d.get("chat_messages", "[]")),
            convars=json.loads(d["convars"]),
            analyzed_at=d["analyzed_at"],
            round_roster_df=self._json_to_df(d["round_roster"]),
            analysis_version=d["analysis_version"],
        )

    def list_demo_analyses(self) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT demo_id, demo_id AS content_hash, file_name, stored_file_name, "
                "map_name, analyzed_at FROM demo_catalog ORDER BY analyzed_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_stage_manifest(
        self, demo_id: str, stage: str, cache_key: str | None = None
    ) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cache_key, manifest FROM coach_stage_manifests "
                "WHERE demo_id = ? AND stage = ?",
                (demo_id, stage),
            ).fetchone()
        if row is None or cache_key is not None and row["cache_key"] != cache_key:
            return None
        return json.loads(row["manifest"])

    def get_stage_rounds(
        self, demo_id: str, stage: str, cache_key: str, round_number: int | None = None
    ) -> dict[int, dict]:
        query = """SELECT r.round_number, r.payload FROM coach_stage_rounds r
                   JOIN coach_stage_manifests m ON m.demo_id=r.demo_id AND m.stage=r.stage
                   AND m.cache_key=r.cache_key
                   WHERE r.demo_id=? AND r.stage=? AND r.cache_key=?"""
        args = [demo_id, stage, cache_key]
        if round_number is not None:
            query += " AND r.round_number=?"
            args.append(round_number)
        query += " ORDER BY r.round_number"
        with self._connect() as conn:
            rows = conn.execute(query, args).fetchall()
        return {row["round_number"]: json.loads(row["payload"]) for row in rows}

    def save_stages(self, demo_id: str, stages: dict[str, tuple[str, dict, dict[int, dict]]]):
        """Atomically publish complete generations. Readers match dependency keys."""
        prepared = []
        for stage, (key, manifest, rounds) in stages.items():
            if not stage or not key or sorted(rounds) != sorted(manifest.get("round_numbers", [])):
                raise ValueError("Incomplete stage generation")
            if manifest.get("demo_id") != demo_id or manifest.get("cache_key") != key:
                raise ValueError("Stage identity mismatch")
            prepared.append(
                (
                    stage,
                    key,
                    json.dumps(manifest, allow_nan=False),
                    [
                        (demo_id, stage, number, key, json.dumps(payload, allow_nan=False))
                        for number, payload in rounds.items()
                    ],
                )
            )
        with self._connect() as conn:
            for stage, key, manifest_json, values in prepared:
                conn.execute(
                    "INSERT INTO coach_stage_manifests VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(demo_id, stage) DO UPDATE SET "
                    "cache_key=excluded.cache_key, manifest=excluded.manifest",
                    (demo_id, stage, key, manifest_json),
                )
                conn.execute(
                    "DELETE FROM coach_stage_rounds WHERE demo_id=? AND stage=?", (demo_id, stage)
                )
                conn.executemany("INSERT INTO coach_stage_rounds VALUES (?, ?, ?, ?, ?)", values)

    def delete_demo_analysis(self, demo_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM demo_analyses WHERE demo_id = ?", (demo_id,))

    def list_demo_players(self, demo_id: str) -> list[dict[str, str]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT steamid, name FROM demo_players WHERE demo_id = ? ORDER BY name, steamid",
                (demo_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def track_player(self, steamid: str) -> None:
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM demo_players WHERE steamid = ? LIMIT 1", (steamid,)
            ).fetchone()
            if not exists:
                raise ValueError("Player must come from a parsed demo")
            conn.execute(
                "INSERT OR IGNORE INTO tracked_players (steamid, added_at) VALUES (?, ?)",
                (steamid, datetime.now(UTC).isoformat()),
            )

    def untrack_player(self, steamid: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tracked_players WHERE steamid = ?", (steamid,))

    def list_tracked_players(self) -> list[dict[str, str | int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT tracked.steamid,
                    COALESCE((SELECT player.name FROM demo_players AS player
                              JOIN demo_catalog AS demo ON demo.demo_id = player.demo_id
                              WHERE player.steamid = tracked.steamid AND player.name != ''
                              ORDER BY demo.analyzed_at DESC LIMIT 1), tracked.steamid) AS name,
                    (SELECT COUNT(*) FROM demo_players AS player
                     WHERE player.steamid = tracked.steamid) AS match_count
                   FROM tracked_players AS tracked ORDER BY name, tracked.steamid"""
            ).fetchall()
        return [dict(row) for row in rows]

    def save_demo_ratings(
        self,
        demo_id: str,
        summary: pd.DataFrame,
        rating_version: int,
        *,
        per_round: pd.DataFrame | None = None,
        analysis_version: int = 0,
    ) -> None:
        """Atomically replace one demo's rating summary, including an empty result."""
        rows = []
        if not summary.empty:
            required = {"steamid", "Rating", "K", "D", "ADR"}
            if not required.issubset(summary.columns):
                raise ValueError("Rating summary is missing required columns")
            rows = [
                (
                    demo_id,
                    str(row.steamid),
                    rating_version,
                    float(row.Rating),
                    int(row.K),
                    int(row.D),
                    float(row.ADR),
                )
                for row in summary.itertuples(index=False)
            ]
        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM demo_catalog WHERE demo_id = ?", (demo_id,)
            ).fetchone()
            if not exists:
                raise ValueError("Cannot save ratings for an unknown demo")
            conn.execute("DELETE FROM demo_ratings WHERE demo_id = ?", (demo_id,))
            conn.executemany(
                """INSERT INTO demo_ratings
                   (demo_id, steamid, rating_version, rating, kills, deaths, adr)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            conn.execute(
                "UPDATE demo_catalog SET rating_version = ? WHERE demo_id = ?",
                (rating_version, demo_id),
            )
            conn.execute("DELETE FROM demo_metric_results WHERE demo_id = ?", (demo_id,))
            if per_round is not None:
                conn.execute(
                    "INSERT INTO demo_metric_results "
                    "(demo_id, analysis_version, metrics_version, summary, per_round) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        demo_id,
                        analysis_version,
                        rating_version,
                        self._df_to_json(summary),
                        self._df_to_json(per_round),
                    ),
                )

    def get_demo_metrics(
        self,
        demo_id: str,
        analysis_version: int,
        metrics_version: int,
    ) -> tuple[pd.DataFrame, pd.DataFrame] | None:
        """Read the full result without loading events or opening the source demo."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT result.summary, result.per_round FROM demo_metric_results AS result "
                "JOIN demo_analyses AS demo ON demo.demo_id = result.demo_id "
                "WHERE result.demo_id = ? AND result.analysis_version = ? "
                "AND result.metrics_version = ? "
                "AND demo.analysis_version = result.analysis_version",
                (demo_id, analysis_version, metrics_version),
            ).fetchone()
        if row is None:
            return None
        return self._json_to_df(row["summary"]), self._json_to_df(row["per_round"])

    def list_player_matches(
        self,
        steamid: str,
        rating_version: int,
    ) -> list[dict[str, str | int | float | None]]:
        """Read an indexed player history without deserializing demo event JSON."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT demo.demo_id, demo.file_name, demo.stored_file_name,
                          demo.map_name, demo.analyzed_at, demo.rating_version,
                          rating.rating, rating.kills, rating.deaths, rating.adr
                   FROM demo_players AS player
                   JOIN demo_catalog AS demo ON demo.demo_id = player.demo_id
                   LEFT JOIN demo_ratings AS rating
                     ON rating.demo_id = player.demo_id
                    AND rating.steamid = player.steamid
                    AND rating.rating_version = ?
                   WHERE player.steamid = ?
                   ORDER BY demo.analyzed_at DESC, demo.demo_id""",
                (rating_version, steamid),
            ).fetchall()
        return [dict(row) for row in rows]
