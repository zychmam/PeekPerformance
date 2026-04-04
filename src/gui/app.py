"""LeetifyHarvester - Streamlit GUI.

Run with:  streamlit run src/gui/app.py
"""

from __future__ import annotations

import json
import logging
import time
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


def _fetch_match_raws(
    selected_matches: list, db: Database, client: LeetifyClient
) -> tuple[list[dict], list[str]]:
    """Fetch raw match data for selected matches, using cache. Returns (raw_list, errors)."""
    raws: list[dict] = []
    errors: list[str] = []
    progress = st.progress(0, text="Fetching match details...")

    for i, m in enumerate(selected_matches):
        progress.progress((i + 1) / len(selected_matches), text=f"Match {i + 1}/{len(selected_matches)}: {m.map_name}")

        raw = db.get_match_raw(m.game_id)
        if raw is None:
            try:
                raw = client.get_match_detail_raw(m.game_id)
                db.upsert_match_raw(m.game_id, raw)
                time.sleep(0.3)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{m.game_id}: {exc}")
                continue
        raws.append(raw)

    progress.empty()
    return raws, errors


def _build_csv_rows(raws: list[dict]) -> list[dict]:
    """Build flat CSV rows from raw match data."""
    all_rows: list[dict] = []
    for raw in raws:
        team_scores = raw.get("team_scores", [])
        score_by_team = {ts.get("team_number", 0): ts.get("score", 0) for ts in team_scores}

        match_info = {
            "match_id": raw.get("id", ""),
            "match_date": raw.get("finished_at", ""),
            "match_map": raw.get("map_name", ""),
            "match_data_source": raw.get("data_source", ""),
        }
        for team_num, team_score in sorted(score_by_team.items()):
            match_info[f"match_score_team_{team_num}"] = team_score

        for player in raw.get("stats", []):
            row = {**match_info}
            for key, value in player.items():
                row[key] = value
            all_rows.append(row)
    return all_rows


def _build_json_export(raws: list[dict], steam_id: str) -> dict:
    """Build hierarchical JSON export from raw match data."""
    matches_out: list[dict] = []

    for raw in raws:
        team_scores = raw.get("team_scores", [])
        score_by_team = {ts.get("team_number", 0): ts.get("score", 0) for ts in team_scores}
        players = raw.get("stats", [])

        # Find subject player's team
        subject_team_num: int | None = None
        for p in players:
            if str(p.get("steam64_id", "")) == steam_id:
                subject_team_num = p.get("initial_team_number")
                break

        # Split players into teams
        teams: dict[int, list[dict]] = {}
        for p in players:
            tn = p.get("initial_team_number", 0)
            teams.setdefault(tn, []).append(p)

        # Build team objects
        team_objects: list[dict] = []
        for tn, team_players in sorted(teams.items()):
            is_subject_team = (tn == subject_team_num)
            team_objects.append({
                "team_number": tn,
                "score": score_by_team.get(tn, 0),
                "is_subject_team": is_subject_team,
                "players": team_players,
            })

        # Determine result
        if subject_team_num is not None:
            own_score = score_by_team.get(subject_team_num, 0)
            enemy_score = sum(v for k, v in score_by_team.items() if k != subject_team_num)
            if own_score > enemy_score:
                result = "win"
            elif own_score < enemy_score:
                result = "loss"
            else:
                result = "tie"
            score_str = f"{own_score}:{enemy_score}"
        else:
            scores = sorted(score_by_team.values(), reverse=True)
            result = "unknown"
            score_str = ":".join(str(s) for s in scores)

        rounds_played = 0
        if players:
            rounds_played = players[0].get("rounds_count", 0)

        matches_out.append({
            "match_id": raw.get("id", ""),
            "date": raw.get("finished_at", ""),
            "map": raw.get("map_name", ""),
            "data_source": raw.get("data_source", ""),
            "rounds_played": rounds_played,
            "result": result,
            "score": score_str,
            "teams": team_objects,
        })

    # Sort chronologically
    matches_out.sort(key=lambda m: m["date"])

    return {
        "subject_player_steam64_id": steam_id,
        "export_date": time.strftime("%Y-%m-%d"),
        "total_matches": len(matches_out),
        "matches": matches_out,
    }


# ---------------------------------------------------------------------------
# Compact (pipe-separated) export for LLM context – ~35 key fields
# ---------------------------------------------------------------------------

