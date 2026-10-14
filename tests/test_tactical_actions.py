"""M4 independent positive/negative examples, coverage, profile and cache invariants."""

import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from src.demos.round_alive import assign_opening, build_alive_states
from src.demos.round_contacts import assign_first_contacts, build_round_contacts
from src.demos.round_index import round_state_index
from src.demos.round_refrags import enrich_refrags
from src.demos.tactical_actions import action_payload, enrich_actions, restore_actions
from src.maps.registry import get_profile
from src.maps.resolver import resolve_region
from src.models.observations import DetectorConfig
from src.models.spatial import MapProfile, Region
from src.models.tactical import (
    Availability,
    Evidence,
    PlayerRound,
    RoundTactics,
    Status,
    TacticalMatch,
)

RATE = 10
POINTS = {
    "spawn": (0, 0),
    "aa": (400, 0),
    "sa": (900, 0),
    "bb": (400, 2000),
    "sb": (900, 2000),
    "ca": (950, 100),
    "cb": (950, 2100),
    "road": (1500, 1000),
}


def profile(rename=False):
    regions = [
        Region("spawn", "Spawn", ["spawn"], kind="spawn"),
        Region(
            "aa",
            "Approach alpha",
            ["aa"],
            kind="approach",
            route_names={"A": "Alpha"},
            defense_sector="A",
        ),
        Region("sa", "Site alpha", ["sa"], kind="site", site_id="A", defense_sector="A"),
        Region(
            "bb",
            "Approach beta",
            ["bb"],
            kind="approach",
            route_names={"B": "Beta"},
            defense_sector="B",
        ),
        Region("sb", "Site beta", ["sb"], kind="site", site_id="B", defense_sector="B"),
        Region("ca", "CT alpha", ["ca"], kind="connector", defense_sector="A"),
        Region("cb", "CT beta", ["cb"], kind="connector", defense_sector="B"),
        Region("road", "Road", ["road"], kind="connector", forward_sides=["CT"]),
    ]
    if rename:
        regions = [replace(r, id="renamed_" + r.id, name="Label " + r.name) for r in regions]
    return MapProfile("de_synthetic", "1", regions, capabilities=["regions", "site_boundaries"])


def event(eid, source, tick, **data):
    return Evidence(eid, source, 1, tick, tick / RATE, data)


def hurt(eid, tick, attacker="T0", victim="C0", amount=10, **extra):
    return event(
        eid,
        "damage",
        tick,
        attacker_steamid=attacker,
        user_steamid=victim,
        attacker_team_num=2 if attacker.startswith("T") else 3,
        user_team_num=2 if victim.startswith("T") else 3,
        weapon="ak47",
        enemy_damage=amount,
        **extra,
    )


def kill(eid, tick, attacker="T0", victim="C0"):
    return event(
        eid,
        "kills",
        tick,
        attacker_steamid=attacker,
        user_steamid=victim,
        attacker_team_num=2 if attacker.startswith("T") else 3,
        user_team_num=2 if victim.startswith("T") else 3,
        weapon="ak47",
    )


def build(paths=None, events=(), *, end=120, gaps=None, renamed=False, unknown_sources=()):
    paths, gaps = paths or {}, gaps or {}
    events = list(events)
    dead = {str(e.data["user_steamid"]): e.tick for e in events if e.source == "kills"}
    pids = [f"{side}{i}" for side in ("T", "C") for i in range(5)]
    for pid in pids:
        for tick in range(end + 1):
            if any(left < tick < right for left, right in gaps.get(pid, [])):
                continue
            area = paths[pid](tick) if pid in paths else ("spawn" if pid.startswith("T") else "ca")
            x, y = POINTS.get(area, (3000, 3000))
            events.append(
                event(
                    f"state-{pid}-{tick}",
                    "states",
                    tick,
                    steamid=pid,
                    team_num=2 if pid.startswith("T") else 3,
                    is_alive=tick < dead.get(pid, end + 1),
                    health=100 if tick < dead.get(pid, end + 1) else 0,
                    X=x,
                    Y=y,
                    Z=0,
                    last_place_name=area,
                    inventory=[],
                )
            )
    evidence = {e.id: e for e in sorted(events, key=lambda e: (e.tick, e.id))}
    record = RoundTactics(
        1,
        0,
        end,
        0,
        {"T": "team1", "CT": "team2"},
        "T",
        "team1",
        "ct_killed",
        {
            source: Availability(
                Status.UNKNOWN
                if source in unknown_sources
                else Status.OBSERVED
                if any(e.source == source for e in events)
                else Status.ABSENT
            )
            for source in (
                "states",
                "damage",
                "kills",
                "bombs",
                "throws",
                "utility_lifecycles",
                "blinds",
            )
        },
        event_ids=list(evidence),
        players=[PlayerRound(pid, None, "T" if pid.startswith("T") else "CT") for pid in pids],
        bomb_event_ids=[e.id for e in events if e.source == "bombs"],
    )
    p = profile(renamed)
    index = round_state_index(record, evidence)
    areas = {e.id: resolve_region(e.data, p) for e in events if e.source == "states"}
    config = DetectorConfig()
    record.contacts, record.contacts_status = build_round_contacts(
        record, evidence, tick_rate=RATE, config=config, areas=areas, state_index=index
    )
    assign_first_contacts(record, evidence)
    assign_opening(record, evidence)
    record.alive_states, record.alive_status = build_alive_states(
        record, evidence, tick_rate=RATE, config=config, state_index=index
    )
    enrich_refrags(record, evidence, tick_rate=RATE, response_seconds=5)
    enrich_actions(record, evidence, p, tick_rate=RATE, config=config, state_index=index)
    match = TacticalMatch("demo", p.map_name, 1, [record], evidence, {})
    match.validate()
    return record, evidence, p, index


