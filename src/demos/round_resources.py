"""Shared sampled resources, with observation age and coverage provenance."""

from dataclasses import asdict

from src.demos.coach_foundations import equipment_at
from src.models.tactical import Status


class RoundResources:
    def __init__(self, record, evidence, index, *, tick_rate, config):
        self.record, self.evidence, self.index = record, evidence, index
        self.max_age = round(config.max_sample_age_seconds * tick_rate)
        self.max_gap = round(config.max_sample_gap_seconds * tick_rate)
        self.cache = {}

    def at(self, tick):
        if tick in self.cache:
            return self.cache[tick]
        record = self.record
        players, refs = {}, []
        for player in record.players:
            lookup = self.index.latest(
                tick,
                player_id=player.player_id,
                max_age_ticks=self.max_age,
                max_gap_ticks=self.max_gap,
            )
            row = lookup.row
            item = {
                "side": player.side,
                "sample_tick": lookup.sample_tick,
                "sample_status": lookup.status,
                "hp": None,
                "alive": None,
                "equipment": None,
                "equipment_age_upper_bound_ticks": None,
                "bomb_carrier": None,
            }
            if row:
                item.update(hp=row.get("health"), alive=row.get("is_alive"))
                refs.append(str(row["event_id"]))
                inventory = row.get("inventory")
                if isinstance(inventory, list):
                    item["bomb_carrier"] = any(
                        str(weapon).removeprefix("weapon_").lower() == "c4" for weapon in inventory
                    )
            state = (
                equipment_at(record.foundation, player.player_id, tick, max_age_ticks=self.max_age)
                if record.foundation
                else None
            )
            if state:
                item["equipment"] = asdict(state["observation"])
                item["equipment_age_upper_bound_ticks"] = state["sample_age_upper_bound_ticks"]
                refs.extend(state["observation"].evidence_ids)
            players[player.player_id] = item
        complete_kills = record.availability.get("kills")
        alive = next((state for state in reversed(record.alive_states) if state.tick <= tick), None)
        counts = None
        if (
            alive
            and complete_kills
            and complete_kills.status in {Status.OBSERVED, Status.ABSENT}
            and alive.status == Status.OBSERVED
        ):
            counts = {"T": alive.t_alive, "CT": alive.ct_alive}
            refs.extend(alive.evidence_ids)
        bombs = [
            self.evidence[eid] for eid in record.bomb_event_ids if self.evidence[eid].tick <= tick
        ]
        # Same-tick observations are not ordered across sources.
        latest_bombs = (
            [event for event in bombs if event.tick == max(e.tick for e in bombs)] if bombs else []
        )
        bomb = [
            {
                "event": event.data.get("event"),
                "tick": event.tick,
                "site": event.data.get("site"),
                "evidence_id": event.id,
            }
            for event in latest_bombs
        ]
        refs.extend(event.id for event in latest_bombs)
        value = {
            "tick": tick,
            "players": players,
            "global_alive": counts,
            "bomb_observations": bomb,
            "evidence_ids": sorted(set(refs)),
        }
        self.cache[tick] = value
        return value
