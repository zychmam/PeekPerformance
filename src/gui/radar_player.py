"""Round-only browser playback. No Streamlit rerun for playback controls."""

import base64
import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.demos.viewer_blinds import recorded_flash_windows
from src.maps.registry import WORKSPACE
from src.models.observations import RoundClock

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "maps"


def _number(value):
    return float(value) if value is not None and pd.notna(value) and math.isfinite(value) else None


def playback_data(context, analysis, rnd, labels, player_id, start_seconds=0, level_id=None):
    clock = context.clock[context.clock.total_rounds_played.eq(rnd)].iloc[0]
    time_basis = RoundClock.from_row(clock.to_dict())
    rate = time_basis.tick_rate
    freeze, end = int(clock.freeze_tick), int(clock.tick)
    profile = context.profile
    levels = profile.radar_levels if profile else []
    level = next((item for item in levels if item.id == level_id), levels[0] if levels else None)

    def sample_level(z):
        if len(levels) == 1:
            return levels[0].id
        candidates = [
            item.id
            for item in levels
            if z is not None
            and (item.z_min is None or z >= item.z_min)
            and (item.z_max is None or z < item.z_max)
        ]
        return candidates[0] if len(candidates) == 1 else None

    states = context.states
    part = states[states.total_rounds_played.eq(rnd)].sort_values("tick", kind="stable")
    ids = list(dict.fromkeys(part.steamid.astype(str)))
    index = {pid: i for i, pid in enumerate(ids)}
    players = [
        {
            "name": labels.get(pid, "Gracz"),
            "selected": pid == str(player_id),
            "samples": [],
            "death": None,
            "flash_intervals": [],
        }
        for pid in ids
    ]
    for row in part.to_dict("records"):
        if row.get("team_num") not in (2, 3):
            continue
        x, y = _number(row.get("X")), _number(row.get("Y"))
        if x is None or y is None:
            continue
        alive = row.get("is_alive")
        players[index[str(row["steamid"])]]["samples"].append(
            [
                (int(row["tick"]) - freeze) / rate,
                x,
                y,
                _number(row.get("Z")),
                bool(alive) if pd.notna(alive) else False,
                int(row["team_num"]),
                _number(row.get("health")),
                row.get("has_bomb") is True,
                _number(row.get("yaw")),
                str(row.get("place", "Nieznana strefa")),
                sample_level(_number(row.get("Z"))),
            ]
        )
    events = []
    kills = analysis.kills_df
    if "total_rounds_played" in kills:
        for row in kills[kills.total_rounds_played.eq(rnd)].to_dict("records"):
            seconds = (int(row["tick"]) - freeze) / rate
            if seconds < 0 or int(row["tick"]) > end:
                continue
            victim, attacker = str(row.get("user_steamid")), str(row.get("attacker_steamid"))
            if victim in index:
                previous = players[index[victim]]["death"]
                players[index[victim]]["death"] = (
                    min(previous, seconds) if previous is not None else seconds
                )
            events.append(
                {
                    "time": seconds,
                    "text": f"{labels.get(attacker, 'Świat')} → {labels.get(victim, 'Gracz')}",
                }
            )
    bombs = analysis.bomb_events_df
    if "total_rounds_played" in bombs:
        names = {
            "bomb_planted": "Plant bomby",
            "bomb_defused": "Rozbrojenie bomby",
            "bomb_exploded": "Wybuch bomby",
        }
        for row in bombs[bombs.total_rounds_played.eq(rnd)].to_dict("records"):
            if row.get("event") in names:
                events.append(
                    {"time": (int(row["tick"]) - freeze) / rate, "text": names[row["event"]]}
                )
    utility = []
    if "total_rounds_played" in context.utility:
        for row in context.utility[context.utility.total_rounds_played.eq(rnd)].to_dict("records"):
            x, y = _number(row.get("x")), _number(row.get("y"))
            if x is not None and y is not None:
                utility.append(
                    {
                        "time": (int(row["tick"]) - freeze) / rate,
                        "x": x,
                        "y": y,
                        "kind": str(row.get("kind", "Utility")),
                        "level_id": sample_level(_number(row.get("z"))),
                    }
                )
    duration = max(0, (end - freeze) / rate)
    smokes, shots = [], []
    for row in context.smokes.to_dict("records"):
        if row.get("total_rounds_played") != rnd:
            continue
        x, y = _number(row.get("x")), _number(row.get("y"))
        if x is not None and y is not None:
            smokes.append(
                {
                    "start": (int(row["tick"]) - freeze) / rate,
                    "end": (int(row["end_tick"]) - freeze) / rate,
                    "x": x,
                    "y": y,
                    "radius": row["radius"],
                    "estimated": row["end_source"] != "event",
                    "level_id": sample_level(_number(row.get("z"))),
                }
            )
    for row in context.shots.to_dict("records"):
        if row.get("total_rounds_played") != rnd:
            continue
        coords = [_number(row.get(key)) for key in ("user_X", "user_Y", "user_yaw")]
        if all(value is not None for value in coords):
            shots.append(
                {
                    "time": (int(row["tick"]) - freeze) / rate,
                    "x": coords[0],
                    "y": coords[1],
                    "yaw": coords[2],
                    "silenced": row.get("silenced") is True,
                    "level_id": sample_level(_number(row.get("user_Z"))),
                }
            )
    metadata = (
        {"pos_x": level.origin_x, "pos_y": level.origin_y, "scale": level.scale} if level else None
    )
    throws, projectiles = [], []
    source_throws = getattr(context, "throws", pd.DataFrame())
    if "total_rounds_played" in source_throws:
        for row in source_throws[source_throws.total_rounds_played.eq(rnd)].to_dict("records"):
            tick = int(row["tick"])
            if not freeze <= tick <= end:
                continue
            owner = str(row.get("user_steamid", ""))
            name = labels.get(owner, "Gracz")
            kind = str(row.get("kind", "Granat"))
            seconds = (tick - freeze) / rate
            events.append({"time": seconds, "text": f"{name} rzuca {kind}"})
            x, y, z = (_number(row.get(f"user_{axis}")) for axis in ("X", "Y", "Z"))
            if x is not None and y is not None:
                throws.append({"time": seconds, "x": x, "y": y, "kind": kind,
                               "name": name, "selected": owner == str(player_id),
                               "team": _number(row.get("user_team_num")),
                               "level_id": sample_level(z)})
    loader = getattr(context, "load_projectiles", None)
    projectile_status = "unavailable"
    if loader is not None:
        saved = loader(int(rnd))
        projectile_status = "ready"
        for row in saved["projectiles"]:
            owner = row["owner"]
            team = None
            if owner in index and players[index[owner]]["samples"]:
                team = players[index[owner]]["samples"][0][5]
            projectiles.append({
                "kind": row["kind"], "name": labels.get(owner, "Gracz"), "team": team,
                "selected": owner == str(player_id),
                "start": (row["start_tick"] - freeze) / rate,
                "end": (row["end_tick"] - freeze) / rate,
                "max_gap": row["max_gap_seconds"],
                "samples": [[(s[0] - freeze) / rate, s[1], s[2], s[3], sample_level(s[3])]
                            for s in row["samples"]],
            })
    deaths = {pid: freeze + players[i]["death"] * rate
              for pid, i in index.items() if players[i]["death"] is not None}
    flashes, flash_events = recorded_flash_windows(
        analysis.player_blinds_df, rnd, freeze, end, rate, deaths,
    )
    for pid, intervals in flashes.items():
        if pid in index:
            players[index[pid]]["flash_intervals"] = intervals
    for event in flash_events:
        victim = labels.get(event["victim"], "Gracz")
        attacker = labels.get(event["attacker"], "Nieznany gracz")
        duration_text = (f"{event['duration']:.2f} s" if event["duration"] is not None
                         else "czas nieznany")
        events.append({"time": (event["tick"] - freeze) / rate,
                       "text": f"{victim} trafiony flashem · {attacker} · {duration_text}"})
    return {
        "players": players,
        "events": sorted(events, key=lambda e: e["time"]),
        "utility": utility,
        "smokes": smokes,
        "shots": shots,
        "throws": throws,
        "projectiles": projectiles,
        "projectile_status": projectile_status,
        "flash_event_count": len(flash_events),
        "flash_timing": "recorded_effect_window_not_full_blindness",
        "level_ranges": [{"id": item.id, "z_min": item.z_min, "z_max": item.z_max}
                         for item in levels],
        "duration": duration,
        "start": min(duration, max(0, start_seconds)),
        "sample_seconds": context.diagnostics.get("sample_ticks", 64) / rate,
        "map": metadata,
        "level_id": level.id if level else None,
        "radar_image": level.image if level else None,
        "width": level.width if level else 1024,
        "height": level.height if level else 1024,
    }


