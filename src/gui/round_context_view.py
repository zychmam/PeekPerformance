"""Observed team setup and utility using a selected map profile."""

from collections.abc import Callable

import pandas as pd
import streamlit as st

from src.demos.round_summary import player_summary, summary_preview, team_summary
from src.demos.coach_foundations import FOUNDATION_VERSION
from src.demos.early_interpretation import INTERPRETATION_VERSION
from src.demos.early_round import EARLY_DETECTOR_VERSION
from src.demos.round_alive import ALIVE_DETECTOR_VERSION
from src.demos.round_contacts import CONTACT_DETECTOR_VERSION
from src.demos.round_refrags import REFRAG_DETECTOR_VERSION
from src.demos.round_moments import MOMENTS_VERSION
from src.demos.tactical_actions import VERSIONS as ACTION_VERSIONS
from src.demos.presentation import player_labels
from src.demos.spatial_service import context_key, round_analysis
from src.demos.tactical_rounds import build_tactical_match
from src.gui.early_round_view import render_early_round
from src.gui.round_evidence_view import render_evidence
from src.gui.round_moment_view import render_round_moments
from src.gui.round_tactical_view import render_tactical_actions
from src.gui.radar_player import render_radar_player
from src.maps.context import SpatialContext
from src.maps.registry import get_profile, profile_compatibility
from src.models.models import DemoAnalysis
from src.models.observations import DetectorConfig, RoundClock
from src.models.tactical import TACTICAL_SCHEMA_VERSION


def _round_result(analysis, context, rnd):
    """One selected round in the session; player changes only reproject the result."""
    fingerprint = context.profile.semantic_fingerprint if context.profile else "none"
    key = (analysis.content_hash, analysis.analysis_version, rnd,
           context_key(analysis, context.profile), fingerprint,
           TACTICAL_SCHEMA_VERSION, FOUNDATION_VERSION, EARLY_DETECTOR_VERSION,
           INTERPRETATION_VERSION, CONTACT_DETECTOR_VERSION, ALIVE_DETECTOR_VERSION,
           REFRAG_DETECTOR_VERSION, MOMENTS_VERSION, tuple(ACTION_VERSIONS.items()), DetectorConfig().fingerprint)
    cached = st.session_state.get("selected_tactical_round")
    if cached is None or cached[0] != key:
        with st.spinner("Układanie podsumowania rundy…"):
            match = build_tactical_match(
                round_analysis(analysis, rnd), context,
                foundations=getattr(context, "foundations", None),
                cached_actions=getattr(context, "tactical_actions", None),
            )
            if getattr(context, "persist_tactical_actions", None):
                context.persist_tactical_actions(match.rounds)
                from src.demos.tactical_actions import action_payload
                context.tactical_actions.update({record.number: action_payload(record)
                                                 for record in match.rounds})
        st.session_state["selected_tactical_round"] = (key, match)
    return st.session_state["selected_tactical_round"][1]


def _summary_panel(record, match, player_id, labels, profile, tick_rate, slider_key, max_seconds):
    st.markdown("### Podsumowanie rundy")
    scope = st.radio("Perspektywa", ["Drużyna", "Wybrany gracz"], horizontal=True,
                     key="round_summary_scope")
    items = (team_summary(record, match.evidence, labels, profile, tick_rate,
                          match.parameters["response_seconds"])
             if scope == "Drużyna" else
             player_summary(record, match.evidence, player_id, labels, profile, tick_rate))
    for heading, text in summary_preview(items, player=scope != "Drużyna"):
        st.markdown(f"**{heading}.** {text}")
    with st.expander("Pełne wyjaśnienie rundy i skoki na mapę"):
        for index, item in enumerate(items):
            st.markdown(f"**{item.title}.** {item.text}")
            if item.tick is not None and record.freeze_end_tick is not None:
                seconds = min(max_seconds, max(0.0, (item.tick - record.freeze_end_tick) / tick_rate))
                if st.button(f"Pokaż na mapie · {seconds:.1f} s", key=f"summary_jump_{record.number}_{scope}_{index}"):
                    st.session_state[slider_key] = seconds
    with st.expander("Sprawdź dowody podsumowania"):
        choice = st.selectbox("Fragment podsumowania", range(len(items)),
                              format_func=lambda i: items[i].title,
                              key=f"summary_proof_{record.number}_{scope}")
        render_evidence(items[choice].evidence_ids, match.evidence, labels,
                        record.freeze_end_tick, tick_rate)
    st.caption("Kontakt oznacza zapisane obrażenia lub eliminację. Obecność na site nie określa pełnej obrony; wejście nie obejmuje wszystkich prób ataku. Kolejność zdarzeń nie dowodzi przyczyny ani intencji.")


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
    rnd = st.selectbox("Runda taktyczna", numbers, key=f"tactical_round_{analysis.content_hash}")
    presentation = profile.presentation_fingerprint if profile else "none"
    key = f"spatial_{context_key(analysis, profile)}_{presentation}_{rnd}"
    auto_load = st.session_state.pop(f"auto_tactical_{analysis.content_hash}_{rnd}", False)
    if key not in st.session_state:
        if load_context is None or not auto_load and not st.button("Przygotuj kontekst rundy"):
            return
        try:
            with st.spinner("Przygotowanie pozycji i zdarzeń…"):
                st.session_state[key] = load_context(analysis, int(rnd))
        except Exception as exc:
            st.error(f"Nie udało się przygotować kontekstu: {exc}")
            return
    context = st.session_state[key]
    if load_context is not None and getattr(context, "load_projectiles", None) is None:
        # Upgrade an already-open session to the new lazy viewer source.
        context = load_context(analysis, int(rnd))
        st.session_state[key] = context
    if profile is None:
        st.info("Mapa nie ma jeszcze profilu przestrzennego. Dostępne są zdarzenia i wyposażenie.")
    elif profile_compatibility(profile, analysis.header.get("patch_version")) != "verified":
        st.caption("Profil mapy nie został zweryfikowany dla tej wersji dema.")
    clock = context.clock[context.clock.total_rounds_played.eq(rnd)].iloc[0]
    if pd.isna(clock.freeze_tick):
        st.warning("Brak końca freeze time — nie określamy fazy early round.")
        return
    round_clock = RoundClock.from_row(clock.to_dict())
    st.write(f"**Wygrywa {clock.winner}** · {clock.get('reason', '')}")
    # Reserve the first slot of the round analysis for the map. Fill it after
    # processing the controls below so event jumps still set the initial time.
    map_slot = st.empty()
    labels = player_labels(analysis.player_info)
    try:
        match = _round_result(analysis, context, int(rnd))
    except Exception as exc:
        st.error(f"Nie udało się przygotować podsumowania: {exc}")
        return
    record = next(r for r in match.rounds if r.number == int(rnd))
    max_seconds = max(1.0, float(round_clock.seconds(clock.tick)))
    slider_key = f"round_time_{analysis.content_hash}_{rnd}"
    _summary_panel(record, match, player_id, labels, context.profile,
                   round_clock.tick_rate, slider_key, max_seconds)
    render_round_moments(record, match.evidence, labels, round_clock.tick_rate,
                         slider_key, max_seconds)
    render_tactical_actions(record, match.evidence, labels, context.profile, player_id,
                            round_clock.tick_rate, slider_key, max_seconds)
    with st.expander("Szczegóły przygotowania i wejścia na site"):
        early_jump = render_early_round(analysis, context, int(rnd), labels, match=match)
        entry = _entry_panel(context, analysis, int(rnd), labels)
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
    with st.expander("Dostępność danych"):
        st.json(context.diagnostics)
