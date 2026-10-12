"""Round input details, with player names and explicit source limitations."""

import pandas as pd
import streamlit as st

from src.models.tactical import Status

BOMB_LABELS = {
    "bomb_planted": "Plant",
    "bomb_defused": "Rozbrojenie",
    "bomb_exploded": "Eksplozja",
    "bomb_pickup": "Podniesienie",
    "bomb_dropped": "Upuszczenie",
    "bomb_beginplant": "Początek plantu",
    "bomb_abortplant": "Przerwanie plantu",
    "bomb_begindefuse": "Początek rozbrajania",
    "bomb_abortdefuse": "Przerwanie rozbrajania",
}


def render_foundation(record, bomb_events, labels):
    foundation = record.foundation
    if foundation is None:
        return
    with st.expander("Dane rundy dla coacha — wyposażenie, bomba i dostępność"):
        if not foundation.equipment_start:
            st.info("Wyposażenie wymaga uzupełnienia z pliku demo.")
        else:
            st.markdown("**Wyposażenie na początku rundy**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Gracz": labels.get(obs.player_id, "Gracz"),
                            "Ekwipunek": (
                                " · ".join(
                                    f"{item} ×{count}" for item, count in obs.inventory.items()
                                )
                                if obs.inventory is not None
                                else None
                            ),
                            "Pancerz": obs.armor,
                            "Hełm": obs.helmet,
                            "Kit": obs.defuse_kit,
                            "Wartość sprzętu": obs.economy.get("current_equip_value"),
                            "Pieniądze": obs.economy.get("balance"),
                        }
                        for obs in foundation.equipment_start
                    ]
                ),
                hide_index=True,
            )
        if bomb_events:
            st.markdown("**Przebieg bomby**")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Czas [s]": event.seconds,
                            "Zdarzenie": BOMB_LABELS.get(event.data.get("event"), "Inne"),
                            "Gracz": labels.get(str(event.data.get("user_steamid")), "Nieustalony"),
                        }
                        for event in sorted(bomb_events, key=lambda event: event.tick)
                    ]
                ),
                hide_index=True,
            )
        incomplete = [
            name
            for name, quality in foundation.source_quality.items()
            if quality.availability.status in {Status.PARTIAL, Status.UNKNOWN}
        ]
        if incomplete:
            st.caption("Źródła z ograniczeniami: " + ", ".join(incomplete))
        st.caption(
            f"Czas: {foundation.clock['tick_rate']:g} ticków/s "
            f"({foundation.clock['time_basis']}). Brak zdarzenia przerwania "
            "plantowania lub rozbrajania nie potwierdza, że próby nie przerwano."
        )
