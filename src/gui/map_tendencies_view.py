"""Small M5 baseline tables with coverage, comparable conditions and round links."""

import pandas as pd
import streamlit as st

from src.demos.map_tendencies import aggregate_tendencies
from src.demos.map_tendencies_service import round_facts_key
from src.gui.map_action_view import render_actions, render_observations, render_sequence
from src.maps.registry import get_profile
from src.maps.resolver import region_label
from src.models.observations import canonical_fingerprint


def _jump(demo_id, number, seconds):
    st.session_state["pending_tactical_navigation"] = {
        "demo_id": demo_id,
        "round": number,
        "seconds": seconds,
    }


def render_map_tendencies(analysis, player_id, labels, load_facts):
    st.subheader("Tendencje mapy")
    key = "map_facts_" + round_facts_key(analysis)
    if key not in st.session_state:
        if load_facts is None:
            st.info("Zestawienia mapy są niedostępne w tym widoku.")
            return
        if not st.button("Przygotuj zestawienia mapy"):
            st.caption(
                "Pierwsze przygotowanie obejmuje wszystkie rundy. "
                "Kolejne filtry używają zapisanych wyników."
            )
            return
        try:
            with st.spinner("Zestawianie obserwacji wszystkich rund…"):
                st.session_state[key] = load_facts(analysis)
        except Exception as exc:
            st.error(f"Nie udało się przygotować zestawień: {exc}")
            return
    facts = st.session_state[key]
    teams = {}
    for fact in facts:
        for data in fact["sides"].values():
            if data["team_id"]:
                teams.setdefault(data["team_id"], set()).update(data["roster"])
    if not teams:
        st.info("Nie udało się ustalić stałej tożsamości drużyn. Nie łączymy nieznanych składów.")
        return
    options = sorted(teams)
    preferred = next((team for team in options if player_id in teams[team]), options[0])
    team = st.selectbox(
        "Drużyna",
        options,
        index=options.index(preferred),
        format_func=lambda tid: (
            "Drużyna "
            + str(options.index(tid) + 1)
            + " · "
            + ", ".join(labels.get(pid, "Gracz") for pid in sorted(teams[tid]))
        ),
        key=f"trends_team_{analysis.content_hash}",
    )
    cols = st.columns(3)
    side = cols[0].radio("Strona drużyny", ["T", "CT"], horizontal=True)
    scope = cols[1].radio("Zakres obserwacji", ["Drużyna", "Wybrany gracz"], horizontal=True)
    snapshot = cols[2].selectbox("Pozycje po [s]", [10, 15])
    selected_player = player_id if scope == "Wybrany gracz" else None
    with st.expander("Porównywalne warunki i zakres rund"):
        selected_rounds = st.multiselect(
            "Uwzględnij rundy",
            [f["number"] for f in facts],
            default=[f["number"] for f in facts],
            key=f"trends_rounds_{analysis.content_hash}",
        )
        require_values = st.checkbox("Wymagaj pełnej wyceny sprzętu obu drużyn")
        require_starting_five = st.checkbox("Tylko rundy rozpoczęte 5 na 5")
        limit_values = st.checkbox("Ogranicz wartość sprzętu wybranej drużyny")
        left, right = st.columns(2)
        minimum = left.number_input(
            "Minimalna wartość sprzętu", 0, 100000, 0, 1000, disabled=not limit_values
        )
        maximum = right.number_input(
            "Maksymalna wartość sprzętu", 0, 100000, 40000, 1000, disabled=not limit_values
        )
        st.caption(
            "Wycena dotyczy startu po freeze time. "
            "Przy filtrze wartości pomijamy rundy bez pełnej wyceny."
        )
    if limit_values and maximum < minimum:
        st.info("Maksymalna wartość musi być nie mniejsza od minimalnej.")
        return
    report = aggregate_tendencies(
        facts,
        team_id=team,
        side=side,
        player_id=selected_player,
        snapshot_seconds=snapshot,
        round_numbers=selected_rounds,
        equipment_min=minimum if limit_values else None,
        equipment_max=maximum if limit_values else None,
        require_equipment=require_values,
        require_starting_five=require_starting_five,
    )
    if not report["rounds"]:
        st.info("Brak rund spełniających filtry dla tej drużyny, strony i gracza.")
        return
    profile = get_profile(analysis.map_name)

    def area(rid):
        return {"__unknown__": "Nieustalone", "__dead__": "Nie żył w chwili pomiaru"}.get(
            rid, region_label(rid, profile)
        )

    def label(name, key):
        if name == "directions":
            return {
                "other": "Pozostałe kierunki",
                "mixed": "Brak jednego dominującego kierunku",
                "no_alive": "Brak żywych T",
            }.get(key, key)
        if name == "opening":
            return ("Opening kill" if key[0] == "kill" else "Opening death") + " · " + area(key[1])
        if name == "utility":
            return f"{key[0]} · {area(key[1])} → {area(key[2])}"
        return key if name in {"ct_setups", "entries"} else area(key)

    proof = []

    def table(name, heading):
        st.markdown(f"**{heading}**")
        rows = report["tables"][name]
        if not rows:
            st.caption("Brak zarejestrowanych przypadków w tym zakresie. Sprawdź pokrycie danych.")
            return
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Obserwacja": label(name, row["key"]),
                        "Liczba": row["count"],
                        "Mianownik": row["denominator"],
                        "% obserwacji": round(row["percentage"], 1),
                        "Mediana czasu [s]": round(row["median_seconds"], 1)
                        if row["median_seconds"] is not None
                        else None,
                        "Rundy": ", ".join(map(str, row["rounds"])),
                    }
                    for row in rows
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        proof.extend((heading + " · " + label(name, row["key"]), row["examples"]) for row in rows)

    n = len(report["rounds"])
    st.caption(
        f"{n} rund · strona {side} · pominięte przez filtry: {len(report['omitted'])}. "
        "Kierunek i ustawienie drużyny pozostają kontekstem zespołowym także przy wybranym graczu."
    )
    tabs = st.tabs(
        [
            "Ustawienie i kierunki",
            "Kontakt i wynik",
            "Utility i warunki",
            "Ataki T" if side == "T" else "Obrona i rotacje CT",
            "Następstwo rund",
            "Wnioski z danych",
        ]
    )
    with tabs[0]:
        if side == "T":
            table("directions", f"Dominujący kierunek żywych T po {snapshot} s — jednostka: runda")
            st.caption("Pozycje w ustalonym czasie nie dowodzą celu ataku ani strategii.")
        else:
            table("ct_setups", "Sektory CT przed pierwszym kontaktem — jednostka: runda")
            st.caption(
                "Snapshot przed kontaktem ma różny czas w różnych rundach. "
                "Mediana jest podana w tabeli."
            )
        table("positions", f"Pozycje po {snapshot} s — jednostka: gracz w rundzie")
        if side == "T":
            table("entries", "Potwierdzone wejścia T — jednostka: zaobserwowane wejście")
            st.caption(
                "Pierwsze potwierdzone przekroczenia nie są mianownikiem wszystkich prób ataku."
            )
    with tabs[1]:
        table(
            "contacts",
            "Pierwszy zarejestrowany kontakt gracza — jednostka: kontakt"
            if selected_player
            else "Pierwszy zarejestrowany kontakt rundy — jednostka: kontakt",
        )
        table("opening", "Miejsca openingów — jednostka: zdarzenie")
        st.caption(
            "Pierwsze fragi w tym samym ticku są równorzędne. "
            "Miejsce dotyczy zawodnika wybranej strony."
        )
        refrags, advantage = report["refrags"], report["advantage"]
        if refrags["events"]:
            proof.append(("Fragi wymieniające — autor odpowiedzi", refrags["kills"]))
        if advantage["examples"]:
            proof.append(("Rundy z przewagą liczebną", advantage["examples"]))
        refrag_frequency = (
            f"Rundy z wymianą: {len(refrags['rounds_with'])}/{refrags['known_rounds']}."
            if refrags["known_rounds"]
            else "Brak pełnych danych do wyliczenia częstości."
        )
        st.write(
            f"**Refragi do 5 s:** {refrags['trade_kills']} unikalnych fragów wymieniających, "
            f"{refrags['traded_deaths']} wymienionych zgonów. " + refrag_frequency
        )
        st.caption(
            "Filtr gracza wybiera autora fraga wymieniającego. "
            "Jeden frag może wymienić kilku kolegów."
        )
        incomplete = sorted(
            {
                item["round"]
                for row in report["tables"]["contacts"]
                for item in row["examples"]
                if item["source_status"] != "observed"
            }
        )
        if incomplete:
            st.caption(
                "Kontakt to pierwsza dostępna obserwacja przy niepełnych źródłach w rundach: "
                + ", ".join(map(str, incomplete))
            )
        if advantage["known_result_rounds"]:
            st.write(
                f"**Rundy z przewagą liczebną drużyny:** wygrane "
                f"{len(advantage['wins'])}/{len(advantage['known_result_rounds'])} "
                "rund z zaobserwowaną przewagą i znanym wynikiem."
            )
        else:
            st.write(
                "**Przewaga liczebna drużyny:** brak rund z rozstrzygniętą przewagą i wynikiem."
            )
        st.caption(
            "Przewaga mogła pojawić się w dowolnym momencie. "
            "Odsetek nie dowodzi jakości decyzji ani wpływu gracza."
        )
    with tabs[2]:
        table(
            "utility",
            f"Early utility, 0–{', '.join(map(str, report['early_seconds']))} s "
            "— jednostka: zarejestrowany rzut",
        )
        st.caption(
            "Miejsce rzutu i efektu są osobne. Nieustalony efekt nie znika z mianownika. "
            "Powiązanie autora/typu/czasu pozostaje ograniczone."
        )
        utility_examples = [item for row in report["tables"]["utility"] for item in row["examples"]]
        st.write(
            f"**Early utility ze spawnu:** {sum(item['from_spawn'] for item in utility_examples)} "
            "zarejestrowanych rzutów; nieustalone miejsce rzutu: "
            f"{sum(item['key'][1] == '__unknown__' for item in utility_examples)}."
        )
        st.markdown("**Warunki rund — wartości sprzętu na starcie**")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Runda": row["round"],
                        "Sprzęt drużyny": row["own"]["economy"]["current_equip_value"]["total"],
                        "Sprzęt rywala": row["opponent"]["economy"]["current_equip_value"]["total"],
                        "Odczyt wyceny": str(
                            row["own"]["economy"]["current_equip_value"]["known_players"]
                        )
                        + "/5",
                        "Poprzedni wynik": {"win": "Wygrana", "loss": "Przegrana"}.get(
                            row["previous_result"], "—"
                        ),
                        "Ocalałych poprzednio": len(row["previous_survivors"])
                        if row["previous_survivors"] is not None
                        else None,
                    }
                    for row in report["equipment"]
                ]
            ),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Przeżycie nie dowodzi zachowania konkretnej broni. "
            "Zmiana stron, luka lub rozpoznany reset przerywa porównanie."
        )
    with tabs[3]:
        render_actions(report, area, labels, proof)
    with tabs[4]:
        render_sequence(report, proof)
    with tabs[5]:
        render_observations(report, area, proof)
    with st.expander("Pokrycie danych"):
        names = {
            "directions": "Kierunek",
            "snapshots": "Pełny snapshot",
            "ct_setups": "Sektory CT",
            "contacts": "Kontakty",
            "opening": "Opening",
            "utility": "Rzuty",
            "refrags": "Refragi",
            "advantage": "Przewaga",
        }
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Dane": names[name],
                        "Rozstrzygnięte rundy": value["known"],
                        "W zakresie": value["eligible"],
                        "Nieustalone rundy": ", ".join(map(str, value["unknown_rounds"])),
                        "Nie dotyczy (runda zakończona)": ", ".join(
                            map(str, value["not_applicable_rounds"])
                        ),
                    }
                    for name, value in report["coverage"].items()
                    if name != "ct_setups" or side == "CT"
                ]
            ),
            hide_index=True,
        )
        st.caption(
            "Niejednoznaczna tożsamość drużyny: "
            + ", ".join(map(str, report["unknown_team_rounds"]))
        )
        if report["reset_coverage"] == "limited":
            st.caption(
                "Źródła nie opisują wszystkich resetów ekonomii. "
                "Nie potwierdzamy pełnej porównywalności dogrywek."
            )
    with st.expander("Rundy źródłowe i przejście do radaru"):
        if proof:
            selection_key = canonical_fingerprint(
                {
                    "team": team,
                    "side": side,
                    "player": selected_player,
                    "snapshot": snapshot,
                    "rounds": report["rounds"],
                }
            )[:12]
            chosen = st.selectbox(
                "Zestawienie",
                range(len(proof)),
                format_func=lambda i: proof[i][0],
                key=f"trend_proof_{selection_key}",
            )
            examples = proof[chosen][1]
            index = st.selectbox(
                "Obserwacja źródłowa",
                range(len(examples)),
                format_func=lambda i: (
                    f"Runda {examples[i]['round']} · "
                    + (
                        f"{examples[i]['seconds']:.1f} s"
                        if examples[i]["seconds"] is not None
                        else "czas nieustalony"
                    )
                ),
                key=f"trend_example_{selection_key}_{chosen}",
            )
            item = examples[index]
            st.button(
                "Przejdź do analizy tej rundy",
                on_click=_jump,
                args=(analysis.content_hash, item["round"], item["seconds"]),
                key=f"trend_jump_{selection_key}",
            )
