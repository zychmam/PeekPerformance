# PeekPerformance — roadmap

Aktualizacja: **2026-10-12, po technicznej integracji Inferno w M2**.
Etapy mają jedną numerację **M2 → M3 → M4 → M5 → M6**.
Ukończone R1/R2, E1 i M1 zachowują historyczne identyfikatory.
Mapowanie poprzednich zadań znajduje się na końcu; [archiwum](docs/roadmap_history.md)
zachowuje wcześniejsze plany i przypisania modeli. Ten plik określa aktualne priorytety.

## Cel i sposób oceny postępu

Wirtualny coach CS2 ma wyjaśniać **jeden konkretny mecz z dema** poprzez przebieg
rund, podobieństwa i różnice między nimi oraz wnioski przydatne zawodnikowi i drużynie.
Pierwszą mapą jest Mirage; druga sprawdzi uniwersalność silnika przed dalszą analizą.

Każdy etap rozwija ten sam ciąg:

**Warunki rundy → działania obu stron → istotne zmiany sytuacji → zakończenie
→ porównanie z podobnymi rundami → wniosek.**

- **Drużyny:** ustawienie T/CT, utility w pierwszych 10–15 s, inicjacja walki,
  opening/refragi w 10 s, rezultat, wejście/plant, reakcje CT i próba retake.
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
| Gracze i ekran meczu | Śledzenie uczestników dema, historia i przybliżony rating, nicki, kompaktowy przegląd, rundy/walka/utility/ekonomia, eksport CSV/Excel. |
| R1 — model taktyczny | Wspólne dowody, ID, zegar, drużyny/strony, statusy kompletności i modele przyszłych epizodów. Referencje bazowe gotowe, pokrycie taktyczne częściowe. |
| R2 — przygotowanie | Snapshoty 0/5/10/15 s i przed kontaktem, early utility, przejścia, kierunki T, ustawienia 5/4+1, kierunek bomby i wysunięte CT. |
| Wejścia na site | Potwierdzone przejścia T, kierunki, uczestnicy w oknie 8 s, CT przed/podczas, nosiciel i wcześniejsze utility. Pełna próba ataku pozostaje do rozpoznania. |
| E1 — fundamenty coacha | Wyposażenie, ekonomia, chronologia bomby, strzały, rzuty/cykl utility i ustawienie przed kontaktem, wraz z dowodami i brakami. |
| Radar | Animacja około 0,1 s (6 ticków przy 64 Hz), sterowanie odtwarzaniem, wygładzenie, aktywne smoke'y i błyski strzałów. Mapa na górze analizy. |
| M1 / A1–A8 | Wdrożone obserwacje niezależne od mapy, profile, resolver, indeksy, podłączenie obecnych detektorów, cache etapami/per runda i UI sterowane profilem. |
| M2 — Inferno | Profil drugiej rzeczywistej mapy, radar, referencje i izolowany odbiór przepływu na 20 rundach; ręczny przegląd replayu/UI otwarty. |

Stack: Python 3.11+, Streamlit, `demoparser2`, pandas, Plotly, SQLite, openpyxl.
Mirage i Inferno mają przygotowane profile rzeczywistych map; profil syntetyczny służy testom.
Nowe detektory starć, rotacji/retake i raport LLM **nie są jeszcze wdrożone**.

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

M2 ma techniczną integrację i otwarty ręczny odbiór taktyczny/UI. M3–M6 są
**zaplanowane, do wykonania**. Złożoność zadań: 1–5.
Weryfikacja rusza od początku każdego etapu, mimo że odbiór jest jego ostatnim zadaniem.

| Etap | Rezultat użytkowy / techniczny | Warunek rozpoczęcia |
| --- | --- | --- |
| **M2 — druga mapa** | Technicznie działa na Mirage i Inferno przez wspólny silnik; ręczny odbiór otwarty. | M1 ukończone; demo Inferno wybrane. |
| **M3 — czytelny przebieg rundy** | Pierwsze kompletne podsumowanie faktów dla drużyn i zawodnika, od startu do zakończenia. | Odbiór M2. |
| **M4 — starcia i przebieg ataku** | Podsumowanie wzbogacone o lokalne walki, efekty utility, próby ataku, rotacje i retake. | Działający opis rundy M3. |
| **M5 — wzorce i wnioski z meczu** | Porównanie podobnych rund, priorytetowe obserwacje i próbny feedback LLM. | Pierwsze opisy M3 pozwalają rozpocząć porównania; wyniki M4 są dołączane stopniowo. |
| **M6 — pełny raport coacha** | Zweryfikowany raport przez API, zapis, ponowne otwarcie i nawigacja do dowodów. | Sprawdzone dane oraz użyteczny próbny feedback z M5. |

M5 rozpoczynamy od podstawowych obserwacji, gdy M4 jest jeszcze rozwijane.
Pierwszy raport nie czeka na pełny słownik strategii ani ocenę wszystkich decyzji.

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

