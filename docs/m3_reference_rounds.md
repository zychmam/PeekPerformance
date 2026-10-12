# M3.1a-b — źródła i rundy referencyjne

Źródło: zapisane ramki parsera dwóch rzeczywistych dem oraz niezależnie zapisane
etapy obserwacji/przestrzeni. Kontrola: `python scripts/m3_reference_audit.py` czyta
SQLite w trybie `mode=ro`; nie używa detektorów M3 ani ich przyszłego opisu.
Przejrzano chronologię fragów, pierwszych dodatnich obrażeń przeciwnika, bomby,
roster i liczbę próbek. To referencje do faktów parsera, nie ręczny replay CS2.
W szczególności nazwy miejsc z eventu zabicia nie dowodzą widoczności lub
dokładnego miejsca wcześniejszego kontaktu.

## Audyt faktów planowanego podsumowania

| Fakt w tekście | Źródło i dostępność | Granica / status przy braku |
| --- | --- | --- |
| Runda, strony, zwycięzca, zakończenie, czas | `rounds_df`, `round_roster_df`, `observations.clock`, `RoundClock`; obie mapy | Zegar zakłada 64 tick/s; identyfikacja drużyny wymaga pełnego rosteru. |
| Wyposażenie na starcie | `equipment` przy freeze, `economy`, `RoundFoundation.equipment_coverage`; obie mapy | Niepełny ekwipunek albo odczyt ekonomii daje `partial/unknown`, bez pewnej etykiety zakupu. |
| Kierunek T i ustawienie CT | `states`, profil mapy, snapshoty 0/5/10/15 i `setup_before_contact`; obie mapy | Próbka musi być świeża i sprzed kontaktu; wsparcie CT nie dodaje drugiego obrońcy. Nie nazywamy zamiaru. |
| Wczesne utility | `throws`, `utility_lifecycles`, `utility`, okna 10/15 s; obie mapy | Rzut, detonacja i efekt to różne fakty. 51 rzutów Mirage bez jednoznacznego połączenia z efektem. |
| Pierwsze obrażenia i uczestnicy | `damage_df` z `enemy_damage>0`; `kills_df` jako awaryjny kontakt; obie mapy | Dodatnie HP i strony wymagają kontroli; obrażenia utility oddzielnie od broni. `kill_only` nie podwaja HP. |
| Obie pozycje kontaktu | `states` przez `RoundIndex`; eventy hurt/kill mają też XYZ i place; obie mapy | Bez próbki nie zastępujemy jej pozycją z przyszłości. Mirage R1 ma 89 nieustalonych przypisań regionu; miejsce może być nieznane. |
| Opening, odpowiedź, liczebność | `kills_df`, roster, `states.is_alive`; obie mapy | Refrag wymaga dokładnego zabójcy i późniejszego ticku. Dwa fragi tego samego ticku nie tworzą kolejności. Brak kompletnego rosteru/gapy → stan częściowy. |
| Potwierdzone wejście | `spatial.entries`, `Episode` z próbkami przed/po; obie mapy | Wejście nie dowodzi planu ataku; wykrycie nie obejmuje prób zatrzymanych przed site'em. |
| Plant/defuse/wybuch | `bomb_events_df` i `bomb_updates`; obie mapy | Pusty strumień plantów nie zawsze dowodzi braku próby. Defuse nie oznacza automatycznie rozpoznanego retake. |
| Udział wybranego gracza | Roster, pozycje, damage/kills, utility, bomba, wejścia; obie mapy | Bez kontaktu/fraga pokazujemy pozostałe działania. Motyw rotacji, save i jakość decyzji pozostają nieocenione. |

Pola `Fight`, `Attack`, `Rotation`, `Retake` mają obecnie status
`not_evaluated`. Sama dostępność wejściowych źródeł w `capabilities` nie zmienia
tego statusu. W M3.1 nie ma jeszcze żadnego detektora kontaktu ani refraga.

## Osiem scenariuszy odbiorowych

Ticki są źródłowe, a czas na ekranie ma być liczony od podanego końca freeze.
Perspektywa gracza to *oczekiwane fakty* do późniejszego opisu, bez oceny duelu
lub taktycznego zamiaru. Nazwy graczy służą tylko tej referencji.

