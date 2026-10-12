# M3 — czytelne podsumowanie przebiegu rundy

Status: M3.1a–c wykonane; detektory M3.2+ pozostają do implementacji. Dawne R3;
aktualna numeracja i zakres: [roadmapa](../ROADMAP.md).
Audyt źródeł, osiem rund referencyjnych i szkic wynikowego widoku:
[referencje M3.1](m3_reference_rounds.md). Kontrakt i testy: `src/models/tactical.py`,
`tests/test_m3_contract.py`.
Plan oparty na obecnych kontraktach i widokach aplikacji. M2 ma profil Inferno
i testy techniczne; przed odbiorem M3 trzeba również sprawdzić radar i pozycje
na rzeczywistych rundach Mirage oraz Inferno w uruchomionej aplikacji.

## Efekt dla użytkownika

Po wybraniu rundy użytkownik w kilkanaście sekund rozumie: jak strony zaczęły,
gdzie nastąpił kontakt, jak zmieniała się przewaga, czy T weszli na site i
podłożyli bombę oraz jak zakończyła się runda. Po wybraniu gracza widzi jego
udział w tej samej historii. Każde istotne twierdzenie prowadzi do dowodu.

M3 daje opis faktów i prostych relacji czasowych. Ocena jakości decyzji,
przypisywanie przyczyn zwycięstwa i zalecenia coacha wymagają kolejnych etapów.
Opisy powstają lokalnie z reguł i szablonów, bez wywołania LLM.

## Co już istnieje i czego wymaga M3

| Obszar | Dostępne obecnie | Praca w M3 |
| --- | --- | --- |
| Warunki rundy | Zegar, strony, roster, wynik, wyposażenie, zaobserwowana ekonomia i jakość źródeł | Zwięzły opis startu; niepełne wyposażenie nie daje pewnej etykiety zakupu |
| Przygotowanie T/CT | Snapshoty 0/5/10/15 s i przed kontaktem, orientacja T, wczesne przejścia/aktywność CT, early utility | Selekcja najważniejszych faktów, jawny czas pomiaru, brak podwójnego liczenia obrońców |
| Kontakty | Obrażenia, fragi, referencje pierwszych zdarzeń, próbki pozycji | Wspólny rekord z obiema pozycjami; osobno obrażenia utility i ogniowe; pierwszy własny kontakt gracza |
| Zmiany sytuacji | Surowe zgony, obrażenia, roster i stan życia | Opening, odpowiedzi/refragi 10 s, przebieg liczebności z kontrolą kompletności |
| Wejście i bomba | Potwierdzone wejścia z uczestnikami/kierunkami, stan CT przy wejściu, plant/defuse/wybuch i zdarzenia nosiciela | Połączenie na jednej osi; wejście nie jest automatycznie rozpoznaną próbą ataku |
| Gracz | Pozycje, wyposażenie, rzuty, obrażenia, fragi, śmierć i aktywność przy bombie | Podsumowanie pojedynczej rundy zamiast tabeli pozycji z całej mapy |
| Prezentacja | Radar z odtwarzaniem, smoki/strzały, panele early i wejść, tabele dowodów | Jeden widok z krótkim opisem, wyborem momentu i szczegółami na żądanie |

Istnienie pola `Fight`, `Rotation` czy `Retake` w kontrakcie nie oznacza
działającej detekcji. Obecne flagi dostępności wejściowych źródeł również tego
nie potwierdzają. W M3 te analizy nadal mają status `not_evaluated`.

## Układ ekranu

1. **Nagłówek:** numer rundy, strony drużyn, wynik, czytelny powód zakończenia,
   czas od końca freeze time. Przykład: „Runda 7 · wygrana T · wybuch bomby”.
   Istotna luka w danych jest widoczna przy opisie, diagnostyka pod rozwinięciem.
2. **Radar na górze:** zachowujemy obecne odtwarzanie i wybór czasu. Pod nim
   krótki wybór momentów: start, pierwszy kontakt, opening, wejście, plant,
   zakończenie — tylko momenty faktycznie dostępne. Wybór ustawia radar około
   2 s przed zdarzeniem; czas jest ograniczony granicami rundy.