def test_pobyt_transition_death_and_gap_do_not_invent_a_path():
    r, _, _, _ = build(
        {"T0": lambda t: "aa" if t < 20 else "sa"},
        [kill("death", 25, "C0", "T0")],
        gaps={"T1": [(10, 60)]},
    )
    stays = [s for s in r.region_stays if s.player_id == "T0"]
    assert [(s.area, s.start_tick, s.end_tick, s.end_reason) for s in stays] == [
        ("aa", 0, 19, "transition"),
        ("sa", 20, 25, "death"),
    ]
    (tr,) = [tr for tr in r.region_transitions if tr.player_id == "T0"]
    assert (tr.departure_tick, tr.arrival_tick) == (19, 20)
    assert not [tr for tr in r.region_transitions if tr.player_id == "T1"]
    assert r.movement_status == Status.PARTIAL


def test_unknown_region_and_missing_profile_do_not_prove_movement():
    r, e, p, index = build({"T0": lambda t: "aa" if t < 20 else "unknown" if t < 40 else "sa"})
    assert not [tr for tr in r.region_transitions if tr.player_id == "T0"]
    assert any(s.area is None for s in r.region_stays)
    enrich_actions(r, e, None, tick_rate=RATE, config=DetectorConfig(), state_index=index)
    assert r.movement_status == r.attacks_status == Status.UNKNOWN


def test_profiles_have_unique_sectors_and_forward_geometry_is_semantic():
    p = get_profile("de_inferno")
    banana = p.regions_by_id["banana"]
    assert banana.is_forward("CT", {"X": 500, "Y": 1500, "Z": 140})
    assert not banana.is_forward("CT", {"X": 500, "Y": 2100, "Z": 140})
    assert not p.regions_by_id["top_mid"].is_forward("CT", {})
    assert p.regions_by_id["ct_spawn"].defense_sector is None
    changed = replace(
        p, regions=[replace(r, defense_sector=None) if r.id == "banana" else r for r in p.regions]
    )
    assert changed.semantic_fingerprint != p.semantic_fingerprint
    relabelled = replace(p, regions=[replace(r, name="Renamed") for r in p.regions])
    assert relabelled.semantic_fingerprint == p.semantic_fingerprint


def test_unique_utility_links_source_effect_and_observed_expiry():
    events = [
        event("throw", "throws", 10, user_steamid="T0", user_team_num=2, kind="HE"),
        event(
            "effect",
            "utility_lifecycles",
            15,
            user_steamid="T0",
            user_team_num=2,
            kind="HE",
            last_place_name="aa",
            end_tick=15,
            end_source="instant_effect",
        ),
        event(
            "damage",
            "damage",
            15,
            attacker_steamid="T0",
            user_steamid="C0",
            attacker_team_num=2,
            user_team_num=3,
            weapon="hegrenade",
            enemy_damage=20,
        ),
    ]
    r, _, _, _ = build(events=events)
    (u,) = r.utility_contexts
    assert (u.throw_tick, u.origin_area, u.effect_tick, u.effect_area, u.end_tick) == (
        10,
        "spawn",
        15,
        "aa",
        15,
    )
    assert u.match_status == "unique_temporal_limited"
    assert u.effect_ids == ["damage"]


def test_ambiguous_flashes_and_estimated_smoke_end_stay_unknown():
    events = [
        event(f"throw{i}", "throws", i, user_steamid="T0", user_team_num=2, kind="Flash")
        for i in (10, 12)
    ]
    events += [
        event("effect", "utility_lifecycles", 15, user_steamid="T0", user_team_num=2, kind="Flash"),
        event(
            "smoke",
            "utility_lifecycles",
            20,
            user_steamid="T1",
            user_team_num=2,
            kind="Smoke",
            end_tick=100,
            end_source="estimated_22s",
        ),
    ]
    r, _, _, _ = build(events=events)
    flash = next(u for u in r.utility_contexts if u.effect_tick == 15)
    assert flash.match_status == "ambiguous" and flash.throw_tick is None
    assert next(u for u in r.utility_contexts if u.kind == "Smoke").end_tick is None


