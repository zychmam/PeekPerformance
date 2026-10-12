"""Inspect local demo sources without changing the application database."""

import argparse
import json
import time
from importlib.metadata import version
from pathlib import Path

from demoparser2 import DemoParser

EVENTS = (
    "round_freeze_end",
    "bomb_planted",
    "bomb_defused",
    "bomb_exploded",
    "bomb_pickup",
    "bomb_dropped",
    "bomb_beginplant",
    "bomb_abortplant",
    "bomb_begindefuse",
    "bomb_abortdefuse",
    "weapon_fire",
    "grenade_thrown",
    "smokegrenade_detonate",
    "smokegrenade_expired",
    "flashbang_detonate",
    "hegrenade_detonate",
    "inferno_startburn",
    "inferno_expire",
)
GROUPS = {
    "inventory": ["inventory"],
    "weapon": ["active_weapon_name"],
    "armor": ["armor_value", "has_helmet"],
    "defuse": ["has_defuser"],
    "economy": [
        "balance",
        "current_equip_value",
        "cash_spent_this_round",
        "start_balance",
        "round_start_equip_value",
    ],
}


def audit(path: Path) -> dict:
    start = time.perf_counter()
    parser = DemoParser(str(path))
    available = set(parser.list_game_events())
    report = {
        "file": path.name,
        "parser_version": version("demoparser2"),
        "notes": [
            "Event counts include warmup and pre-match rounds.",
            "Not listed does not establish parser support or verified absence.",
        ],
        "header": parser.parse_header(),
        "events": {},
        "properties": {},
    }
    requested = [event for event in EVENTS if event in available]
    frames = dict(parser.parse_events(requested))
    for event in EVENTS:
        frame = frames.get(event)
        report["events"][event] = {
            "listed": event in available,
            "rows": len(frame) if frame is not None else None,
            "columns": list(frame.columns) if frame is not None else [],
        }
    freeze = frames.get("round_freeze_end")
    ticks = freeze.tick.astype(int).tolist()[-3:] if freeze is not None else [1000]
    for name, props in GROUPS.items():
        try:
            frame = parser.parse_ticks(props, ticks=ticks)
            # Samples omit identities; values illustrate units and inventory labels.
            samples = frame[props].head(3).to_json(orient="records")
            report["properties"][name] = {
                "status": "ok",
                "rows": len(frame),
                "columns": list(frame.columns),
                "samples": json.loads(samples),
            }
        except Exception as exc:
            report["properties"][name] = {"status": "error", "reason": str(exc)}
    report["seconds"] = round(time.perf_counter() - start, 3)
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("demo", type=Path)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    result = audit(args.demo.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
