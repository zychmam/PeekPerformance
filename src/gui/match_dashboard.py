"""Focused single-match views; raw parser data stays in a separate section."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.demos.demo_analyzer import DemoAnalyzer
from src.demos.match_view import (
    kill_events_table,
    player_rounds_table,
    player_summary_table,
)
from src.maps.context import SpatialContext
from src.demos.presentation import player_labels, presentation_frame
from src.gui.round_context_view import render_round_context
from src.models.models import DemoAnalysis


def _number(value: object, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value):.{decimals}f}"


def _selected_rating(summary: pd.DataFrame, player_id: str) -> pd.Series | None:
    if summary.empty or "steamid" not in summary:
        return None
    rows = summary[summary["steamid"].astype("string") == player_id]
    return rows.iloc[0] if not rows.empty else None


def _rounds_chart(
    rounds: pd.DataFrame, *, interactive: bool = False, key: str | None = None,
) -> None:
    if rounds.empty or "Obrażenia" not in rounds:
        st.info("Brak statystyk rund dla tego gracza.")
        return
    chart = rounds.copy()
    chart["Obrażenia"] = pd.to_numeric(chart["Obrażenia"], errors="coerce").fillna(0)
    fig = px.bar(
        chart, x="Runda", y="Obrażenia", color="Strona gracza",
        color_discrete_map={"T": "#f59e0b", "CT": "#3b82f6", "—": "#9ca3af"},
        hover_data=[column for column in ("K/D/A", "Wygrana strona") if column in chart],
    )
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=15, b=10),
                      xaxis_title="Runda", yaxis_title="Obrażenia przeciwnikom")
    if interactive:
        event = st.plotly_chart(
            fig, use_container_width=True, on_select="rerun",
            selection_mode="points", key=key,
        )
        if event and event.selection.points:
            st.session_state["pending_match_round"] = int(event.selection.points[0]["x"])
            st.rerun()
    else:
        st.plotly_chart(fig, use_container_width=True)


def _switch_to_rounds() -> None:
    st.session_state["match_section"] = "Rundy"


def _overview(
    analysis: DemoAnalysis, summary: pd.DataFrame, player_id: str,
) -> None:
    selected = _selected_rating(summary, player_id)
    if selected is not None:
        rating = _number(selected.get("Rating"), 2)
        kda = f"{int(selected['K'])}/{int(selected['D'])}/{int(selected['A'])}"
        adr = _number(selected.get("ADR"))
        kast = f"{_number(selected.get('KAST%'))}%"
    else:
        rating = kda = adr = kast = "—"
    cols = st.columns(4)
    for col, label, value in zip(
        cols, ("Peek rating", "K / D / A", "ADR", "KAST"),
        (rating, kda, adr, kast), strict=True,
    ):
        col.metric(label, value)
    st.caption(
        "Rating jest przybliżony. ADR to obrażenia przeciwnikom na rundę; "
        "KAST to procent rund z zabójstwem, asystą, przeżyciem lub wymianą."
    )

    st.subheader("Gracze")
    table = player_summary_table(analysis, summary)
    if table.empty:
        st.info("Brak danych graczy.")
    else:
        st.dataframe(
            table, hide_index=True, use_container_width=True,
            column_config={
                "Rating": st.column_config.NumberColumn(format="%.2f"),
                "ADR": st.column_config.NumberColumn(format="%.1f"),
                "KAST": st.column_config.NumberColumn(format="%.1f%%"),
            },
        )

    st.subheader("Przebieg meczu")
    rounds = player_rounds_table(analysis, player_id)
    _rounds_chart(
        rounds, interactive=True,
        key=f"overview_round_chart_{analysis.content_hash}_{player_id}",
    )
    st.caption("Kolor oznacza stronę gracza w rundzie; wynik rundy jest pokazany w widoku Rundy.")
    if not rounds.empty:
        st.button(
            "Zobacz rundy", key="overview_to_rounds", on_click=_switch_to_rounds
        )


def _round_damage_events(analysis: DemoAnalysis, round_number: int) -> pd.DataFrame:
    source = analysis.damage_df
    needed = {"total_rounds_played", "enemy_damage"}
    if source.empty or not needed.issubset(source):
        return pd.DataFrame()
    filtered = source[
        source["total_rounds_played"].eq(round_number)
        & pd.to_numeric(source["enemy_damage"], errors="coerce").gt(0)
    ]
    if filtered.empty:
        return pd.DataFrame()
    display = presentation_frame(filtered, analysis.player_info)
    cols = [
        column for column in ("Atakujący", "Trafiony gracz", "weapon", "enemy_damage")
        if column in display
    ]
    return display[cols].rename(columns={
        "weapon": "Broń", "enemy_damage": "Obrażenia"
    }).reset_index(drop=True)


def _rounds(analysis: DemoAnalysis, player_id: str) -> None:
    st.subheader("Rundy")
    table = player_rounds_table(analysis, player_id)
    if table.empty:
        st.info("Brak ukończonych rund.")
        return
    st.dataframe(table, hide_index=True, use_container_width=True)
    numbers = table["Runda"].dropna().astype(int).tolist()
    if not numbers:
        return
    selected = st.selectbox("Szczegóły rundy", numbers, key=f"round_{analysis.content_hash}")
    row = table.loc[table["Runda"].eq(selected)].iloc[0]
    cols = st.columns(4)
    for col, label, value in zip(
        cols, ("Wygrała strona", "Strona gracza", "K / D / A", "Obrażenia"),
        (row.get("Wygrana strona", "—"), row.get("Strona gracza", "—"),
         row.get("K/D/A", "—"), _number(row.get("Obrażenia"), 0)), strict=True,
    ):
        col.metric(label, value)
    kills = kill_events_table(analysis, selected)
    st.markdown("#### Zabójstwa w rundzie")
    if kills.empty:
        st.info("Brak zabójstw w zapisanych zdarzeniach.")
    else:
        st.dataframe(kills, hide_index=True, use_container_width=True)
    with st.expander("Trafienia przeciwników w tej rundzie"):
        damage = _round_damage_events(analysis, selected)
        if damage.empty:
            st.info("Brak zapisanych trafień przeciwników.")
        else:
            st.dataframe(damage, hide_index=True, use_container_width=True)


def _fight(analysis: DemoAnalysis, summary: pd.DataFrame, player_id: str) -> None:
    st.subheader("Walka")
    selected = _selected_rating(summary, player_id)
    if selected is not None:
        cols = st.columns(4)
        for col, label, value in zip(
            cols, ("HS", "Zabójstwa / runda", "Śmierci / runda", "Średni swing"),
            (f"{_number(selected.get('HS%'))}%", _number(selected.get("KPR"), 2),
             _number(selected.get("DPR"), 2), _number(selected.get("Avg Swing"), 2)),
            strict=True,
        ):
            col.metric(label, value)
    rounds = player_rounds_table(analysis, player_id)
    _rounds_chart(rounds)
    st.caption(
        "Obrażenia obejmują rzeczywistą utratę HP przeciwników, "
        "bez friendly fire i overkill."
    )
    if not rounds.empty:
        st.markdown("#### Runda po rundzie")
        cols = [c for c in ("Runda", "Strona gracza", "K/D/A", "Obrażenia") if c in rounds]
        st.dataframe(rounds[cols], hide_index=True, use_container_width=True)


def _economy_rounds(eco: pd.DataFrame, analysis: DemoAnalysis) -> pd.DataFrame:
    if eco.empty or "tick" not in eco or analysis.rounds_df.empty:
        return pd.DataFrame()
    rounds = analysis.rounds_df
    if not {"start_tick", "tick", "total_rounds_played"}.issubset(rounds):
        return pd.DataFrame()
    result = eco.copy()
    result["Runda"] = pd.NA
    for row in rounds.itertuples():
        result.loc[
            result["tick"].between(row.start_tick, row.tick), "Runda"
        ] = int(row.total_rounds_played)
    return result.dropna(subset=["Runda"])


def _utility_economy(
    analysis: DemoAnalysis, player_id: str,
    demo_path: Callable[[DemoAnalysis], Path | None],
) -> None:
    st.subheader("Utility")
    stats = analysis.round_stats_df
    if not stats.empty and {"steamid", "utility_damage", "total_rounds_played"}.issubset(stats):
        own = stats[stats["steamid"].astype("string").eq(player_id)].copy()
        own = own.sort_values("total_rounds_played")
        total = pd.to_numeric(own["utility_damage"], errors="coerce").sum()
        st.metric("Obrażenia od HE i ognia", _number(total, 0))
        if not own.empty:
            fig = px.bar(own, x="total_rounds_played", y="utility_damage")
            fig.update_layout(height=270, margin=dict(l=10, r=10, t=15, b=10),
                              xaxis_title="Runda", yaxis_title="Obrażenia od utility")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Brak wiarygodnych danych o obrażeniach od utility.")

    blinds = analysis.player_blinds_df
    if not blinds.empty and "thrower_steamid" in blinds:
        own = blinds[blinds["thrower_steamid"].astype("string").eq(player_id)]
        if "is_enemy" in own:
            own = own[own["is_enemy"].fillna(False)]
        st.metric("Oślepieni przeciwnicy (zdarzenia)", len(own))
        if not own.empty:
            display = presentation_frame(own, analysis.player_info)
            cols = [c for c in ("total_rounds_played", "Trafiony gracz", "blind_duration")
                    if c in display]
            if cols:
                with st.expander("Zdarzenia flash"):
                    st.dataframe(display[cols].rename(columns={
                        "total_rounds_played": "Runda", "blind_duration": "Czas oślepienia"
                    }), hide_index=True, use_container_width=True)
    st.caption(
        "Trajektorie granatów to próbki pozycji, nie liczba rzutów. "
        "Sama liczba utility nie dowodzi błędu taktycznego."
    )

    st.subheader("Ekonomia")
    cache_key = f"economy_{analysis.content_hash}"
    if st.button("Wczytaj ekonomię rund", key=f"load_{cache_key}"):
        path = demo_path(analysis)
        if path is None:
            st.warning("Plik demo nie jest dostępny na dysku.")
        else:
            with st.spinner("Wczytywanie ekonomii..."):
                st.session_state[cache_key] = DemoAnalyzer(path).get_economy()
    eco = st.session_state.get(cache_key)
    if eco is None:
        st.caption("Ekonomia jest wczytywana na żądanie z pliku demo.")
        return
    eco = _economy_rounds(eco, analysis)
    if eco.empty or "steamid" not in eco:
        st.info("Brak danych ekonomii przypisanych do ukończonych rund.")
        return
    own = eco[eco["steamid"].astype("string").eq(player_id)]
    columns = {
        "Runda": "Runda", "balance": "Saldo", "current_equip_value": "Wyposażenie",
        "cash_spent_this_round": "Wydano",
    }
    visible = own[[c for c in columns if c in own]].rename(columns=columns)
    st.dataframe(visible, hide_index=True, use_container_width=True)
    if not visible.empty and "Wyposażenie" in visible:
        fig = px.line(visible, x="Runda", y="Wyposażenie", markers=True)
        fig.update_layout(height=270, margin=dict(l=10, r=10, t=15, b=10))
        st.plotly_chart(fig, use_container_width=True)


def _raw_data(
    analysis: DemoAnalysis, demo_path: Callable[[DemoAnalysis], Path | None],
    match_report=None,
) -> None:
    st.subheader("Dane i eksport")
    from src.gui.match_export_view import render_match_export
    render_match_export(analysis, match_report)
    st.caption(
        "Surowe dane parsera do przeglądania; "
        "identyfikatory graczy są zastąpione nickami."
    )
    frames = {name: frame for name, frame in analysis._dataframes().items() if not frame.empty}
    if analysis.header:
        frames["Header"] = pd.DataFrame(
            [(key, value) for key, value in analysis.header.items()
             if "steamid" not in key.lower().replace("_", "")],
            columns=["Pole", "Wartość"],
        )
    if analysis.convars:
        frames["Convars"] = pd.DataFrame(
            [(key, value) for key, value in analysis.convars.items()
             if "steamid" not in key.lower().replace("_", "")],
            columns=["Pole", "Wartość"],
        )
    if frames:
        selected = st.selectbox("Zestaw danych", list(frames), key="raw_dataset")
        st.dataframe(presentation_frame(frames[selected], analysis.player_info),
                     hide_index=True, use_container_width=True, height=450)

    with st.expander("Dodatkowe zdarzenia i stany gracza"):
        path = demo_path(analysis)
        if path is None:
            st.info("Plik źródłowy demo nie jest dostępny na dysku.")
            return
        event_key = f"event_list_{analysis.content_hash}"
        if st.button("Pokaż typy zdarzeń", key=f"list_{event_key}"):
            st.session_state[event_key] = DemoAnalyzer(path).list_events()
        event_names = st.session_state.get(event_key, [])
        if event_names:
            event_name = st.selectbox(
                "Typ zdarzenia", sorted(event_names), key=f"event_{analysis.content_hash}"
            )
            if st.button("Wczytaj zdarzenie", key=f"parse_{analysis.content_hash}"):
                st.session_state[f"raw_{analysis.content_hash}"] = (
                    event_name, DemoAnalyzer(path).get_raw_event(event_name)
                )
        raw = st.session_state.get(f"raw_{analysis.content_hash}")
        if raw is not None:
            name, frame = raw
            st.caption(f"{name}: {len(frame)} zdarzeń")
            if not frame.empty:
                st.dataframe(presentation_frame(frame, analysis.player_info),
                             hide_index=True, use_container_width=True, height=400)

        rounds = analysis.rounds_df
        if not rounds.empty and {"total_rounds_played", "start_tick", "tick"}.issubset(rounds):
            round_id = st.selectbox(
                "Próbki stanu w rundzie",
                rounds["total_rounds_played"].dropna().astype(int).tolist(),
                key=f"states_round_{analysis.content_hash}",
            )
            if st.button("Wczytaj stany graczy", key=f"states_{analysis.content_hash}"):
                row = rounds.loc[rounds["total_rounds_played"].eq(round_id)].iloc[0]
                ticks = list(range(int(row["start_tick"]), int(row["tick"]) + 1, 64))
                st.session_state[f"state_samples_{analysis.content_hash}"] = (
                    round_id, DemoAnalyzer(path).get_player_states(ticks=ticks)
                )
        sampled = st.session_state.get(f"state_samples_{analysis.content_hash}")
        if sampled is not None:
            sampled_round, frame = sampled
            st.caption(f"Runda {sampled_round}: próbki co 64 ticki")
            if not frame.empty:
                st.dataframe(presentation_frame(frame, analysis.player_info),
                             hide_index=True, use_container_width=True, height=400)


def render_match_dashboard(
    analysis: DemoAnalysis, summary: pd.DataFrame,
    track_player: Callable[[str], None],
    demo_path: Callable[[DemoAnalysis], Path | None],
    spatial_context: Callable[[DemoAnalysis], SpatialContext] | None = None,
    map_round_facts: Callable[[DemoAnalysis], list[dict]] | None = None,
    match_report: Callable[[DemoAnalysis], dict] | None = None,
) -> None:
    """Render one focused section per rerun; parser tables stay out of Overview."""
    st.subheader(analysis.map_name or "Mecz")
    st.caption(f"{analysis.file_name} · {len(analysis.rounds_df)} ukończonych rund")
    labels = player_labels(analysis.player_info)
    if not labels:
        st.info("Brak graczy w tym demo.")
        return
    player_key = f"match_player_{analysis.content_hash}"
    preferred = st.session_state.get("selected_steamid")
    if player_key not in st.session_state and preferred in labels:
        st.session_state[player_key] = preferred
    left, right = st.columns([4, 1])
    player_id = left.selectbox(
        "Analizowany gracz", list(labels), format_func=lambda sid: labels[sid],
        key=player_key,
    )
    right.write(" ")
    if right.button("Śledź gracza", key=f"track_{analysis.content_hash}",
                    use_container_width=True):
        track_player(player_id)
        st.toast(f"Dodano: {labels[player_id]}")

    pending_round = st.session_state.pop("pending_match_round", None)
    tactical_navigation = st.session_state.pop("pending_tactical_navigation", None)
    if tactical_navigation and tactical_navigation["demo_id"] == analysis.content_hash:
        number = tactical_navigation["round"]
        st.session_state["match_section"] = "Analiza rundy"
        st.session_state[f"tactical_round_{analysis.content_hash}"] = number
        st.session_state[f"auto_tactical_{analysis.content_hash}_{number}"] = True
        if tactical_navigation["seconds"] is not None:
            st.session_state[f"round_time_{analysis.content_hash}_{number}"] = float(tactical_navigation["seconds"])
    if pending_round is not None:
        st.session_state["match_section"] = "Rundy"
        st.session_state[f"round_{analysis.content_hash}"] = pending_round
    if st.session_state.get("match_section") == "Kontekst mapy":
        st.session_state["match_section"] = "Analiza rundy"
    section = st.radio(
        "Sekcja", ["Przegląd", "Rundy", "Analiza rundy", "Tendencje mapy", "Walka",
                   "Utility i ekonomia", "Dane i eksport"],
        key="match_section", horizontal=True, label_visibility="collapsed",
    )
    if section == "Przegląd":
        _overview(analysis, summary, player_id)
    elif section == "Rundy":
        _rounds(analysis, player_id)
    elif section == "Walka":
        _fight(analysis, summary, player_id)
    elif section == "Analiza rundy":
        render_round_context(analysis, player_id, spatial_context)
    elif section == "Tendencje mapy":
        from src.gui.map_tendencies_view import render_map_tendencies
        render_map_tendencies(analysis, player_id, labels, map_round_facts)
    elif section == "Utility i ekonomia":
        _utility_economy(analysis, player_id, demo_path)
    else:
        _raw_data(analysis, demo_path, match_report)
