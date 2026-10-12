# Przygotowanie rundy — R2.1–R2.3

Mirage, pierwsze **0–15 sekund od potwierdzonego końca freeze time**.
Wynik jest wspólny dla graczy i powstaje z zapisanego kontekstu, bez parsera/API.

## Zapisane obserwacje

- `Preparation.snapshots`: pozycje po 0, 5, 10, 15 s; żywi gracze według
  stref, osobno polegli, brakujące obserwacje, tick każdej próbki i dowody.
  Snapshot używa ostatniej próbki każdego gracza nie starszej niż 1 s.
  Liczby są pełne wyłącznie przy obserwacji całego pięcioosobowego rosteru.
- `Preparation.movements`: zmiany stref z graczem, poprzednim tickiem,
  pierwszą próbką w nowej strefie oraz potwierdzeniem co najmniej 1 s później.
  Powrót do poprzedniej strefy usuwa niepotwierdzone przejście. Brak życia,
  nieznana strefa lub luka ponad 2 s przerywa ścieżkę.
- `Preparation.utility`: autor, rodzaj, czas i XYZ detonacji/startu ognia,
  z identyfikatorem oryginalnego zdarzenia. Granat rzucony przed freeze-end,
  ale działający w oknie, też jest uwzględniany. Granat rzucony przed 15 s,
  ale detonujący później, nie trafia do tego zestawienia.

Site A/B pozostają oddzielne od midu, podejść i łączników. Rampa rozpoznana
z XYZ w PalaceInterior jest tą samą strefą co TRamp. Pozostałe niejednoznaczne
próbki PalaceInterior pozostają nieznane; nie wymuszamy pozycji w pałacu.

Status ustawienia i ruchu opiera się na pokryciu **wczesnego okna**, niezależnie
od luk w późniejszej części rundy. Pusta lista przejść przy pełnych danych
oznacza potwierdzony brak przejść według tej definicji. Nie oznacza braku ruchu
wewnątrz strefy ani pasywnej gry. Niepełne dane nie są zerem.
Puste early utility jest potwierdzonym brakiem tylko przy sprawnych źródłach.

Parametry i wersja detektora znajdują się w `TacticalMatch.parameters`.
Nowe pola mają wartości domyślne, więc wcześniejsze rekordy schematu 1 nadal
się odczytują, z analizą R2 oznaczoną jako niewykonana.

## Interfejs i wydajność

Kontekst mapy → **Początek rundy · 0–15 s**: obie strony, wybór momentu,
szczegóły pozycji i przemieszczeń, utility oraz przycisk ustawienia radaru.
W tabelach używane są nicki. Sesja zachowuje wynik wspólny dla rund;
zmiana czasu/gracza nie buduje go ponownie. Pełne dowody nie są dublowane
w tej warstwie cache. Wyliczenie nie modyfikuje schematu bazy.

Pomiar z zapisanego realnego Mirage: 21 rund, 147 zdarzeń early utility;
przygotowanie pełnego kontraktu około 0,735 s w pojedynczym pomiarze lokalnym.
32 z 42 obserwacji przygotowania drużyny mają pełne pokrycie, 10 częściowe.
To pomiar techniczny, nie ocena trafności wszystkich przejść.

## Weryfikacja i dalsza praca

Testy obejmują chwilowe zmiany etykiet, potwierdzenie ruchu, śmierć, luki,
brakujące osoby, PalaceInterior, round-trip JSON oraz przejście UI na radar.
Osobne oczekiwania dla czterech zapisanych rund rozszerzono o obsadę CT po
10 s i liczbę early utility. Oczekiwania sprawdzono na surowych rekordach;
nie jest to niezależna ocena przez replay. W pierwszej rundzie po 10 s:
2 CT na A, 2 na B, 1 w midzie; flash T w ticku 7533 (11,015625 s).

Otwarte: ręczne oznaczenie przebiegu ruchu na replayu, granice geometryczne
wszystkich stref, obszar/długość działania utility oraz powiązanie z oślepieniem,
obrażeniami i zajęciem przestrzeni. XYZ granatu nie daje obecnie nazwy strefy
ani dowodu skuteczności. Pełna strategia T, agresywność CT i intencja rotacji
pozostają do oceny na podstawie dalszych faz rundy.

## R2.4–R2.5 — profil i krótkie podsumowanie

Wersja 2 detektora early round uzupełnia `Preparation` o:

- `orientation` i `orientation_tick`: obserwowana liczba żywych graczy w kierunku
  A/B/mid/pozostałe w ostatnim dostępnym zaplanowanym momencie 10/15 s.
  Tekst zawsze podaje rzeczywisty moment i zaznacza niepełną obserwację.
- `formation`: pięciu na jednym kierunku, 4+1 albo rozłożenie na kilka kierunków.
  Etykieta wymaga pełnej próbki **pięciu żywych**; brakująca lub martwa osoba
  nie staje się graczem poza grupą. Kierunek jest szeroką strefą, nie odległością
  między zawodnikami. Gracz poza grupą nie jest automatycznie lurkerem.
- `bomb_area`: zaobserwowana strefa pojedynczego żywego nosiciela w tym momencie;
  brak nosiciela lub sprzeczne wskazania pozostają nieznane.
- `first_site_presence_seconds` i `tempo=early_site_entry`: pierwsze istniejące
  potwierdzone wejście T w 0–15 s. Nie jest to rozpoznanie rush/execute ani
  czas pierwszej próby ataku. Brak wejścia nie oznacza wolnego tempa.
- `activity` CT: potwierdzona przez co najmniej 1 s obecność w wysuniętej strefie
  (mid naziemny, underpass, podejścia T). Sam Window, Connector, Catwalk czy
  wybiegnięcie ze spawnu na własny site nie oznaczają wysunięcia.
  Luka >2 s, zmiana miejsca i śmierć przerywają potwierdzenie. Wskazanie jest
  heurystyką opartą na etykietach nawigacji, bez geometrii widoczności.

Pozytywna obecność CT może być raportowana przy brakach w innych danych.
Brak potwierdzonej obecności jest raportowany tylko przy pełnym pokryciu okna;
nie stanowi oceny pasywnego stylu. `target_sequence` pozostaje niewyliczone.

`findings` rozróżniają obserwacje od interpretacji. Każdy wniosek ma dowody;
interpretacje mają ograniczoną pewność i opis ograniczeń. UI pokazuje dwa
osobne krótkie podsumowania T/CT, rozwijane dowody z tickami/czasem/źródłem.
Próbki i utility zostają dostępne pod podsumowaniem. Cache uwzględnia wersje
detektora oraz interpretacji; model i dane dowodowe pozostają lokalne.

Testy kontrolują m.in. 5/4+1/rozłożenie, brakujące i poległe osoby, nosiciela,
potwierdzenie wysunięcia CT, luki i śmierć oraz brak automatycznego rush/execute.
W realnym cache Mirage: 7 ustawień 4+1, 14 bez etykiety formacji; 12 rund
z potwierdzoną wysuniętą obecnością CT. Są to wyniki detektora, wymagające
przeglądu na replayu, a nie ręcznie zatwierdzone etykiety strategii.
