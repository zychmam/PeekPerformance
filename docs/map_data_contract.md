# M1: kontrakty danych i granice mapy

Kontrakty A1, 2026-10-12. Implementacja: `src/models/observations.py` i
`src/models/spatial.py`. Format bieżący ma wersję 1. Historyczne analizy nie są
migrowane; wdrożenie resetuje wyniki i zachowuje demka, konfigurację i graczy.

## Zależności i własność danych

Kierunek importów: modele → ekstrakcja / profile → resolver → detektory → UI.
Modele nie importują parsera, profilu Mirage ani Streamlit.

| Pole poprzedniego MirageContext | Docelowy właściciel |
| --- | --- |
| clock | Obserwacje: start/koniec, freeze, częstotliwość i źródło czasu |
| states | Obserwacje: tick, XYZ, surowe nav labels, gracz, HP, strona, orientacja |
| states.zone/place | Interpretacja przestrzenna; nie należy do payloadu źródeł |
| utility | Obserwowane detonacje / efekty |
| shots | Obserwowane wystrzały |
| equipment/economy | Obserwacje wyposażenia, pieniędzy i ich pokrycie |
| bombs | Obserwowane zdarzenia bomby |
| throws/utility_lifecycles | Rzuty i powiązania z efektem, z jawną niepewnością |
| smokes | Obserwowany czas początku/końca osobno od wizualnego oszacowania końca |
| entries | Wynik detektora, zależny od profilu i konfiguracji |
| diagnostics | Manifest jakości źródeł; błędy pól i luki pozostają jawne |

`MatchObservations` przechowuje tożsamość dema, nazwę mapy, klucz źródeł i ramki
pandas. `to_dict/from_dict` i `to_json/from_json` zachowują SteamID jako tekst,
null zamiast NaN oraz porządek rekordów. Obiekt odrzuca przestrzenne kolumny
`zone/place/region_id/direction` w źródłowych stanach. Pozostałe kolumny wyliczone
przestrzennie usuwa ekstraktor; do źródeł nie wolno dopisywać lokalizacji.

Brak profilu mapy nie blokuje wyposażenia, pierwszego kontaktu, openingu,
obrażeń, refragów ani historii bomby. Brak freeze pozostaje nieznany.

## Czas, konfiguracja i manifest

`RoundClock(round_number,start_tick,freeze_end_tick,end_tick,tick_rate,time_source)`:

- `seconds(tick)` liczy od freeze, zwraca None bez potwierdzonego freeze.
- `ticks(seconds)` przelicza wspólne progi na całkowite ticki; nie tworzy subticków.
- `tick_at(seconds)` i `contains(tick)` obsługują wybór czasu i granice rundy.
- `from_row` czyta bieżące kolumny `total_rounds_played/start_tick/freeze_tick/tick`.
- Domyślne 64 jest oznaczone `assumed_64`; wiarygodne metadane mają własne źródło.

`DetectorConfig` zawiera niezależne od geometrii progi w sekundach: snapshoty,
early round, refrag, przerwa starcia, grupa wejścia, potwierdzenie i świeżość
próbki. Wprowadzenie modelu nie oznacza uruchomienia przyszłych detektorów R3.

`StageManifest` zawiera nazwę etapu, wersję schematu/algorytmu, fingerprinty
rzeczywistych zależności oraz status i ograniczenia. Jego `cache_key` zależy od
wersji i wejść; status opisuje wynik, nie zmienia tożsamości obliczenia.

## Profil przestrzeni

`MapProfile` zawiera `map_name/profile_version/schema_version`, regiony,
połączenia, poziomy radaru, capabilities, compatibility i coverage.

`Region.id` jest stabilnym kluczem, a `name` tekstem prezentacji. Region posiada:

- surowe `nav_labels`, opcjonalne `bounds` XYZ i jawny `priority`;
- fizyczny `kind` oraz `site_id` dla rzeczywistego site'u;
- wielowartościowe `directions`, `support_sites` i zależne od strony `forward_sides`;
- `route_names`: klucze oznaczają site'y osiągane z podejścia, wartości są opisem
  prezentacji; `route_requires_geometry` wymaga rozstrzygnięcia geometrią;
- `level_id` oraz metadata przeznaczone wyłącznie na pochodzenie reguły.

Nie ma wymaganego mida. Region może mieć wiele kierunków; connector nie jest
automatycznie site'em. Strefa wsparcia nie dowodzi widoczności ani udziału w walce.

`RegionBounds` ma dolne granice włączne i jawne `include_max_x/y/z`. Brak Z przy
regule zależnej od wysokości nie spełnia reguły. `SpatialConnection` określa
skierowane przejście (`walk/ladder/drop/jump`) i jego weryfikację. Brak relacji w
niepełnym grafie oznacza brak wiedzy; graf nie modeluje LOS.

