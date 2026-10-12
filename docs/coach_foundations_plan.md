# E1 — uzupełnienie danych dla analizy taktycznej

Data: 2026-10-12. Status: **wdrożone; odbiór techniczny zakończony**.
Wynik, wersje i pomiary: [dokumentacja wdrożenia](coach_foundations.md).
Niezależny przegląd w grze pozostaje otwartą częścią odbioru E1-08.

## Cel i wynik etapu

Dla każdej rundy Mirage przygotować wspólny, zapisany zestaw danych:
wyposażenie zawodników, zdarzenia bomby, strzały, źródła działania smoke’ów
i ustawienie przed pierwszym potwierdzonym kontaktem. Wszystkie obserwacje
mają czas, pochodzenie oraz informację o brakach. Z tych samych danych będą
korzystały później raport drużyny i raport zawodnika.

Etap kończy się działającym odczytem danych z bazy bez parsera oraz odbiorem
na rzeczywistym demie. Starcia, strategie, rotacje, retake i feedback LLM
pozostają kolejnymi etapami R3–R6.

## Stan wyjściowy przed realizacją E1

- `DemoAnalyzer.get_economy()` istnieje, ale `get_full_analysis()` nie zapisuje
  jego wyniku. Puste ramki po błędzie nie wyjaśniają przyczyny braku danych.
- `annotate_states()` wykorzystuje inventory do ustalenia `has_bomb`, po czym
  usuwa inventory. Pozycje są próbkowane co 6 ticków, dodatkowo w tickach
  obrażeń i zabójstw. Czas zakłada obecnie 64 ticki/s.
- `get_bomb_events()` pobiera tylko plant i defuse. Nosiciel jest dodatkowo
  obserwowany w próbkach pozycji.
- `replay_effects.py` pobiera strzały i wygaśnięcia smoke’ów. Przedziały
  smoke’ów tracą część identyfikatorów źródła; brak wygaśnięcia zastępuje
  szacunek 22 s. Okrąg na radarze jest przybliżeniem wizualnym.
- `tactical_rounds.py` udostępnia pozycje i punkty działania utility, ale
  nie włącza jeszcze strzałów i przedziałów smoke’ów do wspólnych dowodów.
- R2 zapisuje ustawienia po 0/5/10/15 s. Potrzebny jest dodatkowy punkt
  odniesienia przed kontaktem, aby oddzielić przygotowanie od skutków walki.
- SQLite przechowuje podstawową analizę i osobny cache przestrzenny meczu.
  Istnieją stabilne ID dowodów, wersje oraz testy zapisu/odczytu.

## Docelowy kontrakt

Rozszerzamy istniejące `CoachInputs`, `Evidence`, `Availability` i
`Preparation`. Nowy rekord danych rundy grupuje źródła i referencje:

```text
RoundFoundation
  demo_id, round_number, schema_version, source_fingerprint
  clock: freeze_tick, end_tick, tick_rate, time_basis
  equipment_start[]
  equipment_changes[]
  bomb_event_ids[]
  shot_event_ids[]
  utility_lifecycle_ids[]
  contact_references:
    first_enemy_damage
    first_firearm_damage
    first_enemy_kill
    preparation_reference
  setup_before_contact
  source_quality{}
```

`Evidence` pozostaje właścicielem informacji o zdarzeniu. Obserwacje i
raporty odwołują się do niego przez ID; nie nadają mu nowych ID zależnych
od wybranego zawodnika. Strumienie istniejących fragów i obrażeń zachowują
własne źródła. Nowe struktury są rozszerzeniem kontraktu, a nie drugim
niezależnym modelem tych samych akcji.

Każda nowa obserwacja zawiera:

- tick, numer rundy i czas względem freeze-end, jeżeli początek jest znany;
- gracza/drużynę i pozycję, jeżeli źródło je udostępnia;
- źródło, ID rekordu źródłowego oraz ID powiązanych obserwacji;
- pochodzenie wartości: event, próbka, wyliczenie lub oszacowanie;
- status dostępności i brakujące pola; dla próbki także tick oraz jej wiek.

Diagnostyka rozdziela wynik odczytu (`ok`, `not_listed`, `unsupported`, `error`,
`not_loaded`) od kompletności danych rundy. Poprawny, pusty odczyt może
potwierdzić zero tylko w sprawdzonym zakresie obsługi źródła. Sama
nieobecność nazwy w liście eventów nie dowodzi obsługi ani zera zdarzeń.
Historyczne puste ramki zachowują status nieznany. Nie używamy zera jako
zamiennika brakującego stanu inventory, wyposażenia lub ekonomii.

