"""Conservative early-round profile; orientation is not the eventual attack target."""

from collections import Counter, defaultdict

from src.maps.resolver import (
    is_forward,
    region_direction,
    region_label,
    region_site,
    resolve_region,
)
from src.models.observations import DetectorConfig
from src.models.tactical import Finding, Status

INTERPRETATION_VERSION = 1
LIMITS = ["Pozycje nie dowodzą intencji, widoczności ani kontroli przestrzeni."]


def direction(area, profile=None):
    return region_direction(area, profile) or "other"


def _finding(prep, text, refs, *, interpretation=False, complete=True):
    if refs:
        prep.findings.append(
            Finding(
                text,
                "interpretation" if interpretation else "observation",
                list(dict.fromkeys(refs)),
                "limited" if interpretation or not complete else "confirmed",
                LIMITS.copy() if interpretation else [],
            )
        )


def interpret_preparation(rnd, evidence, *, profile=None, config=None, tick_rate=64):
    config = config or DetectorConfig()
    for side, prep in (("T", rnd.t_preparation), ("CT", rnd.ct_setup)):
        prep.findings = []
        prep.formation = prep.tempo = prep.activity = prep.bomb_area = None
        prep.orientation = {}
        prep.orientation_tick = None
        prep.separated_player_ids = []
        prep.activity_ids = []
        prep.first_site_presence_seconds = None
        snaps = [s for s in prep.snapshots if s.seconds >= 10 and s.evidence_ids]
        # Describe the latest available scheduled moment, never backfill a missing
        # 15s observation with 10s without exposing the actual chosen time.
        snap = snaps[-1] if snaps else None
        prep.interpretation_status = Status.UNKNOWN if snap is None else snap.status
        if snap:
            alive = [p for p in snap.players if p["alive"] and p["area"]]
            counts = Counter(direction(p["area"], profile) for p in alive)
            prep.orientation = dict(counts)
            prep.orientation_tick = snap.tick
            complete = snap.status == Status.OBSERVED
            if side == "T":
                summary = ", ".join(
                    f"{'pozostałe' if key == 'other' else key}: {n}" for key, n in counts.items()
                )
                _finding(
                    prep,
                    f"Po {snap.seconds} s kierunki obecności T: "
                    f"{summary or 'nieustalone'}. "
                    + ("Pełna obserwacja." if complete else "Widoczna część składu."),
                    snap.evidence_ids,
                    complete=complete,
                )
                # A 4+1 requires five living observed players; a missing/dead fifth
                # is never called a detached player or a lurker.
                if complete and len(alive) == 5:
                    main, n = counts.most_common(1)[0]
                    if main != "other" and n == 5:
                        prep.formation = "concentrated_5"
                        text = f"Pięciu T skupionych w kierunku {main}."
                    elif main != "other" and n == 4 and counts.get("other", 0) == 0:
                        prep.formation = "4_plus_1"
                        prep.separated_player_ids = [
                            p["player_id"] for p in alive if direction(p["area"], profile) != main
                        ]
                        text = f"Ustawienie 4+1: czterech T w kierunku {main}, jeden poza grupą."
                    elif counts.get("other", 0) == 0 and len(counts) >= 2:
                        prep.formation = "distributed"
                        text = "T rozłożeni na kilku kierunkach."
                    else:
                        text = None
                    if text:
                        _finding(
                            prep,
                            text + " To profil ustawienia, cel ataku pozostaje nieustalony.",
                            snap.evidence_ids,
                            interpretation=True,
                        )
                carriers = [p for p in alive if p["has_bomb"] is True]
                if len(carriers) == 1:
                    prep.bomb_area = carriers[0]["area"]
                    _finding(
                        prep,
                        f"Bomba po {snap.seconds} s: kierunek "
                        f"{direction(prep.bomb_area, profile)}.",
                        snap.evidence_ids,
                        complete=complete,
                    )
            else:
                sites = {r.site_id for r in profile.regions if r.kind == "site"}
                counts_by_site = Counter()
                for rid, count in snap.counts.items():
                    site = region_site(rid, profile)
                    if site:
                        counts_by_site[site] += count
                site_text = ", ".join(f"{site}: {counts_by_site[site]}" for site in sorted(sites))
                _finding(
                    prep,
                    f"Po {snap.seconds} s CT na site’ach: {site_text}; "
                    "łączniki i pozostałe pozycje osobno. "
                    + (
                        "Pełna obserwacja."
                        if complete
                        else "Liczby obejmują zaobserwowanych graczy."
                    ),
                    snap.evidence_ids,
                    complete=complete,
                )
        if prep.utility:
            kinds = Counter(u.kind for u in prep.utility)
            _finding(
                prep,
                "Utility w 0–15 s: " + ", ".join(f"{kind}: {n}" for kind, n in kinds.items()) + ".",
                [eid for u in prep.utility for eid in u.evidence_ids],
                complete=prep.utility_status == Status.OBSERVED,
            )
        if side == "T":
            entries = [
                e
                for e in rnd.observed_entries
                if rnd.freeze_end_tick
                <= e.start_tick
                <= rnd.freeze_end_tick + round(config.early_seconds * tick_rate)
            ]
            if entries:
                first = min(entries, key=lambda e: e.start_tick)
                prep.first_site_presence_seconds = (
                    first.start_tick - rnd.freeze_end_tick
                ) / tick_rate
                prep.tempo = "early_site_entry"
                _finding(
                    prep,
                    f"Potwierdzone wejście T do strefy {first.area} "
                    f"po {prep.first_site_presence_seconds:.1f} s. "
                    "Samo wejście nie określa rushu ani execute’u.",
                    first.evidence_ids,
                    complete=first.status == Status.OBSERVED,
                )
        else:
            # Positive forward presence can be reported even with gaps elsewhere.
            # Require the same alive player/place twice, with <=2s sampling gaps.
            by_player = defaultdict(list)
            for eid in prep.snapshot_ids:
                ev = evidence[eid]
                by_player[str(ev.data.get("steamid"))].append(ev)
            refs, forward_players, places = [], [], Counter()
            for pid, samples in by_player.items():
                start = previous = None
                for ev in samples:
                    place = ev.data.get("region_id") or resolve_region(ev.data, profile)
                    if not ev.data.get("is_alive") or not is_forward(place, "CT", profile, ev.data):
                        start = previous = None
                        continue
                    if (
                        previous is None
                        or ev.tick - previous.tick > config.max_sample_gap_seconds * tick_rate
                        or place
                        != (
                            previous.data.get("region_id") or resolve_region(previous.data, profile)
                        )
                    ):
                        start = ev
                    if ev.tick - start.tick >= tick_rate:
                        refs.extend([start.id, ev.id])
                        forward_players.append(pid)
                        places[region_label(place, profile)] += 1
                        break
                    previous = ev
            if refs:
                prep.activity = "forward_presence"
                prep.activity_ids = list(dict.fromkeys(refs))
                locations = ", ".join(f"{place}: {n}" for place, n in places.items())
                _finding(
                    prep,
                    f"Wysunięte pozycje CT: {locations}. "
                    f"Liczba graczy: {len(set(forward_players))}; potwierdzenie ≥1 s. "
                    "Nie potwierdza to zdobycia ani kontroli tych miejsc.",
                    refs,
                    interpretation=True,
                )
            elif prep.status == Status.OBSERVED:
                prep.activity = "no_confirmed_forward_presence"
                _finding(
                    prep,
                    "Brak potwierdzonej obecności CT w zdefiniowanych wysuniętych "
                    "strefach w 0–15 s. Nie przesądza to o pasywnym stylu gry.",
                    prep.snapshot_ids,
                    interpretation=True,
                )
