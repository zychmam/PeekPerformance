# Kontekst Mirage — pierwsza wersja

Aktualny kontekst: **v6**, SQLite 7 (2026-10-12). Dane coacha, wyposażenie,
rozszerzona historia bomby i ustawienie przed kontaktem:
[wdrożenie E1](coach_foundations.md). Sekcje v3–v5 poniżej opisują wcześniejsze
etapy rozwoju odtwarzacza.

## Uruchomienie

Wybierz zapisany mecz `de_mirage`, sekcję **Kontekst mapy** i przycisk
**Przygotuj kontekst Mirage**. Pierwsze wywołanie pobiera dane z lokalnego dema;
kolejne odczytują SQLite. Zmiana gracza korzysta z tego samego wyniku.

## Zakres zaimplementowany

- Zegar każdej ukończonej rundy oparty na rzeczywistym `round_freeze_end`.
  Bez tego eventu brak rozpoznania fazy early; nie zgadujemy z długości freeze time.
- Pozycje XYZ, HP, życie, strona i nazwa strefy wszystkich graczy co 6 ticków,
  dodatkowo w tickach obrażeń, zabójstw, bezpośrednio przed nimi i na końcu rundy.
  Przelicznik 64 ticki/s jest
  jawnym założeniem. Stan w ticku zabójstwa może już oznaczać śmierć ofiary.
- Opcjonalny ekwipunek, kierunek patrzenia i identyfikacja nosiciela C4.
  Bombę pokazujemy przy nosicielu; brak gwiazdki nie oznacza braku bomby w rundzie.
  E1 zapisuje również zdarzenia podnoszenia/upuszczania i plant/defuse;
  ciągłe położenie upuszczonej bomby pozostaje do rozwinięcia.
- Smoke/flash/HE: punkt detonacji; ogień: punkt `inferno_startburn`.
  Są to miejsca działania, nie pozycje rzucającego i nie pełne obszary oddziaływania.
  Raport R2: przedział 0–15 s od końca freeze time oraz osobne okno 0–10 s.
- Zestawienie żywych CT/T w strefach w 12. sekundzie, suwak obserwacji w rundzie,
  pierwsze obrażenia przeciwnika, opening oraz strefy zabójcy i ofiary openingu.
  Snapshot nie przenosi gracza ze starej próbki ani sprzed śmierci.
- Profil zawodnika: pozycja w 12. sekundzie, jedna obserwacja na rundę, osobno T/CT.
  To profil konkretnego punktu czasowego, nie etykieta stałej roli.
- Podkład radarowy i stałe proporcje osi świata. Źródło i transformacja:
  [opis zasobów](../src/assets/maps/README.md).
- Tabela SQLite `demo_spatial_context` i tabele E1 per runda; migracje do 7 bez
  usuwania meczów od schematu demo-only.
  Cache zależy od dema, wersji wejścia, modułu i zdarzeń; zastąpienie analizy
  lub usunięcie meczu usuwa jej kontekst. Brak parsera/API na trafieniu w cache.

## Model stref i ograniczenia

Strefy pochodzą z `last_place_name` parsera, czyli nazw nawigacyjnych gry.
Znane etykiety Mirage mają nazwy polskie; nieznana etykieta pozostaje nieznana.
Nie dopasowujemy współrzędnych do wymyślonych prostokątów. `last_place_name`
może oznaczać ostatnią rozpoznaną strefę, dlatego nie zastępuje modelu geometrii.

Site A/B, podejścia, mid, spawn i łączniki są osobne. Connector, short, jungle,
market i van nie są automatycznie przypisywane do liczby obrońców site'u.
Liczby w widoku opisują obserwowanych żywych graczy, nie ukryte intencje drużyn.

Na radarze wszystkie early granaty są pokazane razem; opis wyjaśnia, że nie są to
aktywne granaty dla aktualnej wartości suwaka. Dwa poziomy w jednym XY wymagają
sprawdzenia Z (dostępne w podpowiedzi). Nie ma jeszcze polygonów i warstw wysokości,
widoczności, zasięgów granatów ani automatycznego dopasowania do wersji geometrii mapy.

## Test rzeczywisty

Lokalne demo: `1-2826a5a8-a40f-4b7f-8654-daf5abb2289b-1-1.dem.zst`, Mirage,
patch 14189. Pierwszy przebieg: **21 rund, 16 930 próbek pozycji, 267 zdarzeń utility**.
Wszystkie rundy mają freeze-end, wszystkie odczytane nazwy stref zostały rozpoznane,
ekwipunek zawiera C4. Test sprawdza również zapis/odczyt cache bez otwierania dema.
To walidacja techniczna; przypisanie ról i zamiarów wymaga ręcznego przeglądu rund.

Testy `tests/test_mirage_context.py`: śmierć i brak starej próbki, zmiana stron,
łącznik zamiast arbitralnego A/B, brak freeze-end, cache i jego unieważnienie,
renderowanie Streamlit oraz opcjonalny E2E (`PEEK_MIRAGE_DEMO`).

## Animacja radaru — kontekst v3

Aktualna wersja zapisuje pozycje co **16 ticków / 0,25 s**, dodatkowo w tickach
kontaktów. Zmiana wersji unieważnia dotychczasowy cache; pierwsze przygotowanie
wymaga oryginalnego dema, kolejne korzystają z SQLite. Realny Mirage ma teraz
**49 870 próbek**, 21 rund i 267 zdarzeń utility. Starsze liczby powyżej opisują v2.

