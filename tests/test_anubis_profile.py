"""Anubis spatial contract against raw positions from the provided demo."""

import json
from pathlib import Path

import pytest

from src.maps.registry import get_profile, profile_compatibility
from src.maps.resolver import classify, entry_route, region_site, support_sites

REFERENCE = json.loads((Path(__file__).parent / "reference/anubis_spatial_facts.json").read_text())


def test_anubis_profile_matches_all_observed_labels_and_assets():
    profile = get_profile("de_anubis")
    assert profile.supports("radar", "site_boundaries", "entry_routes", "forward_presence")
    assert profile_compatibility(profile, REFERENCE["patch"]) == "verified"
    assert profile_compatibility(profile, "unknown") == "unverified"
    assert Path(profile.radar_levels[0].image).is_file()
    for sample in REFERENCE["places"]:
        assignment = classify(sample, profile)
        assert assignment.status == "observed", sample
        assert assignment.region_id and assignment.level_id == "main"


def test_anubis_plants_and_radar_match_independent_positions():
    profile = get_profile("de_anubis")
    sites = set()
    for plant in REFERENCE["plants"]:
        site = region_site(classify(plant, profile).region_id, profile)
        assert site == {"BombsiteA": "A", "BombsiteB": "B"}[plant["last_place_name"]]
        px, py = profile.radar_levels[0].project(plant["X"], plant["Y"])
        assert (
            (700 < px < 850 and 200 < py < 330)
            if site == "A"
            else (280 < px < 370 and 450 < py < 550)
        )
        sites.add(site)
    assert sites == {"A", "B"}


@pytest.mark.parametrize(
    ("label", "site", "route"),
    [
        ("Main", "A", "A main"),
        ("Walkway", "A", "Walkway / od mida"),
        ("Heaven", "A", "Heaven"),
        ("Tunnel", "A", "Od CT / tunel"),
        ("OutsideLong", "B", "B main / long"),
        ("Connector", "B", "Łącznik / od wody"),
        ("BackofB", "B", "Od tyłu B"),
        ("PalaceInterior", "B", "Palace / od mida"),
    ],
)
def test_anubis_site_routes(label, site, route):
    assert entry_route(site, {"last_place_name": label}, get_profile("de_anubis")) == route


def test_anubis_bridge_and_canal_are_not_merged_by_xy_projection():
    profile = get_profile("de_anubis")
    upper = classify({"last_place_name": "Bridge", "X": -100, "Y": 300, "Z": 0}, profile)
    lower = classify({"last_place_name": "Canal", "X": -100, "Y": 300, "Z": -150}, profile)
    assert upper.region_id == "bridge" and lower.region_id == "canal"
    assert classify({"X": -100, "Y": 300, "Z": -150}, profile).status == "unknown"
    assert classify({"last_place_name": "Water"}, profile).region_id == "ct_water"
    assert entry_route("A", {"last_place_name": "Canal"}, profile) == "Nieustalony kierunek"
    assert entry_route("B", {"last_place_name": "Canal"}, profile) == "Nieustalony kierunek"


def test_anubis_shared_support_and_forward_boundaries_are_conservative():
    profile = get_profile("de_anubis")
    for rid in ("ct_spawn", "canal"):
        assert profile.regions_by_id[rid].defense_sector is None
        assert support_sites(rid, profile) == ["A", "B"]
    assert profile.regions_by_id["middle"].defense_sector == "mid"
    main = profile.regions_by_id["a_main"]
    assert main.is_forward("CT", {"X": 1600, "Y": 1000, "Z": -150})
    assert not main.is_forward("CT", {"X": 1600, "Y": 1600, "Z": -150})
    assert main.is_forward("CT", {}) is None
    assert not profile.regions_by_id["ct_spawn"].is_forward("CT", {})
    assert profile.coverage["visibility"] == "not_supported"
