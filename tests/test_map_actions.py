"""Tactical M5 units and negative cases, with independent and synthetic-map references."""

from copy import deepcopy

from src.demos.map_round_facts import build_round_fact
from src.demos.map_tendencies import aggregate_tendencies
from tests.test_map_tendencies import fact
from tests.test_tactical_actions import build, event, hurt


def attack(aid, site="A", *, start=20, entry="observed_presence", plant="not_observed"):
    return {
        "id": aid,
        "target_site": site,
        "start_tick": int(start * 10),
        "end_tick": 900,
        "seconds": start,
        "duration_seconds": 10,
        "entry_spread_seconds": 2,
        "participants": ["alpha0", "alpha1"],
        "main_group": ["alpha0", "alpha1"],
        "detached_players": [],
        "detached_actions": [],
        "utility": [],
        "approaches": ["custom_approach"],
        "entry_outcome": entry,
        "plant_outcome": plant,
        "evidence_ids": [aid],
        "status": "observed",
        "pauses_seconds": 0,
        "tempo_reference_player_id": "alpha0",
        "end_reason": "round_end",
    }


def prepared(number=1, *, winner="alpha"):
    item = fact(number, winner=winner)
    item.update(
        attacks_status="observed",
        movement_status="observed",
        utility_context_status="verified_absent",
        attacks=[],
        ct_activity=[],
        rotation_eligibility=[],
        rotations=[],
        retake={"status": "not_applicable"},
    )
    return item


def aggregate(items, *, side="T", player_id=None, **filters):
    return aggregate_tendencies(items, team_id="alpha", side=side, player_id=player_id, **filters)


def test_two_attempts_in_one_round_have_one_win_denominator_and_separate_entry_plant():
    item = prepared()
    item["attacks"] = [attack("a1", entry="not_observed"), attack("a2", plant="planted")]
    result = aggregate([item])["actions"]
    (site,) = result["sites"]
    assert site["count"] == 2 and site["rounds"] == [1]
    assert site["entry"] == {"count": 1, "denominator": 2, "unknown": 0}
    assert site["plant"] == {"count": 1, "denominator": 2, "unknown": 0}
    assert site["wins"]["count"] == site["wins"]["denominator"] == 1


def test_unknown_outcome_target_and_sources_never_become_confirmed_zero():
    item, unknown = prepared(), prepared(2, winner=None)
    item["attacks_status"] = "verified_absent"
    unknown["attacks_status"] = "partial"
    unknown["attacks"] = [attack("uncertain", None, entry="unknown", plant="unknown")]
    result = aggregate([item, unknown])["actions"]
    assert result["attack_coverage"]["known_rounds"] == [1]
    assert result["attack_coverage"]["unknown_rounds"] == [2]
    assert result["sites"][0]["entry"]["denominator"] == 0
    assert result["sites"][0]["wins"]["denominator"] == 0


def test_player_scope_filters_participation_without_claiming_team_outcome_as_individual():
    item = prepared()
    item["attacks"] = [attack("a")]
    item["attacks"][0]["detached_players"] = ["alpha2"]
    assert len(aggregate([item], player_id="alpha2")["actions"]["attempts"]) == 1
    assert not aggregate([item], player_id="alpha3")["actions"]["attempts"]
    assert aggregate([item], player_id="alpha0")["actions"]["sites"][0]["wins"]["count"] == 1


def test_same_utility_linked_to_two_attempts_is_two_associations_not_two_independent_rounds():
    item = prepared()
    item["attacks"] = [attack("a1"), attack("a2")]
    for a in item["attacks"]:
        a["utility"] = [
            {
                "id": "smoke",
                "player_id": "alpha0",
                "kind": "Smoke",
                "origin_area": "spawn",
                "effect_area": None,
                "throw_tick": 150,
                "match_status": "unknown",
                "evidence_ids": ["throw"],
            }
        ]
    result = aggregate([item])["actions"]
    assert len(result["utility"]) == 2
    assert {u["round"] for u in result["utility"]} == {1}
    assert all(u["phase"] == "before" and u["effect_area"] is None for u in result["utility"])


