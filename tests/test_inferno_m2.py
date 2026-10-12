"""Independent Inferno map facts and shared-profile integration checks."""

from pathlib import Path

import pytest

from src.maps.registry import get_profile, profile_compatibility
from src.maps.resolver import classify, entry_route, region_site, support_sites


def test_inferno_profile_resolves_demo_places_and_radar() -> None:
    profile = get_profile('de_inferno')
    assert profile is not None
    assert profile_compatibility(profile, '14186') == 'verified'
    assert profile_compatibility(profile, 'unknown') == 'unverified'
    assert profile.supports('site_boundaries', 'entry_routes', 'radar')
    assert Path(profile.radar_levels[0].image).is_file()

    # Coordinates and names are observed at real plant events, not produced by
    # the map resolver. The two distinct numeric game site IDs are documented
    # in docs/inferno_m2.md.
    a = {'X': 2090.894287, 'Y': 182.033585, 'Z': 159,
         'last_place_name': 'BombsiteA'}
    b = {'X': 150.942963, 'Y': 2860.201904, 'Z': 160,
         'last_place_name': 'BombsiteB'}
    assert region_site(classify(a, profile).region_id, profile) == 'A'
    assert region_site(classify(b, profile).region_id, profile) == 'B'
    radar = profile.radar_levels[0]
    for sample in (a, b):
        px, py = radar.project(sample['X'], sample['Y'])
        assert 0 <= px < radar.width and 0 <= py < radar.height


@pytest.mark.parametrize(
    ('place', 'site', 'route'),
    [
        ('Banana', 'B', 'Banana'),
        ('Ruins', 'B', 'Ruiny'),
        ('TopofMid', 'A', 'Mid'),
        ('Quad', 'A', 'Quad'),
        ('Balcony', 'A', 'Balkon'),
    ],
)
def test_inferno_observed_entry_approaches(place: str, site: str, route: str) -> None:
    profile = get_profile('de_inferno')
    sample = {'last_place_name': place}
    assert entry_route(site, sample, profile) == route


def test_inferno_uncertain_and_ct_support_are_explicit() -> None:
    profile = get_profile('de_inferno')
    assert classify({'last_place_name': ''}, profile).status == 'unknown'
    assert support_sites('arch', profile) == ['A']
    assert support_sites('ruins', profile) == ['B']
    assert profile.coverage['geometry'] == 'nav-label-only'
    assert profile.coverage['visibility'] == 'not_supported'
