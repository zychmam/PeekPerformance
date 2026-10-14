"""Prepare M5 compact facts and verify fast cached aggregation on both saved demos."""

import json
import sys
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_m3_contacts import EXPECTED
from src.demos.map_tendencies import aggregate_tendencies
from src.demos.map_tendencies_service import get_map_round_facts
from src.demos.tactical_actions import actions_key
from src.maps.registry import get_profile
from src.storage.database import Database


def main():
    db = Database(str(Path.home() / ".peek_performance" / "peekperformance.db"))
    with patch(
        "src.demos.demo_analyzer.DemoParser", side_effect=AssertionError("Unexpected reparse")
    ):
        for demo_id in EXPECTED:
            analysis = db.get_demo_analysis(demo_id, include_auxiliary=False)
            start = perf_counter()
            facts = get_map_round_facts(db, None, analysis)
            prepare = perf_counter() - start
            actions = db.get_stage_rounds(
                demo_id, "tactical_actions", actions_key(analysis, get_profile(analysis.map_name))
            )
            for fact in facts:
                original = actions[fact["number"]]["result"]
                assert {a["id"] for a in fact["attacks"]} == {
                    a["episode"]["id"] for a in original["attacks"]
                }
                assert len(fact["ct_activity"]) == len(original["ct_activity"])
                assert len(fact["rotations"]) == len(original["rotations"])
                assert fact["retake"]["outcome"] == original["retake"]["outcome"]
            start = perf_counter()
            with (
                patch(
                    "src.demos.tactical_rounds.build_tactical_match",
                    side_effect=AssertionError("Rebuilt tactics"),
                ),
                patch(
                    "src.demos.spatial_service.get_spatial_context",
                    side_effect=AssertionError("Read trajectories"),
                ),
            ):
                cached = get_map_round_facts(db, None, analysis)
            assert cached == facts
            read = perf_counter() - start
            size = len(json.dumps(facts, allow_nan=False).encode())
            teams = sorted(
                {data["team_id"] for f in facts for data in f["sides"].values() if data["team_id"]}
            )
            start = perf_counter()
            for team in teams:
                for side in ("T", "CT"):
                    report = aggregate_tendencies(facts, team_id=team, side=side)
                    for rows in report["tables"].values():
                        if rows:
                            assert sum(row["count"] for row in rows) == rows[0]["denominator"]
                            assert all(set(row["rounds"]) <= set(report["rounds"]) for row in rows)
                    assert len(report["tables"]["positions"]) > 0
                    tactical = report["actions"]
                    assert sum(s["count"] for s in tactical["sites"]) == len(tactical["attempts"])
                    for site in tactical["sites"]:
                        assert (
                            site["wins"]["count"]
                            <= site["wins"]["denominator"]
                            <= len(site["rounds"])
                        )
                        assert (
                            site["entry"]["count"] <= site["entry"]["denominator"] <= site["count"]
                        )
                    assert len(tactical["rotations"]) == tactical["rotation_summary"]["eligible"]
                    print(
                        f"  {team} {side}: rounds={len(report['rounds'])} "
                        f"snapshot={report['coverage']['snapshots']['known']} "
                        f"opening={report['coverage']['opening']['known']} "
                        f"utility={report['coverage']['utility']['known']}",
                        flush=True,
                    )
            elapsed = perf_counter() - start
            print(
                f"{analysis.map_name}: {len(facts)} rounds; "
                f"prepare={prepare:.2f}s read={read:.3f}s "
                f"4 aggregates={elapsed:.3f}s facts={size / 1024:.0f}KiB",
                flush=True,
            )
            if "--ui" in sys.argv:
                verify_ui(analysis, facts)


def verify_ui(analysis, facts):
    from streamlit.testing.v1 import AppTest

    from src.demos.map_tendencies_service import round_facts_key

    # All four team/side combinations against the real cached facts, no browser.
    app = AppTest.from_string("""
import streamlit as st
from src.gui.map_tendencies_view import render_map_tendencies
render_map_tendencies(st.session_state['analysis'], None, {}, None)
""")
    app.session_state["analysis"] = analysis
    app.session_state["map_facts_" + round_facts_key(analysis)] = facts
    app.run(timeout=30)
    assert not app.exception
    for team_index in range(2):
        next(s for s in app.selectbox if s.label == "Drużyna").select_index(team_index).run(
            timeout=30
        )
        for side in ("T", "CT"):
            next(r for r in app.radio if r.label == "Strona drużyny").set_value(side).run(
                timeout=30
            )
            assert not app.exception
            assert any("Najczęstsze zaobserwowane" in m.value for m in app.markdown)
    print(f"  {analysis.map_name}: real-data UI T/CT, both teams passed", flush=True)


if __name__ == "__main__":
    main()
