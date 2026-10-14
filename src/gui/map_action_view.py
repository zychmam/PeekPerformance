"""Readable M5 action tables; every group retains source round navigation."""

from collections import defaultdict

import pandas as pd
import streamlit as st

KINDS = {
    "forward_presence": "Wysunięta obecność",
    "positional_presence": "Obrona pozycyjna",
    "withdrawal_from_forward": "Wycofanie z wysunięcia",
}
OUTCOMES = {
    "observed_presence": "Obecność na site",
    "not_observed": "Nie zaobserwowano",
    "planted": "Plant",
    "round_end": "Koniec rundy",
    "withdrawn": "Wycofanie",
    "stopped": "Atak zatrzymany",
    "plant": "Plant",
    "coverage_gap": "Luka danych",
    "arrived": "Dotarł",
    "unknown": "Nieustalone",
    "no_observed_arrival": "Bez dotarcia",
    "interrupted_by_death": "Śmierć po sygnale",
    "won": "Wygrany",
    "lost": "Przegrany",
    "no_attempt": "Potwierdzony brak próby",
    "eligible": "Poza sektorem — okazja do reakcji",
    "already_in_sector": "Już w sektorze",
    "dead": "Nie żył",
}
DIMENSIONS = {
    "direction_10s": "Kierunek po 10 s",
    "first_target": "Cel pierwszej próby",
    "first_tempo": "Okno startu pierwszej próby",
    "early_utility": "Early utility (typ i obszary)",
    "ct_setup": "Ustawienie sektorów CT",
}


def _number(value):
    return round(value, 1) if value is not None else None


def _ratio(value):
    return f"{value['count']}/{value['denominator']}" + (
        f" · ? {value['unknown']}" if value["unknown"] else ""
    )


def _frame(rows):
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.caption(
            "Brak zarejestrowanych przypadków. Sprawdź pokrycie; "
            "brak obserwacji może być luką danych."
        )


