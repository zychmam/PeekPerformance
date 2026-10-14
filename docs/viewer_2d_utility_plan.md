# V2D — rzuty granatów i oślepienie w viewerze 2D

Status: **V2D.1–5 wdrożone w zakresie potwierdzonym przez audyt**: rzuty/loty
oraz oznaczenie deklarowanego efektu flasha. Dokładna pełna faza pozostaje
nieustalona; nie prezentujemy jej jako zmierzonej.
Poboczny epik przed M6. Ręczny odbiór wyglądu i płynności pozostaje otwarty.
[Wyniki i decyzja o flashu](v2d_source_audit.md), [odczyty](v2d_source_audit.json).
[Weryfikacja rzeczywistych lotów i cache](v2d_projectiles_verification.json).

**Korekta po audycie:** obecne dane pozwalają pokazać deklarowane okno efektu
flasha, ale nie dokładną fazę pełnego braku widzenia. V2D.3 przygotuje ten
pierwszy wariant z przerywaną obwódką i jawną legendą. Pełna faza pozostaje
null; gęstsze próbkowanie `flash_duration`/`flash_max_alpha` jej nie ujawni.
V2D.2/V2D.4 wykorzystają `parse_grenades(grenades=False)` dla nowych odczytów:
potwierdzono 87–91% mniej wierszy na sprawdzonych demach (w zaokrągleniu).

## Efekt dla użytkownika

W odtwarzaniu rundy widać, kto i kiedy rzucił granat, jego obserwowany lot
oraz miejsce zadziałania. Przy oślepionym graczu pojawia się obwódka związana
z czasem gry. Pauza, cofanie, zmiana szybkości i skoki do zdarzeń odtwarzają
ten sam stan. Działa wspólnie na Mirage, Inferno, Dust2 i Anubis.

## Co już mamy, czego brakuje

| Źródło / element | Obecny stan | Zastosowanie |
| --- | --- | --- |
| `observations.throws` | Rzuty z `weapon_fire`: tick, zawodnik, typ, pozycja i strona. | Sygnał wypuszczenia granatu przy zawodniku. |
| `analysis.grenades_df` | Surowe trajektorie: `grenade_entity_id`, `grenade_type`, `tick`, x/y/z, `steamid`. W sprawdzonym demie ponad 1,3 mln wierszy, część pozycji null. | Lot pocisku; wymaga przygotowania i indeksowania. |
| `utility_lifecycles` | Efekty i ich cykl, identyfikatory encji; obecne dopasowanie rzutu do efektu jest ograniczone czasowo i jawnie niepewne. | Koniec lotu, powiązanie z detonacją/smoke'em. |
| `player_blinds_df` | Tick, trafiony, rzucający, `blind_duration`, encja, strony. | Zdarzenie flasha; samo nie potwierdza czasu całkowitego braku widzenia. |
| Stany zawodników | Pozycje około 0,1 s; główny ekstraktor obserwacji nie pobiera parametrów flasha. Starsza metoda `get_player_states` prosi o `flash_duration`. | W V2D.1 sprawdzić dostępność i semantykę parametrów oślepienia. |
| Viewer | Canvas/JS, czas lokalny, smoke'y, detonacje, strzały, poziomy mapy. Wybrany zawodnik ma białą obwódkę. | Reużycie renderera i sterowania; zmiana oznaczenia wyboru, by nie kolidował z flashem. |

## 1. Rzut i lot granatu

1. W ticku rzutu krótki impuls przy pozycji rzucającego i mała ikona typu granatu.
   Wizualny impuls około 0,35 s; to oznaczenie zdarzenia, nie czas czynności.
2. W locie mała ikona pocisku z oznaczeniem typu i krótkim, gasnącym śladem
   z ostatnich około 0,5 s. Kolor strony rzucającego; litera/symbol rozróżnia
   smoke, flash, HE, ogień i decoy bez polegania wyłącznie na kolorze.
3. Tor pochodzi z pozycji granatu. Interpolacja tylko między bliskimi, ciągłymi
   próbkami. Nie rysujemy wymyślonego łuku od gracza do detonacji ani pełnej
   linii lotu przez całą rundę. Brak fragmentu toru oznacza przerwę w animacji.
4. Po potwierdzonym końcu lotu znika pocisk; działa obecna warstwa detonacji
   i aktywnych smoke'ów. Brak potwierdzenia końca nie daje wymyślonej detonacji.
5. Rzut bez trajektorii nadal ma impuls i wpis zdarzenia. Tor bez znanego
   rzucającego można pokazać jako neutralny; nie przypisujemy go najbliższemu graczowi.
