"""Real map demo -> saved M3/M4/M5 and radar, with independent parser references."""

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from demoparser2 import DemoParser

from scripts.verify_m5_baseline import verify_ui
from src.config import Config
from src.demos.demo_analyzer import DemoAnalyzer
from src.demos.demo_manager import DemoManager
from src.demos.map_tendencies import aggregate_tendencies
from src.demos.map_tendencies_service import get_map_round_facts
from src.demos.spatial_service import get_spatial_context
from src.demos.versions import ANALYSIS_VERSION
from src.gui.radar_player import playback_data, playback_html
from src.maps.registry import get_profile
from src.maps.resolver import classify, region_site
from src.storage.database import Database


def verify(demo, db, manager, *, ui=False, expected_map=None):
    start = perf_counter()
    digest = manager.content_hash(demo)
    analysis = db.get_demo_analysis(digest)
    if analysis is None or analysis.analysis_version != ANALYSIS_VERSION:
        print("Parsing demo...", flush=True)
        analysis = DemoAnalyzer(demo).get_full_analysis()
        analysis.content_hash = digest
        analysis.stored_file_name = demo.name
        if expected_map:
            assert analysis.map_name == expected_map
        db.upsert_demo_analysis(analysis)
    if expected_map:
        assert analysis.map_name == expected_map
    print(
        f"Parsed {len(analysis.rounds_df)} rounds, {len(analysis.player_info)} players", flush=True
    )
    profile = get_profile(analysis.map_name)
    assert profile and profile.supports("radar", "site_boundaries", "entry_routes")
    # Raw plant positions and names are independent of derived regions/attacks.
    plants = DemoParser(str(demo)).parse_event(
        "bomb_planted", player=["X", "Y", "Z", "last_place_name"]
    )
    live_plants = []
    for plant in plants.to_dict("records"):
        window = analysis.rounds_df[
            (analysis.rounds_df.start_tick <= plant["tick"])
            & (analysis.rounds_df.tick >= plant["tick"])
        ]
        if window.empty:
            continue
        sample = {axis: plant["user_" + axis] for axis in ("X", "Y", "Z", "last_place_name")}
        expected_site = {"BombsiteA": "A", "BombsiteB": "B"}[sample["last_place_name"]]
        assert region_site(classify(sample, profile).region_id, profile) == expected_site
        px, py = profile.radar_levels[0].project(sample["X"], sample["Y"])
        assert 0 <= px < 1024 and 0 <= py < 1024
        live_plants.append(
            {
                "round": int(window.iloc[0].total_rounds_played),
                "tick": int(plant["tick"]),
                "site": expected_site,
                "engine_site": int(plant["site"]),
                "sample": sample,
            }
        )
    assert {p["site"] for p in live_plants} == {"A", "B"}
    print("Preparing all M3/M4/M5 rounds...", flush=True)
    facts = get_map_round_facts(db, manager, analysis)
    assert len(facts) == len(analysis.rounds_df)
    excluded_plants = sorted(set(plants.tick.astype(int)) - {p["tick"] for p in live_plants})
    assert not set(excluded_plants) & {p["tick"] for f in facts for p in f["plants"]}
    for reference in live_plants:
        fact = next(f for f in facts if f["number"] == reference["round"])
        assert any(
            p["tick"] == reference["tick"] and p["site"] == reference["site"]
            for p in fact["plants"]
        )
        assert any(
            a["target_site"] == reference["site"]
            and a["plant_id"] in {p["id"] for p in fact["plants"] if p["tick"] == reference["tick"]}
            for a in fact["attacks"]
        )
    with (
        patch(
            "src.demos.spatial_service.get_spatial_context",
            side_effect=AssertionError("cache reopened sources"),
        ),
        patch(
            "src.demos.tactical_rounds.build_tactical_match",
            side_effect=AssertionError("cache reran detectors"),
        ),
    ):
        read_start = perf_counter()
        assert get_map_round_facts(db, None, analysis) == facts
        read_seconds = perf_counter() - read_start
    teams = sorted({s["team_id"] for f in facts for s in f["sides"].values() if s["team_id"]})
    aggregates = []
    for team in teams:
        for side in ("T", "CT"):
            report = aggregate_tendencies(facts, team_id=team, side=side)
            assert report["rounds"]
            for site in report["actions"]["sites"]:
                assert site["wins"]["count"] <= site["wins"]["denominator"] <= len(site["rounds"])
            aggregates.append(
                {
                    "team": team,
                    "side": side,
                    "rounds": len(report["rounds"]),
                    "attempts": len(report["actions"]["attempts"]),
                    "rotations": len(report["actions"]["rotations"]),
                    "snapshot_known": report["coverage"]["snapshots"]["known"],
                }
            )
    labels = dict(
        zip(analysis.player_info.steamid.astype(str), analysis.player_info.name, strict=True)
    )
    locations, unknown_places = Counter(), Counter()
    for number in (f["number"] for f in facts):
        context = get_spatial_context(db, None, analysis, number)
        locations.update(context.states.location_status)
        unknown_places.update(
            context.states.loc[
                context.states.location_status.ne("observed"), "last_place_name"
            ].fillna("<empty>")
        )
        radar = playback_data(context, analysis, number, labels, next(iter(labels)))
        assert radar["radar_image"] and len(radar["players"]) == 10
        assert "data:image/png;base64" in playback_html(radar)
    if ui:
        verify_ui(analysis, facts)
        verify_round_ui(analysis, facts, db)
    result = {
        "demo": demo.name,
        "demo_id": digest,
        "map": analysis.map_name,
        "patch": analysis.header.get("patch_version"),
        "rounds": len(facts),
        "players": len(analysis.player_info),
        "kills": len(analysis.kills_df),
        "independent_plants": live_plants,
        "excluded_postround_plant_ticks": excluded_plants,
        "aggregates": aggregates,
        "locations": dict(locations),
        "unknown_places": dict(unknown_places),
        "warm_read_seconds": round(read_seconds, 3),
        "total_seconds": round(perf_counter() - start, 2),
    }
    return result


