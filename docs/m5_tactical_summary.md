# M5 — pełna prezentacja danych taktycznych z jednego dema

Wdrożono 2026-10-14 po poprawkach M5.R1–R3. Implementacja i weryfikacja
techniczna M5.1–6 są gotowe; odbiór prezentacji przez użytkownika pozostaje otwarty.
Integracja i próbne wywołania LLM zostały przeniesione do M6.

## Gdzie zobaczyć

**Analiza meczu → Tendencje mapy → Przygotuj zestawienia mapy**.
Wybór stałej drużyny, strony T/CT, zakresu drużyna/gracz, czasu snapshotu,
rund, wyceny sprzętu i początkowego stanu 5 na 5 działa na wspólnych faktach.

| Zakładka | Prezentacja |
| --- | --- |
| Ustawienie i kierunki | Dotychczasowe kierunki T, sektory CT przed kontaktem, pozycje po 10/15 s i potwierdzone wejścia. |
| Kontakt i wynik | Pierwszy dostępny kontakt, opening, osobne liczniki fragów wymieniających i wymienionych zgonów, wykorzystanie przewagi. |
| Utility i warunki | Rzuty w 0–15 s, miejsca rzutu/efektu, rzuty ze spawnu, sprzęt obu stron i poprzedni wynik. |
| Ataki T | Cele prób i wykres częstości, wejście/plant/wygrana osobno; końcowe planty, podobne wykonania, tempo, utility oraz działania poza grupą. |
| Obrona i rotacje CT | Wysunięta/pozycyjna obecność i wycofanie, czas i późniejsze obszary, kontakty, utility, okazje do reakcji, dotarcia i retake. |
| Następstwo rund | Powtórzenia/zmiany po wygranej/przegranej, znane/nieustalone pary i zmiana wyceny obu drużyn. |
| Wnioski z danych | Do pięciu opisowych powtórzeń z licznikami, mianownikami, zakresem i przejściem do rund źródłowych. |

Zakładka działań zależy od strony. Szczegóły prób i par są rozwijane; można je
pobrać jako CSV z nickami. Wspólny wybór źródłowego zestawienia i obserwacji
prowadzi do rundy i właściwego czasu na radarze. Przeglądarka nie była otwierana
automatycznie podczas realizacji.

## Reguły i jednostki

- **Próba T:** rzeczywisty epizod M4, również zatrzymany przed wejściem.
  Kolejne próby i zmiany celu pozostają osobne. Wejście i plant mają mianownik
  znanych wyników prób; zwycięstwo ma mianownik unikalnych rund. Jedna wygrana
  runda z dwoma próbami nie jest dwoma niezależnymi zwycięstwami.
- **Pokrycie prób:** źródła ruchu, kontaktów, utility i bomby muszą być znane
  w obsługiwanym profilu. Potwierdzone epizody z niepełnych źródeł są pokazywane,
  ale nie nazywamy całej takiej rundy kompletnie rozstrzygniętą.
- **Podobne wykonania:** cel, okno startu, zestaw obszarów podejścia i typów
  towarzyszącego utility. Okna 0–20 / 20–45 / >45 s są jawnym opisem czasu od
  końca freeze time, nie detektorem rush/execute. Brak źródeł utility ma osobną
  kategorię. Detale zawierają czas próby, rozpiętość wejścia i przerwy ruchu
  zawodnika referencyjnego z M4.
- **Utility przy próbach:** powiązanie rzutu z próbą; ten sam granat może
  towarzyszyć kolejnym próbom. Miejsce rzutu i efektu pozostają osobne.
  Przed/podczas oznacza relację czasu, nie udowodnioną skuteczność granatu.
- **Poza grupą:** obszary, kontakty, utility, dołączenie i zaobserwowany kontakt
  z rotującym CT. Nie nadajemy automatycznej etykiety lurka ani jego intencji.
- **Aktywność CT:** okres obecności gracza w obszarze; czasy różnych graczy
  mogą się nakładać. Wysunięcie jest semantyką profilu, nie dowodem bezpiecznej
  kontroli. Późniejsze pozycje i kontakty opisują faktyczne następstwo.
- **Utility CT:** rzuty autora podczas jego wysuniętej/pozycyjnej obecności
  lub wycofania. Relacje do ataków T obejmują osiem sekund przed próbą i samą
  próbę, bez udowadniania związku przyczynowego lub przestrzennego.
