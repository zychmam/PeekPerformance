"""Independent M5 units, coverage, side identity and cached UI navigation checks."""

from unittest.mock import patch

from src.demos.map_round_facts import build_round_fact, comparable_rounds
from src.demos.map_tendencies import aggregate_tendencies


def fact(number, direction="A", *, flipped=False, value=12000, winner="alpha"):
    sides = {}
    for side, team in (
        ("T", "beta" if flipped else "alpha"),
        ("CT", "alpha" if flipped else "beta"),
    ):
        roster = [f"{team}{i}" for i in range(5)]
        snap = {
            "tick": number * 1000 + 100,
            "seconds": 10,
            "complete": direction is not None,
            "status": "observed" if direction else "partial",
            "dominant_direction": direction,
            "positions": [
                {
                    "player_id": pid,
                    "area": "area_a" if direction else None,
                    "alive": True,
                    "sample_tick": number * 1000 + 99,
                }
                for pid in roster
            ],
            "evidence_ids": [f"proof{number}"],
        }
        sides[side] = {
            "team_id": team,
            "roster": roster,
            "start_alive": 5,
            "snapshots": {"10": snap},
            "equipment": {
                "economy": {
                    "current_equip_value": {
                        "total": value,
                        "known_players": 5 if value is not None else 1,
                    }
                }
            },
            "first_firearm_contacts": [],
            "player_first_firearm_contacts": [],
            "contacts_known": True,
            "opening": [],
            "opening_known": True,
            "early_throws": [],
            "early_throws_known": True,
            "refrags": [],
            "refrags_known": True,
            "had_advantage": False,
            "end_alive_ids": roster[:2],
        }
    return {
        "number": number,
        "freeze_tick": number * 1000,
        "tick_rate": 10,
        "winner_team_id": winner,
        "winner_side": ("T" if winner == sides["T"]["team_id"] else "CT")
        if winner is not None
        else None,
        "sides": sides,
        "ct_sectors": {},
        "entries": [],
        "early_seconds": 15,
        "metadata": {
            "raw_total_rounds_played": number,
            "reset": False,
            "phase": "live",
            "is_warmup_period": False,
        },
    }


def report(facts, **kwargs):
    return aggregate_tendencies(facts, team_id="alpha", side="T", **kwargs)


def test_direction_denominator_is_known_rounds_and_missing_snapshot_is_not_zero():
    result = report([fact(1), fact(2, "B"), fact(3), fact(4, None)])
    a, b = result["tables"]["directions"]
    assert (a["key"], a["count"], a["denominator"], a["rounds"]) == ("A", 2, 3, [1, 3])
    assert (b["count"], b["denominator"]) == (1, 3)
    assert result["coverage"]["directions"]["unknown_rounds"] == [4]
    assert sum(row["count"] for row in result["tables"]["positions"]) == 20


def test_identity_side_switch_gap_and_reset_break_previous_round_comparison():
    items = [
        fact(1),
        fact(2, winner="beta"),
        fact(3, flipped=True),
        fact(5, flipped=True),
        fact(6, flipped=True),
    ]
    items[-1]["metadata"]["reset"] = True
    rows = comparable_rounds(items)
    assert rows[1]["comparison"]["previous_result"]["T"] == "win"
    assert rows[1]["comparison"]["previous_survivors"]["T"] == ["alpha0", "alpha1"]
    assert all(rows[i]["comparison"]["previous_round"] is None for i in (0, 2, 3, 4))
    assert report(items)["rounds"] == [1, 2]
    assert aggregate_tendencies(items, team_id="alpha", side="CT")["rounds"] == [3, 5, 6]


def test_unknown_team_and_changed_roster_are_not_silently_merged():
    first, second, unknown = fact(1), fact(2), fact(3)
    second["sides"]["T"]["roster"][0] = "substitute"
    unknown["sides"]["T"]["team_id"] = None
    rows = comparable_rounds([first, second, unknown])
    assert rows[1]["comparison"]["previous_round"] is None
    assert report([first, unknown])["unknown_team_rounds"] == [3]


def test_equipment_filters_use_full_totals_and_do_not_treat_missing_as_eco():
    items = [fact(1, value=None), fact(2, value=0), fact(3, value=15000)]
    assert report(items)["rounds"] == [1, 2, 3]
    assert report(items, equipment_min=0, equipment_max=0)["rounds"] == [2]
    items[2]["sides"]["CT"]["equipment"]["economy"]["current_equip_value"]["total"] = None
    assert report(items, require_equipment=True)["rounds"] == [2]


def test_starting_population_filter_requires_known_five_on_both_sides():
    items = [fact(1), fact(2), fact(3)]
    items[1]["sides"]["CT"]["start_alive"] = 4
    items[2]["sides"]["T"]["start_alive"] = None
    assert report(items, require_starting_five=True)["rounds"] == [1]
    assert report(items)["rounds"] == [1, 2, 3]


