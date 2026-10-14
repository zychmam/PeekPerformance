"""Compact chronology and one selected jump into the round radar."""

import pandas as pd
import streamlit as st

from src.gui.foundation_view import BOMB_LABELS
from src.gui.round_evidence_view import render_evidence
from src.models.tactical import Status


def moment_label(moment, record, evidence, labels):
    kind = moment.kind
    if kind == "round_start":
        return "Start po freeze time"
    if kind == "round_end":
        return f"Koniec · wygrywa {record.winner_side or '?'}"
    if kind in {"early_throw", "early_effect"}:
        types = sorted({str(evidence[eid].data.get("kind") or "granat")
                        for eid in moment.event_ids if eid in evidence})
        action = "Rzut" if kind == "early_throw" else "Zadziałanie"
        return f"{action} utility · {', '.join(types) or '?'}"
    if kind == "site_entry":
        entry = next((entry for entry in record.observed_entries
                      if entry.start_tick == moment.start_tick
                      and set(entry.evidence_ids) == set(moment.event_ids)), None)
        return f"Wejście T na site {entry.area or '?'}" if entry else "Wejście T na site"
    if kind == "bomb":
        events = [evidence[eid].data.get("event") for eid in moment.event_ids if eid in evidence]
        return "Bomba · " + ", ".join(dict.fromkeys(BOMB_LABELS.get(event, str(event))
                                                      for event in events))
    if kind == "alive_change":
        return "Zmiana liczebności poza kontaktem z przeciwnikiem"
    kills = [evidence[eid] for eid in moment.event_ids
             if eid in evidence and evidence[eid].source == "kills"]
    if kills:
        prefix = {"opening": "Opening", "refrag": "Refrag"}.get(kind, "Frag")
        if len(kills) > 1:
            return f"{prefix} · {len(kills)} fragi w jednym ticku"
        kill = kills[0]
        attacker = labels.get(str(kill.data.get("attacker_steamid")), "Gracz")
        victim = labels.get(str(kill.data.get("user_steamid")), "Gracz")
        return f"{prefix} · {attacker} → {victim}"
    contacts = [contact for contact in record.contacts if contact.id in moment.contact_ids]
    if contacts:
        prefix = "Pierwszy kontakt" if kind == "first_contact" else "Kontakt"
        if len(contacts) > 1:
            return f"{prefix} · {len(contacts)} zdarzenia w jednym ticku"
        contact = contacts[0]
        attacker = labels.get(contact.attacker_id, "Gracz")
        victim = labels.get(contact.victim_id, "Gracz")
        return f"{prefix} · {attacker} → {victim}"
    return "Zdarzenie rundy"


def render_round_moments(record, evidence, labels, tick_rate, slider_key, max_seconds):
    if not record.moments or record.freeze_end_tick is None:
        return
    moments = [moment for moment in record.moments
               if moment.start_tick >= record.freeze_end_tick]
    def seconds(moment):
        return max(0.0, (moment.start_tick - record.freeze_end_tick) / tick_rate)

    milestones = [moment for moment in moments if moment.kind in
                  {"round_start", "first_contact", "opening", "refrag", "site_entry", "round_end"}
                  or moment.kind == "bomb" and any(
                      evidence[eid].data.get("event") == "bomb_planted"
                      for eid in moment.event_ids if eid in evidence)]
    selected = []
    for kind in ("round_start", "first_contact", "opening", "refrag", "site_entry", "bomb", "round_end"):
        first = next((moment for moment in milestones if moment.kind == kind), None)
        if first is not None:
            selected.append(first)
    st.markdown("### Oś rundy")
    st.caption(" · ".join(f"{seconds(moment):.1f} s {moment_label(moment, record, evidence, labels)}"
                          for moment in sorted(selected, key=lambda item: item.start_tick)))
    with st.expander(f"Pełna chronologia · {len(moments)} momentów"):
        alive = {state.id: state for state in record.alive_states}
        st.dataframe(pd.DataFrame([
            {
                "Czas [s]": round(seconds(moment), 2),
                "Zdarzenie": moment_label(moment, record, evidence, labels),
                "Stan T:CT": (
                    f"{alive[moment.alive_after_id].t_alive}:{alive[moment.alive_after_id].ct_alive}"
                    if moment.alive_after_id in alive
                    and alive[moment.alive_after_id].t_alive is not None
                    and alive[moment.alive_after_id].ct_alive is not None else "—"
                ),
                "Dostępność": (
                    "zegar rundy" if moment.kind in {"round_start", "round_end"}
                    and not moment.event_ids else
                    "obserwowane" if moment.status == Status.OBSERVED else "częściowe"
                ),
            }
            for moment in moments
        ]), hide_index=True, height=360)
        index = st.selectbox("Moment na osi", range(len(moments)),
                             format_func=lambda i: f"{seconds(moments[i]):.1f} s · {moment_label(moments[i], record, evidence, labels)}",
                             key=f"moment_select_{record.number}")
        if st.button("Przejdź do momentu na mapie", key=f"moment_jump_{record.number}"):
            st.session_state[slider_key] = min(max_seconds, seconds(moments[index]))
        moment = moments[index]
        st.caption(f"Źródła: {len(moment.event_ids)} zdarzeń · "
                   f"{len(moment.contact_ids)} kontaktów. "
                   "Równe ticki nie określają kolejności działań.")
        render_evidence(moment.event_ids, evidence, labels, record.freeze_end_tick,
                        tick_rate, limit=10)
