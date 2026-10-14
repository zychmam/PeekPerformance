"""M5.3–5: aggregate observed attempts, defense opportunities and consecutive rounds."""

from collections import defaultdict
from statistics import median

KNOWN = {"observed", "verified_absent"}


def _example(fact, item, **extra):
    tick = item.get("start_tick", item.get("trigger_tick", item.get("tick")))
    seconds = item.get("seconds")
    if seconds is None and tick is not None and fact.get("freeze_tick") is not None:
        rate = fact.get("tick_rate")
        if rate is not None and rate > 0:
            seconds = (tick - fact["freeze_tick"]) / rate
    return {
        "round": fact["number"],
        "tick": tick,
        "seconds": seconds,
        "evidence_ids": item.get("evidence_ids", []),
        **extra,
    }


def _median(items):
    values = [x for x in items if x is not None]
    return median(values) if values else None


def start_band(seconds):
    # Explicit descriptive windows, never rush/execute classifications.
    return (
        "unknown"
        if seconds is None
        else "0–20 s"
        if seconds <= 20
        else "20–45 s"
        if seconds <= 45
        else ">45 s"
    )


def _outcome(items, field, positive, *, rounds=False):
    known = [x for x in items if x[field] not in {None, "unknown"}]
    if rounds:
        denominator = len({x["round"] for x in known})
        count = len({x["round"] for x in known if x[field] == positive})
    else:
        denominator = len(known)
        count = sum(x[field] == positive for x in known)
    unknown = len({x["round"] for x in items}) - denominator if rounds else len(items) - len(known)
    return {"count": count, "denominator": denominator, "unknown": unknown}


