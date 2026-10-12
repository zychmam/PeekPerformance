"""Time/side/availability checks and an optional real Mirage integration test."""

import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.demos.demo_analyzer import DemoAnalyzer
from src.demos.demo_manager import DemoManager
from tests.map_support import (
    MirageContext,
    annotate_states,
    context_key,
    player_setup_profile,
    round_clock,
    snapshot,
)
from tests.map_support import get_mirage_context
from src.demos.versions import ANALYSIS_VERSION
from src.models.models import DemoAnalysis
from src.storage.database import Database


def fixture():
    analysis = DemoAnalysis(
        file_name="mirage.dem", content_hash="hash", map_name="de_mirage",
        analysis_version=ANALYSIS_VERSION,
        rounds_df=pd.DataFrame([
            {"total_rounds_played": 1, "start_tick": 0, "tick": 2000, "winner": "CT"},
            {"total_rounds_played": 2, "start_tick": 2100, "tick": 4500, "winner": "T"},
        ]), player_info=pd.DataFrame([{"steamid": "76561198008873401", "name": "Alice"}]),
    )
    clock = round_clock(analysis.rounds_df, pd.DataFrame({"tick": [128, 2200]}))
    samples = pd.DataFrame([
        {"tick": tick, "steamid": "76561198008873401", "name": "Alice",
         "team_num": team, "last_place_name": place, "is_alive": alive,
         "X": 0, "Y": 0, "Z": 0, "health": 100 if alive else 0,
         "inventory": ["C4 Explosive"] if team == 2 else []}
        for tick, team, place, alive in [
            (128 + 12*64, 3, "BombsiteB", True),
            (128 + 13*64, 3, "BombsiteB", False),
            (2200 + 12*64, 2, "Connector", True),
        ]
    ])
    return analysis, MirageContext(clock, annotate_states(samples, clock), pd.DataFrame(), {})


def test_snapshots_keep_connectors_separate_and_do_not_carry_dead_or_stale_players():
    _, context = fixture()
    assert snapshot(context, 1, 12).zone.item() == "B"
    assert snapshot(context, 1, 13).empty
    assert snapshot(context, 1, 20).empty
    assert snapshot(context, 2, 12).zone.item() == "connector"
    assert snapshot(context, 2, 12).has_bomb.item()
    profile = player_setup_profile(context, "76561198008873401")
    assert profile["Rundy z obserwacją"].sum() == 2
    assert set(profile.Strona) == {"T", "CT"}


def test_missing_freeze_is_not_fabricated():
    analysis, _ = fixture()
    assert round_clock(analysis.rounds_df, pd.DataFrame()).freeze_tick.isna().all()


def test_sqlite_cache_avoids_parser_and_invalidates_with_inputs(tmp_path):
    analysis, context = fixture()
    analysis.kills_df = pd.DataFrame([{
        "tick": 1000.0, "attacker_steamid": 76561198008873401,
        "user_steamid": None,
    }])
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(analysis)
    manager = DemoManager(str(tmp_path / "demos"))
    with (patch.object(manager, "analysis_path", return_value=Path("mirage.dem")),
          patch("src.demos.spatial_service.extract_observations", return_value=__import__("tests.map_support", fromlist=["source_fixture"]).source_fixture(analysis, context)) as parse):
        get_mirage_context(db, manager, analysis)
        assert parse.call_count == 1
    with patch.object(manager, "analysis_path", side_effect=AssertionError("source reopened")):
        reopened = Database(str(tmp_path / "cache.db"))
        saved_analysis = reopened.get_demo_analysis(analysis.content_hash)
        assert context_key(saved_analysis) == context_key(analysis)
        restored = get_mirage_context(reopened, manager, saved_analysis)
    assert restored.states.steamid.tolist() == context.states.steamid.tolist()
    assert restored.states.has_bomb.tolist() == context.states.has_bomb.tolist()
    db.upsert_demo_analysis(analysis)
    assert db.get_stage_manifest(analysis.content_hash, "spatial") is None


def test_mirage_ui_shows_context_without_identifiers():
    analysis, context = fixture()
    app = AppTest.from_string('''
import streamlit as st
from src.gui.round_context_view import render_round_context
render_round_context(st.session_state['analysis'], '76561198008873401', None)
''')
    app.session_state["analysis"] = analysis
    app.session_state[f"spatial_{context_key(analysis)}_{context.profile.presentation_fingerprint}_1"] = context
    app.run()
    assert not app.exception
    assert len(app.slider) == 1
    assert len(app.get("iframe")) == 1
    for table in app.dataframe:
        assert not any("steamid" in column.lower() for column in table.value.columns)