6. Lista zdarzeń: np. `12,35 s · nick rzuca flash`. Skok ustawia czas tuż
   przed rzutem. Domyślnie widoczne wszystkie rzuty; przełącznik warstwy
   oraz opcja ograniczenia do wybranego gracza, bez przeładowania Streamlit.

Powiązania opierają się na rundzie, cyklu życia encji, typie i właścicielu.
Samo `entityid` nie wystarcza, bo encje mogą być ponownie użyte. Dopasowanie
czasowe nie staje się potwierdzonym powiązaniem. Nie poprawiamy go zgadywaniem
przy dwóch kolejnych flashach tego samego zawodnika.

## 2. Oślepienie zawodnika

**Cel:** ciągła biała obwódka przez potwierdzony okres pełnego oślepienia,
następnie osłabienie oznaczenia podczas potwierdzonego wygaszania efektu.

- Osobna zewnętrzna biała obwódka; kolor T/CT postaci pozostaje widoczny.
  Zaznaczenie wybranego gracza zmienia się na wewnętrzną turkusową obwódkę.
- Obwódka podąża za graczem, znika po śmierci i nie zostaje na ostatniej
  znanej pozycji przy luce. Na liście graczy pozostaje dostępny status flasha.
- Użytkownik może wyłączyć warstwę. Lista zdarzeń pokazuje trafienie flashem,
  rzucającego, jeśli jest znany, i rozpoznany rodzaj danych o czasie.
- Oślepienie własnym flashem i flashem kolegi jest również pokazywane.
- Kolejne flashe nie sumują automatycznie czasów. Stany efektu mają pierwszeństwo;
  ewentualne przedziały nakładających się zdarzeń są łączone, bez zliczania overlapu dwa razy.

### Warunek poprawnej interpretacji

V2D.1 sprawdzi pola rzeczywiście dostępne w zainstalowanym parserze i demach:
czas początku/końca, czas trwania, parametry intensywności i ich znaczenie.
Sama dostępność pola o nazwie alpha nie dowodzi chwilowej nieprzezroczystości
ekranu; trzeba odróżnić maksymalną intensywność od wartości w danym momencie.

Jeżeli potrafimy odtworzyć pełną fazę, zachowujemy osobne przedziały
`full_blind` i `recovering`, ich źródła i dokładność czasową. Próbkowanie
około 0,1 s daje granice z taką dokładnością; nie przedstawiamy ich jako
dokładnych ticków. Gdy trzeba, doczytujemy gęściej wyłącznie okolice flasha.

Jeżeli mamy tylko `player_blind + blind_duration`, możemy pokazać przerywaną
obwódkę „zarejestrowany efekt flasha” w przedziale wynikającym ze zdarzenia,
po sprawdzeniu semantyki duration. `full_blind_end_tick` pozostaje null.
Nie podpisujemy takiej obwódki „nic nie widział”. Jest to ograniczona wersja
funkcji, a nie spełnienie wymagania dokładnego czasu pełnego oślepienia.
Wynik V2D.1 rozstrzyga wykonalność pełnej wersji przed jej implementacją.

## 3. Kontrakt i wydajność

Dwa oddzielne, wersjonowane zbiory prezentacyjne:

- `projectiles`: ID cyklu, runda, typ, rzucający/strona lub null,
  tick rzutu, źródła, status powiązania, próbki `[tick,x,y,z]`, obserwowany
  koniec lotu i powiązanie z efektem lub null.
- `blind_intervals`: gracz, runda, start, koniec efektu, osobna granica
  pełnego oślepienia lub null, rodzaj fazy, pochodzenie, status, dokładność
  czasowa i referencje do zdarzeń. Intensywność tylko gdy wynika z danych.

Tick jest podstawą zapisu. Sekundy dla JS liczymy z zegara rundy i jej tick rate.
Brak zegara/pozycji/typu pozostaje jawny; nie tworzymy zdarzeń w czasie 0.
Przedziały renderujemy jako `[start,end)`, obcinając prezentację do aktywnej rundy.

- Przygotowanie raz na demo, zapis etapem/per runda w SQLite. Klucz obejmuje
  źródła, parser i wersję normalizacji, niezależnie od profilu mapy.
- Przy zmianie rundy przekazujemy wyłącznie jej trajektorie i przedziały.
  Surowe milionowe `grenades_df` nie może być ponownie ładowane/dekodowane
  przez normalną ścieżkę otwarcia meczu lub zmiany rundy. Zaplanować mały
  odczyt analizy bez tej kolumny; surowe dane czytać tylko podczas przygotowania.
