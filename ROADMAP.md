# PeekPerformance — roadmap

Aktualizacja: **2026-10-14, M5.1–6 i rozszerzenia M5.D2 (Dust2) / M5.AN (Anubis) zaimplementowane; odbiór taktyczny/prezentacji otwarty. LLM wyłącznie w M6**.
Etapy mają jedną numerację **M2 → M3 → M4 → M5 → V2D (epik poboczny) → M6**.
Ukończone R1/R2, E1 i M1 zachowują historyczne identyfikatory.
Mapowanie poprzednich zadań znajduje się na końcu; [archiwum](docs/roadmap_history.md)
zachowuje wcześniejsze plany i przypisania modeli. Ten plik określa aktualne priorytety.

## Cel i sposób oceny postępu

Wirtualny coach CS2 ma wyjaśniać **jeden konkretny mecz z dema** poprzez przebieg
rund, podobieństwa i różnice między nimi oraz wnioski przydatne zawodnikowi i drużynie.
Mirage, Inferno, Dust2 i Anubis sprawdzają wspólny silnik; kolejne detektory rozwijamy
z zachowaniem ich profili i niezależnych referencji.

Każdy etap rozwija ten sam ciąg:

**Warunki rundy → działania obu stron → istotne zmiany sytuacji → zakończenie
→ porównanie z podobnymi rundami → wniosek.**

- **Drużyny:** ustawienie T/CT, utility w pierwszych 10–15 s, inicjacja walki,
  opening/refragi w 5 s, rezultat, wejście/plant, reakcje CT i próba retake.
- **Zawodnik:** start, pierwszy własny kontakt i rezultat, utility, udział
  w wymianach, dalszy ruch i zakończenie rundy.
- **Mecz:** powtarzane kierunki i sposoby ataku, tempo, ustawienia obrony,
  wykorzystanie przewag i efekty działań w porównywalnych warunkach.

Wyposażenie, ekonomia, liczebność, czas i stan bomby nadają kontekst opisowi od
pierwszej wersji. Fakty, interpretacje i hipotezy są jawne. Następstwo zdarzeń
nie dowodzi przyczyny; 4+1 nie dowodzi lurka, przejście kontroli mapy, a defuse próby retake.
Brak danych nie daje zera ani automatycznej oceny błędu.

**Odbiór każdego etapu:** czy potrafimy trafniej i czytelniej wyjaśnić wskazane
rundy oraz wynikające z nich wzorce? Testy techniczne i referencje potwierdzają
poprawność danych; osobny przegląd wyjaśnień sprawdza użyteczność dla gracza.

## Co jest już zrobione

| Obszar | Status i rezultat |
| --- | --- |
| Import i historia | `.dem`, `.dem.gz`, `.dem.zst`, SHA-256 i SQLite. Mecze wyłącznie z dem; Leetify usunięte. |
| Gracze i ekran meczu | Śledzenie uczestników dema, historia i przybliżony rating, nicki, kompaktowy przegląd, rundy/walka/utility/ekonomia. Stary eksport Excel/CSV zastąpiony raportem JSON. |
| R1 — model taktyczny | Wspólne dowody, ID, zegar, drużyny/strony, statusy kompletności i modele przyszłych epizodów. Referencje bazowe gotowe, pokrycie taktyczne częściowe. |
| R2 — przygotowanie | Snapshoty 0/5/10/15 s i przed kontaktem, early utility, przejścia, kierunki T, ustawienia 5/4+1, kierunek bomby i wysunięte CT. |
| Wejścia na site | Potwierdzone przejścia T, kierunki, uczestnicy w oknie 8 s, CT przed/podczas, nosiciel i wcześniejsze utility. Pełna próba ataku pozostaje do rozpoznania. |
| E1 — fundamenty coacha | Wyposażenie, ekonomia, chronologia bomby, strzały, rzuty/cykl utility i ustawienie przed kontaktem, wraz z dowodami i brakami. |
| Radar | Animacja około 0,1 s (6 ticków przy 64 Hz), sterowanie odtwarzaniem, wygładzenie, aktywne smoke'y i błyski strzałów. Mapa na górze analizy. |
| M1 / A1–A8 | Wdrożone obserwacje niezależne od mapy, profile, resolver, indeksy, podłączenie obecnych detektorów, cache etapami/per runda i UI sterowane profilem. |
| M2 — Inferno | Profil drugiej rzeczywistej mapy, radar, referencje i izolowany odbiór przepływu na 20 rundach; ręczny przegląd replayu/UI otwarty. |
| M3 — chronologia | M3.1–6 ukończone, odbiór zaakceptowany przez użytkownika 2026-10-14. Kontakty, opening, refragi 5 s, liczebność, chronologia i dwa podsumowania z dowodami. |
| M4 — działania taktyczne | Pierwsza implementacja M4.1–6 i M4.7; użytkownik zaakceptował obecną wersję i polecił kontynuować. Dalsza kalibracja według nowych przykładów; jawne ograniczenia pozostają w raporcie. |
| M5.1–2 — podstawowe zestawienia mapy | Porównywalne rundy, stałe drużyny/strony, wycena i poprzedni wynik; kierunki/pozycje, kontakty/openingi, early utility, refragi i przewagi. SQLite bez ponownej analizy przy filtrowaniu, nowy widok i skoki do rund. |
| M5.3–6 — pełniejsza prezentacja | Próby T, aktywność/rotacje/retake CT, następstwo rund, opisowe powtórzenia i źródła. Implementacja gotowa; sens taktyczny do wspólnego przeglądu na przykładach. |
| M5.D2 — Dust2 | Profil 24 obszarów, radar, podejścia long/short/tunel/drzwi B, sektory i wysunięcia CT. Demo użytkownika: 28 rund, 10 graczy; pełna ścieżka M3–M5 i cache. Kalibracja interpretacji na przykładach pozostaje otwarta. |
| M5.AN — Anubis | Profil 28 obszarów, radar, podejścia A main/od mida/B main/łącznik, osobne most i kanał. Demo użytkownika: 24 rundy, 10 graczy; wspólne M3–M5, cache i UI. Puste etykiety pozostają nieznane; kalibracja taktyczna otwarta. |

Stack: Python 3.11+, Streamlit, `demoparser2`, pandas, Plotly, SQLite. Eksport: wersjonowany JSON.
Mirage, Inferno, Dust2 i Anubis mają profile rzeczywistych map; profil syntetyczny służy testom.
Obecna wersja detektorów M4 została zaakceptowana; dalsze korekty wynikają z konkretnych przypadków.
Raport LLM, wraz z próbnymi wywołaniami, pozostaje planem M6.