## Zadania

Złożoność: 1/5 — mała, 5/5 — duża niepewność lub wiele zależności.
Wszystkie zadania należą do bieżącego priorytetu P0.

| ID | Zadanie | Złożoność | Zależności |
| --- | --- | --- | --- |
| E1-01 | Zweryfikować źródła na rzeczywistym Mirage | 2/5 | — |
| E1-02 | Rozszerzyć kontrakt danych i diagnostykę | 3/5 | E1-01 |
| E1-03 | Pozyskiwać wyposażenie i ekonomię | 4/5 | E1-02 |
| E1-04 | Uzupełnić zdarzenia bomby | 3/5 | E1-02 |
| E1-05 | Włączyć strzały i cykl życia utility do dowodów | 4/5 | E1-02 |
| E1-06 | Dodać ustawienie przed pierwszym kontaktem | 3/5 | E1-02 |
| E1-07 | Zintegrować zapis, cache i aktualizację starych analiz | 4/5 | E1-03–06 |
| E1-08 | Zweryfikować całość na referencjach i realnym demie | 3/5 | E1-07; referencje od E1-01 |

### E1-01 — weryfikacja źródeł

**Prace:**

1. Na dostarczonym Mirage sprawdzić eventy i mały zestaw ticków: freeze-end,
   obrażenia, plant/defuse, użycie utility, śmierć nosiciela bomby.
2. Zweryfikować pola inventory, broni, pancerza, hełmu, zestawu do defuse,
   ekonomii i identyfikatorów granatów. Nazwy nowych właściwości oraz ich
   semantykę potwierdzić w zainstalowanym parserze i wynikach odczytu.
3. Sprawdzić kandydatów zdarzeń: drop/pickup bomby, begin/abort plant,
   begin/abort defuse, eksplozja, rzuty granatów i zakończenie ognia.
   Lista kandydatów nie oznacza jeszcze gwarancji ich dostępności.
4. Sprawdzić podstawę przeliczenia czasu; zachować jawne założenie 64 ticki/s,
   jeżeli plik/parser nie daje zweryfikowanej alternatywy.
5. Zapisać tabelę: źródło, obsługa, dostępne pola, zakres, przykładowe rekordy,
   ograniczenia. Wybrać małe fragmenty do dalszych referencji.

**Odbiór:** dla każdego planowanego pola znamy źródło albo mamy jawnie
opisany brak. Potwierdzamy jednostki i znaczenie odczytywanych wartości.
Kosztownego pełnego parsowania nie powtarzamy dla każdego pola osobno.

### E1-02 — kontrakt i jakość źródeł

**Prace:**

1. Dodać modele danych rundy, wyposażenia oraz cyklu życia granatu.
2. Ujednolicić manifest źródeł i dostępność per runda/per pole.
3. Rozszerzyć stabilne ID i walidację referencji na nowe strumienie.
4. Określić wersje kontraktu, ekstrakcji oraz reguły odczytu starszych rekordów.
5. Zachować kolejność wewnątrz źródła. Zdarzenia z różnych źródeł w tym samym
   ticku mają nieznaną kolejność przyczynową.

**Pliki:** `src/models/tactical.py`, `src/demos/coach_data.py`,
`src/demos/tactical_rounds.py`, `src/demos/versions.py`.

**Odbiór:** zapis/odczyt zachowuje wartości i referencje; brak źródła,
potwierdzony brak zdarzeń i niewykonana analiza dają różne stany. Znaczniki
gotowości danych nie deklarują wdrożenia detektorów walk lub retake’u.

### E1-03 — wyposażenie i ekonomia

**Prace:**

1. Włączyć wynik `get_economy()` do przygotowania danych coacha. Snapshot
   początkowy przypisać do freeze-end oraz poprawnego składu i strony.
2. Pobierać zweryfikowane w E1-01 pola: posiadane bronie i granaty z liczbą
   sztuk, broń aktywną, pancerz, hełm, defuse kit, pieniądze i wartość sprzętu.
3. Zachować inventory przed usunięciem go z ramki pozycji. Zapisywać stan
   początkowy i zaobserwowane zmiany, z pokryciem próbek oraz przerwami.
   Rzadkie pola ekonomii pobierać w potrzebnych tickach, nie dla każdej klatki.
