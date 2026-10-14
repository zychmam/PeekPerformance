"""M3.4a chronology retains source identity and same-tick uncertainty."""

from src.demos.round_moments import build_round_moments
from src.models.tactical import (
    AliveState, Contact, Episode, Evidence, PlayerRound, PositionReference,
    RoundTactics, Status, TacticalMatch, derived_id,
)


def test_chronology_orders_sources_groups_equal_ticks_and_retains_interval():
    events = {
        "throw": Evidence("throw", "throws", 1, 5, 0.08,
                          {"kind": "Smoke", "user_steamid": "t0"}),
        "damage": Evidence("damage", "damage", 1, 10, 0.16, {}),
        "kill": Evidence("kill", "kills", 1, 10, 0.16,
                         {"attacker_steamid": "t0", "user_steamid": "c0"}),
        "entry_a": Evidence("entry_a", "states", 1, 18, 0.28, {"steamid": "t0"}),
        "entry_b": Evidence("entry_b", "states", 1, 21, 0.33, {"steamid": "t0"}),
        "teamkill": Evidence("teamkill", "kills", 1, 25, 0.39,
                             {"attacker_steamid": "t1", "user_steamid": "t2"}),
        "plant": Evidence("plant", "bombs", 1, 30, 0.47, {"event": "bomb_planted"}),
    }
    contact = Contact("contact", 1, 10, "damage", "t0", "c0", "T", "CT",
                      evidence_ids=["damage", "kill"], status=Status.OBSERVED)
    alive = AliveState(derived_id(1, "alive", "teamkill"), 1, 25, 4, 4,
                       evidence_ids=["teamkill"], status=Status.PARTIAL)
    record = RoundTactics(1, 0, 40, 0, {}, "T", None, "bomb_planted", {},
                          event_ids=list(events),
                          players=[PlayerRound("t0", None, "T")],
                          contacts=[contact], opening_kill_ids=["kill"],
                          observed_entries=[Episode("entry", "site_entry", 18, 21,
                                                    ["t0"], ["entry_a", "entry_b"],
                                                    status=Status.OBSERVED, area="A")],
                          bomb_event_ids=["plant"], alive_states=[alive])
    record.t_preparation.thrown_utility_ids = ["throw"]
    record.moments = build_round_moments(record, events)
    TacticalMatch("demo", "de_mirage", 1, [record], events, {}).validate()
    assert [moment.start_tick for moment in record.moments] == sorted(
        moment.start_tick for moment in record.moments
    )
    assert record.moments[0].kind == "round_start"
    opening = next(moment for moment in record.moments if moment.kind == "opening")
    assert (opening.start_tick, opening.event_ids, opening.contact_ids) == (
        10, ["damage", "kill"], ["contact"]
    )
    assert not any(moment.kind == "first_contact" and moment.start_tick == 10
                   for moment in record.moments)
    entry = next(moment for moment in record.moments if moment.kind == "site_entry")
    assert (entry.start_tick, entry.end_tick) == (18, 21)
    assert next(moment for moment in record.moments if moment.kind == "alive_change").event_ids == ["teamkill"]
    assert record.moments[-1].kind == "round_end"


def test_moment_ids_are_stable_under_event_order():
    record = RoundTactics(1, 0, 30, 0, {}, None, None, None, {},
                          bomb_event_ids=["b", "a"])
    evidence = {
        "a": Evidence("a", "bombs", 1, 10, 0.1, {"event": "bomb_pickup"}),
        "b": Evidence("b", "bombs", 1, 10, 0.1, {"event": "bomb_dropped"}),
    }
    first = build_round_moments(record, evidence)
    record.bomb_event_ids.reverse()
    second = build_round_moments(record, evidence)
    assert [(item.id, item.kind, item.start_tick) for item in first] == [
        (item.id, item.kind, item.start_tick) for item in second
    ]