Odbiór M1: **163 testy z prawdziwym demem**, bez pominięć; końcowy szybki przebieg
161 zaliczonych i 2 opcjonalne pominięte bez ścieżki dema. SQLite 8, reset dawnych
analiz bez migracji i ponowny import Mirage: **21 rund, ratingi 10 graczy**.
Zachowano 3 śledzonych graczy, 3 dema i konfigurację. Test UI rund 1/2 oraz zmiany
gracza przeszedł bez parsera i wyjątków. Wszystkie 25 wejść zachowało rundę/site/tick.
Cache lokalizacji zmalał o 81,5%; lokalny odczyt rundy wyniósł około 0,19 s.
Odbiór wizualny w przeglądarce i niezależny przegląd taktyczny w grze pozostają otwarte.

Dokumentacja: [odbiór M1 i pomiary](docs/map_independence_implementation.md),
[kontrakty map](docs/map_data_contract.md), [A1–A8](docs/map_independence_plan.md),
[R2](docs/early_round.md), [E1](docs/coach_foundations.md).

## Kolejność przyszłych etapów

M2 ma techniczną integrację i otwarty niezależny odbiór taktyczny. M3 wraz
z korektami M3.6 odebrane przez użytkownika. Obecna wersja M4 zaakceptowana.
**M5.1–6 wdrożone, M5.R1–R3 poprawione; odbiór prezentacji M5 oraz poboczny V2D przed M6**. Złożoność: 1–5.
Przed zamknięciem M5 użytkownik dołożył **M5.D2**: trzecia mapa, Dust2.
Integracja techniczna wykonana; [zakres, referencje i odbiór](docs/dust2_m5.md).
Następnie dołożono **M5.AN — Anubis** na istniejącym demie użytkownika.
Integracja techniczna wykonana; [zakres i referencje](docs/anubis_m5.md).
Końcowa regresja po obu rozszerzeniach: **276 zaliczonych / 2 opcjonalne pominięte**.
Wszystkie cztery mapy korzystają ze wspólnej logiki detektorów i agregacji.
Weryfikacja rusza od początku każdego etapu, mimo że odbiór jest jego ostatnim zadaniem.

| Etap | Rezultat użytkowy / techniczny | Warunek rozpoczęcia |
| --- | --- | --- |
| **M2 — druga mapa** | Technicznie działa na Mirage i Inferno przez wspólny silnik; ręczny odbiór otwarty. | M1 ukończone; demo Inferno wybrane. |
| **M3 — czytelny przebieg rundy** | Ukończone i zaakceptowane, łącznie z korektami opisu początku, późniejszych zdarzeń i zasobów. | Odbiór 2026-10-14. |
| **M4 — działania taktyczne w rundzie** | Ruch, utility i starcia połączone w próby ataku T, udział graczy poza grupą oraz aktywność i reakcje CT. | Zweryfikowane obserwacje M3; korekty opisu przed odbiorem. |
| **M5 — tendencje T/CT w jednym meczu** | Kierunki, tempo, utility, ustawienia, reakcje i zmiany po wyniku poprzedniej rundy, z licznikami i dowodami. | M5.1–2 na poprawionym M3; dalsze miary po odbiorze właściwych detektorów M4. |
| **V2D — granaty i flash w viewerze 2D** | Rzut, obserwowany lot granatu oraz obwódka oślepienia z jawnym rozróżnieniem pełnej fazy i samego czasu efektu. Poboczny epik bez nowych ocen taktycznych. | Akceptacja [projektu V2D](docs/viewer_2d_utility_plan.md); realizacja przed M6. |
| **M6 — pełny raport coacha** | Zweryfikowany raport przez API, zapis, ponowne otwarcie i nawigacja do dowodów. | Sprawdzone dane oraz użyteczny próbny feedback z M5. |

Podstawowe obserwacje M5.1–2 są wdrożone; przed tendencjami T domykamy review.
Pierwszy raport nie czeka na pełny słownik strategii ani ocenę wszystkich decyzji.

## Wnioski z review M3 i zasady dalszej analizy

Mamy pozycje około 0,1 s, HP/życie, wyposażenie/ekonomię, strzały, rzuty,
detonacje, oślepienia, obrażenia, fragi, bombę oraz źródłowe trajektorie granatów.
Główna luka to powiązanie obserwacji w działania taktyczne. Próbkowanie pozostaje
bez zmian; dodatkowe źródła uzasadniamy konkretnym pytaniem i pomiarem jakości.

| Obserwacja z review | Konsekwencja i zadanie |
| --- | --- |
| Opis początku preferuje stan po 15 s, choć na Mirage R1 kontakt wystąpił po 11,4 s, a na Inferno R1 po 9,7 s. | Podstawą początku będzie świeży stan sprzed nazwanego kontaktu; snapshoty z późniejszej walki mają osobny czas. M3.6a. |
| Tekst skupia się na openingu i pierwszym wejściu; dane zawierają późniejsze zmiany sytuacji i zasoby. | Włączyć istotne późniejsze zmiany liczebności, dostępne wyposażenie i pozycje gracza przy ważnych momentach. M3.6b. |
| Kontakt M3 zaczyna się od dodatnich obrażeń lub fraga. | Opisywać go jako zarejestrowany kontakt; nie utożsamiać z pierwszym dostrzeżeniem, strzałem lub komunikatem. M3.6c, M4.6. |
| Wejście wymaga około 0,5 s potwierdzenia; obecny detektor zachowuje pierwsze wejście gracza na site i grupuje je w 8 s. | Dodać próby zatrzymane przed site'em, krótkie/ponowne wejścia, wycofania i zmianę kierunku. Obecnych wejść nie używać jako wszystkich prób. M4.4. |
| Early utility ma współrzędne, ale niewypełniony region; utility przed wejściem obejmuje całą mapę. | Rozdzielić miejsce rzutu i efektu, poprawić powiązania oraz przypisać kontekst konkretnego działania. M4.2. |
| Liczba CT wewnątrz site'u nie jest pełną obsadą jego obrony; wysunięte regiony bywają zbyt szerokie. | Doprecyzować sektory obrony i granice wysunięcia w profilach, zachowując osobno fizyczną obecność i możliwe wsparcie. M4.1. |

**Znaczenie miar:** tempo i przygotowanie utility to osobne osie. Szybki atak
może być przygotowany granatami; późne wejście nie dowodzi execute'u. Początkowy
kierunek T, cel każdej próby i site planta są osobnymi faktami. Jedna runda może
mieć kilka prób; powodzenie wejścia, planta i wygrana rundy mają odrębne wyniki.
Gracz poza grupą nie otrzymuje automatycznie roli lurka. Opisujemy jego działania
podczas konkretnej próby, także brak zarejestrowanego kontaktu lub dołączenie.

**Uniwersalność:** wykorzystujemy istniejący `MapProfile`, resolver i indeksy.
Profil określa regiony, sektory obrony, podejścia, przejścia, poziomy i granice
wysunięcia dla stron. Silnik liczy wspólne reguły pobytu, ruchu, koncentracji,
starć, prób i reakcji, bez warunków po nazwie mapy lub regionu. Sektor przypisany
graczowi w danym momencie jest jednoznaczny albo nieznany; strefy możliwego wsparcia
pozostają osobno i nie zwiększają obsady dwóch site'ów jednocześnie. Profil nie
zawiera gotowych ocen strategii. Niepełny graf nie dowodzi braku drogi ani wsparcia.
Zmiany semantyki profilu muszą wchodzić do jego fingerprintu; nazwy do prezentacji.