3. **Przełącznik „Drużyny / Gracz”**, w drugim widoku wybór nicku. Jeden radar
   zachowuje wybrany czas przy zmianie perspektywy i wyróżnia wybranego gracza.
4. **„Przebieg w skrócie”:** 3–4 krótkie zdania, zwykle do około 90 słów.
   Każda fraza oparta na danych ma powiązanie z czasem i dowodami. Nie wypełniamy
   limitu ogólnikami, jeżeli runda ma mało zdarzeń.
5. **Trzy rozwijane części:** „Początek”, „Kontakt i zmiany sytuacji”,
   „Wejście, bomba i zakończenie”. Ich nagłówki zawierają po jednym zdaniu
   podsumowania. W widoku gracza: „Początek”, „Udział w rundzie”, „Zakończenie”.
6. **Pełna oś i dowody:** kompaktowa tabela `Czas | Zdarzenie | Miejsce |
   Stan T:CT`, z wyborem wiersza prowadzącym do radaru. Domyślnie kilka
   najważniejszych momentów; wszystkie istotne zdarzenia i źródła dostępne
   po rozwinięciu. XYZ, ticki i identyfikatory techniczne tylko w diagnostyce.

Nie dokładamy osobnych tabel powtarzających opening, rzuty czy wynik w kilku
panelach. Dane liczbowe trafiają do zdania lub szczegółów właściwego momentu.
Na małym ekranie ustawienie T i CT układamy pionowo. UI pokazuje nicki;
identyfikatory graczy pozostają wewnętrznym kluczem danych.

## Treść perspektywy drużynowej

| Część | Odpowiedź dla użytkownika | Reguła prezentacji |
| --- | --- | --- |
| Warunki | Z jakim wyposażeniem strony zaczęły? | Broń/utility/rozbrojenie w krótkim opisie; wartości ekonomii tylko przy znanym znaczeniu i pokryciu |
| Początek T | Gdzie T byli skierowani i co rzucili w 10–15 s? | Kierunki i liczebność z podpisanym momentem, rodzaje i miejsca utility, pozycja bomby jeśli znana |
| Początek CT | Gdzie byli obrońcy i czy wysunęli się w early? | A, B, pozostali/nieznani; wsparcie osobno, bez dodawania jednego gracza do obu site'ów; konkretne wysunięte pozycje zamiast nieuzasadnionej oceny agresji |
| Kontakt | Gdzie i między kim zaczęły się obrażenia? | Obie pozycje oraz typ: utility/ogień z broni; pierwszy frag osobno |
| Zmiany sytuacji | Kto uzyskał przewagę i jak odpowiedziała druga strona? | Opening, refrag dokładnego zabójcy, globalny stan T:CT przed/po; inne zabójstwo nazwane kolejnym fragiem |
| Cel rundy | Czy było wejście, plant i co stało się z bombą? | Kierunek, uczestnicy, czas wejścia/planta i stan liczebny przy tych momentach, jeśli znany |
| Koniec | Kto wygrał i w jaki sposób? | Wybuch/rozbrojenie/eliminacja/czas; defuse nie jest jeszcze klasyfikacją retake |

Snapshot po 15 s może pochodzić już z walki. Podstawowy opis ustawienia używa
świeżej próbki sprzed nazwanego kontaktu; snapshoty 10/15 s stanowią dodatkowe
obserwacje z czasem. Nie opisujemy ich jako pewnego planu drużyny.

Przykład WYMYŚLONY, wyłącznie wzorzec treści:
„Po 10 s czterech T było na podejściach do B, a piąty na midzie; do 15 s T
rzucili smoke i dwa flashe. Przed pierwszym kontaktem CT mieli dwóch graczy
na B, dwóch na A i jednego poza site'ami. Alpha zdobył opening przy B w 24 s,
ale został wymieniony po 2,3 s — stan wrócił do 4:4. Trzech T weszło na B;
plant nastąpił przy 3:2, a rundę zakończył wybuch bomby.”

