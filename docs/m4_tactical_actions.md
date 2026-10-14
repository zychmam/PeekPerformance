# M4 — reguły i odbiór detektorów

Status: pierwsza implementacja M4.1–6 i techniczna integracja M4.7 (2026-10-14).
Użytkownik uznał obecną wersję za poprawną i polecił kontynuować do M5.
Dalsza kalibracja odbywa się według nowych przykładów; ograniczenia pozostają jawne.
Wyniki opisują obserwowane działania, nie intencję, widoczność ani komunikację.

## Kryteria przed implementacją

- **M4.1:** ciągłe próbki jednego regionu tworzą pobyt; przejście ma przedział
  od ostatniej próbki starego regionu do pierwszej nowego. Luka >2 s, śmierć
  i nierozpoznany region nie tworzą potwierdzonej drogi. Czas pobytu to odcinek
  obserwacji, nie dowód utrzymania kontroli. Sektor CT jest pojedynczy lub nieznany;
  wsparcie pozostaje oddzielne. Granica dolnej banana jest konserwatywna,
  wymaga wizualnej kalibracji; top mid Inferno nie oznacza automatycznie agresji.
- **M4.2:** powiązanie autora/rodzaju/czasu musi być jednoznaczne w obie strony.
  Zgodne entity ID daje mocniejszy sygnał niż sam czas. Kilka pasujących flashów
  pozostaje niejednoznacznych. Wygaśnięcie szacowane dla radaru nie staje się
  faktem. Efekt HP/flash wymaga jednoznacznego dopasowania, a nie sąsiedztwa.
  Zasoby mają wiek próbki i nie przekraczają luk; brak nie oznacza zera.
- **M4.3:** kontakty łączymy przy przerwie ≤5 s i lokalizacji ≤600 jednostek
  (3D pozycji ofiary). Bez lokalizacji wymagamy wspólnego uczestnika i oznaczamy
  częściowość. Odległe równoległe walki i ponowne walki po przerwie są osobne.
  Wymiana tych samych przeciwników pozostaje razem również na dużym dystansie.
  Obrażenia bez fraga pozostają starciem. Pierwsze fragi w tym samym ticku są
  równorzędne. HP i liczebność mają własny czas; utility w pobliżu nie jest przyczyną.
- **M4.4:** wejście na site jest mocnym sygnałem próby. Przed site'em potrzebna
  jest koncentracja T oraz walka albo skoordynowane utility i ruch. Jeden granat
  lub samo stanie na podejściu daje presję, nie potwierdzoną próbę. Rozdzielamy
  cel, czas startu, obecność na site, plant i wynik rundy. Wycofanie, zatrzymanie,
  luka i zmiana celu mają osobne zakończenia; postplant nie jest nowym atakiem.
  Krótkie/ponowne wejścia zachowujemy, bez wymogu przeżycia 0,5 s.
- **M4.5:** gracz poza koncentracją ma przedziały rozdzielenia, własne kontakty,
  rzuty i późniejsze dołączenie. Nieznana pozycja nie dowodzi rozdzielenia.
  Nie nazywamy automatycznie lurka ani przechwycenia bez kontaktu z rotującym CT.
  Koncentracja: największa jednoznaczna grupa żywych T przy celu połączonych
  odległością ≤600 jednostek; remis grup pozostawia koncentrację nieustaloną.
  Sprawdzamy ją co sekundę i przy przejściach; utrwalamy przedziały ≥1 s.
- **M4.6:** wysunięcie wymaga obserwowanego pobytu ≥1 s w zadeklarowanej strefie.
  Reakcję mierzymy względem nazwanego kontaktu lub planta; nie względem
  nieobserwowanego dostrzeżenia. Tylko żywy CT spoza obrony celu jest kandydatem.
  Ruch wcześniejszy, przybycie, śmierć i utrata pokrycia są osobne; brak rotacji
  wymaga ciągłego pokrycia. Retake wymaga postplant ruchu na site lub walki
  obrońcy z pozycji site/podejścia albo próby rozbrojenia. Sam defuse nie opisuje
  przebiegu próby, sam plant nie dowodzi jej podjęcia.

## Weryfikacja

Testy pozytywne/negatywne, luki, czas i dowody; profil syntetyczny po zmianie ID;
odczyt referencji Mirage/Inferno, regresje M3, serializacja/cache i pomiar całej mapy.
Odbiór techniczny oraz wizualna kalibracja interpretacji są odrębne.

## Implementacja

