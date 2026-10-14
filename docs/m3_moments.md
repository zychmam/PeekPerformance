# M3.4a — wspólna chronologia rundy

`src/demos/round_moments.py` składa `RoundMoment` z istniejących wyników
detektorów. Oś obejmuje start po freeze time, wczesne rzuty i zadziałania
utility, kontakty, opening, refragi i pozostałe fragi, zmiany liczebności
poza kontaktem z przeciwnikiem, potwierdzone wejścia, zdarzenia bomby oraz
koniec rundy. Zdarzenia bomby sprzed końca freeze time są poza tą osią.

Kontakty z tego samego ticku tworzą jeden moment. Jeśli w tym ticku jest
opening albo refrag, moment dostaje tę etykietę i zachowuje wszystkie
zdarzenia źródłowe. Nie przypisujemy kolejności wewnątrz ticku. Wejście
zachowuje czas pierwszego przekroczenia oraz późniejszego potwierdzenia.
Każdy moment ma stabilne ID i opcjonalne powiązanie ze stanem żywych przed/po.
Momenty działań wskazują źródłowe ID zdarzeń; start i koniec mogą opierać się
wyłącznie na zegarze rundy. Brak profilu mapy nie usuwa osi zdarzeń.

W **Analizie rundy** pod podsumowaniem jest krótka oś orientacyjna.
Rozwinięcie pokazuje pełną tabelę; wybór momentu ustawia radar na jego
początkowy tick. W tabeli są nicki i liczebność tylko tam, gdzie jest
wiarygodna, bez SteamID.

Weryfikacja: `tests/test_round_moments.py` sprawdza wspólny tick,
teamkill, wejście jako przedział i stabilność ID. `scripts/verify_m3_moments.py`
sprawdza chronologię i ręcznie zapisane ticki ośmiu rund Mirage/Inferno
bez zapisu do bazy. Pełny odbiór treści i interakcji należy do M3.5.
