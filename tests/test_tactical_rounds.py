"""R1 contract and adapter tested against separately reviewed real event facts."""

import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from tests.map_support import MirageContext, context_key
from src.demos.tactical_rounds import build_tactical_match, load_tactical_match
from src.models.models import DemoAnalysis
from src.models.tactical import Attack, Episode, Finding, Status, TacticalMatch
from src.storage.database import Database

REFERENCE = Path(__file__).parent / "reference"


@pytest.fixture()
def inputs():
    data = json.loads((REFERENCE / "mirage_tactical_facts.json").read_text(encoding="utf-8"))
    analysis = DemoAnalysis(
        file_name="mirage.dem", content_hash=data["provenance"]["demo_hash"],
        map_name="de_mirage", analysis_version=data["analysis_version"],
        **{key: pd.DataFrame(rows) for key, rows in data["frames"].items()},
    )
    return analysis, MirageContext.from_json(json.dumps(data["spatial"]))


def test_reviewed_clocks_kills_refrags_plants_and_winners(inputs):
    result = build_tactical_match(*inputs)
    expected = json.loads((REFERENCE / "mirage_tactical_expectations.json").read_text())
    for case in expected["cases"]:
        rnd = next(r for r in result.rounds if r.number == case["round"])
        assert rnd.freeze_end_tick == case["freeze_tick"]
        assert rnd.end_tick == case["end_tick"]
        assert rnd.winner_side == case["winner"]
        assert rnd.end_reason == case["reason"]
        events = [result.evidence[eid] for eid in rnd.event_ids]
        for label in ("opening", "refrag"):
            if label not in case:
                continue
            target = case[label]
            event = next(e for e in events if e.source == "kills" and e.tick == target["tick"])
            assert event.data["attacker_steamid"] == target["attacker"]
            assert event.data["user_steamid"] == target["victim"]
            assert event.seconds == (event.tick-case["freeze_tick"])/64
        if "refrag" in case:
            assert case["refrag"]["tick"]-case["opening"]["tick"] == case["refrag"]["delay_ticks"]
        for key, name in (("plant_tick", "bomb_planted"), ("defuse_tick", "bomb_defused")):
            if key in case:
                assert any(e.source == "bombs" and e.tick == case[key]
                           and e.data["event"] == name for e in events)
        assert rnd.fights_status == Status.NOT_EVALUATED  # No invented tactical detections.
        assert rnd.retake.status == Status.NOT_EVALUATED


def test_team_identity_survives_switch_and_serialization(inputs):
    match = build_tactical_match(*inputs)
    rounds = {r.number: r for r in match.rounds}
    assert rounds[1].teams_by_side["T"] == rounds[13].teams_by_side["CT"] == "team_1"
    assert rounds[1].teams_by_side["CT"] == rounds[13].teams_by_side["T"] == "team_2"
    payload = json.loads(json.dumps(match.to_dict(), allow_nan=False))
    restored = TacticalMatch.from_dict(payload)
    assert restored.to_dict() == match.to_dict()
    payload["schema_version"] = 999
    with pytest.raises(ValueError, match="Unsupported"):
        TacticalMatch.from_dict(payload)


def test_unknown_absent_partial_and_uncomputed_are_distinct(inputs):
    analysis, spatial = inputs
    match = build_tactical_match(analysis)
    assert all(r.availability["states"].status == Status.UNKNOWN for r in match.rounds)
    assert all(r.t_preparation.status == Status.UNKNOWN for r in match.rounds)
    assert all(r.capabilities["early_preparation"].status == Status.UNKNOWN for r in match.rounds)
    spatial.utility = spatial.utility.iloc[:0]
    match = build_tactical_match(analysis, spatial)
    assert all(r.availability["utility"].status == Status.ABSENT for r in match.rounds)
    assert all(r.availability["states"].status == Status.PARTIAL for r in match.rounds)
    assert all(r.t_preparation.status == Status.PARTIAL for r in match.rounds)
    spatial.diagnostics = {}
    assert build_tactical_match(analysis, spatial).rounds[0].availability["utility"].status == (
        Status.UNKNOWN
    )


def test_changed_roster_is_not_guessed_as_a_known_team(inputs):
    analysis, spatial = inputs
    roster = analysis.round_roster_df
    idx = roster.index[roster.total_rounds_played.eq(13)][0]
    roster.loc[idx, "steamid"] = "substitute"
    rnd = next(r for r in build_tactical_match(analysis, spatial).rounds if r.number == 13)
    assert rnd.availability["team_identity"].status == Status.UNKNOWN


def test_failed_utility_stream_is_partial_even_with_other_grenades(inputs):
    analysis, spatial = inputs
    spatial.diagnostics["sources"]["hegrenade_detonate"] = "error: RuntimeError"
    match = build_tactical_match(analysis, spatial)
    for rnd in match.rounds:
        if any(e.source == "utility" for e in (match.evidence[i] for i in rnd.event_ids)):
            assert rnd.availability["utility"].status == Status.PARTIAL


def test_load_reuses_saved_sources_and_preserves_evidence_ids(inputs, tmp_path):
    analysis, spatial = inputs
    db = Database(str(tmp_path / "cache.db"))
    db.upsert_demo_analysis(analysis)
    from tests.map_support import persist_fixture
    spatial = persist_fixture(db, analysis, spatial)
    direct = build_tactical_match(analysis, spatial)
    with patch("src.demos.demo_analyzer.DemoAnalyzer", side_effect=AssertionError("parser")):
        loaded = load_tactical_match(db, analysis.content_hash)
    assert set(loaded.evidence) == set(direct.evidence)
    assert loaded.to_dict() == direct.to_dict()


def test_model_represents_failed_attack_without_an_entry_and_rejects_false_evidence(inputs):
    match = build_tactical_match(*inputs)
    rnd = match.rounds[0]
    rnd.attacks.append(Attack(
        Episode("synthetic-attempt", "attack", 7500, 7600,
                evidence_ids=[rnd.event_ids[0]], status=Status.OBSERVED),
        target_site="A", outcome="stopped", entry_ids=[],
    ))
    assert rnd.attacks[0].plant_id is None
    with pytest.raises(ValueError, match="requires evidence"):
        Finding("unproven", "interpretation", [])
    rnd.team_findings.append(Finding("invalid reference", "observation", ["missing"]))
    with pytest.raises(ValueError, match="evidence"):
        match.validate()