**Wspólny wynik rundy:** warunki → przygotowanie → pobyty/przejścia → starcia
→ próby ataku → reakcje/zakończenie. Rozwijamy obecny kontrakt, z czasami,
uczestnikami, dowodami, statusem i wersją reguły. Tekst podsumowania nie jest
wejściem agregacji. Przy kluczowych zdarzeniach odtwarzamy liczebność, HP,
pozostałe wyposażenie/utility, czas i stan bomby ze znanym pokryciem danych.

**Wydajność:** kompaktowe wyniki liczymy i wersjonujemy per runda, wspólnie dla
wszystkich graczy. M5 agreguje te wyniki bez ponownego parsowania ani skanowania
trajektorii przy każdej zmianie widoku. Reużywamy etapów SQLite i indeksów M1;
nie tworzymy kopii ciężkich pozycji. Zmiana profilu przelicza zależne interpretacje,
a surowe źródła pozostają niezależne. Historyczne analizy mogą być unieważnione
bez migracji. Odbiór mierzy również koszt przygotowania i odczytu całej mapy.

## M2 — integracja drugiej mapy

Cel: ujawnić zależności od Mirage przed rozwojem nowych detektorów.
Wybrano Inferno i prawdziwe demo; niezależne referencje oraz wyniki integracji są
w [raporcie M2](docs/inferno_m2.md).

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| M2.1 | Wybrać mapę/demo i opisać kilka reprezentatywnych rund, miejsca, wejścia, ustawienia oraz braki danych. | 2/5 | M1 |
| M2.2 | Minimalny profil: radar, regiony, site'y, podejścia, poziomy i uzasadnione kierunki/wsparcie. | 4/5 | M2.1 |
| M2.3 | Uruchomić ekstrakcję, lokalizację, fundamenty, przygotowanie, wejścia, zapis i radar na wspólnym silniku. | 3/5 | M2.2 |
| M2.4 | Poprawić ujawnione założenia Mirage w kontraktach/wspólnej logice; reguły mapy zachować w profilu. | 4/5 | M2.3 |
| M2.5 | Odebrać podstawowy przepływ na obu mapach: referencje, UI, cache, ID, braki danych, wydajność i regresje Mirage. | 3/5 | M2.1–4 |

**Gotowe, gdy:** podstawowe obserwacje odpowiadają referencjom, brak możliwości
profilu daje jawne ograniczenie, a nowe mapy nie wymagają rozgałęzień detektorów
po nazwie. Odczyt zapisanych rund i zmiana gracza nie uruchamiają parsera.
M2 kończy się na integracji i poprawności podstaw; pełny graf widoczności oraz
wszystkie warianty taktyczne pozostają poza jego zakresem. Testy syntetyczne nadal obowiązują.

## M3 — czytelny przebieg całej rundy

Pierwsze podsumowanie powstaje razem z detekcją. Wykorzystujemy istniejące
ustawienia, utility, wejścia i chronologię bomby. Opening, refragi oraz globalna
liczebność nie wymagają segmentacji lokalnych starć. Szczegóły reguł:
[plan analizy rundy M3–M4](docs/round_fights_plan.md).

Szczegółowa dekompozycja **M3.1a–M3.6c**, układ podsumowania drużyn/gracza,
kontrakty, wydajność i kryteria odbioru:
[plan podsumowania rundy M3](docs/m3_round_summary_plan.md).

M3.1a–c, M3.2a–b i M3.3a–b wykonane: [audyt i osiem rund referencyjnych](docs/m3_reference_rounds.md),
kontrakt kontaktu/odpowiedzi/liczebności/momentu, walidacja oraz
[kontakty z obu map](docs/m3_contacts.md), [stan żywych](docs/m3_alive.md)
i [refragi/odpowiedź na opening](docs/m3_refrags.md).
M3.4a–d wykonane: [wspólna chronologia momentów](docs/m3_moments.md),
podsumowania drużyny i gracza, czteroczęściowy skrót, pełne wyjaśnienie,
dowody zdarzeń oraz skok do czasu na radarze. Cache wybranej rundy uwzględnia
wersje detektorów, fundamentów, parametry i profil; zmiana zawodnika używa
tej samej analizy, a zmiana rundy buduje osobny wynik.

M3.5a wykonane: testy granic i brakujących danych oraz odczyt ośmiu rund
Mirage/Inferno przez `scripts/verify_m3_summary.py`. M3.5b: test Streamlit
potwierdza przełączanie perspektywy, zawodnika i rundy oraz skoki na radar.
M3.6a–c wykonane technicznie: ustawienie sprzed kontaktu z czasem i pokryciem,
późniejsze zmiany przewagi/stan 1vN, wyposażenie startowe z liczbą odczytanych
graczy oraz pozycje gracza przy wejściu, plancie i końcu. Skrót ma cztery bloki;
pełne opisy, źródła i skoki pozostają rozwijane. Dane z przyszłości i nieświeże
próbki nie zastępują braków. Indeks pozycji można współdzielić między graczami.

Weryfikacja 2026-10-14: **200 testów zaliczonych, 2 pominięte**; odczyt ośmiu
rund Mirage/Inferno z poprawnymi referencjami i ustawieniem przed kontaktem.
Odczyt oraz podsumowania obu perspektyw dla wszystkich graczy: **0,77–1,19 s/rundę**
w skrypcie, bez parsera. To nie pomiar całego UI. Aplikacja uruchomiona na porcie
8501, endpoint zdrowia odpowiada `ok`. **Użytkownik zaakceptował odbiór M3.5b
i zamknięcie M3 2026-10-14.**