def verify_round_ui(analysis, facts, db):
    from streamlit.testing.v1 import AppTest

    from src.demos.map_tendencies_service import round_facts_key

    app = AppTest.from_string("""
import pandas as pd
import streamlit as st
from src.demos.spatial_service import get_spatial_context
from src.gui.match_dashboard import render_match_dashboard
load = lambda a, rnd=None: get_spatial_context(st.session_state['db'], None, a, rnd)
render_match_dashboard(st.session_state['analysis'], pd.DataFrame(), lambda p: None,
                       lambda a: None, load, None)
""")
    app.session_state["analysis"] = analysis
    app.session_state["db"] = db
    app.session_state["match_section"] = "Tendencje mapy"
    app.session_state["map_facts_" + round_facts_key(analysis)] = facts
    app.run(timeout=30)
    assert not app.exception
    next(b for b in app.button if b.label == "Przejdź do analizy tej rundy").click().run(timeout=30)
    assert not app.exception
    assert app.session_state["match_section"] == "Analiza rundy"
    assert any("Podsumowanie rundy" in m.value for m in app.markdown)
    assert not any("nie ma jeszcze profilu" in i.value for i in app.info)
    next(r for r in app.radio if r.label == "Perspektywa").set_value("Wybrany gracz").run(
        timeout=30
    )
    assert not app.exception
    print(f"  {analysis.map_name} M5 -> round summary/radar, team/player passed", flush=True)


def main(expected_map=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("demo", type=Path, help="Decompressed .dem path")
    parser.add_argument("--map", default=expected_map, help="Expected map identity")
    parser.add_argument("--app", action="store_true", help="Import into configured app storage")
    parser.add_argument("--ui", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.app:
        config = Config.load()
        manager = DemoManager(config.demos_dir)
        destination = manager.demos_dir / args.demo.name
        if destination.exists() and manager.content_hash(destination) != manager.content_hash(
            args.demo
        ):
            raise ValueError("Different demo already stored at destination")
        if not destination.exists():
            shutil.copyfile(args.demo, destination)
        result = verify(
            destination, Database(config.db_path), manager, ui=args.ui, expected_map=args.map
        )
    else:
        with tempfile.TemporaryDirectory() as temporary:
            result = verify(
                args.demo,
                Database(str(Path(temporary) / "dust2.db")),
                DemoManager(str(args.demo.resolve().parent)),
                ui=args.ui,
                expected_map=args.map,
            )
    if args.output:
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
