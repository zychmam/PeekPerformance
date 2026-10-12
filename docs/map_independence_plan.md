# M1 — wspólny model coacha i profile map

Status: **A1–A8 zaimplementowane, odebrane technicznie i wdrożone**.
Wyniki, pomiary i ograniczenia: [raport M1](map_independence_implementation.md).
Data: 2026-10-12. Ukończony etap przed dalszą analizą rund.
Historyczne odwołania do R3 poniżej oznaczają obecny zakres M3–M4;
aktualna kolejność zaczyna się od M2: [roadmapa](../ROADMAP.md).

## Cel i decyzje obowiązujące wszystkie zadania

Oddzielić obserwacje z dema, interpretację przestrzeni i detektory. Kolejna mapa
ma wymagać przede wszystkim profilu oraz referencji, bez kopiowania silnika coacha.
Pierwszym profilem produkcyjnym pozostaje Mirage. Profil syntetyczny służy wyłącznie
sprawdzeniu architektury; nie stanowi deklaracji obsługi kolejnej prawdziwej mapy.

- **Bez migracji historycznych analiz i bez kompatybilności ich formatów.** Można
  usunąć analizy, ratingi, katalog wyników i cache, a demo zaimportować ponownie.
- Zachować źródłowe `.dem` / `.dem.zst`, konfigurację i `tracked_players`.
  Brak meczów po resecie nie może usuwać śledzonego gracza. Nick może być nieznany
  do kolejnego importu; w UI nadal nie wyświetlać SteamID.
- Reset wykonano przy wdrożeniu M1 po testach na tymczasowej bazie.
  Zachowano plik bazy i śledzonych graczy; nie konwertowano dawnych analiz.
- Nowe dane i cache pozostają wersjonowane. Zmiana semantyki mapy ma unieważniać
  tylko odpowiednie wyniki, bez ponownej ekstrakcji dostępnych obserwacji.
- Zachować rozróżnienie: obserwacja, interpretacja, nieznane, potwierdzony brak,
  niewykonana analiza. Brak profilu nie oznacza braku wydarzeń.
- Zachować źródłowe ticki, XYZ, etykiety parsera i dowody. Napisy w UI nie są ID.
- Ustawienie 4+1 nie dowodzi lurka; przejście nie dowodzi kontroli przestrzeni;
  strefa wsparcia nie dowodzi możliwości strzału; graf przejść nie opisuje LOS.
- M1 zachowuje dotychczasowe znaczenie pomiarów. Nowe wykrywanie starć, ataków,
  rotacji, retake oraz ocen decyzji należy do R3/R4 i kolejnych etapów.
- Nie budować systemu pluginów, dowolnych skryptów map ani silnika widoczności.
  Użyć obecnego stosu Python/SQLite/pandas i niewielkich typowanych interfejsów.

## Podział odpowiedzialności i kontrakty docelowe

Nazwy poniżej są docelowymi nazwami do uzgodnienia i zamrożenia w M1.1. Późniejszy
agent nie zmienia wspólnego interfejsu jednostronnie; opisuje potrzebę integratorowi.

| Model / usługa | Zawartość i odpowiedzialność |
| --- | --- |
| `MatchObservations` | Źródłowe zdarzenia i próbki bez nazw/stref wyliczonych z profilu; manifest źródeł i pokrycia. |
| `RoundClock` | Granice rundy i freeze, źródło lub jawne założenie częstotliwości, wspólne przeliczenia czasu. |
| `MapProfile` | Tożsamość, zgodność, regiony, site'y, relacje przestrzenne, oznaczenia taktyczne i radar. |
| `LocationAssignment` | ID obserwacji, region lub kandydaci, poziom, metoda, status, wersja semantyki profilu. |
| `SpatialRelations` | Typowane relacje: możliwość przejścia, podejście, potencjalne wsparcie, kierunek; brak domyślnej widoczności. |
| `RoundIndex` | Indeksy czasu/gracza/źródła; wyszukiwanie świeżej próbki przed zdarzeniem, z zachowaniem luk. |
| `DetectorConfig` | Wspólne progi w sekundach i definicje miar; wersja niezależna od geometrii mapy. |
| Manifest etapu | Wersja schematu/algorytmu, fingerprint rzeczywistych wejść, kompletność i pochodzenie. |