Review 2026-10-13: **32 testy dotyczące M3 zaliczone**, odczyt ośmiu rund
Mirage/Inferno i referencje podsumowań poprawne; około **0,72–1,05 s** na rundę
w tym przebiegu skryptu. To pomiar techniczny odczytu/składania, nie czas całego
UI ani potwierdzenie wszystkich interpretacji taktycznych.

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| M3.1 | Ustalić minimalny rekord przebiegu i przykłady oczekiwanych podsumowań. Dołączyć istniejące warunki startu: wyposażenie/ekonomię, strony, czas i jakość danych. | 3/5 | M2 |
| M3.2 | Uporządkować kontakty: czas, uczestnicy, obie pozycje; osobno pierwsze obrażenia utility i pierwszy kontakt ogniowy. | 3/5 | M3.1 |
| M3.3 | Obliczyć opening rundy, refragi/odpowiedź w 5 s i zmiany globalnej liczebności. Refrag wymaga zabicia dokładnego zabójcy kolegi; ratingowy trade pozostaje osobnym obliczeniem. | 4/5 | M3.2; bez segmentacji |
| M3.4 | Złożyć oś od przygotowania przez kontakty, wymiany i istniejące wejścia/plant do zakończenia. Pokazać krótkie podsumowania drużyn/gracza i dowody na jednym radarze. | 4/5 | M3.1–3; widok rozwijany od pierwszych wyników |
| M3.5 | Sprawdzić całe wyjaśnienia wybranych rund na obu mapach, referencje, granice 5 s, brakujące dane, cache i zmianę gracza. | 3/5 | Referencje od M3.1; odbiór po M3.4 |
| M3.6a | Skorygować opis początku: preferować świeży snapshot sprzed nazwanego kontaktu, osobno oznaczać pomiary 10/15 s i ich pokrycie; bez kontaktu użyć jawnie wskazanego wczesnego momentu. | 2/5 | Obecne M3.4 i E1 |
| M3.6b | Uzupełnić skrót o istotne późniejsze zmiany liczebności, dostępny kontekst wyposażenia i obserwowane pozycje gracza przy kontakcie/wejściu/plancie/końcu. Zachować krótki opis i szczegóły na żądanie. | 3/5 | Obecne M3.4; bez zależności od M4 |
| M3.6c | Ujednolicić znaczenie opisów: kontakt z obrażeniami/frag, obecność na site vs obrona sektora, wejście vs próba, następstwo vs przyczyna; sprawdzić poprawione zdania na referencjach i domknąć M3.5b. | 2/5 | M3.6a–b |

**Gotowe, gdy:** użytkownik rozumie warunki startu, działania stron, pierwszą
wymianę, istotne zmiany przewagi i zakończenie. Każdy opis ma dowody. Widok gracza
pokazuje jego udział w tej samej chronologii. Nieznany wynik kontaktu pozostaje
nieznany; brak fraga nie oznacza przegranego pojedynku. Próby retake/rotacje
pozostają niewyliczone do M4, a zaobserwowany plant/defuse nadal są widoczne.

## M4 — działania taktyczne w rundzie

**Stan 2026-10-14:** pierwsza implementacja M4.1–6 i integracja M4.7;
użytkownik uznał obecną wersję za poprawną i zaakceptował kontynuację do M5.
Reguły, przykłady i ograniczenia: [M4 — działania taktyczne](docs/m4_tactical_actions.md).
W UI: **Kontekst rundy → Działania taktyczne**, cztery zakładki oraz dowody/skoki
na istniejący radar. M3 zachowuje krótki opis; szczegółowe wyniki są rozwijane.

- Pobyty i przejścia obejmują całą rundę, z lukami i śmiercią. Sektory CT są
  rozłączne; możliwe wsparcie nie zwiększa obsady obu site'ów. Dolna banana ma
  konserwatywną granicę geometryczną; top mid Inferno nie oznacza sam w sobie wysunięcia.
- Utility zachowuje osobno rzut, efekt, zaobserwowane wygaśnięcie, kandydatów
  dopasowania i potwierdzone obrażenia/oślepienia. Nieznany region pozostaje nieznany.
- Lokalne starcia, kolejne próby T, krótkie wejścia, rozdzielenie graczy od
  koncentracji, reakcje względem kontaktu/planta i retake mają strukturalny wynik.
  Regiony, progi i źródła są jawne; klasyfikacja intencji/rush/execute nie jest wymuszana.
- SQLite: etap `tactical_actions` per runda, wersje źródeł/profilu/reguł/parametrów,
  bez kopiowania trajektorii ani uzależnienia agregacji od tekstu. Zmiana gracza
  używa wspólnej analizy; cache omija detektory M4.

**Dalsza kontrola jakości według nowych przykładów:** kalibracja granic wysunięcia,
prób zatrzymanych/zmian celu, reakcji CT i konkretności zdań. Nie blokuje przyjętej
wersji M4 ani M5. Czas wyjścia z sektora nie jest pełnym czasem
rozpoczęcia ruchu w jego obrębie. Niejednoznaczne granaty oraz brak regionów
efektu nie mają wymuszonego dopasowania. M5.1–2 może korzystać z odebranych faktów M3.

Weryfikacja techniczna: **221 testów zaliczonych, 2 opcjonalne pominięte**;
21 testów M4, regresje podsumowań ośmiu rund M3 i spójność wyników/cache dla
wszystkich **41 rund** obu map, bez parsera. Ruff nowych modułów przechodzi.
Pełny przepływ mapy po przygotowaniu profilu: Mirage **8,59 s / 8,26 s**,
Inferno **9,97 s / 9,72 s** (obliczenie / ponowny odczyt z cache M4).
Ponowny odczyt wciąż składa M3 ze źródeł; to nie czas samej agregacji M5.

Cel pozostaje ten sam: wyjaśnić przebieg działań obu stron. Po review dodajemy
jawny fundament ruchu i utility, a działanie graczy poza główną grupą oraz
aktywność CT stają się częścią podstawowego zakresu. Etykiety rush/execute/split
i ocena intencji są późniejszym skrótem pomiarów. Zadania M4/M5 poniżej mają
nową numerację; mapowanie wcześniejszej wersji znajduje się na końcu.

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| M4.1 | **Przestrzeń i ruch całej rundy.** Ustalić wspólny rekord pobytu/przejścia: obszar, wejście/wyjście, czas utrzymania, poprzedni/następny obszar, śmierć i luki. Doprecyzować sektory obrony oraz granice wysunięcia w profilach Mirage/Inferno. Wykorzystać obecne próbki i indeksy. | 4/5 | Obserwacje M3 i profile M1/M2 |
| M4.2 | **Kontekst utility i zasobów.** Połączyć autora, miejsce/czas rzutu, miejsce/czas działania, wygaśnięcie i mierzalne efekty. Zweryfikować identyfikatory/istniejące trajektorie dla niejednoznacznych par; zachować niepewność. Dodać wspólny odczyt HP, wyposażenia, bomby i liczebności w momencie zdarzenia. | 4/5 | M4.1, E1, kontakty/liczebność M3 |
| M4.3 | **Lokalne starcia i ich rezultat.** Grupować kontakty czasem, miejscem i uczestnikami; rozdzielać równoległe walki i kolejne epizody. Zachować obrażenia bez fraga, nieustalone pozycje i pierwszy frag epizodu. Wyliczyć HP, straty, refragi i stan lokalny/globalny; dołączyć potwierdzone efekty utility osobno od bliskości czasowej/przestrzennej. | 5/5 | M4.1, M3.2–3; efekty/zasoby po M4.2 |
| M4.4 | **Próby ataku T i tempo.** Powiązać podejścia, główną grupę, bombę, starcia i utility. Zachować kolejne próby w rundzie, zatrzymanie przed site'em, wycofanie, zmianę kierunku, krótkie i ponowne wejścia. Osobno mierzyć czas od freeze, początek natarcia, postoje i rozciągnięcie wejścia. Wyniki wejścia, planta i rundy pozostają odrębne. | 5/5 | M4.1–3 i obecne wejścia/bomba |
| M4.5 | **Gracze poza główną grupą T.** Dla każdej próby wyznaczać rozdzielenie w czasie względem żywych T oraz działania: utrzymanie obszaru, kontakt, utility, przechwycenie obserwowanej rotacji, dołączenie lub udział w zmianie kierunku. Dopuścić kilku graczy poza grupą i nieznaną rolę; samo 4+1 nie oznacza lurka ani jego skuteczności. | 4/5 | M4.1–4; powiązanie z rotacją po M4.6 |
| M4.6 | **Aktywność CT, reakcje i retake.** Rozpoznać wysunięcie, utrzymanie obszaru, wycofanie i późniejsze działania oraz przypisane utility. Rotację opisać względem nazwanego kontaktu/planta: ruch rozpoczęty wcześniej, opóźnienie rozpoczęcia, czas drogi, przybycie lub przerwanie. Powiązać z próbą T i zmianą obsady; osobno wykrywać próby/wynik retake. | 5/5 | Ruch i starcia M4.1–3; kontekst ataku po M4.4; bomba E1 |
| M4.7 | **Integracja i odbiór.** Stopniowo zasilać istniejący opis drużyn/gracza, radar i kompaktowy wynik rundy dla M5. Sprawdzić referencje obu map, luki, nieudane/ponowne próby, równoległe starcia, działania poza grupą i brak retake. Zmierzyć cache, zmianę gracza i odczyt całej mapy. | 4/5 | Referencje od M4.1; odbiór końcowy M4.1–6 |

