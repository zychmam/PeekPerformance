"""Integration gates for selective cache, source identity and map independence."""

import sqlite3
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from src.demos.coach_foundations import foundation_key
from src.demos.observations import observations_key
from src.demos.spatial_service import get_spatial_context, read_context, spatial_key
from src.demos.tactical_rounds import build_tactical_match, load_tactical_match
from src.gui.radar_player import playback_data
from src.maps.context import enrich_spatial
from src.maps.registry import get_profile
from src.models.observations import DetectorConfig
from src.models.spatial import MapProfile, RadarLevel, Region
from src.storage.database import Database
from tests.map_support import source_fixture
from tests.test_coach_foundations import match_inputs as match_inputs


@pytest.fixture
def prepared(tmp_path, match_inputs):
    analysis, fixture = match_inputs
    db = Database(str(tmp_path / "stages.db"))
    db.upsert_demo_analysis(analysis)
    manager = Mock()
    manager.analysis_path.return_value = Path("fixture.dem")
    observations = source_fixture(analysis, fixture)
    with patch("src.demos.spatial_service.extract_observations", return_value=observations):
        context = get_spatial_context(db, manager, analysis, 1)
    return db, manager, analysis, context


def test_semantic_change_reuses_sources_and_foundations_without_demo(prepared):
    db, manager, analysis, context = prepared
    before = load_tactical_match(db, analysis.content_hash, 1)
    raw_manifest = db.get_stage_manifest(analysis.content_hash, "observations")
    foundation = db.get_stage_manifest(analysis.content_hash, "foundations")
    profile = context.profile
    changed = replace(
        profile,
        regions=[replace(r, directions=["B"]) if r.id == "ramp_a" else r for r in profile.regions],
    )
    with (
        patch.object(manager, "analysis_path", side_effect=AssertionError("demo opened")),
        patch(
            "src.demos.spatial_service.extract_observations", side_effect=AssertionError("parser")
        ),
    ):
        after = get_spatial_context(db, manager, analysis, 1, profile=changed)
    assert after.profile.semantic_fingerprint != profile.semantic_fingerprint
    assert (
        after.observations.states.event_id.tolist() == context.observations.states.event_id.tolist()
    )
    assert db.get_stage_manifest(analysis.content_hash, "observations") == raw_manifest
    assert db.get_stage_manifest(analysis.content_hash, "foundations") == foundation
    assert all(
        p["area"] is None for p in before.rounds[0].foundation.setup_before_contact["T"].players
    )
    assert all("region_id" not in e.data for e in before.evidence.values())


def test_presentation_change_does_not_recompute_locations_or_entries(prepared):
    db, manager, analysis, context = prepared
    changed = replace(
        context.profile,
        profile_version="renamed",
        regions=[
            replace(r, name="Renamed " + r.id, route_names={k: "Route " + k for k in r.route_names})
            for r in context.profile.regions
        ],
    )
    with (
        patch("src.demos.spatial_service.enrich_spatial", side_effect=AssertionError("resolver")),
        patch("src.demos.site_entries.enrich_entries", side_effect=AssertionError("detector")),
        patch.object(manager, "analysis_path", side_effect=AssertionError("demo")),
    ):
        after = get_spatial_context(db, manager, analysis, 1, profile=changed)
    assert after.states.place.str.startswith("Renamed").all()
    assert after.states.region_id.tolist() == context.states.region_id.tolist()


def test_detector_config_change_does_not_reclassify_positions(prepared):
    db, manager, analysis, context = prepared
    spatial_manifest = db.get_stage_manifest(analysis.content_hash, "spatial")
    config = replace(DetectorConfig(), entry_group_seconds=4)
    with (
        patch("src.demos.spatial_service.enrich_spatial", side_effect=AssertionError("resolver")),
        patch.object(manager, "analysis_path", side_effect=AssertionError("demo")),
    ):
        changed = get_spatial_context(db, manager, analysis, 1, config=config)
    assert changed is not None
    assert db.get_stage_manifest(analysis.content_hash, "spatial") == spatial_manifest
    assert spatial_key(analysis) == spatial_manifest["cache_key"]


def test_single_round_read_filters_every_payload_query(prepared):
    db, _, analysis, _ = prepared
    with patch.object(db, "get_stage_rounds", wraps=db.get_stage_rounds) as queries:
        context = read_context(db, analysis, 1)
    assert context.clock.total_rounds_played.tolist() == [1]
    assert queries.call_count >= 3
    assert all(call.args[-1] == 1 for call in queries.call_args_list)
    assert context.observations.cache_key == observations_key(analysis)
    assert db.get_stage_manifest(analysis.content_hash, "foundations", foundation_key(analysis))


def test_corrupt_location_alignment_rebuilds_without_parser(prepared):
    db, manager, analysis, original = prepared
    with db._connect() as conn:
        conn.execute(
            """UPDATE coach_stage_rounds SET payload = json_set(payload,
            '$.source_ids_fingerprint', 'wrong') WHERE stage='spatial' AND round_number=1"""
        )
    assert read_context(db, analysis, 1) is None
    with patch.object(manager, "analysis_path", side_effect=AssertionError("demo opened")):
        rebuilt = get_spatial_context(db, manager, analysis, 1)
    assert rebuilt.states.region_id.tolist() == original.states.region_id.tolist()
    assert rebuilt.states.event_id.tolist() == original.states.event_id.tolist()


