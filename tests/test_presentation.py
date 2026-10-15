"""Player-facing match tables and exports use nicknames without exposing SteamIDs."""

from __future__ import annotations

import pandas as pd

from src.demos.presentation import player_labels, presentation_frame

FIRST = "76561198008873401"
SECOND = "76561198008873402"


def test_round_event_tables_share_saved_clock_and_keep_unknown_clock_explicit():
    from src.demos.match_view import display_metric_clock, kill_events_table
    from src.demos.observations import observations_key
    from src.gui.match_dashboard import _round_damage_events
    from src.models.models import DemoAnalysis

    events = pd.DataFrame([
        {"tick": tick, "attacker_steamid": FIRST, "attacker_team_num": 3,
         "user_steamid": SECOND, "user_team_num": 2, "weapon": "ak47",
         "dmg_health": 100, "health": 0, "total_rounds_played": 1}
        for tick in (20, 50, 100, 101)
    ])
    analysis = DemoAnalysis("test.dem", player_info=_players(), kills_df=events,
        damage_df=events, rounds_df=pd.DataFrame([
            {"total_rounds_played": 1, "start_tick": 10, "tick": 100},
        ]))
    original_key = observations_key(analysis)
    analysis.metrics_clock_df = pd.DataFrame([{"tick": 100, "freeze_tick": 50}])
    assert observations_key(analysis) == original_key
    assert len(kill_events_table(analysis, 1)) == 2  # Inclusive freeze/end, no post-round event.
    damage = _round_damage_events(analysis, 1)
    assert damage["Obrażenia"].sum() == 100  # Pre-freeze HP consumption cannot suppress damage.
    analysis.metrics_clock_df = pd.DataFrame()
    assert display_metric_clock(analysis).iloc[0].metrics_clock_status == "unknown"
    assert len(kill_events_table(analysis, 1)) == 3  # Unknown clock preserves the completed window.


def _players() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"steamid": FIRST, "name": "Ace"},
            {"steamid": SECOND, "name": "Ace"},
        ]
    )


def test_duplicate_nicknames_remain_distinct_without_visible_ids() -> None:
    labels = player_labels(_players())
    assert set(labels.values()) == {"Ace (1)", "Ace (2)"}
    events = pd.DataFrame(
        [
            {
                "attacker_steamid": FIRST,
                "attacker_name": "Ace",
                "user_steamid": SECOND,
                "user_name": "Ace",
                "damage": 45,
            },
            {
                "attacker_steamid": SECOND,
                "attacker_name": "Ace",
                "user_steamid": FIRST,
                "user_name": "Ace",
                "damage": 30,
            },
        ]
    )
    view = presentation_frame(events, _players())
    assert view["Atakujący"].tolist() == ["Ace (1)", "Ace (2)"]
    assert view["Trafiony gracz"].tolist() == ["Ace (2)", "Ace (1)"]
    assert not any("steamid" in str(column).lower() for column in view)
    assert FIRST not in view.to_string(index=False)
    assert SECOND not in view.to_string(index=False)


def test_round_stats_use_nickname_as_first_column() -> None:
    stats = pd.DataFrame(
        [
            {"total_rounds_played": 1, "steamid": FIRST, "kills": 2},
            {"total_rounds_played": 1, "steamid": SECOND, "kills": 1},
        ]
    )
    view = presentation_frame(stats, _players())
    assert view.columns[0] == "Gracz"
    assert view["Gracz"].tolist() == ["Ace (1)", "Ace (2)"]
