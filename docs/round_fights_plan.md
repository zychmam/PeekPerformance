# M3–M4 — przebieg rundy, starcia i prezentacja

Status: plan do wykonania po M2, z rozwojem i testami na obu mapach.
Aktualizacja 2026-10-12: dawny zakres R3 podzielono między M3 i M4.
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
M4 wzbogaca je o segmentację lokalnych starć, ich efekt i przebieg ataku.
Do podstawowego opisu M3 nie jest potrzebne rozpoznanie granic lokalnych walk.

## Co mierzymy

Poniżej definicje pomiarów; kolejność implementacji znajduje się na końcu.

1. **Pierwszy obserwowany kontakt:** pierwsze obrażenia przeciwnika, czas,
   autor/odbiorca, broń oraz obie pozycje. Osobno pierwsze obrażenia od utility
   i pierwszy kontakt ogniowy. Bez eventów strzałów/widoczności nie twierdzimy,
   że był to pierwszy strzał, zauważenie lub świadoma inicjacja walki.
2. **Lokalne starcia:** kontakty powiązane miejscem, uczestnikami i czasem.
   Jednoczesne walki na A/B pozostają oddzielne; kontakt na długim dystansie ma
   dwie pozycje, nie wymuszoną wspólną strefę. Nie łączymy całej rundy łańcuchem
   wspólnych graczy. Przy braku lokalizacji pozostaje nieprzypisany kontakt.
   Przerwa bez kontaktu 5 s jest początkową, konfigurowalną granicą epizodu,
   do kalibracji na referencjach. Nowe starcie może zacząć się w tej samej strefie.
3. **Pierwszy frag:** osobno opening całej rundy oraz pierwszy frag lokalnego
   starcia. Powiązanie z wejściem na site to osobna relacja z dowodem; pierwszy
   frag w dowolnym miejscu nie dostaje automatycznie etykiety entry fraga.
4. **Odpowiedź w 10 s od zabójstwa:** refrag wymaga zabicia dokładnie zabójcy
   kolegi. Zapisujemy ofiarę, zabójcę, refragującego, ticki i opóźnienie.
   Inne zabójstwo drużyny to osobna odpowiedź. Relacja refraga może łączyć różne
   lokalne epizody, nie wymusza ich scalenia. Brak odpowiedzi pozostaje nieznany
   przy niepełnym źródle. Nie zmieniamy dotychczasowego ratingowego trade 5 s.
5. **Efekt:** fragi i straty obu stron, obrażenia HP, żywi lokalni uczestnicy
   i globalny stan liczebny przed/po. Wynik wymiany fragów, np. T 2:1 CT,
   oddzielamy od wyniku rundy i skuteczności ataku. Dopełniamy widok po 10 s
   od pierwszego fraga, wyraźnie oddzielony od faktycznego końca starcia.
6. **Utility:** zdarzenia przed/w trakcie walki, autor, czas, miejsce.
   Powiązanie przyczynowe tylko przy dodatkowym dowodzie: np. obrażenia od HE
   albo potwierdzone oślepienie konkretnej ofiary w chwili kontaktu. Sam pobliski
   flash/smoke nie dowodzi wsparcia fraga, blokady widoczności ani zdobycia mapy.
7. **Następstwo przestrzenne:** potwierdzona obecność/przejście po walce,
   wejście do site'u oraz chronologiczne powiązanie z plantem. Zapisujemy
   następstwo; kontrola przestrzeni i przyczyna zmiany wymagają dalszych danych.

Granice epizodu i 10-sekundowe okno odpowiedzi są odrębne. Okno obcinamy końcem
rundy, nie początkiem kolejnego starcia. Każde źródłowe zabójstwo ma jedno
przypisanie do epizodu, ale może być referencją odpowiedzi/powiązania.
Niepewna kolejność zdarzeń w jednym ticku nie jest wymuszaną przyczynowością.

## Zmiana prezentacji obecnego R2

- Przygotowanie: ustawienie z ostatniej świeżej próbki **przed pierwszym
  obserwowanym kontaktem**, obok pomiarów 0/5/10/15 s. Kontakt wybrany jako
  odniesienie jest nazwany. Przy braku wcześniejszej próbki: nieznane.
- Przygotowanie 0–15 s może nakładać się na walkę. Ustawienie po 15 s pozostaje
  pomiarem z podpisem czasu, nie udaje planu początkowego.
- Nagłówek: runda, zwycięzca, sposób zakończenia, czas, stan pokrycia danych.
- Dwa widoki: **Drużyny** i **Wybrany gracz**. Główny widok drużynowy zawiera
  do trzech zdań: przygotowanie T/CT, kluczowa wymiana, dalszy przebieg/wynik.
  Wybór kluczowego starcia początkowo po zmianie liczebności, liczbie ofiar
  i związku z wejściem/plantem; reguła jawna i nie jest oceną jakości decyzji.
- Jedna chronologiczna oś: przygotowanie, kontakt, lokalne starcia, istniejące
  wejścia oraz plant/defuse. Równoległe epizody w osobnych torach.
  Retake pozostaje niewyliczony do M4.4; defuse nie zastępuje detekcji próby.
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
| M3.3 | Opening rundy, refragi/odpowiedź 10 s, globalna liczebność | Dokładny zabójca, opóźnienie, granica 10 s, koniec rundy, nieznana kolejność w ticku; bez zależności od segmentacji i bez zmiany ratingu. |
| M3.4 | Chronologia i pierwsze podsumowania | Dwa zakresy, oś i jeden radar; istniejące wejścia/bomba/wynik; szczegóły na żądanie, nicki. |
| M4.1 | Dawne R3.2 i pierwszy frag epizodu | Równoległe A/B, powtórna walka w tym samym miejscu, kontakt bez fraga/brak pozycji; brak przymusowego scalania. |
| M4.2–3 | Lokalny efekt, utility i następstwa | HP bez podwójnego liczenia, jawne luki, powiązania z wejściem/plantem. Kontekst utility osobno od potwierdzonych efektów. Próba ataku wymaga osobnej definicji. |
| M4.4 | Rotacje i retake z dawnego R4 | Obserwowalny sygnał odniesienia i jawne kryteria próby; wynik rundy nie dowodzi zamiaru. |
| M3.5 / M4.5 | Dawne R3.7 i odbiór widoków | Referencje od początku, całe wyjaśnienia rund na obu mapach, negatywne przypadki i E2E; współdzielone obliczenia oraz cache. |

Kolejność: **M2 → M3.1–3 z referencjami i rozwijanym widokiem M3.4 → odbiór M3.5
→ wzbogacanie M4.1–4 i odbiór M4.5**. Podstawowe porównania M5 startują na
zweryfikowanych wynikach M3 podczas rozwoju M4. Pełne etykiety strategii
nie blokują pierwszego raportu. Oceny błędów i zaleceń coacha wymagają
osobnej walidacji; M3/M4 przede wszystkim wyjaśniają obserwowany przebieg.

Reużywamy `Evidence`, `Episode`, `Fight`, `PlayerRound`, `Preparation`, wejść
sterowanych profilem mapy, lokalnego cache i radaru. Kontrakt wymaga uzupełnienia o pierwsze
kontakty, granice faktycznego epizodu, lokalne/globalne wyniki oraz relacje;
nie utożsamiamy istniejącego `Fight.opening_kill_id` z openingiem rundy.
