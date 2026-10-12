# M1 — implementacja i odbiór

Data: 2026-10-12. Status: **A1–A8 ukończone technicznie i wdrożone lokalnie**.
Niezależna ocena taktyczna replayu i wizualny odbiór w przeglądarce pozostają otwarte.

## Zakres

| Zadanie | Implementacja |
| --- | --- |
| A1 | `MatchObservations`, `RoundClock`, `DetectorConfig`, `MapProfile`, `LocationAssignment`, `SpatialRelations`; jawne wersje i fingerprinty. |
| A2 | Ekstrakcja pozycji, utility, wyposażenia, ekonomii, bomby i strzałów bez interpretacji mapy. ID stemplowane przed podziałem na rundy. |
| A3 | Deklaratywny profil Mirage: regiony, granice XYZ, podejścia, kierunki, wsparcie, ograniczony graf przejść i radar. |
| A4 | Wspólny resolver, rozróżnienie lokalizacji znanej/wieloznacznej/nieznanej oraz indeksy czasu i gracza bez pobierania przyszłych próbek. |
| A5 | Przygotowanie T/CT, wejścia na site i ustawienia przed kontaktem korzystają z nowych modeli. Fundamenty źródłowe nie zawierają interpretacji regionów. |
| A6 | SQLite 8, atomowy zapis generacji etapów, odczyt pojedynczej rundy i selektywna invalidacja. Reset dawnych wyników bez migracji. |
| A7 | Widok rundy i radar sterowane profilem, nazwy oddzielone od ID. Wybór poziomu obejmuje pozycje, utility, smoke i strzały. |
| A8 | Testy kontraktów, integracji, prawdziwego dema, runtime JS, pomiary, reset głównej bazy i ponowny import. |

## Przepływ danych

1. `DemoAnalyzer` przygotowuje analizę bazową, identyfikowaną SHA-256 dema.
2. `observations.py` wydobywa źródła bez pochodnych nazw i regionów.
3. Rejestr wybiera profil mapy; resolver tworzy lokalizacje z jakością przypisania.
4. Wspólne detektory przygotowują kontekst wejść i interpretację przygotowania.
5. `spatial_service.py` publikuje kompletne etapy w jednej transakcji.
6. UI odczytuje wybraną rundę; kolejne wybory zawodnika używają tego samego kontekstu.

Stare moduły `mirage_context.py`, `mirage_entries.py` i `mirage_view.py` zastępują
`observations.py`, `context_summary.py`, `site_entries.py` i `round_context_view.py`.
Testowe adaptery historycznych fixture nie stanowią kompatybilności aplikacji.

## Zapis i cache

`coach_stage_manifests` zapisuje aktualną generację etapu, a `coach_stage_rounds`
jej payloady z kluczem `(demo_id, stage, round_number)`. Odczyt rundy filtruje SQL
przed dekodowaniem JSON. Etapy: `observations`, `spatial`, `entries`, `foundations`.

| Zmiana | Przeliczanie |
| --- | --- |
| Ekstrakcja / źródła | Obserwacje i etapy zależne. |
| Geometria / semantyka profilu | Lokalizacje i wejścia; źródła i fundamenty pozostają. |
| Progi detektora wejść | Wejścia, bez resolvera i parsera. |
| Nazwy / radar / prezentacja | Widok, bez resolvera i detektorów. |
| Gracz / runda przy kompletnym cache | Odczyt i prezentacja, bez parsera. |

Lokalizacje są zapisane kolumnowo w kolejności źródłowych obserwacji.
Fingerprint uporządkowanej listy ID oraz kontrola długości kolumn zabezpieczają
powiązanie. Uszkodzona lokalizacja lub brak fundamentów rundy powoduje odbudowę
ze źródeł. Nie trzeba ponownie otwierać dema. Źródłowe identyfikatory pozostają
niezmienne przy zmianie profilu. Wynik taktyczny R2 jest składany z etapów i
buforowany w sesji per runda; nie ma dodatkowej trwałej tabeli raportów R2.

Wersje: SQLite **8**, obserwacje **1**, zapis lokalizacji **2**, fundamenty **2**,
wejścia **3**, schemat taktyczny **3**.

## Odbiór i pomiary

Demo: `1-2826a5a8-a40f-4b7f-8654-daf5abb2289b-1-1.dem`, Mirage, 21 rund.
127 630 próbek stanów, 267 obserwacji utility, 2 653 wyposażenia, 210 ekonomii,
111 bomby, 2 236 strzałów, 275 rzutów i 74 smoke'y.
Wszystkie **25 wejść** mają identyczne `(runda, site, tick)` jak zapis przed M1.

