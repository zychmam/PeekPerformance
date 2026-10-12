"""Contracts protect map-independent identity and spatial uncertainty."""

from copy import deepcopy

import pandas as pd
import pytest

from src.models.observations import (
    DetectorConfig,
    MatchObservations,
    RoundClock,
    StageManifest,
    observation_id,
)
from src.models.spatial import LocationAssignment, MapProfile, RegionBounds, SpatialRelations


def profile_data():
    return {
        "map_name": "de_test", "profile_version": "1",
        "capabilities": ["site_boundaries", "radar"],
        "coverage": {"connections": "partial"},
        "regions": [
            {"id": "site", "name": "Site", "kind": "site", "site_id": "A"},
            {"id": "path", "name": "Path", "kind": "approach",
             "support_sites": ["A"], "route_names": {"A": "Entry"}, "directions": ["A"],
             "bounds": [{"x_min": 0, "x_max": 5, "y_min": 0, "y_max": 5,
                         "z_min": 0, "z_max": 10, "include_max_z": False}]},
        ],
        "connections": [{"from_region": "path", "to_region": "site", "kind": "drop"}],
        "radar_levels": [{"id": "base", "image": "test.png", "origin_x": 0,
                          "origin_y": 100, "scale": 2}],
    }


def test_profile_text_changes_do_not_invalidate_semantic_analysis():
    data = profile_data()
    original = MapProfile.from_dict(data)
    renamed = deepcopy(data)
    renamed["profile_version"] = "2"
    renamed["regions"][1]["name"] = "Different text"
    renamed["regions"][1]["route_names"]["A"] = "Translated entry"
    renamed["radar_levels"][0]["image"] = "other.png"
    renamed = MapProfile.from_dict(renamed)
    assert original.semantic_fingerprint == renamed.semantic_fingerprint
    assert original.presentation_fingerprint != renamed.presentation_fingerprint
    moved = deepcopy(data)
    moved["regions"][1]["bounds"][0]["x_max"] = 6
    assert original.semantic_fingerprint != MapProfile.from_dict(moved).semantic_fingerprint
    without_route = deepcopy(data)
    without_route["regions"][1]["route_names"] = {}
    assert original.semantic_fingerprint != MapProfile.from_dict(without_route).semantic_fingerprint
    assert MapProfile.from_dict(original.to_dict()) == original


@pytest.mark.parametrize("mutation", ["duplicate", "bad_edge", "bad_site", "schema", "geometry"])
def test_profile_rejects_invalid_declarations(mutation):
    data = profile_data()
    if mutation == "duplicate":
        data["regions"].append(deepcopy(data["regions"][0]))
    elif mutation == "bad_edge":
        data["connections"][0]["to_region"] = "missing"
    elif mutation == "bad_site":
        data["regions"][1]["support_sites"] = ["B"]
    elif mutation == "schema":
        data["schema_version"] = 900
    else:
        data["regions"][1]["bounds"][0]["x_min"] = 8
    with pytest.raises(ValueError):
        MapProfile.from_dict(data)


def test_relations_keep_sites_support_direction_and_traversal_separate():
    profile = MapProfile.from_dict(profile_data())
    relations = SpatialRelations(profile)
    assert relations.site("path") is None
    assert relations.site("site") == "A"
    assert relations.support("path") == ("A",)
    assert relations.approaches("path") == ("A",)
    assert relations.connection("path", "site").kind == "drop"
    assert relations.connection("site", "path") is None
    assert not profile.supports("visibility")
    assert "mid" not in [r.kind for r in profile.regions]


def test_height_boundaries_and_missing_height_do_not_overlap():
    low = RegionBounds(0, 5, 0, 5, 0, 10, include_max_z=False)
    high = RegionBounds(0, 5, 0, 5, 10, 20)
    assert low.contains(2, 2, 9.9)
    assert not low.contains(2, 2, 10)
    assert high.contains(2, 2, 10)
    assert not low.contains(2, 2, None)


def test_round_clock_preserves_unknown_freeze_and_explicit_time_basis():
    clock = RoundClock(0, 10, 100, 1000)
    assert clock.seconds(164) == 1
    assert clock.tick_at(0.5) == 132
    assert RoundClock.from_dict(clock.to_dict()) == clock
    unknown = RoundClock(0, 10, None, 1000)
    assert unknown.seconds(100) is None
    with pytest.raises(ValueError):
        RoundClock(0, 10, 100, 1000, tick_rate=128)
    measured = RoundClock(0, 10, 100, 1000, tick_rate=128, time_source="header")
    assert measured.seconds(228) == 1
    row = {"total_rounds_played": 0, "start_tick": 10, "freeze_tick": 100,
           "tick": 1000, "tick_rate": 128, "time_source": "header.tick_rate"}
    assert RoundClock.from_row(row).seconds(228) == 1


def test_sources_roundtrip_preserves_large_ids_and_rejects_derived_labels():
    source = MatchObservations("demo", "de_unknown", "key", states=pd.DataFrame([
        {"steamid": 76561198000000001, "tick": 150, "X": 3.0, "last_place_name": "Raw"}
    ]))
    restored = MatchObservations.from_json(source.to_json())
    assert restored.states.iloc[0].steamid == "76561198000000001"
    assert source.to_json() == restored.to_json()
    with pytest.raises(ValueError):
        MatchObservations("demo", "map", "key", states=pd.DataFrame([{"zone": "A"}]))
    first = observation_id("demo", "kills", "fingerprint", 0)
    assert first != observation_id("demo", "kills", "fingerprint", 1)


def test_stage_identity_depends_on_inputs_and_algorithm_not_status():
    one = StageManifest("location", 1, "1", {"sources": "s", "map_semantics": "m"})
    partial = StageManifest("location", 1, "1", one.dependencies, status="partial")
    other = StageManifest("location", 1, "1", {"sources": "s", "map_semantics": "changed"})
    assert one.cache_key == partial.cache_key
    assert one.cache_key != other.cache_key
    assert DetectorConfig().fingerprint != DetectorConfig(entry_group_seconds=9).fingerprint


def test_ambiguous_and_unknown_locations_retain_source_reference():
    ambiguous = LocationAssignment("source", candidates=["lower", "upper"], status="partial")
    assert LocationAssignment.from_dict(ambiguous.to_dict()) == ambiguous
    assert ambiguous.region_id is None
    assert LocationAssignment("source").status == "unknown"
    with pytest.raises(ValueError):
        LocationAssignment("source", status="observed")
