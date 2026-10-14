"""Dust2 profile against independent coordinates from the user's demo."""

import json
from pathlib import Path

import pytest

from src.maps.registry import get_profile, profile_compatibility
from src.maps.resolver import classify, entry_route, region_site, support_sites

REFERENCE = json.loads((Path(__file__).parent / "reference/dust2_spatial_facts.json").read_text())


def test_dust2_assets_patch_and_observed_places():
    profile = get_profile("de_dust2")
    assert profile.supports("radar", "site_boundaries", "forward_presence", "entry_routes")
    assert profile_compatibility(profile, REFERENCE["patch"]) == "verified"
    assert profile_compatibility(profile, "unknown") == "unverified"
    assert Path(profile.radar_levels[0].image).is_file()
    for sample in REFERENCE["places"]:
        assignment = classify(sample, profile)
        assert assignment.status == "observed", sample
        assert assignment.region_id is not None and assignment.level_id == "main"
    assert profile.coverage["geometry"] == "nav-label-only"
    assert profile.coverage["visibility"] == "not_supported"


def test_dust2_actual_plants_match_site_and_static_radar_orientation():
    profile = get_profile("de_dust2")
    radar = profile.radar_levels[0]
    sites = set()
    for plant in REFERENCE["plants"]:
        site = region_site(classify(plant, profile).region_id, profile)
        assert site == {"BombsiteA": "A", "BombsiteB": "B"}[plant["last_place_name"]]
        # A is upper right and B upper left on the extracted static north-up PNG.
        px, py = radar.project(plant["X"], plant["Y"])
        assert 0 <= py < 250
        assert (750 < px < 900) if site == "A" else (150 < px < 300)
        sites.add(site)
    assert sites == {"A", "B"}


@pytest.mark.parametrize(
    ("label", "site", "route"),
    [
        ("LongA", "A", "Long"),
        ("ARamp", "A", "Long / rampa A"),
        ("ExtendedA", "A", "Short"),
        ("ShortStairs", "A", "Short"),
        ("UpperTunnel", "B", "Tunel"),
        ("BDoors", "B", "Drzwi B"),
        ("Hole", "B", "Okno B"),
    ],
)
def test_dust2_entry_routes(label, site, route):
    assert entry_route(site, {"last_place_name": label}, get_profile("de_dust2")) == route


def test_dust2_shared_spawn_and_mid_never_double_count_sites():
    profile = get_profile("de_dust2")
    assert profile.regions_by_id["ct_spawn"].defense_sector is None
    assert support_sites("ct_spawn", profile) == ["A", "B"]
    assert profile.regions_by_id["mid_doors"].defense_sector == "mid"
    assert profile.regions_by_id["lower_tunnel"].defense_sector == "mid"
    assert entry_route("B", {"last_place_name": "Middle"}, profile) == "Nieustalony kierunek"


def test_dust2_forward_presence_does_not_treat_back_long_or_spawn_as_ct_push():
    profile = get_profile("de_dust2")
    long = profile.regions_by_id["long_a"]
    assert long.is_forward("CT", {"X": 1400, "Y": 1000, "Z": 0})
    assert not long.is_forward("CT", {"X": 1400, "Y": 2200, "Z": 0})
    assert long.is_forward("CT", {}) is None
    assert not long.is_forward("T", {"X": 1400, "Y": 1000})
    assert not profile.regions_by_id["ct_spawn"].is_forward("CT", {})


def test_dust2_stacked_tunnels_and_unknown_places_are_explicit():
    profile = get_profile("de_dust2")
    upper = classify({"last_place_name": "UpperTunnel"}, profile)
    lower = classify({"last_place_name": "LowerTunnel"}, profile)
    assert upper.region_id != lower.region_id
    assert classify({"last_place_name": "", "X": -1900, "Y": 1300}, profile).status == "unknown"
    assert classify({"last_place_name": "NewUnknownArea"}, profile).status == "unknown"
