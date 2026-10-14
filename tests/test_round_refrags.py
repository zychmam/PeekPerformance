"""M3.3b: exact-killer reply windows, source quality and opening response."""

from src.demos.round_refrags import enrich_refrags
from src.demos.round_summary import player_summary, team_summary
from src.models.tactical import Availability, Evidence, PlayerRound, RoundTactics, Status, TacticalMatch


def _fixture(end=1000, source=Status.OBSERVED):
    players = [PlayerRound(f"t{i}", "t", "T") for i in range(5)] + [
        PlayerRound(f"c{i}", "ct", "CT") for i in range(5)
    ]
    record = RoundTactics(1, 0, end, 0, {"T": "t", "CT": "ct"}, None, None, None,
                          {"kills": Availability(source)}, players=players)
    return record, {}


def _kill(record, evidence, eid, tick, attacker, victim):
    a_side = 2 if attacker.startswith("t") else 3
    v_side = 2 if victim.startswith("t") else 3
    evidence[eid] = Evidence(eid, "kills", 1, tick, tick / 64,
                             {"attacker_steamid": attacker, "user_steamid": victim,
                              "attacker_team_num": a_side, "user_team_num": v_side})
    record.event_ids.append(eid)


def _run(record, evidence, seconds=5):
    enrich_refrags(record, evidence, tick_rate=64, response_seconds=seconds)
    TacticalMatch("demo", "de_unknown", 1, [record], evidence, {}).validate()


def test_exact_killer_and_strict_window_including_five_seconds():
    record, evidence = _fixture(end=900)
    _kill(record, evidence, "opening", 100, "c0", "t0")
    _kill(record, evidence, "not_killer", 150, "t2", "c1")
    _kill(record, evidence, "boundary", 420, "t3", "c0")
    record.opening_kill_ids = ["opening"]
    record.opening_status = Status.OBSERVED
    _run(record, evidence)
    assert [(link.death_id, link.response_kill_id, link.delay_ticks)
            for link in record.refrag_links] == [("opening", "boundary", 320)]
    assert record.opening_window_end_tick == 420
    assert record.opening_window_kill_ids == ["not_killer", "boundary"]
    assert record.opening_response_status == Status.OBSERVED
    summary = team_summary(record, evidence, {}, None, 64)
    response = next(item for item in summary if item.title == "Odpowiedź po openingu")
    assert "zabijając jego zabójcę po 5.0 s" in response.text
    assert set(response.evidence_ids) == {"opening", "not_killer", "boundary"}
    player = player_summary(record, evidence, "t0", {}, None, 64)
    assert any("Jego śmierć wymienił" in item.text for item in player)


def test_one_response_can_refrag_several_deaths_but_duplicate_death_does_not():
    record, evidence = _fixture()
    _kill(record, evidence, "d1", 100, "c0", "t0")
    _kill(record, evidence, "duplicate", 100, "c0", "t0")
    _kill(record, evidence, "d2", 105, "c0", "t1")
    _kill(record, evidence, "reply", 110, "t2", "c0")
    _run(record, evidence)
    assert [(link.death_id, link.response_kill_id) for link in record.refrag_links] == [
        ("d1", "reply"), ("d2", "reply")
    ]


def test_end_of_round_and_unavailable_source_do_not_create_false_absence():
    record, evidence = _fixture(end=150)
    _kill(record, evidence, "d", 100, "c0", "t0")
    _kill(record, evidence, "same", 100, "t1", "c0")
    _run(record, evidence)
    assert record.refrag_links == []
    assert record.refrags_status == Status.ABSENT
    record.availability["kills"] = Availability(Status.UNKNOWN)
    _run(record, evidence)
    assert record.refrags_status == Status.UNKNOWN
    record.availability["kills"] = Availability(Status.PARTIAL)
    _run(record, evidence)
    assert record.refrags_status == Status.PARTIAL

    record, evidence = _fixture(end=150)
    _kill(record, evidence, "death", 100, "c0", "t0")
    _kill(record, evidence, "on_end", 150, "t1", "c0")
    _run(record, evidence)
    assert [(link.response_kill_id, link.observable_window_ticks)
            for link in record.refrag_links] == [("on_end", 50)]


def test_duplicate_or_wrong_side_response_is_not_refrag():
    record, evidence = _fixture()
    _kill(record, evidence, "opening", 100, "c0", "t0")
    _kill(record, evidence, "other", 150, "t1", "c1")
    _kill(record, evidence, "too_late", 421, "t2", "c0")
    _run(record, evidence)
    assert record.refrag_links == []


def test_incomplete_roster_cannot_verify_absence_of_refrag():
    record, evidence = _fixture()
    record.players = [player for player in record.players if player.player_id != "t4"]
    _kill(record, evidence, "opening", 100, "c0", "t0")
    record.opening_kill_ids = ["opening"]
    record.opening_status = Status.OBSERVED
    _run(record, evidence)
    assert record.refrags_status == Status.PARTIAL
    assert record.opening_response_status == Status.PARTIAL
