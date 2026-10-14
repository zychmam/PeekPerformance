"""JSON export contract, numerical consistency, privacy, missing data and UI caching."""

import copy
import json
from pathlib import Path
from unittest.mock import Mock

import jsonschema
import pandas as pd
import pytest

from src.demos.map_round_facts import build_round_fact
from src.demos.match_report import (
    build_match_report,
    encode_match_report,
    table_records,
    validate_match_report,
)
from src.demos.tactical_rounds import build_tactical_match
from src.models.tactical import Availability, Evidence, Status
from tests.test_early_round import reference


@pytest.fixture(scope="module")
def export_fixture():
    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    facts = [build_round_fact(r, match.evidence, context.profile) for r in match.rounds]
    report = build_match_report(
        analysis, facts, match, context.profile, generated_at="2026-10-14T00:00:00+00:00"
    )
    return analysis, facts, match, context.profile, report


def test_report_matches_public_schema_and_is_strict_utf8_json(export_fixture):
    *_, report = export_fixture
    payload = encode_match_report(report)
    assert json.loads(payload) == report
    schema = json.loads(
        Path("docs/schemas/match_report_v1.schema.json").read_text(encoding="utf-8")
    )
    jsonschema.Draft202012Validator(schema).validate(report)
    validate_match_report(report)
    assert report["header"]["scope"] == "entire_match_all_players"
    assert set(report["reading_guide"]["sections"]) <= set(report)


def test_report_totals_match_round_stats_and_side_splits(export_fixture):
    analysis, _, _, _, report = export_fixture
    assert len(report["rounds"]) == len(analysis.rounds_df)
    for player in report["players"]:
        totals = player["match_statistics"]
        if totals is None:
            continue
        rows = [
            p["round_statistics"]
            for r in report["rounds"]
            for p in table_records(r["players"])
            if p["player_id"] == player["player_id"] and p["round_statistics"]
        ]
        assert totals["kills"] == sum(r["kills"] for r in rows)
        assert totals["deaths"] == sum(r["deaths"] for r in rows)
        assert totals["adr"] == pytest.approx(
            sum(r["damage"] for r in rows) / len(rows), abs=0.0051
        )
        assert totals["kast"]["denominator"] == len(rows)
        sides = [s for s in player["side_statistics"].values() if s is not None]
        assert sum(s["kills"] for s in sides) == totals["kills"]
        assert sum(s["rounds_played"] for s in sides) == totals["rounds_played"]
    assert sum(report["header"]["score"].values()) + len(
        report["header"]["unknown_result_rounds"]
    ) == len(report["rounds"])


def test_export_keeps_duplicate_nicknames_distinct_without_steamids(export_fixture):
    analysis, facts, match, profile, _ = export_fixture
    analysis = copy.deepcopy(analysis)
    analysis.player_info["name"] = "SameNickname"
    report = build_match_report(analysis, facts, match, profile)
    players = [p for p in report["players"] if p["nickname"] == "SameNickname"]
    assert len({p["player_id"] for p in players}) == len(players) > 1
    payload = encode_match_report(report)
    for sid in analysis.player_info.steamid.astype(str):
        assert sid.encode() not in payload
    assert b'"attacker_steamid"' not in payload
    assert "site_a" in {r["id"] for r in report["header"]["map_profile"]["regions"]}


def test_export_preserves_unknown_contact_coverage_and_nulls(export_fixture):
    analysis, _, match, profile, _ = export_fixture
    match = copy.deepcopy(match)
    first = match.rounds[0]
    first.contacts_status = Status.PARTIAL
    first.availability["damage"] = Availability(Status.UNKNOWN)
    facts = [build_round_fact(r, match.evidence, profile) for r in match.rounds]
    report = build_match_report(analysis, facts, match, profile)
    assert report["rounds"][0]["combat"]["contacts_status"] == "partial"
    assert report["rounds"][0]["coverage"]["sources"]["damage"]["status"] == "unknown"
    assert any(
        s is None or s["peek_performance_rating"] is None
        for p in report["players"]
        for s in p["side_statistics"].values()
    )
    with pytest.raises(ValueError, match="Incomplete round"):
        build_match_report(analysis, facts[:-1], match, profile)


