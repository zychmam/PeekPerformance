"""Observed region intervals for a whole round; gaps never become movement."""

from bisect import bisect_right
from collections import defaultdict

from src.demos.tactical_ids import action_id
from src.maps.resolver import resolve_region
from src.models.tactical import RegionStay, RegionTransition, Status

MOVEMENT_VERSION = 1


def enrich_movement(record, evidence, profile, *, tick_rate, config, state_index):
    record.region_stays = []
    record.region_transitions = []
    record.movement_gaps = []
    if profile is None or record.freeze_end_tick is None:
        record.movement_status = Status.UNKNOWN
        return
    regions = profile.regions_by_id
    max_gap = round(config.max_sample_gap_seconds * tick_rate)
    max_age = round(config.max_sample_age_seconds * tick_rate)
    deaths = defaultdict(list)
    for eid in record.event_ids:
        event = evidence[eid]
        if event.source == "kills":
            deaths[str(event.data.get("user_steamid"))].append(event)
    for player in record.players:
        samples = state_index.between(
            record.freeze_end_tick, record.end_tick, player_id=player.player_id
        )
        current = None
        previous = None
        last_tick = record.freeze_end_tick

        def close(reason):
            nonlocal current
            if current:
                current.end_reason = reason
                record.region_stays.append(current)
                current = None

        for sample in samples:
            tick = int(sample["tick"])
            # Earliest death is terminal even if a later state erroneously says alive.
            death = next((event for event in deaths[player.player_id] if event.tick <= tick), None)
            if death or sample.get("is_alive") is False or sample.get("is_alive") == 0:
                if current and death and 0 <= death.tick - current.end_tick <= max_gap:
                    current.end_tick = death.tick
                    current.evidence_ids.append(death.id)
                close("death")
                break
            if sample.get("is_alive") not in {True}:
                close("gap")
                record.movement_gaps.append(
                    {"player_id": player.player_id, "start_tick": last_tick, "end_tick": tick}
                )
                previous, last_tick = None, tick
                continue
            if tick - last_tick > max_gap:
                close("gap")
                record.movement_gaps.append(
                    {"player_id": player.player_id, "start_tick": last_tick, "end_tick": tick}
                )
                previous = None
            rid = resolve_region(sample, profile)
            eid = str(sample["event_id"])
            region = regions.get(rid)
            forward = region.is_forward(player.side, sample) if region else None
            if current is None or current.area != rid or current.forward != forward:
                old = current
                close("transition")
                current = RegionStay(
                    action_id("stay", record.number, player.player_id, tick, rid),
                    player.player_id,
                    player.side,
                    rid,
                    tick,
                    tick,
                    Status.OBSERVED if rid else Status.UNKNOWN,
                    "sample_end",
                    [eid],
                    defense_sector=region.defense_sector if region else None,
                    forward=forward,
                )
                if old and old.area and rid and previous:
                    old.next_area, current.previous_area = rid, old.area
                if old and old.area and rid and old.area != rid and previous:
                    record.region_transitions.append(
                        RegionTransition(
                            player.player_id,
                            old.area,
                            rid,
                            old.end_tick,
                            tick,
                            [str(previous["event_id"]), eid],
                        )
                    )
            else:
                current.end_tick = tick
                # Compact provenance: first and latest sample, no copied trajectory.
                current.evidence_ids = list(dict.fromkeys([current.evidence_ids[0], eid]))
            previous, last_tick = sample, tick
        close("round_end" if record.end_tick - last_tick <= max_age else "coverage_end")
        # Death terminates coverage eligibility, not a missing trajectory tail.
        if (not samples or record.end_tick - last_tick > max_gap) and not deaths[player.player_id]:
            record.movement_gaps.append(
                {
                    "player_id": player.player_id,
                    "start_tick": last_tick,
                    "end_tick": record.end_tick,
                }
            )
    unknown = any(stay.area is None for stay in record.region_stays)
    record.movement_status = (
        Status.PARTIAL
        if unknown or record.movement_gaps
        else Status.OBSERVED
        if record.region_stays
        else Status.UNKNOWN
    )
    snapshot = record.ct_setup.setup_before_contact
    if snapshot:
        assignments = {}
        refs = []
        for player in snapshot.players:
            if not player.get("alive"):
                continue
            region = regions.get(player.get("area"))
            assignments[player["player_id"]] = region.defense_sector if region else None
        refs.extend(snapshot.evidence_ids)
        record.ct_sectors_before_contact = {
            "tick": snapshot.tick,
            "assignments": assignments,
            "counts": {
                sector: sum(value == sector for value in assignments.values())
                for sector in sorted(
                    {r.defense_sector for r in regions.values() if r.defense_sector}
                )
            },
            "unknown": len(
                {pid for pid, value in assignments.items() if value is None}
                | set(snapshot.missing_players)
            ),
            "evidence_ids": refs,
            "status": str(snapshot.status),
        }


def stay_at(record, player_id, tick):
    return next(
        (
            stay
            for stay in record.region_stays
            if stay.player_id == player_id and stay.start_tick <= tick <= stay.end_tick
        ),
        None,
    )


class MovementIndex:
    def __init__(self, record):
        self.players = defaultdict(list)
        for stay in record.region_stays:
            self.players[stay.player_id].append(stay)
        self.starts = {}
        for pid, stays in self.players.items():
            stays.sort(key=lambda stay: stay.start_tick)
            self.starts[pid] = [stay.start_tick for stay in stays]

    def at(self, player_id, tick):
        stays = self.players.get(player_id, [])
        i = bisect_right(self.starts.get(player_id, []), tick) - 1
        return stays[i] if i >= 0 and tick <= stays[i].end_tick else None