Szczegółowa dekompozycja **M3.1a–M3.5b**, układ podsumowania drużyn/gracza,
kontrakty, wydajność i kryteria odbioru:
[plan podsumowania rundy M3](docs/m3_round_summary_plan.md).

M3.1a–c wykonane: [audyt i osiem rund referencyjnych](docs/m3_reference_rounds.md),
kontrakt kontaktu/odpowiedzi/liczebności/momentu oraz walidacja. Kolejny krok: M3.2a.

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| M3.1 | Ustalić minimalny rekord przebiegu i przykłady oczekiwanych podsumowań. Dołączyć istniejące warunki startu: wyposażenie/ekonomię, strony, czas i jakość danych. | 3/5 | M2 |
| M3.2 | Uporządkować kontakty: czas, uczestnicy, obie pozycje; osobno pierwsze obrażenia utility i pierwszy kontakt ogniowy. | 3/5 | M3.1 |
| M3.3 | Obliczyć opening rundy, refragi/odpowiedź w 10 s i zmiany globalnej liczebności. Refrag wymaga zabicia dokładnego zabójcy kolegi; ratingowy trade 5 s pozostaje osobny. | 4/5 | M3.2; bez segmentacji |
| M3.4 | Złożyć oś od przygotowania przez kontakty, wymiany i istniejące wejścia/plant do zakończenia. Pokazać krótkie podsumowania drużyn/gracza i dowody na jednym radarze. | 4/5 | M3.1–3; widok rozwijany od pierwszych wyników |
| M3.5 | Sprawdzić całe wyjaśnienia wybranych rund na obu mapach, referencje, granice 10 s, brakujące dane, cache i zmianę gracza. | 3/5 | Referencje od M3.1; odbiór po M3.4 |

**Gotowe, gdy:** użytkownik rozumie warunki startu, działania stron, pierwszą
wymianę, istotne zmiany przewagi i zakończenie. Każdy opis ma dowody. Widok gracza
pokazuje jego udział w tej samej chronologii. Nieznany wynik kontaktu pozostaje
nieznany; brak fraga nie oznacza przegranego pojedynku. Próby retake/rotacje
pozostają niewyliczone do M4, a zaobserwowany plant/defuse nadal są widoczne.

## M4 — lokalne starcia i przebieg ataku

Wzbogacamy działające podsumowanie M3. Opisujemy uczestników, miejsca, tempo,
utility, reakcję obrony i rezultat. Etykiety rush/execute/split są późniejszym
skrótem tych obserwacji i nie stanowią warunku odbioru etapu.

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| M4.1 | Grupować kontakty w lokalne starcia: rozdzielać równoległe miejsca, zachować kontakt bez fraga i niepewną lokalizację; określić pierwszy frag epizodu. | 5/5 | M3.2–3 |
| M4.2 | Opisać lokalny/globalny efekt walki oraz utility: HP, straty, uczestników i potwierdzone efekty flash/HE/ognia. Bliskość czasowa/przestrzenna pozostaje osobnym kontekstem. | 4/5 | M4.1 i dane E1 |
| M4.3 | Powiązać walki z wejściami, plantem i próbami ataku: miejsce, uczestnicy, podejścia, tempo, zatrzymanie/zmiana kierunku oraz wynik. Uwzględnić próby bez wejścia, z jawnymi kryteriami i niepewnością. | 5/5 | M4.1–2 i istniejące wejścia/bomba |
| M4.4 | Rozpoznać obserwowane rotacje CT oraz próby i wynik retake. Czas reakcji odnosić do nazwanego sygnału z danych, np. kontaktu lub planta; bez zakładania momentu zauważenia lub voice comms. | 5/5 | M4.3; szczegółowe definicje przed implementacją |
| M4.5 | Dołączać wyniki do istniejących podsumowań i odebrać je na obu mapach: nieudane próby, luki, równoległe walki, wycofanie i brak potwierdzonego retake. | 4/5 | Weryfikacja od M4.1, końcowy odbiór po M4.4 |

**Gotowe, gdy:** opis wyjaśnia obserwowany przebieg starć i realizacji celu rundy,
oddziela próbę od wyniku i pozwala sprawdzić źródła. „Po walce nastąpił plant”
nie staje się automatycznie twierdzeniem o przyczynie zwycięstwa. Nie wymuszamy
etykiety strategii ani przypisania każdego ruchu do zamiaru.

## M5 — relacje między rundami i wnioski z jednego meczu

