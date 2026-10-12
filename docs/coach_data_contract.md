# Kontrakt danych coacha — wersja 1

Aktualizacja 2026-10-12: bazowy kontrakt i jego identyfikatory pozostają
w wersji 1; uzupełnia go [warstwa E1](coach_foundations.md), schemat
taktyczny 2 oraz zapis per runda. Freeze-end jest utrwalony w kontekście
przestrzennym i fundamencie rundy. Dalszy opis brakującego freeze-end dotyczy
samego bazowego kontraktu, używanego również bez przygotowania kontekstu.

Stan: fundament pod detektory B2. API odczytu: `load_coach_inputs(db, demo_id)`
w `src/demos/coach_data.py`. Nie generuje raportu, nie wywołuje API i nie parsuje dema.
Wymaga aktualnej wersji wejścia; aktualizację starszej analizy obsługuje istniejący
przepływ `ensure_current_analysis`. Ten dokument definiuje również przyszłe detektory;
nie oznacza, że zostały zaimplementowane.

## Tożsamość i kolejność

- Demo: SHA-256 rozpakowanej zawartości. Zawodnik: dokładny SteamID jako tekst,
  nick tylko do prezentacji. Runda: numer 1-based w wybranym segmencie meczu.
- Zdarzenie: typ źródła + hash przestrzeni identyfikatorów + numer wiersza.
  Przestrzeń uwzględnia demo, wersję wejścia/kontraktu i treść całego źródła.
  ID nadajemy przed filtrowaniem i sortowaniem. Dwa identyczne rekordy pozostają
  dwoma zdarzeniami. Nie usuwamy ich bez potwierdzenia, że są duplikatem parsera.
- Kanonizacja obejmuje sortowanie kluczy JSON, 10 miejsc dziesiętnych (zgodnie
  z zapisem SQLite) i równoważność całkowitych wartości liczbowych 1/1.0.
  Zmiana źródła unieważnia jego identyfikatory; odnośniki z innych wersji raportu
  nie mogą być rozwiązywane względem nowych danych.
- W jednym źródle sortowanie po ticku jest stabilne. Kolejność różnych typów
  zdarzeń w tym samym ticku nie jest znana. Nie wyciągamy z niej związku przyczynowego.
- Liczymy różnice ticków, przy obecnym jawnym założeniu 64 ticków/s. Brakuje
  utrwalonego freeze-end, więc czas od round_start nie oznacza czasu aktywnej gry.

## Rundy i strony

- Ukończona runda poza warmup, z prawidłowym zwycięzcą, w oknie
  `start_tick <= tick <= round_end.tick`. Zabójstwo w ticku końca rundy wchodzi
  do wyniku; przerwa i nieukończona runda nie wchodzą.
- Pierwotny licznik silnika zachowujemy jako `raw_total_rounds_played`.
  Powrót do 1 po wartości >= 1 rozpoczyna nowy segment. Zachowujemy ostatni
  segment. Dotyczy m.in. nożówki przed resetem na dostarczonym demie.
  Sam zestaw broni ani zmiana stron nie służą do wycinania rund.
- Ograniczenie: dema zawierające wiele oddzielnych meczów wymagają w przyszłości
  wyboru segmentu. Bez resetu lub flag parsera nie zgadujemy, która runda była rozgrzewką.
- Strona zawodnika pochodzi z rosteru rundy. 2=T, 3=CT. Zmiana stron i dogrywka
  nie zmieniają tożsamości gracza. Trwała identyfikacja drużyny przez cały mecz
  i historia reconnectów nie są jeszcze częścią kontraktu.
- Brak w rosterze nie daje podstaw do uznania gracza za martwego. Historyczny
  rating ma fallback oparty o strony w zdarzeniach; coach musi ujawniać niepełność.

## Metryki: fakty i mianowniki

| Miara | Definicja |
| --- | --- |
| Kill | Śmierć przeciwnika z różnymi, rozpoznanymi stronami T/CT i ID. Teamkill, świat i samobójstwo nie dają fraga. |
| Death | Śmierć zawodnika, także od świata, sojusznika lub siebie; dla rosteru jeden zgon na życie. |
| Obrażenia | `actual_damage`: surowe dmg_health ograniczone pozostałym HP. `enemy_damage`: ta wartość tylko przeciw przeciwnikowi. HP aktualizują również friendly fire i obrażenia od świata. |
| ADR/KPR | Suma obrażeń/fragów dzielona przez liczbę potwierdzonych rund zawodnika. Pokazujemy mianownik; fallback starego ratingu nie dowodzi udziału we wszystkich rundach. |
| KPR/ADR w wygranych | Analogiczna suma wyłącznie w wygranych rundach / liczba wygranych rund. Nie jest to samodzielny dowód wpływu na wygraną. |
| Asysta | Assister z eventu zabójstwa, należący do drużyny zabójcy. |
| KAST aplikacji | Kill, asysta, przeżycie lub wymieniona śmierć; obecna heurystyka zalicza też co najmniej 40 obrażeń ofierze zabitej przez kolegę. To szersza definicja niż sam licznik asyst. |
| Sniping | Dla przyszłej kategorii AWP/Scout; udział użycia osobno od skuteczności. Brak okazji = brak oceny skuteczności. |