def test_missing_foundation_round_is_rebuilt_from_saved_sources(prepared):
    db, manager, analysis, _ = prepared
    with db._connect() as conn:
        conn.execute("DELETE FROM coach_stage_rounds WHERE stage='foundations' AND round_number=1")
    assert read_context(db, analysis, 1) is None
    with patch.object(manager, "analysis_path", side_effect=AssertionError("demo opened")):
        rebuilt = get_spatial_context(db, manager, analysis, 1)
    assert 1 in rebuilt.foundations


def test_atomic_publication_rolls_back_all_stages(prepared):
    db, _, analysis, _ = prepared
    before = db.get_stage_manifest(analysis.content_hash, "observations")
    with db._connect() as conn:
        conn.execute("""CREATE TRIGGER fail_stage BEFORE INSERT ON coach_stage_rounds
                        WHEN NEW.stage='fail' BEGIN SELECT RAISE(ABORT,'failure'); END""")
    manifest = {"demo_id": analysis.content_hash, "cache_key": "new", "round_numbers": [1]}
    with pytest.raises(sqlite3.IntegrityError):
        db.save_stages(
            analysis.content_hash,
            {
                "observations": ("new", manifest, {1: {"test": True}}),
                "fail": ("new", manifest, {1: {"test": True}}),
            },
        )
    assert db.get_stage_manifest(analysis.content_hash, "observations") == before
    assert db.get_stage_manifest(analysis.content_hash, "fail") is None


def test_synthetic_map_without_mid_uses_same_preparation_detector(match_inputs):
    analysis, context = match_inputs
    analysis.map_name = "de_synthetic"
    context.observations.map_name = analysis.map_name
    from src.demos.observations import stamp_observation_ids

    base = context.observations.states[context.observations.states.tick.eq(199)]
    extra = [base.assign(tick=tick) for tick in (740, 1060)]
    context.observations.states = stamp_observation_ids(
        pd.concat([context.observations.states, *extra], ignore_index=True),
        analysis.content_hash,
        "states",
    )
    profile = MapProfile(
        "de_synthetic",
        "1",
        [
            Region(
                "target",
                "Target",
                nav_labels=["BombsiteA", "BombsiteB", "Middle"],
                kind="site",
                site_id="X",
                directions=["X"],
            ),
            Region("approach", "Approach", nav_labels=["TRamp"], kind="approach", directions=["X"]),
        ],
        capabilities=["regions", "site_boundaries", "directions"],
    )
    spatial = enrich_spatial(context.observations, profile)
    result = build_tactical_match(analysis, spatial)
    snap = result.rounds[0].ct_setup.setup_before_contact
    assert snap.counts == {"target": 5}
    assert result.rounds[0].t_preparation.orientation == {"X": 5}


def test_unknown_map_ui_keeps_equipment_and_events(match_inputs):
    analysis, context = match_inputs
    analysis.map_name = "de_unknown"
    context.observations.map_name = analysis.map_name
    spatial = enrich_spatial(context.observations)
    app = AppTest.from_string("""
import streamlit as st
from src.gui.round_context_view import render_round_context
render_round_context(
    st.session_state['analysis'], 'player', lambda match, rnd: st.session_state['context'])
""")
    app.session_state["analysis"] = analysis
    app.session_state["context"] = spatial
    app.run()
    app.button[0].click().run()
    assert not app.exception
    assert app.get("iframe") == []
    assert any("Ekwipunek" in table.value.columns for table in app.dataframe)
    assert any("Zdarzenie" in table.value.columns for table in app.dataframe)


def test_multilevel_radar_keeps_sample_height_distinct(match_inputs):
    analysis, context = match_inputs
    image = get_profile("de_mirage").radar_levels[0].image
    levels = [
        RadarLevel("lower", image, 0, 0, 1, z_max=0),
        RadarLevel("upper", image, 0, 0, 1, z_min=0),
    ]
    profile = replace(
        context.profile,
        radar_levels=levels,
        regions=[replace(r, level_id=None) for r in context.profile.regions],
    )
    spatial = enrich_spatial(context.observations, profile)
    spatial.observations.smokes = pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "tick": 200,
                "end_tick": 300,
                "x": 10,
                "y": 10,
                "z": z,
                "radius": 144,
                "end_source": "event",
            }
            for z in (-10, 10)
        ]
    )
    spatial.observations.shots = pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "tick": 200,
                "user_X": 10,
                "user_Y": 10,
                "user_Z": z,
                "user_yaw": 90,
            }
            for z in (-10, 10)
        ]
    )
    data = playback_data(spatial, analysis, 1, {}, "player", level_id="upper")
    assert data["level_id"] == "upper"
    assert {sample[10] for player in data["players"] for sample in player["samples"]} == {"upper"}
    assert [effect["level_id"] for effect in data["smokes"]] == ["lower", "upper"]
    assert [effect["level_id"] for effect in data["shots"]] == ["lower", "upper"]
