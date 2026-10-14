"""Exact-killer refrags and the observed 5-second response to an opening."""

from __future__ import annotations

from collections import defaultdict

from src.models.tactical import RefragLink, Status, derived_id

REFRAG_DETECTOR_VERSION = 3


def _side(value):
    try:
        return {2: "T", 3: "CT"}.get(int(value))
    except (TypeError, ValueError):
        return None


def _enemy_kills(record, evidence):
    roster = {player.player_id: player.side for player in record.players}
    kills = []
    for eid in record.event_ids:
        event = evidence[eid]
        if event.source != "kills" or event.tick < (record.freeze_end_tick or record.start_tick):
            continue
        attacker = str(event.data.get("attacker_steamid"))
        victim = str(event.data.get("user_steamid"))
        a_side = _side(event.data.get("attacker_team_num"))
        v_side = _side(event.data.get("user_team_num"))
        if (attacker == victim or a_side not in {"T", "CT"} or v_side not in {"T", "CT"}
                or a_side == v_side or roster.get(attacker) != a_side
                or roster.get(victim) != v_side):
            continue
        kills.append(event)
    return sorted(kills, key=lambda item: (item.tick, item.id))


def enrich_refrags(record, evidence, *, tick_rate, response_seconds):
    """One earliest reply per death; one reply may cover several teammates' deaths."""
    kills = _enemy_kills(record, evidence)
    source = record.availability.get("kills")
    source_status = source.status if source else Status.UNKNOWN
    roster_sides = {side: {p.player_id for p in record.players if p.side == side}
                    for side in ("T", "CT")}
    roster_complete = (all(len(ids) == 5 for ids in roster_sides.values())
                       and not roster_sides["T"].intersection(roster_sides["CT"]))
    window_ticks = max(0, round(tick_rate * response_seconds))
    by_victim = defaultdict(list)
    for event in kills:
        by_victim[str(event.data["user_steamid"])].append(event)

    links = []
    seen_deaths = set()
    for death in kills:
        dead_player = str(death.data["user_steamid"])
        if dead_player in seen_deaths:
            continue  # duplicate death events do not manufacture multiple trades
        seen_deaths.add(dead_player)
        killer = str(death.data["attacker_steamid"])
        end = min(record.end_tick, death.tick + window_ticks)
        response = next((event for event in by_victim[killer]
                         if death.tick < event.tick <= end
                         and str(event.data.get("attacker_steamid")) != dead_player
                         and _side(event.data.get("attacker_team_num"))
                         == _side(death.data.get("user_team_num"))), None)
        if response is None:
            continue
        ids = [death.id, response.id]
        links.append(RefragLink(
            derived_id(record.number, "refrag", *ids), record.number,
            death.id, response.id, response.tick - death.tick, end - death.tick,
            ids, Status.OBSERVED if source_status == Status.OBSERVED and roster_complete
            else Status.PARTIAL,
        ))
    record.refrag_links = links
    record.refrags_status = (
        Status.OBSERVED if links and source_status == Status.OBSERVED and roster_complete else
        Status.PARTIAL if links or source_status == Status.PARTIAL or not roster_complete else
        Status.ABSENT if source_status in {Status.OBSERVED, Status.ABSENT} else
        Status.UNKNOWN
    )

    opening = [evidence[eid] for eid in record.opening_kill_ids if eid in evidence]
    if not opening:
        record.opening_response_status = (
            Status.ABSENT if record.opening_status == Status.ABSENT else Status.UNKNOWN
        )
        return
    first_tick = min(event.tick for event in opening)
    end = min(record.end_tick, first_tick + window_ticks)
    record.opening_window_end_tick = end
    record.opening_window_kill_ids = [event.id for event in kills if first_tick < event.tick <= end]
    record.opening_response_status = (
        Status.OBSERVED if source_status == Status.OBSERVED and roster_complete else
        Status.PARTIAL if source_status == Status.PARTIAL or not roster_complete else
        Status.UNKNOWN
    )