def test_parallel_and_repeated_fights_and_damage_without_kill_are_preserved():
    paths = {"T0": lambda t: "aa", "C0": lambda t: "ca", "T1": lambda t: "bb", "C1": lambda t: "cb"}
    r, _, _, _ = build(paths, [hurt("a", 20), hurt("b", 21, "T1", "C1"), hurt("repeat", 90)])
    assert len(r.fights) == 3
    assert sorted(f.after["damage_by_side"]["T"] for f in r.fights) == [10, 10, 10]
    assert all(not f.kill_ids for f in r.fights)
    assert {ref for f in r.fights for ref in f.contact_ids} == {c.id for c in r.contacts}


def test_long_distance_exchange_between_same_opponents_is_one_fight():
    paths = {"T0": lambda t: "spawn", "C0": lambda t: "cb"}
    r, _, _, _ = build(paths, [hurt("a", 20), hurt("reply", 21, "C0", "T0")])
    assert len(r.fights) == 1
    assert r.fights[0].after["damage_by_side"] == {"T": 10, "CT": 10}


def test_simultaneous_local_opening_ties_and_refrags_use_exact_killer():
    r, _, _, _ = build(
        {"T0": lambda t: "aa", "T1": lambda t: "aa"},
        [kill("k1", 20), kill("k2", 20, "T1", "C1"), kill("reply", 25, "C2", "T0")],
    )
    (f,) = r.fights
    assert set(f.opening_kill_ids) == {"k1", "k2"}
    assert f.opening_kill_id is None
    assert any(
        link["death_id"] == "k1" and link["response_kill_id"] == "reply" for link in f.refrags
    )
    assert f.after["deaths_by_side"] == {"T": 1, "CT": 2}


def test_single_utility_or_passive_approach_does_not_become_attack():
    paths = {pid: lambda t: "aa" for pid in ("T0", "T1", "T2")}
    r, _, _, _ = build(
        paths, [event("throw", "throws", 10, user_steamid="T0", user_team_num=2, kind="Smoke")]
    )
    assert not r.attacks and r.t_pressure


def test_posthumous_kill_is_not_a_teammate_refrag():
    r, _, _, _ = build(events=[kill("death", 20, "T0", "C0"), kill("posthumous", 25, "C0", "T0")])
    assert not r.refrag_links


def test_attack_can_be_stopped_before_site_without_kill_or_plant():
    paths = {pid: lambda t: "aa" if t < 40 else "spawn" for pid in ("T0", "T1")}
    r, _, _, _ = build(paths, [hurt("contact", 20)])
    (a,) = r.attacks
    assert a.target_site == "A" and a.outcome == "withdrawn"
    assert a.entry_ids == [] and a.plant_id is None
    assert a.entry_outcome == "not_observed"


def test_short_reentry_and_change_of_target_are_separate_attempts():
    r, _, _, _ = build({"T0": lambda t: "sa" if 20 <= t <= 22 else "sb" if t >= 80 else "spawn"})
    assert [a.target_site for a in r.attacks] == ["A", "B"]
    assert r.attacks[0].first_entry_tick == 20
    assert r.attacks[1].previous_attack_id == r.attacks[0].episode.id


def test_a_detached_player_left_behind_does_not_keep_the_original_group_attack_open():
    paths = {pid: lambda t: "aa" if t < 40 else "spawn" if t < 80 else "sb" for pid in ("T0", "T1")}
    paths["T2"] = lambda t: "aa"
    r, _, _, _ = build(paths, [hurt("contact", 20)])
    a, b = r.attacks
    assert a.target_site == "A" and a.end_reason == "withdrawn"
    assert a.episode.end_tick < b.episode.start_tick
    assert b.target_site == "B" and "T2" in b.detached_players


def test_detached_player_has_actions_and_joining_without_lurk_label():
    paths = {
        "T0": lambda t: "sa" if t >= 20 else "aa",
        "T1": lambda t: "sa" if t >= 20 else "aa",
        "T2": lambda t: "spawn" if t < 70 else "sa",
    }
    r, _, _, _ = build(paths, [hurt("detached-contact", 40, "T2", "C0")])
    a = r.attacks[0]
    action = next(d for d in a.detached_actions if d["player_id"] == "T2")
    assert action["intervals"][0]["contact_ids"]
    assert action["joined_tick"] == 70
    assert "lurk" not in json.dumps(action)


