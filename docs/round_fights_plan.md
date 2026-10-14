# M3–M4 — przebieg rundy, starcia i prezentacja

Aktualizacja **2026-10-14**, po finalizacji technicznej M3. Chronologia i korekty
M3.6 działają; końcowy odbiór wizualny M3.5b pozostaje po stronie użytkownika.
Detektory M4 są do wykonania na obu mapach.
Nowa kolejność M4: ruch/profil → utility/zasoby → starcia → próby T
→ działania poza grupą → aktywność/reakcje CT → końcowy odbiór.
[ROADMAP.md](../ROADMAP.md) określa zadania, zależności i kryteria odbioru.
Ten dokument zachowuje szczegółowe reguły kontaktów i starć.
Szczegółowy zakres wdrożenia M3 i docelowy układ ekranu opisuje
[plan podsumowania rundy](m3_round_summary_plan.md). Opisane poniżej lokalne
starcia, ich karty i tory równoległe są rozszerzeniami M4.

## Cel

Połączyć przygotowanie T/CT z odpowiedzią: gdzie rozpoczęła się walka,
kto uzyskał pierwszy frag, jak odpowiedział przeciwnik i co zmieniło się po starciu.
Osobny raport drużynowy i gracza korzystają ze wspólnych epizodów i dowodów.

W M3 najpierw pokazujemy pełną chronologię faktów: warunki startu, przygotowanie,
kontakty, opening/refragi, zmiany globalnej liczebności, istniejące wejścia,
zdarzenia bomby i zakończenie. Podsumowanie dla drużyn i gracza powstaje od razu.
M4 wzbogaca je o ruch całej rundy, kontekst utility, lokalne starcia, próby
ataku T, działania poza główną grupą oraz aktywność i reakcje CT.
Do podstawowego opisu M3 nie jest potrzebne rozpoznanie granic lokalnych walk.

## Co mierzymy

Poniżej definicje pomiarów; kolejność implementacji znajduje się na końcu.

1. **Pierwszy obserwowany kontakt:** pierwsze dodatnie obrażenia przeciwnika
   lub frag uzupełniający brak eventu obrażeń, czas, autor/odbiorca, broń oraz
   obie pozycje. Osobno utility i kontakt ogniowy. Strzały są zapisane oddzielnie;
   nie ustalają samodzielnie celu ani widoczności. Kontakt M3 nie oznacza
   pierwszego strzału, zauważenia lub świadomej inicjacji walki.
2. **Lokalne starcia:** kontakty powiązane miejscem, uczestnikami i czasem.
   Jednoczesne walki na A/B pozostają oddzielne; kontakt na długim dystansie ma
   dwie pozycje, nie wymuszoną wspólną strefę. Nie łączymy całej rundy łańcuchem
   wspólnych graczy. Przy braku lokalizacji pozostaje nieprzypisany kontakt.
   Przerwa bez kontaktu 5 s jest początkową, konfigurowalną granicą epizodu,
   do kalibracji na referencjach. Nowe starcie może zacząć się w tej samej strefie.
3. **Pierwszy frag:** osobno opening całej rundy oraz pierwszy frag lokalnego
   starcia. Powiązanie z wejściem na site to osobna relacja z dowodem; pierwszy
   frag w dowolnym miejscu nie dostaje automatycznie etykiety entry fraga.
4. **Odpowiedź w 5 s od zabójstwa:** refrag wymaga zabicia dokładnie zabójcy
   kolegi. Zapisujemy ofiarę, zabójcę, refragującego, ticki i opóźnienie.
   Inne zabójstwo drużyny to osobna odpowiedź. Relacja refraga może łączyć różne
   lokalne epizody, nie wymusza ich scalenia. Brak odpowiedzi pozostaje nieznany
   przy niepełnym źródle. Ratingowy trade pozostaje osobnym obliczeniem.
5. **Efekt:** fragi i straty obu stron, obrażenia HP, żywi lokalni uczestnicy
   i globalny stan liczebny przed/po. Wynik wymiany fragów, np. T 2:1 CT,
   oddzielamy od wyniku rundy i skuteczności ataku. Dopełniamy widok po 5 s
   od pierwszego fraga, wyraźnie oddzielony od faktycznego końca starcia.
6. **Utility:** osobno autor/miejsce/czas rzutu, miejsce/czas zadziałania,
   dostępny okres aktywności oraz potwierdzone efekty HP/oślepienia. Dopasowanie
   rzutu do efektu zachowuje metodę i niepewność; używamy istniejących źródeł
   i sprawdzamy trajektorie przed nową ekstrakcją. Przypisanie do starcia/ataku
   wymaga kontekstu przestrzennego i czasowego. Obrażenia HE lub oślepienie
   konkretnej ofiary są dowodem efektu, ale nie rozstrzygają przyczyny wygrania
   walki. Sam pobliski flash/smoke nie dowodzi wsparcia fraga ani blokady widoczności.
