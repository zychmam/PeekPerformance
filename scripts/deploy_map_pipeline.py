"""Explicit M1 deployment: prepare demo before opening/resetting the configured DB."""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import Config
from src.demos.demo_analyzer import DemoAnalyzer
from src.demos.demo_manager import DemoManager
from src.demos.rating_service import calculate_and_store_rating
from src.demos.spatial_service import get_spatial_context
from src.demos.tactical_rounds import load_tactical_match
from src.storage.database import Database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = Config.load()
    manager = DemoManager(config.demos_dir)
    demo = args.demo.resolve(strict=True)
    if demo.parent != manager.demos_dir.resolve():
        raise ValueError("Deploy an existing source demo from the configured demo directory")
    config_path = Path.home() / ".peek_performance" / "config.json"
    original_config = config_path.read_bytes() if config_path.exists() else None
    source_files = {item.name: item.stat().st_size for item in manager.list_demos()}
    with sqlite3.connect(Path(config.db_path).resolve().as_uri() + "?mode=ro", uri=True) as conn:
        tracked = conn.execute(
            "SELECT steamid, added_at FROM tracked_players ORDER BY steamid"
        ).fetchall()
        before_schema = conn.execute("PRAGMA user_version").fetchone()[0]
        previous_analyses = conn.execute("SELECT COUNT(*) FROM demo_analyses").fetchone()[0]

    # A parser failure leaves the old production database untouched.
    analysis = DemoAnalyzer(demo).get_full_analysis()
    analysis.content_hash = manager.content_hash(demo)
    analysis.stored_file_name = demo.name
    if analysis.map_name != "de_mirage" or analysis.rounds_df.empty:
        raise ValueError("M1 deployment requires a successfully parsed Mirage demo")
    db = Database(config.db_path)
    db.upsert_demo_analysis(analysis)
    summary, _ = calculate_and_store_rating(
        db, manager, analysis.content_hash, demo.name, analysis=analysis
    )
    context = get_spatial_context(db, manager, analysis, 1)
    with (
        patch.object(manager, "analysis_path", side_effect=AssertionError("Demo reopened")),
        patch("src.demos.demo_analyzer.DemoParser", side_effect=AssertionError("Parser called")),
    ):
        assert get_spatial_context(db, manager, analysis, 1) is not None
        tactical = load_tactical_match(db, analysis.content_hash, 1)
    with db._connect() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
        assert tracked == [
            tuple(row)
            for row in conn.execute(
                "SELECT steamid, added_at FROM tracked_players ORDER BY steamid"
            )
        ]
        stages = dict(
            conn.execute("SELECT stage, COUNT(*) FROM coach_stage_rounds GROUP BY stage").fetchall()
        )
        current_schema = conn.execute("PRAGMA user_version").fetchone()[0]
        analyses = conn.execute("SELECT COUNT(*) FROM demo_analyses").fetchone()[0]
    assert source_files == {item.name: item.stat().st_size for item in manager.list_demos()}
    assert original_config == (config_path.read_bytes() if config_path.exists() else None)
    assert len(context.foundations) == len(tactical.rounds) == 1
    assert set(stages.values()) == {len(analysis.rounds_df)}
    report = {
        "schema_before": before_schema,
        "schema_after": current_schema,
        "previous_analyses": previous_analyses,
        "current_analyses": analyses,
        "demo_id": analysis.content_hash,
        "map": analysis.map_name,
        "rounds": len(analysis.rounds_df),
        "rated_players": len(summary),
        "tracked_players_preserved": len(tracked),
        "source_demos_preserved": len(source_files),
        "config_unchanged": True,
        "stage_round_counts": stages,
        "warm_round_without_parser": True,
        "sqlite_integrity": "ok",
    }
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