M5.1–3 zaczynamy na zweryfikowanych wynikach M3 podczas rozwoju M4.
Porównania korzystają z dostępnych obserwacji i jawnych mianowników;
analizy wymagające nowych detektorów dochodzą po ich odbiorze.

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| M5.1 | Ustalić porównywalne warunki rund: drużyna/strona, dostępne wyposażenie/ekonomia, czas i liczebność w analizowanym momencie. Uwzględnić wynik poprzedniej rundy i obserwowany zachowany sprzęt tam, gdzie źródła to potwierdzają. | 3/5 | M3 i istniejące E1 |
| M5.2 | Grupować podobne rundy według obserwacji: ustawienia, kierunku/czasu wejścia, użycia utility i wymian. Porównać przebieg i wyniki; podać próby, pokrycie i różnice warunków. | 4/5 | M5.1; próby ataku/rotacje/retake po odpowiednich zadaniach M4 |
| M5.3 | Wybrać kilka najważniejszych powtórzeń i wyjątków: wykorzystanie/utrata przewagi, skuteczne/nieskuteczne wejścia i obrona. Każdy wniosek ma zakres, licznik/mianownik, rundy i ograniczenia; powiązane zdarzenia nie są niezależnymi dowodami. | 4/5 | M5.2; aktualizowane wraz z M4 |
| M5.4 | Złożyć podsumowanie meczu i profil zawodnika z tych samych wyników: pozycje CT, miejsca kontaktów/entry po T, utility oraz kończenie rund. Dopracować istniejące podsumowania rund według ich użyteczności. | 3/5 | M5.2–3; istniejący profil pozycji |
| M5.5 | Przygotować ograniczony pakiet dowodów i kilka próbnych raportów LLM. Sprawdzić liczby, źródła, trafność oraz konkretność feedbacku przed budową pełnej obsługi raportów. | 4/5 | Zweryfikowane M5.3; bez oczekiwania na wszystkie klasyfikacje M4 |

**Gotowe, gdy:** mecz ma kilka uzasadnionych obserwacji o powtarzających się
sytuacjach i ich rezultatach, a próbny feedback jest użyteczny. Jedna sytuacja
nie staje się nawykiem. Bez detekcji wszystkich prób podajemy skuteczność
zaobserwowanych wejść, nie całych ataków. 4+1, potwierdzony lurk i wykorzystanie
lurka to odrębne twierdzenia. Przy małej próbie wynik pozostaje opisem tego meczu.

Próba LLM służy wczesnej ocenie, czy dane wystarczają do feedbacku. Ma jawny
zakres danych i limit wywołań/kosztu. Wykryte luki kierujemy do konkretnej
obserwacji lub reguły; nie rozbudowujemy parsera bez uzasadnionej potrzeby.

## M6 — pełny raport coacha przez API

Budujemy na ocenionym pakiecie i formacie z M5.5. Model w produkcie wybieramy
na podstawie jakości własnych przykładów, czasu i kosztu. Statystyki liczy kod.

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| M6.1 | Utrwalić kontrakt pakietu i raportu: kontekst, wybrane dowody, mocne strony, do 3 priorytetów poprawy, zalecenia i niepewność. | 3/5 | Wyniki próby M5.5 |
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
  rozpoznanie roli lurka i jego wykorzystania, silniejsze oceny wsparcia/widoczności,
  kolejne mapy, kalibracja ratingów oraz trendy między meczami.
  Te rozszerzenia nie blokują pierwszego raportu o zweryfikowanym zakresie.

## Mapowanie starej numeracji

| Poprzednie zadanie | Aktualne miejsce |
| --- | --- |
| M2.1–M2.5 / wcześniejsze MAP2 | M2.1–M2.5, zakres integracji zachowany |
| R3.1 | M3.1–M3.2 |
| R3.2 | M4.1; nie blokuje openingu ani refragów |
| R3.3 | M3.3; pierwszy frag lokalnego epizodu w M4.1 |
| R3.4 | Globalna chronologia M3.3–4; lokalny efekt i następstwa M4.2–3 |
| R3.5 | M4.2; istniejące early utility używane już w M3 |
| R3.6 i R5 | Pierwszy widok M3.4, wzbogacenie M4.5, dopracowanie M5.4 |
| R3.7 oraz V1/V2 | Referencje i odbiór w każdym etapie od początku pracy |
| R4 | M4.3–4; pełne etykiety strategii pozostają rozszerzeniem |
| R6 | M5.1–4; podstawowe porównania startują po M3 |
| B3-01 / B3-07 | Wczesna próba M5.5, kontrakt M6.1 i końcowa ocena M6.5 |
| B3-02 / B3-03 | M6.2 / M6.3 |
| B3-04 / B3-05 | M6.4 |
| B3-06 | M6.5 |
| B5 / kolejne mapy / pełna kalibracja | Późniejsze rozszerzenia po sprawdzeniu analizy jednego meczu |

**M2: podstawowa integracja Inferno wykonana technicznie** na demie
`1-57640da7-9cd0-4aca-890f-4c82c1344eee-1-1.dem.zst`.
Profil, radar, referencje i wyniki: [raport M2](docs/inferno_m2.md).
Ręczny odbiór taktyczny replayu i widoku Streamlit pozostaje otwarty.
Następne zadanie po odbiorze: M3.1 — rekord przebiegu rundy i przykłady podsumowań.
Pierwszy rezultat produktowy po integracji: zrozumiała runda w M3.
Pierwszy pełny kamień milowy coacha: sprawdzalny raport jednego meczu w M6.