def test_zero_cases_stay_distinct_from_unknown_refrags_and_utility():
    first, second = fact(1), fact(2)
    second["sides"]["T"]["refrags_known"] = False
    second["sides"]["T"]["early_throws_known"] = False
    result = report([first, second])
    assert result["refrags"]["known_rounds"] == 1
    assert not result["refrags"]["rounds_with"]
    assert result["coverage"]["utility"]["unknown_rounds"] == [2]


def test_events_are_not_counted_as_independent_rounds_or_collapsed_by_tick():
    first = fact(1)
    first["sides"]["T"]["opening"] = [
        {
            "role": "kill",
            "player_id": f"alpha{i}",
            "area": "area_a",
            "tick": 1200,
            "seconds": 20,
            "evidence_ids": [f"kill{i}"],
        }
        for i in (0, 1)
    ]
    result = report([first])
    (opening,) = result["tables"]["opening"]
    assert opening["count"] == opening["denominator"] == 2
    assert opening["rounds"] == [1]
    assert report([first], player_id="alpha0")["tables"]["opening"][0]["count"] == 1


def test_utility_origin_and_effect_keep_unknown_in_event_denominator():
    first = fact(1)
    first["sides"]["T"]["early_throws"] = [
        {
            "player_id": "alpha0",
            "kind": "Smoke",
            "origin_area": "spawn",
            "origin_kind": "spawn",
            "effect_area": None,
            "tick": 1050,
            "seconds": 5,
            "match_status": "unknown",
            "evidence_ids": ["throw"],
        }
    ]
    (utility,) = report([first])["tables"]["utility"]
    assert utility["key"] == ("Smoke", "spawn", "__unknown__")
    assert utility["denominator"] == 1 and utility["examples"][0]["from_spawn"]


def test_advantage_conversion_excludes_unknown_outcome_and_does_not_imply_player_credit():
    items = [fact(1), fact(2, winner="beta"), fact(3, winner=None)]
    for item in items:
        item["sides"]["T"]["had_advantage"] = True
    result = report(items, player_id="alpha0")
    assert result["advantage"]["rounds_with"] == [1, 2, 3]
    assert result["advantage"]["wins"] == [1]
    assert result["advantage"]["known_result_rounds"] == [1, 2]


def test_fixed_snapshot_times_never_mix_ten_and_fifteen_seconds():
    first = fact(1)
    first["sides"]["T"]["snapshots"]["15"] = {
        **first["sides"]["T"]["snapshots"]["10"],
        "seconds": 15,
        "dominant_direction": "B",
    }
    assert report([first], snapshot_seconds=10)["tables"]["directions"][0]["key"] == "A"
    assert report([first], snapshot_seconds=15)["tables"]["directions"][0]["key"] == "B"
    assert not report([first], snapshot_seconds=5)["tables"]["directions"]


def test_snapshot_after_round_end_is_inapplicable_and_other_metrics_remain_eligible():
    short, boundary, missing = fact(1), fact(2), fact(3)
    short["end_tick"] = short["freeze_tick"] + 99
    boundary["end_tick"] = boundary["freeze_tick"] + 100
    missing["sides"]["T"]["snapshots"] = {}
    result = report([short, boundary, missing])
    coverage = result["coverage"]["snapshots"]
    assert coverage == {
        "eligible": 2,
        "known": 1,
        "unknown_rounds": [3],
        "not_applicable_rounds": [1],
    }
    assert sum(r["count"] for r in result["tables"]["positions"]) == 10
    assert result["coverage"]["contacts"]["eligible"] == 3
    missing["freeze_tick"] = None
    assert report([missing])["coverage"]["snapshots"]["unknown_rounds"] == [3]
    boundary["freeze_tick"] = None
    assert report([boundary])["coverage"]["snapshots"]["unknown_rounds"] == [2]


def test_one_reply_can_trade_two_deaths_with_unique_navigation_and_author_filter():
    from tests.test_tactical_actions import build, kill

    record, evidence, profile, _ = build(
        events=[
            kill("d1", 20, "C0", "T0"),
            kill("d2", 30, "C0", "T1"),
            kill("reply", 40, "T2", "C0"),
        ]
    )
    item = build_round_fact(record, evidence, profile)
    result = aggregate_tendencies([item], team_id="team1", side="T")["refrags"]
    assert (result["trade_kills"], result["traded_deaths"], result["rounds_with"]) == (1, 2, [1])
    assert len(result["kills"]) == 1
    assert {"d1", "d2", "reply"} <= set(result["kills"][0]["evidence_ids"])
    for pid, expected in (("T2", 1), ("T0", 0)):
        own = aggregate_tendencies([item], team_id="team1", side="T", player_id=pid)
        assert own["refrags"]["trade_kills"] == expected


def test_partial_contact_examples_carry_source_completeness():
    from tests.test_tactical_actions import build, hurt

    record, evidence, profile, _ = build(events=[hurt("h", 20)], unknown_sources=["kills"])
    item = build_round_fact(record, evidence, profile)
    result = aggregate_tendencies([item], team_id="team1", side="T")
    assert result["coverage"]["contacts"]["unknown_rounds"] == [1]
    assert result["tables"]["contacts"][0]["examples"][0]["source_status"] == "partial"


