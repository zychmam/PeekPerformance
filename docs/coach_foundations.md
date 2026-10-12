# E1 — dane wejściowe coacha

Wdrożenie i odbiór techniczny: 2026-10-12. Mirage jest pierwszą obsługiwaną
mapą. Plan wykonawczy: [E1-01–E1-08](coach_foundations_plan.md).

## Wynik

Każda runda ma `RoundFoundation`: zegar, wyposażenie na freeze-end,
zaobserwowane zmiany wyposażenia, referencje do zdarzeń bomby, strzałów,
rzutów i działania utility oraz ustawienie przed pierwszym zaobserwowanym
kontaktem. Raporty zawodników korzystają z tych samych danych drużynowych.

Wersje: schemat SQLite **7**, kontekst Mirage **6**, fundamenty **1**,
schemat taktyczny **2**. Odczyt modelu taktycznego akceptuje również schemat
1 i uzupełnia nowe opcjonalne pola. Klucz kontekstu uwzględnia wersję parsera
oraz podstawowe źródła, w tym roster, bombę i oślepienia.

## Pozyskiwanie i pochodzenie

- Pozycje: co 6 ticków oraz w tickach obrażeń/zabójstw i bezpośrednio przed
  nimi. Czas nadal jawnie zakłada 64 ticki/s; nagłówek dema nie potwierdza
  innego przelicznika. Freeze-end pochodzi z eventu.
- Wyposażenie: inventory z liczbą sztuk, broń aktywna, pancerz, hełm i kit.
  Ekonomia korzysta z `DemoAnalyzer.get_economy()` na freeze-end. Zmiany
  inventory są zmianami zaobserwowanych próbek; dokładny tick zmiany między
  próbkami pozostaje nieznany. Ekonomii nie przenosimy jako aktualnego salda
  na późniejszy moment rundy.
- Inventory i pozostałe pola mają wspólny szybki odczyt. Błąd opcjonalnej
  grupy uruchamia niezależne odczyty; błąd pojedynczego pola zachowuje
  dostępne pozostałe wartości. Stany wyposażenia kompresujemy do zmian,
  zachowując zakres i luki pokrycia.
- Bomba: pickup, drop, beginplant, plant, begindefuse, defuse i explosion
  są obecne w dostarczonym Mirage. Zdarzenia pobieramy jednym odczytem
  grupowym z awaryjnym odczytem osobnych źródeł. Plant i defuse z bazowej
  analizy nie są powielane w chronologii. Nieobecne aborty pozostają nieznane.
- Strzały i rzuty: jedno źródło `weapon_fire`. Broń palna jest oddzielona
  od granatów, noży i C4. Rzuty obejmują również decoy.
- Utility: osobno rzut, zadziałanie i dostępne wygaśnięcie. Łączenie rzutu
  z efektem wymaga zgodnego autora, typu i rundy, maksymalnie 20 s odstępu
  oraz jednoznaczności w obie strony. Jest to ograniczona interpretacja
  czasowa. Nie wymuszamy przypisania kolejnych flashów tego samego gracza.
  Pełne trajektorie pozostają dostępne do dalszego uściślania takich par.
- Smoke: rzeczywiste wygaśnięcie jest odróżnione od końca wyświetlania
  w rundzie i szacunku 22 s. Szacunek służy radarowi; analityczny `end_tick`
  pozostaje nieznany bez eventu. Promień na radarze jest orientacyjny.
- Powiązania utility prowadzą do źródłowych dowodów efektu oraz dostępnego
  rzutu. Wygaśnięcie po końcu rundy zachowuje surową obserwację i jej ID;
  nie jest umieszczane jako zdarzenie wewnątrz zakończonej rundy.

`SourceQuality` oddziela wynik odczytu od kompletności. `not_listed` oznacza
brak nazwy w obserwowanej liście eventów; nie rozstrzyga obsługi parsera ani
rzeczywistego braku zdarzeń. Błąd i starszy pusty strumień nie dają zera.

## Kontakt i ustawienie

Zapisujemy pierwsze dodatnie obrażenia przeciwnika, pierwsze obrażenia od
broni palnej, pierwszy frag przeciwnika oraz najwcześniejsze obserwowane
odniesienie dla przygotowania. Friendly fire, self i world go nie inicjują.
Zdarzenia w tym samym ticku zachowują wspólny czas i osobne ID.

