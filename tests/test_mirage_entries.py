"""Entry evidence and limits; these expectations do not infer team intentions."""

from types import SimpleNamespace

import pandas as pd
from streamlit.testing.v1 import AppTest

from tests.map_support import MirageContext
from src.demos.site_entries import detect_entries
from tests.map_support import entry_route
from src.models.models import DemoAnalysis


def example():
    clock = pd.DataFrame([{"total_rounds_played": 1, "freeze_tick": 0, "tick": 1500}])
    records = []
    for tick in range(0, 1501, 64):
        for sid, team in (("t1", 2), ("t2", 2), ("ct1", 3), ("ct2", 3)):
            place = ("TRamp" if tick < (640 if sid == "t1" else 768) else "BombsiteA")
            if team == 3:
                place = "BombsiteA" if sid == "ct1" else "Connector"
            records.append({"total_rounds_played": 1, "tick": tick, "steamid": sid,
                            "team_num": team, "is_alive": True, "last_place_name": place,
                            "seconds": tick/64, "X": 200, "Y": -1550, "Z": -175,
                            "has_bomb": sid == "t2"})
    utility = pd.DataFrame([
        {"total_rounds_played": 1, "tick": tick, "kind": "Flash",
         "user_team_num": 2, "user_steamid": "t2", "x": 0, "y": 0, "z": 0}
        for tick in (100, 300, 700)
    ])
    analysis = DemoAnalysis(file_name="test.dem", round_roster_df=pd.DataFrame([
        {"total_rounds_played": 1, "steamid": "ct1", "team_num": 3},
        {"total_rounds_played": 1, "steamid": "ct2", "team_num": 3},
    ]))
    return MirageContext(clock, pd.DataFrame(records), utility, {}), analysis


def test_group_routes_bomb_defence_and_utility_window():
    context, analysis = example()
    entries = detect_entries(context, analysis)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["tick"] == 640
    assert entry["routes"] == {"Rampa A": 2}
    assert [p["tick"] for p in entry["participants"]] == [640, 768]
    assert entry["ct_before"]["site_count"] == entry["ct_during"]["site_count"] == 1
    assert entry["ct_during"]["support_count"] == 1
    assert entry["ct_during"]["complete"]
    assert entry["bomb_carriers"][0]["steamid"] == "t2"
    assert [e["tick"] for e in entry["utility_before"]] == [300]
    restored = MirageContext.from_json(context.to_json())
    assert detect_entries(restored, analysis) == entries


def test_partial_ct_does_not_claim_complete_count_and_plant_cuts_off_arrivals():
    context, analysis = example()
    context.states = context.states[context.states.steamid.ne("ct2")]
    analysis.bomb_events_df = pd.DataFrame([
        {"event": "bomb_planted", "total_rounds_played": 1, "tick": 700},
    ])
    entries = detect_entries(context, analysis)
    assert len(entries[0]["participants"]) == 1
    assert not entries[0]["ct_during"]["complete"]


def test_gap_and_short_visit_do_not_confirm_entry():
    context, analysis = example()
    # t1 has a brief site blip, t2 disappears before reappearing inside the site.
    context.states.loc[context.states.steamid.eq("t1") & context.states.tick.gt(640),
                       "last_place_name"] = "TRamp"
    from src.maps.resolver import annotate_frame
    context.states = annotate_frame(context.states, context.profile)
    context.states = context.states[~(context.states.steamid.eq("t2")
                                      & context.states.tick.between(600, 1000))]
    assert detect_entries(context, analysis) == []


def test_route_disambiguates_ground_level_palace_label_and_height():
    assert entry_route("A", SimpleNamespace(last_place_name="PalaceInterior",
                                            X=176, Y=-1498, Z=-176)) == "Rampa A"
    assert entry_route("A", SimpleNamespace(last_place_name="Scaffolding",
                                            X=0, Y=-2100, Z=-40)) == "Pałac"
    assert entry_route("A", SimpleNamespace(last_place_name="PalaceInterior",
                                            X=0, Y=-2100, Z=-175)) != "Pałac"
    assert entry_route("B", SimpleNamespace(last_place_name="Catwalk")) == "Short"


def test_entry_panel_shows_observations_without_player_ids():
    context, analysis = example()
    context.entries = detect_entries(context, analysis)
    app = AppTest.from_string('''
import streamlit as st
from src.gui.round_context_view import _entry_panel
_entry_panel(st.session_state['context'], st.session_state['analysis'], 1,
             {'t1':'Alice', 't2':'Bob', 'ct1':'Carol', 'ct2':'Dan'})
''')
    app.session_state["context"] = context
    app.session_state["analysis"] = analysis
    app.run()
    assert not app.exception
    assert len(app.selectbox) == 1
    assert app.dataframe[0].value["Gracz"].tolist() == ["Alice", "Bob"]
    assert not any("steamid" in c for table in app.dataframe for c in table.value.columns)