- Ograniczenie próbek lotu do około 0,1 s z zachowaniem początku, końca
  i istotnych zmian toru; sprawdzić błąd redukcji, by nie prostować odbić.
  Nie zmieniamy przy tym próbkowania pozycji zawodników.
- JS indeksuje przedziały i używa wyszukiwania próbek; nie przechodzi
  wszystkich trajektorii meczu w każdej klatce. Stan wynika z czasu rundy,
  nie z timeoutów uruchomionych przy odtwarzaniu.
- Profil dostarcza wyłącznie przeliczenie współrzędnych i poziomy mapy.
  Poziom pocisku wynika z jego z, niezależnie od poziomu rzucającego.
  Nieznany poziom nie jest rysowany arbitralnie na wybranym piętrze.
- Dla istniejących dem najpierw wykorzystujemy zapisane źródła. Jeśli pełne
  oślepienie wymaga nowych pól, doczytujemy tylko potrzebne dane z oryginału
  i zapisujemy nowy etap; brak pliku źródłowego daje jawne ograniczenie.
  Bez migracji starych analiz i bez globalnego resetu M3–M5.
- W tym epiku nie dokładamy ocen „dobry flash”, nowych detektorów taktycznych
  ani pełnych trajektorii do eksportu dla LLM. Dane o fazach zachowujemy
  z referencjami, żeby mogły później zasilać analizę.

## 4. Dekompozycja

| ID | Zadanie i rezultat | Złożoność | Zależności |
| --- | --- | --- | --- |
| V2D.1 | **Audyt techniczny wykonany:** 797 zdarzeń na czterech mapach, 20 okien co tick, rzeczywiste trajektorie i próbki powiązań. Dokładna pełna faza flasha niedostępna w sprawdzonych źródłach; POV nieporównane. Wszystkie cykle/powiązania będą weryfikowane podczas V2D.2. | 3/5 | Obecne dema i parser |
| V2D.2 | **Wdrożone:** rzeczywiste tory, segmentacja ponownie użytych encji/przerw/skoków, zachowanie ostrych zmian kierunku przy redukcji próbek. Koniec lotu według efektu zgodnego z encją/typem/właścicielem lub ostatniej próbki; brak wymyślonych powiązań z rzutem. | 3/5 | V2D.1 |
| V2D.3 | **Wdrożone:** deklarowane okna efektu, suma przedziałów zamiast sumowania czasu flashów, granice życia/rundy, braki duration bez wymyślania czasu. Pełna faza/intensywność nieustalone. | 3/5 | V2D.1 |
| V2D.4 | **Wdrożone:** etap torów `viewer_projectiles` per runda, UI bez surowych trajektorii. Flash korzysta z już zapisanych małych źródeł; tania projekcja jednej rundy bez nowego cache, parsera i I/O. | 3/5 | V2D.2–3 |
| V2D.5 | **Wdrożone:** impuls/lot/ślad granatów oraz biała przerywana obwódka i FLASH z pozostałym czasem na liście graczy. Wybrany gracz ma turkusową obwódkę. Obie warstwy domyślnie włączone; zdarzenia, legenda i seek. | 3/5 | V2D.4 |
| V2D.6 | **Częściowo:** regresje danych i rzeczywistego JS dla granatów/flasha, kontrola pięciu dem/czterech map bez parsera. Wizualny odbiór/FPS pozostaje otwarty, podobnie jak dokładna pełna faza. | 3/5 | V2D.1–5 |

Kolejność: **V2D.1 → V2D.2/V2D.3 → V2D.4 → V2D.5 → V2D.6**.

## 5. Warunki odbioru

- Można wskazać rzucającego, śledzić rzeczywisty tor i zobaczyć efekt granatu.
- Dwa szybkie rzuty tej samej osoby oraz ponowne użycie ID nie mieszają torów.
- Flash ma początek/koniec zgodny z potwierdzonym źródłem; brak danych o pełnej
  fazie jest widoczny. Przerywana obwódka nie udaje pełnego oślepienia.
- Ten sam czas daje ten sam obraz po pauzie, seeku w obie strony i przy ×0,5/×4.
- Sprawdzić także samoflash/teamflash, nakładanie flashów, śmierć, luki,
  brak czasu trwania, nieznany rzucający i zmianę poziomu.