| Mapa / runda | Oczekiwana oś drużynowa | Oczekiwana perspektywa gracza i ograniczenie |
| --- | --- | --- |
| Mirage 1, freeze 6828 | Pierwsze obrażenia: 7556, -turas → -FERKI (broń). Opening CT: -turas zabija -FERKI 7802. -KVNI zabija dokładnego zabójcę 7874 (72 ticki). Plant A 8436, CT defuse 9671. | -FERKI: otrzymuje pierwsze obrażenia i ginie 7802; jego zgon zostaje wymieniony. 89 próbek tej rundy nie ma pewnego regionu; brak miejsca ma pozostać widoczny. |
| Mirage 6, freeze 32123 | Pierwsze obrażenia: HE 32783; opening CT: --Flavi-- zabija -FERKI 33055. Kolejny frag -KVNI 33162 zabija creep7, więc nie jest wymianą openingu. Plant A 35062, wybuch 37686. | SzlugENDglo: bez fraga, zgon od ztkaaa 36979. Opis udziału nie może wymusić wygranego pojedynku. |
| Mirage 13, freeze 70601 | Pierwsze obrażenia i opening CT: -KVNI zabija ztkaaa 71380. Rassiq zabija dokładnego zabójcę 71436 (56 ticków). CT wygrywa eliminacją 74124; brak `bomb_planted` w surowych eventach. | ztkaaa: ginie jako pierwszy 71380, a jego zabójca zostaje zabity 71436. Brak plantu nie jest etykietą planu T. |
| Mirage 20, freeze 104598 | Pierwsze obrażenia 105746; opening CT: -Tygrysss zabija --Flavi-- 105780. creep7 zabija dokładnego zabójcę 105796 (16 ticków). Plant B 106815, CT defuse 108640. | --Flavi--: ma obrażenia w obu kierunkach przed śmiercią; śmierć wymieniona szybko. Defuse to fakt końcowy, bez automatycznego retake. |
| Inferno 1, freeze 8188 | Pierwsze obrażenia z broni: Naroa_ → Kajla 8810. Opening CT: creep7 zabija Naroa_ 9098. CT wygrywa eliminacją 14368, brak planta. Zapisano wejścia T na B 10858 i 11830. | 00000023: bez fraga, ginie od -turas na B 11102. Samo wejście drużyny nie przypisuje mu udziału bez rekordu uczestnika. |
| Inferno 3, freeze 21347 | Pierwsze obrażenia: HE 22091. Opening T: 00000023 zabija Kajla 23033. creep7 zabija dokładnego zabójcę 23136 (103 ticki). Plant A 24989; T wygrywa eliminacją 27040. | 00000023: zdobywa opening i ginie 23136; CT wymienia śmierć Kajla. Pierwszy kontakt utility nie jest tym samym co pierwszy kontakt ogniowy. |
| Inferno 10, freeze 66236 | Pierwsze obrażenia: ogień 66946. Opening CT: _prs_ zabija antoo_ 67340 w Apartments. creep7 zabija dwóch T w ticku 68083: jeden wspólny stan przed i po, bez fikcyjnej przewagi po pierwszym z tych fragów. Plant B 68896, CT defuse 71183. | antoo_: bez fraga, ginie w openingu. Nie przypisujemy jego śmierci do pierwszych obrażeń od ognia przy B. |
| Inferno 20, freeze 125179 | Pierwsze obrażenia: HE 125826; opening T: beQirichaan zabija Rassiq 127368. Kolejny frag CT na Banana 127565, odpowiedź T 127649 zabija dokładnego zabójcę. CT wygrywa eliminacją 130947; brak planta. | antoo_: ginie na Banana 127565; Naroa_ wymienia jego zabójcę 127649 (84 ticki). Obecność walki na Banana nie dowodzi planu ataku B. |

W scenariuszach bez `bomb_planted` wolno powiedzieć „nie zarejestrowano
planta”; mocniejsze „nie było planta” zależy od jakości strumienia bombowego.
Podobnie późniejsze zadania mają rozstrzygnąć status luk pozycji i kompletność
liczebności przed wydaniem pełnych zdań.

## Szkic wyniku na tych referencjach

Nagłówek: `Runda 10 · Inferno · wygrana CT · rozbrojenie`.
Pod radarem: `Start | Kontakt 66946 | Opening 67340 | Dwa fragi 68083 |
Plant 68896 | Koniec 71183`. Pod przełącznikiem „Drużyny / Gracz” krótki opis
faktów. W „Drużyny” widzimy osobno początek obu stron, kontakt/zmianę stanu,
bombę i koniec. Po wyborze antoo_ ten sam czas radaru zostaje, a treść skupia się
na jego starcie, braku własnego fraga i śmierci przy openingu. Każdy moment
prowadzi do zdarzenia i ma status dostępności; szczegóły techniczne są rozwijane.
