"""Readable source rows for round claims; internal player IDs stay hidden."""

import pandas as pd
import streamlit as st

from src.gui.foundation_view import BOMB_LABELS


SOURCE_LABELS = {
    "states": "Pozycja", "damage": "Obrażenia", "kills": "Zabójstwo",
    "throws": "Rzut granatu", "utility": "Efekt granatu", "blinds": "Oślepienie",
    "bombs": "Bomba", "bomb_updates": "Bomba", "equipment": "Wyposażenie",
    "economy": "Ekonomia", "shots": "Strzał", "smokes": "Dym",
}


def evidence_rows(ids, evidence, labels, freeze_tick, tick_rate, *, limit=12):
    events = sorted((evidence[eid] for eid in dict.fromkeys(ids) if eid in evidence),
                    key=lambda item: (item.tick, item.id))
    rows = []
    for event in events[:limit]:
        data = event.data
        actor_id = (data.get("attacker_steamid") if event.source in {"kills", "damage", "blinds"}
                    else data.get("user_steamid", data.get("steamid")))
        victim_id = data.get("user_steamid") if event.source in {"kills", "damage", "blinds"} else None
        action = data.get("event") or data.get("kind") or data.get("weapon")
        rows.append({
            "Czas [s]": round(max(0, (event.tick - freeze_tick) / tick_rate), 2)
            if freeze_tick is not None else None,
            "Źródło": SOURCE_LABELS.get(event.source, event.source),
            "Zdarzenie": BOMB_LABELS.get(action, str(action)) if action else "—",
            "Gracz": labels.get(str(actor_id), "—") if actor_id is not None else "—",
            "Cel": labels.get(str(victim_id), "—") if victim_id is not None else "—",
        })
    return pd.DataFrame(rows), len(events)


def render_evidence(ids, evidence, labels, freeze_tick, tick_rate, *, limit=12):
    rows, total = evidence_rows(ids, evidence, labels, freeze_tick, tick_rate, limit=limit)
    if rows.empty:
        st.caption("Brak pojedynczego zdarzenia źródłowego; podstawą jest zegar rundy lub stan dostępności danych.")
        return
    st.dataframe(rows, hide_index=True)
    if total > limit:
        st.caption(f"Pokazano pierwszych {limit} z {total} zdarzeń źródłowych.")
