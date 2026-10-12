"""Foundation source gaps, exact chronology, provenance and transactional storage."""

import json
import sqlite3
from copy import deepcopy
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from src.demos.coach_foundations import (
    build_foundations,
    decode_foundation,
    equipment_at,
    foundation_key,
    foundation_payload,
)
from src.demos.foundation_sources import extract_equipment
from tests.map_support import MirageContext, context_key
from src.demos.replay_effects import extract_replay_effects
from tests.map_support import get_mirage_context
from src.demos.tactical_rounds import build_tactical_match, load_tactical_match
from src.demos.versions import ANALYSIS_VERSION
from src.models.models import DemoAnalysis
from src.models.tactical import Status, TacticalMatch
from src.storage.database import Database


@pytest.fixture()
def match_inputs():
    ids = [str(76561198008873401 + i) for i in range(10)]
    roster = [
        {"steamid": pid, "team_num": 2 if i < 5 else 3, "total_rounds_played": 1}
        for i, pid in enumerate(ids)
    ]
    analysis = DemoAnalysis(
        "mirage.dem",
        map_name="de_mirage",
        content_hash="foundation-demo",
        analysis_version=ANALYSIS_VERSION,
        player_info=pd.DataFrame(
            [{"steamid": pid, "name": f"Player {i}"} for i, pid in enumerate(ids)]
        ),
        round_roster_df=pd.DataFrame(roster),
        rounds_df=pd.DataFrame(
            [{"total_rounds_played": 1, "start_tick": 0, "tick": 2000, "winner": "CT"}]
        ),
        kills_df=pd.DataFrame(
            [
                {
                    "total_rounds_played": 1,
                    "tick": 250,
                    "attacker_steamid": ids[0],
                    "user_steamid": ids[5],
                    "attacker_team_num": 2,
                    "user_team_num": 3,
                }
            ]
        ),
        damage_df=pd.DataFrame(
            [
                {
                    "total_rounds_played": 1,
                    "tick": tick,
                    "enemy_damage": damage,
                    "actual_damage": 10,
                    "weapon": weapon,
                    "attacker_steamid": ids[0],
                    "user_steamid": ids[5],
                    "attacker_team_num": 2,
                    "user_team_num": 3,
                }
                for tick, damage, weapon in [
                    (120, 0, "ak47"),
                    (200, 10, "hegrenade"),
                    (240, 10, "ak47"),
                ]
            ]
        ),
        bomb_events_df=pd.DataFrame(
            [
                {
                    "total_rounds_played": 1,
                    "tick": 1000,
                    "event": "bomb_planted",
                    "user_steamid": ids[0],
                }
            ]
        ),
    )
    states = []
    for tick in [100, 199, 200, 239, 249, 500, 2000]:
        for i, pid in enumerate(ids):
            place = (
                "TRamp" if i < 5 else "BombsiteA" if i < 7 else "BombsiteB" if i < 9 else "Middle"
            )
            if tick >= 200 and i >= 5:
                place = "BombsiteB"
            states.append(
                {
                    "total_rounds_played": 1,
                    "tick": tick,
                    "steamid": pid,
                    "team_num": 2 if i < 5 else 3,
                    "X": 0,
                    "Y": 0,
                    "Z": 0,
                    "health": 100,
                    "is_alive": True,
                    "last_place_name": place,
                    "has_bomb": i == 0,
                }
            )
    context = MirageContext(
        analysis.rounds_df.assign(freeze_tick=100),
        pd.DataFrame(states),
        pd.DataFrame(),
        {
            "sources": {
                "weapon_fire": "ok",
                "equipment_inventory": "ok",
                "equipment_weapon": "ok",
                "equipment_armor": "ok",
                "equipment_defuse": "ok",
                "equipment_economy": "ok",
                "bomb_planted": "ok",
                "bomb_pickup": "ok",
            }
        },
    )
    context.equipment = pd.DataFrame(
        [
            {
                "tick": tick,
                "total_rounds_played": 1,
                "steamid": pid,
                "team_num": 2 if i < 5 else 3,
                "inventory": ["AK-47", "Flashbang", "Flashbang"]
                if tick == 100
                else ["AK-47", "Flashbang"],
                "active_weapon_name": "AK-47",
                "armor_value": 100,
                "has_helmet": True,
                "has_defuser": i >= 5,
            }
            for tick in [100, 300]
            for i, pid in enumerate(ids)
        ]
    )
    context.economy = pd.DataFrame(
        [
            {
                "tick": 100,
                "total_rounds_played": 1,
                "steamid": pid,
                "team_num": 2 if i < 5 else 3,
                "balance": 50,
                "current_equip_value": 4000,
                "cash_spent_this_round": 3000,
                "start_balance": 3050,
                "round_start_equip_value": 4000,
            }
            for i, pid in enumerate(ids)
        ]
    )
    context.bombs = pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "tick": 1000,
                "event": "bomb_planted",
                "user_steamid": ids[0],
            },
            {"total_rounds_played": 1, "tick": 180, "event": "bomb_pickup", "user_steamid": ids[0]},
        ]
    )
    context.diagnostics["equipment_coverage"] = {
        1: {
            pid: {
                "first_tick": 100,
                "last_tick": 2000,
                "max_gap_ticks": 6,
                "gaps": [],
                "sample_count": 318,
            }
            for pid in ids
        }
    }
    return analysis, context


