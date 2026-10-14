# M5.D2 — Dust2 przed zamknięciem M5

Dodane na prośbę użytkownika 2026-10-14. Integracja techniczna gotowa;
ocena sensu interpretacji i kalibracja na przykładach pozostają otwarte,
wspólnie z odbiorem M5. Żadna integracja LLM nie jest częścią tego rozszerzenia.

## Implementacja

- Profil `src/maps/profiles/de_dust2.json`, rejestr `de_dust2` i lokalny radar.
  Nie zmieniono wspólnych detektorów, agregacji ani widoków pod nazwę mapy.
- 24 nazwane regiony odczytane z prawdziwego dema: oba site'y, long, short,
  catwalk, pit, mid/drzwi mid, górny/dolny tunel, schody, drzwi/okno B i respy.
- Podejścia A: long/rampa oraz short/catwalk. Podejścia B: tunel, drzwi i okno.
  Mid i dolny tunel nie dostają automatycznie celu A/B.
- Jednoznaczne sektory A/B/mid. Resp CT pozostaje wspólnym wsparciem, bez
  podwójnego zaliczania graczy do obrony obu site'ów.
- Wysunięcia CT są określone deklaratywnie: m.in. catwalk, tunel i mid.
  Long A ma ograniczenie `Y <= 1550`, schody short `Y <= 1650`, aby nie
  zaliczać każdego pobytu blisko własnego site'u jako wysunięcia. To jawne,
  konserwatywne heurystyki wymagające przeglądu taktycznego.
- Regiony są rozpoznawane po etykietach nav, bez ogólnego przypisywania
  obszarów z prostokątów. Nieznane etykiety pozostają nieznane. Górny i dolny
  tunel rozdziela etykieta, nie ocena widoczności na płaskim radarze.
- Radar i transformacja pochodzą z przypiętego
  [Awpy data release 2000927](https://github.com/pnxenopoulos/awpy-data/releases/tag/2000927):
  `pos_x=-2476`, `pos_y=3239`, `scale=4.4`. Statyczny obraz jest ustawiony
  północą do góry. Metadane `rotate=1`, `zoom=1.1` zachowano w pliku źródłowym;
  nie obracamy ponownie tekstury. Konwersja pos/scale odpowiada
  [implementacji Awpy](https://github.com/pnxenopoulos/awpy/blob/main/awpy/plot/utils.py).

## Referencja i przebieg integracyjny

Demo użytkownika: `1-610da466-b271-4c18-90d4-c2da4b0d75d4-1-1.dem.zst`,
mapa `de_dust2`, patch `14186`, SHA-256 rozpakowanego dema
`1ac357e6b6d8a27e88223d18c32b12028b0931d1ff4a4c93f8bcd8807f35c4f5`.

Wynik: **28 rund, 10 graczy, 205 fragów**, 18 plantów w aktywnych oknach rund.
Surowe `round_end` zawiera 30 rekordów: zdarzenie początkowe w ticku 1 oraz
rundę przed restartem w ticku 2397 usuwa istniejąca normalizacja.
Plant w ticku 148697 nastąpił po końcu rundy 23 i przed startem rundy 24;
poprawnie nie zasila statystyk aktywnej rundy.

Niezależnie od resolvera odczytano próbki pozycji i `bomb_planted` przez
demoparser2. Mała referencja bez identyfikatorów graczy jest w
`tests/reference/dust2_spatial_facts.json`. Przykłady:

| Runda / tick | Etykieta / site | Rola referencji |
| --- | --- | --- |
| 1 / 6363 | BombsiteA / A | Plant i pozycja w prawym górnym site na radarze. |
| 2 / 10112 | BombsiteB / B | Plant i pozycja w lewym górnym site. |
| 22 / 143378 | BombsiteB / B | Drugi przykład B w późniejszej części meczu. |

Numeryczne ID site'ów w tym demie to 498 i 248. Silnik nie traktuje ich
jako uniwersalnego enum A/B; site wynika z pozycji/profilu.

Pełny przebieg `scripts/verify_dust2_m5.py` obejmuje import, zapis źródeł,
M3/M4/M5 wszystkich rund, zgodność plantów i prób z niezależnymi zdarzeniami,
radar wszystkich rund oraz cache przy zabronionym odczycie źródeł/detektorów.
Zestawienia obu drużyn po T i CT sprawdzono przez AppTest bez przeglądarki.
Przeszło również przejście z M5 do podsumowania rundy/radaru i zmiana
perspektywy drużyna/gracz. Pełna regresja po dodaniu Dust2: **264 zaliczone,
2 opcjonalne pominięte**. Ruff profilu/rejestru, testów i skryptu przechodzi.

Wszystkie **214 330 próbek pozycji** uzyskały znany region. To pokrycie
etykiet w tym demie, nie dowód trafności każdej interpretacji taktycznej.
Snapshoty po 10 s są kompletne we wszystkich 28 rundach obu stron.
Wykryto 16 i 24 próby T oraz 75 i 62 okazje/reakcje CT dla obu drużyn;
próby nie są liczbą niezależnych rund, a reakcje nie oznaczają samych dotarć.

Pierwszy import, przygotowanie i sprawdzenie zajęły lokalnie około 76 s;
odczyt gotowych faktów około 81 ms. Demo i wyniki zapisano do skonfigurowanej
bazy/katalogu aplikacji, więc mecz jest dostępny na liście zapisanych analiz.

## Odbiór

Pozostaje rozmowa na wybranych rundach: granice ataków, użyteczność
sektorów, progi wysunięć, rotacje i interpretacja utility. Znane ograniczenia
M4/M5 pozostają aktualne: brak pełnej geometrii efektów utility, widoczności
i pewnej intencji strategii/lurka. Dodanie Dust2 nie zmienia ich w potwierdzone fakty.

Uruchomienie powtarzalnej weryfikacji:

```powershell
.\.venv-codex\Scripts\python.exe scripts/verify_dust2_m5.py samples/1-610da466-b271-4c18-90d4-c2da4b0d75d4-1-1.dem --app --ui
```

Bez `--app` skrypt używa tymczasowej, izolowanej bazy.
