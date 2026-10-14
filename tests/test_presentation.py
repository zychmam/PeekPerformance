"""Player-facing match tables and exports use nicknames without exposing SteamIDs."""

from __future__ import annotations

import pandas as pd

from src.demos.presentation import player_labels, presentation_frame

FIRST = "76561198008873401"
SECOND = "76561198008873402"


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
