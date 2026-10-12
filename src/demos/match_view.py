"""Small, player-facing projections of one parsed match.

The frames returned here contain display values only. SteamIDs remain keys used
to join parser data, and a side is shown only when an event proves it for that
player in that particular round.
"""

from __future__ import annotations

import pandas as pd

from src.demos.presentation import presentation_frame
from src.models.models import DemoAnalysis


def _number(frame: pd.DataFrame, column: str, default: float = 0) -> pd.Series:
    if column not in frame:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _side(value: object) -> str:
    if pd.isna(value):
        return "—"
    return {2: "T", 3: "CT", "2": "T", "3": "CT", "T": "T",
            "CT": "CT", "TERRORIST": "T"}.get(value, "—")


def player_summary_table(
    analysis: DemoAnalysis, rating_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Use the same canonical summary as player cards and the stored rating."""
    columns = ["Gracz", "Rating", "K/D/A", "ADR", "KAST"]
    if not rating_summary.empty and {"steamid", "K", "D", "A"}.issubset(rating_summary):
        view = presentation_frame(rating_summary, analysis.player_info).copy()
        view["K/D/A"] = (
            view["K"].astype(int).astype(str) + "/"
            + view["D"].astype(int).astype(str) + "/"
            + view["A"].astype(int).astype(str)
        )
        view["KAST"] = view.get("KAST%", float("nan"))
        for field in ("Rating", "ADR"):
            if field not in view:
                view[field] = float("nan")
        return view[columns].sort_values(
            ["Rating", "Gracz"], ascending=[False, True], na_position="last"
        ).reset_index(drop=True)
    source = analysis.scoreboard
    if source.empty or "steam_id" not in source:
        return pd.DataFrame(columns=columns)

    ids = source["steam_id"].astype("string")
    names = presentation_frame(source[["steam_id"]], analysis.player_info)["Gracz"]
    main = pd.DataFrame({
        "Gracz": names,
        "K/D/A": (
            _number(source, "kills_total").astype(int).astype(str) + "/"
            + _number(source, "deaths_total").astype(int).astype(str) + "/"
            + _number(source, "assists_total").astype(int).astype(str)
        ),
    })
    main["Rating"] = float("nan")
    main["ADR"] = float("nan")
    main["KAST"] = float("nan")
    if not rating_summary.empty and "steamid" in rating_summary:
        rated = rating_summary.copy()
        rated["steamid"] = rated["steamid"].astype("string")
        rated = rated.drop_duplicates("steamid").set_index("steamid")
        for rating_col, display_col in (("Rating", "Rating"), ("ADR", "ADR"),
                                        ("KAST%", "KAST")):
            if rating_col in rated:
                main[display_col] = pd.to_numeric(
                    ids.map(rated[rating_col]), errors="coerce"
                )
    if main["ADR"].isna().any():
        stats = analysis.round_stats_df
        if not stats.empty and {"steamid", "damage"}.issubset(stats):
            adr = stats.assign(steamid=stats["steamid"].astype("string"))
            adr = adr.groupby("steamid")["damage"].mean()
            main["ADR"] = main["ADR"].fillna(ids.map(adr))
    main = main[columns].sort_values(
        ["Rating", "Gracz"], ascending=[False, True], na_position="last",
    )
    return main.reset_index(drop=True)


def _event_side(analysis: DemoAnalysis, player_id: str) -> dict[int, str]:
    """Infer this player's side from their own events, never final scoreboard side."""
    evidence: dict[int, set[str]] = {}
    for events in (analysis.kills_df, analysis.damage_df):
        if events.empty or "total_rounds_played" not in events:
            continue
        for id_col, side_col in (
            ("attacker_steamid", "attacker_team_num"),
            ("user_steamid", "user_team_num"),
        ):
            if id_col not in events or side_col not in events:
                continue
            selected = events[events[id_col].astype("string").eq(player_id)]
            for round_number, side_value in zip(
                selected["total_rounds_played"], selected[side_col], strict=False,
            ):
                side = _side(side_value)
                if pd.notna(round_number) and side != "—":
                    evidence.setdefault(int(round_number), set()).add(side)
    return {round_number: next(iter(sides)) for round_number, sides in evidence.items()
            if len(sides) == 1}


def player_rounds_table(analysis: DemoAnalysis, player_id: str) -> pd.DataFrame:
    """Completed rounds with winner side and the selected player's round metrics.

    Player side is unknown when there is no direct per-round event evidence or
    evidence conflicts. Winner always means T/CT side, not a persistent team.
    """
    columns = ["Runda", "Wygrana strona", "Strona gracza", "K/D/A", "Obrażenia"]
    rounds = analysis.rounds_df
    if rounds.empty or "total_rounds_played" not in rounds:
        return pd.DataFrame(columns=columns)
    result = pd.DataFrame({
        "Runda": pd.to_numeric(rounds["total_rounds_played"], errors="coerce"),
        "Wygrana strona": rounds["winner"].map(_side) if "winner" in rounds else "—",
    }).dropna(subset=["Runda"])
    result["Runda"] = result["Runda"].astype(int)
    result = result.drop_duplicates("Runda").sort_values("Runda").reset_index(drop=True)
    sides = _event_side(analysis, str(player_id))
    roster = analysis.round_roster_df
    if not roster.empty and {"steamid", "team_num", "total_rounds_played"}.issubset(roster):
        own = roster[roster["steamid"].astype("string").eq(str(player_id))]
        for rnd, rows in own.groupby("total_rounds_played"):
            known_sides = set(rows["team_num"].map(_side)) - {"—"}
            sides[int(rnd)] = next(iter(known_sides)) if len(known_sides) == 1 else "—"
    result["Strona gracza"] = result["Runda"].map(sides).fillna("—")

    stats = analysis.round_stats_df
    if not stats.empty and {"steamid", "total_rounds_played"}.issubset(stats):
        selected = stats[stats["steamid"].astype("string").eq(str(player_id))].copy()
        selected["Runda"] = pd.to_numeric(
            selected["total_rounds_played"], errors="coerce",
        )
        selected = selected.dropna(subset=["Runda"])
        if not selected.empty:
            selected["Runda"] = selected["Runda"].astype(int)
            for field, output in (("kills", "K"), ("deaths", "D"),
                                  ("damage", "Obrażenia")):
                selected[output] = _number(selected, field)
            values = ["K", "D", "Obrażenia"]
            if "assists" in selected:
                selected["A"] = _number(selected, "assists")
                values.append("A")
            stats_by_round = selected.groupby("Runda")[values].sum()
            result = result.join(stats_by_round, on="Runda")
    for field in ("K", "D", "Obrażenia"):
        if field not in result:
            result[field] = float("nan")

    kills = analysis.kills_df
    assists: dict[int, int] = {}
    if not kills.empty and {"assister_steamid", "total_rounds_played"}.issubset(kills):
        selected = kills[kills["assister_steamid"].astype("string").eq(str(player_id))]
        counted = pd.to_numeric(selected["total_rounds_played"], errors="coerce")
        assists = counted.dropna().astype(int).value_counts().to_dict()
    if "A" not in result:
        result["A"] = result["Runda"].map(assists).fillna(0)
    result["A"] = result["A"].fillna(0).astype(int)
    known = result[["K", "D"]].notna().all(axis=1)
    result["K/D/A"] = "—"
    result.loc[known, "K/D/A"] = (
        result.loc[known, "K"].astype(int).astype(str) + "/"
        + result.loc[known, "D"].astype(int).astype(str) + "/"
        + result.loc[known, "A"].astype(str)
    )
    return result[columns]


def kill_events_table(analysis: DemoAnalysis, round_number: int) -> pd.DataFrame:
    """Short kill feed for a selected round; parser IDs and coordinates stay hidden."""
    columns = ["Atakujący", "Ofiara", "Broń", "HS"]
    events = analysis.kills_df
    if events.empty or "total_rounds_played" not in events:
        return pd.DataFrame(columns=columns)
    selected = events[
        pd.to_numeric(events["total_rounds_played"], errors="coerce").eq(round_number)
    ]
    if "tick" in selected:
        selected = selected.sort_values("tick")
    view = presentation_frame(selected, analysis.player_info)
    result = pd.DataFrame(index=view.index)
    for output, candidates in (
        ("Atakujący", ("Atakujący", "attacker_name")),
        ("Ofiara", ("Trafiony gracz", "user_name")),
        ("Broń", ("weapon",)),
        ("HS", ("headshot",)),
    ):
        result[output] = next((view[col] for col in candidates if col in view), "—")
    return result[columns].reset_index(drop=True)
