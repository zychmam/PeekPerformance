"""Evidence identity, availability and parser-free loading guarantees."""

from unittest.mock import patch

import pandas as pd
import pytest

from src.demos.coach_data import build_coach_inputs, load_coach_inputs
from src.demos.versions import ANALYSIS_VERSION
from src.models.models import DemoAnalysis
from src.storage.database import Database


def _analysis():
    return DemoAnalysis(
        file_name="example.dem", content_hash="demo-hash", analysis_version=ANALYSIS_VERSION,
        kills_df=pd.DataFrame([
            {"tick": 20.0, "total_rounds_played": 1, "attacker_steamid": "76561198008873401",
             "user_steamid": "76561198008873402", "attacker_team_num": 2, "user_team_num": 3},
        ] * 2),
        round_roster_df=pd.DataFrame([{
            "steamid": 76561198008873401, "team_num": 2, "total_rounds_played": 1,
        }]),
        grenades_df=pd.DataFrame([{"tick": 1, "X": 500}]),
        chat_messages_df=pd.DataFrame([{"text": "private"}]),
    )


def test_evidence_ids_survive_sqlite_and_identical_events_remain_distinct(tmp_path):
    db = Database(str(tmp_path / "cache.db"))
    analysis = _analysis()
    before = build_coach_inputs(analysis)
    db.upsert_demo_analysis(analysis)
    with patch("src.demos.demo_analyzer.DemoAnalyzer", side_effect=AssertionError("parser")):
        after = load_coach_inputs(db, analysis.content_hash)
    ids = before.frames["kills"]["event_id"].tolist()
    assert len(set(ids)) == 2
    assert ids == after.frames["kills"]["event_id"].tolist()
    assert before.frames["roster"].event_id.tolist() == after.frames["roster"].event_id.tolist()
    assert before.frames["roster"].steamid.item() == "76561198008873401"
    assert after.event(ids[0])["attacker_steamid"] == "76561198008873401"
    assert after.availability["kills"].status == "present"
    with pytest.raises(KeyError):
        after.event("invented")
    light = db.get_demo_analysis(analysis.content_hash, include_auxiliary=False)
    assert light.grenades_df.empty and light.chat_messages_df.empty
    assert not db.get_demo_analysis(analysis.content_hash).grenades_df.empty


def test_source_change_invalidates_ids_and_input_is_not_mutated():
    analysis = _analysis()
    original = build_coach_inputs(analysis)
    assert "event_id" not in analysis.kills_df
    analysis.kills_df.loc[0, "tick"] = 21
    changed = build_coach_inputs(analysis)
    assert set(original.frames["kills"].event_id).isdisjoint(changed.frames["kills"].event_id)


def test_missing_partial_and_null_sources_are_not_zero_counts():
    analysis = _analysis()
    analysis.kills_df.loc[0, "user_team_num"] = None
    analysis.damage_df = pd.DataFrame([{"tick": 20}])
    inputs = build_coach_inputs(analysis)
    assert inputs.availability["blinds"].status == "unknown"
    assert inputs.availability["damage"].status == "partial"
    assert "enemy_damage" in inputs.availability["damage"].missing_columns
    assert inputs.availability["kills"].null_columns == ("user_team_num",)
    assert inputs.availability["player_states"].status == "not_loaded"


def test_unknown_and_stale_inputs_fail_without_upgrade(tmp_path):
    db = Database(str(tmp_path / "cache.db"))
    with pytest.raises(ValueError, match="Unknown"):
        load_coach_inputs(db, "missing")
    analysis = _analysis()
    analysis.analysis_version = 0
    db.upsert_demo_analysis(analysis)
    with pytest.raises(ValueError, match="upgrade"):
        load_coach_inputs(db, analysis.content_hash)
