"""Print compact, read-only source facts for M3 reference round review.

Usage: python scripts/m3_reference_audit.py [sqlite_path]
"""

import json
import sqlite3
import sys
from pathlib import Path


ROUNDS = {"de_mirage": (1, 6, 13, 20), "de_inferno": (1, 3, 10, 20)}


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".peek_performance" / "peekperformance.db"
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    for map_name, numbers in ROUNDS.items():
        row = connection.execute(
            "SELECT * FROM demo_analyses WHERE map_name=? ORDER BY analyzed_at DESC LIMIT 1",
            (map_name,),
        ).fetchone()
        if row is None:
            continue
        data = {name: json.loads(row[name]) for name in ("rounds", "kills", "damage", "bomb_events", "round_roster")}
        manifest = connection.execute(
            "SELECT cache_key FROM coach_stage_manifests WHERE demo_id=? AND stage='observations'",
            (row["demo_id"],),
        ).fetchone()
        spatial_manifest = connection.execute(
            "SELECT cache_key FROM coach_stage_manifests WHERE demo_id=? AND stage='spatial'",
            (row["demo_id"],),
        ).fetchone()
        for number in numbers:
            rnd = next(r for r in data["rounds"] if r["total_rounds_played"] == number)
            roster = {str(p["steamid"]): p["name"] for p in data["round_roster"] if p["total_rounds_played"] == number}
            def name(value):
                return roster.get(str(value), "unknown")
            kills = [
                {"tick": e["tick"], "attacker": name(e.get("attacker_steamid")),
                 "victim": name(e.get("user_steamid")), "weapon": e.get("weapon"),
                 "attacker_place": e.get("attacker_last_place_name"),
                 "victim_place": e.get("user_last_place_name")}
                for e in data["kills"] if e["total_rounds_played"] == number
            ]
            damage = [
                {"tick": e["tick"], "attacker": name(e.get("attacker_steamid")),
                 "victim": name(e.get("user_steamid")), "weapon": e.get("weapon"),
                 "hp": e.get("enemy_damage")}
                for e in data["damage"]
                if e["total_rounds_played"] == number and (e.get("enemy_damage") or 0) > 0
            ]
            bombs = [
                {"tick": e["tick"], "event": e["event"], "site": e.get("site")}
                for e in data["bomb_events"] if e["total_rounds_played"] == number
            ]
            sources = {}
            non_observed_locations = None
            payload = {}
            source_row = None
            if manifest:
                source_row = connection.execute(
                    "SELECT payload FROM coach_stage_rounds WHERE demo_id=? AND stage='observations' "
                    "AND cache_key=? AND round_number=?",
                    (row["demo_id"], manifest["cache_key"], number),
                ).fetchone()
                if source_row:
                    payload = json.loads(source_row["payload"])
                    sources = {key: len(value) for key, value in payload.items() if isinstance(value, list)}
            if spatial_manifest:
                spatial_row = connection.execute(
                    "SELECT payload FROM coach_stage_rounds WHERE demo_id=? AND stage='spatial' "
                    "AND cache_key=? AND round_number=?",
                    (row["demo_id"], spatial_manifest["cache_key"], number),
                ).fetchone()
                if spatial_row:
                    locations = json.loads(spatial_row["payload"])["locations"]["location_status"]
                    non_observed_locations = sum(status != "observed" for status in locations)
            print(json.dumps({
                "map": map_name, "round": number, "freeze_tick": next(
                    (e["freeze_tick"] for e in payload.get("clock", []) if e.get("total_rounds_played") == number),
                    None,
                ) if manifest and source_row else None,
                "end_tick": rnd["tick"], "winner": rnd["winner"], "reason": rnd["reason"],
                "damage_first": damage[:3], "kills": kills, "bombs": bombs,
                "source_counts": sources, "non_observed_locations": non_observed_locations,
            }, ensure_ascii=False))


if __name__ == "__main__":
    main()