def test_export_rejects_broken_references_and_nonfinite_numbers(export_fixture):
    *_, report = export_fixture
    broken = copy.deepcopy(report)
    event = table_records(broken["source_events"])[0]
    broken["source_events"]["rows"].pop(0)
    # Force a reference to the removed source regardless of fixture event order.
    broken["rounds"][0]["combat"]["test_reference"] = {"evidence_ids": [event["id"]]}
    with pytest.raises(ValueError, match="Unresolved source"):
        encode_match_report(broken)


def test_prefreeze_world_death_keeps_later_kill_and_source_event(export_fixture):
    analysis, facts, match, profile, _ = export_fixture
    analysis, match = copy.deepcopy(analysis), copy.deepcopy(match)
    record = match.rounds[0]
    kill = next(
        e
        for e in match.evidence.values()
        if e.source == "kills"
        and e.round_number == record.number
        and e.tick > record.freeze_end_tick
    )
    world = dict(kill.data)
    world.update(
        tick=record.freeze_end_tick - 1,
        weapon="world",
        attacker_steamid=world["user_steamid"],
        attacker_team_num=world["user_team_num"],
        total_rounds_played=record.number,
    )
    analysis.kills_df = pd.concat([analysis.kills_df, pd.DataFrame([world])], ignore_index=True)
    match.evidence["world-before-freeze"] = Evidence(
        "world-before-freeze", "kills", record.number, world["tick"], -1, world
    )
    report = build_match_report(analysis, facts, match, profile)
    reconciliation = report["limitations"]["statistics_reconciliation"]
    assert reconciliation["status"] == "consistent"
    assert reconciliation["difference"] == 0
    repeated = reconciliation["repeated_death_events"]
    assert any(r["earlier_death_before_freeze"] for r in repeated)
    encode_match_report(report)
    broken = copy.deepcopy(report)
    broken["players"][0]["match_statistics"]["adr"] = float("nan")
    with pytest.raises(ValueError):
        encode_match_report(broken)


def test_export_ui_prepares_once_and_reuses_complete_match(export_fixture):
    from streamlit.testing.v1 import AppTest

    analysis, _, _, _, report = export_fixture
    loader = Mock(return_value=report)
    app = AppTest.from_string("""
import streamlit as st
from src.gui.match_export_view import render_match_export
render_match_export(st.session_state['analysis'], st.session_state['loader'])
""")
    app.session_state["analysis"] = analysis
    app.session_state["loader"] = loader
    app.run()
    assert loader.call_count == 0
    app.button[0].click().run(timeout=20)
    assert not app.exception
    assert loader.call_count == 1
    assert any("Pobierz raport JSON" in b.label for b in app.get("download_button"))
    app.run()
    assert loader.call_count == 1


def test_dashboard_export_has_only_json_download(export_fixture):
    from streamlit.testing.v1 import AppTest

    analysis, _, _, _, report = export_fixture
    app = AppTest.from_string("""
import pandas as pd
import streamlit as st
from src.gui.match_dashboard import render_match_dashboard
render_match_dashboard(st.session_state['analysis'], pd.DataFrame(), lambda p:None,
                       lambda a:None, None, None, lambda a:st.session_state['report'])
""")
    app.session_state["analysis"] = analysis
    app.session_state["report"] = report
    app.session_state["match_section"] = "Dane i eksport"
    app.run(timeout=20)
    assert not app.exception
    next(b for b in app.button if b.label == "Przygotuj raport JSON").click().run(timeout=20)
    assert not app.exception
    assert [b.label for b in app.get("download_button")] == ["Pobierz raport JSON"]
