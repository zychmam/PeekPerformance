"""M3.3a: global alive count with complete and incomplete evidence."""

from src.demos.round_alive import build_alive_states
from src.models.observations import DetectorConfig
from src.models.tactical import Availability, Evidence, PlayerRound, RoundTactics, Status, TacticalMatch


def _fixture(*, omit=None, ct_count=5):
    players = [PlayerRound(f"t{i}", "one", "T") for i in range(5)] + [
        PlayerRound(f"c{i}", "two", "CT") for i in range(ct_count)
    ]
    events = {}
    for player in players:
        if player.player_id == omit:
            continue
        events[f"s-{player.player_id}"] = Evidence(
            f"s-{player.player_id}", "states", 1, 100, 0,
            {"steamid": player.player_id, "team_num": 2 if player.side == "T" else 3,
             "is_alive": True},
        )
    rnd = RoundTactics(
        1, 0, 300, 100, {"T": "one", "CT": "two"}, None, None, None,
        {"states": Availability(Status.OBSERVED), "kills": Availability(Status.OBSERVED)},
        event_ids=list(events), players=players,
    )
    return rnd, events


def _death(events, rnd, eid, tick, victim, side, attacker=None):
    events[eid] = Evidence(eid, "kills", 1, tick, (tick - 100) / 64,
                           {"user_steamid": victim, "user_team_num": side,
                            "attacker_steamid": attacker})
    rnd.event_ids.append(eid)


def _build(rnd, events):
    result = build_alive_states(rnd, events, tick_rate=64, config=DetectorConfig())
    rnd.alive_states, rnd.alive_status = result
    TacticalMatch("demo", "de_unknown", 2, [rnd], events, {}).validate()
    return result


def test_teamkill_suicide_duplicate_and_same_tick_deaths_update_once():
    rnd, events = _fixture()
    _death(events, rnd, "teamkill", 120, "t0", 2, "t1")
    _death(events, rnd, "duplicate", 120, "t0", 2, "t1")
    _death(events, rnd, "ct", 130, "c0", 3, "t2")
    _death(events, rnd, "t", 130, "t2", 2, "c1")
    _death(events, rnd, "suicide", 140, "c1", 3, "c1")
    states, status = _build(rnd, events)
    assert status == Status.OBSERVED
    assert [(s.tick, s.t_alive, s.ct_alive) for s in states] == [
        (100, 5, 5), (120, 4, 5), (130, 3, 4), (140, 3, 3),
    ]
    assert len([s for s in states if s.tick == 130]) == 1
    assert "t0" in states[-1].dead_ids
    assert states[-1].evidence_ids[-1] == "suicide"


def test_incomplete_roster_or_baseline_never_becomes_five_vs_five():
    for rnd, events in (_fixture(ct_count=4), _fixture(omit="c0")):
        states, status = _build(rnd, events)
        assert status == Status.PARTIAL
        assert states[0].t_alive == 5
        assert states[0].ct_alive is None
    rnd, events = _fixture(omit="t0")
    events["future"] = Evidence("future", "states", 1, 105, 5/64,
                                 {"steamid": "t0", "team_num": 2, "is_alive": True})
    rnd.event_ids.append("future")
    states, _ = _build(rnd, events)
    assert states[0].t_alive is None


def test_contradictory_snapshot_degrades_only_affected_side():
    rnd, events = _fixture()
    events["unexpected-dead"] = Evidence(
        "unexpected-dead", "states", 1, 110, 10/64,
        {"steamid": "c0", "team_num": 3, "is_alive": False},
    )
    rnd.event_ids.append("unexpected-dead")
    _death(events, rnd, "kill", 120, "t0", 2, "c1")
    states, status = _build(rnd, events)
    assert status == Status.PARTIAL
    assert [(s.tick, s.t_alive, s.ct_alive) for s in states] == [
        (100, 5, 5), (110, 5, None), (120, 4, None),
    ]


def test_later_duplicate_death_makes_side_unknown_without_second_decrement():
    rnd, events = _fixture()
    _death(events, rnd, "first", 120, "t0", 2)
    _death(events, rnd, "later", 130, "t0", 2)
    states, status = _build(rnd, events)
    assert status == Status.PARTIAL
    assert [(s.t_alive, s.ct_alive) for s in states] == [(5, 5), (4, 5), (None, 5)]


def test_missing_kill_stream_does_not_verify_full_round_survival():
    rnd, events = _fixture()
    rnd.availability["kills"] = Availability(Status.UNKNOWN)
    states, status = _build(rnd, events)
    assert states[0].t_alive == states[0].ct_alive == 5
    assert status == Status.PARTIAL
