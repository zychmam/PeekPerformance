"""Read-only V2D source audit; no application/cache changes or renderer assumptions."""

import argparse
import json
import math
import sqlite3
import sys
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from demoparser2 import DemoParser

from src.config import Config
from src.storage.database import Database

PROPS = ["flash_duration", "flash_max_alpha", "health", "is_alive", "life_state", "game_time"]
UNAVAILABLE_PROBES = [
    "CCSPlayerPawn.m_flFlashBangTime",
    "CCSPlayerPawn.m_flFlashOverlayAlpha",
]
PARSER_SOURCE = {
    "tag": "v0.42.0",
    "commit": "d3767705dc5846d73ed29db50eaeda58778dc934",
    "repository": "https://github.com/LaihoE/demoparser",
}


def records(frame):
    return json.loads(frame.to_json(orient="records", double_precision=10))


def audit_flash(parser, events, clock, rate):
    freezes = clock.set_index("total_rounds_played").freeze_tick.to_dict()
    ends = clock.set_index("total_rounds_played").tick.to_dict()
    active = [
        e
        for e in events
        if math.isfinite(e.get("blind_duration", float("nan")))
        and e["blind_duration"] > 0
        and pd.notna(freezes.get(e["total_rounds_played"]))
        and freezes[e["total_rounds_played"]] <= e["tick"] <= ends[e["total_rounds_played"]]
    ]
    if not active:
        return {"status": "no_positive_active_events", "cases": []}
    observed_fields = parser.list_updated_fields()
    sampled = parser.parse_ticks(PROPS, ticks=sorted({e["tick"] for e in active}))
    available = [p for p in PROPS if p in sampled]
    if set(available) != set(PROPS):
        raise ValueError(f"Audit needs fields: {set(PROPS) - set(available)}")
    by_key = {(int(r["tick"]), str(r["steamid"])): r for r in records(sampled)}
    live, dead, missing, differences = [], [], [], []
    for e in active:
        state = by_key.get((e["tick"], str(e["user_steamid"])))
        if state is None:
            missing.append(e)
            continue
        differences.append(abs(e["blind_duration"] - state["flash_duration"]))
        (live if state["is_alive"] and state["health"] > 0 else dead).append(e)
    selected = []
    if live:
        selected.extend(
            [
                ("strongest_live", max(live, key=lambda e: e["blind_duration"])),
                ("shortest_live", min(live, key=lambda e: e["blind_duration"])),
            ]
        )
    self_events = [e for e in live if str(e["user_steamid"]) == str(e["attacker_steamid"])]
    if self_events:
        selected.append(("self_flash", max(self_events, key=lambda e: e["blind_duration"])))
    overlap = []
    last = {}
    for e in sorted(live, key=lambda e: e["tick"]):
        key = (e["total_rounds_played"], str(e["user_steamid"]))
        previous = last.get(key)
        if previous and e["tick"] < previous["tick"] + previous["blind_duration"] * rate:
            overlap.append((previous, e))
        last[key] = e
    if overlap:
        selected.extend([("overlap_first", overlap[0][0]), ("overlap_second", overlap[0][1])])
    ticks = set()
    for _, e in selected:
        end = min(
            ends[e["total_rounds_played"]],
            e["tick"] + math.ceil((e["blind_duration"] * 1.5 + 0.5) * rate),
        )
        ticks.update(range(e["tick"] - 2, end + 1))
    users = sorted({int(e["user_steamid"]) for _, e in selected})
    timeline = (
        parser.parse_ticks(PROPS, ticks=sorted(ticks), players=users) if ticks else pd.DataFrame()
    )
    player_ids = {str(sid): f"p{i:02}" for i, sid in enumerate(sorted(sampled.steamid.unique()), 1)}
    cases = []
    for kind, e in selected:
        end_tick = e["tick"] + e["blind_duration"] * rate
        end = min(
            ends[e["total_rounds_played"]],
            e["tick"] + math.ceil((e["blind_duration"] * 1.5 + 0.5) * rate),
        )
        part = timeline[
            timeline.steamid.astype(str).eq(str(e["user_steamid"]))
            & timeline.tick.between(e["tick"] - 2, end)
        ].copy()
        changed = part.flash_duration.ne(part.flash_duration.shift()) | part.is_alive.ne(
            part.is_alive.shift()
        )
        critical = {
            e["tick"] - 1,
            e["tick"],
            e["tick"] + 1,
            math.floor(end_tick),
            math.ceil(end_tick),
            end,
        }
        rows = part[changed | part.tick.isin(critical)].drop(
            columns=["name", "steamid"], errors="ignore"
        )
        after = part[part.tick.gt(end_tick)]
        linked = [
            other
            for other in live
            if other["total_rounds_played"] == e["total_rounds_played"]
            and str(other["user_steamid"]) == str(e["user_steamid"])
            and e["tick"] < other["tick"] <= end
        ]
        initial = part[part.tick.eq(e["tick"])]
        cleared = part[part.tick.gt(e["tick"]) & part.flash_duration.eq(0)]
        cleared_tick = int(cleared.tick.iloc[0]) if len(cleared) else None
        cases.append(
            {
                "kind": kind,
                "round": e["total_rounds_played"],
                "player_id": player_ids[str(e["user_steamid"])],
                "tick": e["tick"],
                "seconds_after_freeze": (e["tick"] - freezes[e["total_rounds_played"]]) / rate,
                "event_duration_seconds": e["blind_duration"],
                "event_window_end_tick": end_tick,
                "initial_network_duration": float(initial.flash_duration.iloc[0])
                if len(initial)
                else None,
                "duration_nonzero_after_event_window": bool(after.flash_duration.gt(0).any()),
                "next_flash_ticks_in_sample": [other["tick"] for other in linked],
                "first_network_zero_tick": cleared_tick,
                "network_zero_elapsed_ratio": (cleared_tick - e["tick"])
                / rate
                / e["blind_duration"]
                if cleared_tick and not linked and bool(cleared.is_alive.iloc[0])
                else None,
                "samples": records(rows),
                "full_blind_end_tick": None,
            }
        )
    probes = {}
    for prop in UNAVAILABLE_PROBES:
        try:
            result = parser.parse_ticks([prop], ticks=[active[0]["tick"]])
            probes[prop] = "column_present" if prop in result else "column_absent"
        except Exception as exc:
            probes[prop] = f"error: {type(exc).__name__}"
    return {
        "status": "audited",
        "all_saved_events": len(events),
        "positive_active_events": len(active),
        "live_positive_events": len(live),
        "nonlive_positive_events": len(dead),
        "missing_state_events": len(missing),
        "duration_event_state_max_difference": max(differences, default=None),
        "overlap_pairs": len(overlap),
        "available_columns": available,
        "network_flash_fields": [f for f in observed_fields if "Flash" in f],
        "unsupported_probes": probes,
        "cases": cases,
    }