def test_precontact_uses_strictly_earlier_state_and_keeps_contact_types(match_inputs):
    analysis, context = match_inputs
    match = build_tactical_match(analysis, context)
    rnd = match.rounds[0]
    foundation = rnd.foundation
    assert foundation.contact_references["first_enemy_damage"].tick == 200
    assert foundation.contact_references["first_firearm_damage"].tick == 240
    assert foundation.contact_references["first_enemy_kill"].tick == 250
    assert foundation.setup_before_contact["CT"].counts == {}
    assert rnd.ct_setup.setup_before_contact.counts == {"site_a": 2, "site_b": 2, "mid": 1}
    assert all(p["sample_tick"] == 199 for p in foundation.setup_before_contact["CT"].players)
    assert rnd.ct_setup.setup_before_contact.tick == 199
    assert rnd.fights_status == rnd.retake.status == Status.NOT_EVALUATED
    assert (
        TacticalMatch.from_dict(json.loads(json.dumps(match.to_dict()))).to_dict()
        == match.to_dict()
    )


def test_missing_prior_samples_kill_fallback_and_same_tick_do_not_invent_order(match_inputs):
    analysis, context = match_inputs
    context.observations.states = context.states[context.states.tick.ge(200)]
    analysis.damage_df = analysis.damage_df.iloc[:0]
    analysis.kills_df.loc[0, "tick"] = 200
    match = build_tactical_match(analysis, context)
    foundation = match.rounds[0].foundation
    assert foundation.contact_references["preparation_reference"].tick == 200
    assert foundation.setup_before_contact["CT"].status == Status.UNKNOWN
    assert not foundation.setup_before_contact["CT"].players
    analysis.kills_df = pd.concat([analysis.kills_df, analysis.kills_df], ignore_index=True)
    foundation = build_foundations(analysis, context)[0][1]
    assert len(foundation.contact_references["first_enemy_kill"].evidence_ids) == 2
    analysis.kills_df = analysis.kills_df.iloc[:0]
    foundation = build_foundations(analysis, context)[0][1]
    assert foundation.contact_references["preparation_reference"].tick is None
    assert foundation.contact_references["preparation_reference"].status == Status.UNKNOWN
    assert not foundation.setup_before_contact


def test_inventory_counts_and_compressed_lookup_respect_unknowns_and_gaps(match_inputs):
    analysis, context = match_inputs
    pid = analysis.player_info.iloc[0].steamid
    foundation = build_foundations(analysis, context)[0][1]
    start = next(obs for obs in foundation.equipment_start if obs.player_id == pid)
    assert start.inventory["Flashbang"] == 2
    assert start.economy["balance"] == 50
    assert equipment_at(foundation, pid, 299)["observation"].inventory["Flashbang"] == 2
    assert equipment_at(foundation, pid, 300)["observation"].inventory["Flashbang"] == 1
    foundation.equipment_coverage[pid]["gaps"] = [[400, 700]]
    assert equipment_at(foundation, pid, 500) is None
    assert equipment_at(foundation, pid, 99) is None
    assert equipment_at(foundation, pid, 2001) is None
    context.equipment["inventory"] = None
    foundation = build_foundations(analysis, context)[0][1]
    assert foundation.equipment_start[0].inventory is None
    assert foundation.source_quality["equipment_inventory"].availability.status == Status.PARTIAL


