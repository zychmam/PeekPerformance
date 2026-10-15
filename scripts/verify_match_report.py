"""Validate real exported reports on saved maps without reopening any demo parser."""

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jsonschema

from src.config import Config
from src.demos.demo_analyzer import enemy_mask, normalize_round_events
from src.demos.demo_manager import DemoManager
from src.demos.match_report import encode_match_report, prepare_match_report, table_records
from src.demos.rating_calculator import RATING_VERSION
from src.demos.rating_service import calculate_and_store_rating
from src.storage.database import Database


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("exports"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = Config.load()
    db, manager = Database(config.db_path), DemoManager(config.demos_dir)
    schema = json.loads(
        Path("docs/schemas/match_report_v1.schema.json").read_text(encoding="utf-8")
    )
    with patch("src.demos.demo_analyzer.DemoParser", side_effect=AssertionError("Reopened parser")):
        for item in db.list_demo_analyses():
            if item["map_name"] not in {"de_mirage", "de_inferno", "de_dust2", "de_anubis"}:
                continue
            start = perf_counter()
            analysis = db.get_demo_analysis(item["demo_id"])
            report = prepare_match_report(db, manager, analysis)
            payload = encode_match_report(report)
            decoded = json.loads(payload)
            assert decoded == report
            jsonschema.Draft202012Validator(schema).validate(decoded)
            kills = normalize_round_events(analysis.kills_df, analysis.rounds_df)
            reconciliation = report["limitations"]["statistics_reconciliation"]
            assert reconciliation["source_enemy_kills"] == int(enemy_mask(kills).sum())
            assert (
                sum(
                    p["match_statistics"]["kills"]
                    for p in report["players"]
                    if p["match_statistics"]
                )
                == reconciliation["reported_enemy_kills"]
            )
            assert reconciliation["difference"] == 0
            assert reconciliation["unknown_clock_rounds"] == []
            events = {e["id"]: e for e in table_records(report["source_events"])}
            for rnd in report["rounds"]:
                plant_source = rnd["coverage"]["sources"].get("bomb_planted", {})
                if plant_source.get("status") == "absent":
                    assert not rnd["result"]["plants"]
                    assert rnd["result"]["retake"]["status"] == "not_applicable"
                    assert all(a["plant_outcome"] == "not_observed"
                               for a in table_records(rnd["attacks"]["attempts"]))
                round_stats = {p["player_id"]: p["round_statistics"]
                               for p in table_records(rnd["players"])}
                for link in rnd["combat"]["refrags"]:
                    victim = events[link["death_id"]]["details"]["user_player_id"]
                    assert round_stats[victim]["kast"] == 1, (analysis.map_name, rnd["number"])
            summary, _ = calculate_and_store_rating(
                db, manager, item["demo_id"], item["stored_file_name"], analysis=analysis,
            )
            assert int(summary.K.sum()) == reconciliation["reported_enemy_kills"]
            assert all(r["rating_version"] == RATING_VERSION for r in
                       db.list_player_matches(str(summary.iloc[0].steamid), RATING_VERSION)
                       if r["demo_id"] == item["demo_id"])
            for player in report["players"]:
                if player["match_statistics"] is None:
                    continue
                rounds = [
                    p["round_statistics"]
                    for r in report["rounds"]
                    for p in table_records(r["players"])
                    if p["player_id"] == player["player_id"] and p["round_statistics"]
                ]
                assert sum(r["kills"] for r in rounds) == player["match_statistics"]["kills"]
                assert (
                    abs(
                        sum(r["damage"] for r in rounds) / len(rounds)
                        - player["match_statistics"]["adr"]
                    )
                    <= 0.0051
                )
            path = args.output_dir / f"{analysis.map_name}_match_report_v1.0.json"
            path.write_bytes(payload)
            print(
                f"{analysis.map_name}: {len(report['rounds'])} rounds, "
                f"{len(report['players'])} players, {len(payload) / 1024:.0f} KiB, "
                f"{perf_counter() - start:.2f}s; schema/counts/refs/privacy passed",
                flush=True,
            )


if __name__ == "__main__":
    main()