def render_actions(report, area, labels, proof):
    actions = report["actions"]
    if report["side"] == "T":
        coverage = actions["attack_coverage"]
        st.caption(
            f"Próby T: pełne rozstrzygnięcie "
            f"{len(coverage['known_rounds'])}/{coverage['eligible']} rund. "
            f"Niepełne/nieustalone: {', '.join(map(str, coverage['unknown_rounds'])) or '—'}."
        )
        st.markdown("**Cele prób i skuteczność**")
        _frame(
            [
                {
                    "Site": x["site"] or "Nieustalony",
                    "Próby": x["count"],
                    "Wszystkie próby": x["denominator"],
                    "Rundy": ", ".join(map(str, x["rounds"])),
                    "Wejście / znane próby": _ratio(x["entry"]),
                    "Plant / znane próby": _ratio(x["plant"]),
                    "Wygrane / znane rundy": _ratio(x["wins"]),
                }
                for x in actions["sites"]
            ]
        )
        if actions["sites"]:
            st.bar_chart(
                pd.DataFrame(
                    {
                        "Site": [x["site"] or "?" for x in actions["sites"]],
                        "Próby": [x["count"] for x in actions["sites"]],
                    }
                ).set_index("Site")
            )
        st.caption(
            "Jedna runda może zawierać kilka prób i oba cele. "
            "Wygrana rundy jest kontekstem wszystkich jej prób. "
            "Wejście oznacza obecność na site; nie dowodzi zdobycia pełnej kontroli. "
            "? oznacza nierozstrzygnięte wyniki."
        )
        st.markdown("**Końcowe planty — osobno od celów prób**")
        _frame(
            [
                {
                    "Runda": p["round"],
                    "Site": p["site"] or "Nieustalony",
                    "Czas [s]": _number(p["seconds"]),
                    "Plantujący": labels.get(p["player_id"], "Gracz"),
                }
                for p in actions["plants"]
            ]
        )
        if actions["plants"]:
            proof.append(("Końcowe planty T", actions["plants"]))
        st.caption(
            f"Pełne źródła bomby: {len(actions['bombs_known_rounds'])}"
            f"/{len(report['rounds'])} rund. "
            "Plant pozostaje kontekstem drużyny także przy filtrze gracza."
        )
        st.markdown("**Podobne wykonania — cel, okno startu, podejścia i typy utility**")
        _frame(
            [
                {
                    "Cel / start": f"{x['site'] or '?'} · {x['start_band']}",
                    "Podejścia": ", ".join(area(a) for a in x["approaches"]) or "—",
                    "Utility": ", ".join(
                        "Niepełne źródła" if k == "unknown" else k for k in x["utility_kinds"]
                    )
                    or "Brak zaobserwowanego",
                    "Próby / rundy": f"{x['attempts']} / {len(x['rounds'])}",
                    "Start [s]": _number(x["start_median"]),
                    "Czas próby [s]": _number(x["duration_median"]),
                    "Rozpiętość wejścia [s]": _number(x["entry_spread_median"]),
                }
                for x in actions["executions"]
            ]
        )
        st.caption(
            "Czasy są medianami znanych wartości. "
            "Okna 0–20 / 20–45 / >45 s opisują start od końca freeze time. "
            "Nie są klasyfikacją rush/execute. Grupy mogą zawierać pojedynczą próbę."
        )
        for x in actions["executions"]:
            proof.append((f"Próby T · {x['site']} · {x['start_band']}", x["examples"]))
        with st.expander("Próby runda po rundzie — tempo, grupa i zakończenie"):
            rows = [
                {
                    "Runda": a["round"],
                    "Site": a["target_site"],
                    "Start [s]": _number(a["seconds"]),
                    "Czas [s]": _number(a["duration_seconds"]),
                    "Przerwy ruchu [s]": _number(a["pauses_seconds"]),
                    "Referencja tempa": labels.get(a["tempo_reference_player_id"], "Gracz"),
                    "Grupa": ", ".join(labels.get(pid, "Gracz") for pid in a["main_group"]),
                    "Poza grupą": ", ".join(
                        labels.get(pid, "Gracz") for pid in a["detached_players"]
                    ),
                    "Wejście": OUTCOMES.get(a["entry_outcome"], "Nieustalone"),
                    "Plant": OUTCOMES.get(a["plant_outcome"], "Nieustalone"),
                    "Zakończenie": OUTCOMES.get(a["end_reason"], "Nieustalone"),
                    "Wygrywa": a["round_outcome"],
                    "Dane": "Zaobserwowano" if a["status"] == "observed" else "Niepełne",
                }
                for a in actions["attempts"]
            ]
            _frame(rows)
            st.caption(
                "Przerwy ruchu dotyczą wskazanego gracza referencyjnego. "
                "Udział poza grupą może zmieniać się w trakcie próby."
            )
        st.markdown("**Utility towarzyszące próbom**")
        groups = defaultdict(list)
        for u in actions["utility"]:
            groups[
                (
                    u["site"],
                    u["start_band"],
                    u["kind"],
                    u["origin_area"],
                    u["effect_area"],
                    u["phase"],
                )
            ].append(u)
        _frame(
            [
                {
                    "Cel / start": f"{k[0]} · {k[1]}",
                    "Granat": k[2],
                    "Skąd → gdzie": f"{area(k[3])} → {area(k[4])}",
                    "Faza": "Przed próbą" if k[5] == "before" else "Podczas",
                    "Powiązania z próbą": len(v),
                    "Rundy": ", ".join(map(str, sorted({u["round"] for u in v}))),
                }
                for k, v in groups.items()
            ]
        )
        proof.extend((f"Utility próby · {k[0]} · {k[2]}", v) for k, v in groups.items())
        st.caption(
            "Rzut może towarzyszyć więcej niż jednej próbie; jednostką jest powiązanie. "
            "Relacja czasu/miejsca "
            "nie dowodzi skuteczności granatu. Pełne źródła utility: "
            f"{len(actions['utility_known_rounds'])}/{len(report['rounds'])} rund."
        )
        st.markdown("**Zawodnicy poza główną grupą podczas ataku**")
        _frame(
            [
                {
                    "Runda / cel": f"{a['round']} · {a['site']}",
                    "Gracz": labels.get(a["player_id"], "Gracz"),
                    "Obszary": ", ".join(dict.fromkeys(area(i["area"]) for i in a["intervals"])),
                    "Kontakty": len({cid for i in a["intervals"] for cid in i["contact_ids"]}),
                    "Utility": len(
                        {uid for i in a["intervals"] for uid in i["utility_context_ids"]}
                    ),
                    "Dołączył": "Tak" if a["joined_tick"] is not None else "Nie zaobserwowano",
                    "Kontakty z rotującymi CT": len(a["rotation_contact_ids"]),
                }
                for a in actions["detached"]
            ]
        )
        if actions["detached"]:
            proof.append(("Działania poza grupą", actions["detached"]))
        st.caption(
            "To opis obecności i zdarzeń. Nie dowodzi roli lurka ani celowego odcięcia rotacji."
        )
    else:
        st.caption(
            f"Pełne pokrycie ruchu CT: {len(actions['movement_coverage']['known_rounds'])}"
            f"/{len(report['rounds'])} rund. "
            "Obecność wysunięta wynika z profilu mapy; nie potwierdza bezpiecznej kontroli obszaru."
        )
        groups = defaultdict(list)
        for a in actions["activity"]:
            groups[(a["kind"], a["area"])].append(a)
        st.markdown("**Aktywność CT i późniejsze pozycje**")
        _frame(
            [
                {
                    "Działanie": KINDS.get(k[0], k[0]),
                    "Obszar": area(k[1]),
                    "Okresy gracza": len(v),
                    "Rundy": ", ".join(map(str, sorted({a["round"] for a in v}))),
                    "Łączny czas graczy [s]": _number(sum(a["duration_seconds"] or 0 for a in v)),
                    "Kontakty": len({cid for a in v for cid in a["contact_ids"]}),
                    "Późniejsze obszary": ", ".join(sorted({area(a["next_area"]) for a in v})),
                }
                for k, v in groups.items()
            ]
        )
        proof.extend((f"CT · {KINDS.get(k[0], k[0])} · {area(k[1])}", v) for k, v in groups.items())
        st.caption(
            "Czasy kilku graczy nakładają się. "
            "Późniejsza pozycja opisuje następstwo, nie korzyść taktyczną."
        )
        st.markdown("**Utility przy obronie**")
        utility_groups = defaultdict(list)
        for u in actions["utility"]:
            utility_groups[(u["activity"], u["kind"], u["origin_area"], u["effect_area"])].append(u)
        _frame(
            [
                {
                    "Działanie": KINDS.get(k[0], k[0]),
                    "Granat": k[1],
                    "Skąd → gdzie": f"{area(k[2])} → {area(k[3])}",
                    "Powiązania": len(v),
                    "Próby T w tym czasie": ", ".join(
                        sorted(
                            {
                                f"{r['site']} · {'przed' if r['phase'] == 'before' else 'podczas'}"
                                for u in v
                                for r in u.get("attack_relations", [])
                            }
                        )
                    )
                    or "Nie zaobserwowano",
                    "Rundy": ", ".join(map(str, sorted({u["round"] for u in v}))),
                }
                for k, v in utility_groups.items()
            ]
        )
        proof.extend((f"CT utility · {k[1]} · {area(k[2])}", v) for k, v in utility_groups.items())
        st.markdown("**Reakcje na nazwany kontakt lub plant**")
        summary = actions["rotation_summary"]
        st.write(
            f"Dotarcia: {summary['arrived']}/{summary['eligible']} okazji spoza sektora. "
            f"Nieustalona kwalifikacja: {summary['unknown']}."
        )
        st.write(
            f"Mediana opuszczenia sektora względem sygnału: {summary['reaction_median']} s "
            f"({summary['reaction_known']} pomiarów); "
            f"przejście do celu: {summary['travel_median']} s "
            f"({summary['travel_known']} pomiarów)."
        )
        _frame(
            [
                {
                    "Runda": r["round"],
                    "Gracz": labels.get(r["player_id"], "Gracz"),
                    "Cel": r["target_site"],
                    "Sygnał": "Plant" if r["trigger_kind"] == "plant" else "Zarejestrowany kontakt",
                    "Opuszczenie sektora [s]": _number(r["reaction_seconds"]),
                    "Droga [s]": _number(r["travel_seconds"]),
                    "Wynik": OUTCOMES.get(r["outcome"], r["outcome"]),
                }
                for r in actions["rotations"]
            ]
        )
        if actions["rotations"]:
            proof.append(("Reakcje CT", actions["rotations"]))
        with st.expander("Wszystkie okazje do reakcji — kwalifikacja"):
            _frame(
                [
                    {
                        "Runda": o["round"],
                        "Gracz": labels.get(o["player_id"], "Gracz"),
                        "Cel": o["target_site"],
                        "Status": OUTCOMES.get(o["status"], o["status"]),
                    }
                    for o in actions["opportunities"]
                ]
            )
        st.caption(
            "Ujemny czas oznacza ruch rozpoczęty przed sygnałem. "
            "Mierzymy opuszczenie sektora względem zdarzenia, nie moment zauważenia przeciwnika. "
            "Kolejny sygnał może tworzyć nową okazję dla tego samego gracza."
        )
        st.markdown("**Retake — kontekst drużyny**")
        attempted = [r for r in actions["retakes"] if r.get("episode")]
        known_outcomes = [r for r in attempted if r.get("outcome") in {"won", "lost"}]
        st.write(
            f"Wygrane: {sum(r['outcome'] == 'won' for r in known_outcomes)}/{len(known_outcomes)} "
            f"prób ze znanym wynikiem. Próby ogółem: {len(attempted)}; "
            "Potwierdzony brak próby: "
            f"{sum(r.get('outcome') == 'no_attempt' for r in actions['retakes'])}."
        )
        _frame(
            [
                {
                    "Runda": r["round"],
                    "Próba": "Tak"
                    if r.get("episode")
                    else "Nie dotyczy"
                    if r["status"] == "not_applicable"
                    else OUTCOMES.get(r.get("outcome"), "Nieustalone"),
                    "Wynik": OUTCOMES.get(r.get("outcome"), "—"),
                    "Uczestnicy": ", ".join(labels.get(pid, "Gracz") for pid in r["participants"]),
                    "Defuse": "Tak" if r.get("defuse_id") else "Nie zaobserwowano",
                }
                for r in actions["retakes"]
            ]
        )
        retake_examples = [r for r in actions["retakes"] if r.get("episode")]
        if retake_examples:
            proof.append(("Retake CT", retake_examples))
        st.caption(
            "Filtr gracza zawęża aktywność i reakcje; wynik retake pozostaje kontekstem drużyny."
        )