Kierunek zależności: modele → ekstrakcja / profile → resolver → detektory → raport / UI.
Modele i ekstrakcja nie importują profilu Mirage ani Streamlit. UI nie klasyfikuje XYZ.
`RoundFoundation` zachowuje dane wyposażenia/zdarzeń; przestrzenna interpretacja
snapshotu przed kontaktem należy do etapu zależnego od profilu. Wybór ticka i próbek
przed kontaktem pozostaje niezależny od mapy. Fizyczny układ tych pól ustala M1.1.

Proponowany układ plików:

```text
src/models/observations.py          # obserwacje, czas, manifesty
src/models/spatial.py               # profil, lokalizacja, relacje
src/maps/registry.py                # dobór profilu i jego możliwości
src/maps/profiles/de_mirage.json     # reguły przestrzenne Mirage
src/maps/resolver.py                # wspólne dopasowanie stref
src/demos/observations.py           # ekstrakcja niezależna od mapy
src/demos/round_index.py            # wspólny indeks odczytu
src/demos/spatial_service.py        # uruchamianie etapów i cache
```

Istniejące `tactical.py`, `foundation_sources.py`, `replay_effects.py`, detektory
i radar wykorzystujemy ponownie. Nie przenosić plików wyłącznie dla estetyki.

## Kolejność agentów i własność plików

| Agent / pakiet | Zależności | Złożoność | Główny rezultat |
| --- | --- | --- | --- |
| A1 / M1.1 — kontrakty | — | 3/5 | Zamrożone interfejsy, podział pól i zależności cache |
| A2 / M1.2 — obserwacje | M1.1 | 4/5 | Ekstrakcja, zegar i źródłowe ID niezależne od mapy |
| A3 / M1.3 — profil Mirage | M1.1 | 3/5 | Profil i walidator, pełny spis przeniesionych reguł |
| A4 / M1.4 — resolver | M1.1, M1.3 | 4/5 | Lokalizacja, relacje i indeksy do wspólnych analiz |
| A5 / M1.5 — obecne detektory | M1.2, M1.4 | 4/5 | R2/E1 i wejścia korzystające ze wspólnego modelu |
| A6 / M1.6 — storage i cache | M1.1; integracja po M1.2/M1.4/M1.5 | 3/5 | Nowy zapis, selektywne przeliczanie i reset wyników |
| A7 / M1.7 — UI i radar | M1.3, M1.5, M1.6 | 3/5 | Widok dobierany przez możliwości mapy |
| A8 / M1.8 — odbiór | Referencje od M1.1; odbiór po M1.7 | 4/5 | Testy integracji, wydajność, raport i gotowość R3 |

To pakiety dla kolejnych agentów, nie polecenie uruchomienia ośmiu agentów naraz.
M1.2 i M1.3 można realizować równolegle po M1.1. M1.6 może wcześniej przygotować
storage przeciw zamrożonym kontraktom; końcowe podłączenie wykonuje po detektorach.
Referencje M1.8 można zbierać od początku. Integrator rozstrzyga zmiany kontraktów.

Właściciele wspólnych plików: A1 `src/models/*`; A2 ekstrakcja i
`tactical_evidence.py`; A5 `coach_foundations.py`, `tactical_rounds.py` i detektory;
A6 `database.py`, `spatial_service.py`; A7 `src/gui/*` i aktywa radaru.
Przekazanie własności pliku jest jawne. Nie nadpisywać pracy innego agenta.

## A1 — M1.1: kontrakty i granice odpowiedzialności

**Cel:** pozostali agenci mogą implementować niezależnie bez zgadywania pól.

1. Spisać każde użycie `ZONES`, `ROUTES`, `SUPPORT`, `CT_FORWARD_PLACES`, reguł XYZ,
   `de_mirage`, stałej 64, kluczy cache i etykiet przestrzennych w danych dowodowych.
2. Przypisać pola obecnego `MirageContext` do obserwacji, lokalizacji, wyników
   detektorów lub prezentacji. Oddzielić fakty czasu smoke od wizualnego szacunku.