def test_changed_target_within_round_and_plant_are_retained_on_renamed_map():
    record, evidence, profile, _ = build(
        {"T0": lambda t: "sa" if 20 <= t <= 22 else "sb" if t >= 80 else "spawn"},
        events=[event("plant", "bombs", 90, event="bomb_planted", site="B", user_steamid="T0")],
        renamed=True,
    )
    item = build_round_fact(record, evidence, profile, metadata={"tick_rate": 10})
    result = aggregate_tendencies([item], team_id="team1", side="T")["actions"]
    assert [a["target_site"] for a in result["attempts"]] == ["A", "B"]
    assert result["plants"][0]["site"] == "B"
    assert result["plants"][0]["seconds"] == 9
    assert result["attempts"][1]["previous_attack_id"] == result["attempts"][0]["id"]


def test_ct_rotation_opportunities_include_nonarrival_unknown_and_player_filter():
    paths = {
        "T0": lambda t: "aa",
        "T1": lambda t: "aa",
        "C0": lambda t: "cb" if t < 40 else "road" if t < 50 else "ca",
        "C1": lambda t: "cb",
    }
    record, evidence, profile, _ = build(paths, [hurt("contact", 20)])
    item = build_round_fact(record, evidence, profile, metadata={"tick_rate": 10})
    report = aggregate_tendencies([item], team_id="team2", side="CT")["actions"]
    assert report["rotation_summary"]["eligible"] == 2
    assert report["rotation_summary"]["arrived"] == 1
    assert report["rotation_summary"]["reaction_median"] == 1.9
    assert report["rotation_summary"]["reaction_known"] == 1
    personal = aggregate_tendencies([item], team_id="team2", side="CT", player_id="C1")["actions"]
    assert personal["rotation_summary"]["eligible"] == 1
    assert personal["rotation_summary"]["arrived"] == 0
    assert personal["rotation_summary"]["reaction_median"] is None


def test_missing_attack_sources_keep_observed_attempt_but_not_complete_coverage():
    record, evidence, profile, _ = build({"T0": lambda t: "sa"}, unknown_sources=["throws"])
    item = build_round_fact(record, evidence, profile, metadata={"tick_rate": 10})
    result = aggregate_tendencies([item], team_id="team1", side="T")["actions"]
    assert result["attempts"] and result["attack_coverage"]["unknown_rounds"] == [1]


def test_ct_utility_navigation_uses_throw_time_and_temporal_attack_association():
    record, evidence, profile, _ = build(
        {"T0": lambda t: "sa" if t >= 50 else "spawn"},
        [event("smoke", "throws", 20, user_steamid="C0", user_team_num=3, kind="Smoke")],
    )
    item = build_round_fact(record, evidence, profile, metadata={"tick_rate": 10})
    result = aggregate_tendencies([item], team_id="team2", side="CT")["actions"]
    utility = result["utility"][0]
    assert utility["seconds"] == 2 and utility["tick"] == 20
    assert utility["attack_relations"][0]["phase"] == "before"
    assert utility["attack_relations"][0]["offset_seconds"] == -3


def test_unknown_win_denominator_counts_rounds_instead_of_attempts():
    item = prepared(winner=None)
    item["attacks"] = [attack("a"), attack("b")]
    assert aggregate([item])["actions"]["sites"][0]["wins"] == {
        "count": 0,
        "denominator": 0,
        "unknown": 1,
    }


