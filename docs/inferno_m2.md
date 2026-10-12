# M2 — integracja Inferno

Status: podstawowy przepływ M2.1–M2.5 zaimplementowany i sprawdzony technicznie
12 października 2026. Osobny przegląd taktyczny w kliencie gry oraz ręczny odbiór
widoku Streamlit nadal wymagają wykonania przez osobę z dostępem do replayu/UI.

## Źródło i niezależne punkty kontrolne

Demo: `samples/1-57640da7-9cd0-4aca-890f-4c82c1344eee-1-1.dem.zst`.
Nagłówek parsera: `de_inferno`, patch `14186`, FACEIT. Analiza bazowa po usunięciu
segmentu przedmeczowego: 20 zakończonych rund, 10 graczy, 138 fragów.

Etykiety i pozycje poniżej pochodzą bezpośrednio z `demoparser2`, zanim profil
Inferno zostanie użyty. Numericzne `site=296` odpowiada A, `site=1023` B:

| Runda | Fakt z dema | Oczekiwana obserwacja mapowa |
| --- | --- | --- |
| 3 | Plant tick 24989, `BombsiteA`, (2091, 182) | Wejście A od Top Mid tick 24551, 3 uczestników |
| 7 | Plant tick 51159, `BombsiteB`, (151, 2860) | Wejście B z Banana tick 47766; kolejna grupa tick 49866 |
| 10 | Plant tick 68896, `BombsiteB`, (290, 2587) | Wejście B z Banana tick 67298, 3 uczestników |
| 13 | Bez plantu | Wejście A z balkonu tick 86410, 2 uczestników; wejście samo nie dowodzi skutecznego ataku |

Plik [wyników przebiegu](reference/inferno_m2_verification.json) zawiera wszystkie
grupy wejść, pokrycie lokalizacji i pomiar. Liczby wejść są kontrolą regresji
detektora, a nie niezależnym opisem zamiaru T. Referencją dla site'u i położenia
plantu jest osobny strumień zdarzeń parsera.

## Profil i zakres

`src/maps/profiles/de_inferno.json` mapuje 23 zaobserwowane etykiety nav na
stabilne ID, site'y A/B, podstawowe podejścia, wsparcie CT i połączenia.
Kierunek z rampy T jest nieznany, bo prowadzi do różnych części mapy. Powiązania
wsparcia oznaczają sąsiedztwo, nie widoczność ani faktyczny udział w walce.
Połączenia są częściowe i mają status `limited`; brak krawędzi nie oznacza braku
przejścia. Profil nie zawiera siatki kolizji ani pełnego grafu widoczności.

Radar i transformacja `(pos_x=-2087, pos_y=3870, scale=4.9)` pochodzą z
[Awpy data release 2000927](https://github.com/pnxenopoulos/awpy-data/releases/tag/2000927).
Ten sam obraz jest używany dla całej mapy; wysokość `Z` pozostaje w próbkach,
ale radar nie przedstawia oddzielnego piętra apartamentów. Profil deklaruje
zgodność dla patcha dema 14186 na podstawie tego lokalnego testu. Nie twierdzi,
że grafika z release 2000927 ma identyczną geometrię w tym patchu.

## Odbiór techniczny

Izolowany przebieg `scripts/verify_inferno_m2.py` wykonuje analizę bazową,
obserwacje, lokalizację, fundamenty, przygotowanie rund i wejścia przez wspólny
silnik. Sprawdza zapis i odczyt rund 1/2 bez parsera, stabilność źródłowych ID,
zbudowanie radaru i niezależne punkty kontrolne. Dla wszystkich 20 rund uzyskano
153 711 przypisań `observed` oraz 39 `unknown` z pustą etykietą nawigacyjną;
nieznanych próbek nie zamieniono na pozorne zero lub site.

Profil nie wymaga rozgałęzień po nazwie mapy w detektorach. Brak profilu nadal
zachowuje obserwacje niezależne od mapy. Testy syntetyczne i regresje Mirage są
uruchamiane razem z testami Inferno. M2 nie rozszerza klasyfikacji o próby ataku,
rotacje i retake planowane w późniejszych etapach.

Pełny zestaw: **168 zaliczonych, 2 opcjonalne pominięte** bez zmiennych ze
ścieżką do dema. Izolowana regresja na rzeczywistym Mirage:
[wynik](reference/m2_mirage_regression.json) — 21 rund, 25 wejść, odczyt i
przeliczenie profilu bez parsera. Przebieg Inferno z przesłanego `.dem.zst`
zakończył się poprawnie w około 33 s przygotowania na tej maszynie; to
pojedynczy pomiar, nie gwarancja wydajności.
