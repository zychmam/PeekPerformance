"""Compact, evidence-backed R2 team preparation view."""

import pandas as pd
import streamlit as st

from src.demos.coach_foundations import FOUNDATION_VERSION
from src.demos.early_interpretation import INTERPRETATION_VERSION
from src.demos.early_round import EARLY_DETECTOR_VERSION
from src.demos.spatial_service import context_key, round_analysis
from src.demos.tactical_rounds import build_tactical_match
from src.maps.resolver import region_label
from src.models.observations import RoundClock
from src.models.tactical import Status

STATUS_LABELS = {
    Status.OBSERVED: "Pełne obserwacje",
    Status.PARTIAL: "Niepełne obserwacje",
    Status.UNKNOWN: "Brak wystarczających danych",
    Status.ABSENT: "Nie zaobserwowano",
}


def area_label(value, profile=None):
    return region_label(value, profile)


def render_early_round(analysis, context, rnd, labels):
    presentation = context.profile.presentation_fingerprint if context.profile else "none"
    key = (
        f"early_{EARLY_DETECTOR_VERSION}_{INTERPRETATION_VERSION}_"
        f"foundation_{FOUNDATION_VERSION}_{context_key(analysis, context.profile)}_"
        f"{presentation}_{rnd}"
    )
    if key not in st.session_state:
        match = build_tactical_match(
            round_analysis(analysis, rnd),
            context,
            foundations=getattr(context, "foundations", None),
        )
        # Keep the compact observations, not a second copy of all source evidence.
        refs = {
            eid
            for r in match.rounds
            for p in (r.t_preparation, r.ct_setup)
            for finding in p.findings
            for eid in finding.evidence_ids
        }
        st.session_state[key] = {
            "rounds": {r.number: r for r in match.rounds},
            "proof": {
                eid: {
                    "Źródło": match.evidence[eid].source,
                    "Tick": match.evidence[eid].tick,
                    "Czas [s]": match.evidence[eid].seconds,
                }
                for eid in refs
            },
            "foundation_events": {
                r.number: [match.evidence[eid] for eid in r.bomb_event_ids] for r in match.rounds
            },
        }
    record = st.session_state[key]["rounds"][rnd]
    clock = RoundClock.from_row(
        context.clock[context.clock.total_rounds_played.eq(rnd)].iloc[0].to_dict()
    )
    st.markdown("### Początek rundy · 0–15 s")
    for col, side, prep in zip(
        st.columns(2), ("T", "CT"), (record.t_preparation, record.ct_setup), strict=True
    ):
        with col:
            st.markdown(f"**{side} · podsumowanie przygotowania**")
            visible = [
                f
                for f in prep.findings
                if not (prep.formation and f.text.startswith("Po ") and side == "T")
            ]
            if not visible:
                st.caption("Za mało danych do podsumowania przygotowania.")
            for finding in visible:
                prefix = "Interpretacja: " if finding.kind == "interpretation" else ""
                st.write(prefix + finding.text)
            if visible:
                with st.expander(f"Dowody podsumowania {side}"):
                    for finding in visible:
                        st.write(finding.text)
                        for limit in finding.limitations:
                            st.caption(limit)
                        rows = [st.session_state[key]["proof"][eid] for eid in finding.evidence_ids]
                        st.caption(
                            f"Dowodów: {len(rows)}. "
                            + ("Pokazano pierwszych 12." if len(rows) > 12 else "")
                        )
                        st.dataframe(pd.DataFrame(rows[:12]), hide_index=True)
    before = any(p.setup_before_contact for p in (record.t_preparation, record.ct_setup))
    moments = ["Przed pierwszym kontaktem", 0, 5, 10, 15] if before else [0, 5, 10, 15]
    moment = st.selectbox(
        "Moment ustawienia",
        moments,
        index=0 if before else 2,
        key=f"early_moment_{analysis.content_hash}_{rnd}",
    )
    for col, side, prep in zip(
        st.columns(2), ("T", "CT"), (record.t_preparation, record.ct_setup), strict=True
    ):
        with col:
            is_before = isinstance(moment, str)
            st.markdown(f"**{side} · {moment}{'' if is_before else ' s'}**")
            snap = (
                prep.setup_before_contact
                if is_before
                else next((s for s in prep.snapshots if s.seconds == moment), None)
            )
            if snap is None:
                st.caption("Brak próbki w obrębie rundy.")
            else:
                st.write(
                    " · ".join(
                        f"{area_label(area, context.profile)}: {n}"
                        for area, n in snap.counts.items()
                    )
                    or "Brak zaobserwowanych żywych graczy w znanych strefach."
                )
                st.caption(STATUS_LABELS[snap.status])
                if is_before:
                    st.caption(
                        f"Ustawienie {snap.seconds:.2f} s od końca freeze time; "
                        "wyłącznie próbki sprzed pierwszego zaobserwowanego kontaktu."
                    )
                with st.expander(f"Pozycje {side} i ruch w 0–15 s"):
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Gracz": labels.get(p["player_id"], "Gracz"),
                                    "Strefa": area_label(p["area"], context.profile)
                                    if p["alive"]
                                    else "Nie żyje",
                                    "Pozycja": area_label(p["area"], context.profile),
                                    "Próbka [s]": clock.seconds(p["sample_tick"]),
                                    "Bomba": p["has_bomb"],
                                }
                                for p in snap.players
                            ]
                        ),
                        hide_index=True,
                    )
                    st.caption("Przejścia: " + STATUS_LABELS[prep.movement_status])
                    if prep.movements:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "Gracz": labels.get(m.player_id, "Gracz"),
                                        "Z": area_label(m.from_area, context.profile),
                                        "Do": area_label(m.to_area, context.profile),
                                        "Przybycie [s]": clock.seconds(m.arrival_tick),
                                        "Potwierdzenie [s]": clock.seconds(m.confirmed_tick),
                                    }
                                    for m in prep.movements
                                ]
                            ),
                            hide_index=True,
                        )
            st.caption("Utility: " + STATUS_LABELS[prep.utility_status])
            if prep.utility_windows:
                throws_quality = record.foundation.source_quality["throws"].availability.status
                throws_counts = (
                    f"{len(prep.utility_windows['10']['throws'])} / "
                    f"{len(prep.utility_windows['15']['throws'])}"
                    if throws_quality in {Status.OBSERVED, Status.ABSENT}
                    else "brak pełnych danych"
                )
                effects_counts = (
                    f"{len(prep.utility_windows['10']['effects'])} / "
                    f"{len(prep.utility_windows['15']['effects'])}"
                    if prep.utility_status in {Status.OBSERVED, Status.ABSENT}
                    else "brak pełnych danych"
                )
                st.caption(
                    f"Rzuty do 10 / 15 s: {throws_counts}. "
                    f"Zadziałania do 10 / 15 s: {effects_counts}."
                )
            if prep.utility:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Gracz": labels.get(u.player_id, "Gracz"),
                                "Typ": u.kind,
                                "Czas [s]": round(u.seconds, 2),
                                **{
                                    axis.upper(): round(value, 1) if value is not None else None
                                    for axis, value in u.position.items()
                                },
                            }
                            for u in prep.utility
                        ]
                    ),
                    hide_index=True,
                )
    st.caption(
        "Site A/B liczymy osobno od łączników i podejść. Próbka może być do 1 s "
        "starsza od wybranego momentu. Przejście wymaga utrzymania strefy przez "
        "co najmniej 1 s; przerwy ponad 2 s przerywają ścieżkę. Utility oznacza "
        "detonację/start ognia w 0–15 s, również dla granatu rzuconego wcześniej. "
        "Punkt działania nie określa pokrycia ani wpływu na zajęcie przestrzeni."
    )
    from src.gui.foundation_view import render_foundation

    render_foundation(record, st.session_state[key]["foundation_events"][rnd], labels)
    if st.button("Pokaż ustawienie na mapie", key=f"early_jump_{analysis.content_hash}_{rnd}"):
        if isinstance(moment, str):
            snapshot = (
                record.t_preparation.setup_before_contact or record.ct_setup.setup_before_contact
            )
            return max(0.0, snapshot.seconds) if snapshot else None
        return float(moment)
    return None
