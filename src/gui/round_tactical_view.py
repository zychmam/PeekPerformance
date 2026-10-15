"""Compact tactical action tables, nicknames and links to the existing radar."""

import pandas as pd
import streamlit as st

from src.gui.round_evidence_view import render_evidence
from src.maps.resolver import region_label
from src.models.tactical import Status

OUTCOMES = {
    "planted": "Plant",
    "entered": "Wejście",
    "stopped": "Zatrzymanie",
    "withdrawn": "Wycofanie",
    "unknown": "Nieustalone",
    "arrived": "Dotarł",
    "no_observed_arrival": "Bez przybycia",
    "interrupted_by_death": "Śmierć",
    "won": "Udany",
    "lost": "Nieudany",
    "no_attempt": "Brak wykrytej próby",
}
ACTIVITY = {
    "forward_presence": "Wysunięta obecność",
    "withdrawal_from_forward": "Wycofanie z wysunięcia",
    "positional_presence": "Obecność pozycyjna",
}


def render_tactical_actions(
    record, evidence, labels, profile, player_id, tick_rate, slider_key, max_seconds
):
    st.markdown("### Działania taktyczne")
    if not profile:
        st.info("Brak profilu mapy: dostępne są kontakty, bez interpretacji przestrzennej.")
    freeze = record.freeze_end_tick

    def seconds(tick):
        return (
            round((tick - freeze) / tick_rate, 1)
            if tick is not None and freeze is not None
            else None
        )

    def names(ids):
        return ", ".join(labels.get(pid, "Gracz") for pid in ids)

    def area(rid):
        return region_label(rid, profile) if rid else "Nieustalone"

    def table(rows):
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        else:
            st.caption("Brak wykrytych przypadków w dostępnych danych.")

    proof = []
    tabs = st.tabs(["Ataki T", "Obrona CT", "Walki i utility", "Ruch gracza"])
    with tabs[0]:
        table(
            [
                {
                    "Cel": a.target_site,
                    "Start [s]": seconds(a.episode.start_tick),
                    "Koniec [s]": seconds(a.episode.end_tick),
                    "Uczestnicy": names(a.episode.participants),
                    "Wejście [s]": seconds(a.first_entry_tick),
                    "Rezultat": OUTCOMES.get(a.outcome, "Nieustalone"),
                    "Poza grupą": names(a.detached_players) or "—",
                }
                for a in record.attacks
            ]
        )
        with st.expander("Tempo i przygotowanie prób"):
            table(
                [
                    {
                        "Cel": a.target_site,
                        "Start od freeze [s]": a.start_seconds,
                        "Rozciągnięcie pierwszych wejść [s]": a.entry_spread_seconds,
                        "Gracz odniesienia": names([a.tempo_reference_player_id]),
                        "Postoje gracza [s]": round(a.pauses_seconds, 1),
                        "Powiązane rzuty": len(a.utility_context_ids),
                    }
                    for a in record.attacks
                ]
            )
            st.caption(
                "Postój: obserwowana prędkość do 32 jednostek/s. "
                "To pomiar wskazanego gracza, nie automatyczna ocena tempa całej drużyny."
            )
        for i, attack in enumerate(record.attacks, 1):
            proof.append(
                (
                    f"Próba T {i} · {attack.target_site}",
                    attack.episode.start_tick,
                    attack.episode.evidence_ids,
                )
            )
            for action in attack.detached_actions:
                for interval in action["intervals"]:
                    st.caption(
                        f"{names([action['player_id']])} poza grupą: {area(interval['area'])}, "
                        f"{seconds(interval['start_tick'])}–{seconds(interval['end_tick'])} s; "
                        f"kontakty: {len(interval['contact_ids'])}, "
                        f"rzuty: {len(interval['utility_context_ids'])}."
                        + (
                            f" Dołączenie: {seconds(action['joined_tick'])} s."
                            if action["joined_tick"]
                            else ""
                        )
                    )
        if not record.attacks and record.t_pressure:
            st.caption(
                "Zaobserwowano obecność na podejściach; "
                "sygnał nie wystarczył do potwierdzenia próby ataku."
            )
        st.caption(
            "Start oznacza pierwszy mocny sygnał próby, nie moment podjęcia decyzji. "
            "Tempo i utility są osobnymi miarami. Wejście, plant i wynik rundy są rozdzielone."
        )
    with tabs[1]:
        setup = record.ct_sectors_before_contact
        if setup:
            st.write(
                "**Sektory CT przed kontaktem:** "
                + " · ".join(f"{key}: {value}" for key, value in setup["counts"].items())
                + f" · nieustalone: {setup['unknown']} · {seconds(setup['tick'])} s"
            )
            proof.append(("Sektory CT przed kontaktem", setup["tick"], setup["evidence_ids"]))
        table(
            [
                {
                    "Gracz": names([r.player_id]),
                    "Sygnał [s]": seconds(evidence[r.information_event_id].tick),
                    "Cel": r.target_site,
                    "Dotarcie [s]": seconds(r.arrival_tick),
                    "Opóźnienie wyjścia z sektora [s]": r.reaction_seconds,
                    "Rezultat": OUTCOMES.get(r.outcome, r.outcome),
                }
                for r in record.rotations
            ]
        )
        for rotation in record.rotations:
            proof.append(
                (
                    f"Reakcja CT · {names([rotation.player_id])} · "
                    f"{seconds(rotation.episode.start_tick)} s",
                    rotation.episode.start_tick,
                    rotation.episode.evidence_ids,
                )
            )
        with st.expander("Obecność i wysunięcia CT"):
            table(
                [
                    {
                        "Gracz": names(a.participants),
                        "Od [s]": seconds(a.start_tick),
                        "Do [s]": seconds(a.end_tick),
                        "Obszar": area(a.area),
                        "Działanie": ACTIVITY[a.kind],
                    }
                    for a in record.ct_activity
                ]
            )
        retake = record.retake
        st.write(
            "**Retake:** "
            + (
                "Nie dotyczy — brak planta"
                if retake.status == Status.NOT_APPLICABLE
                else OUTCOMES.get(retake.outcome, "Nieustalony")
            )
        )
        if retake.episode:
            proof.append(("Próba retake", retake.episode.start_tick, retake.episode.evidence_ids))
        st.caption(
            "Sektor jest przypisaniem pozycyjnym; nie dowodzi widoczności ani kontroli. "
            "Reakcja odnosi się do kontaktu/planta; "
            "czas wyjścia z sektora nie jest czasem usłyszenia informacji."
        )
    with tabs[2]:
        table(
            [
                {
                    "Od [s]": seconds(f.episode.start_tick),
                    "Do [s]": seconds(f.episode.end_tick),
                    "Obszar": area(f.area),
                    "Gracze": names(f.episode.participants),
                    "HP zadane T": f.after["damage_by_side"]["T"],
                    "HP zadane CT": f.after["damage_by_side"]["CT"],
                    "Zgony T:CT": str(f.after["deaths_by_side"]["T"])
                    + ":"
                    + str(f.after["deaths_by_side"]["CT"]),
                    "Fragi wymieniające": len({r["response_kill_id"] for r in f.refrags}),
                    "Wymienione zgony": len({r["death_id"] for r in f.refrags}),
                }
                for f in record.fights
            ]
        )
        for i, fight in enumerate(record.fights, 1):
            proof.append(
                (f"Lokalna walka {i}", fight.episode.start_tick, fight.episode.evidence_ids)
            )
        st.caption("Refrag: odpowiedź do 5 s. Jeden frag może wymienić kilka zgonów kolegów.")
        with st.expander("Rzuty i efekty granatów"):
            table(
                [
                    {
                        "Gracz": names([u.player_id]),
                        "Granat": u.kind,
                        "Rzut [s]": seconds(u.throw_tick),
                        "Skąd": area(u.origin_area),
                        "Efekt [s]": seconds(u.effect_tick),
                        "Gdzie": area(u.effect_area),
                        "Koniec [s]": seconds(u.end_tick),
                        "Powiązanie": {
                            "entity_identity": "ID granatu",
                            "unique_temporal_limited": "Autor/typ/czas — ograniczone",
                            "ambiguous": "Niejednoznaczne",
                            "unknown": "Nieustalone",
                        }.get(u.match_status, "Nieustalone"),
                        "Potwierdzone efekty": len(u.effect_ids),
                    }
                    for u in record.utility_contexts
                ]
            )
        st.caption(
            "Lokalne walki: przerwa do 5 s i odległość do 600 jednostek. "
            "HP to zarejestrowane obrażenia. "
            "Nieustalony region granatu nie oznacza braku jego współrzędnych."
        )
    with tabs[3]:
        table(
            [
                {
                    "Obszar": area(s.area),
                    "Od [s]": seconds(s.start_tick),
                    "Do [s]": seconds(s.end_tick),
                    "Pobyt [s]": round((s.end_tick - s.start_tick) / tick_rate, 1),
                    "Zakończenie": {
                        "transition": "Przejście",
                        "death": "Śmierć",
                        "gap": "Luka",
                        "round_end": "Koniec rundy",
                        "coverage_end": "Koniec pokrycia",
                    }.get(s.end_reason, s.end_reason),
                }
                for s in record.region_stays
                if s.player_id == player_id
            ]
        )
        for i, stay in enumerate(s for s in record.region_stays if s.player_id == player_id):
            proof.append(
                (f"Pobyt gracza {i + 1} · {area(stay.area)}", stay.start_tick, stay.evidence_ids)
            )
        st.caption(
            "Pobyt to obserwacja próbek, nie dowód kontroli obszaru. "
            "Luka nie jest traktowana jako potwierdzone przejście."
        )
    with st.expander("Dowody działań i skok na radar"):
        if proof:
            selected = st.selectbox(
                "Działanie",
                range(len(proof)),
                format_func=lambda i: proof[i][0],
                key=f"tactical_proof_{record.number}",
            )
            _, tick, refs = proof[selected]
            if st.button("Pokaż działanie na mapie", key=f"tactical_jump_{record.number}"):
                st.session_state[slider_key] = min(
                    max_seconds, max(0.0, (tick - freeze) / tick_rate)
                )
            render_evidence(refs, evidence, labels, freeze, tick_rate)
        else:
            st.caption("Brak wykrytych działań.")
    if record.movement_status != Status.OBSERVED:
        st.caption(
            "Pokrycie pozycji jest częściowe. "
            "Brak wykrytego działania nie oznacza pewności, że go nie było."
        )