`RadarLevel` zawiera obraz, początek transformacji, skalę, rozmiar i opcjonalne
wysokości. `project` przelicza współrzędne bez wpływu na liczby taktyczne.
Walidator modelu sprawdza wersje, unikalność ID, referencje, geometrię i transformację;
rejestr profili sprawdza dodatkowo istnienie plików obrazów.

## Lokalizacja i relacje

`LocationAssignment` odwołuje się do `observation_id`, nie kopiuje źródłowego stanu.
Zawiera region lub kandydatów, poziom, metodę, status i fingerprint semantyki.

```json
{"observation_id":"demo:states:hash:0","region_id":"ramp","candidates":["ramp"],"method":"geometry","status":"observed","profile_fingerprint":"map-hash"}
```

```json
{"observation_id":"demo:states:hash:1","region_id":null,"candidates":["lower","upper"],"method":"nav_label","status":"partial","profile_fingerprint":"map-hash"}
```

```json
{"observation_id":"demo:states:hash:2","region_id":null,"candidates":[],"method":"none","status":"unknown","profile_fingerprint":null}
```

`SpatialRelations(profile)` udostępnia `site`, `approaches`, `support`,
`directions`, `forward`, `connection`. Nie wnioskuje intencji z etykiety.
Indeks rundy w `src/demos/round_index.py` jest usługą, nie dodatkową kopią źródeł.
Zwraca najnowszą próbkę <= żądany tick wraz ze świeżością; nigdy przyszłą próbkę.

## Dowody, fingerprinty i wymagania detektorów

ID źródła: `demo_id:source:source_fingerprint:index`. Indeks rozróżnia identyczne
rekordy w jednym ticku. Fingerprint pochodzi ze znormalizowanego strumienia bez
etykiet profilu. Stabilność obejmuje to samo wejście i normalizację, nie dowolną
zmianę parsera. ID wyników pochodnych mają własny etap, wersję i zależności.

| Fingerprint | Wejścia | Co unieważnia |
| --- | --- | --- |
| Źródła | demo, parser, ekstrakcja, źródłowe ramki i czas | Obserwacje i zależne etapy |
| Semantyka mapy | regiony, geometria, kierunki, podejścia, wsparcie, połączenia, capabilities i pokrycie | Lokalizacje i zależne analizy |
| Detektor | wersja, progi, wymagane źródła i semantyka, jeśli używana | Wynik detektora i agregaty |
| Prezentacja | nazwy regionów i tras, radar i transformacja | Widok |

Sama edycja `profile_version` lub tekstu opisu nie zmienia liczb. Zmiana klucza
site'u w `route_names` zmienia semantykę. Zmiana jego opisu zmienia prezentację.
Metadata nie zawiera reguł wykonywalnych. Mapowy fingerprint nie zależy od danych
gracza. Wyniki drużynowe są współdzielone między widokami zawodników.

Opening/refrag potrzebują zdarzeń i czasu. Miejsce kontaktu wymaga przypisania
lokalizacji. Wejście wymaga rozpoznawania site'ów; kierunek wejścia podejść;
wysunięcie CT oznaczeń strony. Capabilities są jawne; profil bez danej możliwości
nie może powodować pozornego wyniku zerowego. Obsługa, zgodność wersji mapy,
kompletność źródeł i wykonanie analizy są osobnymi stanami.

## Inwentarz zależności przed refactorem

M1 wdrożono: SQLite 8, obserwacje 1, zapis lokalizacji 2, fundamenty 2,
schemat taktyczny 3. Szczegóły zapisu i odbioru: [raport M1](map_independence_implementation.md).

| Miejsce | Zależność do wydzielenia |
| --- | --- |
| mirage_context.py | ZONES, blokady de_mirage, /64, klasyfikacja stanów i etykiety openingu, klucz źródeł i profilu razem |
| mirage_entries.py | ROUTES/SUPPORT, BombsiteA/B, XYZ rampy/pałacu, 8/2/0.5 s przeliczone stałą 64 |
| early_round.py | ZONES, classify_area z XYZ, blokada mapy, snapshoty /64 |
| early_interpretation.py | CT_FORWARD_PLACES, kierunek ze stringów A/B/mid, ZONES, progi ticków |
| coach_foundations.py | context_key, area/place w snapshotach, sekundy i tick_rate=64 |
| tactical_evidence.py | przestrzenne pola stanów w namespace źródeł, sekundy /64 |
| replay_effects.py / foundation_sources.py | czas lifecycle i pokrycia względem częstotliwości |
| gui/early_round_view.py | ZONES, ręczne nazwy ramp/palace, klucz session_state |
| gui/mirage_view.py / radar.py | blokada mapy, /64, obraz i transformacja mapy |
| spatial_service.py / database.py | zapis źródeł+interpretacji razem i historyczne fallbacki |

Lista dotyczy stanu przed wdrożeniem M1; integracja usuwa te zależności z warstw
wspólnych. Testy kontraktów obejmują błędne wersje i referencje, wysokość, kierunek
przejść, jawny fallback czasu, duplikaty źródłowe i rozdzielenie fingerprintów.
