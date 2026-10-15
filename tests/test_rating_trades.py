"""KAST trade credit agrees with the tactical detector, independently of swing sharing."""

import pandas as pd
import pytest

from src.demos.rating_calculator import compute_rating_from_events
from src.demos.round_refrags import enrich_refrags
from tests.test_round_refrags import _fixture, _kill


def calculate(events, rate=64):
    record, evidence = _fixture(end=2000)
    for i, (tick, attacker, victim) in enumerate(events):
        _kill(record, evidence, str(i), tick, attacker, victim)
    enrich_refrags(record, evidence, tick_rate=rate, response_seconds=5)
    roster = pd.DataFrame([
        {"steamid": p.player_id, "team_num": 2 if p.side == "T" else 3,
         "total_rounds_played": 1} for p in record.players
    ])
    kills = pd.DataFrame([{**e.data, "tick": e.tick} for e in evidence.values()])
    summary, per_round = compute_rating_from_events(
        pd.DataFrame([{"steamid": p.player_id, "name": p.player_id} for p in record.players]),
        kills, pd.DataFrame(),
        pd.DataFrame([{"total_rounds_played": 1, "start_tick": 0,
                       "freeze_tick": 0, "tick": record.end_tick, "winner": 2}]),
        pd.DataFrame(), roster=roster, tick_rate=rate,
    )
    return record, evidence, summary.set_index("steamid"), per_round.set_index("steamid")


def test_one_reply_credits_both_victims_without_multiplying_swing_reward():
    record, _, summary, rows = calculate([
        (100, "c0", "t0"), (150, "c0", "t1"), (200, "t2", "c0"),
    ])
    assert len(record.refrag_links) == 2
    assert len({r.response_kill_id for r in record.refrag_links}) == 1
    assert rows.loc[["t0", "t1"], "kast"].tolist() == [1, 1]
    assert summary.loc[["t0", "t1"], "KAST%"].tolist() == [100, 100]
    assert rows.loc["t2", "kills"] == 1
    # Existing heuristic: one trade reward goes to the most recently killed teammate.
    assert rows.loc["t0", "Swing"] == pytest.approx(-22, abs=0.005)
    assert rows.loc["t1", "Swing"] == pytest.approx(-15 + 14 * .2 / .85, abs=0.005)


@pytest.mark.parametrize("rate,reply,expected", [
    (64, 420, 1), (64, 421, 0), (128, 740, 1), (128, 741, 0),
])
def test_five_second_boundary_matches_tactical_detector(rate, reply, expected):
    record, _, _, rows = calculate([(100, "c0", "t0"), (reply, "t1", "c0")], rate)
    assert len(record.refrag_links) == expected
    assert rows.loc["t0", "kast"] == expected


@pytest.mark.parametrize("events", [
    [(100, "c0", "t0"), (100, "t1", "c0")],
    [(100, "t1", "c0"), (100, "c0", "t0")],
    [(100, "c0", "t0"), (150, "t1", "c1")],
])
def test_simultaneous_or_wrong_killer_kills_do_not_credit_trade(events):
    record, _, _, rows = calculate(events)
    assert record.refrag_links == []
    assert rows.loc["t0", "kast"] == 0


def test_duplicate_death_does_not_duplicate_trade_or_counters():
    record, _, _, rows = calculate([
        (100, "c0", "t0"), (100, "c0", "t0"),
        (150, "c0", "t1"), (200, "t2", "c0"),
    ])
    assert len(record.refrag_links) == 2
    assert rows.loc["c0", "kills"] == 2
    assert rows.loc[["t0", "t1"], "deaths"].tolist() == [1, 1]
    assert rows.loc[["t0", "t1"], "kast"].tolist() == [1, 1]


def test_round_fight_table_distinguishes_reply_kills_from_traded_deaths():
    from streamlit.testing.v1 import AppTest

    from tests.test_tactical_actions import build, kill

    record, evidence, profile, _ = build(
        {"T0": lambda t: "aa", "T1": lambda t: "aa", "T2": lambda t: "aa"},
        [kill("d1", 20, "C0", "T0"), kill("d2", 21, "C0", "T1"),
         kill("reply", 22, "T2", "C0")],
    )
    app = AppTest.from_string("""
import streamlit as st
from src.gui.round_tactical_view import render_tactical_actions
render_tactical_actions(st.session_state['record'], st.session_state['evidence'],
    {}, st.session_state['profile'], 'T2', 10, 'time', 60)
""")
    app.session_state["record"] = record
    app.session_state["evidence"] = evidence
    app.session_state["profile"] = profile
    app.run(timeout=20)
    assert not app.exception
    frame = next(d.value for d in app.dataframe if "Fragi wymieniające" in d.value)
    assert frame["Fragi wymieniające"].sum() == 1
    assert frame["Wymienione zgony"].sum() == 2