def playback_html(data):
    # JSON is inert script data. Nicknames must never close the script tag or
    # become HTML; the client inserts them with textContent/canvas.fillText.
    payload = json.dumps(data, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
    template = (ASSETS / "radar_player.html").read_text(encoding="utf-8")
    script = (ASSETS / "radar_player.js").read_text(encoding="utf-8")
    path = (WORKSPACE / data["radar_image"]).resolve()
    if not path.is_relative_to(WORKSPACE.resolve()) or not path.is_file():
        raise ValueError("Radar image unavailable")
    radar = base64.b64encode(path.read_bytes()).decode()
    return (
        template.replace("__SCRIPT__", script)
        .replace("__RADAR__", radar)
        .replace(
            "__PAYLOAD__",
            payload,
        )
    )


def render_radar_player(context, analysis, rnd, labels, player_id, start_seconds):
    levels = context.profile.radar_levels if context.profile else []
    if not levels or not all((WORKSPACE / level.image).is_file() for level in levels):
        st.info("Radar dla tej mapy jest niedostępny.")
        return
    selected = (
        st.selectbox(
            "Poziom mapy",
            [level.id for level in levels],
            key=f"radar_level_{analysis.content_hash}_{rnd}",
        )
        if len(levels) > 1
        else levels[0].id
    )
    if len(levels) > 1:
        st.caption(
            "Radar pokazuje wybrany poziom; pozycje o nieustalonej wysokości "
            "pozostają tylko na liście graczy."
        )
    with st.spinner("Przygotowanie animacji granatów…"):
        data = playback_data(context, analysis, rnd, labels, player_id, start_seconds, selected)
    components.html(playback_html(data), height=900, scrolling=True)
