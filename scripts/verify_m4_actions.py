"""Verify/rebuild M4 from stored sources on both maps; never opens a demo parser."""

import json
import sys
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_m3_contacts import EXPECTED
from src.demos.spatial_service import get_spatial_context, read_context
from src.demos.tactical_actions import action_payload
from src.demos.tactical_rounds import build_tactical_match
from src.storage.database import Database


def main():
    db = Database(str(Path.home() / ".peek_performance" / "peekperformance.db"))
    with patch(
        "src.demos.demo_analyzer.DemoParser", side_effect=AssertionError("No reparse allowed")
    ):
        for demo_id, reference_rounds in EXPECTED.items():
            analysis = db.get_demo_analysis(demo_id, include_auxiliary=False)
            start = perf_counter()
            context = get_spatial_context(db, None, analysis)
            match = build_tactical_match(
                analysis,
                context,
                foundations=context.foundations,
                cached_actions=context.tactical_actions,
            )
            cold = perf_counter() - start
            payloads = {
                r.number: json.loads(json.dumps(action_payload(r), allow_nan=False))
                for r in match.rounds
            }
            context.persist_tactical_actions(match.rounds)
            start = perf_counter()
            cached = read_context(db, analysis)
            with patch(
                "src.demos.tactical_actions.enrich_movement",
                side_effect=AssertionError("M4 cache missed"),
            ):
                restored = build_tactical_match(
                    analysis,
                    cached,
                    foundations=cached.foundations,
                    cached_actions=cached.tactical_actions,
                )
            warm = perf_counter() - start
            assert payloads == {r.number: action_payload(r) for r in restored.rounds}
            size = len(json.dumps(payloads).encode())
            print(
                f"{analysis.map_name}: rounds={len(match.rounds)} cold={cold:.2f}s "
                f"warm={warm:.2f}s actions={size / 1024:.0f}KiB"
            )
            for r in match.rounds:
                assert {ref for f in r.fights for ref in f.contact_ids} == {
                    c.id for c in r.contacts
                }
                assert len([ref for f in r.fights for ref in f.contact_ids]) == len(r.contacts)
                if r.number in reference_rounds:
                    print(
                        f"  R{r.number}: stays={len(r.region_stays)} fights={len(r.fights)} "
                        f"attacks={[(a.target_site, a.outcome) for a in r.attacks]} "
                        f"reactions={len(r.rotations)} retake={r.retake.outcome}"
                    )


if __name__ == "__main__":
    main()