3. Zdefiniować modele z tabeli kontraktów, format serializacji i walidację.
   Pojęcia site, podejście, wsparcie i kierunek mają osobne pola/relacje.
4. Ustalić identyfikację regionów, profilu, obserwacji i zdarzeń pochodnych.
   Stabilność źródłowych ID obowiązuje dla tego samego wejścia i wersji normalizacji;
   nie obiecywać identycznych ID po zmianie parsera/ekstrakcji.
5. Ustalić wymagane możliwości detektorów: np. opening wymaga killów, wejście
   wymaga granic site'u, a ocena wysunięcia wymaga oznaczeń zależnych od strony.
6. Zdefiniować fingerprinty obserwacji, semantyki mapy, detektora i prezentacji.
   Nazwy i obraz radaru nie mogą unieważniać źródeł lub wyników liczbowych.
7. Zapisać ustalenia w `docs/map_data_contract.md`; dodać małe przykłady poprawnego,
   częściowego i nieznanego dopasowania. Przekazać listę interfejsów agentom A2–A7.

**Odbiór:** modele dają się zapisać/odczytać; referencje mają określony typ i zakres;
brak wymaganego mida lub jednej wspólnej etykiety kierunku dla każdej pozycji.
Testy obejmują błędne relacje/wersje, kolizje ID i brak możliwości profilu.

## A2 — M1.2: obserwacje, czas i źródłowe dowody

**Wejście:** kontrakty A1; obecne `mirage_context.py`, `foundation_sources.py`,
`replay_effects.py`, `tactical_evidence.py`, `coach_data.py` i `demo_analyzer.py`.

1. Wydzielić `extract_observations()` i model niezależny od mapy. Sprawdzać zgodność
   mapy pliku z metadanymi importu; usunąć ograniczenie ekstrakcji do `de_mirage`.
2. Zachować źródłowe etykiety nawigacyjne i XYZ, bez dopisywania wyliczonych stref,
   nazw prezentacyjnych i wejść do źródłowego payloadu.
3. Zachować odczyt wyposażenia, ekonomii, bomby, strzałów, rzutów i lifecycle utility
   z niezależnym raportowaniem błędów pól. Zachować około 0,1 s próbkowania i dodatkowe
   próbki przy zdarzeniach; nie interpolować źródłowych pozycji.
4. Wprowadzić wspólny zegar. Wykorzystać wiarygodne metadane czasu, jeżeli dostępne;
   zachować jawne założenie 64 w pozostałych przypadkach. Nie zgadywać subticków.
   Progi wyrażać w sekundach i przeliczać przez jeden interfejs.
5. Generować ID tylko ze znormalizowanego strumienia źródłowego, z deterministycznym
   rozróżnieniem duplikatów. Nie scalać zdarzeń tylko dlatego, że mają ten sam tick.
6. Zachować powiązania utility oraz źródłowy porządek, gdy jest dostępny; brak
   rozstrzygalnej kolejności w tym samym ticku pozostaje jawny.
7. Przekazać A6 gotowy manifest obserwacji i fingerprint ekstrakcji; nie modyfikować
   jednocześnie z A6 orkiestratora zapisu.

**Odbiór:** ten sam zestaw obserwacji daje te same ID po zapisie/odczycie i zmianie
profilu; nieznana mapa nie blokuje odczytu źródeł. Realne Mirage zachowuje liczniki
E1 i referencyjne ticki. Testy: źródła częściowe, duplikaty w ticku, granice rundy,
czas, brak profilu oraz źródłowy koniec smoke odrębny od prezentacji.

## A3 — M1.3: deklaratywny profil Mirage

**Wejście:** kontrakt A1; słowniki/reguły z `mirage_context.py`, `mirage_entries.py`,
`early_round.py`, `early_interpretation.py`, `early_round_view.py` oraz aktywa mapy.

1. Przenieść istniejące strefy i ich nazwy do jednego profilu, nadać stabilne ID.
2. Przenieść rozróżnienie rampy/pałacu oparte na XYZ, z jawnymi zasadami granic
   przedziałów i priorytetami tylko tam, gdzie są uzasadnione.