- Co najmniej jedna rzeczywista runda na każdej mapie; co najmniej jeden
  ciągły lot z odbiciem i jeden przypadek ponownego oślepienia. Referencje
  liczone z danych oraz ręczna kontrola w replayu gry, gdy jest dostępny.
- Otwarcie przygotowanej rundy bez parsera i bez surowego odczytu trajektorii.
  Zmierzyć payload, czas zimnego przygotowania, ciepłego odczytu i koszt
  renderowania. Cel ciepłego odczytu wraz z projekcją: poniżej 0,5 s lokalnie;
  cel renderera: co najmniej 30 FPS na urządzeniu użytkownika, także w rundzie
  z największą liczbą granatów. To cele do pomiaru, nie obecne wyniki.
- Dotychczasowe smoke'y, strzały, ruch i nawigacja nadal działają.

Pełne wymaganie „obwódka tak długo, jak gracz nic nie widział” uznajemy za
zrealizowane dopiero po potwierdzeniu źródła i sprawdzeniu fazy pełnego flasha.
Implementacja samego czasu zdarzenia nie zamyka tej części odbioru.

## Wdrożenie granatów — 2026-10-14

W analizie rundy, na radarze: **Rzuty i lot granatów** (domyślnie włączone).
Przy wypuszczeniu widać impuls, ikonę typu i napis RZUT; podczas lotu ikonę
F/H/S/M/D i ślad z ostatnich 0,55 s. Lista zdarzeń zawiera nick rzucającego.
Można ograniczyć warstwę do wybranego gracza. Dym nadal renderuje istniejąca
warstwa smoke'ów, a pocisk znika przy potwierdzonej detonacji.

Przygotowano i zapisano tory całych pięciu lokalnych meczów. Kontrola rundy 2:
Mirage (nowsze demo) 14 lotów, Dust2 9, Inferno 13, Anubis 10,
Mirage (wcześniejsze demo) 11. Ciepły odczyt wraz z budową całego payloadu
viewera: **0,054–0,161 s** lokalnie. Zimne przygotowanie torów całego meczu
oraz payloadu wybranej rundy: **3,9–6,2 s** z zapisanych danych, bez parsera.
Nie są to pomiary FPS przeglądarki; pełny payload nadal zawiera stany zawodników.

Skrypt kontroli: `scripts/verify_viewer_projectiles.py`. Nie otwiera przeglądarki.
Testy JS wykonują rzeczywisty renderer i sprawdzają rzut/lot, cofanie,
interpolację, przerwy w próbkach i wyłączenie warstwy. Testy normalizacji
obejmują odbicie, ponowne użycie encji i smoke pozostający po zakończeniu lotu.

Pełna regresja po wdrożeniu: **298 zaliczonych, 2 opcjonalne pominięte**.
Ruff zmienionych modułów viewera/cache, testów i skryptu przechodzi.
Aplikacja zrestartowana; endpoint zdrowia zwraca HTTP 200.

## Wdrożenie oznaczenia flasha — 2026-10-15

Warstwa **Efekt flasha** jest domyślnie włączona. Gracz trafiony flashem ma
białą przerywaną obwódkę oraz napis FLASH; lista graczy pokazuje pozostały
czas deklarowanego okna. Turkus oznacza wybór gracza. Oznaczenie jest liczone
z czasu rundy, więc pauza/cofanie/zmiana szybkości zachowują stan.

Zdarzenia sprzed freeze, trafienia od chwili śmierci i brakujący/niepoprawny
duration nie tworzą przedziału. Przy nieznanym duration pozostaje wpis
zdarzenia. Przedziały są obcinane do śmierci i końca rundy. Nakładające się
okna są łączone do wizualizacji, a każde trafienie pozostaje osobnym zdarzeniem.
Przy braku pozycji nie rysujemy obwódki na starej pozycji.

Kontrola rzeczywistej rundy 2: nowszy Mirage 3 oznaczanych graczy, Dust2 6,
Inferno 3, Anubis 6, wcześniejszy Mirage 5. Przygotowanie payloadu z cache
zajmuje około 0,04–0,09 s lokalnie. Nie wykonano przeglądarkowego pomiaru FPS
ani porównania pełnej fazy z POV w grze. Deklarowany efekt nie jest oznaczany
jako potwierdzona całkowita ślepota.

Regresja po dodaniu flasha: **307 zaliczonych, 2 opcjonalne pominięte**.
Sprawdzono rzeczywisty JS: granice przedziału, cofanie, wyłączenie warstwy,
status na liście oraz brak obwódki po śmierci. Aplikacja zrestartowana.
