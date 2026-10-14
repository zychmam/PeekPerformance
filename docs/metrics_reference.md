# Metryki meczu i dane referencyjne

## Definicje używane przez aplikację

Od **metryk v4** liczniki K/D/A, obrażenia, KAST, przeżycie i Swing korzystają
z aktywnego okna od `round_freeze_end` do `round_end` włącznie. Zdarzenia
sprzed freeze pozostają w źródłach, ale nie zużywają życia ani HP po starcie.
Nadal dopuszczamy jeden aktywny zgon gracza na rundę; rzeczywiste zgony od
świata i sojuszników w aktywnym oknie pozostają liczone. Lista żywych na początku
okna pochodzi z rosteru stron; nie modelujemy dodatkowych respawnów w aktywnej rundzie.

Jeżeli freeze jest nieznany albo poza granicami rundy, zachowujemy całe okno
ukończonej rundy. `metrics_clock_status=unknown` w metrykach rund oraz
`limitations.statistics_reconciliation.unknown_clock_rounds` w JSON ujawniają
to ograniczenie. Nie rozpoznajemy resetów po broni ani rodzaju śmierci.
Świeżo parsowane rundy zapisują zegar. Dla wcześniejszych analiz używamy
zapisanej projekcji zegara obserwacji, bez odczytu trajektorii i bez parsera.
Nowy zapis obserwacji unieważnia metryki i skrót historii; cache sesji UI
uwzględnia generację obserwacji. Starsze analizy bez żadnego zegara wymagają
przygotowania kontekstu albo ponownego wczytania dema, żeby usunąć ograniczenie.

- **Runda:** ukończona runda poza rozgrzewką, zidentyfikowana przedziałem ticków od `round_start` do `round_end` włącznie. Numeracja w aplikacji zaczyna się od 1. Nieukończone rundy nie wchodzą do statystyk. Powrót pierwotnego licznika do 1 po wartości >= 1 rozpoczyna nowy segment meczu; zachowujemy ostatni segment, wykluczając m.in. nożówkę przed resetem na dostarczonym demie. Sama broń nie służy do rozpoznawania nożówki.
- **Zabójstwo:** `player_death` przeciwnika z rozpoznanymi stronami T/CT. Zabójstwo sojusznika, samobójstwo i śmierć od świata zwiększają licznik śmierci ofiary, ale nie zwiększają licznika zabójstw atakującego.
- **Obrażenia:** `dmg_health` pozostaje surową wartością zdarzenia. `actual_damage` oznacza rzeczywistą utratę HP, ograniczoną dostępnym HP ofiary. `enemy_damage` obejmuje tylko tę utratę HP u przeciwnika; pomija friendly fire, samouszkodzenie i świat. `utility_damage` jest częścią `enemy_damage` z HE lub ognia.
- **ADR:** suma `enemy_damage` podzielona przez liczbę rozegranych rund. W widoku statystyk rund `damage` oznacza tę samą wartość po agregacji dla rundy.
- **KAST:** procent rund, w których gracz zdobył zabójstwo, asystę, przeżył lub jego śmierć została wymieniona. Obecna heurystyka zalicza także wkład co najmniej 40 obrażeń w ofiarę zabitą przez kolegę. Wykrycie wymiany używa pięciosekundowego okna przy założeniu 64 ticków na sekundę. Definicja jest własna, nie deklarujemy zgodności z HLTV.
- **Rating i Round Swing:** własna heurystyka PeekPerformance. Zmiana tabelarycznie oszacowanego prawdopodobieństwa wygrania rundy jest dzielona między zabójstwo, wcześniejsze obrażenia ofiary, asystę flashem i wymianę. Wynik łączy tę zmianę z KPR, ADR, przeżywalnością, KAST i rundami z wieloma zabójstwami. To **nie jest oficjalny rating HLTV ani Leetify**; współczynniki i wartości referencyjne wymagają kalibracji na realnych meczach.

## Fixture regresyjny

[`tests/reference/two_rounds.json`](../tests/reference/two_rounds.json) jest **syntetycznym**, ręcznie rozpisanym zestawem zdarzeń w formacie podobnym do wyjścia `demoparser2`. Zawiera rozgrzewkę, dwie ukończone rundy, rundę niedokończoną, zmianę stron, friendly fire, samobójstwo, śmierć od świata, overkill, obrażenia od HE i ognia, asystę flashem, trade oraz podłożenie bomby. Dane nie pochodzą z prawdziwego dema i nie służą do kalibracji ratingu.

Oczekiwane wyniki w fixture zostały policzone z definicji powyżej. Przykłady: A1 trafia B1 za 30 HP, A2 zadaje pozostałe 70 HP mimo surowego `dmg_health=120`; A1 otrzymuje 35 punktów obrażeń od HE na B2. W pierwszej rundzie A1 ma łącznie 65 obrażeń przeciwnikom, więc przy dwóch rundach ADR wynosi 32,5. Śmierci A3 od sojusznika i B2 od świata liczą się jako śmierci bez pozytywnego kredytu za zabójstwo.

Testy w [`tests/test_reference_analysis.py`](../tests/test_reference_analysis.py) sprawdzają przypisanie zdarzeń do rund, HP, obrażenia, liczniki graczy, Swing i integralność SteamID po przejściu przez SQLite. Testy danych i cache są też w [`tests/test_demo_identity.py`](../tests/test_demo_identity.py).

## Walidacja na prawdziwym demo

Aktualizacja 2026-10-08: ręczny przegląd eksportu zdarzeń wykazał doliczaną nożówkę. Poprawiono segmentację: 24 rundy i 166 zabójstw zamiast 25/172. Dodano zanonimizowany wyciąg prawdziwych zdarzeń i niezależnie policzone przykłady obrażeń, wymian oraz zmiany stron. Szczegóły, zakres kontroli i definicje przyszłych detektorów są w [kontrakcie coacha](coach_data_contract.md). Nie zastępuje to niezależnej weryfikacji parsera w kliencie gry.

Lokalne demo `samples/1-1ccc85d8-33b4-4de8-a6fd-ed34154629d0-1-1.dem.zst` przeszło test `tests/test_real_demo_e2e.py`: parsowanie, zapis i odczyt, obliczenie ratingu, projekcje widoków i eksport. Ten test sprawdza działanie całego przepływu i spójność danych; nie zastępuje niezależnej kontroli wartości statystyk. Przed uznaniem metryk i ratingu za zweryfikowane trzeba ręcznie policzyć przypadki kontrolne i porównać je z wynikiem aplikacji. Szczególnie warto sprawdzić rozgrzewkę, overtime, zmianę stron, reconnect gracza, obrażenia od ognia, friendly fire, świat oraz granice rund. Pliki demo pozostają wyłączone z repozytorium przez `.gitignore`.