3. Opisać site'y, podejścia, potencjalne wsparcie, kierunki i wysunięte obszary CT
   oddzielnie. Relacje mogą być wielowartościowe; nie wymuszać celu ataku w connectorze.
4. Dodać tylko znane połączenia istotne dla obecnych funkcji. Relacja może być
   skierowana; brak połączenia w niepełnym profilu nie dowodzi braku przejścia.
5. Dodać opis radaru, transformację i strukturę poziomów. Nie deklarować pełnej
   obsługi geometrii 3D tylko na podstawie podziału wysokości.
6. Walidować duplikaty, brakujące regiony relacji, geometrię, wysokości, transformację
   i odwołania do plików. Przechowywać źródło/weryfikację reguł oraz zgodność profilu.
7. Stworzyć rejestr profili. Nie dopasowywać profilu innej mapy ani nie zakładać
   zgodności po nieznanej zmianie mapy; rozdzielić wsparcie, zgodność i pokrycie.

**Odbiór:** wszystkie dotychczasowe reguły Mirage mają odpowiednik lub jawnie
udokumentowane odrzucenie. Same nazwy regionów nie wyzwalają zachowań detektora.
Testy walidatora, niejednoznaczności i odwołań; mapa spoza rejestru zwraca brak
profilu z zachowaniem dostępności analizy zdarzeń.

## A4 — M1.4: wspólna interpretacja przestrzeni i indeksy

**Wejście:** kontrakty A1, profil A3; przykład obserwacji od A2 lub fixture kontraktu.

1. Zbudować resolver przyjmujący surowe próbki i profil. Dopasowywać partiami:
   indeks etykiet, filtr zakresów, dokładna geometria tylko dla kandydatów.
2. Obsłużyć granice, wysokość, brakujące XYZ i konflikt etykiety z geometrią.
   Rozstrzygnięcie wynika z reguł profilu; niewyjaśniony konflikt daje niepewność.
3. Wyniki przechowywać oddzielnie z referencją do obserwacji. Rozdzielić kompletność
   próbek od kompletności ich klasyfikacji przestrzennej.
4. Udostępnić typowane zapytania o site, podejście, wsparcie i znane połączenie.
   Nie utożsamiać braku wpisu w niepełnym grafie z dowodem niedostępności.
5. Przygotować `RoundIndex`: sortowanie raz, zakresy per gracz/źródło, wyszukiwanie
   próbki o ticku <= żądany tick; jawny wiek, luki i brak dopasowania.
6. Skompilowany profil przechowywać w ograniczonym cache po fingerprintcie semantyki.
   Nie budować macierzy odległości pomiędzy wszystkimi próbkami ani pełnego pathfindingu.

**Odbiór:** rampa/pałac i syntetyczne poziomy o wspólnym XY rozdzielone, zdarzenie
nie otrzymuje przyszłej próbki. Testy granic, luk, nieznanych nazw, braków wysokości,
jednokierunkowego przejścia i odrębności relacji przejścia od widoczności.

## A5 — M1.5: podłączenie E1/R2 i wejść

**Własność:** `early_round.py`, `early_interpretation.py`, `mirage_entries.py`,
`coach_foundations.py`, `tactical_rounds.py`; wspólne modele zmieniać przez A1.

1. Zastąpić importy słowników Mirage zapytaniami do profilu/resolvera.
2. Snapshoty 0/5/10/15 s i przed kontaktem zbudować ze wspólnego zegara i indeksu.
   Wyposażenie, kontakty i bomba działają także przy braku przypisania stref.
3. Liczyć obecność na site osobno od wsparcia; zachować jawne brakujące próbki
   i nieznane lokalizacje. Nie podawać pełnej obsady przy niepełnym pokryciu.
4. Wydzielić wspólny detektor obserwowanych wejść. Granice, drogi i nazwy pochodzą
   z profilu; okno 8 s, potwierdzenie 0,5 s i dotychczasowe ograniczenia z configu.
5. Kierunki, formacje i wysuniętą obecność opierać na jawnych relacjach. Dla obszaru
   wieloznacznego nie przydzielać arbitralnie A/B ani nie tworzyć fałszywego 4+1.
