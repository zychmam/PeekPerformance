"""Event-specific bomb absence, uncertainty and downstream denominators."""

import pandas as pd
import pytest

from src.demos.bomb_coverage import combined_coverage, event_known
from src.demos.map_action_facts import action_facts
from src.demos.map_action_tendencies import aggregate_actions
from src.demos.round_attacks import enrich_attacks
from src.demos.round_defense import _retake
from src.demos.round_movement import MovementIndex
from src.demos.tactical_rounds import build_tactical_match
from src.models.tactical import Availability, Status
from tests.test_coach_foundations import match_inputs  # noqa: F401
from tests.test_tactical_actions import RATE, build, event, hurt


@pytest.mark.parametrize("read,status", [
    ("ok", Status.ABSENT), ("not_listed", Status.UNKNOWN),
    ("unsupported", Status.UNKNOWN), ("error: ValueError", Status.UNKNOWN),
    ("not_loaded", Status.UNKNOWN),
])
def test_empty_plant_source_uses_actual_read_diagnostics(match_inputs, read, status):  # noqa: F811
    analysis, context = match_inputs
    analysis.bomb_events_df = pd.DataFrame()
    context.bombs = pd.DataFrame()
    context.diagnostics["sources"]["bomb_planted"] = read
    record = build_tactical_match(analysis, context).rounds[0]
    assert record.availability["bomb_planted"].status == status
    assert record.retake.status == (Status.NOT_APPLICABLE if read == "ok" else Status.UNKNOWN)
    assert event_known(record, "bomb_planted") == (read == "ok")
    # Missing defuse/explosion sources cannot erase known absence of a plant.
    assert record.availability["bombs"].status == Status.UNKNOWN


def test_unknown_plant_cannot_inherit_known_other_bomb_events():
    record, _, _, _ = build()
    record.availability["bomb_planted"] = Availability(Status.UNKNOWN)
    record.availability["bomb_defused"] = Availability(Status.OBSERVED)
    record.availability["bomb_exploded"] = Availability(Status.ABSENT)
    assert not event_known(record, "bomb_planted")
    assert combined_coverage(record).status == Status.PARTIAL
    record.availability["bomb_planted"] = Availability(Status.ABSENT)
    assert combined_coverage(record).status == Status.OBSERVED


def test_attack_plant_denominator_uses_only_required_source():
    record, evidence, profile, index = build(
        {"T0": lambda t: "aa", "T1": lambda t: "aa"}, [hurt("contact", 20)],
    )
    record.availability["bombs"] = Availability(Status.UNKNOWN)
    for source in (Status.ABSENT, Status.UNKNOWN, Status.PARTIAL):
        record.availability["bomb_planted"] = Availability(source)
        enrich_attacks(record, evidence, profile, tick_rate=RATE,
                       movements=MovementIndex(record), state_index=index)
        assert record.attacks
        assert all(a.plant_outcome == ("not_observed" if source == Status.ABSENT else "unknown")
                   for a in record.attacks)
        fact = {"number": 1, "winner_side": "CT", "freeze_tick": 0, "tick_rate": RATE,
                **action_facts(record, evidence, profile, lambda t: t / RATE)}
        report = aggregate_actions([fact], side="T")
        assert report["sites"][0]["plant"]["denominator"] == (
            len(record.attacks) if source == Status.ABSENT else 0)
        assert report["bombs_known_rounds"] == ([1] if source == Status.ABSENT else [])


def test_missing_defuse_source_prevents_claiming_no_retake_attempt():
    plant = event("plant", "bombs", 50, event="bomb_planted", user_steamid="T0", site="A")
    record, evidence, profile, index = build({"T0": lambda t: "sa"}, [plant])
    assert record.retake.outcome == "no_attempt"
    record.availability["bomb_begindefuse"] = Availability(Status.UNKNOWN)
    _retake(record, evidence, profile, [plant], tick_rate=RATE, state_index=index)
    assert record.retake.status == Status.UNKNOWN
    assert record.retake.outcome == "unknown"
    assert record.retake.episode is None