def test_source_facts_keep_personal_first_contact_and_exact_zero_equipment():
    from src.models.tactical import EquipmentObservation, RoundFoundation
    from tests.test_tactical_actions import RATE, build, hurt

    record, evidence, profile, _ = build(events=[hurt("first", 20), hurt("later", 50, "T1", "C1")])
    record.foundation = RoundFoundation("demo", 1, "source", {"tick_rate": RATE})
    record.foundation.equipment_start = [
        EquipmentObservation(
            f"T{i}", 0, 2, {}, None, 0, False, False, {"current_equip_value": 0}, []
        )
        for i in range(5)
    ]
    value = build_round_fact(record, evidence, profile)
    own = value["sides"]["T"]
    assert own["equipment"]["economy"]["current_equip_value"]["total"] == 0
    assert own["opening_known"] and own["opening"] == []
    assert [c["seconds"] for c in own["first_firearm_contacts"]] == [2]
    assert (
        next(c for c in own["player_first_firearm_contacts"] if c["player_id"] == "T1")["seconds"]
        == 5
    )


def test_round_fact_sqlite_cache_avoids_sources_and_detectors(tmp_path):
    from src.demos.map_tendencies_service import get_map_round_facts, round_facts_key
    from src.storage.database import Database
    from tests.map_support import persist_fixture
    from tests.test_early_round import reference

    analysis, context = reference()
    db = Database(str(tmp_path / "facts.db"))
    db.upsert_demo_analysis(analysis)
    persist_fixture(db, analysis, context)
    initial = get_map_round_facts(db, None, analysis)
    with (
        patch(
            "src.demos.tactical_rounds.build_tactical_match",
            side_effect=AssertionError("detectors called"),
        ),
        patch(
            "src.demos.spatial_service.get_spatial_context",
            side_effect=AssertionError("sources read"),
        ),
    ):
        assert get_map_round_facts(db, None, analysis) == initial
    assert set(
        db.get_stage_rounds(analysis.content_hash, "map_round_facts", round_facts_key(analysis))
    ) == {item["number"] for item in initial}


def test_map_view_filters_and_round_link_without_browser():
    from streamlit.testing.v1 import AppTest

    from src.demos.map_tendencies_service import round_facts_key
    from src.models.models import DemoAnalysis

    analysis = DemoAnalysis("test.dem", map_name="de_synthetic", content_hash="test")
    items = [fact(1), fact(2, "B")]
    app = AppTest.from_string("""
import streamlit as st
from src.gui.map_tendencies_view import render_map_tendencies
render_map_tendencies(st.session_state['analysis'], 'alpha0', {'alpha0':'Nickname'}, None)
""")
    app.session_state["analysis"] = analysis
    app.session_state["map_facts_" + round_facts_key(analysis)] = items
    app.run(timeout=20)
    assert not app.exception
    assert any("Dominujący kierunek" in text.value for text in app.markdown)
    next(b for b in app.button if b.label == "Przejdź do analizy tej rundy").click().run()
    assert app.session_state["pending_tactical_navigation"]["round"] in {1, 2}
    next(r for r in app.radio if r.label == "Zakres obserwacji").set_value("Wybrany gracz").run()
    assert not app.exception
    for table in app.dataframe:
        assert not any("steamid" in str(c).lower() for c in table.value.columns)


def test_dashboard_round_link_opens_requested_context_and_radar_time():
    from streamlit.testing.v1 import AppTest

    from src.demos.map_tendencies_service import round_facts_key
    from src.demos.tactical_rounds import build_tactical_match
    from tests.test_early_round import reference

    analysis, context = reference()
    match = build_tactical_match(analysis, context)
    facts = [build_round_fact(r, match.evidence, context.profile) for r in match.rounds]
    app = AppTest.from_string("""
import pandas as pd
import streamlit as st
from src.gui.match_dashboard import render_match_dashboard
render_match_dashboard(st.session_state['analysis'], pd.DataFrame(), lambda p:None,
                       lambda a:None, lambda a,rnd=None:st.session_state['context'], None)
""")
    app.session_state["analysis"] = analysis
    app.session_state["context"] = context
    app.session_state["match_section"] = "Tendencje mapy"
    app.session_state["map_facts_" + round_facts_key(analysis)] = facts
    app.run(timeout=30)
    assert not app.exception
    source = next(w for w in app.selectbox if w.label == "Obserwacja źródłowa")
    expected_number = int(source.options[source.value].split()[1])
    next(b for b in app.button if b.label == "Przejdź do analizy tej rundy").click().run(timeout=30)
    assert not app.exception
    assert app.session_state["match_section"] == "Analiza rundy"
    assert app.session_state["selected_tactical_round"][1].rounds[0].number == expected_number
    assert app.session_state[f"round_time_{analysis.content_hash}_{expected_number}"] == 10.0