6. W `TacticalMatch` zapisać wersje i dostępność wymaganych możliwości. Samo istnienie
   profilu nie oznacza kompletności danych, wykonania ani walidacji detektora.
7. Zastąpić dotychczasowe etykiety w wynikach ID regionów + referencjami; teksty
   użytkowe formatować z nazw profilu. Przygotować opis wejść dla przyszłego R3.

**Odbiór:** zachowanie obecnych wyników Mirage na referencjach; zmiany wynikające
z ujawnionej niejednoznaczności opisane i oparte na dowodach. Testy aktualnych
snapshotów, wejść, utility, braków oraz profilu bez mida. Detektory nie zawierają
nazw map, regionów Mirage ani granic XYZ.

## A6 — M1.6: zapis, cache i jednorazowy reset analiz

**Własność:** `database.py`, `spatial_service.py`; kontrakty od A1, adaptery A2/A5.

1. Zaprojektować prosty zapis etapów: manifest meczu/etapu oraz payloady rund,
   klucze po demo/etap/runda, indeksowane odczyty jednej rundy. Wspólne obserwacje
   nie są kopiowane osobno dla każdego gracza i detektora.
2. Wdrożyć fingerprinty zależności: źródła → lokalizacje → zależne detektory.
   Analizy niespatialne nie zależą od profilu. Nazwy i radar nie zmieniają liczb.
3. Zachować atomowe publikowanie manifestu z rundami oraz koordynację żądań dla
   tego samego demo. Nie udostępniać mieszaniny nowych i starych etapów jako aktualnej.
4. Ciepły odczyt nie otwiera dema. Poprawka profilu przelicza zapisane obserwacje;
   brak źródła na dysku nie blokuje tego, gdy potrzebne obserwacje są kompletne.
5. Przygotować jednorazowy, transakcyjny reset tabel wynikowych podczas wdrożenia
   nowego schematu. Jawna lista tabel; nie usuwać pliku bazy, `tracked_players`,
   konfiguracji ani plików dem. Reset nie powtarza się przy każdym uruchomieniu.
6. Usunąć konwersje i fallbacki historycznych analiz/cache zastąpione resetem.
   Nową bazę tworzyć od razu w docelowym schemacie. Nie wspierać otwierania bazy
   o nowszym, nierozpoznanym schemacie przez automatyczne kasowanie danych.
7. Udostępnić A7 API odczytu pojedynczej rundy i manifestu dostępnych analiz.
   Zapewnić unieważnienie sesji/cache UI po resecie i ponownym imporcie.

**Odbiór:** testy na tymczasowej bazie: reset zachowuje śledzonych graczy i pliki,
nowy import działa, ponowny start nie usuwa nowych wyników, rollback zachowuje spójność,
równoczesne żądania w procesie nie dublują ekstrakcji. Zmiana profilu wykonuje zero
wywołań parsera i nie zmienia źródłowych ID; zmiana gracza nie uruchamia analizy.

## A7 — M1.7: UI i radar sterowane profilem

**Własność:** `mirage_view.py`, `early_round_view.py`, `foundation_view.py`,
`radar_player.py`, integracja `app.py` i aktywa radaru.

1. Widok rundy otrzymuje dane oraz możliwości profilu. Usunąć warunki `de_mirage`
   i mapowanie nazw rampy/pałacu z UI; dobierać etykiety z profilu.
2. Radar pobiera obraz i transformację z profilu. Zachować mapę na górze, smoke'y,
   strzały, wybór czasu, lokalne odtwarzanie i nicki.
3. Payload wybranego meczu/rundy zawiera tylko potrzebne próbki i zdarzenia.
   Zmiana zawodnika zmienia wyróżnienie/perspektywę, bez przeliczenia analizy meczu.
4. Uwzględnić poziomy radaru w kontrakcie. Na fixture pokazać wybór poziomu lub
   czytelne odróżnienie graczy; samo wspólne XY nie może udawać tej samej kondygnacji.
5. Brak profilu/radaru ogranicza odpowiedni fragment widoku. Zachować chronologię,
   wyposażenie, wyniki i dostępne kontakty, z krótką informacją o brakach.
