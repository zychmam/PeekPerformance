"""Tests for DemoAnalyzer with mocked DemoParser."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.demos.demo_analyzer import DemoAnalyzer
from src.models.models import DemoAnalysis


@pytest.fixture()
def demo_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.dem"
    p.write_bytes(b"FAKE")
    return p


@pytest.fixture()
def mock_parser() -> MagicMock:
    parser = MagicMock()
    parser.parse_header.return_value = {"map_name": "de_dust2", "server_name": "Test"}
    parser.parse_player_info.return_value = pd.DataFrame(
        [{"steamid": "111", "name": "Alice"}, {"steamid": "222", "name": "Bob"}]
    )
    parser.parse_chat_messages.return_value = pd.DataFrame(
        [{"param1": "Alice", "param2": "gg"}]
    )
    parser.parse_convars.return_value = {"sv_cheats": "0"}
    parser.list_game_events.return_value = ["player_death", "player_hurt", "round_end"]
    parser.parse_event.return_value = pd.DataFrame()
    parser.parse_ticks.return_value = pd.DataFrame()
    parser.parse_grenades.return_value = pd.DataFrame()
    return parser


class TestDemoAnalyzerHeader:
    @patch("src.demos.demo_analyzer.DemoParser")
    def test_get_header(self, mock_cls: MagicMock, demo_path: Path, mock_parser: MagicMock) -> None:
        mock_cls.return_value = mock_parser
        analyzer = DemoAnalyzer(demo_path)
        header = analyzer.get_header()
        assert header["map_name"] == "de_dust2"
        mock_parser.parse_header.assert_called_once()


class TestDemoAnalyzerPlayerInfo:
    @patch("src.demos.demo_analyzer.DemoParser")
    def test_get_player_info(self, mock_cls: MagicMock, demo_path: Path, mock_parser: MagicMock) -> None:
        mock_cls.return_value = mock_parser
        analyzer = DemoAnalyzer(demo_path)
        info = analyzer.get_player_info()
        assert len(info) == 2
        assert "Alice" in info["name"].values


class TestDemoAnalyzerChatMessages:
    @patch("src.demos.demo_analyzer.DemoParser")
    def test_get_chat_messages(self, mock_cls: MagicMock, demo_path: Path, mock_parser: MagicMock) -> None:
        mock_cls.return_value = mock_parser
        analyzer = DemoAnalyzer(demo_path)
        chat = analyzer.get_chat_messages()
        assert not chat.empty
        assert "gg" in chat["param2"].values


class TestDemoAnalyzerFullAnalysis:
    @patch("src.demos.demo_analyzer.DemoParser")
    def test_full_analysis_returns_demo_analysis(
        self, mock_cls: MagicMock, demo_path: Path, mock_parser: MagicMock
    ) -> None:
        mock_cls.return_value = mock_parser
        analyzer = DemoAnalyzer(demo_path)
        result = analyzer.get_full_analysis()
        assert isinstance(result, DemoAnalysis)
        assert result.file_name == "test.dem"
        assert result.map_name == "de_dust2"

    @patch("src.demos.demo_analyzer.DemoParser")
    def test_full_analysis_graceful_on_errors(
        self, mock_cls: MagicMock, demo_path: Path, mock_parser: MagicMock
    ) -> None:
        """Methods that fail should return empty DataFrames, not crash."""
        mock_parser.parse_event.side_effect = Exception("parse error")
        mock_parser.parse_grenades.side_effect = Exception("grenade error")
        mock_parser.parse_ticks.side_effect = Exception("tick error")
        mock_cls.return_value = mock_parser
        analyzer = DemoAnalyzer(demo_path)
        result = analyzer.get_full_analysis()
        assert isinstance(result, DemoAnalysis)
        assert result.kills_df.empty
        assert result.grenades_df.empty
        assert result.scoreboard.empty


class TestDemoAnalyzerListEvents:
    @patch("src.demos.demo_analyzer.DemoParser")
    def test_list_events(self, mock_cls: MagicMock, demo_path: Path, mock_parser: MagicMock) -> None:
        mock_cls.return_value = mock_parser
        analyzer = DemoAnalyzer(demo_path)
        events = analyzer.list_events()
        assert "player_death" in events

    @patch("src.demos.demo_analyzer.DemoParser")
    def test_list_events_graceful_on_error(self, mock_cls: MagicMock, demo_path: Path, mock_parser: MagicMock) -> None:
        mock_parser.list_game_events.side_effect = Exception("fail")
        mock_cls.return_value = mock_parser
        analyzer = DemoAnalyzer(demo_path)
        events = analyzer.list_events()
        assert events == []