| Pomiar | Wynik |
| --- | --- |
| Przygotowanie kontekstu wszystkich rund + odczyt rundy 1 | 19,19 s |
| Odczyt zapisanego kontekstu rundy 1 | 0,187 s |
| Odczyt i złożenie raportu taktycznego rundy 1 | 0,484 s |
| Przeliczenie semantyki profilu dla całego meczu | 4,25 s |
| Zmienione nazwy profilu — odczyt rundy | 0,182 s |
| Szczyt pamięci procesu obejmującego parser i całą weryfikację | 801,61 MiB |

To jeden przebieg lokalny, bez gwarancji czasu. Pierwszy pomiar zaczyna się od
istniejącej analizy bazowej, obejmuje ekstrakcję coacha i zapis do pustej bazy;
nie obejmuje pierwotnego parsowania statystyk bazowych. Historyczne pomiary E1
(16,93 s przygotowania, 0,71 s całego kontekstu, 65 ms fundamentów jednej rundy)
dotyczą różnych zakresów; nie są bezpośrednim benchmarkiem tych samych operacji.

Payload lokalizacji zmniejszono z **38 553 050 do 7 143 540 bajtów — o 81,5%**.
Obserwacje zajmują 66 923 015 B, fundamenty 7 261 630 B, wejścia 64 820 B.
Nie jest to rozmiar całego pliku SQLite. Źródła pozostają największą częścią cache.

Pełny przebieg z `PEEK_MIRAGE_DEMO` i `PEEK_E2E_DEMO`: **163 passed**, bez pominięć.
Końcowy szybki zestaw po poprawkach odbiorowych: **161 passed, 2 skipped**
(dwa testy wymagające jawnej ścieżki dema). Ruff E/F/I dla modułów M1 bez uwag.
Testy obejmują brak ponownego parsera, zmianę profilu/prezentacji/progów,
atomowy rollback, uszkodzone powiązania, brakującą rundę, mapę bez profilu,
syntetyczną mapę bez mida, poziomy wysokości i działanie kontrolek JS.

Artefakty: [pomiary](reference/mirage_map_pipeline_verification.json),
[wdrożenie](reference/m1_deployment.json), [UI](reference/m1_ui_verification.json).

## Wdrożenie lokalne

Po testach wykonano `scripts/deploy_map_pipeline.py --apply` dla Mirage.
Analiza bazowa została sparsowana przed otwarciem bazy wymagającej resetu.
Schemat **7 → 8**, bez konwersji historycznych analiz. Zachowano 3 śledzonych
graczy wraz z datami dodania, 3 dema oraz niezmienioną konfigurację.
Ponowny import zapisał jeden mecz, 21 rund każdego etapu i ratingi 10 graczy.
SQLite integrity check i foreign key check poprawne.

Aplikacja: `http://127.0.0.1:8501`, health `ok`.
AppTest na głównej bazie sprawdził rundy 1/2, jeden radar w rundzie, zmianę
gracza bez nowych kontekstów, brak widocznych kolumn SteamID i brak wyjątków.
Parser był zablokowany podczas tego testu. Przeglądarka nie była dostępna
w środowisku odbioru; nie deklarujemy wizualnego sprawdzenia animacji.

## Ograniczenia i następny etap

- Jedyny rzeczywisty profil to Mirage. Nowa mapa wymaga profilu, aktywów i referencji.
- Graf przejść Mirage jest częściowy; nie opisuje widoczności ani kontroli mapy.
- Niepełne źródła, niejednoznaczne regiony i brak zgodności patcha są jawne.
  Czas może korzystać z oznaczonego założenia 64 Hz, gdy brak wiarygodnego nagłówka.
- Wejście wymaga potwierdzonej obecności; krótki wypad zakończony śmiercią może wypaść.
  4+1 nie potwierdza lurka, a defuse nie potwierdza zidentyfikowanej próby retake.
- Obrys smoke jest orientacyjny; brak eventu końca daje oznaczony szacunek czasu.
- Niezależny przegląd taktyczny w grze pozostaje otwarty. M1 nie wdraża nowych
  detektorów lokalnych walk, rush/execute, rotacji ani retake i nie generuje raportu LLM.

Aktualna kolejność po przeglądzie roadmapy: **M2 — druga mapa → M3 — czytelna
runda → M4 — starcia i atak**, z podstawowymi porównaniami M5 rozpoczynanymi
po M3. Dalej M6 — pełny raport coacha. Zakres: [roadmapa](../ROADMAP.md),
reguły kontaktów i starć: [M3–M4](round_fights_plan.md).
