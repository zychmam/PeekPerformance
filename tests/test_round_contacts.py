"""M3.2a: contact normalization and position provenance."""

import json
from pathlib import Path

import pandas as pd

from src.demos.round_contacts import assign_first_contacts, build_round_contacts
from src.demos.round_alive import assign_opening
from src.demos.tactical_rounds import build_tactical_match
from src.models.models import DemoAnalysis
from src.models.observations import DetectorConfig
from src.models.tactical import Availability, Evidence, PlayerRound, RoundTactics, Status, TacticalMatch
from tests.map_support import MirageContext


def _round(events, *, freeze=0, availability=Status.OBSERVED):
    evidence = {event.id: event for event in events}
    rnd = RoundTactics(
        1, 0, 300, freeze, {"T": "one", "CT": "two"}, None, None, None,
        {"damage": Availability(availability), "kills": Availability(availability)},
        event_ids=list(evidence),
    )
    return rnd, evidence


def _event(eid, source, tick, **data):
    return Evidence(eid, source, 1, tick, tick / 64, data)


def _hurt(eid, tick, attacker="a", victim="b", amount=10, a_team=2, v_team=3):
    return _event(eid, "damage", tick, attacker_steamid=attacker,
                  user_steamid=victim, attacker_team_num=a_team,
                  user_team_num=v_team, enemy_damage=amount, weapon="ak47")


def _kill(eid, tick, attacker="a", victim="b", a_team=2, v_team=3):
    return _event(eid, "kills", tick, attacker_steamid=attacker,
                  user_steamid=victim, attacker_team_num=a_team,
                  user_team_num=v_team, weapon="ak47")


def test_damage_and_same_tick_kill_share_one_contact_without_double_hp():
    events = [
        _event("sa", "states", 19, steamid="a", X=1, Y=2, Z=3),
        _event("sb", "states", 18, steamid="b", X=4, Y=5, Z=6),
        _hurt("h1", 20, amount=7), _hurt("h2", 20, amount=10),
        _kill("k1", 20), _kill("k2", 30, attacker="c", victim="d"),
        _hurt("friend", 25, attacker="a", victim="c", a_team=2, v_team=2),
        _hurt("zero", 26, amount=0),
    ]
    rnd, evidence = _round(events)
    contacts, status = build_round_contacts(rnd, evidence, tick_rate=64,
                                            config=DetectorConfig(), areas={"sa": "mid"})
    assert status == Status.OBSERVED
    assert [(c.tick, c.kind, c.actual_damage) for c in contacts] == [
        (20, "damage", 17), (30, "kill_only", None),
    ]
    assert contacts[0].evidence_ids == ["h1", "h2", "k1"]
    assert contacts[0].attacker_position.evidence_id == "sa"
    assert contacts[0].attacker_position.age_ticks == 1
    assert contacts[0].attacker_position.area == "mid"
    assert contacts[0].victim_position.evidence_id == "sb"
    assert contacts[1].attacker_position.status == Status.UNKNOWN
    rnd.contacts, rnd.contacts_status = contacts, status
    TacticalMatch("demo", "de_unknown", 2, [rnd], evidence, {}).validate()
    assert [c.id for c in build_round_contacts(rnd, evidence, tick_rate=64,
               config=DetectorConfig())[0]] == [c.id for c in contacts]


def test_position_never_uses_future_or_coverage_gap_and_works_without_map():
    events = [
        _event("old", "states", 10, steamid="a", X=1),
        _event("future", "states", 200, steamid="a", X=2),
        _hurt("h1", 50), _hurt("h2", 100),
    ]
    rnd, evidence = _round(events)
    contacts, _ = build_round_contacts(rnd, evidence, tick_rate=64,
                                       config=DetectorConfig())
    assert len(contacts) == 2
    assert all(c.attacker_position.status == Status.UNKNOWN for c in contacts)
    assert all(c.attacker_position.evidence_id is None for c in contacts)
    assert all(c.attacker_position.sample_tick == 10 for c in contacts)
    assert all(c.attacker_position.area is None for c in contacts)


def test_empty_or_pre_freeze_sources_do_not_claim_verified_absence():
    rnd, evidence = _round([_hurt("h", 20)], freeze=30, availability=Status.UNKNOWN)
    assert build_round_contacts(rnd, evidence, tick_rate=64,
                                config=DetectorConfig()) == ([], Status.UNKNOWN)


def test_complete_sources_include_verified_empty_and_filtered_enemy_contacts():
    for source, event in (("damage", _hurt("h", 20)), ("kills", _kill("k", 20))):
        rnd, evidence = _round([event], availability=Status.ABSENT)
        rnd.availability[source] = Availability(Status.OBSERVED)
        contacts, status = build_round_contacts(rnd, evidence, tick_rate=64, config=DetectorConfig())
        assert len(contacts) == 1 and status == Status.OBSERVED
        rnd.availability["kills" if source == "damage" else "damage"] = Availability(Status.UNKNOWN)
        assert build_round_contacts(rnd, evidence, tick_rate=64, config=DetectorConfig())[1] == Status.PARTIAL
    rnd, evidence = _round([_hurt("friendly", 20, a_team=2, v_team=2)])
    assert build_round_contacts(rnd, evidence, tick_rate=64, config=DetectorConfig()) == ([], Status.ABSENT)


