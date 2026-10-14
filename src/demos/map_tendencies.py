"""M5.1–2 aggregates with explicit units, opportunities and round references."""

from collections import defaultdict
from statistics import median

from src.demos.map_action_tendencies import aggregate_actions, aggregate_sequence
from src.demos.map_round_facts import comparable_rounds

TENDENCIES_VERSION = 2


def _buckets(observations, unit):
    groups = defaultdict(list)
    for item in observations:
        groups[item["key"]].append(item)
    denominator = len(observations)
    return [
        {
            "key": key,
            "count": len(items),
            "denominator": denominator,
            "unit": unit,
            "percentage": 100 * len(items) / denominator if denominator else None,
            "rounds": sorted({item["round"] for item in items}),
            "median_seconds": median(
                [item["seconds"] for item in items if item.get("seconds") is not None]
            )
            if any(item.get("seconds") is not None for item in items)
            else None,
            "examples": items,
        }
        for key, items in sorted(groups.items(), key=lambda pair: (-len(pair[1]), str(pair[0])))
    ]


def aggregate_tendencies(
    facts,
    *,
    team_id,
    side,
    player_id=None,
    snapshot_seconds=10,
    round_numbers=None,
    equipment_min=None,
    equipment_max=None,
    require_equipment=False,
    require_starting_five=False,
):
    if side not in {"T", "CT"} or team_id is None:
        raise ValueError("Stable team and side required")
    selected, omitted, unknown_team = [], [], []
    for fact in comparable_rounds(facts):
        data = fact["sides"][side]
        if data["team_id"] is None:
            unknown_team.append(fact["number"])
            continue
        if data["team_id"] != team_id or player_id and player_id not in data["roster"]:
            continue
        if round_numbers is not None and fact["number"] not in round_numbers:
            continue
        if require_starting_five and any(
            data.get("start_alive") != 5 for data in fact["sides"].values()
        ):
            omitted.append({"round": fact["number"], "reason": "starting_alive"})
            continue
        value = data["equipment"]["economy"]["current_equip_value"]["total"]
        if fact["metadata"].get("is_warmup_period") is True:
            omitted.append({"round": fact["number"], "reason": "warmup"})
            continue
        filtered_value = equipment_min is not None or equipment_max is not None or require_equipment
        opponent = fact["sides"]["CT" if side == "T" else "T"]["equipment"]["economy"][
            "current_equip_value"
        ]["total"]
        if (
            value is None
            and filtered_value
            or require_equipment
            and opponent is None
            or value is not None
            and equipment_min is not None
            and value < equipment_min
            or value is not None
            and equipment_max is not None
            and value > equipment_max
        ):
            omitted.append({"round": fact["number"], "reason": "equipment"})
            continue
        selected.append(fact)
    observations = {
        name: []
        for name in (
            "directions",
            "positions",
            "ct_setups",
            "contacts",
            "opening",
            "utility",
            "entries",
        )
    }
    coverage = {
        name: {
            "eligible": len(selected),
            "known": 0,
            "unknown_rounds": [],
            "not_applicable_rounds": [],
        }
        for name in (
            "directions",
            "snapshots",
            "ct_setups",
            "contacts",
            "opening",
            "utility",
            "refrags",
            "advantage",
        )
    }
    refrag_rounds, advantage_rounds, conversion_rounds = [], [], []
    refrag_events, advantage_examples = [], []

    def observe(name, fact, key, refs, tick=None, seconds=None, **extra):
        observations[name].append(
            {
                "key": key,
                "round": fact["number"],
                "tick": tick,
                "seconds": seconds,
                "evidence_ids": sorted(set(refs)),
                **extra,
            }
        )

    def known(name, fact, valid):
        if valid:
            coverage[name]["known"] += 1
        else:
            coverage[name]["unknown_rounds"].append(fact["number"])

    for fact in selected:
        data = fact["sides"][side]
        freeze, end, rate = fact.get("freeze_tick"), fact.get("end_tick"), fact.get("tick_rate")
        snapshot_applicable = not (
            freeze is not None
            and end is not None
            and rate is not None
            and rate > 0
            and freeze + snapshot_seconds * rate > end
        )
        snap = next(
            (s for s in data["snapshots"].values() if s["seconds"] == snapshot_seconds), None
        )
        if freeze is None or rate is None or rate <= 0:
            snap = None
        if not snapshot_applicable:
            snap = None
            for name in ("snapshots", "directions"):
                coverage[name]["eligible"] -= 1
                coverage[name]["not_applicable_rounds"].append(fact["number"])
        else:
            known("snapshots", fact, bool(snap and snap["complete"]))
        direction = snap["dominant_direction"] if snap else None
        if snapshot_applicable:
            known("directions", fact, direction is not None)
        if direction is not None:
            observe(
                "directions", fact, direction, snap["evidence_ids"], snap["tick"], snap["seconds"]
            )
        if snap:
            for player in snap["positions"]:
                if player_id and player["player_id"] != player_id:
                    continue
                key = (
                    player["area"]
                    if player["alive"] and player["area"]
                    else ("__dead__" if player["alive"] is False else "__unknown__")
                )
                observe(
                    "positions",
                    fact,
                    key,
                    snap["evidence_ids"],
                    snap["tick"],
                    snap["seconds"],
                    player_id=player["player_id"],
                )
        elif snapshot_applicable:
            for pid in data["roster"]:
                if not player_id or pid == player_id:
                    observe("positions", fact, "__unknown__", [], player_id=pid)
        setup = fact["ct_sectors"]
        valid_setup = (
            side == "CT"
            and setup
            and setup.get("unknown") == 0
            and setup.get("status") == "observed"
        )
        known("ct_setups", fact, bool(valid_setup))
        if valid_setup:
            key = " | ".join(
                f"{sector}:{count}" for sector, count in sorted(setup["counts"].items())
            )
            secs = (
                (setup["tick"] - fact["freeze_tick"]) / fact["tick_rate"]
                if fact["freeze_tick"] is not None
                else None
            )
            observe("ct_setups", fact, key, setup["evidence_ids"], setup["tick"], secs)
        known("contacts", fact, data["contacts_known"])
        contacts = (
            data.get("player_first_firearm_contacts", [])
            if player_id
            else data["first_firearm_contacts"]
        )
        for item in contacts:
            if player_id and item["player_id"] != player_id:
                continue
            observe(
                "contacts",
                fact,
                item["area"] or "__unknown__",
                item["evidence_ids"],
                item["tick"],
                item["seconds"],
                player_id=item["player_id"],
                source_status=data.get(
                    "contacts_status", "observed" if data["contacts_known"] else "partial"
                ),
            )
        known("opening", fact, data["opening_known"])
        for item in data["opening"] if data["opening_known"] else []:
            if player_id and item["player_id"] != player_id:
                continue
            observe(
                "opening",
                fact,
                (item["role"], item["area"] or "__unknown__"),
                item["evidence_ids"],
                item["tick"],
                item["seconds"],
                player_id=item["player_id"],
            )
        known("utility", fact, data["early_throws_known"])
        for item in data["early_throws"]:
            if player_id and item["player_id"] != player_id:
                continue
            observe(
                "utility",
                fact,
                (
                    item["kind"],
                    item["origin_area"] or "__unknown__",
                    item["effect_area"] or "__unknown__",
                ),
                item["evidence_ids"],
                item["tick"],
                item["seconds"],
                player_id=item["player_id"],
                from_spawn=item["origin_kind"] == "spawn",
                match_status=item["match_status"],
            )
        for entry in fact["entries"] if side == "T" else []:
            if player_id and player_id not in entry["players"]:
                continue
            observe(
                "entries",
                fact,
                entry["site"] or "__unknown__",
                entry["evidence_ids"],
                entry["tick"],
                entry["seconds"],
            )
        known("refrags", fact, data["refrags_known"])
        own_refrags = [
            item for item in data["refrags"] if not player_id or item["player_id"] == player_id
        ]
        refrag_events.extend({**item, "round": fact["number"]} for item in own_refrags)
        if data["refrags_known"] and own_refrags:
            refrag_rounds.append(fact["number"])
        advantage = data["had_advantage"]
        known("advantage", fact, advantage is not None)
        if advantage:
            advantage_rounds.append(fact["number"])
            tick = data.get("first_advantage_tick")
            advantage_examples.append(
                {
                    "round": fact["number"],
                    "tick": tick,
                    "seconds": (tick - fact["freeze_tick"]) / fact["tick_rate"]
                    if tick is not None and fact["freeze_tick"] is not None
                    else None,
                    "evidence_ids": data.get("advantage_evidence_ids", []),
                }
            )
            if fact["winner_team_id"] == team_id:
                conversion_rounds.append(fact["number"])
    return {
        "version": TENDENCIES_VERSION,
        "actions": aggregate_actions(selected, side=side, player_id=player_id),
        "sequence": aggregate_sequence(selected, side),
        "team_id": team_id,
        "side": side,
        "player_id": player_id,
        "snapshot_seconds": snapshot_seconds,
        "rounds": [f["number"] for f in selected],
        "omitted": omitted,
        "unknown_team_rounds": unknown_team,
        "coverage": coverage,
        "tables": {
            name: _buckets(
                items,
                "player_snapshots"
                if name == "positions"
                else "rounds"
                if name in {"directions", "ct_setups"}
                else "observed_events",
            )
            for name, items in observations.items()
        },
        "refrags": {
            "rounds_with": refrag_rounds,
            "known_rounds": coverage["refrags"]["known"],
            "events": refrag_events,
            "trade_kills": len({(e["round"], e["response_kill_id"]) for e in refrag_events}),
            "traded_deaths": len({(e["round"], e["initial_death_id"]) for e in refrag_events}),
            "kills": _unique_replies(refrag_events),
        },
        "advantage": {
            "examples": advantage_examples,
            "rounds_with": advantage_rounds,
            "wins": conversion_rounds,
            "known_result_rounds": [
                f["number"]
                for f in selected
                if f["number"] in advantage_rounds and f["winner_team_id"] is not None
            ],
        },
        "equipment": [
            {
                "round": f["number"],
                "own": f["sides"][side]["equipment"],
                "opponent": f["sides"]["CT" if side == "T" else "T"]["equipment"],
                "previous_result": f["comparison"]["previous_result"][side],
                "previous_survivors": f["comparison"]["previous_survivors"][side],
                "segment": f["comparison"]["segment"],
            }
            for f in selected
        ],
        "early_seconds": sorted({f["early_seconds"] for f in selected}),
        "reset_coverage": "limited"
        if any(f["comparison"]["reset_coverage"] == "limited" for f in selected)
        else "explicit",
    }


def _unique_replies(events):
    replies = {}
    for event in events:
        key = (event["round"], event["response_kill_id"])
        item = replies.setdefault(key, {**event, "evidence_ids": [], "traded_player_ids": []})
        item["evidence_ids"] = sorted(set(item["evidence_ids"] + event["evidence_ids"]))
        item["traded_player_ids"] = sorted(
            set(item["traded_player_ids"] + [event["traded_player_id"]])
        )
    return list(replies.values())