Ustawienie ma docelowy tick `kontakt - 1`; próbki muszą pochodzić sprzed
kontaktu i mieć maksymalnie 1 s wieku. Braki graczy oraz stref pozostają
jawne. Brak kontaktu nie tworzy sztucznego snapshotu. Pozycje CT na site,
midzie i w łącznikach są rozdzielone. Snapshoty 0/5/10/15 s pozostają dostępne.

W UI domyślny moment to ustawienie przed kontaktem, jeżeli dostępne. Osobne
liczniki pokazują rzuty i zadziałania do 10/15 s. Wyposażenie oraz chronologia
bomby są pod rozwinięciem „Dane rundy dla coacha”. Tabele prezentują nicki.

## Zapis i odczyt

`get_mirage_context()` przygotowuje dane wspólnie dla meczu, publikuje cache
przestrzenny i fundamenty atomowo. Blokada per baza/demo zapobiega ponownej
ekstrakcji przy równoczesnych żądaniach w procesie aplikacji.

- `demo_coach_enrichment`: manifest, wersja, fingerprint i lista rund.
- `demo_coach_round_inputs`: klucz `(demo_id, round_number)`, fingerprint,
  kompaktowy model rundy i potrzebny podzbiór dowodów.

Odczyt jednej rundy filtruje ją w SQL, nie wczytuje wszystkich payloadów.
Ciężkie pozycje pozostają w istniejącym cache przestrzennym. Zastąpienie
analizy i usunięcie dema unieważnia również fundamenty. Błąd zapisu zachowuje
poprzedni zestaw. Migracja 6→7 zachowuje mecze oraz śledzonych graczy.

```python
from src.demos.coach_foundations import decode_foundation, foundation_key

saved = db.get_coach_round_inputs(analysis.content_hash, foundation_key(analysis), 1)
foundation, evidence = decode_foundation(saved[1])
```

`load_tactical_match()` odczytuje zapis bez parsera/API i dołącza fundamenty
do istniejącego modelu. Stary kontekst bez oryginalnego pliku pozostaje
czytelny z informacją o konieczności uzupełnienia. Detektory starć, ataków,
rotacji i retake’u zachowują status `not_evaluated` do realizacji R3/R4.

## Odbiór i pomiary

Źródła zweryfikowane na demoparser2 **0.42.0**:
[audyt](reference/mirage_sources_audit.json).
Dokładne pomiary: [protokół](reference/mirage_foundations_verification.json).
Ręcznie sprawdzone rekordy parsera:
[oczekiwania referencyjne](../tests/reference/mirage_foundation_expectations.json).

Realne Mirage: **21 rund**, **127 630 próbek pozycji**, **2653 obserwacje
wyposażenia po kompresji**, **210 stanów ekonomii**, **2236 strzałów**,
**275 rzutów** i **267 efektów utility**. 216 efektów ma ograniczone
dopasowanie czasowe do rzutu, 51 pozostaje nieprzypisanych. Z 74 smoke’ów
63 mają event wygaśnięcia, 11 korzysta z oszacowania wyłącznie na radarze.

Jeden lokalny przebieg: przygotowanie/ekstrakcja/zapis **16,93 s**, ciepły
odczyt kontekstu **0,71 s**, odczyt i dekodowanie jednej rundy **65 ms**.
Ciepły odczyt wykonał **0 wywołań parsera**. Fundamenty wszystkich rund
zajmują około **6,28 MB** JSON. Szczyt working set procesu pomiarowego wyniósł
**702 MiB**, obejmując również natywny parser i wcześniejszy pomiar bazowy.
To pojedyncze pomiary, nie budżety wydajności ani przyrost pamięci aplikacji.

Pełny zestaw: **127 testów zaliczonych, 1 opcjonalny pominięty**, w tym
aktywny test prawdziwego Mirage, zapis/odczyt wszystkich referencji,
niezależne oczekiwania ticków i wyposażenia, migracja, rollback, żądania
równoczesne oraz widok Streamlit/radar. Ruff dla nowych modułów przechodzi.

Odbiór techniczny E1 zakończony. Niezależny przegląd tych momentów w grze
pozostaje otwarty; nie deklarujemy walidacji zamiarów ani oceny taktyki.
