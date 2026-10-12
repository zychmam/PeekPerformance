# Model rundy taktycznej — R1/E1/M3.1, schemat 4

M3.1 dodał wąskie rekordy `Contact`, `RefragLink`, `AliveState`, `RoundMoment`
oraz `PositionReference`. Na razie listy wyników pozostają puste; detektory
powstają w M3.2–3. `PlayerRound.first_contact_id` odnosi się do wyliczonego
`Contact`, a nie bezpośrednio do zdarzenia źródłowego. Każdy taki kontakt
wskazuje surowe `Evidence`. `derived_id` buduje stabilne ID z numeru rundy,
rodzaju i kanonicznych ID źródeł. Odczyt starszego schematu taktycznego nie
jest wspierany; analizę można odtworzyć z zachowanych źródeł.

Aktualizacja 2026-10-12: `RoundTactics.foundation` zawiera dane E1;
`Preparation` ma ustawienie przed kontaktem oraz osobne okna rzutów/efektów.
Adapter korzysta ze wspólnego rejestru `tactical_evidence.py`. Nowy model
powstaje z zachowanych źródeł; starszy zapis kontraktu nie jest odczytywany. Szczegóły:
[dane coacha E1](coach_foundations.md).

## Cel i granica tej implementacji

Model odpowiada sześciu pytaniom użytkownika: przygotowanie T (early utility),
ustawienie/aktywność CT, inicjacja walki i refragi, efekt walki, atak/plant,
odpowiedź CT i retake. Nie uruchamia nowych detektorów strategii. Zbiera dowody,
przenosi istniejące wejścia i przygotowuje miejsce na wyniki R2–R6.

Kod: `src/models/tactical.py`, adapter `src/demos/tactical_rounds.py`.

## Struktura

`TacticalMatch` zawiera identyfikator dema, wersję wejścia i schematu, parametry,
rejestr dowodów, drużyny oraz rundy. Każde `RoundTactics` zawiera:

| Pole | Przeznaczenie |
| --- | --- |
| t_preparation | Early rozstawienie i utility T; docelowo tempo, formacja, cele, oddzielony gracz |
| ct_setup | Early ustawienie i aktywność CT; docelowo wysunięcia i cofnięcia |
| fights | Epizody: początek, entry, utility, obrażenia, refragi, stan przed/po i zmiany przestrzeni |
| attacks | Próby ataku, także zatrzymane przed wejściem; cel, fale wejścia, uczestnicy, plant i rezultat |
| observed_entries | Obecne przekroczenia strefy site'u; nie są automatycznie próbami ataku |
| rotations | Trasa, rozpoczęcie, dotarcie i jawny sygnał odniesienia; bez domysłów o voice comms |
| bomb_event_ids | Plant/defuse oraz dostępne zdarzenia pickup/drop, rozpoczęcia prób i eksplozji z E1 |
| foundation | Wyposażenie, źródła bomby/strzałów/utility, odniesienia kontaktu i jakość danych E1 |
| retake | Osobna próba i jej rezultat; zwycięstwo rundy samo nie określa próby |
| team_findings | Wnioski o obu drużynach |
| players | Osobna perspektywa każdego gracza: kontakt, epizody, utility i wnioski |

Pojedynczy `Finding` musi wskazywać dowody i odróżnia obserwację od interpretacji.
`Episode` ma ID, przedział ticków, uczestników, obszar i powiązania. Nie zakładamy
jednego starcia ani jednego celu na rundę. Wycofanie i zmiana celu mogą łączyć
kilka `Attack`; nieudana próba może nie mieć żadnego `observed_entry`.

Stan rezultatu jest osobny od dostępności źródeł:

- `observed`: jest obserwacja; nie oznacza bezbłędnego ani kompletnego parsera.
- `verified_absent`: potwierdzony brak przy poprawnie odczytanym źródle.
- `partial`: tylko część wymaganych danych; np. brak gracza albo luka w próbkach.
- `unknown`: nie można ustalić.
- `not_applicable`: dany element nie dotyczy sytuacji; wymaga potwierdzenia warunku.
- `not_evaluated`: jeszcze nie uruchomiono odpowiedniej analizy.

Puste listy fights/attacks/rotations mają osobne statusy `not_evaluated`.
Nie są komunikatem „nie było walki”. Brak eventu plant w starym cache nie dowodzi
braku planta. Dlatego adapter nie nadaje sam `not_applicable` retake'owi.

## Wspólne źródła i czas (R1.2)

`load_tactical_match(db, demo_id)` czyta lekką analizę i istniejący spatial cache.
Nie otwiera pliku demo, nie uruchamia API i nie zmienia bazy.
`build_tactical_match(analysis, spatial)` umożliwia użycie już wczytanych danych.

