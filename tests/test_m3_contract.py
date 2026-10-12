"""M3.1c contract invariants, before any round-summary detector runs."""

import json
from dataclasses import replace

import pytest

from src.models.tactical import (
    AliveState,
    Contact,
    Evidence,
    PlayerRound,
    PositionReference,
    RefragLink,
    RoundMoment,
    RoundTactics,
    Status,
    TacticalMatch,
    derived_id,
)


def example_match():
    evidence = {
        "s1": Evidence("s1", "states", 1, 19, 0.3, {"steamid": "a"}),
        "h1": Evidence("h1", "damage", 1, 20, 0.31, {"attacker_steamid": "a"}),
        "k1": Evidence("k1", "kills", 1, 30, 0.47, {
            "attacker_steamid": "a", "user_steamid": "b",
            "attacker_team_num": 2, "user_team_num": 3,
        }),
        "k2": Evidence("k2", "kills", 1, 40, 0.63, {
            "attacker_steamid": "c", "user_steamid": "a",
            "attacker_team_num": 3, "user_team_num": 2,
        }),
    }
    contact = Contact(
        derived_id(1, "contact", "h1"), 1, 20, "damage", "a", "b", "T", "CT",
        "ak47", 17, PositionReference(Status.OBSERVED, "s1", 19, 1, "mid"),
        PositionReference(Status.UNKNOWN), ["h1"], Status.OBSERVED,
    )
    state = AliveState(
        derived_id(1, "alive", "k1"), 1, 30, 5, 4,
        ["a", "c"], ["b"], ["k1"], Status.PARTIAL,
    )
    link = RefragLink(
        derived_id(1, "refrag", "k1", "k2"), 1, "k1", "k2", 10, 20,
        ["k1", "k2"], Status.OBSERVED,
    )
    moment = RoundMoment(
        derived_id(1, "moment", "h1"), 1, "first_contact", 20, 20,
        ["a", "b"], ["h1"], [contact.id], None, state.id, Status.OBSERVED,
    )
    rnd = RoundTactics(
        1, 0, 100, 10, {"T": "one", "CT": "two"}, "CT", "two", "t_killed", {},
        event_ids=list(evidence), players=[PlayerRound("a", "one", "T",
            first_contact_id=contact.id, contact_ids=[contact.id])],
        contacts=[contact], refrag_links=[link], alive_states=[state], moments=[moment],
    )
    return TacticalMatch("demo", "de_mirage", 2, [rnd], evidence, {})


def test_m3_contract_roundtrips_and_ids_are_stable():
    match = example_match()
    match.validate()
    payload = json.loads(json.dumps(match.to_dict(), allow_nan=False))
    assert TacticalMatch.from_dict(payload).to_dict() == payload
    assert derived_id(1, "refrag", "k2", "k1") == derived_id(1, "refrag", "k1", "k2")
    assert derived_id(2, "refrag", "k1", "k2") != derived_id(1, "refrag", "k1", "k2")


def test_m3_contract_rejects_future_or_cross_round_position():
    match = example_match()
    contact = match.rounds[0].contacts[0]
    contact.attacker_position.sample_tick = 21
    with pytest.raises(ValueError, match="position"):
        match.validate()
    contact.attacker_position.sample_tick = 19
    match.evidence["s1"] = replace(match.evidence["s1"], round_number=2)
    with pytest.raises(ValueError, match="round|position"):
        match.validate()


def test_m3_contract_rejects_invalid_derived_references():
    match = example_match()
    match.rounds[0].moments[0].contact_ids = ["missing"]
    with pytest.raises(ValueError, match="contact"):
        match.validate()
    match = example_match()
    match.rounds[0].players[0].first_contact_id = "missing"
    with pytest.raises(ValueError, match="contact"):
        match.validate()
    match = example_match()
    match.rounds[0].contacts[0].round_number = 2
    with pytest.raises(ValueError, match="another round"):
        match.validate()


def test_m3_contract_requires_strict_refrag_chronology_and_exact_killer():
    match = example_match()
    match.evidence["k2"] = replace(match.evidence["k2"], tick=30)
    with pytest.raises(ValueError, match="chronology"):
        match.validate()
    match = example_match()
    match.evidence["k2"].data["user_steamid"] = "other"
    with pytest.raises(ValueError, match="exact killer"):
        match.validate()