Ten przykład opisuje obserwacje. Sam układ 4+1 nie uzasadnia określenia
„lurk”, a smoke przed wejściem nie dowodzi odcięcia obrońcy.

## Treść perspektywy zawodnika

| Część | Zawartość |
| --- | --- |
| Start | Strona, świeża pierwsza pozycja po freeze, broń i utility; pozycja przed pierwszym własnym kontaktem, jeśli dostępna |
| Pierwszy własny kontakt | Przeciwnik, czas, obie pozycje, kto zadał pierwsze zarejestrowane obrażenia; utility i kontakt ogniowy oddzielnie |
| Efekt kontaktu | „Zabił X”, „zginął od X”, „obrażenia bez potwierdzonego rozstrzygnięcia”; przy wielu uczestnikach opis zdarzeń bez wymuszania pojedynku 1v1 |
| Wkład | Fragi/refragi, czy jego śmierć wymieniono, potwierdzone obrażenia, rzuty i mierzalne efekty utility; własne wejście/plant/defuse |
| Dalszy przebieg | Kilka istotnych, zaobserwowanych pozycji przy kontakcie/wejściu/plancie/końcu; pełna ścieżka pozostaje w radarze |
| Koniec | Śmierć i jej czas albo potwierdzone przeżycie oraz ostatnia znana pozycja/ekwipunek; przeżycie nie dowodzi decyzji o save |

W M3 „przemieścił się z A do B” wymaga próbek obu miejsc, a między nimi może
pozostać luka. Nie określamy jeszcze motywu ani czasu reakcji rotacji.
Zawodnik bez fraga nadal dostaje opis udziału; zawodnik bez kontaktu — opis
zaobserwowanego ruchu, utility i końca rundy, bez sztucznej oceny duelu.

## Kontrakt i reguły obliczeń

Rozszerzamy istniejące `RoundTactics`, `PlayerRound`, `Evidence`, `Finding`
i `Availability`. Nie tworzymy drugiego kompletnego modelu meczu ani drugiego
magazynu pozycji. Proponowane nowe rekordy mają wąski zakres:

- `Contact`: ID, rodzaj, tick, autor/odbiorca i strony, broń, faktyczne HP,
  referencje do obu pozycji wraz z wiekiem próbek, evidence IDs i dostępność.
- `RefragLink`: ID śmierci kolegi, ID zabicia jego zabójcy, opóźnienie,
  długość obserwowalnego okna i status. Jeden frag może wymieniać więcej niż
  jedną śmierć; zachowujemy relacje, a liczbę fragów liczymy po unikalnych ID.
- `AliveState`: tick, liczba żywych T/CT, znani żywi/martwi, status i dowody.
- `RoundMoment`: stabilne ID, typ, tick lub przedział, uczestnicy, powiązane
  zdarzenia, stan liczebny przed/po i dostępność. Surowe dane wskazane przez ID.
- Projekcja widoku: wybrane momenty, ustrukturyzowane fakty do zdań i odnośniki
  do dowodów. Tekst/etykiety prezentacji nie są wejściem kolejnych detektorów.

Zegar pochodzi z `RoundClock`; przy założonym tickrate oznaczamy ograniczenie
precyzji. Źródłowe ID pozostają stabilne. Brak profilu usuwa tylko opis
przestrzenny; fragi, liczebność i chronologia bomby nadal mogą być dostępne.

Kontakty budujemy z dodatnich obrażeń przeciwnika. Fragi uzupełniają kontakt
przy braku eventu obrażeń bez podwójnego naliczania HP. Friendly fire, suicide
i world damage nie stają się kontaktami przeciwników, ale śmierci z tych
przyczyn aktualizują liczebność. Pozycja nie może pochodzić z przyszłości;
limit wieku próbki jest jawny i wykorzystuje istniejący indeks.