Każdy `Evidence` ma źródło, rundę, tick, czas od freeze-end i pierwotne pola.
Bez freeze-end czas w sekundach pozostaje nieznany. Zachowujemy ticki.
Wspólny tick różnych strumieni nie daje dowodu ich kolejności przyczynowej.
IDs zdarzeń coacha są zachowane. Dodatkowe źródła otrzymują deterministyczne ID
z hasha dema, źródła, kanonicznej zawartości i kolejności rekordów.
SteamID to tekst; null pozostaje null. JSON nie zawiera NaN.

Parametry: early 15 s (także granica 10 s), odpowiedź na starcie 10 s,
fala wejścia 8 s, założenie 64 ticków/s. Granice early są obcięte końcem rundy.
To definicje analizy, nie zmiana dotychczasowej pięciosekundowej metryki trade.
Adapter przypisuje wczesne próbki i utility do T/CT, ale nie nazywa strategii.

Trwałe drużyny identyfikujemy po pierwszym kompletnym, rozłącznym składzie 5v5.
Ten sam skład po drugiej stronie zachowuje `team_id`. Zastępstwa i niepełne
składy pozostają niejednoznaczne; nie zgadujemy przynależności na podstawie nicka.
Identyfikatory team_1/team_2 są lokalne dla meczu, nie globalne między meczami.

## Kompletność (R1.3)

Każda runda ma manifest dla kills, damage, blinds, utility, states, bombs,
zegara, tożsamości drużyn, widoczności i historii bomby. Sprawdzamy wymagane
kolumny, null oraz pokrycie próbkami względem rosteru i czasu aktywnej rundy.
Luki ponad 2 s i brak zawodników obniżają status stanów do `partial`.

`capabilities` zestawia wymagania modułów: early preparation, fights,
utility effects, entry context, rotation from contact, plant/defuse i retake.
Informuje o dostępności wejścia, nie o poprawności ani wykonaniu detektora.

Poprawnie zdiagnozowane źródła utility pozwalają potwierdzić pusty wynik.
Dla starych zdarzeń walki/bomby pusta tabela pozostaje `unknown`.
Widoczność nie jest zbierana. Historia bomby ma najwyżej częściowe pokrycie:
nosiciel oraz plant/defuse, bez utrwalonych pickup/drop.

## Referencje (R1.4)

`tests/reference/mirage_tactical_facts.json`: zanonimizowany wyciąg rund
1, 6, 13 i 20 z dostarczonego Mirage, z wybranymi próbkami pozycji.
To celowo niepełna próbka przestrzenna — manifest powinien to wykryć.
`mirage_tactical_expectations.json`: osobno wpisane, ręcznie sprawdzone ticki
i rezultaty wraz z zakresem kontroli i listą luk. Oczekiwań nie generuje adapter.

- Runda 1: opening 7802, refrag 7874 (72 ticki = 1,125 s), plant 8436, defuse 9671.
- Runda 6: plant 35062, koniec wybuchem 37686; sam wynik nie potwierdza próby retake'u.
- Runda 13: zmiana stron zachowuje drużyny; opening 71380, refrag 71436.
- Runda 20: plant 106815, defuse 108640; refrag po 16 tickach.

Kontrola jest oparta na eksporcie parsera, nie niezależnym odtworzeniu w grze.
Otwarte, jawnie zapisane przykłady: start/koniec rotacji, etykiety nieudanej próby
ataku, retake z początkiem, split/lurker/zmiana celu i równoległe starcia.
Nie przedstawiamy tych detektorów jako zweryfikowanych. Model potrafi zapisać
nieudaną próbę bez wejścia i nieznany wynik; pokrywają to testy kontrolowane.

## Wydajność i agregacje

Jeden rejestr dowodów jest wspólny dla graczy i raportu drużynowego. Nowe wyniki
odwołują się do źródeł przez ID. Pełny model jest wewnętrznym dokumentem audytowym,
nie payloadem LLM; pakiet API będzie osobną, ograniczoną projekcją.
Na lokalnym cache Mirage: 21 rund, 18 168 dowodów, 26 istniejących wejść;
pojedynczy pomiar budowy ok. 0,73 s (nie jest to gwarantowany budżet wydajności).

Późniejsze podsumowanie mapy będzie liczyło próby, wejścia, planty i zwycięstwa
osobno; przy formacji liczbę uczestników odnosimy do żywych T na początku akcji.
Brak detekcji próby ataku uniemożliwia obecnie uczciwe policzenie takiej skuteczności.
Tempo, rozłożenie, utility i kierunki są wymiarami strategii; nie wymuszamy
rozłącznej etykiety rush/execute/default.
