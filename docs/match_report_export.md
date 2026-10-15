# Raport JSON meczu — format 1.0

Jedyny eksport aplikacji, zastępujący Excel, ZIP CSV oraz przyciski eksportu
częściowych tabel M5. Przygotowany do ręcznej analizy i przekazania do LLM;
nie wywołuje API modelu. Format zaakceptowany przez użytkownika przed implementacją.

**Dane i eksport → Przygotuj raport JSON → Pobierz raport JSON**.
Eksport obejmuje cały mecz i wszystkich graczy bez filtrów aktualnego widoku.
Po przygotowaniu plik jest przechowywany w sesji; kolejne reruny/pobrania
nie uruchamiają analizy. Klucz obejmuje wersję eksportu, ratingu i faktów mapy.

## Kontrakt

`header.format = peekperformance_match_report`, `schema_version = 1.0`.
UTF-8, zwykły JSON, bez NaN/Infinity. Niezgodna zmiana formatu wymaga nowej wersji.
[Formalny JSON Schema](schemas/match_report_v1.schema.json) określa sekcje,
typy statystyk i strukturę rund. Model danych nie zależy od nazwy mapy.

| Sekcja | Znaczenie |
| --- | --- |
| header | Mapa/demo, wynik stałych drużyn, liczby rund/graczy, czas eksportu, wersje, słownik obszarów. |
| reading_guide | Opisy sekcji, jednostki, statusy, definicje statystyk, interpretacja kluczy tabel i ograniczenia. |
| teams | Składy oraz wyniki całego meczu i T/CT, bez utraty tożsamości po zmianie stron. |
| players | Lokalne ID i nick, statystyki całego meczu, T/CT i jawnie nieustalonej strony. |
| map_analysis | Zestawienia wszystkich drużyn/stron i graczy: miary, mianowniki, pokrycie, następstwo rund i udział w działaniach. |
| rounds | Zegar, wynik, zasoby, przygotowanie, walki, ataki, obrona, utility, wszyscy zawodnicy, opis regułowy i pokrycie. |
| source_events | Zdarzenia będące źródłami dowodów, z czasem i istotnymi polami. |
| limitations | Ograniczenia profilu/reguł, pominięte surowe dane i statusy kompletności. |

Statystyki gracza: fragi, zgony, asysty, damage, ADR, HS, KAST, przeżycia,
utility damage i przybliżony Peek Performance Rating. Odsetki mają
count/denominator/unit/percentage. Rating jest liczony dla całego meczu;
rating T/CT pozostaje null. Definicja KAST i ratingu jest lokalna dla projektu.
Od metryk v5 KAST obejmuje wszystkich kolegów wymienionych jednym fragiem,
z odpowiedzią w późniejszym ticku i w czasie do 5 s włącznie. Lokalna definicja
obejmuje też wkład co najmniej 40 HP w ofiarę zabitą przez kolegę; opis znajduje
się w `reading_guide.metrics.kast`. Schemat eksportu pozostaje 1.0, wersja
ratingu w nagłówku i kluczu cache zmienia się na 5.

Po M5.REV3 `coverage.sources` opisuje osobno odczyt każdego zdarzenia bomby.
Znany brak `bomb_planted` daje plant `not_observed` i retake `not_applicable`;
błąd lub nieodczytany strumień pozostaje nieznany. Zbiorcze `bombs` nie zastępuje
statusów zdarzeń. W agregatach `bombs_known_rounds` oznacza pokrycie plantów,
zgodnie z guide. Brak próby retake po plancie wymaga też znanych źródeł defuse.

## Tabele z nagłówkami

Powtarzalne rekordy mają nagłówki raz, zamiast kopiowania nazw kilkudziesięciu
pól w każdym wierszu. To oszczędza miejsce przy zachowaniu znaczenia:

```json
{
  "columns": ["id", "tick", "attacker_id", "victim_id", "actual_damage"],
  "rows": [
    ["d00001", 1234, "p01", "p02", 35],
    ["d00002", 1240, "p02", "p01", 20]
  ]
}
```

Przykład jest ilustracyjny. Wiersz ma dokładnie tyle wartości, ile nagłówków;
brak wartości jest null. Pusta kolekcja to `[]`. Sekcje meczu, gracze i rundy
pozostają nazwanymi obiektami. Zagnieżdżone tabele również mają własne columns.
Pomocnik `table_records()` dekoduje tabelę do listy słowników.

ID graczy: `p01`; zdarzeń źródłowych: `e00001`; obiektów analitycznych:
`d00001`. Nicki mogą się powtarzać; lokalne ID zachowują ich odrębność.
SteamID nie jest eksportowane w kluczach, wartościach ani odwołaniach.
Nazwy regionów rozwiązuje słownik header.map_profile.regions.

## Rundy i odwołania

- `resources.equipment_records` przechowuje definicje inwentarzy raz.
  `equipment_start` i `equipment_changes` wskazują gracza, tick i equipment_id.
  Same przełączenia aktywnej broni nie tworzą zmiany inwentarza.
- before/after w walkach zachowuje lokalnych uczestników, HP, życie, jakość
  próbki, referencję sprzętu i czas jego obserwacji; global_alive obejmuje obie strony.