Przed każdym detektorem zapisujemy kryteria i przykłady pozytywne/negatywne.
Rozpoznanie próby ataku nie może wymagać fraga, wejścia ani planta: potrzebne
są również przypadki podejścia/utility zakończonego wycofaniem. Krótką obecność,
potwierdzone utrzymanie site'u i niepewne przekroczenie odróżniamy zamiast
jednego progu wycinającego nieudane wejścia. Tempo pozostaje pomiarem; progi
etykiet kalibrujemy na obu mapach i jawnie podajemy ich wersję.
Pojedynczy granat lub obecność na podejściu nie wystarczają do potwierdzenia
próby: słaby sygnał pozostaje presją/nieustalonym działaniem. Referencje obejmują
utility bez natarcia i ruch niezwiązany z atakiem; nie wymuszamy celu każdej rundy.

Brak rotacji oceniamy tylko przy znanym pokryciu i dla uprawnionych żywych
graczy spoza docelowej obrony. Śmierć, koniec rundy lub luka mogą przerwać
obserwację — nie dają zerowego czasu reakcji. Obserwowana obecność i przejścia
nie dowodzą pełnej kontroli, widoczności ani motywu ruchu.

**Gotowe, gdy:** użytkownik widzi przygotowanie obu stron, przebieg lokalnych
walk, próby T wraz z działaniami poza grupą, reakcje CT i zakończenie. Każdy opis
ma źródła i rozdziela próbę od rezultatu. Te same reguły przechodzą referencje
Mirage/Inferno oraz test profilu syntetycznego po zmianie ID regionów; brak
możliwości profilu daje jawne ograniczenie. Wyniki nadają się do agregacji M5
bez wyciągania faktów z tekstu. Nie wymagamy oceny intencji ani geometrii widoczności.

## M5 — tendencje T/CT i relacje między rundami jednego meczu

**Wdrożone M5.1–6 oraz poprawki M5.R1–R3. Odbiór prezentacji przez użytkownika pozostaje otwarty.**
[Reguły, jednostki, wydajność i ograniczenia](docs/m5_baseline.md).
[Zakres M5.3–6, format prezentacji i weryfikacja](docs/m5_tactical_summary.md).
UI: **Tendencje mapy → Przygotuj zestawienia mapy**. Filtry drużyny, T/CT,
gracza, czasu snapshotu, rund i wyceny sprzętu. Mianowniki oraz nieustalone
przypadki są jawne; rozkład obecności T nie jest klasyfikacją strategii.
Opcjonalny filtr 5 na 5 wymaga znanej liczebności obu stron na starcie.

Etap SQLite `map_round_facts` pozwala odczytać pełniejsze fakty całej mapy w około
**52–60 ms**, a cztery agregacje drużyna/strona zajmują około **6–7 ms**.
Po pierwszym przygotowaniu filtry nie uruchamiają parsera ani detektorów.
Zweryfikowane obie mapy, 41 rund, cache oraz widoki T/CT obu drużyn przez AppTest
na rzeczywistych danych. Regresje obejmują jednostki, niepełne źródła, zmiany celów,
rotacje, następstwo rund i nawigację do radaru. Ruff nowych modułów przechodzi.
Pełna regresja po tych zmianach: **252 zaliczone / 2 opcjonalne pominięte**.

**Dostępne:** cele/tempo/przygotowanie kolejnych prób T i udział poza grupą,
osobny wynik wejścia/planta/rundy, aktywność/reakcje CT i retake oraz porównania
po wygranej/przegranej. Widoki: **Ataki T / Obrona i rotacje CT**, **Następstwo rund**,
**Wnioski z danych**. Zachowano wcześniejsze zestawienia i wspólną nawigację.
M5 kończy się pełną prezentacją danych i obserwacji M5.6. Integracja, próbne
wywołania i ocena raportów LLM należą w całości do M6, zgodnie z decyzją użytkownika.

M5 odpowiada bezpośrednio na pytania użytkownika o T i CT. **M5.1–2 korzystają
z odebranych obserwacji M3/M4.** Dalsze miary udostępniamy po odbiorze
właściwego detektora; brak detekcji nie jest zerem. Wyniki pozostają opisem
jednego meczu, z warunkami porównania i rozmiarem próby.

### Poprawki review przed M5.3

[Review kodu, reprodukcje i kryteria odbioru](docs/m5_review.md).
Status: **M5.R1–R3 wdrożone i objęte regresją**. Przed rozszerzeniem M5 sprawdzono
51 testów oraz cache obu map. Kontakty mają wersję 2; pełne fakty M5 wersję 6.

| Zadanie | Priorytet / złożoność | Zakres i odbiór |
| --- | --- | --- |
| **M5.R1** | P1 / 2 z 5 | Poprawić kompletność kontaktów: OBSERVED + potwierdzony ABSENT to znane źródła. Znany brak kwalifikujących kontaktów odróżnić od luki. Jawny status pierwszego dostępnego kontaktu w niepełnej rundzie. Regresje damage-only/kill-only/puste/niepełne źródła; wersjonowanie cache. |
| **M5.R2** | P1 / 2 z 5 | Rozdzielić unikalne fragi wymieniające i wymienione zgony, zachowując ID obu zdarzeń. Jeden frag za dwóch kolegów = 1 frag, 2 zgony, 1 runda. Sprawdzić filtr gracza, podpisy i dowody; zwiększyć wersję faktów. |
| **M5.R3** | P2 / 2 z 5 | Snapshot po końcu rundy oznaczyć jako niekwalifikujący się do pomiaru, zamiast brakujących pozycji. Osobne eligible/known/unknown/not_applicable; nie zmieniać zakresu innych miar. Test granicy czasu, braków zegara i próbek. |
| **M5.R4** | P2 / 1 z 5 | **Wykonane w review:** uaktualnić końcową kolejność i usunąć sprzeczne wskazanie M3.5b/M4.1 jako następnego zadania. |