6. Czytać świeży stan po resecie/ponownym imporcie; śledzony gracz bez meczu ma
   poprawny pusty panel. Nie wyświetlać surowych SteamID jako zastępczych nicków.

**Odbiór:** testy Streamlit i istniejącego runtime JS: przejście do ticka, zmiana
gracza/rundy, nieznana mapa, brak grafiki, transformacja i syntetyczne poziomy.
Odtwarzanie nie generuje rerunów Streamlit; szczegóły techniczne nie dominują UI.

## A8 — M1.8: referencje, integracja i pomiary

1. Przed resetem zebrać obecne liczniki i przypadki Mirage: rampa/pałac, wejście
   apps/short, brak pozycji, granica strefy, precontact, plant, smoke i strzały.
   Wykorzystać istniejące oczekiwania; nie generować wszystkich oczekiwań z detektora.
2. Przygotować niewielki profil syntetyczny: brak mida, dwa nakładające się poziomy,
   wieloznaczny kierunek, jednostronne przejście i niepełny graf. Zmiana nazw regionów
   nie zmienia wyniku liczbowego wspólnego detektora.
3. Złożyć E2E: import → obserwacje → profil → lokalizacje → E1/R2 → zapis → odczyt
   rundy → UI. Osobno przejść przypadek mapy bez profilu.
4. Sprawdzić invalidację: nazwa/radar, semantyka mapy, konfiguracja detektora,
   wersja ekstrakcji. Rejestrować liczbę wywołań parsera i etapów obliczeń.
5. Zmierzyć cold import/przygotowanie, ciepły odczyt rundy, zmianę gracza,
   przeliczenie profilu, rozmiar payloadów i pamięć procesu na tym samym demie.
   Oddzielić ładowanie całego meczu od odczytu fundamentów i od pełnego payloadu radaru.
6. Porównać z bazą pomiarową E1: ~16,93 s przygotowania, ~0,71 s ciepłego kontekstu,
   ~65 ms fundamentów rundy. To pojedyncze pomiary innych zakresów, nie SLA.
   Istotną regresję powtórzyć i wyjaśnić; nie deklarować wyniku przed pomiarem.
7. Uruchomić właściwe testy, pełny zestaw na końcu, realny Mirage i kontrolę importów
   zależnych od mapy. Zaktualizować dokumentację oraz status roadmapy.
8. Dopiero po odbiorze technicznym integrator stosuje reset do bazy aplikacji,
   importuje realne demo ponownie i sprawdza działanie. Niezależny przegląd w grze
   pozostaje osobnym, jawnym statusem; testy nie zastępują oceny taktycznej replayu.

**Twarde kryteria:** brak parsera przy zmianie profilu/rundy/gracza z kompletnym
cache; niezmienne źródłowe ID przy zmianie profilu; brak ładowania wszystkich rund
dla odczytu jednej; spójność referencji; zachowane źródła i gracze po resecie;
brak reguł Mirage w modelach, ekstrakcji i ogólnych detektorach.

## Raport przekazania wymagany od każdego agenta

- Zakończone podzadania i zmienione pliki.
- Interfejsy udostępnione następnemu agentowi, format przykładowego wejścia/wyjścia.
- Uruchomione testy i rzeczywiste wyniki, w tym jawne pominięcia.
- Zmiany znaczenia danych, pozostałe ograniczenia i blokery integracji.
- Brak resetu danych produkcyjnych przez agentów cząstkowych; odpowiada integrator
  w końcowym kroku M1.8. Nie commitować/resetować cudzych zmian w repozytorium.

## Gotowość do M3–M4

M3–M4 otrzymują źródłowe kontakty z oboma końcami, wspólny zegar, stabilne dowody,
lokalizacje z jakością, indeks rundy i typowane relacje mapy. Detektor refragów
nie potrzebuje profilu, segmentacja lokalnych walk wykorzystuje przestrzeń bez
utożsamiania przejść z LOS, a etykieta wejścia na site opiera się na profilu.
Pełną obsługę kolejnej prawdziwej mapy potwierdza dopiero jej profil i realne demo.
