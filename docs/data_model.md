# Model danych: PeekPerformance – Leetify Match Export

**Źródło:** Leetify Public API (https://leetify.com) — platforma analityczna dla Counter-Strike 2.  
**Dostępne formaty eksportu:** CSV (flat), JSON (hierarchiczny, zalecany dla LLM) i Compact text (lekki format dla AI).

---

## Format JSON (zalecany dla AI/LLM)

Hierarchiczna struktura — każdy mecz jest samodzielnym obiektem z podziałem na drużyny. LLM nie musi nic łączyć ani mapować.

### Struktura najwyższego poziomu

```json
{
  "subject_player_steam64_id": "76561198008873400",
  "export_date": "2026-04-03",
  "total_matches": 6,
  "matches": [ ... ]
}
```

- `subject_player_steam64_id` — steam ID gracza, którego mecze zostały wyeksportowane (nie musi być "głównym bohaterem" artykułu)
- `matches` — tablica meczy posortowana chronologicznie

### Struktura meczu

```json
{
  "match_id": "a0281340-560e-4eb1-9a4d-f5fd43dba638",
  "date": "2026-04-01T21:13:22.000Z",
  "map": "de_anubis",
  "data_source": "faceit",
  "rounds_played": 21,
  "result": "loss",
  "score": "8:13",
  "teams": [
    {
      "team_number": 2,
      "score": 8,
      "is_subject_team": true,
      "players": [ ... ]
    },
    {
      "team_number": 3,
      "score": 13,
      "is_subject_team": false,
      "players": [ ... ]
    }
  ]
}
```

- `result` — `"win"` / `"loss"` / `"tie"` z perspektywy `subject_player`
- `score` — wynik w formacie "own:enemy" z perspektywy `subject_player`
- `is_subject_team` — `true` dla drużyny, w której gra `subject_player`
- Każdy team zawiera 5 graczy z pełnymi statystykami (66 pól)

### Struktura gracza (wewnątrz `players`)

Każdy gracz ma **wszystkie** pola opisane poniżej w sekcjach referencyjnych.

---

## Format Compact (LLM-optimized, `.txt`)

**Najlżejszy format** — ~5-8× mniej tokenów niż JSON. Pipe-separated tabele z ~35 kluczowymi statystykami.

### Struktura pliku

```
# CS2 Export | subject=76561198008873400 | 2026-04-03 | 6 matches

## M1 | 2026-04-01 | de_anubis | LOSS 8:13 | faceit | 21r

### TEAM 2 (8) ★
name|kills|deaths|kd|adr|rating|ct_rat|t_rat|hs%|preaim|react|cs%|3k|4k|5k|flash_foe|trade%|util_death
creep7|15|18|0.83|72.10|-3.0|1.0|-6.0|0.21|8.20|0.52|0.75|0|0|0|4|0.60|245

### TEAM 3 (13)
name|kills|deaths|kd|adr|rating|...
21ARMAS|23|11|2.09|109.76|7.2|...
```

- `★` oznacza drużynę `subject_player`
- Nagłówki kolumn pojawiają się raz per drużyna (nie per gracz)
- `M1`, `M2`... — numeracja meczy chronologicznie
- Wszystkie wartości float zaokrąglone do 2 miejsc

### Lista pól w formacie compact (35 pól)

| Skrót | Pełna nazwa API | Opis |
|---|---|---|
| name | name | Nick gracza |
| steam64 | steam64_id | Steam ID |
| kills | total_kills | Zabójstwa |
| deaths | total_deaths | Śmierci |
| assists | total_assists | Asysty |
| kd | kd_ratio | Kill/Death ratio |
| adr | dpr | Damage Per Round |
| dmg | total_damage | Łączny damage |
| rating | leetify_rating | Rating Leetify za mecz ×100 (np. 7.2 = oryg. 0.072) |
| ct_rat | ct_leetify_rating | Rating za stronę CT ×100 |
| t_rat | t_leetify_rating | Rating za stronę T ×100 |
| score | score | Punkty scoreboard |
| mvps | mvps | MVP rundy |
| rounds | rounds_count | Łączne rundy |
| surv% | rounds_survived_percentage | % rund przeżytych |
| hs_kills | total_hs_kills | Zabójstwa headshotem |
| hs% | accuracy_head | % headshot |
| acc_spotted | accuracy_enemy_spotted | Celność na widocznego wroga |
| preaim | preaim | Kąt preaim (° — niżej = lepiej) |
| react | reaction_time | Czas reakcji (s — niżej = lepiej) |
| cs% | counter_strafing_shots_good_ratio | Counter-strafe ratio |
| spray_acc | spray_accuracy | Celność spray'a |
| 2k | multi2k | Rundy z 2 killami |
| 3k | multi3k | Rundy z 3 killami |
| 4k | multi4k | Rundy z 4 killami (highlight) |
| 5k | multi5k | Ace (najrzadsze) |
| flash_thrown | flashbang_thrown | Rzucone flashe |
| flash_foe | flashbang_hit_foe | Oślepieni przeciwnicy |
| flash_kill | flashbang_leading_to_kill | Flashe → kill |
| smokes | smoke_thrown | Dymne |
| molotovs | molotov_thrown | Mołotowy |
| he | he_thrown | Granaty HE |
| util_death | utility_on_death_avg | Wartość $ granatów przy śmierci |
| trade% | trade_kills_success_percentage | % udanych trade killi |
| traded% | traded_deaths_success_percentage | % pomścionych śmierci |

---

## Format CSV (flat)

1 wiersz = statystyki 1 gracza w 1 meczu. N meczy × 10 graczy = N×10 wierszy, 72 kolumny. Kolumny na poziomie meczu mają prefix `match_`.

---

## Referencja pól statystyk gracza

Te same pola występują w obu formatach (w JSON jako pola obiektu gracza, w CSV jako kolumny).

| Kolumna | Opis | Zakres/interpretacja |
|---|---|---|
| `total_kills` | Łączne zabójstwa | Więcej = lepiej |
| `total_deaths` | Łączne śmierci | Mniej = lepiej |
| `total_assists` | Asysty | — |
| `kd_ratio` | Kill/Death ratio | >1.0 = pozytywny, 1.0 = neutralny |
| `dpr` | Damage Per Round (ADR) | ~80 = średni, >100 = bardzo dobry |
| `total_damage` | Łączny damage w meczu | — |
| `leetify_rating` | Algorytmiczny rating Leetify na ten mecz | ~0 = średni, >0.05 = dobry, <-0.05 = słaby. **NIE jest to ogólny rating gracza, a ocena za ten konkretny mecz** |
| `ct_leetify_rating` | Rating Leetify tylko za rundy po stronie CT (obrona) | j.w. |
| `t_leetify_rating` | Rating Leetify tylko za rundy po stronie T (atak) | j.w. |
| `score` | Punkty scoreboard w meczu | — |
| `mvps` | Liczba rund z tytułem MVP | — |

---

## Statystyki rund

| Kolumna | Opis |
|---|---|
| `rounds_count` | Łączna liczba rozegranych rund |
| `rounds_won` | Rundy wygrane przez drużynę gracza |
| `rounds_lost` | Rundy przegrane |
| `rounds_survived` | Ile rund gracz przeżył |
| `rounds_survived_percentage` | % rund, w których gracz przeżył (0.0–1.0) |

---

## Multi-kille (highlights)

| Kolumna | Opis |
|---|---|
| `multi1k` | Rundy z dokładnie 1 zabójstwem |
| `multi2k` | Rundy z 2 zabójstwami (double kill) |
| `multi3k` | Rundy z 3 zabójstwami (triple kill) — wartościowy moment |
| `multi4k` | Rundy z 4 zabójstwami (quad kill) — **highlight meczu** |
| `multi5k` | Rundy z 5 zabójstwami (ace) — **najrzadsze, najbardziej spektakularne** |

---

## Celność (aim)

| Kolumna | Opis | Interpretacja |
|---|---|---|
| `accuracy` | Ogólna celność (trafienia/strzały) | 0.0–1.0 |
| `accuracy_enemy_spotted` | Celność gdy widzi przeciwnika | ~0.30–0.35 = dobra |
| `accuracy_head` | % strzałów w głowę | >0.25 = dobry headshot ratio |
| `total_hs_kills` | Zabójstwa headshotem | — |
| `spray_accuracy` | Celność podczas spray'a (seria strzałów) | 0.0–1.0 |
| `shots_fired` | Łączne oddane strzały | — |
| `shots_fired_enemy_spotted` | Strzały oddane gdy widział przeciwnika | — |
| `shots_hit_enemy_spotted` | Trafienia gdy widział przeciwnika | — |
| `shots_hit_foe` | Trafienia w przeciwników | — |
| `shots_hit_friend` | Trafienia w sojuszników (friendly fire) | 0 = idealnie |

---

## Mechanika gry (skill)

| Kolumna | Opis | Interpretacja |
|---|---|---|
| `preaim` | Kąt preaim (°) — jak blisko celownik jest wroga przed walką | **Niżej = lepiej**. <7° = elitarny, 7–10 = dobry, >12 = słaby |
| `reaction_time` | Czas reakcji w sekundach | **Niżej = lepiej**. <0.50s = szybki, >0.70s = wolny |
| `counter_strafing_shots_good_ratio` | % strzałów z poprawnym counter-strafem | >0.85 = dobry, to kluczowa mechanika CS2 |
| `counter_strafing_shots_all` | Łączne strzały podczas ruchu | — |
| `counter_strafing_shots_good` | Strzały z poprawnym counter-strafem | — |
| `counter_strafing_shots_bad` | Strzały bez counter-strafe'a (w ruchu) | — |

---

## Granaty i utility

| Kolumna | Opis |
|---|---|
| `he_thrown` | Rzucone granaty HE (odłamkowe) |
| `molotov_thrown` | Rzucone koktajle Mołotowa / granaty zapalające |
| `smoke_thrown` | Rzucone granaty dymne |
| `flashbang_thrown` | Rzucone granaty oślepiające |
| `flashbang_hit_foe` | Ilu przeciwników oślepionych |
| `flashbang_hit_friend` | Ilu sojuszników oślepionych (źle) |
| `flashbang_hit_foe_avg_duration` | Średni czas oślepienia przeciwnika (s) |
| `flashbang_leading_to_kill` | Flashe prowadzące do zabójstwa |
| `flash_assist` | Asysty flashem |
| `he_foes_damage_avg` | Średni damage HE na przeciwnikach na granat |
| `he_friends_damage_avg` | Średni damage HE na sojusznikach (friendly fire) |
| `utility_on_death_avg` | Średnia wartość $ granatów przy śmierci — **niżej = lepiej** (gracz zużywa granaty przed śmiercią) |

---

## Trade kille (wymiana fragów)

| Kolumna | Opis |
|---|---|
| `trade_kill_opportunities` | Sytuacje, gdzie gracz mógł zrobić trade kill (zemsta za zabitego kolegę) |
| `trade_kill_attempts` | Ile razy próbował |
| `trade_kills_succeed` | Ile razy udało się |
| `trade_kill_attempts_percentage` | % szans gdzie próbował (0.0–1.0) |
| `trade_kills_success_percentage` | % udanych prób (0.0–1.0) |
| `trade_kill_opportunities_per_round` | Okazje do trade killa per runda |
| `traded_death_opportunities` | Sytuacje, gdzie teammate mógł pomścić śmierć gracza |
| `traded_death_attempts` | Ile razy teammate próbował |
| `traded_deaths_succeed` | Ile razy teammate udanie pomścił |
| `traded_death_attempts_percentage` | % sytuacji gdzie teammate próbował pomścić (0.0–1.0) |
| `traded_deaths_success_percentage` | % udanych pomścień (0.0–1.0) |
| `traded_deaths_opportunities_per_round` | Okazje do pomścienia per runda |

---

## Wskazówki do pisania artykułu esportowego

2. **Ustal wynik każdego meczu** korzystając z algorytmu powyżej (sekcja "Jak ustalić wynik").
3. **Leetify rating ≠ K/D**: gracz z dużym K/D ale złym ratingiem → fragy nie miały wpływu na rundy (np. eco-fragi, exit-kille). Rating Leetify waży fragy kontekstem rundy.
4. **Preaim + reaction_time** to najlepsze metryki mechanicznego poziomu gracza. Porównuj graczy między sobą w tym samym meczu.
5. **Counter-strafing ratio** > 0.85 oznacza dojrzałą mechanikę — gracz strzela stojąc, nie w biegu.
6. **Multi4k/multi5k** to momenty do wyróżnienia jako highlighty meczu. Szukaj ich w danych.
7. **Trade kill success %** mówi o graniu zespołowym — wysokie = dobrze gra z drużyną.
8. **Utility on death** niska = gracz efektywnie zużywa granaty (nie marnuje pieniędzy umierając z pełnym ekwipunkiem).
9. **Porównuj graczy z obu drużyn** — kontekst poziomu przeciwników jest ważny (np. "gracz zrobił ACE mimo że przeciwnik miał ADR 135").
10. **Narracja mecz po meczu** — ułóż mecze chronologicznie (`match_date`) i opisz sesję: formę, wzloty, spadki, najlepszy/najgorszy mecz.
