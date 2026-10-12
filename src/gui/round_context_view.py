"""Observed team setup and utility using a selected map profile."""

from collections.abc import Callable

import pandas as pd
import streamlit as st

from src.demos.context_summary import player_setup_profile, round_observations
from src.demos.presentation import player_labels
from src.demos.spatial_service import context_key
from src.gui.early_round_view import render_early_round
from src.gui.radar_player import render_radar_player
from src.maps.context import SpatialContext
from src.maps.registry import get_profile, profile_compatibility
from src.models.models import DemoAnalysis
from src.models.observations import RoundClock


def _entry_panel(context: SpatialContext, analysis: DemoAnalysis, rnd: int, labels: dict):
    entries = [entry for entry in context.entries if entry["round"] == rnd]
    st.markdown("### Wejścia T na site")
    if context.profile is None or not context.profile.supports("site_boundaries"):
        st.info("Rozpoznawanie wejść jest niedostępne bez profilu granic site'ów tej mapy.")
        return None
    if not entries:
        st.info(
            "Brak potwierdzonego wejścia na site w dostępnych próbkach. "
            "Nie oznacza to braku próby ataku."
        )
        return None
    index = st.selectbox(
        "Wykryte wejście",
        range(len(entries)),
        format_func=lambda i: (
            f"{entries[i]['site']} · {entries[i]['seconds']:.1f} s · "
            f"{len(entries[i]['participants'])} T w oknie 8 s"
        ),
        key=f"entry_select_{analysis.content_hash}_{rnd}",
    )
    entry = entries[index]
    st.write("**Kierunki:** " + " · ".join(f"{k}: {v}" for k, v in entry["routes"].items()))
    cols = st.columns(2)
    for col, field, title in (
        (cols[0], "ct_before", "CT — 2 s przed wejściem"),
        (cols[1], "ct_during", "CT — przy wejściu"),
    ):
        defence = entry[field]
        col.markdown(f"**{title}**")
        prefix = "" if defence["complete"] else "Zaobserwowano: "
        col.write(
            f"{prefix}{defence['site_count']} na site · "
            f"{defence['support_count']} w strefach wsparcia"
        )
        if not defence["complete"]:
            col.caption("Niepełne dane — liczby nie potwierdzają pełnej obsady.")
    carriers = entry["bomb_carriers"]
    st.write(
        "**Bomba przy wejściu:** "
        + (
            " · ".join(f"{labels.get(p['steamid'], 'Gracz')} — {p['place']}" for p in carriers)
            if carriers
            else "nosiciel nieustalony; bomba mogła być upuszczona lub podłożona."
        )
    )
    st.caption(
        "Wejście oznacza potwierdzoną zmianę strefy nawigacyjnej dema. "
        "Zliczamy uczestników w 8 s, również wejścia pojedyncze. "
        "To nie jest jeszcze klasyfikacja rush/execute."
    )
    with st.expander("Uczestnicy, obrońcy i dowody"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Gracz": labels.get(p["steamid"], "Gracz"),
                        "Kierunek": p["route"],
                        "Czas [s]": round(p["seconds"], 2),
                        "Tick przed": p["previous_tick"],
                        "Tick wejścia": p["tick"],
                        "Tick potwierdzenia": p["confirmed_tick"],
                    }
                    for p in entry["participants"]
                ]
            ),
            hide_index=True,
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Moment": label,
                        "Gracz": labels.get(p["steamid"], "Gracz"),
                        "Strefa": p["place"],
                        "Grupa": {"site": "Site", "support": "Wsparcie", "other": "Pozostałe"}[
                            p["group"]
                        ],
                    }
                    for field, label in (("ct_before", "Przed"), ("ct_during", "Podczas"))
                    for p in entry[field]["players"]
                ]
            ),
            hide_index=True,
        )
        st.caption(
            "Krótki wypad zakończony śmiercią lub odwrotem może nie mieć "
            "potwierdzenia. Strefa wsparcia nie dowodzi widoczności ani możliwości pomocy."
        )
    return entry