def test_rotation_delay_arrival_and_no_arrival_have_coverage():
    paths = {
        "T0": lambda t: "aa",
        "T1": lambda t: "aa",
        "C0": lambda t: "cb" if t < 40 else "road" if t < 50 else "ca",
        "C1": lambda t: "cb",
    }
    r, _, _, _ = build(paths, [hurt("contact", 20)])
    arrived = next(rot for rot in r.rotations if rot.player_id == "C0")
    assert (arrived.outcome, arrived.arrival_tick) == ("arrived", 50)
    assert arrived.reaction_seconds == 1.9 and arrived.travel_seconds == 1.1
    assert (
        next(rot for rot in r.rotations if rot.player_id == "C1").outcome == "no_observed_arrival"
    )


def test_rotation_gap_does_not_report_no_reaction_or_zero_delay():
    paths = {"T0": lambda t: "aa", "T1": lambda t: "aa", "C0": lambda t: "cb"}
    r, _, _, _ = build(paths, [hurt("contact", 20)], gaps={"C0": [(30, 70)]})
    rot = next(rot for rot in r.rotations if rot.player_id == "C0")
    assert rot.outcome == "unknown" and rot.reaction_seconds is None
    assert (
        next(item for item in r.rotation_eligibility if item["player_id"] == "C0")["status"]
        == "eligible"
    )


def test_resources_never_bridge_a_position_gap_or_use_future_hp():
    r, _, _, _ = build(events=[hurt("contact", 20)], gaps={"C0": [(10, 70)]})
    before = r.fights[0].before["players"]["C0"]
    assert before["hp"] is None
    assert before["sample_status"] == "gap"


def test_movement_started_before_named_contact_is_not_a_positive_reaction_delay():
    paths = {
        "T0": lambda t: "aa",
        "T1": lambda t: "aa",
        "C0": lambda t: "cb" if t < 40 else "road" if t < 60 else "ca",
    }
    r, _, _, _ = build(paths, [hurt("contact", 45)])
    rotation = next(rot for rot in r.rotations if rot.player_id == "C0")
    assert rotation.already_moving and rotation.reaction_seconds < 0
    assert rotation.outcome == "arrived"


def test_retake_requires_observed_action_and_plant_is_not_an_attempt():
    plant = event("plant", "bombs", 50, event="bomb_planted", user_steamid="T0", site="A")
    paths = {"T0": lambda t: "sa", "C0": lambda t: "cb" if t < 80 else "sa"}
    r, _, _, _ = build(paths, [plant])
    assert r.retake.episode and r.retake.outcome == "lost"
    assert r.retake.episode.start_tick == 80
    no_attempt, _, _, _ = build({"T0": lambda t: "sa"}, [plant])
    assert no_attempt.retake.outcome == "no_attempt"
    assert no_attempt.retake.episode is None


def test_map_agnostic_actions_and_cache_roundtrip_avoid_detector_work():
    paths = {"T0": lambda t: "aa", "T1": lambda t: "aa"}
    r, evidence, p, index = build(paths, [hurt("contact", 20)])
    renamed, _, _, _ = build(paths, [hurt("contact", 20)], renamed=True)
    assert [(a.target_site, a.start_seconds, a.outcome) for a in r.attacks] == [
        (a.target_site, a.start_seconds, a.outcome) for a in renamed.attacks
    ]
    payload = json.loads(json.dumps(action_payload(r), allow_nan=False))
    assert "event_ids" not in payload["result"]
    with patch(
        "src.demos.tactical_actions.enrich_movement", side_effect=AssertionError("recomputed")
    ):
        enrich_actions(
            r,
            evidence,
            p,
            tick_rate=RATE,
            config=DetectorConfig(),
            state_index=index,
            cached=payload,
        )
    assert action_payload(r) == payload
    payload["round_number"] = 2
    with pytest.raises(ValueError):
        restore_actions(r, payload)


def test_sqlite_action_cache_merges_rounds_and_invalidates_semantic_changes(tmp_path):
    from src.demos.tactical_actions import actions_key, save_action_rounds
    from src.models.models import DemoAnalysis
    from src.storage.database import Database

    db = Database(str(tmp_path / "actions.db"))
    analysis = DemoAnalysis("test.dem", map_name="de_synthetic", content_hash="demo")
    db.upsert_demo_analysis(analysis)
    r, _, p, _ = build()
    key = actions_key(analysis, p)
    save_action_rounds(db, "demo", key, [r])
    second = replace(r, number=2)
    save_action_rounds(db, "demo", key, [second])
    assert set(db.get_stage_rounds("demo", "tactical_actions", key)) == {1, 2}
    assert set(db.get_stage_rounds("demo", "tactical_actions", key, 1)) == {1}
    changed = replace(p, regions=[replace(reg, defense_sector=None) for reg in p.regions])
    assert actions_key(analysis, changed) != key
    assert not db.get_stage_rounds("demo", "tactical_actions", actions_key(analysis, changed))