4. Udostępnić stan zawodnika dla wskazanego ticka wraz z wiekiem, zakresem
   pokrycia i brakami. Granice tolerancji określić w konfiguracji kontraktu.
5. Rozdzielić opcjonalne grupy właściwości: brak jednego pola nie może
   usuwać poprawnie odczytanych pozycji, inventory lub pozostałego wyposażenia.

Zmiana inventory między próbkami oznacza zmianę zaobserwowanego stanu.
Dokładny moment rzutu, podniesienia lub upuszczenia wymaga właściwego eventu.
Broń aktywna nie zastępuje pełnej listy posiadanych broni.

**Pliki:** `src/demos/demo_analyzer.py`, `src/demos/mirage_context.py`,
modele z E1-02; pomocniczy moduł ekstrakcji wyposażenia, jeżeli ograniczy
rozrost obecnych plików.

**Odbiór:** na wybranych zawodnikach zgadzają się stan początkowy, dwie
sztuki flasha, użycie/zmiana granatu oraz dostępność kitu/pancerza. Braki
zostają brakami. Nie ma kopiowania pełnego inventory do każdego raportu.

### E1-04 — zdarzenia bomby

**Prace:**

1. Zachować plant i defuse, dodać zdarzenia potwierdzone w E1-01.
2. Normalizować numer rundy, tick, gracza, stronę, site i pozycję, zachowując
   nieznane wartości oraz oryginalny typ eventu.
3. Udostępnić jedną chronologię bomby z odnośnikami do jej nosiciela
   w próbkach pozycji. Rozbieżności eventów i próbek oznaczać diagnostyką.
4. Oznaczyć zakończenie przez eksplozję osobno jako event lub wniosek z
   przyczyny końca rundy. Drugi wariant nie dostaje zmyślonego ticka eksplozji.
5. Wyeliminować duplikaty plant/defuse podczas łączenia podstawowej analizy
   z nowym rozszerzeniem danych.

**Pliki:** `src/demos/demo_analyzer.py`, `src/demos/coach_data.py`,
`src/demos/tactical_rounds.py`.

**Odbiór:** można odtworzyć dostępne zdarzenia nosiciela, plantu i rozbrojenia
w poprawnej rundzie. Brak abort lub pickup nie powoduje dopisania fikcyjnego
zdarzenia. Ten task dostarcza fakty do późniejszego detektora retake’u.

### E1-05 — strzały i utility we wspólnych dowodach

**Prace:**

1. Włączyć istniejące `weapon_fire` do adaptera taktycznego: gracz, broń,
   tick, pozycja i kierunek. Zachować filtr przedmiotów innych niż broń palna.
2. Zachować oryginalne identyfikatory oraz dowody detonacji i wygaśnięcia
   smoke’a, jego autora, pozycję oraz sposób dopasowania eventów.
3. Rozdzielić rzeczywisty czas wygaśnięcia, koniec przedziału widocznego
   w rundzie i oszacowanie stosowane przez radar. Oszacowanie 22 s nie staje
   się potwierdzonym czasem działania w analizie taktycznej.
4. Dodać rekord cyklu życia utility: `throw_tick`, `effect_tick`,
   `end_tick`, `thrower_id`, `kind`, pozycje i referencje źródeł. Pola
   niedostępne pozostają puste. Łączenie przede wszystkim po identyfikatorach,
   z kontrolą ponownego użycia entity ID oraz zgodności czasu i miejsca.
5. Wykorzystać istniejące trajektorie tylko tam, gdzie pomagają wiarygodnie
   połączyć rzut z efektem. Wynik niejednoznaczny zachowuje osobne obserwacje.
6. Rozdzielić w R2 granaty rzucone w 0–10/0–15 s od granatów działających
   w tych oknach. Granat rzucony w 14 s, działający w 16 s ma dwa różne czasy.

**Pliki:** `src/demos/replay_effects.py`, `src/demos/mirage_context.py`,
`src/demos/early_round.py`, `src/demos/tactical_rounds.py`.

**Odbiór:** radar i coach wskazują te same źródłowe strzały/smoke’y.
Pewność dopasowania i szacowane wygaśnięcia przechodzą przez zapis/odczyt.
Sam strzał nie jest kontaktem z rozpoznanym wrogiem, a wizualny promień
smoke’a nie jest dowodem blokady widoczności.

### E1-06 — ustawienie przed pierwszym kontaktem

**Prace:**

