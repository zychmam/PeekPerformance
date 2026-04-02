"""LeetifyHarvester - Streamlit GUI.

Run with:  streamlit run src/gui/app.py
"""

from __future__ import annotations

import logging
from dataclasses import asdict

import pandas as pd
import plotly.express as px
import streamlit as st

from src.api.leetify_client import LeetifyAPIError, LeetifyClient
from src.config import Config
from src.storage.database import Database

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session-level singletons
# ---------------------------------------------------------------------------


def _get_config() -> Config:
    if "config" not in st.session_state:
        st.session_state["config"] = Config.load()
    return st.session_state["config"]


def _get_db() -> Database:
    if "db" not in st.session_state:
        st.session_state["db"] = Database(_get_config().db_path)
    return st.session_state["db"]


def _get_client() -> LeetifyClient:
    if "client" not in st.session_state:
        st.session_state["client"] = LeetifyClient(_get_config())
    return st.session_state["client"]


# ---------------------------------------------------------------------------
# Formatting helper
# ---------------------------------------------------------------------------


def _fmt(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "\u2014"
    return f"{value:.{decimals}f}"


# ---------------------------------------------------------------------------
# Sidebar - player management
# ---------------------------------------------------------------------------


def _sidebar() -> str | None:
    """Render sidebar and return the currently selected Steam ID (if any)."""
    st.sidebar.title("\U0001f3af Leetify Harvester")

    # --- Settings expander --------------------------------------------------
    with st.sidebar.expander("\u2699\ufe0f Settings"):
        cfg = _get_config()
        new_key = st.text_input("Leetify API key", value=cfg.api_key, type="password")
        if new_key != cfg.api_key:
            cfg.api_key = new_key
            cfg.save()
            # Recreate client with new key
            st.session_state.pop("client", None)
            st.rerun()

    # --- Add player ---------------------------------------------------------
    st.sidebar.subheader("Add Player")
    new_steam_id = st.sidebar.text_input(
        "Steam64 ID",
        placeholder="e.g. 76561198096123254",
    )
    if st.sidebar.button("\u2795 Add & Fetch", use_container_width=True) and new_steam_id.strip():
        _fetch_player(new_steam_id.strip())

    # --- Player list --------------------------------------------------------
    st.sidebar.divider()
    st.sidebar.subheader("Tracked Players")
    db = _get_db()
    players = db.list_players()

    if not players:
        st.sidebar.info("No players tracked yet. Add a Steam64 ID above.")
        return None

    options = {p.steam_id: f"{p.name or 'Unknown'} ({p.steam_id})" for p in players}
    selected = st.sidebar.radio(
        "Select player",
        options=list(options.keys()),
        format_func=lambda sid: options[sid],
        label_visibility="collapsed",
    )

    col1, col2 = st.sidebar.columns(2)
    if col1.button("\U0001f504 Refresh", use_container_width=True) and selected:
        _fetch_player(selected)
    if col2.button("\U0001f5d1\ufe0f Remove", use_container_width=True) and selected:
        db.delete_player(selected)
        st.rerun()

    return selected


def _fetch_player(steam_id: str) -> None:
    """Fetch profile + matches from the API and store locally."""
    client = _get_client()
    db = _get_db()
    try:
        with st.spinner(f"Fetching profile for {steam_id}..."):
            profile = client.get_player_profile(steam_id)
            db.upsert_player(profile)

        with st.spinner(f"Fetching matches for {steam_id}..."):
            matches = client.get_player_matches(steam_id)
            db.upsert_matches(matches)

        st.sidebar.success(f"Fetched {len(matches)} matches for {profile.name}")
    except LeetifyAPIError as exc:
        st.sidebar.error(f"API error: {exc}")
    except Exception as exc:  # noqa: BLE001
        st.sidebar.error(f"Error: {exc}")
    finally:
        st.rerun()


# ---------------------------------------------------------------------------
# Main content - tabs
# ---------------------------------------------------------------------------


def _tab_player_overview(steam_id: str) -> None:
    """Show player profile summary."""
    db = _get_db()
    player = db.get_player(steam_id)
    if player is None:
        st.warning("Player not found in local cache.")
        return

    st.header(f"Player: {player.name}")
    cols = st.columns(5)
    cols[0].metric("Leetify Rating", _fmt(player.leetify_rating))
    cols[1].metric("Aim", _fmt(player.aim_rating))
    cols[2].metric("Utility", _fmt(player.utility_rating))
    cols[3].metric("Positioning", _fmt(player.positioning_rating))
    cols[4].metric("Rank", player.rank or "\u2014")

    # Radar chart of ratings
    ratings = {
        "Aim": player.aim_rating,
        "Utility": player.utility_rating,
        "Positioning": player.positioning_rating,
        "Overall": player.leetify_rating,
    }
    valid = {k: v for k, v in ratings.items() if v is not None}
    if valid:
        fig = px.line_polar(
            r=list(valid.values()),
            theta=list(valid.keys()),
            line_close=True,
            range_r=[0, max(valid.values()) * 1.2],
        )
        fig.update_traces(fill="toself")
        fig.update_layout(height=350, margin=dict(t=30, b=30))
        st.plotly_chart(fig, use_container_width=True)


def _tab_matches(steam_id: str) -> None:
    """Match history table with filters."""
    db = _get_db()
    matches = db.get_matches(steam_id)
    if not matches:
        st.info("No matches stored. Click **Refresh** in the sidebar.")
        return

    df = pd.DataFrame([asdict(m) for m in matches])

    # Filters
    col1, col2, col3 = st.columns(3)
    maps = sorted(df["map_name"].dropna().unique())
    selected_maps = col1.multiselect("Map", maps, default=maps)
    results = col2.multiselect("Result", ["win", "loss", "tie"], default=["win", "loss", "tie"])
    modes = sorted(df["game_mode"].dropna().unique())
    selected_modes = col3.multiselect("Game Mode", modes, default=modes) if modes else modes

    mask = df["map_name"].isin(selected_maps) & df["result"].isin(results)
    if selected_modes:
        mask = mask & df["game_mode"].isin(selected_modes)
    df = df[mask]

    # Summary metrics
    if not df.empty:
        mcols = st.columns(6)
        mcols[0].metric("Matches", len(df))
        wins = int((df["result"] == "win").sum())
        losses = int((df["result"] == "loss").sum())
        mcols[1].metric("Win Rate", f"{wins / len(df) * 100:.0f}%")
        mcols[2].metric("Avg K/D", _fmt(df["kd_ratio"].mean()))
        mcols[3].metric("Avg ADR", _fmt(df["adr"].mean(), 1))
        mcols[4].metric("Avg Rating", _fmt(df["leetify_rating"].mean()))
        mcols[5].metric("W / L", f"{wins} / {losses}")

    # Display columns
    display_cols = [
        "match_date",
        "map_name",
        "result",
        "score_own",
        "score_enemy",
        "kills",
        "deaths",
        "assists",
        "kd_ratio",
        "adr",
        "leetify_rating",
        "hltv_rating",
        "hs_percent",
        "game_mode",
    ]
    present = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[present].rename(
            columns={
                "match_date": "Date",
                "map_name": "Map",
                "result": "Result",
                "score_own": "Own",
                "score_enemy": "Enemy",
                "kills": "K",
                "deaths": "D",
                "assists": "A",
                "kd_ratio": "K/D",
                "adr": "ADR",
                "leetify_rating": "Leetify",
                "hltv_rating": "HLTV",
                "hs_percent": "HS%",
                "game_mode": "Mode",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )


def _tab_charts(steam_id: str) -> None:
    """Performance charts over time."""
    db = _get_db()
    matches = db.get_matches(steam_id)
    if not matches:
        st.info("No matches to chart.")
        return

    df = pd.DataFrame([asdict(m) for m in matches])
    df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
    df = df.sort_values("match_date")

    metric = st.selectbox(
        "Metric",
        ["leetify_rating", "hltv_rating", "kd_ratio", "adr", "hs_percent", "kills"],
    )
    nice_names = {
        "leetify_rating": "Leetify Rating",
        "hltv_rating": "HLTV Rating",
        "kd_ratio": "K/D Ratio",
        "adr": "ADR",
        "hs_percent": "HS %",
        "kills": "Kills",
    }

    chart_df = df.dropna(subset=[metric])
    if chart_df.empty:
        st.warning(f"No data for {nice_names.get(metric, metric)}.")
        return

    fig = px.line(
        chart_df,
        x="match_date",
        y=metric,
        color_discrete_sequence=["#636EFA"],
        labels={"match_date": "Date", metric: nice_names.get(metric, metric)},
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)

    # Map breakdown bar chart
    st.subheader(f"{nice_names.get(metric, metric)} by Map")
    map_avg = chart_df.groupby("map_name")[metric].mean().reset_index()
    fig2 = px.bar(
        map_avg,
        x="map_name",
        y=metric,
        labels={"map_name": "Map", metric: nice_names.get(metric, metric)},
    )
    fig2.update_layout(height=350)
    st.plotly_chart(fig2, use_container_width=True)


def _tab_match_detail(steam_id: str) -> None:
    """Inspect a single match in detail."""
    db = _get_db()
    matches = db.get_matches(steam_id)
    if not matches:
        st.info("No matches available.")
        return

    options = {
        m.game_id: (
            f"{m.match_date[:10]} | {m.map_name}"
            f" | {m.score_own}-{m.score_enemy} ({m.result})"
        )
        for m in matches
    }
    game_id = st.selectbox("Select Match", list(options.keys()), format_func=lambda g: options[g])

    if not game_id:
        return

    # Try cached detail first, otherwise fetch
    detail = db.get_match_detail(game_id)
    if detail is None:
        if st.button("Fetch match detail from API"):
            try:
                client = _get_client()
                with st.spinner("Fetching..."):
                    detail = client.get_match_detail(game_id)
                    db.upsert_match_detail(detail)
            except LeetifyAPIError as exc:
                st.error(f"API error: {exc}")
                return
            except Exception as exc:  # noqa: BLE001
                st.error(f"Error: {exc}")
                return
        else:
            st.info("Click the button above to fetch detailed stats for this match.")
            return

    st.subheader(f"{detail.map_name}  \u2014  {detail.score_team_a}:{detail.score_team_b}")
    st.caption(f"Mode: {detail.game_mode} | Rounds: {detail.rounds_played}")

    if detail.players:
        pdf = pd.DataFrame([asdict(p) for p in detail.players])
        display = [
            "name",
            "team",
            "kills",
            "deaths",
            "assists",
            "kd_ratio",
            "adr",
            "leetify_rating",
            "hltv_rating",
            "hs_percent",
            "utility_damage",
            "flash_assists",
            "first_kills",
            "first_deaths",
        ]
        present = [c for c in display if c in pdf.columns]
        st.dataframe(
            pdf[present].rename(
                columns={
                    "name": "Player",
                    "team": "Team",
                    "kills": "K",
                    "deaths": "D",
                    "assists": "A",
                    "kd_ratio": "K/D",
                    "adr": "ADR",
                    "leetify_rating": "Leetify",
                    "hltv_rating": "HLTV",
                    "hs_percent": "HS%",
                    "utility_damage": "Util Dmg",
                    "flash_assists": "Flash A",
                    "first_kills": "FK",
                    "first_deaths": "FD",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


def _tab_compare_players() -> None:
    """Compare stats across multiple tracked players."""
    db = _get_db()
    players = db.list_players()
    if len(players) < 2:
        st.info("Track at least 2 players to use the comparison view.")
        return

    options = {p.steam_id: f"{p.name or p.steam_id}" for p in players}
    selected = st.multiselect(
        "Players to compare",
        list(options.keys()),
        default=list(options.keys())[:2],
        format_func=lambda sid: options[sid],
    )
    if len(selected) < 2:
        return

    rows = []
    for sid in selected:
        p = db.get_player(sid)
        matches = db.get_matches(sid)
        if p is None:
            continue
        df = pd.DataFrame([asdict(m) for m in matches]) if matches else pd.DataFrame()
        wins = int((df["result"] == "win").sum()) if not df.empty else 0
        total = len(df) if not df.empty else 0
        rows.append(
            {
                "Player": p.name or p.steam_id,
                "Leetify": p.leetify_rating,
                "Aim": p.aim_rating,
                "Utility": p.utility_rating,
                "Positioning": p.positioning_rating,
                "Matches": total,
                "Win Rate": f"{wins / total * 100:.0f}%" if total else "\u2014",
                "Avg K/D": df["kd_ratio"].mean() if not df.empty else None,
                "Avg ADR": df["adr"].mean() if not df.empty else None,
            }
        )

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the Streamlit application."""
    _page_config()
    selected = _sidebar()

    if selected is None:
        st.title("Welcome to Leetify Harvester")
        st.markdown(
            """
            **Get started:**
            1. (Optional) Enter your Leetify API key in **Settings** for higher rate limits.
            2. Add a player by entering their **Steam64 ID** in the sidebar.
            3. Browse matches, stats, and charts!

            > Data provided by [Leetify](https://leetify.com).
            """
        )
        return

    tab_overview, tab_matches, tab_charts, tab_detail, tab_compare = st.tabs(
        ["Overview", "Matches", "Charts", "Match Detail", "Compare Players"]
    )

    with tab_overview:
        _tab_player_overview(selected)
    with tab_matches:
        _tab_matches(selected)
    with tab_charts:
        _tab_charts(selected)
    with tab_detail:
        _tab_match_detail(selected)
    with tab_compare:
        _tab_compare_players()


def _page_config() -> None:
    st.set_page_config(
        page_title="Leetify Harvester",
        page_icon="\U0001f3af",
        layout="wide",
    )


if __name__ == "__main__":
    main()
