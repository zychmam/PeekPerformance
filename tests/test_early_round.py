"""R2 gap, boundary and real recorded setup checks."""

import json
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.demos.early_round import _movements as _moves, area as _area, enrich_early_round
from src.maps.registry import get_profile

def _movements(samples, player):
    return _moves(samples, player, profile=get_profile("de_mirage"))

def area(data):
    return _area(data, get_profile("de_mirage"))
from tests.map_support import MirageContext, context_key
from src.demos.tactical_rounds import build_tactical_match
from src.models.models import DemoAnalysis
from src.models.tactical import (
    Availability,
    Evidence,
    PlayerRound,
    RoundTactics,
    Status,
    TacticalMatch,
)


def sample(tick, place, alive=True, pid="P0"):
    return Evidence(f"{pid}:{tick}", "states", 1, tick, tick/64, {
        "steamid": pid, "team_num": 3, "is_alive": alive,
        "last_place_name": place, "X": 0, "Y": 0, "Z": 0,
    })


def test_transition_requires_confirmation_and_resets_after_gap_or_death():
    transient = [sample(0, "BombsiteA"), sample(64, "Connector"), sample(128, "BombsiteA")]
    assert not _movements(transient, "P0")
    confirmed = transient + [sample(192, "Connector"), sample(256, "Connector")]
    move, = _movements(confirmed, "P0")
    assert (move.from_area, move.to_area, move.arrival_tick, move.confirmed_tick) == (
        "site_a", "connector", 192, 256,
    )
    for middle in (sample(64, "Connector", False), sample(256, "Connector")):
        assert not _movements([sample(0, "BombsiteA"), middle,
                               sample(middle.tick+64, "Connector")], "P0")


def test_ambiguous_palace_and_connectors_are_not_site_defenders():
    assert area(sample(0, "Connector").data) == "connector"
    assert area(sample(0, "PalaceInterior").data) is None
    assert area({"last_place_name": "PalaceInterior", "X": 176,
                 "Y": -1498, "Z": -176}) == "ramp_a"
    assert area({"last_place_name": "PalaceInterior", "X": 0,
                 "Y": -2200, "Z": 0}) == "palace"


def test_complete_setup_verified_no_movement_and_stale_missing_not_zero():
    evidence = {}
    for pid in [f"P{i}" for i in range(5)]:
        for tick in range(0, 961, 64):
            ev = sample(tick, "BombsiteA", pid=pid)
            evidence[ev.id] = ev
    rnd = RoundTactics(1, 0, 2000, 0, {}, None, None, None,
                       {"utility": Availability(Status.ABSENT)}, list(evidence),
                       players=[PlayerRound(f"P{i}", "team_1", "CT") for i in range(5)])
    enrich_early_round(rnd, evidence, "de_mirage")
    assert rnd.ct_setup.status == Status.OBSERVED
    assert rnd.ct_setup.movement_status == Status.ABSENT
    assert [s.counts for s in rnd.ct_setup.snapshots] == [{"site_a": 5}]*4
    # An entire missing player is not presented as a complete four-player setup.
    rnd.event_ids = [eid for eid in evidence if not eid.startswith("P4:")]
    enrich_early_round(rnd, evidence, "de_mirage")
    assert rnd.ct_setup.status == Status.PARTIAL
    assert rnd.ct_setup.snapshots[-1].missing_players == ["P4"]
    assert rnd.ct_setup.movement_status == Status.PARTIAL
    rnd.event_ids = [eid for eid in rnd.event_ids if evidence[eid].tick < 128]
    enrich_early_round(rnd, evidence, "de_mirage")
    assert rnd.ct_setup.snapshots[-1].status == Status.UNKNOWN
    assert rnd.ct_setup.snapshots[-1].counts == {}


def reference():
    data = json.loads((Path(__file__).parent / "reference" /
                       "mirage_tactical_facts.json").read_text(encoding="utf-8"))
    analysis = DemoAnalysis(file_name="mirage.dem", map_name="de_mirage",
                            content_hash=data["provenance"]["demo_hash"],
                            analysis_version=data["analysis_version"],
                            **{key: pd.DataFrame(rows) for key, rows in data["frames"].items()})
    return analysis, MirageContext.from_json(json.dumps(data["spatial"]))


def test_recorded_early_mirage_counts_and_utility_have_source_proof():
    match = build_tactical_match(*reference())
    expected = json.loads((Path(__file__).parent / "reference" /
                           "mirage_tactical_expectations.json").read_text(encoding="utf-8"))
    for case in expected["cases"]:
        record = next(r for r in match.rounds if r.number == case["round"])
        reviewed = case["early_observations"]
        from collections import Counter
        from src.maps.registry import get_profile
        profile = get_profile("de_mirage")
        grouped = Counter()
        for rid, count in next(s for s in record.ct_setup.snapshots if s.seconds == 10).counts.items():
            region = profile.regions_by_id[rid]
            category = region.site_id or region.kind
            if category in {"connector", "spawn"}:
                category += " / " + region.nav_labels[0]
            grouped[category] += count
        assert dict(grouped) == reviewed["ct_counts_at_10_seconds"]
        assert len(record.t_preparation.utility)+len(record.ct_setup.utility) == (
            reviewed["utility_effects_0_to_15_seconds_both_sides"]
        )
    rnd = next(r for r in match.rounds if r.number == 1)
    snap = next(s for s in rnd.ct_setup.snapshots if s.seconds == 10)
    # Independently reviewed raw records: A=2, B=2, SnipersNest=1 at tick7468.
    assert snap.counts == {"site_a": 2, "site_b": 2, "window": 1}
    assert snap.status == Status.OBSERVED
    flash, = rnd.t_preparation.utility
    assert (flash.player_id, flash.kind, flash.tick, flash.seconds) == (
        "P01", "Flash", 7533, 11.015625,
    )
    assert match.evidence[flash.evidence_ids[0]].source == "utility"
    assert rnd.ct_setup.movement_status == Status.PARTIAL  # Sparse reference, 5s gaps.
    assert TacticalMatch.from_dict(json.loads(json.dumps(match.to_dict()))).to_dict() == (
        match.to_dict()
    )
    # 15s includes its boundary, excludes later detonations.
    assert all(0 <= u.seconds <= 15 for r in match.rounds
               for p in (r.t_preparation, r.ct_setup) for u in p.utility)


def test_early_view_uses_nicks_and_jump_updates_radar_without_rebuilding():
    analysis, context = reference()
    app = AppTest.from_string('''
import streamlit as st
from src.gui.round_context_view import render_round_context
render_round_context(st.session_state['analysis'], 'P01', None)
''')
    app.session_state["analysis"] = analysis
    app.session_state[f"spatial_{context_key(analysis)}_{context.profile.presentation_fingerprint}_1"] = context
    app.run(timeout=30)
    assert not app.exception
    assert any("Początek rundy" in m.value for m in app.markdown)
    assert any("podsumowanie przygotowania" in m.value for m in app.markdown)
    assert any("Interpretacja:" in m.value for m in app.markdown)
    next(w for w in app.selectbox if w.label == "Moment ustawienia").set_value(5).run()
    next(b for b in app.button if b.label == "Pokaż ustawienie na mapie").click().run()
    assert not app.exception
    assert app.slider[0].value == 5.0
    for table in app.dataframe:
        assert not any("steamid" in str(c).lower() for c in table.value.columns)