Nie sumujemy powiązanych statystyk jako niezależnego wkładu. Brak danych to nie 0.
Rating pozostaje heurystyką wymagającą kalibracji. Nie znamy pełnych wzorów HLTV.

## Definicje przyszłych detektorów

1. **Opening:** pierwsze zabójstwo przeciwnika w ukończonej rundzie. Wcześniejszy
   teamkill lub śmierć od świata są osobnymi zdarzeniami; stan liczebności może
   już różnić się od 5v5. Wspólny tick wielu zabójstw oznaczamy jako niejednoznaczny.
   Próby = opening kills + opening deaths; skuteczność = kills / próby.
2. **Trade:** zawodnik zabija przeciwnika, który wcześniej zabił jego kolegę
   w tej samej rundzie, w przedziale 0–320 ticków włącznie. Przy kilku ofiarach
   przypisujemy najbliższą poprzedzającą śmierć; pojedynczy frag nie wymienia
   jednocześnie wszystkich wcześniejszych ofiar. Wspólny tick obniża pewność.
   Wariant 192 ticków służy porównaniu, nie miesza się z wynikiem 320 ticków.
   Brak wymiany nie dowodzi, że istniała możliwość jej wykonania.
3. **Flash support:** asysta flashem zgłoszona w kill evencie jest osobnym faktem.
   Dodatkowe powiązanie z player_blind wymaga właściwego przeciwnika, kolegi,
   rundy i aktywnego oślepienia w chwili zabójstwa. Wiele pasujących flashów
   nie daje automatycznie wielu asyst. Czas oślepienia celu liczymy jako sumę
   przedziałów bez nakładania, z obcięciem do śmierci/końca rundy; nie przypisujemy
   sumy wielu rzucającym bez jawnej reguły. Friendly flashes osobno.
4. **Przewaga:** liczba potwierdzonych żywych T/CT przed i po zdarzeniu.
   Przy niepełnym rosterze nie publikujemy dokładnej przewagi jako faktu.
   Utrata przewagi jest sygnałem do przeglądu, nie automatyczną oceną błędu.

## Dostępność i wydajność

Manifest źródeł podaje liczbę wierszy, brakujące wymagane kolumny i kolumny z null:

- `present`: są wiersze i wymagane pola; nie gwarantuje kompletności parsera.
- `partial`: brak części pól albo wartości; detektor musi sprawdzić własne wymagania.
- `unknown`: pusta tabela. Stary zapis nie odróżnia braku zdarzeń od awarii parsera.
- `not_loaded`: świadomie nie pobrano danych, np. trajektorii i stanów graczy.

Odczyt coacha pomija w SELECT trajektorie granatów, czat i scoreboard. Dane
przygotowujemy raz na mecz, następnie filtrujemy po zawodnikach. Pozycje przy
zdarzeniach są migawkami, nie dowodem widoczności czy ciągłą ścieżką ruchu.
Nie ma tu danych ekonomii, pełnego ekwipunku, komunikacji głosowej ani wiedzy gracza.
Potwierdzenie parserowego „poprawnie odczytano zero zdarzeń” wymaga przyszłego
zapisu diagnostyki źródeł; obecny kontrakt celowo pozostawia ten przypadek nieznanym.

## Kontrola na realnych zdarzeniach

Źródło: lokalne demo de_anubis, SHA-256
`c5f3f99d0cfe9eee7f1bf0dbdc2ab8ff2509a4ef01630ac3451bd9ced7dddda0`.
Zanonimizowany wyciąg: `tests/reference/anubis_coach_extract.json`.
Wartości oczekiwane policzono przez przegląd wyeksportowanych zdarzeń, bez użycia
wyników ratingu. To kontrola interpretacji danych parsera, nie niezależny replay
w kliencie gry i nie kalibracja całego ratingu.

| Przypadek | Dowód i oczekiwany wynik |
| --- | --- |
| Nożówka | Pierwszy round_end tick 2661 i następny 8021 mają licznik 1. Odrzucamy segment przed start_tick 4009: 24 rundy zamiast 25, 166 zabójstw zamiast 172. |
| Opening rundy 1 | Tick 6922: A1 zabija B2. CT 5v5 → 5v4. |
| Obrażenia A1 w rundzie 1 | 100 + 5 + 100 + 16 + 16 = 237 HP, 2 zabójstwa. |
| Obrażenia A2 w rundzie 1 | 95 + 100 + 15 + 36 = 246 HP, 3 zabójstwa. Tick 7121: 110 surowe, 95 HP celu. Tick 8021: 125 surowe, 36 HP celu. |
| Trade rundy 1 | B1 zabija A5 w 7337, A2 zabija B1 w 7602: 265 ticków = 4,140625 s. Wymiana przy 5 s, brak przy 3 s. |
| Zmiana stron | A2 ma CT w ostatniej rundzie pierwszej połowy i T w rundzie 13; round_start 68092. |
| Flash support rundy 13 | A3 oślepia B1 w 70498 na 3,0594 s; A2 zabija B1 w 70540, assistedflash=True. Różnica 42 ticki = 0,65625 s. W danych jest również wcześniejszy flash: detektor musi rozwiązać nakładanie. |

Otwarte: niezależne porównanie z odtworzeniem dema, więcej meczów, reconnect,
pełna walidacja dogrywki i kalibracja ratingu. Synthetic fixture nadal sprawdza
świat, friendly fire, samobójstwo, ogień i granice rund.