7. **Następstwo przestrzenne:** potwierdzona obecność/przejście po walce,
   wejście do site'u oraz chronologiczne powiązanie z plantem. Zapisujemy
   następstwo; kontrola przestrzeni i przyczyna zmiany wymagają dalszych danych.

Granice epizodu i 5-sekundowe okno odpowiedzi są odrębne. Okno obcinamy końcem
rundy, nie początkiem kolejnego starcia. Każde źródłowe zabójstwo ma jedno
przypisanie do epizodu, ale może być referencją odpowiedzi/powiązania.
Niepewna kolejność zdarzeń w jednym ticku nie jest wymuszaną przyczynowością.

## Fundament przestrzenny i powiązanie działań

M4.1 rozwija obecne profile i indeksy o przedziały pobytu/przejścia całej rundy:
gracz, obszar, wejście/wyjście, czas utrzymania, śmierć, luki i źródła. Profil
deklaruje sektory obrony i granice wysunięcia, a wspólny silnik mierzy zachowanie.
Nie dodajemy reguł po nazwie mapy ani regionu. Testy obejmują obie mapy i profil
syntetyczny ze zmienionymi ID. Niepełna topologia pozostaje ograniczeniem.

M4.4 łączy starcia, ruch, bombę i utility w kolejne próby ataku. Próba może
zostać zatrzymana przed site'em lub zakończyć się wycofaniem bez fraga. Sam rzut
lub obecność na podejściu nie wystarczają do potwierdzenia celu. Zachowujemy
krótkie i ponowne wejścia oraz niepewne przekroczenia; obecne potwierdzone wejścia
są jednym ze źródeł. Tempo opisują czas od freeze, początek natarcia, postoje
i rozciągnięcie wejścia; przygotowanie utility jest osobnym wymiarem.

M4.5 opisuje główną grupę i graczy odłączonych w czasie konkretnej próby,
względem liczby żywych T. Ich kontakty, utility, utrzymanie pozycji, dołączenie
i udział w zmianie kierunku nie otrzymują automatycznie etykiety lurka.
Powiązanie z przechwyceniem rotacji dochodzi po detekcji ruchu CT w M4.6.

M4.6 opisuje wysunięcia, utrzymanie obecności, wycofania i reakcje CT. Dla rotacji
podajemy nazwany sygnał odniesienia, moment rozpoczęcia ruchu, czas drogi oraz
przybycie/przerwanie; ruch wcześniejszy nie staje się reakcją. Luki, śmierć
i koniec rundy nie dają zerowego opóźnienia. Próba retake ma własne kryteria,
osobne od eventu defuse. Opisy wykorzystania obecności wskazują obserwowane
następstwa, bez pewnego przypisywania kontroli, komunikacji lub motywu.

Wyniki per runda zasilają M5 bez odczytywania faktów z tekstu i ponownego parsera.
Te same zdarzenia nie są liczone jako niezależne powtórzenia. Wyniki wejścia,
planta i całej rundy oraz ich mianowniki pozostają osobne.

## Zmiana prezentacji obecnego R2

- Przygotowanie: ustawienie z ostatniej świeżej próbki **przed pierwszym
  obserwowanym kontaktem**, obok pomiarów 0/5/10/15 s. Kontakt wybrany jako
  odniesienie jest nazwany. Przy braku wcześniejszej próbki: nieznane.
- Przygotowanie 0–15 s może nakładać się na walkę. Ustawienie po 15 s pozostaje
  pomiarem z podpisem czasu, nie udaje planu początkowego.
- Nagłówek: runda, zwycięzca, sposób zakończenia, czas, stan pokrycia danych.
- Dwa widoki: **Drużyny** i **Wybrany gracz**. Główny widok drużynowy zawiera
  3–4 krótkie zdania: przygotowanie T/CT, ważna wymiana, dalszy przebieg/wynik.
  Wybór kluczowego starcia początkowo po zmianie liczebności, liczbie ofiar
  i związku z wejściem/plantem; reguła jawna i nie jest oceną jakości decyzji.
- Jedna chronologiczna oś: przygotowanie, kontakt, lokalne starcia, istniejące
  wejścia oraz plant/defuse. Równoległe epizody w osobnych torach.
  Retake pozostaje niewyliczony do M4.6; defuse nie zastępuje detekcji próby.
- Jeden radar zsynchronizowany z wybranym zdarzeniem i suwakiem. Przy starciu
  wyróżnieni uczestnicy, obie pozycje kontaktu, krótkie obserwowane ścieżki,
  wybrane utility. Luki ścieżek widoczne, brak sugerowanej widoczności.
