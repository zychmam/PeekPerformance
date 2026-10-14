"""Round narration stays tied to source evidence and the selected player."""

from copy import deepcopy

from src.demos.round_summary import player_summary, summary_preview, team_summary
from src.demos.tactical_rounds import build_tactical_match
from src.gui.round_evidence_view import evidence_rows
from src.models.tactical import AliveState, Availability, Contact, EquipmentObservation, Evidence, Finding, SetupSnapshot, Status
from tests.test_early_round import reference


def test_mirage_summaries_refer_to_existing_events_and_use_nicknames():
    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    labels = {player.player_id: f"Nick {i}" for i, player in enumerate(match.rounds[0].players)}
    for record in match.rounds:
        rate = record.foundation.clock["tick_rate"]
        for items in (team_summary(record, match.evidence, labels, context.profile, rate),
                      player_summary(record, match.evidence, record.players[0].player_id,
                                     labels, context.profile, rate)):
            assert items
            assert all(eid in match.evidence for item in items for eid in item.evidence_ids)
            assert all(player.player_id not in item.text for item in items
                       for player in record.players)
            for item in items:
                table, total = evidence_rows(item.evidence_ids, match.evidence, labels,
                                             record.freeze_end_tick, rate)
                assert total == len(set(item.evidence_ids))
                assert "steamid" not in " ".join(table.columns).lower()


def test_first_contact_uses_earliest_kill_only_event():
    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    record = deepcopy(match.rounds[0])
    original = min(record.contacts, key=lambda contact: contact.tick)
    earlier = Contact("synthetic", record.number, original.tick - 1, "kill_only",
                      original.attacker_id, original.victim_id, "T", "CT",
                      evidence_ids=list(original.evidence_ids), status=Status.OBSERVED,
                      modality="firearm")
    record.contacts.append(earlier)
    item = next(item for item in team_summary(record, match.evidence, {}, context.profile, 64)
                if item.title == "Pierwszy kontakt")
    assert item.tick == earlier.tick
    assert "eliminacja" in item.text


def test_missing_sources_do_not_claim_zero_player_activity():
    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    record = deepcopy(match.rounds[0])
    record.availability["kills"] = Availability(Status.UNKNOWN)
    record.availability["throws"] = Availability(Status.UNKNOWN)
    player = record.players[0]
    items = player_summary(record, match.evidence, player.player_id, {}, context.profile, 64)
    activity = next(item.text for item in items if item.title == "Udział w rundzie")
    assert "niepełne dane" in activity
    assert "0 fragów" not in activity
    assert "0 rzutów" not in activity


def test_start_uses_precontact_state_and_never_a_later_finding():
    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    record = deepcopy(match.rounds[0])
    tick = min(c.tick for c in record.contacts)
    prep = record.ct_setup
    prep.setup_before_contact = SetupSnapshot(0, tick - 1, Status.PARTIAL,
        counts={"site_a": 2}, evidence_ids=[record.event_ids[0]])
    prep.findings = [Finding("Późny stan nie opisuje początku", "observation", [record.event_ids[0]])]
    summary = team_summary(record, match.evidence, {}, context.profile, 64)
    start = next(i for i in summary if i.title == "Początek · CT")
    assert start.tick == tick - 1
    assert "przed pierwszym zarejestrowanym kontaktem" in start.text
    assert "niepełne pokrycie" in start.text
    assert "Późny stan" not in start.text
    for invalid_tick in (tick, tick + 64, tick - 65):
        prep.setup_before_contact.tick = invalid_tick
        start = next(i for i in team_summary(record, match.evidence, {}, context.profile, 64)
                     if i.title == "Początek · CT")
        assert start.tick is None
        assert "Brak świeżego ustawienia" in start.text
        assert record.event_ids[0] not in start.evidence_ids


def test_no_contact_start_names_early_time():
    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    record = deepcopy(match.rounds[0])
    record.contacts = []
    record.ct_setup.snapshots = [SetupSnapshot(5, record.freeze_end_tick + 320,
        Status.OBSERVED, counts={"site_b": 2})]
    start = next(i for i in team_summary(record, match.evidence, {}, context.profile, 64)
                 if i.title == "Początek · CT")
    assert "5.0 s" in start.text
    assert "przed pierwszym" not in start.text


def test_later_reversal_is_in_preview_and_unknown_counts_are_not_used():
    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    record = deepcopy(match.rounds[0])
    record.availability["kills"] = Availability(Status.OBSERVED)
    boundary = record.freeze_end_tick + 400
    record.opening_window_end_tick = boundary
    record.alive_states = [
        AliveState("a", record.number, boundary, 5, 4),
        AliveState("b", record.number, boundary + 64, 3, 4),
        AliveState("c", record.number, boundary + 128, None, 4),
        AliveState("d", record.number, boundary + 192, 0, 4),
    ]
    items = team_summary(record, match.evidence, {}, context.profile, 64)
    changes = [i for i in items if i.title == "Późniejsza zmiana liczebności"]
    assert len(changes) == 1
    assert "5 T : 4 CT → 3 T : 4 CT" in changes[0].text
    assert "3 T : 4 CT" in " ".join(text for _, text in summary_preview(items))
    record.availability["kills"] = Availability(Status.UNKNOWN)
    assert not any(i.title == "Późniejsza zmiana liczebności"
                   for i in team_summary(record, match.evidence, {}, context.profile, 64))


def test_positions_never_use_future_or_stale_sample_and_nick_is_not_truncated():
    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    record = deepcopy(match.rounds[0])
    player = record.players[0].player_id
    for sample_tick, expected in ((record.end_tick + 1, "brak świeżej"),
                                  (record.end_tick - 65, "brak świeżej"),
                                  (record.end_tick - 1, "próbka")):
        record = deepcopy(match.rounds[0])
        evidence = dict(match.evidence)
        record.event_ids = [eid for eid in record.event_ids if evidence[eid].source != "states"]
        evidence["test-state"] = Evidence("test-state", "states", record.number, sample_tick, None,
            {"steamid": player, "is_alive": True, "last_place_name": "BombsiteA"})
        record.event_ids.append("test-state")
        items = player_summary(record, evidence, player, {player: "Dr. Player"}, context.profile, 64)
        end = next(i for i in items if i.title == "Pozycja przy zdarzeniu" and "koniec rundy" in i.text)
        assert expected in end.text
        assert ("test-state" in end.evidence_ids) == (sample_tick == record.end_tick - 1)
        assert "Dr. Player" in " ".join(text for _, text in summary_preview(items, player=True))


def test_equipment_reports_known_subset_without_inventing_buy_type():
    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    record = deepcopy(match.rounds[0])
    player = next(p for p in record.players if p.side == "CT")
    record.foundation.equipment_start = [EquipmentObservation(
        player.player_id, record.freeze_end_tick, 3, {"m4a1": 1, "smokegrenade": 1},
        "m4a1", 100, None, None, {}, [record.event_ids[0]])]
    item = next(i for i in team_summary(record, match.evidence, {}, context.profile, 64)
                if i.title == "Wyposażenie na starcie")
    assert "CT: ekwipunek odczytany dla 1/5" in item.text
    assert "T: ekwipunek odczytany dla 0/5" in item.text
    assert "Kity:" not in item.text
    assert "full buy" not in item.text
    assert item.evidence_ids == (record.event_ids[0],)
