# M5.1–2 — porównywalne rundy i pierwsze zestawienia mapy

Wdrożone 2026-10-14 po akceptacji obecnej wersji M4 przez użytkownika.
UI: **Tendencje mapy → Przygotuj zestawienia mapy**. Obliczenia są lokalne.

## Zakres

- Stała tożsamość drużyny, rozdział T/CT, wybór gracza i podzbioru rund.
- Opcjonalny filtr początkowego stanu 5 na 5: obie liczebności muszą być znane.
- Wartość sprzętu drużyny/rywala na końcu freeze time; pełna suma wyłącznie
  przy odczycie wszystkich pięciu zawodników. Filtry wartości pomijają nieznane
  wyceny. Pusta wycena nie jest eco, a prawdziwa wartość 0 pozostaje zerem.
- Wynik poprzedniej rundy i znani ocaleńcy w obrębie ciągłego segmentu tej samej
  strony i składu. Zmiana stron/składu, luka, cofnięcie licznika, warmup,
  rozpoznana zmiana fazy lub reset przerywają porównanie. Nie zakładamy MR12
  ani nie wnioskujemy o zachowaniu broni z identycznego wyposażenia.
- Kierunki T i pozycje graczy w stałym czasie 10/15 s, sektory CT przed
  kontaktem z osobnym czasem pomiaru, miejsca/czasy pierwszych kontaktów ogniowych
  i openingów, early utility, potwierdzone wejścia, refragi i rundy z przewagą.
- Rozdzielone miejsce rzutu i efektu, informacja o rzucie ze spawnu,
  jawne nieustalone lokalizacje. Sektor CT i kierunek T są kontekstem drużyny
  również przy filtrowaniu obserwacji konkretnego zawodnika.
- Każde zestawienie prowadzi do przykładowej rundy i czasu na radarze;
  brak technicznych identyfikatorów graczy w tabelach.

## Jednostki i mianowniki

| Miara | Jednostka / mianownik |
| --- | --- |
| Dominujący kierunek T | Runda z kompletnym snapshotem żywych graczy i rozstrzygniętym kierunkiem. Niepełne rundy osobno; remis kierunków ma własną kategorię. |
| Pozycje | Gracz w rundzie, w wybranym stałym czasie. Nieżyjący i nieustalone pozycje pozostają kategoriami w mianowniku. |
| Sektory CT | Runda z rozstrzygniętym snapshotem przed kontaktem. Czas jest zmienny; nie mieszamy go ze stałym pomiarem 10/15 s. |
| Kontakt | Zarejestrowane pierwsze kontakty, z zachowaniem remisów ticków; w perspektywie gracza jego własny pierwszy kontakt. |
| Opening | Zdarzenie, nie zawsze jedna sztuka na rundę: jednoczesne pierwsze fragi są równorzędne. Tylko rozstrzygnięte źródło zabójstw. |
| Early utility | Zarejestrowany rzut 0–15 s; procent dotyczy rzutów, nie wszystkich rund. Nieustalone pochodzenie/efekt pozostają w mianowniku. Pokrycie źródła rzutów osobno. |
| Wejścia | Pierwsze potwierdzone przekroczenia z istniejącego detektora. To nie wszystkie próby ataku ani ich skuteczność. |
| Refragi | Osobno unikalne fragi wymieniające, wymienione zgony i rundy z wymianą / rundy ze znanym pokryciem. Filtr gracza wskazuje autora odpowiedzi. Jeden frag może wymienić kilku kolegów. |
| Wykorzystanie przewagi | Wygrane / rundy z zaobserwowaną przewagą liczebną i znanym wynikiem. Bez przypisywania wpływu zawodnikowi i bez oceny decyzji. |

## Implementacja i wydajność

`map_round_facts.py` tworzy wersjonowany, strukturalny wynik rundy ze wspólnej
analizy M3/M4. `map_tendencies_service.py` zapisuje go w etapie SQLite
`map_round_facts`. Klucz obejmuje źródła, fundamenty, semantykę profilu,
parametry/schemat i wersje detektorów. Nazwy do prezentacji są rozwiązywane w UI.

Pierwsze przygotowanie używa zapisanych źródeł i cache M4. Kolejne odczyty nie
wywołują `get_spatial_context`, parsera ani detektorów. `map_tendencies.py`
agreguje wyłącznie kompaktowe fakty; filtry w sesji nie czytają ponownie pozycji.
UI i nawigacja: `map_tendencies_view.py`, istniejący dashboard i radar rundy.

Weryfikacja obu rzeczywistych meczów: `scripts/verify_m5_baseline.py`.
Historyczne pomiary M5.1–2: odczyt około **45–48 ms**, cztery agregacje drużyna/strona
około **2–3 ms**; wyniki całej mapy **715–747 KiB**. Pierwsze przygotowanie
około **8–10 s**, ze źródeł i cache M4, bez parsera. To pomiary lokalne,
nie gwarancja czasu całego UI ani dowolnego dema.

Testy obejmują jednostki/mianowniki, missing vs zero, zmianę stron/składu,
luki/reset, wycenę częściową, remisy openingów, czasy snapshotów, osobisty kontakt,
cache SQLite bez detektorów oraz przejście z zestawienia do radaru.

Weryfikacja: pełny przebieg **234 testy zaliczone, 2 opcjonalne pominięte**.
Po dodaniu filtra 5 na 5: końcowe **21 testów agregacji, UI i regresji rund**
zaliczonych, w tym 14 testów M5. Wszystkie 41 rund obu dem zapisane/odczytane
bez parsera i bez detektorów podczas odczytu cache; Ruff nowych modułów przechodzi.

## Ograniczenia i następny krok

Źródła obecnych dem nie opisują wszystkich resetów ekonomii/dogrywek; zakres
porównywalności jest jawnie ograniczony. Mirage ma częściowo nieustalone regiony
w snapshotach T po 10 s (6/12 i 5/9 pełnych snapshotów dla drużyn); takie rundy
nie zasilają rozkładu kierunków. Miejsca efektu utility na Inferno bywają nieznane.

**Review 2026-10-14 — poprawki wykonane:** kontakty uwzględniają znane puste
źródła, refragi mają rozdzielone jednostki, snapshot po końcu rundy oznacza
„nie dotyczy”, a nie brak pozycji. Brak zegara pozostaje nieustalony.
[Uzasadnienie review](m5_review.md).

**M5.3–6 wdrożone:** rzeczywiste próby T, działania/rotacje/retake CT, porównania
rund i obserwacje z danych. [Aktualny zakres i pomiary](m5_tactical_summary.md).
Odbiór prezentacji pozostaje otwarty. Integracja i próbne raporty LLM są w M6.