- **Rotacje:** okazja to gracz względem nazwanego kontaktu/planta. Kwalifikacja
  obejmuje także nieżyjących, już obecnych w sektorze i nieznane pozycje.
  Wśród kwalifikujących się są dotarcia, brak dotarcia, śmierć i nieustalone
  przebiegi. Mediany pokazują liczbę faktycznych pomiarów; ujemna reakcja
  oznacza opuszczenie sektora przed sygnałem. Nie mierzymy chwili zobaczenia rywala.
- **Retake:** próba i jej wynik, potwierdzony brak próby, brak zastosowania
  bez planta i nieustalony przebieg pozostają odrębne. Wynik jest drużynowy.
- **Następstwo:** tylko sąsiednie wybrane rundy tej samej strony i segmentu.
  Porównujemy kierunek po 10 s, pierwszy cel/okno startu, early utility i
  ustawienie CT. Remisy pierwszych prób są zbiorem równorzędnych celów.
  Nieznane cele/czasy/obszary utility dają nieustalone porównanie, a nie
  potwierdzone powtórzenie. Zmiana ekonomii jest jawna, bez automatycznego
  wyrównywania zasobów i bez przypisywania świadomej adaptacji.
- **Gracz:** filtr dotyczy własnych kontaktów, rzutów, udziału w próbach,
  działań poza grupą, obecności i rotacji. Kierunek/ustawienie, plant,
  zwycięstwo i następstwo strategii pozostają kontekstem zespołowym.

## Poprawki review

M5.R1: OBSERVED + potwierdzony ABSENT oznacza znane źródła kontaktów.
Znane niekwalifikujące się zdarzenia dają brak kontaktu, nie lukę danych.
Przy niepełnych źródłach zachowany kontakt ma jawny status pierwszej
dostępnej obserwacji.

M5.R2: jeden frag za dwóch kolegów daje **1 frag wymieniający, 2 wymienione
zgony i 1 rundę**. Zachowano ID obu zdarzeń, a nawigacja unikalnej odpowiedzi
łączy dowody wszystkich wymienionych zgonów. Filtr gracza wskazuje autora fraga.

M5.R3: snapshot późniejszy od końca rundy jest niekwalifikujący się do pomiaru;
nie dodaje pięciu nieznanych pozycji. Granica dokładnie w końcu rundy pozostaje
kwalifikująca. Brak zegara/próbki pozostaje nieustalony. Inne miary zachowują zakres.

## Implementacja, cache i weryfikacja

- `map_action_facts.py` projektuje odebrane wyniki M4 do wspólnych faktów M5.
  `map_action_tendencies.py` agreguje działania i następstwo bez parsera,
  trajektorii, bazy, zależności od nazw map ani nowych detektorów.
- `map_round_facts.py`: wersja **6**; kontakty: wersja **2**;
  agregaty `map_tendencies.py`: wersja **2**. Klucz etapów unieważnia stare wyniki.
  Historyczne analizy nie wymagają migracji. W sesji zmiana wersji zmienia klucz.
- Obie rzeczywiste mapy, **41 rund**: zgodność ID/liczb działań i wyników retake
  z zapisanymi wynikami M4; cache hit sprawdzany przy zakazanym odczycie źródeł
  i detektorów. AppTest przeszedł widoki T/CT obu drużyn na obu meczach.
- Pełna regresja: **252 zaliczone, 2 opcjonalne pominięte**. Ruff nowych/zmienianych
  modułów M5 i testów przechodzi. Nowe przypadki obejmują również syntetyczną
  mapę z przemianowanymi obszarami, zmianę A→B, nieznane źródła, kilka prób w
  jednej rundzie, brak dotarcia, utility, filtr gracza, remisy i porównania po wyniku.
- `scripts/verify_m5_baseline.py --ui`: odczyt pełnych faktów **52 ms Mirage /
  60 ms Inferno**; cztery agregacje **6 / 7 ms**; przygotowanie **8,34 / 9,88 s**
  ze źródeł i M4 bez parsera. Fakty **2479 / 2892 KiB**. To lokalny pomiar,
  nie gwarancja czasu renderowania całego UI.

## Odbiór i ograniczenia

Pozostaje przegląd czytelności przez użytkownika na jego rundach. Zachowano
ograniczenia detektorów M4 i profili: część obszarów Mirage jest nieustalona,
efekty utility bywają nieprzypisane, resetów ekonomii nie znamy w pełni.
Pełnego słownika strategii, jakości lurka, widoczności, intencji ani przyczyn
wyniku nie wyprowadzamy z samych pozycji i następstwa zdarzeń.

Po odbiorze M5 można rozpocząć M6: pakiet danych, próbny feedback, adapter API,
walidacja odpowiedzi i raport. W tym etapie nie dodano ani nie wywołano LLM.
