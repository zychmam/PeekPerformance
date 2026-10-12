"""Round-scoped animation payload and actual JavaScript playback behavior."""

import json
import shutil
import subprocess
from pathlib import Path

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
    assert any(p["death"] == (7802-6828)/64 for p in data["players"])
    assert any(e["text"] == "Plant bomby" for e in data["events"])
    assert len(data["utility"]) == len(context.utility[context.utility.total_rounds_played.eq(1)])
    payload = json.dumps(data, allow_nan=False)
    assert "steamid" not in payload
    assert '"P01"' not in payload
    html = playback_html(data)
    assert '</script><script>alert' not in html
    assert "\\u003c/script>" in html
    assert 'requestAnimationFrame' in html
    assert 'https://' not in html  # Self-contained, no external scripts or images.


@pytest.mark.skipif(not shutil.which("node"), reason="Node needed for JS runtime verification")
def test_javascript_controls_and_timing():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([shutil.which("node"), "tests/radar_player_runtime.cjs"],
                            cwd=root, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