Radar jest lokalnym komponentem HTML/canvas, otrzymującym wyłącznie wybraną
rundę. Play/pause, przewijanie, krok ±0,25 s i prędkości ×0,5/×1/×2/×4 nie
wykonują rerun Streamlit, nie parsują dema i nie wywołują API. Dostępny jest
wybór zdarzenia: frag, plant, defuse, wybuch. Przyciski istniejących wejść i
ustawień early round ustawiają początek odtwarzacza. Runda startuje od 0 s.

Domyślnie pozycje są ostatnimi zaobserwowanymi próbkami. Opcjonalne wygładzenie
interpoluje tylko XY między pobliskimi próbkami żywego gracza tej samej strony,
przy małej zmianie wysokości i dystansu. To efekt wizualny, bez gwarancji
przebiegu przez geometrię mapy. Luki nie są interpolowane; stara pozycja znika.
Śmierć z eventu kill usuwa gracza dokładnie w jego ticku, nawet gdy próbka stanów
jeszcze wskazuje życie. Nicki, HP, strefa, nosiciel i kierunek patrzenia są
zsynchronizowane z ostatnią próbką; lista fragów i bomby z czasami eventów.
Brak ciągłej historii upuszczonej/podłożonej bomby pozostaje ograniczeniem.

Utility na animacji to wyłącznie punkty detonacji/startu ognia z ostatniej 1 s,
bez przewidywania przyszłych granatów ani udawania aktywnych smoke'ów/obszarów.
Tabela utility pod radarem zachowuje osobno podpisane okno 0–15 s lub przed wejściem.
Radar XY nie rozdziela pięter. Pełne SteamID nie trafiają do payloadu odtwarzacza;
nicki są danymi tekstowymi, zasoby lokalne, bez zewnętrznych skryptów/CDN.

Odbiór: 111 testów zaliczonych, 1 opcjonalny pominięty, w tym pełne parsowanie
realnego Mirage i osadzenie komponentu w Streamlit. Rzeczywisty skrypt JS
sprawdzony w Node z atrapą DOM/canvas: sterowanie, prędkość, śmierć, luki,
interpolacja i ostatnia klatka. Dostępna sesja computer-use nie udostępniała
przeglądarki, więc wizualny odbiór w rzeczywistej przeglądarce pozostaje otwarty.

## Smoke’y i błyski strzałów — kontekst v5

Próbkowanie pozostaje co 6 ticków (**0,09375 s**, około 0,1 s). Nowy cache
przechowuje osobne ramki `smokes` i `shots`; starsze payloady odczytują je jako
puste. Po zmianie wersji przygotowujemy je z oryginalnego dema.

Smoke: detonate → expired dopasowane po entityid i XYZ (tolerancja 8 jednostek,
ochrona przed ponownym użyciem ID). Wygaśnięcie może nastąpić po końcu rundy,
dlatego dopasowanie korzysta z surowych eventów; odtwarzanie obcina do końca
rundy. Brak dopasowania daje jawne `estimated_22s`, nie potwierdzone wygaśnięcie.
Obrys jest orientacyjnym kołem o promieniu 144 jednostek, półprzezroczystym,
rysowanym pod graczami, z krótkim efektem pojawienia i zaniku. Nie odwzorowuje
ścian, pięter ani chwilowych dziur po HE/strzałach. Dokładne smoke’y w grze są
dynamiczne i reagują na otoczenie: [Valve — Responsive Smokes](https://www.counter-strike.net/cs2).
To warstwa wizualna, nie geometria używana do ustalania widoczności czy kontroli.

Strzał: rzeczywisty `weapon_fire` z XYZ i yaw strzelającego w ticku eventu.
Noże, bagnety, rzucanie granatów i C4 są wykluczone. Krótki błysk 0,1 s
jest rysowany na końcu znacznika kierunku broni; tłumik zmniejsza intensywność.
Nie symulujemy toru pocisku, trafienia ani dokładnego modelu lufy 3D.
Obie warstwy mają osobne przełączniki i poprawnie reagują na przewijanie.

Realne Mirage: **74 smoke’y (63 z eventem wygaśnięcia, 11 z szacunkiem)
i 2236 strzałów**, 122 950 próbek pozycji. Gęstsze próbkowanie rozpoznaje
pierwsze wejście w ticku 7464, cztery ticki wcześniej niż historyczne próbki
co 16/64 ticki. Poprzednia próbka wejścia ma tick 7458; obsada CT pozostaje 2/2.
Testy obejmują dopasowanie smoke, ponowne użycie entityid, wygaśnięcie poza rundą,
brak źródeł, filtrowanie broni, round-trip SQLite/JSON, granice aktywności
efektów w rzeczywistym skrypcie JS oraz pełne parsowanie Mirage i widok Streamlit.

## Następne zadania

1. Zweryfikować na wybranych rundach mapowanie stref i geometrię wysokości;
   dodać wersjonowane granice obszarów oraz bramki wejścia na A/B.
2. Wyznaczyć fazy rundy, rotacje, przejścia między strefami i pozycję bomby po upuszczeniu.
3. Policzyć CT przy site'cie przed atakiem i podczas wejścia; zachować oddzielnie
   graczy w łącznikach oraz niepełne dane.
4. Połączyć sekwencje ruchu, bomby i utility w wskaźniki presji A/B/mid.
5. Dopiero potem klasyfikować rush/execute/split i prawdopodobny plan.
6. Rozszerzyć profil gracza o kontakt/entry, pozycję śmierci, koniec rundy i rotacje.

Źródło definicji pól parsera: [demoparser2](https://github.com/RPSam/demoparser2).
