# Wejścia T na Mirage — detektor v2

## Co pokazujemy

W kontekście rundy pojawia się lista obserwowanych wejść na A/B. Wybór epizodu
pokazuje czas, uczestników i kierunki, żywych CT na site oraz osobno w strefach
wsparcia (2 s przed wejściem i w chwili wejścia), a także zaobserwowanego nosiciela
bomby. Przycisk ustawia mapę na tick pierwszego wejścia. Utility można przełączyć
z early round na okno 8 s przed tym wejściem, niezależnie od fazy rundy.

## Reguły

- Podstawa: przejście żywego T z innej strefy do `BombsiteA`/`BombsiteB`.
  Wcześniejsza próbka musi być oddalona o nie więcej niż 2 s.
- Potwierdzenie: dalsza obserwacja żywego gracza w tej samej strefie po co najmniej
  0,5 s, bez przerwy między próbkami powyżej 2 s. Krótkie wychylenia lub śmierci
  przed potwierdzeniem mogą nie zostać wykryte; brak epizodu nie oznacza braku ataku.
- Pierwsze przejście zawodnika na każdy site w rundzie liczymy raz. Uczestnicy
  z kolejnych 8 s tworzą epizod. Liczba oznacza różnych wchodzących w oknie,
  nie równoczesną obecność. Dalsze wejścia innych graczy są kolejnym epizodem.
- Przy znanym plant tick wykluczamy nowe przejścia od tego ticka. Gdy brak plantu
  w zapisanych eventach, nie da się odróżnić braku planta od niepełnego źródła.
- Kierunek wynika z poprzedniej strefy. Dla A dodatkowo sprawdzamy XYZ, ponieważ
  `PalaceInterior` w realnym demie oznacza także fragment wyjścia z rampy.
  Podejście rampą: X 0..650, Y -1800..-1250, Z -300..-100 (górna granica wyłączona).
  Podejście pałacem: X -200..400, Y -2450..-1800, Z -100..150.
  To obszary dowodowe podejścia, nie precyzyjny model kolizji; poza nimi kierunek
  pozostaje nieustalony. Short i apartamenty B są rozdzielane etykietami dema.
- CT na site: wyłącznie etykieta danego site'u. Wsparcie A: connector, jungle,
  schody, CT spawn; wsparcie B: short, market, van. Przynależność do strefy nie
  dowodzi widoczności ani rzeczywistej możliwości pomocy.
- Liczby CT są kompletne tylko przy obecności wszystkich CT z rosteru w próbce,
  znanym stanie życia i rozpoznanych strefach żywych graczy. W przeciwnym razie
  UI pokazuje liczbę zaobserwowaną i informację o niepełnych danych.
- Okno utility obejmuje całą mapę i obie strony. Powiązanie czasowe nie dowodzi,
  że konkretny granat wspierał to wejście. Punkty na radarze pozwalają to sprawdzić.
- Nie klasyfikujemy jeszcze execute/rush/fake ani nie przypisujemy intencji.

## Zapis i wydajność

Epizody są przechowywane w istniejącym payloadzie kontekstu przestrzennego SQLite,
w polu `entries`; każdy ma ID z wersją, rundą, site'em i tickiem, próbki przejścia,
obrońców, bombę, utility oraz ograniczenia. `entry_version` jest osobny od wersji
parsowania pozycji. Aktualizacja detektora przelicza zapisane próbki bez parsera.
Zmiana zawodnika korzysta z tego samego wyniku. Stary payload bez `entries` jest
odczytywany i uzupełniany; istniejące dane meczu pozostają zachowane.

## Sprawdzone na dostarczonym Mirage

W pierwszej rundzie pierwsze potwierdzone wejście A zaczyna się w ticku 7468
(10 s po freeze-end). W oknie jest dwóch T wchodzących rampą. Próbka drugiego
gracza przed wejściem, tick 7596, ma etykietę `PalaceInterior`, ale współrzędne
około (176, -1498, -176), czyli podejście rampą na parterze. Potwierdza to potrzebę
uwzględnienia wysokości. W tickach 7340 i 7468 obserwujemy dwóch żywych CT na A.

Te oczekiwania sprawdza test realnego dema. Testy syntetyczne obejmują grupowanie,
okno utility, plant, lukę w próbkach, krótkie wejście, niepełny roster CT,
wysokość pałacu, zapis/odczyt i UI z nickami. Przegląd dotyczy zapisanych pozycji;
pełna walidacja wszystkich kierunków i czułości wymaga oznaczenia większej liczby
rund, w tym szybkich wejść zakończonych śmiercią.
