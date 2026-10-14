# M5.AN — Anubis przed zamknięciem M5

Dodano 2026-10-14, po Dust2, na prośbę użytkownika. Integracja techniczna
jest gotowa; odbiór sensu interpretacji na wybranych rundach pozostaje otwarty.

## Implementacja

- Profil `src/maps/profiles/de_anubis.json`, rejestr map, lokalny radar
  i metadane. Wspólne detektory oraz UI M3/M4/M5 nie otrzymały warunków
  zależnych od nazwy Anubis.
- 28 regionów z etykiet faktycznie odczytanych z dema. A: main, walkway,
  fontanna, heaven i dojście od CT. B: main/long, łącznik od wody, tył B,
  Bricks, Palace i dojścia od CT. Mid oraz most pozostają osobnymi regionami.
- **Bridge i Canal są rozdzielone po nav-label**, mimo nakładania się na
  płaskim radarze. Nie wnioskujemy o widoczności z tej projekcji. Brak
  etykiety nie uruchamia zgadywania piętra z samego XY.
- Etykieta `Water` w tym demie leży za respem CT; ma osobny region `ct_water`.
  Nie jest aliasem `Canal`.
- Kanał i resp CT wspierają obie strony mapy, ale nie otrzymują równocześnie
  sektorów obrony A i B ani jednoznacznego kierunku ataku T. Obecność
  w kanale nie dowodzi wyboru site'u.
- Wysunięcia CT wynikają z profilu. A main ma konserwatywną granicę
  `Y <= 1300`, drzwi mid `Y <= 500`; dalsze obszary używają etykiet nav.
  Te granice są heurystykami do wspólnej kalibracji na rundach.
- Radar z [Awpy release 2000927](https://github.com/pnxenopoulos/awpy-data/releases/tag/2000927):
  `pos_x=-2796`, `pos_y=3328`, `scale=5.22`, 1024 × 1024. Surowe pozycje
  plantów potwierdzają ustawienie site'ów na obrazie.

## Demo i weryfikacja

`1-1ccc85d8-33b4-4de8-a6fd-ed34154629d0-1-1.dem.zst`, patch `14189`,
SHA-256 rozpakowanego dema
`c5f3f99d0cfe9eee7f1bf0dbdc2ab8ff2509a4ef01630ac3451bd9ced7dddda0`.

Wynik: **24 rundy, 10 graczy, 166 fragów i 7 plantów w aktywnych rundach**.
Surowy plant w ticku 33309 leży poza aktywnymi oknami rund i nie zasila
agregatów. Osiem zdarzeń surowych nie oznacza ośmiu plantów w statystykach.

| Runda / tick | Niezależna referencja |
| --- | --- |
| 4 / 24968 | Plant A, `BombsiteA`, pozycja około (1276, 1938, -192). |
| 7 / 42955 | Plant B, `BombsiteB`, pozycja około (-1136, 687, -2). |
| 21 / 110132 | Późniejszy plant A, około (967, 1752, -192). |

Numeryczne site ID w tym demie to 444 i 239. Ich znaczenie A/B nie jest
zaszyte w silniku; przypisanie korzysta z pozycji i profilu.
Mała referencja bez danych graczy: `tests/reference/anubis_spatial_facts.json`.

Pełna ścieżka sprawdziła zapis analizy, M3/M4/M5 wszystkich rund, zgodność
plantów i prób z surowymi zdarzeniami, radar wszystkich rund, filtry obu
drużyn T/CT oraz nawigację M5 → podsumowanie rundy/radar, także zmianę
perspektywy drużyna/gracz. AppTest nie otwiera przeglądarki.

**139 021 próbek ze znaną lokalizacją, 39 nieustalonych** — wszystkie
nieustalone miały pustą etykietę nav. Nie ukrywamy ich ani nie przypisujemy
do najbliższego obszaru. Snapshoty po 10 s były kompletne dla wszystkich
rund obu stron. Wykryto 9 i 12 prób T oraz 51 i 53 okazje/reakcje CT;
to jednostki działań, nie liczba wygranych rund lub samych dotarć.

Odczyt gotowych faktów: lokalnie około **59 ms**. Przygotowanie z istniejącą
analizą, sprawdzenie źródeł, radarów i UI zajęło około 38 s. Cache hit
przeszedł przy zakazanym odczycie źródeł i uruchamianiu detektorów.
Wyniki są w skonfigurowanej bazie aplikacji; wcześniejsze demo Anubis
otrzymało nowy kontekst profilu bez migracji historycznych wyników.

## Powtarzalny test i odbiór

Wspólny skrypt obsługuje różne profile; polecenie Dust2 zachowano jako
cienki wrapper. Domyślnie używa bazy tymczasowej, `--app` publikuje wyniki
do skonfigurowanej lokalnej bazy i katalogu dem:

```powershell
.\.venv-codex\Scripts\python.exe scripts/verify_profile_m5.py samples/1-1ccc85d8-33b4-4de8-a6fd-ed34154629d0-1-1.dem --map de_anubis --app --ui
```

Do ręcznego odbioru pozostają progi wysunięć, granice prób, ocena rotacji,
użyteczność sektorów i kontekst utility. Nav-label-only nie zapewnia pełnej
geometrii efektów granatów, widoczności ani rozpoznania intencji.
LLM pozostaje wyłącznie zakresem M6.

Końcowa regresja po Dust2 i Anubis: **276 testów zaliczonych,
2 opcjonalne pominięte**. Ruff nowych testów, skryptów i rejestru przechodzi.