- Karta starcia: miejsce/czas, pierwszy frag, refragi z opóźnieniem,
  wynik wymiany, globalnie przed/po, potwierdzone następstwo. Maksymalnie kilka
  liczb; szczegóły zdarzeń pod rozwinięciem.
- Surowe XYZ/ticki, długa lista ruchu i diagnostyka w szczegółach. Dowód
  otwiera konkretny moment radaru; nie ograniczamy audytu do pierwszych 12
  rekordów. Usuwamy powielane tabele utility i openingu.
- Profil pozycji zawodnika z całej mapy przenosimy z widoku pojedynczej rundy
  do profilu mapy. Perspektywa gracza pokazuje początek, pierwszy jego kontakt,
  obrażenia/frag/śmierć, wymianę, utility i dalszą obserwowaną trasę.
- Wyposażenie/ekonomia, czas, liczebność i bomba stanowią kontekst podsumowania.
  Te same obserwacje służą porównywaniu podobnych rund w M5, rozwijanym już po M3.

## Podział między M3 i M4

| Obecne zadania | Zakres wcześniejszego planu | Istotne kryteria |
| --- | --- | --- |
| M3.1–2 | Dawne R3.1: rekord i kontakty | Warunki rundy, oba końce kontaktu, typ, ticki, status; bez friendly/self/world. |
| M3.3 | Opening rundy, refragi/odpowiedź 5 s, globalna liczebność | Dokładny zabójca, opóźnienie, granica 5 s, koniec rundy, nieznana kolejność w ticku; bez zależności od segmentacji i bez zmiany ratingu. |
| M3.4 | Chronologia i pierwsze podsumowania | Dwa zakresy, oś i jeden radar; istniejące wejścia/bomba/wynik; szczegóły na żądanie, nicki. |
| M3.6 | Korekty po review | Początek sprzed kontaktu, późniejsze zmiany sytuacji, wyposażenie i jawne znaczenie miar. |
| M4.1 | Wspólny fundament przestrzeni i ruchu | Pobyty/przejścia przez całą rundę, sektory obrony, granice wysunięcia i luki; reguły wspólne dla map. |
| M4.2 | Utility i zasoby przy zdarzeniach | Miejsce rzutu osobno od efektu, jakość powiązania, HP/wyposażenie/bomba/liczebność. |
| M4.3 | Dawne R3.2 oraz lokalny efekt | Równoległe A/B, ponowna walka, obrażenia bez fraga, nieznane pozycje, pierwszy frag epizodu; HP bez podwójnego liczenia. |
| M4.4 | Próby ataku z dawnego R4 | Także krótkie, ponowne i zatrzymane próby; zmiany celu, tempo, kontekst utility i rezultat. |
| M4.5 | Udział graczy poza grupą | Zachowanie podczas konkretnej próby; 4+1 nie dowodzi roli lurka. |
| M4.6 | Aktywność CT, rotacje i retake | Obserwowalny sygnał odniesienia i jawne kryteria próby; wynik rundy nie dowodzi zamiaru. |
| M3.5 / M4.7 | Dawne R3.7 i odbiór widoków | Referencje od początku, całe wyjaśnienia rund na obu mapach, negatywne przypadki i E2E; współdzielone obliczenia oraz cache. |

M3.6 i odbiór M3.5b zaakceptowane przez użytkownika 2026-10-14. Pierwsza
implementacja M4.1–6 gotowa; aktualne reguły i granice odbioru opisano
w [M4 — działania taktyczne](m4_tactical_actions.md). Najbliższa kolejność:
**M5.3 — tendencje prób T → M5.4 — tendencje CT**. Obecna wersja M4 zaakceptowana
przez użytkownika; M5.1–2 wdrożone. Referencje i integracja towarzyszą każdemu zadaniu.
Podstawowe porównania M5.1–2 startują na poprawionych wynikach M3 podczas rozwoju
M4; tendencje T/CT i następstwo rund M5.3–5 dochodzą po właściwych detektorach.
Wnioski M5.6 oraz próbny LLM M5.7 rozwijamy na odebranym zakresie. Pełne etykiety strategii
nie blokują pierwszego raportu. Oceny błędów i zaleceń coacha wymagają
osobnej walidacji; M3/M4 przede wszystkim wyjaśniają obserwowany przebieg.

Reużywamy `Evidence`, `Contact`, `RoundMoment`, `Episode`, `Fight`, `PlayerRound`,
`Preparation`, wejścia sterowane profilem mapy, lokalny cache i radar. Kontakty,
opening/refragi i globalna liczebność już istnieją. Kontrakt rozszerzamy o pobyty,
granice faktycznego epizodu, lokalne wyniki i powiązania działań;
nie utożsamiamy istniejącego `Fight.opening_kill_id` z openingiem rundy.
