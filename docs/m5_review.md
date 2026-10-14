# Review przed M5.3 — 2026-10-14

**Aktualizacja po realizacji:** M5.R1–R3 poprawiono i objęto regresjami.
M5.3–6 są zaimplementowane; [zakres i weryfikacja](m5_tactical_summary.md).
Poniżej zachowano pierwotne ustalenia review jako uzasadnienie zmian.

Zakres: kod faktów/agregacji/usługi/UI M5.1–2, zależności kontaktów i refragów
M3, kontrakt cache M4 oraz zgodność roadmapy ze stanem implementacji.
Nie jest to ponowny odbiór taktyczny wszystkich detektorów M4 na radarze.
Pierwotne review zmieniało wyłącznie dokumentację; poprawki kodu wykonano
w kolejnym etapie opisanym w aktualizacji na początku pliku.

## Potwierdzone problemy

### M5.R1 — P1: kompletność kontaktów

`src/demos/round_contacts.py:180` wymaga statusu `OBSERVED` obu źródeł.
Gdy obrażenia są znane, a zabójstw poprawnie nie było (`ABSENT`), kontakty
otrzymują `PARTIAL`. Przypadek odwrotny ma ten sam problem. W M5 taka runda
zwiększa liczbę nieustalonych rund mimo kompletnego źródła.

Reprodukcja: fixture `build(events=[hurt('damage',20)])` ma damage=observed,
kills=verified_absent, contacts_status=partial oraz contacts_known=False.

Naprawa: traktować OBSERVED i ABSENT jako znane pokrycie źródła; rozdzielić
kompletność źródła od obecności kwalifikującego kontaktu. Dla kompletnego
źródła zawierającego wyłącznie zdarzenia odrzucone przez reguły kontaktu
zwracać potwierdzony brak. Zachować UNKNOWN/PARTIAL przy rzeczywistych lukach.
W agregacji/UI wskazać, że pierwszy kontakt z niepełnego źródła jest pierwszym
wśród dostępnych obserwacji; status powinien towarzyszyć przykładowi, nie tylko
zbiorczej tabeli pokrycia.

Odbiór: damage-only, kill-only, brak kwalifikujących zdarzeń, oba źródła puste,
źródło niepełne; poprawne pokrycie i opis w M5. Zmiana wersji detektora i cache.

### M5.R2 — P1: refrag jako zabójstwo i wymieniony zgon

Detektor poprawnie tworzy relację dla każdego wymienionego zgonu. Jednak
`map_round_facts.py:228` i `map_tendencies.py:251` przenoszą każdą relację jako
osobne zdarzenie, a UI (`map_tendencies_view.py:201`) podpisuje ich liczbę
„Refragi”. Jeden frag może więc wyglądać jak dwa fragi wymieniające.

Reprodukcja: C0 zabija T0 i T1, następnie T2 zabija C0 w oknie 5 s.
Detektor zwraca 2 relacje, 1 unikalny response_kill_id, M5 pokazuje 2 wymiany.
To nie błąd samego detektora relacji; dokumentacja już dopuszcza wiele zgonów
dla jednej odpowiedzi, lecz prezentacja nie wyjaśnia jednostki.

Naprawa: zachować jawne response_kill_id i initial_death_id w faktach.
Raportować osobno unikalne zabójstwa wymieniające, wymienione zgony i rundy
z wymianą. Przy filtrze zawodnika jawnie rozróżniać autora odpowiedzi od ofiary.

Odbiór: przykład 1 frag / 2 wymienione zgony / 1 runda; remisy i filtr gracza;
nawigacja do jednej odpowiedzi z kompletem dowodów. Zmiana wersji faktów.

### M5.R3 — P2, przed M5.3: snapshot po zakończeniu rundy

`early_round.py` prawidłowo pomija snapshot późniejszy niż koniec rundy.
`map_tendencies.py:146–167` traktuje jego brak jako nieustalone pozycje całego
składu i wlicza rundę do eligible. To myli brak okazji do pomiaru z luką danych.

Reprodukcja: runda kończy się po 5 s, wybrany snapshot to 10 s. Wynik:
eligible=1, unknown_rounds=[1], 5 pozycji __unknown__.

Naprawa: sprawdzać freeze/end/tick_rate. Zakończona wcześniej runda ma osobną
kategorię „poza zakresem pomiaru” i nie zasila mianownika pozycji ani kierunków.
Brak próbki w nadal trwającej rundzie pozostaje nieznany. Nie usuwać tej rundy
z innych statystyk. Nieznany zegar także nie oznacza potwierdzonego wykluczenia.

Odbiór: koniec przed, dokładnie w i po czasie snapshotu, brak zegara, prawdziwa
luka próbek. UI pokazuje eligible/known/unknown/not_applicable w kontekście miary.

### M5.R4 — P2: porządek roadmapy — wykonane w review

Końcowa kolejność nadal wskazywała odbiór M3.5b i implementację M4.1, sprzecznie
z aktualnym stanem M4/M5. Poprawiono najbliższe zadania i wskazanie następnego
kroku. Akceptacja użytkownika M3/M4 pozostaje ważna.

## Co zachować i czego wymagać przy M5.3

- Podział na kompaktowe fakty, czystą agregację, cache i UI jest odpowiedni.
  Filtry nie muszą wracać do parsera ani próbek pozycji. Nie potrzeba przebudowy.
- Stable team/side, segmenty porównania, pełna wycena, rozróżnienie brak/zero
  oraz dowody i przejścia do rundy są właściwym fundamentem.
- Profile map sterują regionami; nie znaleziono nazw Mirage/Inferno zaszytych
  w przejrzanej agregacji M5. Utrzymać test syntetycznego profilu.
- M5.3 musi dopiero dodać kompaktowe próby ataku z M4: obecne fakty mają
  `entries`, lecz nie mają listy `attacks`. To planowany zakres, nie ukończona
  integracja. Nie zastępować prób pierwszymi wejściami.
- Nowy kontrakt próby: ID, cel, czas, status/kompletność, związane utility,
  uczestnicy/odłączeni, osobne wyniki wejścia/planta/rundy i dowody. Uwzględnić
  wiele prób w rundzie i znany brak próby osobno od nieznanej detekcji.
- Przy zmianie faktów zwiększyć wersję cache i odbudować z zapisanych źródeł;
  zgodnie z ustaleniami bez migracji historycznych wyników.
- Pokrycie kierunków T na Mirage pozostaje ograniczone (wcześniej zmierzone
  6/12 i 5/9 kompletnych snapshotów). Nie wnioskować o preferencji całej strony
  bez podania próbki. Rozszerzać profil po ustaleniu konkretnych braków, bez
  obowiązkowego nowego epiku mapowania przed M5.3.

## Weryfikacja review

47 testów zaliczonych: test_map_tendencies, test_tactical_actions,
test_round_contacts, test_round_refrags (19,22 s). Dodatkowo trzy niezależne
reprodukcje powyższych problemów na fixture źródłowym/agregacyjnym.
Istniejące testy nie obejmują tych oczekiwań; ich przejście nie zamyka poprawek.
Nie uruchamiano przeglądarki ani ponownego parsowania dem.

Kolejność: M5.R1 → M5.R2 → M5.R3 → regresje i odczyt cache obu map → M5.3.