Refrag: ściśle późniejsze zabicie dokładnego zabójcy kolegi, do 10 s włącznie,
w tej samej rundzie. Okno kończy się z rundą. Równe ticki bez wiarygodnej
kolejności nie dowodzą odpowiedzi. Brak fragów przy brakującym źródle pozostaje
nieznany. Dotychczasowe ratingowe okno 5 s ma odrębną semantykę i wersję.

Liczebność startuje od zweryfikowanego rosteru i stanów życia. Przetwarzamy
unikalne zgony, konfrontujemy ze snapshotami; rozbieżność/reconnect daje
ograniczenie, nie automatyczne 5:5. Jednoczesne zgony mają wspólny stan
przed/po ticku; nie produkujemy fikcyjnej chwilowej przewagi.

Selekcja krótkiego opisu ma stałą kolejność: przygotowanie → pierwszy kontakt
i opening/odpowiedź → istotna zmiana liczebności → wejście/plant → koniec.
Duplikujące się momenty łączymy prezentacyjnie. Opening, zmiana strony mającej
przewagę i liczebność przy celu są kandydatami do skrótu, ale nazwa „moment
decydujący” wymaga więcej dowodów. Pełna oś zachowuje pozostałe zdarzenia.

## Dekompozycja implementacji

Złożoność 1–5. Każde podzadanie ma określony rezultat i warunek odbioru.
Numeracja rozwija zadania M3.1–M3.5 z roadmapy.

| ID | Zakres i rezultat | Odbiór | Złożoność / zależność |
| --- | --- | --- | --- |
| M3.1a | Audyt dostępnych pól i źródeł na Mirage/Inferno; tabela fakt → źródło → braki | Potwierdzona dostępność każdej frazy planowanego podsumowania | 2 / M2 |
| M3.1b | Wybór 6–8 rund obu map i ręczny zapis oczekiwanej chronologii/team/player przed detektorami | Przykłady normalne, bez plantu, bez własnego fraga, szybki kontakt, luki; fakty sprawdzone poza nowym podsumowaniem | 3 / 1a |
| M3.1c | Uzupełnienie kontraktów o kontakty, relacje, liczebność i momenty; walidacja referencji/statusów | Serializacja, stabilne ID, niezgodność rund odrzucana; szkic UI na przykładach z 1b | 3 / 1a–b |
| M3.2a | Normalizacja obrażeń/fragów i powiązanie pozycji obu uczestników | Brak przyszłych próbek, jawne unknown, brak dubli HP; działanie bez profilu | 3 / 1c |
| M3.2b | Pierwszy kontakt utility/ogniowy rundy i każdego gracza; reuse referencji E1 | Zgodność czasów z E1; kontakt przyjmowany i zadawany; frag bez damage; brak dowodu widoczności | 3 / 2a |
| M3.3a | Opening przeciwników i stan żywych w przebiegu całej rundy | Teamkill/suicide zmieniają liczbę, duplikaty nie; wspólny stan po równych tickach | 4 / 2a |
| M3.3b | Refragi 10 s i kolejne zabójstwa stron; widok stanu po oknie openingu | Granice 0/10/>10 s, koniec rundy, kilka ofiar jednego zabójcy, brak kolejności; rating bez zmian | 4 / 3a |
| M3.4a | Wspólna chronologia z early, kontaktów, liczebności, wejść, bomby i końca | Spójne ID/czasy/statusy, selekcja krótkiej osi, pełne źródła dostępne | 3 / 2b, 3a–b |
| M3.4b | Reguły zdań drużynowych i projekcja udziału gracza | Opis zgodny z 1b, każdy fakt ma dowód; brak wymuszonego duelu/strategii/retake | 4 / 4a |
| M3.4c | Przebudowa widoku: radar na górze, dwa zakresy, skrót, rozwinięcia i tabela momentów | Nicki, wybór zdarzenia ustawia radar, zmiana gracza zachowuje czas; bez powielanych tabel i profilu całej mapy w rundzie | 4 / szkielet po 1c, finalizacja po 4b |
| M3.4d | Wspólny serwis/składanie i cache wyniku rundy, wersje oraz unieważnianie | Zmiana gracza bez parsera i ponownej detekcji; odczyt jednej rundy; brak duplikacji pozycji w cache | 3 / projekt po 1c, integracja z 4a–c |
| M3.5a | Testy detektorów i kompletnego opisu wobec referencji na obu mapach | Żadne zdanie nie ma brakujących dowodów; unknown nie zmienia się w zero; regresje istniejących wejść i early | 3 / stale od 1b, odbiór po 4b |
| M3.5b | Odbiór UI/E2E i wydajności; restart działającej aplikacji po wdrożeniu | Obie mapy, zmiana rundy/gracza, skok na radar, brak profilu/braki danych, ponowne otwarcie bez parsera; sprawdzona uruchomiona instancja | 3 / 4c–d, 5a |