@pytest.mark.skipif(not os.environ.get("PEEK_MIRAGE_DEMO"), reason="Set PEEK_MIRAGE_DEMO")
def test_real_mirage_spatial_pipeline(tmp_path):
    source = Path(os.environ["PEEK_MIRAGE_DEMO"])
    manager = DemoManager(str(tmp_path / "demos"))
    path = manager.save_uploaded(source.name, source.read_bytes())
    analysis = DemoAnalyzer(path).get_full_analysis()
    analysis.content_hash = manager.content_hash(path)
    analysis.stored_file_name = path.name
    assert analysis.map_name == "de_mirage"
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(analysis)
    context = get_mirage_context(db, manager, analysis)
    assert context.entries
    if source.name.startswith("1-2826a5a8"):
        first = context.entries[0]
        # 6-tick sampling resolves the crossing four ticks earlier than the
        # historical 16/64-tick snapshots (7468); previous sample is 7458.
        assert (first["round"], first["site"], first["tick"]) == (1, "A", 7464)
        assert first["routes"] == {"Rampa A": 2}
        assert first["ct_before"]["site_count"] == first["ct_during"]["site_count"] == 2
        assert first["ct_during"]["complete"]
    assert context.clock.freeze_tick.notna().all()
    assert not context.states.empty and not context.utility.empty
    assert not context.smokes.empty and not context.shots.empty
    assert context.smokes.end_tick.ge(context.smokes.tick).all()
    assert not context.shots.weapon.str.contains("knife|bayonet").any()
    assert context.states.seconds.ge(0).all()
    assert context.states.steamid.str.len().eq(17).all()
    assert context.states.has_bomb.eq(True).any(), "C4 inventory mapping failed"
    assert context.states.zone.ne("unknown").mean() > 0.95
    with patch.object(manager, "analysis_path", side_effect=AssertionError("source reopened")):
        cached = get_mirage_context(db, manager, analysis)
    pd.testing.assert_frame_equal(context.states, cached.states, check_dtype=False)
    pd.testing.assert_frame_equal(context.smokes, cached.smokes, check_dtype=False)
    pd.testing.assert_frame_equal(context.shots, cached.shots, check_dtype=False)
    assert context.entries == cached.entries
    from src.demos.coach_foundations import decode_foundation, foundation_key
    from src.demos.tactical_rounds import load_tactical_match

    saved = db.get_stage_rounds(analysis.content_hash, "foundations", foundation_key(analysis))
    assert len(saved) == len(analysis.rounds_df)
    single = db.get_stage_rounds(analysis.content_hash, "foundations", foundation_key(analysis), 1)
    assert list(single) == [1]
    with patch("src.demos.demo_analyzer.DemoParser", side_effect=AssertionError("source reopened")):
        tactical = load_tactical_match(db, analysis.content_hash)
    for rnd in tactical.rounds:
        foundation, proof = decode_foundation(saved[rnd.number])
        assert rnd.foundation == foundation
        assert all(tactical.evidence[eid] == event for eid, event in proof.items())
        assert len(foundation.equipment_start) == 10
        ref = foundation.contact_references["preparation_reference"]
        for snapshot in foundation.setup_before_contact.values():
            assert all(player["sample_tick"] < ref.tick for player in snapshot.players)
    import json

    expectations = json.loads((Path(__file__).parent / "reference" /
                              "mirage_foundation_expectations.json").read_text())
    if analysis.content_hash == expectations["demo_hash"]:
        expected = expectations["round_1"]
        foundation = tactical.rounds[0].foundation
        assert len(tactical.rounds) == expectations["rounds"]
        assert sum(len(r.foundation.equipment_start) for r in tactical.rounds) == 210
        for key in ("first_enemy_damage", "first_firearm_damage", "first_enemy_kill"):
            assert foundation.contact_references[key].tick == expected[f"{key}_tick"]
        assert all(s.tick == expected["setup_before_contact_tick"]
                   for s in foundation.setup_before_contact.values())
        assert sum(bool(e.defuse_kit) for e in foundation.equipment_start) == expected["defuse_kits"]
        assert sum(bool(e.helmet) for e in foundation.equipment_start) == expected["helmets"]
        assert sorted(e.economy["current_equip_value"] for e in foundation.equipment_start) == (
            expected["equipment_values"])
        assert sorted(tactical.evidence[eid].tick for eid in foundation.thrown_utility_ids) == (
            expected["utility_throw_ticks"])
        smoke = next(tactical.evidence[eid] for eid in foundation.utility_lifecycle_ids
                     if tactical.evidence[eid].data.get("entityid") == expected["smoke"]["entityid"])
        assert smoke.tick == expected["smoke"]["effect_tick"]
        assert smoke.data["throw_tick"] == expected["smoke"]["throw_tick"]
        assert smoke.data["end_tick"] == expected["smoke"]["observed_end_tick"]
        assert smoke.data["display_end_tick"] == expected["smoke"]["display_end_tick"]
        assert {tactical.evidence[eid].source for eid in smoke.data["evidence_ids"]} == {
            "utility", "throws"}
    # Exercise the full view and tick-accurate jump using actual saved data.
    app = AppTest.from_string('''
import streamlit as st
from src.gui.round_context_view import render_round_context
render_round_context(st.session_state['analysis'], st.session_state['player'], None)
''')
    app.session_state["analysis"] = analysis
    app.session_state["player"] = str(analysis.player_info.iloc[0].steamid)
    app.session_state[f"spatial_{context_key(analysis)}_{context.profile.presentation_fingerprint}_1"] = cached
    app.run(timeout=30)
    assert not app.exception
    first_entry = cached.entries[0]
    for widget in app.selectbox:
        if widget.label == "Runda taktyczna":
            widget.set_value(first_entry["round"]).run(timeout=30)
            break
    next(b for b in app.button if b.label == "Przejdź do wejścia na mapie").click().run(timeout=30)
    assert not app.exception
    assert app.slider[0].value == pytest.approx(first_entry["seconds"])
    for table in app.dataframe:
        assert not any("steamid" in str(c).lower() for c in table.value.columns)
    print(f"Mirage: rounds={len(context.clock)}, samples={len(context.states)}, "
          f"utility={len(context.utility)}, diagnostics={context.diagnostics}")