def render_sequence(report, proof):
    sequence = report["sequence"]
    st.caption(
        "Porównujemy tylko sąsiednie rundy tej samej drużyny i strony w wybranym zakresie. "
        "Zmiana składu, reset, zmiana stron lub luka przerywa porównanie. "
        "To następstwo, nie dowód świadomej adaptacji."
    )
    _frame(
        [
            {
                "Po wyniku": "Wygrana" if s["previous_result"] == "win" else "Przegrana",
                "Cecha": DIMENSIONS[s["dimension"]],
                "Powtórzone": s["repeated"],
                "Zmienione": s["changed"],
                "Znane pary": s["denominator"],
                "Nieustalone": s["unknown"],
            }
            for s in sequence["summaries"]
        ]
    )
    proof.extend(
        (f"Następstwo · {DIMENSIONS[s['dimension']]} · {s['previous_result']}", s["examples"])
        for s in sequence["summaries"]
        if s["examples"]
    )
    with st.expander("Pary rund i zmiana zasobów"):
        rows = [
            {
                "Rundy": f"{p['previous_round']} → {p['round']}",
                "Poprzedni wynik": p["previous_result"],
                "Zmiana sprzętu drużyny": p["equipment_delta"],
                "Zmiana sprzętu rywala": p["opponent_equipment_delta"],
                **{
                    DIMENSIONS[d]: {
                        "changed": "Zmiana",
                        "repeated": "Powtórzenie",
                        "unknown": "Nieustalone",
                    }[v]
                    for d, v in p["transitions"].items()
                },
            }
            for p in sequence["pairs"]
        ]
        _frame(rows)
    st.caption(
        "Bez porównywalnego poprzednika: "
        + (", ".join(map(str, sequence["excluded_rounds"])) or "—")
        + ". Zestawienie nie wyrównuje ekonomii automatycznie; użyj filtrów wartości sprzętu."
    )