_COMPACT_PLAYER_FIELDS: list[tuple[str, str]] = [
    # (api_field, short_header)
    ("name", "name"),
    ("steam64_id", "steam64"),
    ("total_kills", "kills"),
    ("total_deaths", "deaths"),
    ("total_assists", "assists"),
    ("kd_ratio", "kd"),
    ("dpr", "adr"),
    ("total_damage", "dmg"),
    ("leetify_rating", "rating"),
    ("ct_leetify_rating", "ct_rat"),
    ("t_leetify_rating", "t_rat"),
    ("score", "score"),
    ("mvps", "mvps"),
    ("rounds_count", "rounds"),
    ("rounds_survived_percentage", "surv%"),
    ("total_hs_kills", "hs_kills"),
    ("accuracy_head", "hs%"),
    ("accuracy_enemy_spotted", "acc_spotted"),
    ("preaim", "preaim"),
    ("reaction_time", "react"),
    ("counter_strafing_shots_good_ratio", "cs%"),
    ("spray_accuracy", "spray_acc"),
    ("multi2k", "2k"),
    ("multi3k", "3k"),
    ("multi4k", "4k"),
    ("multi5k", "5k"),
    ("flashbang_thrown", "flash_thrown"),
    ("flashbang_hit_foe", "flash_foe"),
    ("flashbang_leading_to_kill", "flash_kill"),
    ("smoke_thrown", "smokes"),
    ("molotov_thrown", "molotovs"),
    ("he_thrown", "he"),
    ("utility_on_death_avg", "util_death"),
    ("trade_kills_success_percentage", "trade%"),
    ("traded_deaths_success_percentage", "traded%"),
]

_COMPACT_HEADERS = "|".join(h for _, h in _COMPACT_PLAYER_FIELDS)

_RATING_FIELDS = {"leetify_rating", "ct_leetify_rating", "t_leetify_rating"}


def _fmt_compact_val(val: object, field: str = "") -> str:
    if val is None:
        return ""
    if isinstance(val, float):
        if field in _RATING_FIELDS:
            return f"{val * 100:.1f}"
        return f"{val:.2f}" if abs(val) < 100 else f"{val:.0f}"
    return str(val)


def _build_compact_export(raws: list[dict], steam_id: str) -> str:
    """Build ultra-compact pipe-separated text export for LLM context windows."""
    lines: list[str] = []
    lines.append(f"# CS2 Export | subject={steam_id} | {time.strftime('%Y-%m-%d')} | {len(raws)} matches")
    lines.append("")

    # Sort chronologically
    sorted_raws = sorted(raws, key=lambda r: r.get("finished_at", ""))

    for idx, raw in enumerate(sorted_raws, 1):
        team_scores = raw.get("team_scores", [])
        score_by_team = {ts.get("team_number", 0): ts.get("score", 0) for ts in team_scores}
        players = raw.get("stats", [])

        # Find subject team
        subject_team_num: int | None = None
        for p in players:
            if str(p.get("steam64_id", "")) == steam_id:
                subject_team_num = p.get("initial_team_number")
                break

        # Result
        if subject_team_num is not None:
            own = score_by_team.get(subject_team_num, 0)
            enemy = sum(v for k, v in score_by_team.items() if k != subject_team_num)
            result = "WIN" if own > enemy else ("LOSS" if own < enemy else "TIE")
            score_str = f"{own}:{enemy}"
        else:
            scores = sorted(score_by_team.values(), reverse=True)
            result = "?"
            score_str = ":".join(str(s) for s in scores)

        map_name = raw.get("map_name", "?")
        date = raw.get("finished_at", "")[:10]
        source = raw.get("data_source", "")
        rounds = players[0].get("rounds_count", 0) if players else 0

        lines.append(f"## M{idx} | {date} | {map_name} | {result} {score_str} | {source} | {rounds}r")

        # Group players by team
        teams: dict[int, list[dict]] = {}
        for p in players:
            tn = p.get("initial_team_number", 0)
            teams.setdefault(tn, []).append(p)

        for tn in sorted(teams):
            is_subj = (tn == subject_team_num)
            marker = " ★" if is_subj else ""
            team_score = score_by_team.get(tn, 0)
            lines.append(f"### TEAM {tn} ({team_score}){marker}")
            lines.append(_COMPACT_HEADERS)

            for p in teams[tn]:
                vals = [_fmt_compact_val(p.get(field), field) for field, _ in _COMPACT_PLAYER_FIELDS]
                lines.append("|".join(vals))

        lines.append("")

    return "\n".join(lines)


