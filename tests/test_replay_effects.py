"""Smoke lifetime matching and exact gunfire source positions."""

from unittest.mock import Mock

import pandas as pd

from tests.map_support import MirageContext
from src.demos.replay_effects import extract_replay_effects
from src.gui.radar_player import playback_data
from tests.test_early_round import reference


def test_smoke_entity_reuse_expiry_outside_round_and_no_knife_flash():
    clock = pd.DataFrame([{"total_rounds_played": 1, "start_tick": 0,
                           "tick": 1000, "freeze_tick": 0}])
    utility = pd.DataFrame([
        {"source_event": "smokegrenade_detonate", "tick": tick,
         "total_rounds_played": 1, "entityid": eid, "x": 10, "y": 20, "z": 30}
        for tick, eid in [(100, 1), (200, 2), (300, 3)]
    ])
    expire = pd.DataFrame([
        {"entityid": 1, "tick": 400, "x": 99, "y": 20, "z": 30},
        {"entityid": 1, "tick": 500, "x": 10, "y": 20, "z": 30},
        {"entityid": 2, "tick": 1100, "x": 10, "y": 20, "z": 30},
    ])
    fire = pd.DataFrame([{"tick": 350, "weapon": weapon, "user_X": 42, "user_Y": 50,
                           "user_yaw": 90} for weapon in
                          ["weapon_ak47", "weapon_knife_survival_bowie",
                           "weapon_smokegrenade", "weapon_c4", "weapon_bayonet"]])
    parser = Mock()
    parser.parse_event.side_effect = lambda name, **_: (
        expire if name == "smokegrenade_expired" else fire
    )
    smokes, shots = extract_replay_effects(parser, clock, utility,
                                          {"smokegrenade_expired", "weapon_fire"}, {})
    assert smokes.end_tick.tolist() == [500, 1000, 1000]
    assert smokes.end_source.tolist() == ["event", "event", "estimated_22s"]
    assert shots.weapon.tolist() == ["weapon_ak47"]
    assert shots.user_X.item() == 42


def test_new_effects_survive_cache_and_playback_conversion():
    analysis, context = reference()
    context.smokes = pd.DataFrame([{
        "total_rounds_played": 1, "tick": 7000, "end_tick": 8000,
        "x": 10, "y": 20, "z": 30, "radius": 144, "end_source": "event",
    }])
    context.shots = pd.DataFrame([{
        "total_rounds_played": 1, "tick": 7100, "user_X": 100, "user_Y": 200,
        "user_yaw": 45, "silenced": True, "user_steamid": "P01",
    }])
    restored = MirageContext.from_json(context.to_json())
    data = playback_data(restored, analysis, 1, {"P01": "Alice"}, "P01")
    assert data["smokes"][0]["end"] == (8000-6828)/64
    assert not data["smokes"][0]["estimated"]
    assert data["shots"][0] == {"time": (7100-6828)/64, "x": 100, "y": 200,
                                     "yaw": 45, "silenced": True, "level_id": "main"}


def test_unavailable_effect_sources_do_not_fake_shots_or_expiry():
    clock = pd.DataFrame([{"total_rounds_played": 1, "tick": 1000}])
    diagnostic = {}
    smokes, shots = extract_replay_effects(Mock(), clock, pd.DataFrame(), set(), diagnostic)
    assert smokes.empty and shots.empty
    assert diagnostic["sources"]["weapon_fire"] == "absent"