def test_optional_property_failure_preserves_armor_inventory_and_economy():
    clock = pd.DataFrame(
        [{"total_rounds_played": 1, "start_tick": 0, "tick": 1000, "freeze_tick": 100}]
    )
    parser = Mock()

    def parse(props, ticks):
        if "has_helmet" in props or "start_balance" in props:
            raise ValueError("Unsupported optional property")
        return pd.DataFrame(
            [
                {
                    "tick": tick,
                    "steamid": "76561198008873401",
                    **{
                        prop: ["Flashbang", "Flashbang"]
                        if prop == "inventory"
                        else 2
                        if prop == "team_num"
                        else 80
                        for prop in props
                    },
                }
                for tick in ticks
            ]
        )

    parser.parse_ticks.side_effect = parse
    diagnostics = {}
    equipment, economy, coverage = extract_equipment(parser, [100, 106, 500], clock, diagnostics)
    assert equipment.iloc[0].inventory == ["Flashbang", "Flashbang"]
    assert equipment.iloc[0].armor_value == 80
    assert "has_helmet" not in equipment
    assert economy.iloc[0].balance == 80
    assert "start_balance" not in economy
    assert coverage[1]["76561198008873401"]["gaps"] == [[106, 500]]


def test_absent_events_are_unknown_but_successful_empty_stream_is_verified_zero(match_inputs):
    analysis, context = match_inputs
    foundation = build_foundations(analysis, context)[0][1]
    assert foundation.source_quality["shots"].availability.status == Status.ABSENT
    assert foundation.source_quality["bomb_abortplant"].availability.status == Status.UNKNOWN
    assert foundation.source_quality["bomb_pickup"].availability.status == Status.OBSERVED
    assert len(foundation.bomb_event_ids) == 2  # plant once, pickup once
    context.diagnostics["sources"]["weapon_fire"] = "error: RuntimeError"
    foundation = build_foundations(analysis, context)[0][1]
    assert foundation.source_quality["shots"].availability.status == Status.UNKNOWN


def test_throw_effect_windows_are_independent_and_smoke_estimate_stays_visual(match_inputs):
    analysis, context = match_inputs
    pid = analysis.player_info.iloc[0].steamid
    clock = context.clock
    throws = pd.DataFrame(
        [
            {
                "tick": 100 + 14 * 64,
                "weapon": "weapon_smokegrenade",
                "user_steamid": pid,
                "user_team_num": 2,
            }
        ]
    )
    effects = pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "tick": 100 + 16 * 64,
                "kind": "Smoke",
                "source_event": "smokegrenade_detonate",
                "entityid": 10,
                "user_steamid": pid,
                "user_team_num": 2,
                "x": 1,
                "y": 2,
                "z": 3,
            }
        ]
    )
    parser = Mock()
    parser.parse_event.return_value = throws
    extras = {}
    context.utility = effects
    context.smokes, context.shots = extract_replay_effects(
        parser, clock, effects, {"weapon_fire"}, context.diagnostics, extras=extras
    )
    context.throws = extras["throws"]
    context.utility_lifecycles = extras["utility_lifecycles"]
    match = build_tactical_match(analysis, context)
    prep = match.rounds[0].t_preparation
    assert len(prep.utility_windows["15"]["throws"]) == 1
    assert len(prep.utility_windows["10"]["throws"]) == 0
    assert len(prep.utility_windows["15"]["effects"]) == 0
    lifecycle = context.utility_lifecycles.iloc[0]
    assert lifecycle.throw_tick == 100 + 14 * 64
    assert lifecycle.throw_match == "unique_temporal_limited"
    assert lifecycle.end_tick is None
    assert lifecycle.end_source == "unknown"
    assert context.smokes.iloc[0].end_source == "estimated_22s"


def test_ambiguous_consecutive_flashes_do_not_force_a_throw_match(match_inputs):
    _, context = match_inputs
    pid = "76561198008873401"
    shots = pd.DataFrame(
        [
            {"tick": tick, "weapon": "weapon_flashbang", "user_steamid": pid, "user_team_num": 2}
            for tick in [150, 160]
        ]
    )
    utility = pd.DataFrame(
        [
            {
                "tick": tick,
                "total_rounds_played": 1,
                "kind": "Flash",
                "source_event": "flashbang_detonate",
                "entityid": tick,
                "user_steamid": pid,
                "user_team_num": 2,
            }
            for tick in [200, 210]
        ]
    )
    parser = Mock()
    parser.parse_event.return_value = shots
    extras = {}
    extract_replay_effects(parser, context.clock, utility, {"weapon_fire"}, {}, extras=extras)
    assert extras["utility_lifecycles"].throw_tick.isna().all()
    assert len(extras["throws"]) == 2


def _save(db, analysis, context):
    from tests.map_support import persist_fixture
    persist_fixture(db, analysis, context)
    rounds, evidence = build_foundations(analysis, context)
    payloads = {number: foundation_payload(rnd, evidence) for number, rnd in rounds.items()}
    key = foundation_key(analysis)
    db.save_stages(analysis.content_hash, {"foundations": (key, {
        "demo_id": analysis.content_hash, "cache_key": key, "round_numbers": sorted(rounds)}, payloads)})
    return payloads