1. Z istniejących obrażeń i fragów wyznaczyć osobne odniesienia: pierwsze
   dodatnie obrażenia przeciwnika, pierwsze obrażenia od broni palnej oraz
   pierwszy frag przeciwnika. Friendly fire, self i world nie inicjują tego
   punktu odniesienia. Zachować utility jako odrębny typ obrażeń.
2. Dla przygotowania wybrać najwcześniejsze potwierdzone zdarzenie obrażeń
   lub zabójstwa przeciwnika. Wskazać jego rodzaj i ograniczenia źródeł.
3. Dobrać ostatnie świeże pozycje T/CT o ticku ściśle mniejszym od kontaktu.
   Przy nowej ekstrakcji dodać potrzebny tick poprzedzający event do wspólnej
   listy próbek. Nie uruchamiać osobnego parsera dla każdego zawodnika.
4. Zachować rozdzielenie A, B, mid i stref wsparcia, nosiciela bomby oraz
   liczbę brakujących zawodników. Dla brakujących/starych próbek zwrócić
   częściowe lub nieznane ustawienie; nie używać próbki po kontakcie.
5. Zachować snapshoty 0/5/10/15 s z ich czasem i dodać referencję do nowego
   ustawienia w `Preparation`. Późniejszy kontakt może powstać przed końcem
   okna early round; te dwa zakresy mogą się nakładać.

**Pliki:** `src/demos/early_round.py`, `src/demos/mirage_context.py`,
`src/models/tactical.py`, adapter taktyczny. Pełne grupowanie starć zostaje R3.

**Odbiór:** poprawne przykłady kontaktu przed 5 s, obrażeń od HE przed pierwszym
trafieniem z broni, braku obrażeń przy zarejestrowanym fragu i braku kontaktu.
Gdy źródło jest częściowe, wynik jest pierwszym zaobserwowanym kontaktem,
ze wskazaniem ograniczenia. Brak wcześniejszej próbki nie daje ustawienia
z przyszłości.

### E1-07 — baza, cache i ścieżka aktualizacji

**Prace:**

1. Dodać addytywną migrację SQLite: manifest rozszerzenia per demo oraz
   kompaktowe dane wejściowe per runda. Proponowane tabele:
   `demo_coach_enrichment` i `demo_coach_round_inputs`; klucz drugiej to
   `(demo_id, round_number)`, indeks i powiązanie z katalogiem dem.
2. W manifeście zapisać wersje schematu/ekstrakcji, fingerprint źródeł,
   ustawienia próbkowania, podstawę czasu i diagnostykę. W rekordzie rundy
   zapisać nowe strumienie i referencje do istniejących źródeł.
3. Dodać usługę przygotowania danych dla całego meczu. Nowe dane pozyskuje
   jednym wspólnym przebiegiem przygotowania; poszczególne odczyty parsera
   grupuje według wymaganych źródeł i ticków. Wykorzystuje aktualny cache.
4. Zachować osobną funkcję samego odczytu bez parsera i zapisów do bazy.
   Adapter taktyczny łączy bazowe ramki, kontekst przestrzenny i rozszerzenie.
5. Zapis manifestu oraz rund wykonać atomowo. Ponowne przygotowanie jest
   idempotentne. Nieudana aktualizacja nie publikuje części nowego zestawu
   jako aktualnego; poprzedni zapis pozostaje dostępny ze swoją wersją.
6. Dla starego dema pokazać stan „dane coacha wymagają uzupełnienia”.
   Przygotowanie wykonuje istniejąca akcja przygotowania kontekstu;
   bez pliku źródłowego działa odczyt posiadanych danych z listą braków.
7. Unieważniać zależne wyniki przy zmianie źródeł/wersji. Usunięcie dema
   usuwa jego rozszerzenie. Ekstrakcja jest wspólna dla wszystkich graczy;
   rerun Streamlit i zmiana zawodnika nie powodują ponownego parsowania.

**Pliki:** `src/storage/database.py`, `src/demos/spatial_service.py`,
`src/demos/tactical_rounds.py`, `src/gui/mirage_view.py`; niewielka usługa
przygotowania danych coacha wydzielona z UI.

W tym etapie pozycje mogą pozostać w dotychczasowym cache przestrzennym.
Nowa tabela rund nie kopiuje całej macierzy pozycji ani pełnych trajektorii.
Ewentualny podział ciężkiego cache pozycji na rundy wymaga osobnego pomiaru
i zadania. Radar zachowuje format prezentacji; jego dane oraz analityczne
dowody pochodzą ze wspólnej ekstrakcji i spójnych wersji źródeł.