def _tab_ai_export(steam_id: str) -> None:
    """Export full match data (all players, all stats) for AI consumption."""
    db = _get_db()
    matches = db.get_matches(steam_id)
    if not matches:
        st.info("No matches stored. Click **Refresh** in the sidebar first.")
        return

    st.subheader("Export full match data for AI")
    st.caption(
        "Fetches detailed stats for **all 10 players** in each match (66 stat fields per player). "
        "Results are cached locally after first fetch."
    )

    # Build selectable match list
    match_options = {
        m.game_id: f"{m.match_date[:10]} | {m.map_name} | {m.score_own}-{m.score_enemy} ({m.result})"
        for m in matches
    }

    col_sel1, col_sel2 = st.columns([1, 1])
    with col_sel1:
        if st.button("Select all", use_container_width=True):
            st.session_state["ai_export_selection"] = list(match_options.keys())
    with col_sel2:
        if st.button("Deselect all", use_container_width=True):
            st.session_state["ai_export_selection"] = []

    default = st.session_state.get("ai_export_selection", list(match_options.keys())[:5])
    selected_ids = st.multiselect(
        "Select matches to export",
        options=list(match_options.keys()),
        default=[gid for gid in default if gid in match_options],
        format_func=lambda gid: match_options[gid],
    )
    st.session_state["ai_export_selection"] = selected_ids

    if not selected_ids:
        st.info("Select at least one match above.")
        return

    selected_matches = [m for m in matches if m.game_id in selected_ids]

    if not st.button(f"\U0001f4e5 Fetch & Export ({len(selected_matches)} matches)", use_container_width=True):
        return

    client = _get_client()
    raws, errors = _fetch_match_raws(selected_matches, db, client)

    if errors:
        st.warning(f"Failed to fetch {len(errors)} match(es): {'; '.join(errors[:3])}")

    if not raws:
        st.error("No data to export.")
        return

    # Build all formats
    csv_rows = _build_csv_rows(raws)
    json_data = _build_json_export(raws, steam_id)
    compact_text = _build_compact_export(raws, steam_id)

    df = pd.DataFrame(csv_rows)
    compact_tokens_est = len(compact_text) // 4
    json_tokens_est = len(json.dumps(json_data, ensure_ascii=False)) // 4
    st.success(
        f"Ready: **{len(raws)}** matches, **{len(csv_rows)}** player rows  \n"
        f"Compact: ~{compact_tokens_est:,} tokens | JSON: ~{json_tokens_est:,} tokens"
    )

    # Preview
    st.dataframe(df, use_container_width=True, hide_index=True, height=500)

    # Download buttons
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    with col_dl1:
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="\U0001f4be CSV (flat, all fields)",
            data=csv_bytes,
            file_name=f"leetify_export_{steam_id}_{len(raws)}matches.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_dl2:
        json_bytes = json.dumps(json_data, ensure_ascii=False, indent=2).encode("utf-8")
        st.download_button(
            label="\U0001f916 JSON (hierarchical)",
            data=json_bytes,
            file_name=f"leetify_export_{steam_id}_{len(raws)}matches.json",
            mime="application/json",
            use_container_width=True,
        )
    with col_dl3:
        compact_bytes = compact_text.encode("utf-8")
        st.download_button(
            label="\u26a1 Compact (LLM-optimized)",
            data=compact_bytes,
            file_name=f"leetify_export_{steam_id}_{len(raws)}matches.txt",
            mime="text/plain",
            use_container_width=True,
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

    tab_overview, tab_matches, tab_charts, tab_detail, tab_export, tab_compare = st.tabs(
        ["Overview", "Matches", "Charts", "Match Detail", "AI Export", "Compare Players"]
    )

    with tab_overview:
        _tab_player_overview(selected)
    with tab_matches:
        _tab_matches(selected)
    with tab_charts:
        _tab_charts(selected)
    with tab_detail:
        _tab_match_detail(selected)
    with tab_export:
        _tab_ai_export(selected)
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
