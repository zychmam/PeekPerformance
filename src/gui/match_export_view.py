"""One replacement JSON export for the entire match, independent of view filters."""

from pathlib import Path

import streamlit as st

from src.demos.match_report import encode_match_report, report_cache_key


def render_match_export(analysis, load_report):
    st.subheader("Raport meczu do analizy — JSON")
    st.caption(
        "Cały mecz i wszyscy gracze: wynik, statystyki, rundy, analizy taktyczne, "
        "tendencje mapy, definicje i ograniczenia. Aktualne filtry nie ograniczają eksportu. "
        "Surowe trajektorie i każdy strzał są pominięte."
    )
    if load_report is None:
        st.info("Eksport raportu jest niedostępny w tym widoku.")
        return
    key = report_cache_key(analysis)
    if st.button("Przygotuj raport JSON", key=f"prepare_{key}"):
        try:
            with st.spinner("Przygotowanie danych wszystkich rund i graczy…"):
                report = load_report(analysis)
                st.session_state[key] = (report, encode_match_report(report))
        except Exception as exc:
            st.error(f"Nie udało się przygotować raportu: {exc}")
            return
    if key not in st.session_state:
        return
    report, payload = st.session_state[key]
    header = report["header"]
    reconciliation = report["limitations"].get("statistics_reconciliation", {})
    if reconciliation.get("status") == "discrepancy":
        st.info(
            f"Kontrola źródeł: różnica {reconciliation['difference']} między liczbą fragów "
            "źródłowych a kalkulatorem aplikacji. Raport zawiera wyjaśnienie i zdarzenia "
            "w limitations.statistics_reconciliation."
        )
    st.caption(
        f"Format {header['schema_version']} · {header['round_count']} rund · "
        f"{header['player_count']} graczy · {len(payload) / 1024:.0f} KiB. "
        "Plik UTF-8 zawiera własną instrukcję odczytu i krótkie ID graczy zamiast SteamID."
    )
    st.download_button(
        "Pobierz raport JSON",
        payload,
        file_name=f"{Path(analysis.file_name).stem}_match_report_v{header['schema_version']}.json",
        mime="application/json",
        key=f"download_{key}",
    )
    with st.expander("Nagłówek i instrukcja odczytu raportu"):
        st.json({"header": header, "reading_guide": report["reading_guide"]})