def render_round_context(
    analysis: DemoAnalysis,
    player_id: str,
    load_context: Callable[[DemoAnalysis, int], SpatialContext] | None,
) -> None:
    st.subheader("Kontekst rundy")
    profile = get_profile(analysis.map_name)
    numbers = analysis.rounds_df.total_rounds_played.astype(int).tolist()
    if not numbers:
        st.info("Brak danych rund.")
        return
    rnd = st.selectbox("Runda taktyczna", numbers)
    presentation = profile.presentation_fingerprint if profile else "none"
    key = f"spatial_{context_key(analysis, profile)}_{presentation}_{rnd}"
    if key not in st.session_state:
        if load_context is None or not st.button("Przygotuj kontekst rundy"):
            return
        try:
            with st.spinner("Przygotowanie pozycji i zdarzeń…"):
                st.session_state[key] = load_context(analysis, int(rnd))
        except Exception as exc:
            st.error(f"Nie udało się przygotować kontekstu: {exc}")
            return
    context = st.session_state[key]
    if profile is None:
        st.info("Mapa nie ma jeszcze profilu przestrzennego. Dostępne są zdarzenia i wyposażenie.")
    elif profile_compatibility(profile, analysis.header.get("patch_version")) != "verified":
        st.caption("Profil mapy nie został zweryfikowany dla tej wersji dema.")
    clock = context.clock[context.clock.total_rounds_played.eq(rnd)].iloc[0]
    if pd.isna(clock.freeze_tick):
        st.warning("Brak końca freeze time — nie określamy fazy early round.")
        return
    round_clock = RoundClock.from_row(clock.to_dict())
    observations = round_observations(context, analysis).set_index("round").loc[rnd]
    st.write(f"**Wygrywa {clock.winner}** · {clock.get('reason', '')}")
    # Reserve the first slot of the round analysis for the map. Fill it after
    # processing the controls below so event jumps still set the initial time.
    map_slot = st.empty()
    labels = player_labels(analysis.player_info)
    early_jump = render_early_round(analysis, context, int(rnd), labels)
    entry = _entry_panel(context, analysis, int(rnd), labels)
    show_entry_utility = st.checkbox(
        "Pokaż utility z 8 s przed wybranym wejściem",
        value=entry is not None,
        disabled=entry is None,
    )
    max_seconds = max(1.0, float(round_clock.seconds(clock.tick)))
    slider_key = f"round_time_{analysis.content_hash}_{rnd}"
    if entry is not None and st.button("Przejdź do wejścia na mapie"):
        st.session_state[slider_key] = min(max_seconds, max(0.0, float(entry["seconds"])))
    if early_jump is not None:
        st.session_state[slider_key] = min(max_seconds, early_jump)
    slider_default = (
        {}
        if slider_key in st.session_state
        else {
            "value": 0.0,
        }
    )
    with st.expander("Dokładny moment startu odtwarzacza"):
        seconds = st.slider(
            "Sekundy od końca freeze time",
            0.0,
            max_seconds,
            step=1 / round_clock.tick_rate,
            format="%.2f",
            key=slider_key,
            **slider_default,
        )
    with map_slot.container():
        render_radar_player(context, analysis, int(rnd), labels, player_id, seconds)
        st.caption(
            "Odtwarzacz ma własny suwak i przyciski. Powyższy suwak oraz przyciski "
            "ustawiają początkowy moment odtwarzacza. Odtwarzanie działa w przeglądarce."
        )
    utility = context.utility
    utility_title = "Tabela utility — pierwsze 15 sekund"
    if not utility.empty:
        start, end = 0, 15
        if entry is not None and show_entry_utility:
            start, end = max(0, entry["seconds"] - 8), entry["seconds"]
            utility_title = "Tabela utility — 8 s przed wejściem"
        utility = utility[utility.total_rounds_played.eq(rnd) & utility.seconds.between(start, end)]
    for field, label in (("contact_tick", "Pierwsze obrażenia"), ("opening_tick", "Opening")):
        tick = observations[field]
        if pd.notna(tick):
            st.write(f"**{label}:** {round_clock.seconds(tick):.1f} s")
    if pd.notna(observations.opening_tick):
        st.write(
            f"Pozycja zabójcy: {observations.opening_attacker_place or 'brak danych'} · "
            f"pozycja ofiary: {observations.opening_victim_place or 'brak danych'}"
        )
    if not utility.empty:
        table = utility.copy()
        table["Gracz"] = table.user_steamid.astype("string").map(labels)
        st.markdown(f"**{utility_title}**")
        st.dataframe(
            table[["Gracz", "kind", "seconds", "x", "y", "z"]].rename(
                columns={"kind": "Typ", "seconds": "Czas [s]"}
            ),
            hide_index=True,
        )
    st.markdown("**Pozycja wybranego gracza po 12 sekundach tej rundy**")
    st.dataframe(player_setup_profile(context, player_id), hide_index=True)
    st.caption("Jedna obserwacja na rundę; rundy bez próbki lub po śmierci gracza są pomijane.")
    with st.expander("Dostępność danych"):
        st.json(context.diagnostics)