Praktyczne porcje pracy: **1a–c → 2a–b + 3a → 3b + 4a → 4b–d → 5a–b**.
Szkic UI i przykłady odbiorowe powstają od początku. Podzadania 4c/4d należy
koordynować wokół jednego serwisu, żeby UI nie utrwalił osobnej ścieżki liczenia.

## Technika i wydajność

Obecny `tactical_rounds.py` pozostaje miejscem składania kontraktu; detektory
kontaktów/odpowiedzi i projekcja podsumowania dostają małe moduły z funkcjami
bez zależności od Streamlit. `round_context_view.py` odpowiada za prezentację,
`early_round_view.py` dostarcza uporządkowane szczegóły przygotowania.

Najpierw wybieramy rundę przez istniejący odczyt etapów i `round_analysis`.
Zdarzenia sortujemy raz, przechodzimy chronologicznie, a pozycje pobieramy przez
`RoundIndex`. Kontakty i zgony współdzielą indeksy; unikamy skanowania
wszystkich próbek dla każdego eventu i ponownego parsowania dema.

Klucz wyniku: źródła, runda, wersje detektorów, parametry oraz semantyka profilu.
Wybrany gracz nie jest częścią klucza analizy drużynowej. Wszystkie projekcje
graczy korzystają ze wspólnego wyniku; radar używa istniejących próbek.
Etykiety/tekst/radar mają oddzielną zależność prezentacyjną od semantyki mapy.
W M3 wystarczy cache wyniku w sesji nad istniejącymi etapami SQLite; osobny
trwały etap dokładamy wyłącznie, jeżeli pomiar wykazuje potrzebę.

Mierzymy czas odczytu rundy, budowy faktów, projekcji gracza i rozmiar cache
na obu demach. Cel UX po przygotowaniu danych: zmiana gracza/rundy około 1 s
na tej maszynie; to cel do pomiaru, nie obecna gwarancja. Kryterium twarde:
brak parsera przy powtórnym otwarciu i brak ponownej detekcji po zmianie gracza.
Zmiana kontraktu unieważnia wynik pochodny; nie planujemy migracji historycznych.

## Miejsca rozszerzeń

| Następny etap | Rozszerzenie tego samego podsumowania |
| --- | --- |
| M4.1–2 | Kontakty grupowane w lokalne walki; rozwinięcie momentu o uczestników, efekt HP i udowodnione wsparcie utility |
| M4.3 | Wejścia powiązane z próbami ataku, również zatrzymanymi przed site'em; zmiana kierunku z dowodami |
| M4.4 | W istniejącej części końcowej pojawiają się rotacje i próby retake; brak nowej równoległej osi |
| M5 | Agregacja tych samych faktów według stron, warunków i sytuacji; od wzorca meczowego przejście do konkretnej rundy |
| M6 | Grounded feedback i priorytety rozwoju gracza z referencjami do momentów; deterministyczny opis faktów pozostaje audytowalną podstawą |

Odbiór M3 wymaga pełnego przebiegu dla obu perspektyw i obu map. Nie wystarczy
liczba zaliczonych testów ani wygenerowany HTML: trzeba potwierdzić czytelność,
działanie przycisków i zgodność wybranych momentów z radarem uruchomionej aplikacji.
