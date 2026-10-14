"""Prepare real saved grenade flights, verify playback and source-free warm reads."""

import json
import sys
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import Config
from src.demos.demo_manager import DemoManager
from src.demos.spatial_service import get_spatial_context
from src.gui.radar_player import playback_data, playback_html
from src.storage.database import Database


def main():
    config = Config.load()
    db, manager = Database(config.db_path), DemoManager(config.demos_dir)
    results = []
    with patch("demoparser2.DemoParser", side_effect=AssertionError("Parser reopened")):
        for item in db.list_demo_analyses():
            if item["map_name"] not in {"de_mirage", "de_inferno", "de_dust2", "de_anubis"}:
                continue
            analysis = db.get_demo_analysis(item["demo_id"], include_grenades=False)
            assert analysis.grenades_df.empty
            context = get_spatial_context(db, manager, analysis, 2)
            labels = {str(row.steamid): str(row.name) for row in analysis.player_info.itertuples()}
            player = next(iter(labels))
            start = perf_counter()
            payload = playback_data(context, analysis, 2, labels, player)
            cold = perf_counter() - start
            assert payload["projectile_status"] == "ready"
            assert payload["throws"] and payload["projectiles"]
            flashed = [p for p in payload["players"] if p["flash_intervals"]]
            assert flashed and payload["flash_event_count"] > 0
            assert payload["flash_timing"] == "recorded_effect_window_not_full_blindness"
            for player_state in flashed:
                for first, last in player_state["flash_intervals"]:
                    assert 0 <= first < last <= payload["duration"]
                    if player_state["death"] is not None:
                        assert last <= player_state["death"]
            for track in payload["projectiles"]:
                assert track["start"] < track["end"]
                assert all(track["start"] <= s[0] < track["end"] for s in track["samples"])
                assert all(a[0] < b[0] for a, b in zip(
                    track["samples"], track["samples"][1:], strict=False,
                ))
            encoded = json.dumps(payload, allow_nan=False)
            assert "steamid" not in encoded
            assert all(sid not in encoded for sid in labels)
            html = playback_html(payload)
            assert 'id="grenades" checked' in html
            assert 'id="flashes" checked' in html
            assert "function drawGrenades" in html
            with (
                patch.object(db, "get_demo_projectiles", side_effect=AssertionError("Raw read")),
                patch.object(
                    db, "get_observation_frame", side_effect=AssertionError("Source read")
                ),
                patch.object(manager, "analysis_path", side_effect=AssertionError("Binary read")),
            ):
                start = perf_counter()
                warm_payload = playback_data(context, analysis, 2, labels, player)
                warm = perf_counter() - start
            assert warm_payload == payload
            if analysis.map_name == "de_anubis":
                assert any(
                    abs(p["start"] - (10290 - 9749) / 64) < 1e-9
                    for p in payload["projectiles"]
                    if p["kind"] == "Flash"
                )
            result = {
                "map": analysis.map_name,
                "demo_file": analysis.file_name,
                "round": 2,
                "throws": len(payload["throws"]),
                "projectiles": len(payload["projectiles"]),
                "flash_events": payload["flash_event_count"],
                "flashed_players": len(flashed),
                "flash_intervals": sum(len(p["flash_intervals"]) for p in flashed),
                "flight_samples": sum(len(p["samples"]) for p in payload["projectiles"]),
                "payload_bytes": len(encoded.encode("utf-8")),
                "prepare_seconds": round(cold, 3),
                "warm_seconds": round(warm, 3),
            }
            results.append(result)
            print(json.dumps(result), flush=True)
    Path("docs/v2d_projectiles_verification.json").write_text(
        json.dumps(
            {"checks": "passed; cached sources, no parser, no browser", "results": results},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