def audit_projectiles(conn, demo_id, parser, events):
    # Aggregate in SQLite: never deserialize the million-row frame into Python.
    rows = conn.execute(
        """
        SELECT json_extract(j.value,'$.grenade_type') AS kind, count(*) AS rows,
          sum(json_type(j.value,'$.x') IN ('real','integer') AND
              json_type(j.value,'$.y') IN ('real','integer') AND
              json_type(j.value,'$.z') IN ('real','integer')) AS valid_positions,
          count(DISTINCT json_extract(j.value,'$.grenade_entity_id')) AS entity_ids
        FROM demo_analyses a, json_each(a.grenades) j WHERE a.demo_id=? GROUP BY kind
    """,
        (demo_id,),
    ).fetchall()
    started = perf_counter()
    only_projectiles = parser.parse_grenades(grenades=False)
    valid = only_projectiles.dropna(subset=["x", "y", "z"])
    examples = []
    for event in events:
        if len(examples) >= 2:
            break
        part = valid[
            valid.grenade_type.eq("CFlashbangProjectile")
            & valid.grenade_entity_id.eq(event.get("entityid"))
            & valid.steamid.astype(str).eq(str(event.get("attacker_steamid")))
            & valid.tick.between(event["tick"] - 20 * 64, event["tick"])
        ].sort_values("tick")
        if part.empty:
            continue
        examples.append(
            {
                "round": event["total_rounds_played"],
                "blind_tick": event["tick"],
                "projectile_entity": event["entityid"],
                "same_owner_and_entity": True,
                "rows_in_previous_20s": len(part),
                "last_sample_tick": int(part.tick.iloc[-1]),
                "ticks_to_blind": int(event["tick"] - part.tick.iloc[-1]),
                "endpoints": records(part.iloc[[0, -1]][["tick", "x", "y", "z"]]),
            }
        )
    return {
        "types": [dict(row) for row in rows],
        "rows": sum(row["rows"] for row in rows),
        "projectiles_only_parser_rows": len(only_projectiles),
        "projectiles_only_valid_positions": len(valid),
        "projectiles_only_types": sorted(only_projectiles.grenade_type.unique().tolist()),
        "projectiles_only_parse_seconds": round(perf_counter() - started, 2),
        "flash_link_examples": examples,
        "warning": "Entity IDs are not unique projectile lifetimes; null positions are not flight.",
    }


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path, default=Path("docs/v2d_source_audit.json"))
    cli.add_argument("--map", choices=["de_mirage", "de_inferno", "de_dust2", "de_anubis"])
    args = cli.parse_args()
    config = Config.load()
    db = Database(config.db_path)
    output = {
        "audit_version": 1,
        "parser_version": version("demoparser2"),
        "source_reference_for_installed_0_42_0": PARSER_SOURCE,
        "pov_visual_validation": "not_performed",
        "maps": [],
    }
    with sqlite3.connect(config.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT demo_id,map_name,stored_file_name,player_blinds FROM demo_analyses "
            "ORDER BY analyzed_at DESC"
        ).fetchall()
        used = set()
        for row in rows:
            name = row["map_name"]
            if name in used or args.map and name != args.map:
                continue
            manifest = db.get_stage_manifest(row["demo_id"], "observations")
            if manifest is None:
                continue
            clock = db.get_observation_clock(row["demo_id"], manifest["cache_key"])
            if clock.empty:
                continue
            path = Path(config.demos_dir) / row["stored_file_name"]
            if not path.is_file():
                continue
            started = perf_counter()
            parser = DemoParser(str(path))
            rates = clock.tick_rate.unique()
            if len(rates) != 1:
                raise ValueError("Audit expects one explicit clock frequency per match")
            flash = audit_flash(parser, json.loads(row["player_blinds"]), clock, float(rates[0]))
            projectiles = audit_projectiles(
                conn, row["demo_id"], parser, json.loads(row["player_blinds"])
            )
            result = {
                "map": name,
                "demo_file": row["stored_file_name"],
                "tick_rate": float(rates[0]),
                "time_sources": clock.time_source.unique().tolist(),
                "flash": flash,
                "projectiles": projectiles,
                "elapsed_seconds": round(perf_counter() - started, 2),
            }
            output["maps"].append(result)
            used.add(name)
            print(
                f"{name}: {flash.get('live_positive_events')} live flashes; "
                f"{projectiles['rows']} trajectory rows; {result['elapsed_seconds']}s",
                flush=True,
            )
    if not output["maps"]:
        raise RuntimeError("No saved observation clock and original demo available")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
