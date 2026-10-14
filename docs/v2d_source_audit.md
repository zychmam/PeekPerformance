# V2D.1 — audyt źródeł viewera

Data: 2026-10-14. **Audyt techniczny wykonany; renderer bez zmian.**
Parser lokalny: `demoparser2 0.42.0`. Dane: zapisane dema i ich zegary
obserwacji, cztery mapy. Odczyt stanu flasha w wybranych oknach co tick,
nie tylko co 0,1 s. Wyniki: [anonimizowane odczyty](v2d_source_audit.json).
Skrypt: [`audit_viewer_sources.py`](../scripts/audit_viewer_sources.py).

## Decyzja

**`blind_duration` można wykorzystać do wizualizacji deklarowanego czasu
efektu flasha. Nie potwierdza ono czasu całkowitego braku widzenia.**

Obecne źródła nie wystarczają do wyznaczenia `full_blind_end_tick` ani
chwilowej intensywności białego ekranu. Te wartości pozostają null.
Nie wyprowadzamy ich z `flash_duration > 0`, `flash_max_alpha == 255`
ani z arbitralnej części czasu zdarzenia.

V2D.3 może przygotować przedziały „zarejestrowany efekt flasha”, pochodzące
z ticku zdarzenia i jego duration, ograniczone życiem zawodnika i rundą.
Przerywana biała obwódka oznacza ten przedział, z odpowiednią legendą.
Ciągła obwódka „pełne oślepienie” i rzeczywiste fazy odzyskiwania wzroku
pozostają niewdrożone do czasu uzyskania potwierdzonego źródła lub modelu
zweryfikowanego z obrazem gry. Nie tworzymy pozornej intensywności przez
liniowe wygaszanie opacity. Zwykłe animacyjne wygaszenie ikony musi być
odróżnione od mierzonego odzyskiwania widzenia.

**Rzuty i loty można wdrożyć z istniejących danych.** Potwierdzono rzeczywiste
pozycje pocisków, właściciela i przykład powiązania z encją flasha.

## 1. Semantyka i sprawdzenie pól

W kodzie tagu odpowiadającego zainstalowanej wersji parsera:

- `flash_duration` mapuje się na `CCSPlayerPawn.m_flFlashDuration`.
- `flash_max_alpha` mapuje się na `CCSPlayerPawn.m_flFlashMaxAlpha`.
- Parser zwraca wartości zapisanej właściwości; nie oblicza widoczności
  sceny ani rozdziału pełnego flasha i wygaszania.

