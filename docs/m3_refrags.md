# M3.3b — refragi i odpowiedź po openingu

`src/demos/round_refrags.py` łączy śmierć zawodnika z **późniejszym**
zabiciem dokładnie jego zabójcy przez kolegę z drużyny. Okno trwa do 5 s
włącznie i kończy się najpóźniej z rundą. Zdarzenia o tym samym ticku nie
tworzą refraga. Jeden frag może wymienić kilka wcześniejszych śmierci tego
samego sprawcy; zdublowana śmierć jednego gracza jest liczona raz.

Rekord rundy przechowuje `RefragLink` z dwoma źródłowymi ID, opóźnieniem,
obserwowalnym oknem i statusem. Dodatkowo zapisuje wszystkie późniejsze fragi
przeciwników w 5 s od openingu, również te, które nie są refragami.
Podsumowanie pokazuje liczbę kolejnych fragów obu stron, wymianę openingu
i ostatni dostępny stan T:CT w oknie. Przy częściowym źródle nie potwierdza
braku wymiany. Ratingowy trade pozostaje osobnym obliczeniem.

Weryfikacja: `tests/test_round_refrags.py` pokrywa równe ticki, granicę
5 s, koniec rundy, dokładnego zabójcę, wiele ofiar i niepełny roster.
`scripts/verify_m3_refrags.py` odczytuje osiem rund z zapisanych dem Mirage
i Inferno bez zapisu do bazy. Potwierdza ręcznie sprawdzone refragi openingu
oraz późniejszą wymianę na Inferno 20. Na Mirage 6 kolejny frag w oknie
nie jest błędnie nazywany refragiem openingu.

M3.4 nadal musi złożyć te relacje z wejściami, utility i bombą w jedną
chronologiczną oś momentów.
