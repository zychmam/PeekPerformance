"""Compact projection of accepted M4 actions; no map names or new detectors."""

from dataclasses import asdict

from src.demos.bomb_coverage import event_known

def action_facts(record, evidence, profile, seconds):
    regions = profile.regions_by_id if profile else {}
    utilities = {u.id: asdict(u) for u in record.utility_contexts}
    attacks = []
    for attack in record.attacks:
        item = asdict(attack)
        episode = item.pop("episode")
        item.update(episode)
        item["seconds"] = seconds(episode["start_tick"])
        item["duration_seconds"] = (
            seconds(episode["end_tick"]) - item["seconds"] if item["seconds"] is not None else None
        )
        item["utility"] = [utilities[uid] for uid in attack.utility_context_ids if uid in utilities]
        item["approaches"] = sorted(
            {
                stay.area
                for stay in record.region_stays
                if stay.player_id in attack.episode.participants
                and stay.start_tick <= attack.episode.end_tick
                and stay.end_tick >= attack.episode.start_tick
                and stay.area in regions
                and regions[stay.area].kind == "approach"
            }
        )
        attacks.append(item)
    activity = []
    for episode in record.ct_activity:
        item = asdict(episode)
        item["seconds"] = seconds(episode.start_tick)
        item["duration_seconds"] = (
            seconds(episode.end_tick) - item["seconds"] if item["seconds"] is not None else None
        )
        item["utility"] = [utilities[uid] for uid in episode.related_ids if uid in utilities]
        item["contact_ids"] = [c.id for c in record.contacts if c.id in episode.related_ids]
        for utility in item["utility"]:
            utility["attack_relations"] = [
                {
                    "attack_id": a.episode.id,
                    "site": a.target_site,
                    "phase": "before" if utility["throw_tick"] < a.episode.start_tick else "during",
                    "offset_seconds": seconds(utility["throw_tick"])
                    - seconds(a.episode.start_tick),
                }
                for a in record.attacks
                if utility["throw_tick"] is not None
                and seconds(utility["throw_tick"]) is not None
                and seconds(utility["throw_tick"]) >= seconds(a.episode.start_tick) - 8
                and utility["throw_tick"] <= a.episode.end_tick
            ]
        activity.append(item)
    rotations = []
    for rotation in record.rotations:
        item = asdict(rotation)
        episode = item.pop("episode")
        item.update(episode)
        item["seconds"] = seconds(episode["start_tick"])
        rotations.append(item)
    retake = asdict(record.retake)
    if retake["episode"]:
        retake["episode"]["seconds"] = seconds(retake["episode"]["start_tick"])
    # Actual later presence after a forward interval; do not infer its purpose.
    for item in activity:
        pid = item["participants"][0]
        later = next(
            (
                s
                for s in record.region_stays
                if s.player_id == pid and s.start_tick > item["end_tick"] and s.area is not None
            ),
            None,
        )
        item["next_area"] = later.area if later else None
    sites = {r.site_id for r in regions.values() if r.kind == "site"}
    plants = []
    for eid in record.bomb_event_ids:
        event = evidence[eid]
        if event.data.get("event") != "bomb_planted":
            continue
        site = next((a.target_site for a in record.attacks if a.plant_id == eid), None)
        if site is None and record.retake.plant_id == eid and record.retake.episode:
            site = record.retake.episode.area
        if site is None and event.data.get("site") in sites:
            site = event.data["site"]
        plants.append(
            {
                "id": eid,
                "site": site,
                "tick": event.tick,
                "seconds": seconds(event.tick),
                "player_id": str(event.data.get("user_steamid")),
                "evidence_ids": [eid],
            }
        )
    return {
        "attacks_status": str(record.attacks_status),
        "attacks_complete": bool(
            profile
            and record.attacks_status in {"observed", "verified_absent"}
            and record.movement_status == "observed"
            and record.contacts_status in {"observed", "verified_absent"}
            and record.utility_context_status in {"observed", "verified_absent"}
            and event_known(record, "bomb_planted")
        ),
        "utility_context_status": str(record.utility_context_status),
        "attacks": attacks,
        "movement_status": str(record.movement_status),
        "ct_activity": activity,
        "rotation_eligibility": record.rotation_eligibility,
        "rotations_status": str(record.rotations_status),
        "rotations": rotations,
        "retake": retake,
        "plants": plants,
        "bombs_known": event_known(record, "bomb_planted"),
    }