def test_ct_activity_and_retake_preserve_no_attempt_vs_unknown_vs_not_applicable():
    record, evidence, profile, _ = build({"C0": lambda t: "road" if t < 30 else "cb"})
    item = build_round_fact(record, evidence, profile, metadata={"tick_rate": 10})
    actions = aggregate_tendencies([item], team_id="team2", side="CT")["actions"]
    assert {a["kind"] for a in actions["activity"]} >= {
        "forward_presence",
        "withdrawal_from_forward",
    }
    assert actions["retakes"][0]["status"] == "not_applicable"
    item["retake"] = {"status": "verified_absent", "outcome": "no_attempt", "episode": None}
    assert (
        aggregate_tendencies([item], team_id="team2", side="CT")["actions"]["retakes"][0]["outcome"]
        == "no_attempt"
    )
    item["retake"] = {"status": "unknown", "outcome": "unknown", "episode": None}
    assert (
        aggregate_tendencies([item], team_id="team2", side="CT")["actions"]["retakes"][0]["outcome"]
        == "unknown"
    )


def test_sequence_after_win_loss_unknown_fields_and_filtered_predecessor():
    items = [prepared(1), prepared(2, winner="beta"), prepared(3)]
    items[0]["attacks"] = [attack("a1")]
    items[1]["attacks"] = [attack("a2")]
    items[2]["attacks"] = [attack("a3", "B", start=50)]
    result = aggregate(items)["sequence"]
    assert result["pairs"][0]["transitions"]["first_target"] == "repeated"
    assert result["pairs"][1]["previous_result"] == "loss"
    assert result["pairs"][1]["transitions"]["first_target"] == "changed"
    items[1]["attacks"][0]["target_site"] = None
    assert aggregate(items)["sequence"]["pairs"][0]["transitions"]["first_target"] == "unknown"
    assert not aggregate(items, round_numbers=[1, 3])["sequence"]["pairs"]


def test_sequence_tied_attempts_are_order_independent_and_unknown_utility_locations_are_not_equal():
    first, second = prepared(), prepared(2)
    first["attacks"] = [attack("a", "A"), attack("b", "B")]
    second["attacks"] = list(reversed(deepcopy(first["attacks"])))
    result = aggregate([first, second])["sequence"]["pairs"][0]
    assert result["transitions"]["first_target"] == "repeated"
    for item in (first, second):
        item["sides"]["T"]["early_throws"] = [
            {
                "kind": "Smoke",
                "origin_area": "spawn",
                "effect_area": None,
                "evidence_ids": ["throw"],
                "tick": 1100,
                "seconds": 10,
                "player_id": "alpha0",
                "origin_kind": "spawn",
                "match_status": "unknown",
            }
        ]
    assert (
        aggregate([first, second])["sequence"]["pairs"][0]["transitions"]["early_utility"]
        == "unknown"
    )


def test_real_action_ui_ct_and_t_player_no_exceptions_or_raw_player_ids():
    from streamlit.testing.v1 import AppTest

    from src.demos.map_tendencies_service import round_facts_key
    from src.models.models import DemoAnalysis

    record, evidence, profile, _ = build({"T0": lambda t: "sa" if t > 20 else "aa"})
    item = build_round_fact(record, evidence, profile, metadata={"tick_rate": 10})
    analysis = DemoAnalysis("fixture.dem", map_name="de_synthetic", content_hash="m5-actions")
    app = AppTest.from_string("""
import streamlit as st
from src.gui.map_tendencies_view import render_map_tendencies
render_map_tendencies(st.session_state['analysis'], 'T0', st.session_state['labels'], None)
""")
    app.session_state["analysis"] = analysis
    app.session_state["labels"] = {
        f"{prefix}{i}": f"Nick{prefix}{i}" for prefix in ("T", "C") for i in range(5)
    }
    app.session_state["map_facts_" + round_facts_key(analysis)] = [item]
    app.run(timeout=20)
    assert not app.exception
    assert any("Cele prób" in m.value for m in app.markdown)
    next(s for s in app.selectbox if s.label == "Drużyna").select_index(1).run()
    next(r for r in app.radio if r.label == "Strona drużyny").set_value("CT").run()
    assert not app.exception
    assert any("Aktywność CT" in m.value for m in app.markdown)
    next(r for r in app.radio if r.label == "Zakres obserwacji").set_value("Wybrany gracz").run()
    assert not app.exception
