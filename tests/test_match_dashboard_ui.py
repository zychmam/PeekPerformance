"""The Streamlit match view defaults to a compact, usable overview."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.config import Config
from src.demos.versions import ANALYSIS_VERSION, METRICS_VERSION
from src.models.models import DemoAnalysis


def test_match_dashboard_shows_compact_overview_and_round_details(tmp_path: Path) -> None:
    player = "76561198008873401"
    opponent = "76561198008873402"
    analysis = DemoAnalysis(
        file_name="match.dem", content_hash="match-hash", map_name="de_mirage",
        player_info=pd.DataFrame([
            {"steamid": player, "name": "Alice"},
            {"steamid": opponent, "name": "Bob"},
        ]),
        scoreboard=pd.DataFrame([
            {"steam_id": player, "kills_total": 1, "deaths_total": 0,
             "assists_total": 0, "player_name": "Alice", "tick": 100},
            {"steam_id": opponent, "kills_total": 0, "deaths_total": 1,
             "assists_total": 0, "player_name": "Bob", "tick": 100},
        ]),
        rounds_df=pd.DataFrame([{
            "total_rounds_played": 1, "winner": 3, "start_tick": 10, "tick": 100,
        }]),
        round_stats_df=pd.DataFrame([
            {"steamid": player, "total_rounds_played": 1, "kills": 1,
             "deaths": 0, "damage": 75, "utility_damage": 0},
        ]),
        kills_df=pd.DataFrame([{
            "total_rounds_played": 1, "tick": 50,
            "attacker_steamid": player, "attacker_team_num": 3,
            "user_steamid": opponent, "user_team_num": 2,
            "weapon": "ak47", "headshot": True,
        }]),
    )
    summary = pd.DataFrame([
        {"steamid": player, "Rating": 1.2, "K": 1, "D": 0, "A": 0,
         "ADR": 75, "KAST%": 100, "HS%": 100, "KPR": 1, "DPR": 0,
         "Avg Swing": 12},
    ])
    config = Config(db_path=str(tmp_path / "matches.db"), demos_dir=str(tmp_path / "demos"))
    app_path = Path(__file__).resolve().parents[1] / "src" / "gui" / "app.py"
    app = AppTest.from_file(str(app_path))
    app.session_state["current_demo_analysis"] = analysis
    app.session_state[f"rating_match-hash_a{ANALYSIS_VERSION}_m{METRICS_VERSION}"] = (
        summary, analysis.round_stats_df.rename(columns={"total_rounds_played": "Runda"})
    )

    with patch.object(Config, "load", return_value=config):
        app.run(timeout=30)
        assert not app.exception
        assert app.radio[0].value == "Przegląd"
        assert app.dataframe[0].value.columns.tolist() == [
            "Gracz", "Rating", "K/D/A", "ADR", "KAST"
        ]
        assert len(app.dataframe) == 1

        app.radio[0].set_value("Rundy").run(timeout=30)
        assert not app.exception
        assert app.dataframe[0].value.columns.tolist() == [
            "Runda", "Wygrana strona", "Strona gracza", "K/D/A", "Obrażenia"
        ]
        assert app.dataframe[1].value.columns.tolist() == [
            "Atakujący", "Ofiara", "Broń", "HS"
        ]
