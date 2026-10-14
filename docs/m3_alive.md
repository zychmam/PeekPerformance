# M3.3a — stan żywych w rundzie

`src/demos/round_alive.py` buduje jedną sekwencję `AliveState` dla obu stron.
Pierwszy zarejestrowany frag na przeciwniku jest openingiem; przy równym ticku
zachowujemy wszystkie fragi, bez wymyślania ich kolejności.
Punkt startowy powstaje z rosteru i najświeższych próbek `states.is_alive`
na końcu freeze time. Pewna liczba wymaga pełnego, rozłącznego składu 5+5,
zgodnej strony i próbki każdego gracza. Brak próbki nie zamienia się w 5:5.
Jeżeli strumień fragów jest nieznany, start może być 5:5, ale status przebiegu
całej rundy jest częściowy; brak fragów nie dowodzi przeżycia do końca.

Zgony z `kills` zmieniają stan także przy teamkillu, samobójstwie i world
damage. Zduplikowany zgon w tym samym ticku nie odejmuje gracza drugi raz.
Wszystkie zgony z jednego ticku mają jeden wspólny stan po zdarzeniu, bez
arbitralnej kolejności. Późniejszy drugi zgon tej samej osoby, nieznany gracz,
niezgodna drużyna lub sprzeczna próbka `is_alive` obniżają stan odpowiedniej
strony do `partial` i liczby `null` od chwili rozbieżności. Wcześniejsze
zweryfikowane stany pozostają dostępne. `AliveState` wskazuje źródłowe próbki
startowe, zgony i ewentualną sprzeczną próbkę.

Testy: `tests/test_round_alive.py`. Skrypt `scripts/verify_m3_contacts.py`
sprawdza też wynik żywych w ośmiu rundach z dwóch prawdziwych dem, czytając
bazę tylko do odczytu. Start każdej z tych rund to 5:5; końcowe liczby są
zgodne z zapisanymi zgonami. Kontrola nie oznacza niezależnego replayu.

To globalna liczebność i opening. Refragi w oknie 5 s opisuje
[M3.3b](m3_refrags.md); lokalne starcia pozostają kolejnym etapem.