- `combat` zawiera kontakty, opening, refragi, lokalne starcia, liczebność
  i momenty chronologii. `attacks` zawiera kolejne próby, także bez wejścia.
- `defense` zawiera aktywność CT, okazje do reakcji i rotacje. Wynik rundy,
  plant i retake są osobne. `utility.contexts` ma autorów, miejsca rzutu i efektu,
  czasy, powiązania i jakość dopasowania.
- Zawodnik w rundzie ma statystyki, pozycję startową, pierwsze kontakty,
  referencje do utility/ataków/rotacji i znany stan końcowy. Nieznane uczestnictwo
  lub strona pozostają oznaczone zamiast zgadywania.
- `evidence_ids` wskazuje source_events. Pozycje nie wymagają eksportowania
  całej trajektorii: zachowane są obszar, tick próbki i jej status.
- Agregaty wskazują rundy i obiekty. Szczegóły działań oraz kontekst drużyny
  nie są kopiowane dla każdego zawodnika. Snapshot agregatów wynosi 10 s;
  rundy zachowują również snapshoty 0/5/15 s i ustawienie przed kontaktem.

Nie eksportujemy pełnych trajektorii, każdego strzału, czatu, convars ani
surowych powielonych rekordów equipment/economy. Zasoby i zmiany istotne dla
analizy pozostają w rundach. Pełny mecz nadal może mieć kilka MB; UI podaje
rzeczywisty rozmiar przed pobraniem. Nie przycinamy po cichu rund ani danych.

## Interpretacja i weryfikacja

Statusy: observed / absent / partial / unknown / not_applicable / not_evaluated.
null nie oznacza zera. Atak i opis regułowy to interpretacje; surowe zdarzenia
są obserwacjami. Tempo nie jest automatycznie rush/execute; odłączenie od grupy
nie dowodzi lurka, a reakcja względem kontaktu nie jest momentem zauważenia.

Przed pobraniem walidowane są liczniki, tabele, referencje dowodów i sprzętu,
prywatne ID oraz poprawność JSON. Testy sprawdzają zgodność statystyk z rundami,
zmiany stron i nieciągłą numerację, nieznane źródła, powtarzające się nicki,
odrzucanie błędnych referencji i cache UI. `jsonschema` jest zależnością dev.

`scripts/verify_match_report.py` sprawdza cztery zapisane mapy bez parsera,
porównuje fragi z surowymi zdarzeniami przeciwników i ADR z danymi rund,
waliduje schemat oraz zapisuje pliki w ignorowanym katalogu `exports/`.
Jakość interpretacji taktycznej pozostaje przedmiotem ręcznej oceny na przykładach.

## Poprawka starszych statystyk — M5.EX.R1

Walidacja rzeczywistych danych wykazała istniejący problem kalkulatora:
Inferno R12 (zgon od świata 78883, freeze 80472, późniejszy frag 82262)
i Anubis R3 (zgon 12899, freeze 16592, późniejszy frag 20814).
Starszy kalkulator dopuszczał jeden zgon gracza w całym oknie rundy, więc
wcześniejszy reset powodował pominięcie późniejszego prawidłowego fraga.
Poprawiono wspólny kalkulator: **metryki v4** liczą zdarzenia od końca freeze
do końca rundy włącznie. Filtrowanie następuje przed odbudowaniem HP, więc
obrażenia sprzed freeze nie zmniejszają dostępnego HP aktywnego życia.

Eksport, ekran i historia korzystają ze wspólnego kalkulatora.
`limitations.statistics_reconciliation` podaje fragi źródłowe, fragi w aktywnym
oknie, wykluczone fragi sprzed freeze, liczbę raportowaną oraz różnicę względem
aktywnego okna. Powtórne zgony nadal mają referencje źródeł, także gdy są
prawidłowo rozdzielone przez freeze. Brak zegara jest jawny w
`unknown_clock_rounds`: zachowujemy wtedy całe okno i nie zgadujemy resetu.
Zdarzenia sprzed freeze pozostają dostępne w źródłach. Zapis nowych obserwacji
unieważnia stare metryki; wczytanie zegara nie dekoduje trajektorii.

## Wynik odbioru technicznego — 2026-10-14

Pełna regresja: **292 testy zaliczone, 2 opcjonalne pominięte**.
Ruff nowych modułów, testów i skryptu przechodzi. Cztery raporty przeszły
JSON Schema, spójność liczników/rund/ADR, odwołania, ochronę ID i odczyt
bez parsera. Wyniki lokalnego przebiegu:

| Mapa | Rundy / gracze | Rozmiar | Przygotowanie i walidacja | Fragi kalkulator / źródła |
| --- | --- | --- | --- | --- |
| Dust2 | 28 / 10 | 3879 KiB | 26,34 s | 205 / 205 |
| Inferno | 20 / 10 | 2809 KiB | 18,01 s | 136 / 136 |
| Anubis | 24 / 10 | 2754 KiB | 19,78 s | 164 / 164 |
| Mirage | 21 / 10 | 2607 KiB | 16,58 s | 153 / 153 |

To pomiary przygotowania z zapisanych źródeł wraz z walidacją, nie czasu
ponownego pobierania gotowych bajtów w sesji. Przykładowe pliki są w lokalnym
`exports/`; katalog nie trafia do repozytorium.