[Mapowanie w demoparser 0.42.0](https://github.com/LaihoE/demoparser/blob/d3767705dc5846d73ed29db50eaeda58778dc934/src/parser/src/maps.rs#L1083).

| Pole / próba | Wynik na naszych demach | Wniosek |
| --- | --- | --- |
| `player_blind.blind_duration` vs `flash_duration` w ticku trafienia | Zgodne dla wszystkich 797 sprawdzonych zdarzeń, także tych dotyczących nieżywych. | Dwa odczyty tego samego czasu nie są niezależnym potwierdzeniem obrazu gracza. |
| `flash_duration` w kolejnych tickach | Przechowuje wartość początkową; nie maleje co tick. Zero może pojawić się później lub po śmierci. | Nie jest zegarem pozostałego oślepienia. |
| `flash_max_alpha` | Wartość 255 występuje również przed trafieniem i po deklarowanym końcu. Przy niektórych stanach występuje 0. | Nie jest bieżącą alfą nakładki ekranowej; warunek 255 nie wykrywa pełnego flasha. |
| `CCSPlayerPawn.m_flFlashBangTime` | Brak w liście aktualizowanych pól; próba odczytu nie zwraca kolumny. | Brak dostępnego czasu klientowej fazy. |
| `CCSPlayerPawn.m_flFlashOverlayAlpha` | Brak w liście aktualizowanych pól; próba odczytu nie zwraca kolumny. | Brak obserwowanej chwilowej intensywności. |

Ważne: brak wspieranego pola może dać tabelę bez kolumny, zamiast wyjątku.
Ekstraktor musi sprawdzać również kolumny i faktyczne wartości.

Jako źródło pomocnicze sprawdzono implementację innego parsera CS2:
[`demoinfocs`, Player/FlashDuration](https://github.com/markus-wa/demoinfocs-golang/blob/b2c4bd882e9c6c87750959ad5096638d87bc074c/pkg/demoinfocs/common/player.go).
Opisuje ona różnicę między czasem oślepienia i dłuższym oknem efektu silnika;
pozostały czas wylicza z ticku trafienia. To potwierdza potrzebę rozdzielenia
pojęć, ale nie jest wzorem na fazę białego ekranu w naszych demach.

## 2. Przypadki kontrolne flasha

Wybrano po pięć przypadków na mapę: najdłuższy dla żywego gracza,
najkrótszy, samoflash i parę kolejnych trafień przed końcem deklarowanego
okna. Zapisano stan przed trafieniem, w trafieniu, po trafieniu, przy
deklarowanym końcu i przy zmianach wartości/życia. Granice sprawdzano co tick.

| Mapa | Zdarzenia aktywnej rundy | Żywi w ticku zdarzenia | Nieżywi w ticku zdarzenia | Pary nakładających się deklarowanych okien |
| --- | --- | --- | --- | --- |
| Mirage | 173 | 168 | 5 | 26 |
| Dust2 | 316 | 305 | 11 | 82 |
| Inferno | 196 | 185 | 11 | 24 |
| Anubis | 112 | 108 | 4 | 9 |
| **Razem** | **797** | **766** | **31** | **141** |

Liczba par oznacza kolejne zdarzenia tego samego gracza w jednej rundzie,
których deklarowane okna zachodzą na siebie. Nie jest liczbą granatów,
wykonanych dobrych flashów ani niezależnych epizodów.

### Konkretne wyniki

- **Dust2 R15, tick 88462, 25,172 s po freeze:** duration 5,1060 s.
  `flash_duration` pozostaje 5,1060 także po deklarowanym końcu. Zero pojawia
  się w ticku 88920, po 7,15625 s. Gracz nadal żyje, bez kolejnego flasha
  w sprawdzanym oknie. Nie możemy interpretować tych 7,16 s jako pełnej ślepoty.
- **Inferno R9, tick 62078, 15,375 s po freeze:** duration 5,1959 s,
  zero dopiero w ticku 62544, po 7,28125 s. Analogiczny wynik.
- **Mirage R10, tick 61986, 7,266 s po freeze:** duration 0,1080 s,
  `flash_max_alpha=255` również przed zdarzeniem. Samo alpha nie rozróżnia
  tego krótkiego efektu od silnego flasha.
- **Anubis R2:** duration 2,0475 s w ticku 10394; kolejny flash po
  0,96875 s, w ticku 10456, ustawia duration 1,4863 s. Pole zmienia się na
  nową wartość, nie na sumę 3,5338 s. Surowe zdarzenia trzeba zachować osobno.
- **Anubis R20, tick 103220:** duration 5,0384 s, ale gracz ginie w ticku
  103317, po 1,515625 s; pole przechodzi do zera. Obwódka musi zniknąć
  przy śmierci, a zero nie dowodzi odzyskania wzroku przez żywego gracza.

W izolowanych silnych przypadkach wyzerowanie właściwości następuje około
1,4 razy później niż duration zdarzenia. To obserwacja, **nie współczynnik do
wdrożenia**. Przy krótkich czasach znaczenie ma też kwantyzacja ticków;
przy śmierci, kolejnym flashu i końcu rundy nie można wyznaczać takiego ilorazu.

## 3. Granaty i optymalizacja źródła

Domyślne `parse_grenades()` zapisuje również przedmioty typu `CFlashbang`,
`CHEGrenade`, `CSmokeGrenade` itd., które w sprawdzonych demach mają null
zamiast pozycji. Lot mają typy `*Projectile`.

Sprawdzono na wszystkich czterech demach **`parse_grenades(grenades=False)`**:
wynik zawiera same pociski; wszystkie ich pozycje w tych demach są dostępne.
Liczba zgadza się z liczbą prawidłowych pozycji w zapisanym surowym zbiorze.

| Mapa | Wszystkie zapisane wiersze | Same pociski z pozycją | Pominięte wiersze |
| --- | --- | --- | --- |
| Mirage | 1 346 224 | 180 950 | 86,6% |
| Dust2 | 2 243 824 | 278 957 | 87,6% |
| Inferno | 1 504 222 | 196 699 | 86,9% |
| Anubis | 1 909 737 | 172 021 | 91,0% |

Zachowanie flagi potwierdza
[kod parsera 0.42.0](https://github.com/LaihoE/demoparser/blob/d3767705dc5846d73ed29db50eaeda58778dc934/src/parser/src/second_pass/collect_data.rs#L277).
To planowana optymalizacja V2D.2/V2D.4; nie zmieniono jeszcze parsera aplikacji.
Nie potrzebujemy zwiększać ogólnego próbkowania zawodników.

Przykład **Anubis R2, encja 434**:

1. Zapisany `weapon_fire` typu flash tego samego gracza: tick **10284**,
   pozycja `(231,923; 1257,557; -31,969)`.
2. Pierwsza próbka pocisku: tick **10290**. Sześć ticków, czyli 0,09375 s,
   po zdarzeniu rzutu. To dwa osobne czasy, których nie należy utożsamiać.
3. Ostatnia próbka pocisku: tick **10393**.
4. `player_blind`: tick **10394**, ta sama encja i rzucający.

Analogiczne powiązanie encji/właściciela i końca toru jeden tick przed
`player_blind` znaleziono na pozostałych mapach. Kilku trafionych jednym
flashem daje kilka zdarzeń tego samego pocisku; nie tworzymy kilku lotów.
Są to próbki potwierdzające wykonalność, nie audyt wszystkich powiązań granatów.
Rozdzielanie ponownie użytych encji, końca lotu smoke'a i braków pozostaje V2D.2.

## 4. Ograniczenia i dalszy kierunek

- **Nie wykonano wizualnego porównania POV w kliencie CS2.** Powyższe
  przykłady są gotową listą do kontroli w oryginalnych demach wskazanych
  w JSON. Nie oznaczamy dokładnej fazy pełnego flasha jako zweryfikowanej.
- Zegary czterech zapisanych analiz używają jawnego `assumed_64`.
  Liczby ticków są obserwowane; sekundy i długość okien zakładają 64 Hz.
  Lokalne zmiany `game_time` w przykładach są zgodne z takim przeliczeniem.
- „Nieżywy w ticku” dotyczy końca ticku. Nie dowodzi, że zdarzenie jest
  błędne: flash i śmierć mogą wystąpić w tym samym ticku.
- Gęstsze próbkowanie tych samych stałych właściwości nie dostarczy
  nieobecnej chwilowej alfy; nie trzeba odczytywać ich co tick całego meczu.
- Decyzja techniczna na V2D.2–5: rzeczywiste rzuty i loty; dla flasha
  jawnie opisane deklarowane okno efektu. Dokładna pełna faza pozostaje
  osobnym ograniczeniem, bez blokowania prac nad granatami.

Ponowienie audytu lokalnie:

```powershell
.\.venv-codex\Scripts\python.exe scripts/audit_viewer_sources.py
```

Skrypt wymaga oryginalnych plików dema i zapisanych obserwacji. Nie zapisuje
nowych wyników do bazy aplikacji. Raport nie zawiera nicków ani SteamID.
