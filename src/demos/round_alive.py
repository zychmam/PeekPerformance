"""Global T:CT alive states from a verified start and recorded deaths."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from src.demos.round_index import round_state_index
from src.models.tactical import AliveState, Status, derived_id

ALIVE_DETECTOR_VERSION = 2


def assign_opening(round_tactics, evidence):
    """First enemy kill(s), preserving simultaneous ticks and source IDs."""
    refs = set(round_tactics.contact_references.get("first_enemy_kill", []))
    round_tactics.opening_kill_ids = sorted({
        eid for contact in round_tactics.contacts if contact.id in refs
        for eid in contact.evidence_ids if evidence[eid].source == "kills"
    })
    round_tactics.opening_status = (
        Status.OBSERVED if round_tactics.opening_kill_ids
        else Status.ABSENT if round_tactics.contacts_status == Status.ABSENT
        else Status.UNKNOWN
    )


def _side(value):
    try:
        return {2: "T", 3: "CT"}.get(int(value))
    except (TypeError, ValueError):
        return None


def build_alive_states(round_tactics, evidence, *, tick_rate, config, state_index=None):
    freeze = round_tactics.freeze_end_tick
    if freeze is None:
        return [], Status.UNKNOWN
    roster = {player.player_id: player.side for player in round_tactics.players
              if player.side in {"T", "CT"}}
    sides = {side: {pid for pid, member_side in roster.items() if member_side == side}
             for side in ("T", "CT")}
    events = [evidence[eid] for eid in round_tactics.event_ids]
    all_states = [event for event in events if event.source == "states"]
    states = [event for event in all_states if event.tick >= freeze]
    index = state_index or round_state_index(round_tactics, evidence)
    age = max(1, round(tick_rate * config.max_sample_age_seconds))
    gap = max(1, round(tick_rate * config.max_sample_gap_seconds))
    baseline, baseline_refs = {}, []
    valid = {side: len(sides[side]) == 5 for side in sides}
    for pid, side in roster.items():
        sample = index.latest(freeze, player_id=pid, max_age_ticks=age,
                              max_gap_ticks=gap)
        row = sample.row
        if (row is None or _side(row.get("team_num")) != side
                or pd.isna(row.get("is_alive"))):
            valid[side] = False
            continue
        baseline[pid] = bool(row["is_alive"])
        baseline_refs.append(str(row["event_id"]))

    death_events = defaultdict(list)
    first_death = {}
    invalid_deaths = defaultdict(set)
    for event in events:
        if event.source != "kills" or event.tick < freeze:
            continue
        pid = str(event.data.get("user_steamid"))
        side = _side(event.data.get("user_team_num"))
        if pid not in roster or roster[pid] != side:
            invalid_deaths[event.tick].add(side or "T")
            if pid in roster:
                invalid_deaths[event.tick].add(roster[pid])
            if side is None:
                invalid_deaths[event.tick].add("CT")
            continue
        death_events[event.tick].append((pid, event.id))
        first_death.setdefault(pid, event.tick)

    # A state sample contradicting the death stream makes later counts unknown.
    first_contradiction = {}
    for event in states:
        row = event.data
        pid = str(row.get("steamid"))
        if pid not in baseline or pd.isna(row.get("is_alive")):
            continue
        death_tick = first_death.get(pid)
        if event.tick == death_tick:
            continue  # Same-tick samples have no reliable before/after order.
        expected_alive = baseline[pid] and (death_tick is None or event.tick < death_tick)
        if bool(row["is_alive"]) != expected_alive or _side(row.get("team_num")) != roster[pid]:
            side = roster[pid]
            if side not in first_contradiction or event.tick < first_contradiction[side][0]:
                first_contradiction[side] = (event.tick, [event.id])
            elif event.tick == first_contradiction[side][0]:
                first_contradiction[side][1].append(event.id)
    contradictions = defaultdict(dict)
    for side, (tick, ids) in first_contradiction.items():
        contradictions[tick][side] = ids

    alive = {pid for pid, value in baseline.items() if value}
    dead = {pid for pid, value in baseline.items() if not value}
    refs = list(dict.fromkeys(baseline_refs))
    states_out = []
    degraded = {"T": False, "CT": False}
    kills_known = (
        round_tactics.availability.get("kills") is not None
        and round_tactics.availability["kills"].status in {Status.OBSERVED, Status.ABSENT}
    )
    checkpoints = sorted({freeze, *death_events, *invalid_deaths, *contradictions})
    for tick in checkpoints:
        previously_dead = set(dead)
        processed = set()
        for pid, eid in death_events.get(tick, []):
            refs.append(eid)
            if pid in previously_dead:
                degraded[roster[pid]] = True
            if pid in processed:
                continue
            processed.add(pid)
            dead.add(pid)
            alive.discard(pid)
        for side in invalid_deaths.get(tick, ()):
            degraded[side] = True
        for side, ids in contradictions.get(tick, {}).items():
            degraded[side] = True
            refs.extend(ids)
        counts = {
            side: len(alive & members) if valid[side] and not degraded[side] else None
            for side, members in sides.items()
        }
        status = (
            Status.OBSERVED if all(count is not None for count in counts.values())
            and round_tactics.availability.get("states") is not None
            and round_tactics.availability["states"].status == Status.OBSERVED
            and (tick == freeze or kills_known)
            else Status.PARTIAL if refs else Status.UNKNOWN
        )
        source_ids = list(dict.fromkeys(refs))
        states_out.append(AliveState(
            derived_id(round_tactics.number, "alive", *source_ids, f"tick:{tick}"),
            round_tactics.number, tick, counts["T"], counts["CT"],
            sorted(alive), sorted(dead), source_ids, status,
        ))
    result_status = (
        Status.OBSERVED if kills_known and states_out
        and all(s.status == Status.OBSERVED for s in states_out)
        else Status.PARTIAL if states_out and any(s.evidence_ids for s in states_out)
        else Status.UNKNOWN
    )
    return states_out, result_status
