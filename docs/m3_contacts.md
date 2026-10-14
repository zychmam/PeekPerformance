# M3.2 — kontakty rundy

Detektor `src/demos/round_contacts.py` wykorzystuje zapisane `damage`, `kills`
i `states`. Wynik jest częścią `RoundTactics.contacts` i nie wymaga ponownego
parsowania dema. Kontrakt ma schemat 6. Przykłady wejściowe i oczekiwane ticki:
[referencje M3.1](m3_reference_rounds.md).

## Zasady

- Dodatnie, rzeczywiste obrażenia HP przeciwnika tworzą kontakt `damage`.
  Friendly fire, samobójstwo, world damage i 0 HP nie tworzą kontaktu przeciwników.
- Obrażenia jednej uporządkowanej pary w tym samym ticku są jednym kontaktem:
  sumujemy wyłącznie `enemy_damage` i zachowujemy każde źródłowe ID. Frag tej
  samej pary w tym ticku dołącza do kontaktu bez dodania kolejnych HP.
- Frag bez takiego zdarzenia obrażeń tworzy `kill_only` z nieznaną wartością HP.
  Późniejszy frag nie scala się z wcześniejszymi obrażeniami w wymyślony duel.
- `modality` odróżnia broń, utility, mieszane źródła i nieznaną broń. Nie
  wnioskujemy o widoczności, zwycięstwie pojedynku ani skuteczności granatu
  z samego faktu kontaktu.
- Obie pozycje odnoszą się do ostatniej próbki `states` **sprzed** ticku
  kontaktu. Limit wieku to 1 s, a luki próbkowania do 2 s według
  `DetectorConfig` i zegara rundy. Przyszła lub nieświeża próbka nie staje się
  pozycją. Sam stan pozycji może być zaobserwowany bez nazwy regionu, jeżeli
  profil mapy jest niedostępny.
- `contact_references` rundy wskazuje pierwszy damage, pierwszy damage z broni,
  pierwszy damage od utility, pierwszy frag oraz pierwsze kontakty każdego
  rodzaju. Gracz ma własne `first_any`, `first_dealt`, `first_received`,
  `first_firearm`, `first_utility`. Wszystkie remisy w ticku zachowują listę ID;
  pojedyncze `first_contact_id` jest wówczas puste.
- Pusty wynik ma `unknown`, jeżeli brak zdarzeń nie został potwierdzony
  diagnostyką źródeł. `Fight`, refragi i liczebność pozostają do M3.3–M4.

ID kontaktu powstaje z kanonicznych ID obrażeń albo samego fraga oraz numeru
rundy. Miejsce jest dodatkiem mapowym do tej samej obserwacji; nie zmienia ID.
Wybrany gracz nie uruchamia detekcji ponownie: jego referencje są projekcją
jednej listy kontaktów rundy.

## Sprawdzenie

`tests/test_round_contacts.py` obejmuje podwójne źródła HP/frag, friendly fire,
brak profilu, przyszłe i stare próbki, role gracza oraz remisy ticków.
`scripts/verify_m3_contacts.py` czyta produkcyjną SQLite w trybie `mode=ro` i
porównuje osiem rund Mirage/Inferno z oczekiwanymi tickami oraz referencjami E1.
W tej próbie wszystkie 532 pozycje uczestników 266 kontaktów miały próbkę sprzed
zdarzenia. To nie dowodzi dokładności każdego przypisanego regionu ani
kompletności strumienia zdarzeń; luki w innych rundach pozostają jawne.