Warunek rozpoczęcia M5.3 został spełniony. Odczyt cache obu map po zmianie wersji
nie wywołuje detektorów przy filtrowaniu; dawne wyniki nie wymagają migracji.
Fakty obejmują rzeczywiste `attacks`, aktywność CT, okazje/rotacje, retake i planty
z M4. Osobne mianowniki rund/prób i wyniki wejścia/planta/rundy są w UI.
Pokrycie prób wymaga kompletnych źródeł używanych przez detektor, również utility
i bomby. Obserwacje z niepełnej rundy pozostają dostępne z jawnym ograniczeniem.

Status zadań poniżej: **M5.1–6 zaimplementowane i zweryfikowane technicznie;
odbiór czytelności i użyteczności prezentacji przez użytkownika pozostaje otwarty**.

### Zadania M5

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| M5.1 | **Porównywalne rundy i mianowniki.** Zachować tożsamość drużyny przy zmianie stron; porównywać osobno T/CT, wyposażenie/ekonomię, czas i liczebność. Uwzględnić brakujące dane, zachowany sprzęt, wynik poprzedniej rundy i granice połów/resetów. Ustalić jednostkę: runda, próba ataku lub okazja do reakcji. | 3/5 | M3.6 i E1 |
| M5.2 | **Pierwsze zestawienia z M3.** Rozkład wczesnych kierunków/pozycji, miejsc i czasu kontaktów/openingów, early utility, refragów i wykorzystania przewag. Podawać czas snapshotu i pokrycie; wejścia liczyć jako zaobserwowane wejścia. Rozszerzyć zestawienia o sektory M4.1 i miejsca rzutu/działania M4.2 po ich odbiorze. | 3/5 | M5.1; bez oczekiwania na pełne M4 |
| M5.3 | **Tendencje T.** Zestawić początkowy kierunek, cele kolejnych prób, A/B, tempo, przygotowanie utility, podejścia, działania graczy poza grupą i końcowy plant. Grupować podobne wykonania; osobno skuteczność wejścia, planta i wygrania rundy. | 4/5 | M5.1–2, M4.4–5; kontekst utility M4.2 |
| M5.4 | **Tendencje CT.** Zestawić ustawienia sektorów, częstość/kierunki wysunięć, utrzymanie i późniejsze wykorzystanie obecności, utility przy aktywnej i pozycyjnej obronie, reakcje/rotacje oraz retake. Podać okazje do reakcji, brak/przerwanie rotacji i czasy dla obserwowanych przypadków. | 4/5 | M5.1–2, M4.1–3 i M4.6 |
| M5.5 | **Zmiany między kolejnymi rundami.** Porównać powtórzenie/zmianę kierunku, tempa, utility i ustawienia po wygranej/przegranej w obrębie tej samej strony. Uwzględnić zmianę zasobów i próby w poprzedniej rundzie; opisywać następstwo bez udowadniania świadomej adaptacji. | 3/5 | Wersja podstawowa po M5.2; pełna po M5.3–4 |
| M5.6 | **Wnioski i prezentacja mapy/gracza.** Wybrać kilka istotnych powtórzeń i wyjątków z M5.2–5; zestawić warunki, przebieg i wyniki. Każdy wniosek: zakres, licznik/mianownik, pokrycie, rundy/dowody i ograniczenia. Widoki T/CT oraz udział zawodnika prowadzą do tej samej rundy i radaru. | 4/5 | Iteracyjnie od M5.2; pełny zakres po M5.3–5 |
| M5.7 | **Przeniesione do M6.1.** M5 nie obejmuje integracji ani prób LLM. Odbiór M5 dotyczy kompletnej prezentacji danych z dema. | — | Decyzja użytkownika |
| M5.D2 | **Dust2 przed zamknięciem M5 — zaimplementowane.** Profil/asset/rejestr, obszary i podejścia, sektory/wysunięcia CT, wspólne M3–M5, referencje z prawdziwego dema, radar, cache i UI. Bez rozgałęzień detektorów pod nazwę mapy. Ręczny odbiór interpretacji pozostaje otwarty. | 3/5 | M5.1–6; demo Dust2 użytkownika |
| M5.AN | **Anubis przed zamknięciem M5 — zaimplementowane.** Profil/asset/rejestr, podejścia A/B, rozdział Bridge/Canal, sektory i wysunięcia CT, wspólne M3–M5. Referencje z dema, radar, cache i UI; wspólny skrypt weryfikacji nowych map. Ręczny odbiór interpretacji pozostaje otwarty. | 3/5 | M5.D2; demo Anubis użytkownika |
| M5.EX | **Raport JSON do ręcznego LLM — zaimplementowane.** Zastępuje Excel/CSV; cały mecz, wszyscy gracze, statystyki T/CT, rundy M3/M4, agregaty M5, definicje, pokrycie i krótkie referencje. Schema 1.0, tabelki columns/rows, bez SteamID i surowych trajektorii. [Kontrakt](docs/match_report_export.md). | 3/5 | M5.1–6; format zaakceptowany przez użytkownika |
| M5.EX.R1 | **Poprawione:** wspólny kalkulator liczy zdarzenia od końca freeze do końca rundy włącznie; reset sprzed freeze nie zużywa życia ani HP aktywnej rundy. Brak zegara jest jawny, bez zgadywania resetu. Metryki v4, unieważnianie cache po zapisaniu zegara obserwacji; odczyt samego zegara bez dekodowania trajektorii. Inferno R12 i Anubis R3 zachowują późniejsze prawidłowe fragi; UI, historia i JSON korzystają z tej samej reguły. | 3/5 | Przypadki z rzeczywistych dem wykryte podczas walidacji M5.EX |

Odbiór techniczny M5.EX i M5.EX.R1: **292 testy zaliczone / 2 opcjonalne pominięte**.
Raporty czterech map (93 rundy) przeszły walidację schematu, odwołań i statystyk.
Po korekcie kalkulatora brak rozbieżności fragów: Dust2 205, Inferno 136,
Anubis 164, Mirage 153. Zregenerowano raporty bez ponownego parsowania dem.

Docelowe pytania odbiorowe, z przejściem do przykładowych rund:

| Perspektywa | Pytanie i zakres odpowiedzi | Zadania |
| --- | --- | --- |
| T | A czy B: wczesny kierunek, cel próby i plant osobno, również zmiana celu w rundzie. | M4.4, M5.2–3 |
| T | Jak szybko atakowali dany site: czas przygotowania, start natarcia i długość wejścia; tempo osobno od execute/rush. | M4.4, M5.3 |
| T | Jakie utility towarzyszyło szybkim/wolnym atakom i gdzie działało. | M4.2–4, M5.3 |
| T | Co podczas ataku robił gracz poza grupą: pozycja, kontakt, utility, dołączenie, przechwycenie lub udział w zmianie kierunku. | M4.5–6, M5.3 |
| T | Gdzie następowały pierwsze kontakty/openingi; obserwowane podejścia także bez obrażeń jako osobna miara. | M3, M4.1, M5.2–3 |
| T | Jakie utility rzucano ze spawnu: region autora, czas i cel; early utility ma osobne zestawienie. | M4.2, M5.2–3 |
| T | Co powtarzano/zmieniano po wygranej lub przegranej, z uwzględnieniem ekonomii. | M5.5 |
| CT | Jakie ustawienia sektorów wybierano przed kontaktem i jak zmieniała się obsada. | M4.1, M5.2 i M5.4 |
| CT | Jak często grano wysunięciem, utrzymaniem pozycji i wycofaniem; wynik działań zamiast pojedynczej etykiety stylu. | M4.6, M5.4 |
| CT | W których obszarach podejmowano próby wysunięcia/przejęcia i jak długo utrzymywano obecność. | M4.1 i M4.6, M5.4 |
| CT | Co następowało po uzyskaniu obecności: utrzymanie, przesunięcie obrony, flanka, kontakt lub wycofanie; kontrola pozostaje ograniczoną interpretacją. | M4.6, M5.4 |
| CT | Jakie utility towarzyszyło wysunięciom i lokalnym walkom. | M4.2–3 i M4.6, M5.4 |
| CT | Jakie utility stosowano przy obronie pozycyjnej i w relacji czasowej do natarcia T. | M4.2 i M4.4–6, M5.4 |
| CT | Kiedy zaczynano rotację i kiedy docierano względem nazwanego kontaktu/planta, także ruch wcześniejszy i brak przybycia. | M4.6, M5.4 |

**Gotowe, gdy:** raport taktyczny meczu odpowiada na powyższe pytania w zweryfikowanym
zakresie, a braki pokazuje jawnie. Ma kilka uzasadnionych obserwacji, pełne
zestawienia danych i nawigację do dowodów. Jedna sytuacja nie staje się nawykiem; zdarzenia z tej samej
próby nie są niezależnymi powtórzeniami. Wyniki podają osobno próby, rundy,
wejścia, planty i zwycięstwa, z liczbą przypadków pominiętych/nieznanych.
Zmiana kierunku po porażce nie dowodzi intencji ani przyczyny adaptacji.

M5 udostępnia obliczone przez kod obserwacje; generowanie feedbacku przez LLM
zaczyna się w M6 po odbiorze tej prezentacji. Wykryte luki kierujemy do konkretnej
obserwacji lub reguły; nie rozbudowujemy parsera bez uzasadnionej potrzeby.

## V2D — ulepszenie viewera 2D przed M6

**Status: V2D.1–5 wdrożone w zakresie audytu: granaty i deklarowane okna
efektu flasha. Ręczny odbiór V2D.6 pozostaje otwarty; dokładna faza pełnego
oślepienia nieustalona. Aktualizacja V2D: 2026-10-15.**
[Pełny projekt, kontrakt i warunki odbioru](docs/viewer_2d_utility_plan.md).
[Wynik audytu źródeł i decyzja](docs/v2d_source_audit.md).

Cel: widzieć, kto rzucił granat, jego rzeczywisty lot i kto został oślepiony.
Reużywamy rzutów `weapon_fire`, zapisanych trajektorii, cykli utility i zdarzeń
`player_blind`. V2D.1: 797 zdarzeń na czterech mapach; `flash_duration` jest
wartością początkową, a `flash_max_alpha` nie jest chwilową alfą ekranu.
Dokładna pełna faza pozostaje nieznana; wdrażamy deklarowane okno efektu
z przerywaną białą obwódką. Stała obwódka pełnego oślepienia wymaga nowego
potwierdzenia; POV nie zostało porównane. Wybór gracza zmienia obwódkę
na turkusową, żeby nie mylił się z flashem.

| ID | Zadanie | Złożoność | Zależności |
| --- | --- | --- | --- |
| V2D.1 | **Audyt techniczny wykonany.** Przykłady z czterech map, semantyka flasha i rzeczywiste tory. Potwierdzono odczyt samych pocisków (87–91% mniej wierszy). Pełna faza flasha nieustalona; dalsza kontrola wszystkich powiązań w V2D.2. | 3/5 | Obecne źródła |
| V2D.2 | **Wdrożone:** rzeczywiste trajektorie, podział cykli encji/przerw/skoków, redukcja próbek z zachowaniem ostrych zmian kierunku. Koniec lotu według zgodnego efektu lub końca obserwacji. | 3/5 | V2D.1 |
| V2D.3 | **Wdrożone:** deklarowane okna efektu, łączenie przedziałów bez sumowania czasu, granice śmierci/rundy i brak duration bez fikcyjnego czasu. Pełna faza/intensywność nieustalone. | 3/5 | V2D.1 |
| V2D.4 | **Wdrożone:** cache torów per runda, UI bez surowych trajektorii; flash projektowany tanio z istniejących małych źródeł bez dodatkowego parsera/I/O. Payload z cache po flashu około 0,04–0,09 s lokalnie. | 3/5 | V2D.2–3 |
| V2D.5 | **Wdrożone:** rzuty/loty/ślad oraz biała przerywana obwódka FLASH i status z czasem na liście graczy. Turkusowy wybór gracza, domyślnie włączone warstwy, zdarzenia i cofanie. | 3/5 | V2D.4 |
| V2D.6 | **Częściowo:** testy danych i rzeczywistego JS dla granatów/flasha, kontrola pięciu dem/czterech map bez parsera. Ręczny odbiór wyglądu/FPS pozostaje otwarty. [Wyniki](docs/v2d_projectiles_verification.json). | 3/5 | V2D.1–5 |

Renderer korzysta z tego samego zegara co runda i z profilu tylko do projekcji
oraz poziomów. Brak powiązania nie daje wymyślonej paraboli. Pełna faza flasha
wymaga potwierdzonego źródła; sama animacja `blind_duration` jej nie zastępuje.
Bez migracji dawnych analiz, nowych detektorów taktycznych i integracji LLM.

## M6 — pełny raport coacha przez API