def render_observations(report, area, proof):
    st.markdown("**Najczęstsze zaobserwowane powtórzenia**")
    observations = []
    actions = report["actions"]
    if report["side"] == "T":
        for site in actions["sites"]:
            if len(site["rounds"]) >= 2:
                observations.append(
                    (
                        f"Cel {site['site']}: {site['count']}/{site['denominator']} "
                        "zarejestrowanych prób "
                        f"w {len(site['rounds'])} rundach; wejście {_ratio(site['entry'])}, "
                        f"plant {_ratio(site['plant'])}, wygrane rundy {_ratio(site['wins'])}.",
                        site["examples"],
                    )
                )
    else:
        groups = defaultdict(list)
        for a in actions["activity"]:
            if a["kind"] == "forward_presence":
                groups[a["area"]].append(a)
        known_rounds = set(actions["movement_coverage"]["known_rounds"])
        for rid, examples in sorted(groups.items(), key=lambda p: -len({a["round"] for a in p[1]}))[
            :2
        ]:
            rounds = {a["round"] for a in examples} & known_rounds
            if len(rounds) >= 2:
                observations.append(
                    (
                        f"Wysunięta obecność CT w {area(rid)}: {len(rounds)}/{len(known_rounds)} "
                        "rund z pełnym pokryciem ruchu.",
                        [a for a in examples if a["round"] in rounds],
                    )
                )
    for name, title in (("contacts", "Pierwszy dostępny kontakt"), ("utility", "Early utility")):
        for row in report["tables"][name][:1]:
            if len(row["rounds"]) >= 2:
                text = (
                    area(row["key"])
                    if name == "contacts"
                    else f"{row['key'][0]}: {area(row['key'][1])} → {area(row['key'][2])}"
                )
                observations.append(
                    (
                        f"{title} — {text}: {row['count']}/{row['denominator']} obserwacji "
                        f"w {len(row['rounds'])} rundach; "
                        f"pełne źródła {report['coverage'][name]['known']}"
                        f"/{report['coverage'][name]['eligible']} rund.",
                        row["examples"],
                    )
                )
    for summary in report["sequence"]["summaries"]:
        if summary["denominator"] >= 2 and summary["dimension"] in {"first_target", "ct_setup"}:
            result = "wygranej" if summary["previous_result"] == "win" else "przegranej"
            observations.append(
                (
                    f"Po {result}: {DIMENSIONS[summary['dimension']].lower()} "
                    f"powtórzono w {summary['repeated']}/{summary['denominator']} "
                    "znanych par rund, "
                    f"zmieniono w {summary['changed']}/{summary['denominator']}. "
                    f"Nieustalone pary: {summary['unknown']}; ekonomia jest w zestawieniu par.",
                    summary["examples"],
                )
            )
    for text, examples in observations[:5]:
        st.write("• " + text)
        proof.append((text, examples))
    if not observations:
        st.info(
            "Za mało powtarzających się obserwacji. "
            "Szczegółowe dane poszczególnych rund są w pozostałych zakładkach."
        )
    st.caption(
        "Powtórzenie wymaga co najmniej dwóch różnych rund. "
        "To opis tego meczu; nie ocena jakości decyzji "
        "ani rekomendacja coacha. Braki i szczegóły są w odpowiednich zestawieniach."
    )
