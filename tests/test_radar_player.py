"""Round-scoped animation payload and actual JavaScript playback behavior."""

import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from src.gui.radar_player import playback_data, playback_html
from tests.test_early_round import reference


def test_round_payload_has_exact_events_no_ids_and_safe_nicknames():
    analysis, context = reference()
    labels = {f"P{i:02}": f"Nick{i}" for i in range(1, 11)}
    labels["P01"] = '</script><script>alert("bad")</script>'
    data = playback_data(context, analysis, 1, labels, "P01", 10)
    assert data["start"] == 10
    assert len(data["players"]) == 10
    assert len([p for p in data["players"] if p["selected"]]) == 1
    assert all(0 <= s[0] <= data["duration"] for p in data["players"] for s in p["samples"])
    assert any(p["death"] == (7802 - 6828) / 64 for p in data["players"])
    assert any(e["text"] == "Plant bomby" for e in data["events"])
    assert len(data["utility"]) == len(context.utility[context.utility.total_rounds_played.eq(1)])
    payload = json.dumps(data, allow_nan=False)
    assert "steamid" not in payload
    assert '"P01"' not in payload
    html = playback_html(data)
    assert "</script><script>alert" not in html
    assert "\\u003c/script>" in html
    assert "requestAnimationFrame" in html
    assert "https://" not in html  # Self-contained, no external scripts or images.


def test_grenade_payload_has_throw_actor_and_real_flight_without_private_ids():
    analysis, context = reference()
    freeze = int(context.clock[context.clock.total_rounds_played.eq(1)].iloc[0].freeze_tick)
    context.observations.throws = pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "tick": freeze + 64,
                "user_steamid": "P01",
                "kind": "Flash",
                "user_X": 1.0,
                "user_Y": 2.0,
                "user_Z": 0.0,
                "user_team_num": 2,
            }
        ]
    )
    context.load_projectiles = lambda rnd: {
        "projectiles": [
            {
                "kind": "Flash",
                "owner": "P01",
                "start_tick": freeze + 70,
                "end_tick": freeze + 100,
                "max_gap_seconds": 0.15,
                "samples": [[freeze + 70, 1.0, 2.0, 0.0], [freeze + 99, 9.0, 4.0, 0.0]],
            }
        ]
    }
    data = playback_data(context, analysis, 1, {"P01": "Rzucający"}, "P01")
    assert data["throws"][0]["name"] == "Rzucający"
    assert any(e["text"] == "Rzucający rzuca Flash" for e in data["events"])
    assert data["projectiles"][0]["start"] == 70 / 64
    assert data["projectiles"][0]["selected"] is True
    assert '"P01"' not in json.dumps(data)


def test_flash_payload_maps_victim_and_preserves_source_time_without_full_blind_claim():
    analysis, context = reference()
    freeze = int(context.clock[context.clock.total_rounds_played.eq(1)].iloc[0].freeze_tick)
    analysis.player_blinds_df = pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "tick": freeze + 64,
                "user_steamid": "P01",
                "attacker_steamid": "P01",
                "blind_duration": 2.0,
            },
            {
                "total_rounds_played": 1,
                "tick": freeze + 128,
                "user_steamid": "P01",
                "attacker_steamid": "P02",
                "blind_duration": 2.0,
            },
        ]
    )
    data = playback_data(context, analysis, 1, {"P01": "Alice", "P02": "Bob"}, "P01")
    player = next(p for p in data["players"] if p["name"] == "Alice")
    assert player["flash_intervals"] == [[1.0, 4.0]]
    assert data["flash_event_count"] == 2
    assert data["flash_timing"] == "recorded_effect_window_not_full_blindness"
    assert any("Alice trafiony flashem" in e["text"] for e in data["events"])
    assert 'id="flashes" checked' in playback_html(data)


@pytest.mark.skipif(not shutil.which("node"), reason="Node needed for JS runtime verification")
def test_javascript_controls_and_timing():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [shutil.which("node"), "tests/radar_player_runtime.cjs"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