**Odbiór:** migracja zachowuje mecze i śledzonych graczy; odczyt jednej rundy
rozszerzenia nie ładuje wszystkich jego rund. Ponowny odczyt i zmiana gracza
wykonują zero odczytów parsera. Starszych danych nie przedstawiamy jako
spełniających nowy kontrakt. Dokładnej oszczędności czasu nie deklarujemy
przed pomiarem.

### E1-08 — referencje i odbiór

**Prace i wymagane przypadki:**

- Kontrakt: zachowanie dużych SteamID jako stringów, stabilność ID po
  SQLite/JSON, null kontra zero, błędy pojedynczych opcjonalnych źródeł.
- Wyposażenie: snapshot na freeze-end, liczba granatów, zmiana inventory,
  brak gracza/przerwa próbek, śmierć, kit oraz pancerz, jeżeli obsługiwane.
- Bomba: dostępne warianty plant/defuse/eksplozji, zmiana nosiciela,
  zdarzenia blisko końca rundy i niepełny strumień.
- Utility: nakładające się smoke’i, ponowne użycie entity ID, wygaśnięcie
  po końcu rundy, brak expiry, dwa granaty tego samego typu oraz granice
  okien 10/15 s. Osobno rzut i zadziałanie.
- Ustawienie: bardzo wczesny kontakt, utility przed strzałami, zdarzenia
  w jednym ticku, brak świeżej pozycji i runda bez kontaktu.
- Integracja: rzeczywiste Mirage → przygotowanie → zapis do tymczasowej
  bazy → ponowny odczyt → wybór innego zawodnika; parser zablokowany podczas
  ciepłego odczytu. Nie używać produkcyjnej bazy do testów migracji.
- Regresja radaru: te same źródłowe strzały, czasy smoke’ów i dotychczasowe
  sterowanie po uzupełnieniu kontraktu.
- Pomiary: czas dodatkowej ekstrakcji, czas odczytu cache, liczba wywołań
  parsera, rozmiar dodatkowych danych oraz szczyt pamięci względem bazowego
  przebiegu na tym samym demie. Wyniki zapisać w protokole odbioru.

Referencje źródłowe mają ręcznie zapisane oczekiwania niezależne od wyniku
nowego kodu. Wybrane momenty należy obejrzeć na replayu. Jeśli dane z dema
nie zawierają danego przypadku, test syntetyczny nie jest przedstawiany
jako jego walidacja na realnym meczu.

**Pliki:** istniejące testy `test_coach_data.py`, `test_tactical_rounds.py`,
`test_mirage_context.py`, `test_replay_effects.py`, `test_early_round.py`,
`test_database.py`, `test_real_demo_e2e.py` oraz małe fixture’y referencyjne.

**Odbiór końcowy:** dla wybranej rundy umiemy wskazać wyposażenie na starcie,
dostępne zdarzenia bomby, autorów i czasy strzałów/utility oraz ustawienie
przed kontaktem. Każda odpowiedź prowadzi do źródła, a braki pozostają jawne.
Powtórny odczyt nie wymaga parsera ani API.

## Kolejność wdrożenia i porcje zmian

1. **Źródła i kontrakt:** E1-01 → E1-02. Zatwierdzić faktycznie dostępne
   pola i oczekiwania referencyjne przed rozbudową ekstrakcji.
2. **Zbieranie danych:** E1-03 → E1-04 → E1-05 → E1-06. Zadania po E1-02
   są logicznie niezależne, lecz dotykają wspólnych adapterów; wdrażać małymi
   porcjami z testami odpowiednich źródeł, bez równoczesnych zmian tych plików.
3. **Zapis i aktualizacja:** E1-07. Kształt migracji ustalić w E1-02,
   implementację zapisu połączyć z gotowymi modelami źródeł.
4. **Odbiór etapu:** E1-08. Referencje i testy powstają od początku;
   na końcu uruchomić pełną ścieżkę integracyjną i zapisać pomiary.

Aktualizacja kolejności po odbiorze E1 i M1: najpierw M2 — integracja drugiej
mapy, następnie M3 — chronologia i podsumowanie rundy oraz M4 — lokalne starcia
i przebieg ataku. Dane E1 dostarczają kontekstu wyposażenia, utility i ustawienia
przed kontaktem bez dodatkowego parsowania dla gracza. Obowiązujący plan
i mapowanie dawnych zadań: [roadmapa](../ROADMAP.md).