Budujemy na odebranej prezentacji danych M5.6. Model w produkcie wybieramy
na podstawie jakości własnych przykładów, czasu i kosztu. Statystyki liczy kod.

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| M6.1 | Przygotować pakiet zweryfikowanych danych i kontrakt raportu: kontekst, dowody, mocne strony, do 3 priorytetów poprawy, zalecenia i niepewność. Tu przeniesiono próbny feedback z M5.7; po adapterze M6.2 ocenić kilka ograniczonych raportów przed dalszą integracją. | 4/5 | Odbiór M5.6 |
| M6.2 | Dodać usługę API: konfiguracja, sekrety poza repo/logami, timeout, ograniczone retry, limity i ewidencja użycia. Wykorzystać adapter próby, jeśli powstał. | 4/5 | M6.1 |
| M6.3 | Walidować format, liczby, rundy/gracza/stronę, referencje i dopuszczalną pewność. Odrzucać niepopartą odpowiedź lub podejmować ograniczoną próbę naprawy. | 4/5 | M6.1–2 |
| M6.4 | Zapisać wersjonowany raport i dodać generowanie, postęp, odczyt oraz przejście do dowodów. Cache uwzględnia dane, detektory, prompt i model; podwójny klik/rerun nie dubluje kosztu. | 4/5 | M6.2–3 |
| M6.5 | Odebrać całą ścieżkę: E2E z kontrolowaną odpowiedzią, błędy/cache oraz osobny przegląd jakości rzeczywistych raportów. | 4/5 | M6.1–4 |

**Gotowe, gdy:** wybrany zawodnik otrzymuje merytoryczny raport jednego meczu,
każdy wniosek o grze prowadzi do danych, a ponowne otwarcie nie uruchamia API.
Walidacja struktury nie jest gwarancją trafności taktycznej. Ocena brakującego
utility wymaga wyposażenia, czasu i możliwości użycia, które muszą wynikać z dowodów.

## Walidacja, utrzymanie i zakres późniejszy

- **W każdym M2–M6:** niezależne referencje, przypadki negatywne i niepełne dane,
  testy właściwe dla zmiany, odbiór czytelności. W M2/M3 domykamy wizualny odbiór radaru.
  Szerszą walidację reconnect/dogrywki kontynuujemy; niesprawdzonych przypadków
  nie przedstawiamy jako potwierdzonej obsługi. Nowe detektory sprawdzamy na obu mapach.
- **Utrzymanie:** pomiary kilku długości dem i CI z testami/Ruff (dawne A9, 3/5).
  Dalszą kompresję źródeł uruchamiamy według pomiarów (dawne A10, 3/5).
  Korzystamy z M1; historyczne analizy nie wymagają migracji.
- **Później, według potrzeby:** pełniejsze etykiety rush/execute/split/default,
  ocena intencji i jakości gry lurka, silniejsze oceny wsparcia/widoczności,
  kolejne mapy, kalibracja ratingów oraz trendy między meczami. Obserwowany udział
  gracza poza grupą oraz jego powiązanie z atakiem należą już do M4.5/M5.3.
  Te rozszerzenia nie blokują pierwszego raportu o zweryfikowanym zakresie.
- **Dodatkowe źródła warunkowo:** sygnały wykrycia przeciwnika dopiero po
  sprawdzeniu ich dostępności i znaczenia; trafienia pocisków w otoczenie dla
  analizy wymian bez obrażeń; dokładniejsza geometria do ocen widoczności/smoke.
  Kierunek patrzenia i orientacyjny promień smoke'a na radarze nie dowodzą
  widoczności. Te źródła nie blokują M4/M5 i nie uzasadniają same w sobie
  zwiększenia częstotliwości próbkowania.

## Mapowanie starej numeracji

| Poprzednie zadanie | Aktualne miejsce |
| --- | --- |
| M2.1–M2.5 / wcześniejsze MAP2 | M2.1–M2.5, zakres integracji zachowany |
| R3.1 | M3.1–M3.2 |
| R3.2 | M4.3; nie blokuje openingu ani refragów |
| R3.3 | M3.3; pierwszy frag lokalnego epizodu w M4.3 |
| R3.4 | Globalna chronologia M3.3–4; lokalny efekt i następstwa M4.3–4 |
| R3.5 | M4.2–3; istniejące early utility używane już w M3 |
| R3.6 i R5 | Pierwszy widok M3.4, korekty M3.6, wzbogacenie M4.7, dopracowanie M5.6 |
| R3.7 oraz V1/V2 | Referencje i odbiór w każdym etapie od początku pracy |
| R4 | M4.4–6; pełne etykiety strategii pozostają rozszerzeniem |
| R6 | M5.1–6; podstawowe porównania startują po korektach M3 |
| B3-01 / B3-07 | Pakiet i próbny feedback M6.1–2, końcowa ocena M6.5 |
| B3-02 / B3-03 | M6.2 / M6.3 |
| B3-04 / B3-05 | M6.4 |
| B3-06 | M6.5 |
| B5 / kolejne mapy / pełna kalibracja | Późniejsze rozszerzenia po sprawdzeniu analizy jednego meczu |

Numeracja M4/M5 sprzed review z 2026-10-13 jest mapowana poniżej. Starsze opisy
w historii rozmowy/archiwum zachowują historyczne znaczenie; do nowych prac
obowiązuje numeracja w aktualnych tabelach.

| Zadanie przed review | Aktualne miejsce |
| --- | --- |
| M4.1 — grupowanie starć | M4.3; wcześniej wspólny fundament M4.1 |
| M4.2 — efekt walki i utility | M4.2–3 |
| M4.3 — próby ataku | M4.4; zachowanie odłączonych graczy rozwija M4.5 |
| M4.4 — rotacje i retake | M4.6, z opisem aktywności CT |
| M4.5 — integracja i odbiór | M4.7 |
| M5.1 — porównywalne warunki | M5.1 |
| M5.2 — podobne rundy | M5.2–5: podstawy, T, CT, następstwo rund |
| M5.3 — najważniejsze wzorce | M5.6 |
| M5.4 — podsumowanie meczu/gracza | M5.6 |
| M5.5 — próbny LLM | M6.1–2 (dawne M5.7) |

## Najbliższa kolejność wykonania

1. **Odbiór prezentacji M5.6:** przejrzeć nowe widoki T/CT, porównania rund,
   pokrycie i przejścia do radaru, także na Dust2 z M5.D2 i Anubis z M5.AN.
   M5.R1–R3, M5.3–6 oraz integracje obu dodatkowych map są zaimplementowane.
2. **Poprawki wynikające z odbioru M5:** konkretne przykłady błędów danych lub
   nieczytelnego przedstawienia, bez dokładania nowych kategorii detektorów.
   **M5.EX.R1 wykonane:** zgony/reset przed freeze nie zaburzają już aktywnych
   statystyk na Inferno i Anubis. Pozostaje ręczna ocena sensu interpretacji taktycznych.
3. **V2D przed M6:** granaty i oznaczenie deklarowanego efektu flasha wdrożone.
   Dalej ręczny odbiór na czterech mapach. Pełna faza flasha wymaga dodatkowego potwierdzenia.
4. **M6.1–2:** pakiet danych i próbny feedback LLM po odbiorze M5 i epiku V2D.
5. **M6.3–5:** walidacja raportu, zapis/cache i pełna integracja usługi.

**Następny krok: ręczny odbiór granatów i oznaczenia flasha w viewerze (V2D.6).
Odbiór M5.6 pozostaje otwarty.**
M3 i obecna wersja M4 zostały odebrane. LLM nie jest częścią zakończenia M5.
