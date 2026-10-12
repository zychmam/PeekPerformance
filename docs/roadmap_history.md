# Archiwum roadmapy PeekPerformance

Zapis wcześniejszych planów i wyników sprzed uporządkowania roadmapy 2026-10-12.
Zawiera historyczne statusy, wersje, propozycje modeli i kolejność, które mogły
zostać zastąpione. Aktualny zakres i priorytety: [ROADMAP.md](../ROADMAP.md).
W szczególności dawne zadania migracji analiz nie obowiązują — M1 wdrożono
przez reset wyników i ponowny import dema.

## Stan bieżący — 2026-10-12, po wdrożeniu M1

**A1–A8 zakończone i odebrane technicznie.** Obserwacje, profil mapy,
lokalizacje, fundamenty rund i detektory mają rozdzielone odpowiedzialności.
Cache zapisujemy etapami i per runda; zmiana profilu lub progów nie parsuje dema.
Mirage jest jedynym przygotowanym profilem rzeczywistej mapy.

Weryfikacja: 163 testy z prawdziwym demem, bez pominięć. Ostatni szybki przebieg
po poprawkach odbiorowych: 161 zaliczonych, 2 opcjonalne bez ustawionego dema.
Główna baza ma schemat 8: stare analizy zresetowano, Mirage zaimportowano ponownie
(21 rund, 10 ratingów). Zachowano 3 śledzonych graczy, 3 dema i konfigurację.
Test widoku rund 1/2 oraz zmiany gracza przeszedł bez parsera i wyjątków.
Odbiór wizualny w przeglądarce i niezależny przegląd taktyczny w grze pozostają otwarte.

**Następny etap: R3.1–R3.4 — kontakty, lokalne starcia, opening/refragi 10 s,
efekt walki i następstwo przestrzenne.** R3.5 powiąże utility z dowodami;
R3.6 pokaże wspólną oś zdarzeń i osobne perspektywy drużyn/gracza.
R3.7, czyli referencje i walidacja, towarzyszy implementacji od początku.
Dalej R4: atak, rotacje, bomba i retake; R5: krótkie podsumowania;
R6: agregaty taktyczne mapy. Raport LLM oprzemy na sprawdzonych dowodach.

Szczegóły: [odbiór M1](map_independence_implementation.md),
[plan R3](round_fights_plan.md). Starsze sekcje poniżej dokumentują wcześniejsze etapy.

## Cel produktu

PeekPerformance ma być wirtualnym coachem Counter-Strike 2. Pierwszy cel to analiza **jednego konkretnego meczu** z pliku `.dem`, `.dem.gz` lub `.dem.zst`: czytelne liczby i wykresy oraz raport AI wskazujący dobre zagrania, błędy, powtarzające się zachowania, użycie utility i rzeczy do poprawy. Każdy wniosek ma prowadzić do danych z odpowiedniej rundy. Analiza postępu między meczami jest następnym etapem.

## Punkt wyjścia

Projekt używa Pythona, Streamlit, `demoparser2`, pandas, Plotly, SQLite i openpyxl. Dziś odczytuje demo, pokazuje statystyki i zdarzenia, oblicza przybliżony rating oraz eksportuje Excel i CSV. Historia meczów pochodzi wyłącznie z przeparsowanych dem; stara integracja API i jej tabele zostały usunięte. Raportu AI ani analizy taktycznej jeszcze nie ma.

## Aktualny stan i najbliższe cele — 2026-10-08

Wdrożone: zapis dem po zawartości, historia oparta wyłącznie na demach, panele śledzonych graczy, nicki w interfejsie oraz przebudowa analizy meczu. Przegląd ma pięć kolumn, wybór gracza i przejście z wykresu do rundy. Walka, utility, ekonomia oraz dane i eksport mają osobne sekcje. Logika prezentacji i widoki zostały wydzielone z `app.py`. Próbki stanów są pobierane dla wybranej rundy. Ostatni pełny przebieg po fundamencie coacha: **79 zaliczonych testów**, w tym przepływ z prawdziwym demem; Ruff dla zmienionych modułów bez uwag.

Test E2E potwierdza działanie parsowania, zapisu, ratingu, projekcji i eksportu. Ręczne sprawdzenie wartości statystyk oraz kalibracja ratingu pozostają otwarte. B1 jest częściowo zrealizowane: brakuje pełnej identyfikacji drużyn przez zmianę stron, listy najważniejszych sytuacji i powiązania każdej metryki ze źródłami.

Najbliższa kolejność:

1. **A / P1 — wspólne dane i trwały cache: implementacja ukończona.** Skład, strony i pełne wyniki są zapisane; widoki korzystają ze wspólnych liczników. Podstawowa kontrola wybranych zdarzeń została wykonana; szersza walidacja pozostaje otwarta (A-C02 poniżej).
2. **B2 — sytuacje warte omówienia (4/5 dla pierwszej wersji).** Wykrywać pierwsze zabójstwa i śmierci, wymiany, multikille i wsparcie flashem. Każda sytuacja ma gracza, rundę, czas, identyfikatory zdarzeń i liczby. Pokazać je jako krótkie karty z przejściem do rundy. Samo wykrycie zdarzenia nie oznacza oceny decyzji jako błędnej.
3. **B3 — pierwszy raport coacha przez API (5/5).** Przygotować uporządkowany pakiet dowodów i raport: mocne strony, problemy, tendencje w meczu oraz trzy zalecenia. Sprawdzać liczby i odwołania do zdarzeń. Zapisywać raport wraz z wersją analizy i promptu. Model API wybrać na podstawie porównania raportów z tego samego materiału.
4. **B4 — kontekst taktyczny i utility (5/5).** Dodać mapę 2D, pozycje, czas rzutów, wyposażenie i przebieg wejść/obrony. Dopiero z takim kontekstem oceniać brakujące utility i decyzje taktyczne.
5. **B5 — trendy między meczami (4/5).** Porównywać sprawdzone metryki i sygnały z kolejnych raportów, z uwzględnieniem mapy, strony i wielkości próby.

