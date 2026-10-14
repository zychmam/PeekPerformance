"""Observed grenade flight: reused entities, real turns, gaps, effects and warm cache."""

from unittest.mock import patch

import pandas as pd

from src.demos.demo_manager import DemoManager
from src.demos.viewer_projectiles import get_round_projectiles, normalize_projectiles
from src.models.models import DemoAnalysis
from src.storage.database import Database


def clock():
    return pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "start_tick": 0,
                "freeze_tick": 10,
                "tick": 100,
                "tick_rate": 64,
            },
            {
                "total_rounds_played": 2,
                "start_tick": 101,
                "freeze_tick": 110,
                "tick": 200,
                "tick_rate": 64,
            },
        ]
    )


def samples(ticks, *, kind="CFlashbangProjectile", entity=42, owner="76561198008873400"):
    return pd.DataFrame(
        [
            {
                "tick": tick,
                "grenade_type": kind,
                "grenade_entity_id": entity,
                "steamid": owner,
                "x": float(tick),
                "y": 0.0,
                "z": 50.0,
            }
            for tick in ticks
        ]
    )


def test_reused_entity_across_rounds_and_gaps_does_not_join_flights():
    raw = samples([1, 2, 20, 21, 22, 50, 51, 120, 121])
    result = normalize_projectiles(raw, clock(), pd.DataFrame())
    assert [(p["start_tick"], p["end_tick"]) for p in result[1]["projectiles"]] == [
        (20, 23),
        (50, 52),
    ]
    assert result[2]["projectiles"][0]["start_tick"] == 120


def test_smoke_flight_stops_at_matching_effect_not_expiry_or_other_owner():
    raw = samples(range(20, 90), kind="CSmokeGrenadeProjectile")
    effects = pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "entityid": 42,
                "kind": "Smoke",
                "tick": 25,
                "user_steamid": "other",
            },
            {
                "total_rounds_played": 1,
                "entityid": 42,
                "kind": "Smoke",
                "tick": 40,
                "user_steamid": "76561198008873400",
            },
        ]
    )
    (projectile,) = normalize_projectiles(raw, clock(), effects)[1]["projectiles"]
    assert projectile["end_tick"] == 40
    assert projectile["end_source"] == "effect_entity_owner"
    assert projectile["samples"][-1][0] == 39


def test_smoke_persisting_next_round_does_not_start_a_new_flight():
    raw = samples(range(20, 150), kind="CSmokeGrenadeProjectile")
    effects = pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "entityid": 42,
                "kind": "Smoke",
                "tick": 40,
                "user_steamid": "76561198008873400",
            }
        ]
    )
    result = normalize_projectiles(raw, clock(), effects)
    assert len(result[1]["projectiles"]) == 1
    assert result[2]["projectiles"] == []


def test_bounce_is_preserved_between_regular_samples_and_nulls_are_not_positions():
    raw = samples(range(20, 32))
    raw["x"] = [0, 10, 20, 10, 0, -10, -20, -30, -40, -50, -60, -70]
    held = samples([25], kind="CFlashbang")
    missing = samples([40, 41])
    missing["x"] = float("nan")
    (projectile,) = normalize_projectiles(
        pd.concat([raw, held, missing]),
        clock(),
        pd.DataFrame(),
    )[1]["projectiles"]
    assert [22, 20.0, 0.0, 50.0] in projectile["samples"]
    assert projectile["start_tick"] == 20
    assert projectile["end_tick"] == 32


def test_cold_prepare_from_saved_projectiles_then_round_read_without_source(tmp_path):
    db = Database(str(tmp_path / "viewer.db"))
    analysis = DemoAnalysis(
        file_name="match.dem",
        stored_file_name="match.dem",
        content_hash="match",
        rounds_df=clock(),
        grenades_df=samples([20, 21, 22, 120, 121]),
    )
    db.upsert_demo_analysis(analysis)
    manifest = {"demo_id": "match", "cache_key": "sources", "round_numbers": [1, 2]}
    db.save_stages(
        "match",
        {
            "observations": (
                "sources",
                manifest,
                {
                    n: {
                        "clock": part.to_dict("records"),
                        "utility": [],
                        "states": ["do not decode"],
                    }
                    for n, part in clock().groupby("total_rounds_played")
                },
            )
        },
    )
    lightweight = db.get_demo_analysis("match", include_grenades=False)
    assert lightweight.grenades_df.empty
    manager = DemoManager(str(tmp_path / "demos"))
    with patch.object(manager, "analysis_path", side_effect=AssertionError("binary opened")):
        first = get_round_projectiles(db, manager, lightweight, "sources", 1)
    assert len(first["projectiles"]) == 1
    with (
        patch.object(db, "get_demo_projectiles", side_effect=AssertionError("raw source read")),
        patch.object(db, "get_observation_frame", side_effect=AssertionError("source decoded")),
        patch.object(manager, "analysis_path", side_effect=AssertionError("binary opened")),
    ):
        second = get_round_projectiles(db, manager, lightweight, "sources", 2)
    assert second["projectiles"][0]["start_tick"] == 120
