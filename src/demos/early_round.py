"""R2 observed early setup; no inferred intent, line of sight or utility coverage."""

from collections import defaultdict

import pandas as pd

from src.demos.early_interpretation import interpret_preparation
from src.demos.round_index import RoundIndex
from src.maps.registry import get_profile
from src.maps.resolver import resolve_region
from src.models.observations import DetectorConfig
from src.models.tactical import EarlyUtility, Movement, SetupSnapshot, Status

EARLY_DETECTOR_VERSION = 2
TICK_RATE = 64
EARLY_SECONDS = 15
SNAPSHOT_SECONDS = (0, 5, 10, 15)
MAX_AGE = 64
MAX_GAP = 128
CONFIRM_TICKS = 64


def area(data, profile=None):
    """Stable region ID; physical location is separate from its tactical roles."""
    return data.get("region_id") or (resolve_region(data, profile) if profile else None)


def _movements(samples, player_id, *, profile=None, max_gap=MAX_GAP, confirm_ticks=CONFIRM_TICKS):
    """Stable nav-area changes: continuous alive samples, target held >=1 second."""
    result = []
    anchor = candidate = last = None
    for sample in samples:
        current = area(sample.data, profile)
        if (
            not sample.data.get("is_alive")
            or current is None
            or last is not None
            and sample.tick - last.tick > max_gap
        ):
            anchor = candidate = None
        if not sample.data.get("is_alive") or current is None:
            last = sample
            continue
        if anchor is None:
            anchor = sample
        elif current == area(anchor.data, profile):
            anchor, candidate = sample, None
        elif candidate is None or current != area(candidate.data, profile):
            candidate = sample
        elif sample.tick - candidate.tick >= confirm_ticks:
            result.append(
                Movement(
                    player_id,
                    area(anchor.data, profile),
                    current,
                    anchor.tick,
                    candidate.tick,
                    sample.tick,
                    list(dict.fromkeys([anchor.id, candidate.id, sample.id])),
                )
            )
            anchor, candidate = sample, None
        last = sample
    return result


def enrich_early_round(rnd, evidence, map_name, *, profile=None, config=None, tick_rate=64):
    """Fill typed observations once from round-local evidence. Missing != zero."""
    profile = profile or get_profile(map_name)
    config = config or DetectorConfig()
    max_age = round(config.max_sample_age_seconds * tick_rate)
    max_gap = round(config.max_sample_gap_seconds * tick_rate)
    if rnd.freeze_end_tick is None:
        for prep in (rnd.t_preparation, rnd.ct_setup):
            prep.status = prep.movement_status = prep.utility_status = Status.UNKNOWN
            prep.interpretation_status = Status.UNKNOWN
        return
    freeze = rnd.freeze_end_tick
    end = min(rnd.end_tick, freeze + round(config.early_seconds * tick_rate))
    states = defaultdict(list)
    for eid in rnd.event_ids:
        ev = evidence[eid]
        if ev.source == "states" and freeze <= ev.tick <= end:
            states[str(ev.data.get("steamid"))].append(ev)
    indexed_states = RoundIndex(
        pd.DataFrame(
            [
                {**s.data, "tick": s.tick, "event_id": s.id}
                for samples in states.values()
                for s in samples
            ]
        )
    )
    for team, side, prep in ((2, "T", rnd.t_preparation), (3, "CT", rnd.ct_setup)):
        expected = {p.player_id for p in rnd.players if p.side == side}
        prep.snapshots = []
        prep.movements = []
        prep.utility = []
        for seconds in config.snapshot_seconds:
            tick = freeze + round(seconds * tick_rate)
            if tick > rnd.end_tick:
                continue
            players, refs, missing, counts = [], [], [], defaultdict(int)
            for pid in sorted(expected):
                lookup = indexed_states.latest(
                    tick, player_id=pid, max_age_ticks=max_age, max_gap_ticks=max_gap
                )
                sample = evidence[lookup.row["event_id"]] if lookup.row else None
                if (
                    sample is None
                    or tick - sample.tick > max_age
                    or sample.data.get("team_num") != team
                    or sample.data.get("is_alive") is None
                ):
                    missing.append(pid)
                    continue
                alive = bool(sample.data["is_alive"])
                location = area(sample.data, profile) if alive else None
                if alive and location is None:
                    missing.append(pid)
                if alive and location is not None:
                    counts[location] += 1
                refs.append(sample.id)
                players.append(
                    {
                        "player_id": pid,
                        "alive": alive,
                        "area": location,
                        "place": sample.data.get("last_place_name"),
                        "sample_tick": sample.tick,
                        "has_bomb": sample.data.get("has_bomb"),
                    }
                )
            status = (
                Status.UNKNOWN
                if not expected or not players
                else Status.PARTIAL
                if missing or len(expected) != 5
                else Status.OBSERVED
            )
            prep.snapshots.append(
                SetupSnapshot(
                    seconds,
                    tick,
                    status,
                    players,
                    dict(counts),
                    missing,
                    refs,
                )
            )
        # Early-window coverage independently of late-round gaps.
        continuous = len(expected) == 5
        for pid in sorted(expected):
            samples = [s for s in states[pid] if s.data.get("team_num") == team]
            continuous &= (
                bool(samples)
                and samples[0].tick <= freeze + max_age
                and samples[-1].tick >= end - max_age
                and all(
                    b.tick - a.tick <= max_gap for a, b in zip(samples, samples[1:], strict=False)
                )
                and all(
                    s.data.get("is_alive") is not None
                    and (not s.data["is_alive"] or area(s.data, profile) is not None)
                    for s in samples
                )
            )
            prep.movements.extend(
                _movements(
                    samples, pid, profile=profile, max_gap=max_gap, confirm_ticks=round(tick_rate)
                )
            )
        prep.status = (
            Status.OBSERVED
            if continuous
            else Status.PARTIAL
            if any(s.evidence_ids for s in prep.snapshots)
            else Status.UNKNOWN
        )
        prep.movement_status = (
            Status.OBSERVED
            if prep.movements and continuous
            else Status.ABSENT
            if continuous
            else prep.status
        )
        prep.utility_status = rnd.availability["utility"].status
        for eid in prep.utility_ids:
            ev = evidence[eid]
            prep.utility.append(
                EarlyUtility(
                    ev.data.get("user_steamid"),
                    str(ev.data.get("kind", "Unknown")),
                    ev.tick,
                    (ev.tick - freeze) / tick_rate,
                    None,
                    {key: ev.data.get(key) for key in ("x", "y", "z")},
                    [eid],
                )
            )
        if not prep.utility and prep.utility_status == Status.OBSERVED:
            prep.utility_status = (
                Status.UNKNOWN if rnd.availability["utility"].reasons else Status.ABSENT
            )
    if profile is not None:
        interpret_preparation(rnd, evidence, profile=profile, config=config, tick_rate=tick_rate)
    else:
        for prep in (rnd.t_preparation, rnd.ct_setup):
            prep.interpretation_status = Status.UNKNOWN