def test_round_cache_roundtrip_no_parser_and_stable_evidence_ids(tmp_path, match_inputs):
    analysis, context = match_inputs
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(analysis)
    payloads = _save(db, analysis, context)
    with patch("src.demos.demo_analyzer.DemoParser", side_effect=AssertionError("parser called")):
        stored = db.get_stage_rounds(analysis.content_hash, "foundations", foundation_key(analysis), 1)
        assert stored == payloads
        foundation, evidence = decode_foundation(stored[1])
        match = load_tactical_match(db, analysis.content_hash)
    assert match.rounds[0].foundation == foundation
    assert all(match.evidence[eid] == event for eid, event in evidence.items())
    assert all(len(obs.player_id) == 17 for obs in foundation.equipment_start)
    assert db.get_stage_rounds(analysis.content_hash, "foundations", "stale-key", 1) == {}
    analysis.bomb_events_df.loc[0, "tick"] += 1
    assert db.get_stage_manifest(analysis.content_hash, "foundations", foundation_key(analysis)) is None


def test_atomic_failure_preserves_manifest_rounds_and_spatial_cache(tmp_path, match_inputs):
    analysis, context = match_inputs
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(analysis)
    before = _save(db, analysis, context)
    manifest = db.get_stage_manifest(analysis.content_hash, "foundations")
    spatial = db.get_stage_manifest(analysis.content_hash, "spatial")
    with db._connect() as conn:
        conn.execute("""CREATE TRIGGER fail_foundation BEFORE INSERT ON coach_stage_rounds WHEN NEW.stage = 'foundations'
                        BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        _save(db, analysis, context)
    assert db.get_stage_manifest(analysis.content_hash, "foundations") == manifest
    assert db.get_stage_rounds(analysis.content_hash, "foundations", foundation_key(analysis)) == before
    assert db.get_stage_manifest(analysis.content_hash, "spatial") == spatial


def test_additive_migration_keeps_players_and_delete_cascades(tmp_path, match_inputs):
    analysis, context = match_inputs
    path = str(tmp_path / "cache.db")
    db = Database(path)
    db.upsert_demo_analysis(analysis)
    pid = analysis.player_info.iloc[0].steamid
    db.track_player(pid)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE coach_stage_rounds")
        conn.execute("DROP TABLE coach_stage_manifests")
        conn.execute("PRAGMA user_version = 6")
    db = Database(path)
    assert len(db.list_demo_analyses()) == 0
    assert db.list_tracked_players()[0]["steamid"] == pid
    db.upsert_demo_analysis(analysis)
    _save(db, analysis, context)
    db.delete_demo_analysis(analysis.content_hash)
    assert db.get_stage_manifest(analysis.content_hash, "foundations") is None
    assert db.get_stage_rounds(analysis.content_hash, "foundations", foundation_key(analysis)) == {}


def test_unavailable_original_demo_requires_reimport_without_current_observations(tmp_path, match_inputs):
    analysis, context = match_inputs
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(analysis)
    manager = Mock()
    manager.analysis_path.return_value = None
    with pytest.raises(FileNotFoundError):
        get_mirage_context(db, manager, analysis)
    assert db.get_stage_manifest(analysis.content_hash, "observations") is None


def test_decode_rejects_invented_and_cross_round_references(match_inputs):
    analysis, context = match_inputs
    rounds, evidence = build_foundations(analysis, context)
    payload = foundation_payload(rounds[1], evidence)
    payload["foundation"]["contact_references"]["preparation_reference"]["evidence_ids"] = [
        "invented"
    ]
    with pytest.raises(ValueError, match="reference"):
        decode_foundation(payload)


def test_concurrent_preparation_extracts_once_and_reimport_invalidates(tmp_path, match_inputs):
    import time
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path

    analysis, context = match_inputs
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(analysis)
    manager = Mock()
    manager.analysis_path.return_value = Path("mirage.dem")

    def extract(*args):
        time.sleep(0.05)
        from tests.map_support import source_fixture
        return source_fixture(analysis, context)

    with patch("src.demos.spatial_service.extract_observations", side_effect=extract) as parse:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: get_mirage_context(db, manager, analysis), [0, 1]))
        assert len(results) == 2
        assert parse.call_count == 1
    assert db.get_stage_manifest(analysis.content_hash, "foundations", foundation_key(analysis)) is not None
    db.upsert_demo_analysis(analysis)
    assert db.get_stage_manifest(analysis.content_hash, "foundations") is None
    assert db.get_stage_rounds(analysis.content_hash, "foundations", foundation_key(analysis)) == {}
