"""Display projections retain round context and hide technical identifiers."""

from __future__ import annotations

import pandas as pd

from src.demos.match_view import (
    kill_events_table,
    player_rounds_table,
    player_summary_table,
)
from src.models.models import DemoAnalysis

FIRST = "76561198008873401"
SECOND = "76561198008873402"


def _analysis() -> DemoAnalysis:
    return DemoAnalysis(
        file_name="match.dem",
        player_info=pd.DataFrame([
            {"steamid": FIRST, "name": "Ace"},
            {"steamid": SECOND, "name": "Ace"},
        ]),
        scoreboard=pd.DataFrame([
            {"steam_id": FIRST, "player_name": "Ace", "kills_total": 2,
             "deaths_total": 1, "assists_total": 1, "team_num": 2},
            {"steam_id": SECOND, "player_name": "Ace", "kills_total": 0,
             "deaths_total": 2, "assists_total": 0, "team_num": 3},
        ]),
        rounds_df=pd.DataFrame([
            {"total_rounds_played": 1, "winner": 2},
            {"total_rounds_played": 2, "winner": 3},
            {"total_rounds_played": 3, "winner": 2},
        ]),
        round_stats_df=pd.DataFrame([
            {"steamid": FIRST, "total_rounds_played": 1, "kills": 1,
             "deaths": 0, "damage": 75},
            {"steamid": FIRST, "total_rounds_played": 2, "kills": 1,
             "deaths": 1, "damage": 101},
            {"steamid": FIRST, "total_rounds_played": 3, "kills": 0,
             "deaths": 0, "damage": 0},
        ]),
        kills_df=pd.DataFrame([
            {"total_rounds_played": 1, "tick": 10,
             "attacker_steamid": FIRST, "attacker_team_num": 3,
             "user_steamid": SECOND, "user_team_num": 2,
             "assister_steamid": "", "weapon": "ak47", "headshot": True},
            {"total_rounds_played": 2, "tick": 20,
             "attacker_steamid": SECOND, "attacker_team_num": 3,
             "user_steamid": FIRST, "user_team_num": 2,
             "assister_steamid": FIRST, "weapon": "m4a1", "headshot": False},
        ]),
    )


def test_player_summary_has_exactly_five_display_columns() -> None:
    analysis = _analysis()
    rated = pd.DataFrame([
        {"steamid": SECOND, "Rating": 0.7, "ADR": 42, "KAST%": 50},
        {"steamid": FIRST, "Rating": 1.3, "ADR": 88, "KAST%": 75},
    ])
    view = player_summary_table(analysis, rated)

    assert view.columns.tolist() == ["Gracz", "Rating", "K/D/A", "ADR", "KAST"]
    assert view.iloc[0].to_dict() == {
        "Gracz": "Ace (1)", "Rating": 1.3, "K/D/A": "2/1/1", "ADR": 88,
        "KAST": 75,
    }
    assert FIRST not in view.to_string() and SECOND not in view.to_string()


def test_player_rounds_never_uses_final_scoreboard_side() -> None:
    view = player_rounds_table(_analysis(), FIRST)

    assert view.columns.tolist() == [
        "Runda", "Wygrana strona", "Strona gracza", "K/D/A", "Obrażenia",
    ]
    assert view["Wygrana strona"].tolist() == ["T", "CT", "T"]
    assert view["Strona gracza"].tolist() == ["CT", "T", "—"]
    assert view["K/D/A"].tolist() == ["1/0/0", "1/1/1", "0/0/0"]
    assert view["Obrażenia"].tolist() == [75, 101, 0]
    assert FIRST not in view.to_string()


def test_missing_data_does_not_invent_a_player_side() -> None:
    analysis = _analysis()
    analysis.round_stats_df = pd.DataFrame()
    analysis.kills_df = pd.DataFrame()
    view = player_rounds_table(analysis, FIRST)

    assert view["Strona gracza"].tolist() == ["—"] * 3
    assert view["Wygrana strona"].tolist() == ["T", "CT", "T"]
    assert view["K/D/A"].tolist() == ["—"] * 3
    assert view["Obrażenia"].isna().all()


def test_conflicting_side_evidence_is_unknown() -> None:
    analysis = _analysis()
    analysis.damage_df = pd.DataFrame([{
        "total_rounds_played": 1, "attacker_steamid": FIRST,
        "attacker_team_num": 2,
    }])
    view = player_rounds_table(analysis, FIRST)

    assert view.loc[0, "Strona gracza"] == "—"
    assert view.loc[1, "Strona gracza"] == "T"


def test_short_kill_feed_hides_ids_and_coordinates() -> None:
    view = kill_events_table(_analysis(), 1)

    assert view.columns.tolist() == ["Atakujący", "Ofiara", "Broń", "HS"]
    assert view.iloc[0].to_dict() == {
        "Atakujący": "Ace (1)", "Ofiara": "Ace (2)",
        "Broń": "ak47", "HS": True,
    }
    assert FIRST not in view.to_string() and SECOND not in view.to_string()