Najbliższy kamień milowy: dla jednego wybranego gracza z obecnego dema pokazać kilka sprawdzalnych sytuacji i wygenerować raport AI z konkretnymi zaleceniami oraz odnośnikami do rund.

**Aktualizacja refaktoru:** wdrożono wspólne liczniki dla tabeli, kart i rund; zapis składu oraz strony graczy w rundach; pełny wynik ratingu i rund w SQLite; osobne wersje wejścia i metryk; migrację zachowującą mecze i śledzenie. Starsze wejścia są uzupełniane jednorazowo z oryginalnego dema. Zmiana wersji metryk przelicza zapisane zdarzenia, a aktualne wyniki są odczytywane bez parsera. Test na realnym demie potwierdza zgodność sum rund z podsumowaniem dla 10 graczy; po wykryciu i usunięciu nożówki właściwy zakres to 24 rundy (historyczny test obejmował 25). Szersza walidacja i kalibracja ratingu pozostają otwarte. Następna funkcja: chronologia i sytuacje B2.

## Jak czytać oceny

Złożoność to moja ocena pracy **nad implementacją w tym repozytorium**, w skali od 1 (mała, lokalna zmiana) do 5 (duża niepewność i wiele zależności). Model w tabelach oznacza model do **wykonania zadania programistycznego w Codex**, wraz z sugerowanym poziomem rozumowania. To punkt wyjścia, a nie gwarancja wyniku ani potwierdzenie dostępu do modelu na danym koncie. Dobór opiera się na [oficjalnej dokumentacji OpenAI dotyczącej wyboru modelu](https://developers.openai.com/api/docs/guides/model-selection): Luna sprawdza się przy zadaniach wąskich, GPT-6.1 Sol przy złożonej pracy technicznej z uwzględnieniem kosztu, a Astra przy najbardziej wymagającej analizie.

## A. Poprawa istniejącego kodu

| Priorytet | Zadanie | Złożoność | Model do implementacji | Kryterium ukończenia |
| --- | --- | --- | --- | --- |
| P0 | Naprawić zapis identyfikatorów SteamID w SQLite i identyfikować dema po zawartości, a nie samej nazwie pliku. | **4/5** — dotyka zapisu, odczytu i istniejącego cache. | **GPT-6.1 Sol, high** | SteamID jest identyczny przed zapisem i po odczycie; dwa różne dema o tej samej nazwie mają osobne analizy. |
| P0 | Ustalić definicje statystyk i poprawić obliczenia rund, obrażeń, friendly fire, ADR, utility i ratingu. | **5/5** — niejednoznaczności danych i wysoki koszt błędnego wyniku. | **GPT-6 Astra, high** | Wyniki zgadzają się z ręcznie sprawdzonymi przykładami z realnych dem. Rating jest jasno oznaczony jako przybliżony. |
| P0 | Przygotować zestaw referencyjnych dem lub zanonimizowanych wyników i testy algorytmów. | **4/5** — wymaga doboru przypadków i wiarygodnych wartości oczekiwanych. | **GPT-6.1 Sol, high** | Zmiana parsera albo formuły ujawnia regresję w testach. |
| P1 | Ujednolicić przepływ parsowania i cache. | **4/5** — zmiana przepływu danych przez kilka modułów. | **GPT-6.1 Sol, high** | Główne widoki, rating i przyszły raport korzystają z tych samych danych; odświeżenie UI nie parsuje meczu bez potrzeby. |
| P1 | Naprawić filtr rundy w „Player States”, eksport pustej analizy oraz komunikaty dla błędnych plików. | **2/5** — ograniczone, dobrze wskazane usterki. | **GPT-6 Luna, medium** | Widoki pokazują wybrane dane, a niepoprawny plik nie tworzy pozornie kompletnej analizy. |
| P1 | Rozdzielić pozostały moduł interfejsu demo na widoki i logikę analizy. | **4/5** — duży zakres zmian i ryzyko regresji widoków. | **GPT-6.1 Sol, high** | Analizę można rozwijać i testować niezależnie od Streamlit. |
| P2 | Mierzyć czas i zużycie pamięci dla kilku rozmiarów dem; uruchamiać testy i Ruff w CI. | **3/5** — potrzebny powtarzalny zestaw danych i środowisko. | **GPT-6.1 Sol, medium** | Regresje poprawności i wydajności są widoczne przed wydaniem. |

Przegląd przed wdrożeniem P0 wykazał zmianę SteamID `76561198008873401` na `76561198008873408` po zapisie i odczycie z cache oraz kolizję cache po nazwie pliku. Wskazał również błędy filtra rundy w „Player States” i pustego eksportu Excel. Te dwa ostatnie należą do P1. Deklarację wersji Pythona poprawiono na 3.11+.

**Stan P0:** integralność SteamID i rozróżnianie dem po zawartości mają implementację oraz testy. Metryki i rating korzystają ze wspólnej numeracji rund oraz obrażeń przeciwników; są pokryte syntetycznym fixture opisanym w [dokumentacji metryk](metrics_reference.md). Test E2E na dostarczonym prawdziwym demie przeszedł. Porównanie statystyk z niezależnie, ręcznie sprawdzonymi wynikami pozostaje warunkiem zamknięcia walidacji ich poprawności.

## B. Rozwój nowych funkcji

| Etap | Złożoność | Model do implementacji | Powód wyboru |
| --- | --- | --- | --- |
| B1. Obraz jednego meczu | **4/5** | **GPT-6.1 Sol, high** | Łączy obliczenia, interaktywny interfejs i nawigację do danych źródłowych. |
| B2. Sygnały coachingowe | **5/5** | **GPT-6 Astra, high** | Wymaga ostrożnego wnioskowania z niepełnych danych i walidacji znaczenia zdarzeń. |
| B3. Raport AI | **5/5** | **GPT-6 Astra, high** | Łączy API, format danych, sprawdzanie dowodów i ocenę jakości raportu. |
| B4. Głębsza analiza taktyczna | **5/5** | **GPT-6 Astra, xhigh** | Największa niepewność interpretacji pozycji, utility i decyzji graczy. |
| B5. Trendy między meczami | **4/5** | **GPT-6.1 Sol, high** | Wymaga porównywalnych metryk i uczciwego traktowania małych prób. |

### B1. Obraz jednego meczu

Zbudować ekran wybranego gracza z osią rund, wynikami po stronach CT/T, obrażeniami, skutecznością, ekonomią, użyciem granatów i listą najważniejszych sytuacji. Kliknięcie punktu na wykresie powinno otwierać rundę i zdarzenia, z których pochodzi wynik.

**Gotowe, gdy:** użytkownik potrafi znaleźć źródło każdej pokazanej statystyki i przejść od podsumowania do konkretnej sytuacji.

### B2. Sygnały coachingowe z danych

Wydzielić moduł wykrywający sytuacje warte omówienia, na przykład pierwsze zabójstwa i śmierci, trade, wsparcie flashem, granaty zachowane do śmierci, powtarzające się zgony w podobnym momencie rundy i decyzje ekonomiczne. Każdy sygnał ma zawierać gracza, rundę, czas, zdarzenia źródłowe, liczby i ograniczenia interpretacji.

Ocena taktyki oraz „brakującego utility” wymaga kontekstu pozycji graczy i przebiegu rundy. Sama liczba rzuconych granatów nie jest wystarczającą podstawą do takiego wniosku.

**Gotowe, gdy:** wykryte przykłady dobrych i słabych zagrań przechodzą ręczny przegląd na kilku realnych demach.

### B3. Raport AI dla jednego meczu

Po wybraniu akcji „Generuj raport” aplikacja przygotowuje ograniczony, uporządkowany zestaw statystyk i sygnałów, a następnie wysyła go do wybranego modelu przez API. Raport obejmuje mocne strony, najważniejsze problemy, tendencje w tym meczu i konkretne zalecenia treningowe. Każdy wniosek wskazuje rundę i dowody. Wynik trzeba sprawdzić przed pokazaniem: liczby i odwołania, których nie ma w danych, są odrzucane lub poprawiane. Raport jest zapisywany przy meczu, żeby ponowne otwarcie nie wymagało kolejnego wywołania API.

Przed wysyłką użytkownik powinien zobaczyć, jakie dane zostaną przekazane dostawcy modelu. Klucz API należy przechowywać poza raportem i repozytorium. Interfejs powinien obsługiwać limit kosztu, timeout i błąd dostawcy.

**Gotowe, gdy:** dla realnego demo raport zawiera użyteczny feedback, a każdy jego wniosek można sprawdzić w widoku rundy.

**Model działający w produkcie:** to osobna decyzja od modelu implementującego B3. Na pierwszy prototyp raportu wybrałbym **GPT-6.1 Sol** i porównał jego raporty z **GPT-6 Astra** na tych samych demach. Wybór powinien zależeć od trafności wniosków, liczby błędnych twierdzeń, czasu odpowiedzi i kosztu raportu. Dokumentacja OpenAI zaleca takie porównanie na własnych zadaniach: [wybór modelu](https://developers.openai.com/api/docs/guides/model-selection), [katalog modeli](https://developers.openai.com/api/docs/models).

### B4. Głębsza analiza taktyczna

Dodać mapy pozycji i ścieżek, kolejność użycia utility, analizę wsparcia przy wejściu i obronie oraz wzorce rotacji. Wnioski powinny rozróżniać obserwację od oceny decyzji i zaznaczać sytuacje, w których demo nie daje wystarczającego kontekstu.

**Gotowe, gdy:** przykłady taktyczne są weryfikowane na zdarzeniach i pozycjach, bez przypisywania graczom intencji niewidocznych w danych.

### B5. Trendy między meczami

Po dopracowaniu analizy jednego meczu porównywać podobne sytuacje między meczami: mapy, strony CT/T, skuteczność utility, powtarzalne błędy i realizację wcześniejszych zaleceń. Przy każdym trendzie pokazywać liczbę analizowanych sytuacji.

**Gotowe, gdy:** raport progresu lub regresu opiera się na porównywalnych meczach i nie przedstawia pojedynczego zdarzenia jako stałego nawyku.

## Plan wykonawczy coacha dla zawodnika i mapy — 2026-10-08

Ten plan rozwija B1–B5 i określa aktualną kolejność pracy. Status fundamentu A-C opisano poniżej; zadania B2–B5 pozostają **do wykonania**. Istniejący parser, widoki, wspólne liczniki i cache stanowią ich podstawę. P0 oznacza warunek pierwszego wiarygodnego raportu, P1 rozszerzenie analizy jednego meczu, P2 rozwój po walidacji tego raportu. Złożoność: 1–5 według skali powyżej. Dobór modeli do implementacji pozostaje zgodny z tabelami A/B; rozpisanie zadań nie uruchamia subagentów. Model API coacha wybieramy osobno w B3-07.

### Założenia i granice pierwszej wersji

- Przepływ: wybór meczu i zawodnika → kontrola danych/cache → chronologia rund → metryki → epizody → kontekst → wybór tematów → API → walidacja → zapis i widok raportu.
- MVP obejmuje openingi, wymiany, zmiany przewagi i wsparcie flashami. Pokazuje mocne strony oraz maksymalnie trzy priorytety poprawy, z podziałem T/CT tam, gdzie dane to uzasadniają.
- Kategorie inspirowane HLTV porządkują profil. Nie sumujemy ocen stylu do ratingu i nie odtwarzamy nieznanych wzorów HLTV. Skale 0–100 wymagają późniejszej kalibracji. Brak użycia snajperki nie obniża oceny gracza.
- Statystyki liczy kod. LLM interpretuje dostarczone dowody. Każdy wniosek o meczu wskazuje metryki lub epizody; ogólne zalecenia są powiązane z tymi wnioskami.
- Detekcja zdarzenia nie oznacza błędu gracza. Oddzielamy fakt, interpretację i hipotezę; nie zakładamy znajomości komunikacji głosowej ani pełnej wiedzy gracza.
- Pełne dane dema i SteamID nie są potrzebne w API: używamy identyfikatorów uczestników i ograniczonego pakietu dowodów. Nick służy prezentacji w aplikacji.

### A-C. Refaktor i wiarygodność istniejących danych

**Aktualizacja 2026-10-08:**

- **A-C01 — gotowy kontrakt v1:** [definicje, identyfikatory, ograniczenia i przykłady](coach_data_contract.md). Specyfikacja przyszłych detektorów nie oznacza ich implementacji.
- **A-C02 — wykonana kontrola podstawowa, walidacja szersza otwarta:** ręcznie policzone przykłady z eksportu zdarzeń rzeczywistego dema oraz zanonimizowany fixture. Wykryto i poprawiono doliczaną nożówkę: właściwy mecz ma 24 rundy i 166 zabójstw, a nie wcześniejsze 25/172. Sprawdzono obrażenia, overkill, wymianę, zmianę stron i dane flash support. To kontrola interpretacji danych parsera, nie niezależny replay w grze. Otwarte pozostają kolejne dema, reconnect, pełna walidacja dogrywki i kalibracja ratingu.
- **A-C03 — gotowa warstwa odczytu:** `load_coach_inputs` pobiera dane z SQLite bez parsera/API i bez trajektorii granatów, czatu i scoreboardu. Nadaje stabilne identyfikatory dowodów i manifest dostępności. Puste źródła mają status nieznany, nie potwierdzone zero. Diagnostyka pozwalająca rozróżnić zero zdarzeń od awarii parsera wymaga dalszego rozszerzenia zapisu.
- Wersje wejścia/metryk podniesiono do 2/3; starsze analizy wymagają jednorazowego uzupełnienia z oryginalnego dema w istniejącym przepływie aktualizacji.

| ID | Priorytet | Zadanie i zakres | Złożoność | Zależności | Kryterium ukończenia |
| --- | --- | --- | --- | --- | --- |
| A-C01 | P0 | Spisać kontrakt metryk i zdarzeń: granice rund, czas/tick, identyfikacja drużyn przez zmianę stron i dogrywkę, źródła danych, liczniki/mianowniki, brak danych. Ustalić definicję openingu, trade'a i flash support. | 4/5 | Istniejące metryki | Wersjonowana specyfikacja z przykładami, regułami dla teamkill/samobójstwa, końca rundy i niepełnego rosteru; jawne różnice względem nieznanych definicji HLTV. |
| A-C02 | P0 | Przygotować niezależnie sprawdzone przykłady z realnego dema i porównać z obliczeniami; poprawić rozbieżności. Rozbudować referencje o przypadki brzegowe. | 4/5 | A-C01 | Zapisane oczekiwane wartości i źródła dla wybranych rund: obrażenia, opening, trade, flash, przewaga, strona; automatyczny test zgodności. Test E2E nie zastępuje ręcznej walidacji znaczenia danych. |
| A-C03 | P0 | Uporządkować kontrakt dostępu do zapisanych danych dla coacha: manifest dostępności, wersje, stabilne identyfikatory zdarzeń i zakres danych pozycyjnych. | 3/5 | A-C01 | Coach korzysta z istniejącego cache; braki danych są jawne. Zmiana wersji metryk nie uruchamia parsera, jeśli zapisane wejście wystarcza. |

### B2. Chronologia, statystyki i epizody coachingowe

| ID | Priorytet | Zadanie i zakres | Złożoność | Zależności | Kryterium ukończenia |
| --- | --- | --- | --- | --- | --- |
| B2-01 | P0 | Zbudować wspólną chronologię rund dla wszystkich graczy: składy, strony, zabójstwa, HP, liczebność, bomba, czas oraz dostępne wyposażenie. | 4/5 | A-C03 | Deterministyczna kolejność także dla zdarzeń w tym samym ticku; poprawny stan przed/po zdarzeniu i zmiana stron. Brak wyposażenia lub pozycji nie jest zastępowany zerem. |
| B2-02 | P0 | Zapisywać epizody i dowody: ID, typ, uczestnicy, runda/ticki, stan przed/po, źródła, wersja detektora, ograniczenia i poziom pewności. | 3/5 | B2-01 | Stabilne odwołania po zapisie i odczycie, bez duplikowania na ponownym uruchomieniu; źródła można otworzyć w widoku rundy. |
| B2-03 | P0 | Detektor openingów: pierwsze prawidłowe zabójstwo, uczestnicy, strona, dalszy przebieg przewagi i wynik rundy. | 3/5 | B2-02 | Zgodność z referencjami; próby = opening kills + opening deaths; wynik rundy opisany jako kontekst zespołowy. |
| B2-04 | P0 | Detektor wymian: kolega zabija zabójcę gracza w określonym oknie; startowo 5 s, wariant 3 s do porównania. | 4/5 | B2-02 | Testy granicy czasu, łańcucha zabójstw i przypisania jednej wymiany do poprzedniego zgonu; zapis czasu wymiany. Brak trade'a nie jest nazywany zmarnowaną okazją bez danych przestrzennych. |
| B2-05 | P0 | Detektor zmian przewagi i ich sekwencji: np. 5v4 → 4v4, utrata przewagi, odzyskanie równowagi. | 3/5 | B2-02 | Stan liczebności zgadza się z chronologią; epizod wskazuje uczestników i wynik. Utrata przewagi nie przypisuje automatycznie winy ostatniemu zabitemu. |
| B2-06 | P0 | Detektor wsparcia flashem: rzucający, oślepiony przeciwnik, czas i powiązane zabójstwo; osobno oślepienia kolegów. | 4/5 | B2-02 | Jawna reguła powiązania i testy wielu flashów/ofiar; nakładające się oślepienia nie zawyżają wybranej miary czasu. Odróżniamy asystę z eventu od własnej heurystyki. |
| B2-07 | P0 | Zbudować profil gracza w meczu i po stronach: firepower, openingi, trading/entrying, utility oraz dostępne metryki broni i clutchów. | 3/5 | B2-03–06 | Wartości zgodne ze wspólnymi licznikami; każda proporcja ma licznik, mianownik i źródła. Przy braku okazji: brak danych; przy małej próbie: widoczna liczba sytuacji. Bez nieuzasadnionych ocen 0–100. |
| B2-08 | P0 | Grupować epizody i wybierać tematy: pozytywne zagrania, problemy, powtórzenia; usuwać wielokrotne liczenie tej samej akcji. | 4/5 | B2-03–07 | Deterministyczny wybór z uzasadnieniem wpływu, powtarzalności, próby i pewności. Opening + trade + flash w jednej akcji nie daje trzech niezależnych dowodów. Możliwy wynik „za mało danych”. |
| B2-09 | P0 | Dodać karty epizodów i przejście do dowodów w rundzie, z filtrem zawodnika i strony. | 3/5 | B2-02, B2-08 | Użytkownik otwiera z karty właściwą rundę, czas i zdarzenia; widzi fakty i ograniczenia przed uruchomieniem LLM. |

Wagi początkowe służą wyłącznie wyborowi tematów: bomba/czas 5, przewaga/wymiany 5, opening/utility 4, dobór i wykonanie walki 4, ekonomia 3, same agregaty 2. Są heurystyką do walidacji, a nie wagami ratingu. Tematy niewspierane przez wdrożone detektory nie są generowane. Pewność detekcji ogranicza siłę wniosku.

### B3. Uruchamianie coacha i raport AI

| ID | Priorytet | Zadanie i zakres | Złożoność | Zależności | Kryterium ukończenia |
| --- | --- | --- | --- | --- | --- |
| B3-01 | P0 | Przygotować schemat pakietu dowodów i odpowiedzi: kontekst meczu/mapy, gracz, T/CT, metryki, wybrane epizody, ograniczenia, mocne strony, do 3 priorytetów i zalecenia. | 4/5 | B2-07–08 | Pakiet mieści się w ustalonym budżecie; redukcja zachowuje kontekst i ujawnia pominięcia. Twierdzenia mają evidence IDs. Dowody i nicki są danymi, nie instrukcjami dla modelu. |
| B3-02 | P0 | Dodać usługę generowania przez API: konfiguracja dostawcy/modelu, format odpowiedzi, timeout, ograniczone retry, limit tokenów/kosztu, ewidencja użycia. | 4/5 | B3-01 | Sekrety poza repo/logami; obsługa błędów autoryzacji, limitów, timeoutów i niepoprawnej odpowiedzi. Użytkownik zna zakres wysyłanych danych; płatne ponowienia są ograniczone. |
| B3-03 | P0 | Zaimplementować walidację raportu: schemat, istnienie dowodów, zgodność liczb, gracza i strony, dozwolona pewność twierdzeń. | 4/5 | B3-01–02 | Testy odrzucają wymyślone rundy i sprzeczne liczby. Ograniczona naprawa lub czytelny błąd zamiast publikacji wadliwego raportu. Walidacja struktury nie jest przedstawiana jako gwarancja trafności taktycznej. |
| B3-04 | P0 | Zapisać raporty i przebieg generowania; cache po demo, graczu, zakresie, wersjach danych/metryk/detektorów, selekcji, promptu, schematu i konfiguracji modelu. | 4/5 | A-C03, B3-01 | Migracja zachowuje mecze; aktualny raport otwiera się bez API. Zmiana zależności unieważnia odpowiednią warstwę. Rerun Streamlit i podwójny klik nie uruchamiają drugiego zlecenia; po błędzie API używamy gotowego pakietu. |
| B3-05 | P0 | Dodać akcję „Analizuj z coachem”, etapy postępu i ekran raportu: podsumowanie, profil, mocne strony, priorytety, kluczowe rundy i cel na kolejny mecz. | 3/5 | B2-09, B3-02–04 | Działa dla wybranego zawodnika; nicki bez SteamID, jawny stan cache i braków danych, odnośniki do dowodów. Odświeżenie UI nie generuje kosztu. |
| B3-06 | P0 | Test integracyjny całej ścieżki na realnym demie z kontrolowaną odpowiedzią API; scenariusze błędów, cache i zmiany wersji. | 4/5 | A-C02, B3-03–05 | Demo → gracz → epizody → pakiet → walidacja → zapis → ponowne otwarcie. Drugie otwarcie bez parsowania/API; wadliwa odpowiedź nie trafia do opublikowanego raportu. |
| B3-07 | P0 | Ocenić raporty przez rzeczywiste API na tym samym materiale i wybrać model produkcyjny na podstawie trafności, dowodów, użyteczności, czasu i kosztu. | 4/5 | B3-06 | Ręczny przegląd raportów i protokół porównania; brak niepopartych faktów w zestawie odbiorowym. Test z atrapą API oraz ocena jakości prawdziwego raportu opisane osobno. |

### B4–B5. Rozszerzenia po MVP

| ID | Priorytet | Zadanie i zakres | Złożoność | Zależności | Kryterium ukończenia |
| --- | --- | --- | --- | --- | --- |
| B4-01 | P1 | Mapy 2D i strefy: transformacja współrzędnych, poziomy wysokości, nazwy miejsc, wersja mapy; zacząć od mapy z referencyjnego dema. | 4/5 | B2-01–02 | Sprawdzone pozycje na podkładzie i synchronizacja czasu; nieobsługiwana mapa zachowuje analizę liczbową. |
| B4-02 | P1 | Dołączyć pozycje, wyposażenie i ścieżki w oknach wokół epizodów; cache wspólny dla graczy, dokładność adekwatna do detektora. | 4/5 | B4-01, A-C03 | Wizualizacja wskazuje rozdzielczość i braki. Próbkowanie stanów nie udaje ciągłej obserwacji; pomiar czasu i pamięci przed poszerzeniem zakresu. |
| B4-03 | P1 | Ocena możliwości trade'a i wsparcia wejść: odstęp, czas dotarcia, widoczność, przeszkody i smoke. | 5/5 | B4-02, B2-04 | Ręcznie sprawdzone przykłady możliwej i niemożliwej wymiany; sama odległość nie wystarcza. Brak geometrii/widoczności obniża pewność lub wyłącza ocenę. |
| B4-04 | P1 | Analiza bomby, czasu, postplantu i clutchów; save oraz ekonomia jako kontekst decyzji. | 4/5 | B2-01–02, B4-02 | Próby 1vX mają jawne definicje; rozróżnienie walki o cel i zachowania sprzętu, brak automatycznej kary za przeżycie przegranej rundy. |
| B4-05 | P1 | Analiza utility taktycznego i powtarzanych wejść/rotacji; stopniowo smoke, molotov, HE i brakujące wsparcie. | 5/5 | B4-02–04 | Wniosek o brakującym utility uwzględnia posiadany granat, czas, możliwość użycia i przestrzeń. Nie przypisujemy intencji ani wiedzy niedostępnej w dowodach. |
| B4-06 | P1 | Zmierzyć wydajność i koszt całego coacha: zimny/ciepły cache, kilku graczy z tego samego dema, różne długości meczów, API. | 3/5 | B3-07, B4-02 | Zapisane pomiary czasu, pamięci, rozmiaru danych i kosztu; na ich podstawie budżety regresji. Wspólne etapy nie są powtarzane dla każdego zawodnika. |
| B5-01 | P2 | Kalibracja ocen i punktów odniesienia według mapy, strony i dostępnych danych o poziomie graczy; osobno styl i skuteczność. | 5/5 | A-C02, B3-07, większy zbiór referencyjny | Udokumentowana grupa odniesienia, wielkość próby i wersja formuły. Brak danych nie daje zera; brak sumowania stylów do oceny umiejętności. |
| B5-02 | P2 | Trendy i realizacja zaleceń między meczami śledzonego gracza. | 4/5 | B3-07, stabilne metryki i detektory | Porównywalny kontekst, widoczne liczby okazji i wersje; pojedyncza sytuacja nie staje się deklarowanym nawykiem. |

### Kolejność i bramki odbioru

1. **M1 — sprawdzalne dane:** A-C01–03 → B2-01–02. Kontrakty i ręcznie zweryfikowane przykłady gotowe przed oceną detektorów.
2. **M2 — coach bez LLM:** B2-03–06 → B2-07–09. Karty openingów, wymian, przewagi i flash support prowadzą do dowodów; błędy detekcji poprawione na referencjach.
3. **M3 — pierwszy pełny raport:** B3-01 → B3-02–05 → B3-06–07. Jeden wybrany gracz z realnego dema dostaje sprawdzony raport, a ponowne otwarcie nie wywołuje API. Odbiór wymaga testu technicznego i ręcznej oceny jakości.
4. **M4 — kontekst przestrzenny i taktyczny:** B4-01–06, etapami dla obsługiwanych map. Każdy nowy rodzaj wniosków przechodzi walidację przed wejściem do raportu.
5. **M5 — porównania:** B5-01–02 po potwierdzeniu użyteczności analizy jednego meczu.

**Zmiana kolejności na życzenie użytkownika: najpierw kontekst drużynowy rundy na Mirage.**
Poniższy plan T zastępuje wcześniejsze „detektory zdarzeń najpierw”. B2/B3 pozostają
celem, ale korzystają z obserwacji przestrzennych i faz rundy.

| ID | Zadanie | Złożoność | Stan |
| --- | --- | --- | --- |
| T1 | Strefy Mirage, geometria, poziomy i wejścia na site’y | 4/5 | Częściowo: podkład i nazwy stref z dema; granice geometryczne i wysokości otwarte. |
| T2 | Pozycje, życie, strony, kierunek patrzenia, nosiciel i droga bomby | 4/5 | Próbki i nosiciel gotowe; bomba upuszczona/podłożona i ciągłe ścieżki do rozwinięcia. |
| T3 | Zegar i fazy rundy | 3/5 | Freeze-end i czasy zdarzeń gotowe; wejścia i fazy taktyczne otwarte. |
| T4 | Early utility: rzucający, czas, miejsce i obszar działania | 4/5 | Punkty detonacji/startu ognia i czas gotowe; zasięgi i pokrycie stref otwarte. |
| T5 | Ustawienia CT/T i rotacje | 4/5 | Snapshot obu stron po 12 s i dowolny czas; rotacje oraz obsada podczas ataku otwarte. |
| T6 | Presja A/B/mid oraz detekcja wejścia | 5/5 | Do wykonania po walidacji T1–T5. |
| T7 | Rush, execute, split, zmiana kierunku, stack i retake | 5/5 | Do wykonania; oddzielić obserwację od zamiaru. |
| T8 | Wersjonowany rekord rozszerzonej rundy | 3/5 | Cache wejść przestrzennych gotowy; fazy i interpretacje do dodania. |
| T9 | Profil pozycji i tendencji zawodnika | 4/5 | Profil ustawienia po 12 s gotowy; entry, śmierci i zakończenia rund osobno do dodania. |
| T10 | Widok mapy i weryfikacja na realnym demie | 4/5 | Radar, suwak, early utility i test techniczny Mirage gotowe; ręczna ocena taktyczna otwarta. |

Pierwszy przebieg Mirage: 21 rund, 16 930 próbek pozycji, 267 zdarzeń utility.
Zakres i ograniczenia: [kontekst Mirage](mirage_context.md).
Najbliższy pakiet: geometryczna walidacja stref i wejść, fazy/rotacje oraz ustawienie CT
przed atakiem. Następnie presja A/B i rozpoznanie schematu rundy; LLM po walidacji tych danych.

**Aktualizacja 2026-10-09 — wejścia na site:** wdrożono pierwszą wersję detektora
przejść T do stref A/B, kierunki, grupowanie uczestników w 8 s, CT przed/podczas
wejścia, nosiciela bomby i utility poprzedzające epizod. W UI są dowody i przejście
do czasu na mapie. Wynik zapisuje się wspólnie dla graczy i przelicza z cache
po zmianie wersji detektora. Sprawdzenie pierwszej rundy realnego Mirage ujawniło
nakładanie etykiety PalaceInterior z wyjściem rampy; rozróżnienie wykorzystuje XYZ.
To etap T5/T6, nie pełna geometryczna detekcja ani rozpoznanie planu taktycznego.
Definicje i ograniczenia: [wejścia Mirage](mirage_entries.md).
Odbiór 2026-10-11: 10 testów kontekstu i wejść zaliczonych, w tym pełne parsowanie
realnego Mirage, odczyt cache bez parsera i test interfejsu z przejściem do czasu
wejścia. Wcześniejszy pełny zestaw: 89 zaliczonych, 1 opcjonalny test pominięty.
Następnie: oznaczone przykłady B apps/short, krótkie wejścia zakończone śmiercią,
rotacje i sekwencje faz; później presja A/B oraz execute/rush.

## Kolejność realizacji

### Aktualny priorytet — model taktyczny R1–R6 (2026-10-11)

Uzgodniona struktura: przygotowanie T i early utility (0–15 s), ustawienie
i aktywność CT, inicjacja starć i refragi w 10 s, rezultat walki, atak/plant,
rotacje i retake. Raport drużynowy i indywidualny są oddzielne; dowody wspólne.
Ten kierunek zastępuje kolejność opartą najpierw na izolowanych statystykach.

| Zadanie | Status | Wynik |
| --- | --- | --- |
| R1.1 Model rundy i epizodów | Wdrożone | Wersjonowane modele przygotowania, walki, prób ataku (także bez wejścia), rotacji, retake'u i perspektywy gracza; walidacja dowodów i zapis/odczyt JSON. |
| R1.2 Wspólny dostęp do danych | Wdrożone | Adapter ze wspólnym czasem, stabilnymi ID, istniejącymi wejściami i identyfikacją drużyn przez zmianę stron; odczyt cache bez parsera/API. |
| R1.3 Kompletność | Wdrożone | Wymagania źródeł i modułów, null, brakujące pola, luki próbkowania/rosteru; osobno nieznane, potwierdzony brak i analiza niewykonana. |
| R1.4 Referencje | Zestaw bazowy gotowy; pokrycie taktyczne częściowe | Cztery zanonimizowane rundy Mirage i osobne ręczne oczekiwania. Plant/defuse, wybuch, refragi i zmiana stron sprawdzone. Rotacje, początek retake'u, nieudany atak i lurker wymagają dalszych ręcznych adnotacji; luki są zapisane w fixture. |

Dokumentacja: [model rundy taktycznej](tactical_round_model.md).
R1 jest warstwą danych; nie deklaruje nowych detekcji strategii ani ocen taktyki.
Model wczytuje 21 rund, 18 168 dowodów i 26 istniejących wejść z realnego cache Mirage.
Pełne źródła zostają lokalnym materiałem audytowym; nie są automatycznie wysyłane do LLM.

**R2.1–R2.3 wdrożone (2026-10-11):** ustawienia obu stron po 0/5/10/15 s,
potwierdzone przejścia między strefami, early utility z autorem, czasem i XYZ.
Nowy panel w kontekście Mirage prowadzi do wskazanego momentu na radarze.
Źródłem jest istniejący cache; przeliczenie wspólne dla graczy, bez API/parsera.
R1.4 rozszerzone o cztery obsady CT po 10 s i liczniki early utility;
pełna walidacja taktyczna na replayu pozostaje otwarta.
Szczegóły: [przygotowanie rundy](early_round.md).
R2.3 obejmuje punkty działania; zasięg, efekty i wpływ na zajmowanie przestrzeni
pozostają do rozwinięcia. Ruch między strefami nie jest jeszcze oceną agresywności.

**R2.4–R2.5 wdrożone (2026-10-11):** profil kierunków T, pełne ustawienia 5/4+1/
rozłożenie, zaobserwowany kierunek bomby, wczesne wejście i wysunięte pozycje CT.
UI pokazuje osobne krótkie podsumowania T/CT z dowodami; interpretacje mają
ograniczoną pewność. Brak etykiety przy niepełnym składzie, brak automatycznego
lurkera, celu ataku, rush/execute ani oceny pasywności. Wyniki detektora
wymagają dalszego przeglądu na replayu, zwłaszcza klasyfikacji stref CT.

**M1 wdrożone (2026-10-12): profile map wydzielone przed R3.**
Obserwacje, przestrzenny profil mapy i wspólne detektory są rozdzielone.
Zadania A1–A8: [plan M1](map_independence_plan.md).
Reset wyników/cache i ponowny import Mirage wykonane; pliki dem, konfiguracja
i śledzeni gracze zachowani. [Raport odbioru](map_independence_implementation.md).
Następnie R3 — lokalne starcia, opening, refragi 10 s i rezultat wymiany.
Dalsze ręczne adnotacje na replayu pozostają otwarte.

**Plan R3 do przeglądu:** [starcia i nowy widok przebiegu rundy](round_fights_plan.md).
Na życzenie użytkownika **R3 zaczęte od animacji radaru**: rzeczywiste próbkowanie
co 0,25 s (cache kontekstu v3), odtwarzanie w przeglądarce, play/pause, seek,
prędkości, kroki ±0,25 s, zdarzenia i opcjonalne wygładzenie. Realny cache Mirage
przeliczony, aplikacja zrestartowana. Test pełnego dema i runtime JS zaliczone;
wizualny odbiór w przeglądarce otwarty. Szczegóły: [kontekst Mirage](mirage_context.md).
Dalsza aktualizacja odtwarzacza: próbkowanie około 0,1 s (6 ticków), aktywne
smoke’y z dopasowaniem wygaśnięcia i subtelne błyski prawdziwych strzałów.
Obrys smoke orientacyjny, brakujące wygaśnięcia oznaczone jako szacowane;
warstwy wyłączalne. Kontekst v5 zapisany dla realnego Mirage.
R3.1 kontrakt kontaktów → R3.2 lokalne epizody → R3.3 opening/refragi →
R3.4 efekt i następstwo przestrzenne → R3.6 wspólna oś/radar; R3.5 utility
etapami, R3.7 referencje od początku. Ważna poprawka R2: ustawienie przed
pierwszym kontaktem, ponieważ pomiar po 15 s może już opisywać efekt walki.
Później R3 starcia i ich efekty → R4 atak/rotacje/bomba/retake → R5 dwa podsumowania
rundy → R6 wzorce i skuteczność na poziomie mapy.

### E1 — uzupełnienie podstaw analizy (2026-10-12)

Status: **E1-01–E1-07 wdrożone; E1-08 odebrane technicznie**. Niezależny
przegląd w grze pozostaje otwarty. Wspólne dane dla podsumowań drużyny
i zawodnika uzupełniają istniejące R1/R2 przed detektorami R3.

| ID | Zadanie | Złożoność | Zależności |
| --- | --- | --- | --- |
| E1-01 | Sprawdzić dostępność i semantykę nowych źródeł na realnym Mirage | 2/5 | — |
| E1-02 | Rozszerzyć kontrakt, dowody, jakość źródeł i wersjonowanie | 3/5 | E1-01 |
| E1-03 | Zapisywać wyposażenie na początku rundy, zmiany inventory i ekonomię | 4/5 | E1-02 |
| E1-04 | Uzupełnić chronologię bomby o dostępne zdarzenia | 3/5 | E1-02 |
| E1-05 | Włączyć strzały i cykl życia utility do danych coacha | 4/5 | E1-02 |
| E1-06 | Dodać ustawienie obu stron przed pierwszym potwierdzonym kontaktem | 3/5 | E1-02 |
| E1-07 | Dodać zapis per runda, cache i aktualizację istniejących analiz | 4/5 | E1-03–06 |
| E1-08 | Referencje, migracja, integracja na realnym demie i pomiary | 3/5 | E1-07; referencje od E1-01 |

Pełny zakres i kryteria: [plan E1](coach_foundations_plan.md).
Implementacja i pomiary: [dane coacha E1](coach_foundations.md).

Odbiór: dane zapisane i odczytywane bez parsera/API, wspólne dla wszystkich
zawodników; wyposażenie, bomba, strzały/utility i ustawienie przed kontaktem
mają dowody oraz jawne braki. Pozycje pozostają w obecnym cache przestrzennym;
nowa warstwa rund zawiera kompaktowe dane analityczne. Potem kontynuacja R3–R6.

Weryfikacja: 127 testów zaliczonych, 1 opcjonalny pominięty, w tym pełny test
realnego Mirage. 21 rund, 210 stanów wyposażenia/ekonomii na starcie,
2653 obserwacje wyposażenia po kompresji, 2236 strzałów i 275 rzutów.
Przygotowanie 16,93 s, ciepły kontekst 0,71 s, dane jednej rundy 65 ms;
ciepły odczyt bez parsera. To pojedynczy pomiar lokalny. Wersje: SQLite 7,
kontekst 6, fundamenty 1, schemat taktyczny 2. UI dodaje ustawienie przed
kontaktem i rozwijane dane wyposażenia/bomby; radar pozostaje na górze.

Najpierw poprawność identyfikatorów i statystyk oraz dema referencyjne. Następnie ekran i sygnały dla jednego meczu, a potem raport AI oparty na tych sygnałach. Głębszą analizę taktyczną i trendy między meczami warto rozwijać po sprawdzeniu jakości raportu pojedynczego meczu.

Pierwszy kamień milowy produktu: **jeden wiarygodny raport dla jednego realnego demo**, z wykresami, kilkoma trafnie wykrytymi sytuacjami i zaleceniami, których źródła można otworzyć w widoku rundy.
