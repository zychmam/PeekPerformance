from dataclasses import replace

import pandas as pd
import pytest

from src.demos.round_index import RoundIndex
from src.maps.context import enrich_spatial
from src.maps.registry import get_profile, profile_compatibility, validate_assets
from src.maps.resolver import annotate_frame, classify, entry_route, region_direction
from src.models.observations import MatchObservations
from src.models.spatial import MapProfile, RadarLevel, Region, RegionBounds, SpatialConnection, SpatialRelations


def stacked_profile():
    return MapProfile("test_stacked", "1", [
        Region("lower", "Lower", ["Overlap"], kind="site", site_id="X", level_id="low",
               bounds=[RegionBounds(0, 10, 0, 10, 0, 10, include_max_z=False)]),
        Region("upper", "Upper", ["Overlap"], kind="site", site_id="Y", level_id="high",
               bounds=[RegionBounds(0, 10, 0, 10, 10, 20)]),
        Region("fork", "Fork", ["Fork"], directions=["X", "Y"], support_sites=["X"]),
    ], connections=[SpatialConnection("upper", "lower", kind="drop")],
       radar_levels=[RadarLevel("low", "unused.png", 0, 10, 1, z_min=0, z_max=10),
                     RadarLevel("high", "unused.png", 0, 10, 1, z_min=10, z_max=20)],
       coverage={"connections": "partial"})


def test_mirage_reference_boxes_and_route_uncertainty():
    profile = get_profile("de_mirage")
    assert len(profile.regions) == 23
    row = {"event_id": "source:0", "last_place_name": "PalaceInterior", "X": 100, "Y": -1400, "Z": -150}
    assert classify(row, profile).region_id == "ramp_a"
    assert entry_route("A", row, profile) == "Rampa A"
    row.update(Y=-2000, Z=-100)
    assert classify(row, profile).region_id == "palace"
    assert entry_route("A", row, profile) == "Pałac"
    row.update(Z=None)
    assert entry_route("A", row, profile) == "Nieustalony kierunek"
    assert profile_compatibility(profile, 14189) == "verified"
    assert profile_compatibility(profile, 99999) == "unverified"


def test_multilevel_height_boundaries_no_mid_and_direction_ambiguity():
    profile = stacked_profile()
    assert not any(r.kind == "mid" for r in profile.regions)
    row = {"event_id": "s", "last_place_name": "Overlap", "X": 5, "Y": 5, "Z": 9.99}
    assert classify(row, profile).region_id == "lower"
    row["Z"] = 10
    assert classify(row, profile).region_id == "upper"
    row["Z"] = None
    assert classify(row, profile).region_id is None
    assert region_direction("fork", profile) is None
    relations = SpatialRelations(profile)
    assert relations.connection("upper", "lower").kind == "drop"
    assert relations.connection("lower", "upper") is None
    assert relations.connection("fork", "lower") is None
    assert not hasattr(relations, "visible")


def test_unexplained_label_geometry_conflict_retains_candidates():
    profile = MapProfile("conflict", "1", [
        Region("label", "Label", ["Here"]),
        Region("geometry", "Geometry", bounds=[RegionBounds(0, 10, 0, 10)]),
    ])
    assignment = classify({"event_id": "e", "last_place_name": "Here", "X": 5, "Y": 5}, profile)
    assert assignment.region_id is None
    assert assignment.status == "partial"
    assert assignment.candidates == ["geometry", "label"]


def test_sources_and_ids_unchanged_by_profiles_and_presentation():
    profile = get_profile("de_mirage")
    raw = pd.DataFrame([{"event_id": "e", "last_place_name": "BombsiteA", "tick": 10}])
    before = raw.copy(deep=True)
    enriched = annotate_frame(raw, profile)
    assert enriched.region_id.tolist() == ["site_a"]
    pd.testing.assert_frame_equal(raw, before)
    renamed = replace(profile, regions=[replace(r, name="Renamed " + r.name) for r in profile.regions])
    assert renamed.semantic_fingerprint == profile.semantic_fingerprint
    assert renamed.presentation_fingerprint != profile.presentation_fingerprint
    again = annotate_frame(raw, renamed)
    assert again.place.iloc[0].startswith("Renamed")
    assert classify(raw.iloc[0].to_dict(), profile).observation_id == "e"
    assert get_profile("de_not_registered") is None
    unknown = annotate_frame(raw, None)
    assert unknown.region_id.isna().all()
    assert unknown.location_status.eq("unknown").all()
    obs = MatchObservations("demo", "de_mirage", "key", states=raw)
    context = enrich_spatial(obs)
    assert context.states.observation_id.tolist() == ["e"]
    pd.testing.assert_frame_equal(obs.states, before)


def test_profile_validation_relations_geometry_assets():
    with pytest.raises(ValueError, match="geometry"):
        RegionBounds(10, 0, 0, 10)
    with pytest.raises(ValueError, match="unknown region"):
        MapProfile("bad", "1", [Region("one", "One")],
                   connections=[SpatialConnection("one", "missing")])
    with pytest.raises(ValueError, match="radar asset"):
        validate_assets(stacked_profile())


def test_round_index_time_bounds_staleness_gaps_and_source_order():
    frame = pd.DataFrame([
        {"steamid": "p", "tick": 30, "event_id": "future", "total_rounds_played": 1},
        {"steamid": "p", "tick": 10, "event_id": "first", "total_rounds_played": 1},
        {"steamid": "p", "tick": 10, "event_id": "second", "total_rounds_played": 1},
        {"steamid": "p", "tick": 19, "event_id": "other-round", "total_rounds_played": 2},
    ])
    index = RoundIndex(frame, 1)
    assert index.before(10, player_id="p").status == "missing"
    assert index.latest(10, player_id="p").row["event_id"] == "second"
    assert index.latest(20, player_id="p").sample_tick == 10
    assert index.latest(20, player_id="p", max_age_ticks=5).status == "stale"
    assert index.latest(20, player_id="p", max_gap_ticks=12).status == "gap"
    assert len(index.between(0, 20, player_id="p")) == 2
    explicit = RoundIndex(frame, 1, gaps={"p": [(10, 30)]})
    assert explicit.latest(20, player_id="p").status == "gap"
    assert explicit.latest(30, player_id="p").status == "observed"