def aggregate_actions(selected, *, side, player_id=None):
    attempts, activity, rotations, opportunities, retakes, utility, detached = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    plants = []
    attack_coverage, movement_coverage = [], []
    for fact in selected:
        if side == "T":
            plants.extend({**p, "round": fact["number"]} for p in fact.get("plants", []))
        if fact.get("attacks_complete", fact.get("attacks_status") in KNOWN):
            attack_coverage.append(fact["number"])
        if fact.get("movement_status") == "observed":
            movement_coverage.append(fact["number"])
        for attack in fact.get("attacks", []) if side == "T" else []:
            # Player scope describes involvement; results are still team outcomes.
            if player_id and player_id not in set(
                attack["participants"] + attack["detached_players"]
            ):
                continue
            item = {**attack, **_example(fact, attack)}
            item["start_band"] = start_band(attack["seconds"])
            item["round_outcome"] = fact["winner_side"]
            item["utility_known"] = fact.get("utility_context_status") in KNOWN
            attempts.append(item)
            for u in attack["utility"]:
                if player_id and u["player_id"] != player_id:
                    continue
                utility.append(
                    {
                        **_example(fact, attack),
                        "attack_id": attack["id"],
                        "site": attack["target_site"],
                        "start_band": item["start_band"],
                        "kind": u["kind"],
                        "origin_area": u["origin_area"],
                        "effect_area": u["effect_area"],
                        "match_status": u["match_status"],
                        "phase": "before" if u["throw_tick"] < attack["start_tick"] else "during",
                        "player_id": u["player_id"],
                        "evidence_ids": u["evidence_ids"],
                        "tick": u["throw_tick"],
                        "seconds": (u["throw_tick"] - fact["freeze_tick"]) / fact["tick_rate"]
                        if fact.get("freeze_tick") is not None
                        else None,
                    }
                )
            for action in attack["detached_actions"]:
                if player_id and action["player_id"] != player_id:
                    continue
                detached.append(
                    {
                        **_example(fact, {"start_tick": action["intervals"][0]["start_tick"]}),
                        **action,
                        "attack_id": attack["id"],
                        "site": attack["target_site"],
                        "evidence_ids": sorted(
                            {ref for i in action["intervals"] for ref in i["evidence_ids"]}
                        ),
                    }
                )
        if side != "CT":
            continue
        for episode in fact.get("ct_activity", []):
            if player_id and player_id not in episode["participants"]:
                continue
            activity.append({**episode, **_example(fact, episode)})
            for u in episode["utility"]:
                utility.append(
                    {
                        **_example(fact, {"start_tick": u["throw_tick"]}),
                        **u,
                        "activity": episode["kind"],
                        "activity_id": episode["id"],
                    }
                )
        for opportunity in fact.get("rotation_eligibility", []):
            if player_id and opportunity["player_id"] != player_id:
                continue
            opportunities.append({**_example(fact, opportunity), **opportunity})
        for rotation in fact.get("rotations", []):
            if player_id and rotation["player_id"] != player_id:
                continue
            rotations.append({**rotation, **_example(fact, rotation)})
        retake = fact.get("retake", {"status": "unknown"})
        retakes.append(
            {
                **retake,
                **_example(fact, retake.get("episode") or {}),
                "participants": (retake.get("episode") or {}).get("participants", []),
            }
        )
    groups = defaultdict(list)
    for item in attempts:
        signature = (
            item["target_site"],
            item["start_band"],
            tuple(item["approaches"]),
            tuple(sorted({u["kind"] for u in item["utility"]}))
            if item["utility_known"]
            else ("unknown",),
        )
        groups[signature].append(item)
    executions = []
    for signature, items in sorted(groups.items(), key=lambda pair: (-len(pair[1]), str(pair[0]))):
        executions.append(
            {
                "site": signature[0],
                "start_band": signature[1],
                "approaches": list(signature[2]),
                "utility_kinds": list(signature[3]),
                "attempts": len(items),
                "rounds": sorted({x["round"] for x in items}),
                "denominator": len(attempts),
                "start_median": _median(x["seconds"] for x in items),
                "duration_median": _median(x["duration_seconds"] for x in items),
                "entry_spread_median": _median(x["entry_spread_seconds"] for x in items),
                "entry": _outcome(items, "entry_outcome", "observed_presence"),
                "plant": _outcome(items, "plant_outcome", "planted"),
                "wins": _outcome(items, "round_outcome", "T", rounds=True),
                "examples": items,
            }
        )
    sites = []
    for site in sorted({a["target_site"] for a in attempts}, key=str):
        items = [a for a in attempts if a["target_site"] == site]
        sites.append(
            {
                "site": site,
                "count": len(items),
                "denominator": len(attempts),
                "rounds": sorted({a["round"] for a in items}),
                "entry": _outcome(items, "entry_outcome", "observed_presence"),
                "plant": _outcome(items, "plant_outcome", "planted"),
                "wins": _outcome(items, "round_outcome", "T", rounds=True),
                "examples": items,
            }
        )
    return {
        "plants": plants,
        "bombs_known_rounds": [f["number"] for f in selected if f.get("bombs_known")],
        "attempts": attempts,
        "executions": executions,
        "sites": sites,
        "attack_coverage": {
            "eligible": len(selected),
            "known_rounds": attack_coverage,
            "unknown_rounds": [f["number"] for f in selected if f["number"] not in attack_coverage],
        },
        "movement_coverage": {
            "eligible": len(selected),
            "known_rounds": movement_coverage,
            "unknown_rounds": [
                f["number"] for f in selected if f["number"] not in movement_coverage
            ],
        },
        "utility": utility,
        "detached": detached,
        "activity": activity,
        "utility_known_rounds": [
            f["number"] for f in selected if f.get("utility_context_status") in KNOWN
        ],
        "opportunities": opportunities,
        "rotations": rotations,
        "retakes": retakes,
        "rotation_summary": {
            "eligible": sum(o["status"] == "eligible" for o in opportunities),
            "unknown": sum(o["status"] == "unknown" for o in opportunities),
            "arrived": sum(r["outcome"] == "arrived" for r in rotations),
            "reaction_median": _median(
                r["reaction_seconds"] for r in rotations if r["outcome"] == "arrived"
            ),
            "reaction_known": sum(
                r["outcome"] == "arrived" and r["reaction_seconds"] is not None for r in rotations
            ),
            "travel_median": _median(
                r["travel_seconds"] for r in rotations if r["outcome"] == "arrived"
            ),
            "travel_known": sum(
                r["outcome"] == "arrived" and r["travel_seconds"] is not None for r in rotations
            ),
        },
    }