def test_first_contacts_separate_utility_firearm_and_player_roles():
    he = _hurt("he", 20, attacker="a", victim="b", amount=8)
    he.data["weapon"] = "hegrenade"
    events = [he, _hurt("gun", 30, attacker="b", victim="a", amount=17,
                              a_team=3, v_team=2), _kill("kill", 30, attacker="b",
                              victim="a", a_team=3, v_team=2)]
    rnd, evidence = _round(events)
    rnd.players = [PlayerRound("a", "one", "T"), PlayerRound("b", "two", "CT")]
    rnd.contacts, rnd.contacts_status = build_round_contacts(
        rnd, evidence, tick_rate=64, config=DetectorConfig())
    assign_first_contacts(rnd, evidence)
    assert [rnd.contacts[0].modality, rnd.contacts[1].modality] == ["utility", "firearm"]
    assert rnd.contact_references["first_enemy_damage"] == [rnd.contacts[0].id]
    assert rnd.contact_references["first_utility_damage"] == [rnd.contacts[0].id]
    assert rnd.contact_references["first_firearm_damage"] == [rnd.contacts[1].id]
    assert rnd.contact_references["first_enemy_kill"] == [rnd.contacts[1].id]
    a, b = rnd.players
    assert a.contact_references["first_dealt"] == [rnd.contacts[0].id]
    assert a.contact_references["first_received"] == [rnd.contacts[1].id]
    assert b.contact_references["first_received"] == [rnd.contacts[0].id]
    assert b.contact_references["first_dealt"] == [rnd.contacts[1].id]
    assert a.first_contact_id == b.first_contact_id == rnd.contacts[0].id
    TacticalMatch("demo", "de_unknown", 2, [rnd], evidence, {}).validate()


def test_same_tick_first_contacts_keep_all_ties():
    events = [_hurt("one", 20, attacker="a", victim="b"),
              _hurt("two", 20, attacker="a", victim="c")]
    rnd, evidence = _round(events)
    rnd.players = [PlayerRound("a", "one", "T")]
    rnd.contacts, rnd.contacts_status = build_round_contacts(
        rnd, evidence, tick_rate=64, config=DetectorConfig())
    assign_first_contacts(rnd, evidence)
    assert len(rnd.contact_references["first_enemy_damage"]) == 2
    assert len(rnd.players[0].contact_references["first_any"]) == 2
    assert rnd.players[0].first_contact_id is None


def test_simultaneous_enemy_openings_keep_both_kill_sources():
    events = [_kill("one", 20, attacker="a", victim="b"),
              _kill("two", 20, attacker="c", victim="d")]
    rnd, evidence = _round(events)
    rnd.contacts, rnd.contacts_status = build_round_contacts(
        rnd, evidence, tick_rate=64, config=DetectorConfig())
    assign_first_contacts(rnd, evidence)
    assign_opening(rnd, evidence)
    assert rnd.opening_status == Status.OBSERVED
    assert rnd.opening_kill_ids == ["one", "two"]


def test_reviewed_mirage_contacts_match_raw_reference_ticks():
    data = json.loads((Path(__file__).parent / "reference" / "mirage_tactical_facts.json")
                      .read_text(encoding="utf-8"))
    analysis = DemoAnalysis(
        file_name="mirage.dem", content_hash=data["provenance"]["demo_hash"],
        map_name="de_mirage", analysis_version=data["analysis_version"],
        **{key: pd.DataFrame(rows) for key, rows in data["frames"].items()},
    )
    match = build_tactical_match(analysis, MirageContext.from_json(json.dumps(data["spatial"])))
    expected = {1: (7556, 7802), 6: (32783, 33055),
                13: (71380, 71380), 20: (105746, 105780)}
    for number, (damage_tick, opening_tick) in expected.items():
        rnd = next(r for r in match.rounds if r.number == number)
        assert min(c.tick for c in rnd.contacts if c.kind == "damage") == damage_tick
        assert any(c.tick == opening_tick and any(
            match.evidence[eid].source == "kills" for eid in c.evidence_ids
        ) for c in rnd.contacts)
        assert {match.evidence[eid].tick for eid in rnd.opening_kill_ids} == {opening_tick}
        assert all(
            c.attacker_position.sample_tick is None or c.attacker_position.sample_tick < c.tick
            for c in rnd.contacts
        )
        if rnd.foundation:
            for new_key, old_key in (
                ("first_enemy_damage", "first_enemy_damage"),
                ("first_firearm_damage", "first_firearm_damage"),
                ("first_enemy_kill", "first_enemy_kill"),
            ):
                ids = rnd.contact_references[new_key]
                old_tick = rnd.foundation.contact_references[old_key].tick
                if ids and old_tick is not None:
                    assert {c.tick for c in rnd.contacts if c.id in ids} == {old_tick}
    assert match.rounds[0].fights_status == Status.OBSERVED
    assert {ref for fight in match.rounds[0].fights for ref in fight.contact_ids} == {
        contact.id for contact in match.rounds[0].contacts}
