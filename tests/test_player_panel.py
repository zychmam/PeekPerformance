"""A tracked player sees persisted match ratings without reopening demo files."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from src.config import Config
from src.demos.presentation import is_steam_id_column
from src.demos.rating_calculator import RATING_VERSION
from src.models.models import DemoAnalysis
from src.storage.database import Database


def test_tracked_player_panel_reads_saved_match_rating(tmp_path: Path) -> None:
    config = Config(db_path=str(tmp_path / "matches.db"), demos_dir=str(tmp_path / "demos"))
    db = Database(config.db_path)
    db.upsert_demo_analysis(DemoAnalysis(
        file_name="match.dem", content_hash="match-hash", map_name="de_anubis",
        player_info=pd.DataFrame([{"steamid": "76561198008873401", "name": "Alice"}]),
    ))
    db.track_player("76561198008873401")
    db.save_demo_ratings("match-hash", pd.DataFrame([{
        "steamid": "76561198008873401", "Rating": 1.23,
        "K": 19, "D": 14, "ADR": 83.5,
    }]), rating_version=RATING_VERSION)

    with patch.object(Config, "load", return_value=config):
        app_path = Path(__file__).resolve().parents[1] / "src" / "gui" / "app.py"
        with patch.object(
            Database, "get_demo_analysis",
            side_effect=AssertionError("full JSON loaded"),
        ):
            app = AppTest.from_file(str(app_path)).run(timeout=30)

    assert not app.exception
    assert app.sidebar.radio[0].value == "Mecze gracza"
    assert any("Mecze gracza: Alice" in header.value for header in app.header)
    table = app.dataframe[0].value
    assert table.loc[0, "Mapa"] == "de_anubis"
    assert table.loc[0, "Peek rating"] == 1.23
    assert table.loc[0, "K"] == 19
    open_button = next(
        button for button in app.button if button.label == "Otwórz analizę meczu"
    )
    with patch.object(Config, "load", return_value=config):
        app = open_button.click().run(timeout=30)
    assert app.sidebar.radio[0].value == "Analiza demo"
    assert any(header.value == "Analiza meczu" for header in app.header)
    assert all("session_state" not in error.message for error in app.exception)
    assert any(header.value == "de_anubis" for header in app.subheader)
    for table in app.dataframe:
        assert not any(is_steam_id_column(column) for column in table.value.columns)