def _signatures(fact, side):
    data = fact["sides"][side]
    snap = next((s for s in data["snapshots"].values() if s["seconds"] == 10), None)
    setup = fact.get("ct_sectors")
    attacks = fact.get("attacks", [])
    attacks_known = fact.get("attacks_complete", fact.get("attacks_status") in KNOWN)
    freeze, rate, end = fact.get("freeze_tick"), fact.get("tick_rate"), fact.get("end_tick")
    if freeze is None or rate is None or rate <= 0 or end is not None and freeze + 10 * rate > end:
        snap = None
    first_tick = min((a["start_tick"] for a in attacks), default=None)
    first = [a for a in attacks if a["start_tick"] == first_tick]
    # Tied attempts are a set, not an arbitrary ordered decision.
    return {
        "direction_10s": snap["dominant_direction"] if snap and snap["complete"] else None,
        "first_target": tuple(sorted({a["target_site"] for a in first}))
        if attacks_known and all(a["target_site"] is not None for a in first)
        else None,
        "first_tempo": tuple(sorted({start_band(a["seconds"]) for a in first}))
        if attacks_known and all(a["seconds"] is not None for a in first)
        else None,
        "early_utility": tuple(
            sorted(
                (u["kind"], u["origin_area"] or "unknown", u["effect_area"] or "unknown")
                for u in data["early_throws"]
            )
        )
        if data["early_throws_known"]
        and all(
            u["origin_area"] is not None and u["effect_area"] is not None
            for u in data["early_throws"]
        )
        else None,
        "ct_setup": tuple(sorted(setup["counts"].items()))
        if setup and setup.get("unknown") == 0 and setup.get("status") == "observed"
        else None,
    }


def aggregate_sequence(selected, side):
    by_number = {f["number"]: f for f in selected}
    pairs = []
    dimensions = (
        ("direction_10s", "first_target", "first_tempo", "early_utility")
        if side == "T"
        else ("ct_setup", "early_utility")
    )
    for current in selected:
        previous = by_number.get(current["comparison"]["previous_round"])
        if previous is None:
            continue
        before, after = _signatures(previous, side), _signatures(current, side)
        transitions = {
            d: "unknown"
            if before[d] is None or after[d] is None
            else "repeated"
            if before[d] == after[d]
            else "changed"
            for d in dimensions
        }
        own = current["sides"][side]["equipment"]["economy"]["current_equip_value"]["total"]
        old = previous["sides"][side]["equipment"]["economy"]["current_equip_value"]["total"]
        opponent_side = "CT" if side == "T" else "T"
        opponent = current["sides"][opponent_side]["equipment"]["economy"]["current_equip_value"][
            "total"
        ]
        old_opponent = previous["sides"][opponent_side]["equipment"]["economy"][
            "current_equip_value"
        ]["total"]
        refs = sorted(
            {
                ref
                for f in (previous, current)
                for s in f["sides"][side]["snapshots"].values()
                for ref in s["evidence_ids"]
            }
            | {
                ref
                for f in (previous, current)
                for u in f["sides"][side]["early_throws"]
                for ref in u["evidence_ids"]
            }
            | {
                ref
                for f in (previous, current)
                for a in f.get("attacks", [])
                for ref in a["evidence_ids"]
            }
        )
        pairs.append(
            {
                "previous_round": previous["number"],
                "round": current["number"],
                "previous_result": current["comparison"]["previous_result"][side],
                "transitions": transitions,
                "before": before,
                "after": after,
                "equipment_delta": own - old if own is not None and old is not None else None,
                "opponent_equipment_delta": opponent - old_opponent
                if opponent is not None and old_opponent is not None
                else None,
                "evidence_ids": refs,
                "tick": current["freeze_tick"],
                "seconds": 0.0,
            }
        )
    summaries = []
    for result in ("win", "loss"):
        items = [p for p in pairs if p["previous_result"] == result]
        for dimension in dimensions:
            known = [p for p in items if p["transitions"][dimension] != "unknown"]
            summaries.append(
                {
                    "previous_result": result,
                    "dimension": dimension,
                    "repeated": sum(p["transitions"][dimension] == "repeated" for p in known),
                    "changed": sum(p["transitions"][dimension] == "changed" for p in known),
                    "denominator": len(known),
                    "unknown": len(items) - len(known),
                    "examples": known,
                }
            )
    return {
        "pairs": pairs,
        "summaries": summaries,
        "excluded_rounds": [
            f["number"] for f in selected if f["number"] not in {p["round"] for p in pairs}
        ],
    }
