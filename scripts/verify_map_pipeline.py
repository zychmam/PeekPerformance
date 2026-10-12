"""Verify and measure M1 with an isolated database; never reset the source DB."""

import argparse
import ctypes
import json
import sqlite3
import sys
import tempfile
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.demos.demo_analyzer import DemoAnalyzer
from src.demos.demo_manager import DemoManager
from src.demos.spatial_service import get_spatial_context
from src.demos.tactical_rounds import load_tactical_match
from src.models.models import DemoAnalysis
from src.storage.database import Database


def peak_working_set_mib():
    if sys.platform != "win32":
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (name, ctypes.c_size_t)
            for name in (
                "PeakWorkingSetSize",
                "WorkingSetSize",
                "QuotaPeakPagedPoolUsage",
                "QuotaPagedPoolUsage",
                "QuotaPeakNonPagedPoolUsage",
                "QuotaNonPagedPoolUsage",
                "PagefileUsage",
                "PeakPagefileUsage",
            )
        ]

    process = ctypes.windll.kernel32.GetCurrentProcess
    process.restype = wintypes.HANDLE
    info = ctypes.windll.psapi.GetProcessMemoryInfo
    info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    if not info(process(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError()
    return round(counters.PeakWorkingSetSize / 1024**2, 2)


def read_baseline(database, file_name):
    # Source database is read-only. Its migrations and production data are untouched.
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """SELECT file_name, content_hash, stored_file_name, map_name,
            header, player_info, kills, damage, rounds, bomb_events, player_blinds,
            round_roster, analysis_version FROM demo_analyses WHERE stored_file_name = ?""",
            (file_name,),
        ).fetchone()
    if row is None:
        raise ValueError("Demo must already have a saved base analysis")
    data = dict(row)
    frames = {
        dest: Database._json_to_df(data[src])
        for dest, src in {
            "player_info": "player_info",
            "kills_df": "kills",
            "damage_df": "damage",
            "rounds_df": "rounds",
            "bomb_events_df": "bomb_events",
            "player_blinds_df": "player_blinds",
            "round_roster_df": "round_roster",
        }.items()
    }
    return DemoAnalysis(
        data["file_name"],
        map_name=data["map_name"],
        header=json.loads(data["header"]),
        content_hash=data["content_hash"],
        stored_file_name=data["stored_file_name"],
        analysis_version=data["analysis_version"],
        **frames,
    )


def verify(demo, source_database=None):
    baseline_entries = None
    if source_database:
        analysis = read_baseline(source_database, demo.name)
        origin = "read_only_saved_base"
        with sqlite3.connect(source_database.resolve().as_uri() + "?mode=ro", uri=True) as conn:
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='demo_spatial_context'"
            ).fetchone():
                row = conn.execute(
                    "SELECT payload FROM demo_spatial_context WHERE demo_id=?",
                    (analysis.content_hash,),
                ).fetchone()
                if row:
                    baseline_entries = [
                        (entry["round"], entry["site"], entry["tick"])
                        for entry in json.loads(row[0])["entries"]
                    ]
    else:
        analysis = DemoAnalyzer(demo).get_full_analysis()
        analysis.content_hash = DemoManager.content_hash(demo)
        analysis.stored_file_name = demo.name
        origin = "fresh_parser"
    calls = Counter()

    class CountingParser:
        def __init__(self, parser):
            self.parser = parser

        def __getattr__(self, name):
            target = getattr(self.parser, name)

            def invoke(*args, **kwargs):
                calls[name] += 1
                return target(*args, **kwargs)

            return invoke

    def analyzer(path):
        result = DemoAnalyzer(path)
        result._parser = CountingParser(result._parser)
        return result

    manager = DemoManager(str(demo.parent))
    measurements = {}
    with tempfile.TemporaryDirectory() as temp:
        db = Database(str(Path(temp) / "verification.db"))
        db.upsert_demo_analysis(analysis)
        started = time.perf_counter()
        with patch("src.demos.observations.DemoAnalyzer", side_effect=analyzer):
            context = get_spatial_context(db, manager, analysis, 1)
        measurements["cold_prepare_all_rounds_and_read_round_1_seconds"] = (
            time.perf_counter() - started
        )
        cold_calls = dict(calls)
        calls.clear()
        with (
            patch(
                "src.demos.observations.DemoAnalyzer", side_effect=AssertionError("Parser called")
            ),
            patch.object(manager, "analysis_path", side_effect=AssertionError("Demo reopened")),
        ):
            started = time.perf_counter()
            warm = get_spatial_context(db, manager, analysis, 1)
            measurements["warm_round_context_seconds"] = time.perf_counter() - started
            started = time.perf_counter()
            tactical = load_tactical_match(db, analysis.content_hash, 1)
            measurements["warm_round_tactical_report_seconds"] = time.perf_counter() - started
            changed = replace(
                context.profile,
                regions=[
                    replace(r, directions=["A", "B"]) if r.id == "ramp_a" else r
                    for r in context.profile.regions
                ],
            )
            started = time.perf_counter()
            reclassified = get_spatial_context(db, manager, analysis, 1, profile=changed)
            measurements["map_semantics_rebuild_all_rounds_seconds"] = time.perf_counter() - started
            renamed = replace(
                changed, regions=[replace(r, name="Display " + r.id) for r in changed.regions]
            )
            started = time.perf_counter()
            displayed = get_spatial_context(db, manager, analysis, 1, profile=renamed)
            measurements["presentation_change_round_read_seconds"] = time.perf_counter() - started
        ids = context.observations.states.event_id.tolist()
        assert (
            ids
            == warm.observations.states.event_id.tolist()
            == reclassified.observations.states.event_id.tolist()
        )
        assert ids == displayed.observations.states.event_id.tolist()
        assert tactical.rounds[0].foundation.contact_references["first_enemy_damage"].tick == 7556
        assert len(tactical.rounds[0].foundation.equipment_start) == 10
        with db._connect() as conn:
            counts = {
                name: conn.execute(
                    "SELECT SUM(json_array_length(payload, ?)) FROM coach_stage_rounds "
                    "WHERE stage='observations'",
                    ("$." + name,),
                ).fetchone()[0]
                for name in (
                    "clock",
                    "states",
                    "utility",
                    "equipment",
                    "economy",
                    "bombs",
                    "shots",
                    "throws",
                    "utility_lifecycles",
                    "smokes",
                )
            }
            sizes = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT stage, SUM(length(CAST(payload AS BLOB))) "
                    "FROM coach_stage_rounds GROUP BY stage"
                )
            }
            entries = conn.execute(
                "SELECT SUM(json_array_length(payload, '$.entries')) "
                "FROM coach_stage_rounds WHERE stage='entries'"
            ).fetchone()[0]
            current_entries = [
                (entry["round"], entry["site"], entry["tick"])
                for (payload,) in conn.execute(
                    "SELECT payload FROM coach_stage_rounds "
                    "WHERE stage='entries' ORDER BY round_number"
                )
                for entry in json.loads(payload)["entries"]
            ]
            if baseline_entries is not None:
                assert current_entries == baseline_entries, "Observed entry regression"
    return {
        "demo_name": demo.name,
        "demo_id": analysis.content_hash,
        "base_analysis_origin": origin,
        "counts": counts,
        "entries": entries,
        "historical_entry_round_site_tick_match": (
            current_entries == baseline_entries if baseline_entries is not None else None
        ),
        "measurements": measurements,
        "cold_parser_calls": cold_calls,
        "warm_and_profile_change_parser_calls": dict(calls),
        "stage_payload_bytes": sizes,
        "peak_process_working_set_mib": peak_working_set_mib(),
        "notes": [
            "One local run, not an SLA.",
            "Peak includes all preceding stages and native parser.",
            "All writes use a temporary database; source database opened read-only.",
            "Independent in-game replay review remains open.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("demo", type=Path)
    parser.add_argument("--source-database", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.demo, args.source_database)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