| Zadanie | Moduły i wynik |
| --- | --- |
| M4.1 | `round_movement.py`: RegionStay, RegionTransition, MovementIndex i luki. Profil: defense_sector i forward_bounds w semantycznym fingerprint. |
| M4.2 | `round_utility.py`, `round_resources.py`: rzut/efekt/wygaśnięcie, kandydaci dopasowania, mierzalne efekty i zasoby HP/życie/wyposażenie/bomba. |
| M4.3 | `round_fights.py`: epizody, równorzędne pierwsze fragi, obrażenia/zgony/refragi, zasoby przed/po, efekty utility osobno od kontekstu. |
| M4.4 | `round_attacks.py`: presja/próba, kolejne cele, krótkie/ponowne wejścia, zatrzymanie/wycofanie/luka, zasoby, czasy startu/wejścia. |
| M4.5 | Dynamiczna koncentracja i przedziały rozdzielenia, kontakty, rzuty, dołączenie i kontakt z obserwowanym rotującym CT. |
| M4.6 | `round_defense.py`: obecność/wysunięcie/wycofanie, utility i kontakty, okazje do reakcji, przybycia/braki/pokrycie, próba i wynik retake. |
| M4.7 | `tactical_actions.py`, `round_tactical_view.py`: SQLite per runda, wersje, cztery zakładki, tekst, dowody/skoki i wspólna analiza wszystkich graczy. |

Reakcja odnosi się do kontaktu ogniowego przy celu, kontaktu kolejnej próby lub
planta. Czas startu jest granicą wyjścia z sektora, nie detekcją pierwszego kroku
w jego obrębie. Wcześniejszy ruch jest osobny. `rotation_eligibility` zachowuje
przypadki uprawnione, już obecne, martwe i nieznane dla poprawnych mianowników M5.

Postój to prędkość ≤32 jednostek/s wskazanego zawodnika odniesienia, nie styl
drużyny. Czas pobytu w regionie jest osobną miarą. Koniec próby oznacza koniec
obserwowanej aktywności; wycofanie potwierdzamy po 3 s braku głównej grupy przy celu,
z uwzględnieniem zgonów. Pozostawiony gracz nie utrzymuje sztucznie starej próby.

SQLite `tactical_actions` zapisuje wynik strukturalny bez tekstu i ciężkiej
trajektorii. Klucz uwzględnia źródła, fundamenty, semantykę profilu, schemat,
wersje detektorów i parametry. Zapis kolejnej rundy zachowuje inne rundy;
zmiana gracza używa tej samej analizy.

## Granice pierwszej wersji i odbiór M4.7

- Inferno ma głównie regiony nawigacyjne. Granat o znanych XYZ może nie mieć
  regionu. Nie zgadujemy najbliższego site'u; pełniejsza geometria wymaga kalibracji.
- Sprawdzone trajektorie mają `grenade_entity_id`, autora, tick i XYZ; rzuty
  `weapon_fire` rzeczywistych dem nie mają entity ID. Etap źródeł nie przechowuje
  indeksu powiązań z trajektoriami. Wieloznaczne pary pozostają jawne; kompaktowy
  indeks warto dołożyć po pokazaniu przykładu, w którym daje poprawne rozstrzygnięcie.
- Powiązanie utility z uczestnikiem próby nie dowodzi rzutu pod site, a punkt
  efektu blisko walki nie dowodzi przyczyny zdobycia obszaru.
- Nie rekonstruujemy komunikacji, pełnej widoczności ani świadomej adaptacji.
  Progi prób/koncentracji i dolnej banana wymagają przeglądu obu map na radarze.
- Naprawiona regresja M3: zabójstwo po własnej śmierci nie jest refragiem kolegi.

UI: **Kontekst rundy → Działania taktyczne** — Ataki T / Obrona CT / Walki
i utility / Ruch gracza, z dowodami i skokami na istniejący radar.

Weryfikacja źródłowa `scripts/verify_m4_actions.py`: wszystkie **41 rund**,
zgodny zapis/odczyt wyników i pominięcie detektorów M4 przy odczycie cache,
bez parsera. Mirage: przygotowanie/obliczenia **8,59 s**, ponowny pełny przepływ
**8,26 s**, wynik M4 **5,49 MiB**; Inferno: **9,97 s / 9,72 s / 6,09 MiB**.
Pomiar po przygotowaniu nowych profili przestrzennych. Odczyt nadal buduje M3
ze źródeł; nie jest to czas samej agregacji M5 ani całego UI. Referencje M3
oraz testy syntetyczne nie potwierdzają automatycznie wszystkich interpretacji M4.

Końcowy przebieg testów: **221 passed, 2 skipped**, w tym 21 przypadków M4;
Ruff nowych modułów przechodzi. Osiem podsumowań referencyjnych M3 po rozszerzeniu:
**0,83–1,26 s/rundę**, z dowodami i projekcją dla wszystkich graczy, bez parsera.
