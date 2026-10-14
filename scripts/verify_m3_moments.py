"""Read-only check of the M3.4a chronology on eight reviewed rounds."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_m3_contacts import EXPECTED, ReadOnlyDatabase
from src.demos.tactical_rounds import load_tactical_match


REVIEWED = {
    "de_mirage": {
        1: {"opening": 7802, "refrag": 7874, "plant": 8436, "end": 9671},
        6: {"opening": 33055, "plant": 35062, "end": 37686},
        13: {"opening": 71380, "refrag": 71436, "end": 74124},
        20: {"opening": 105780, "refrag": 105796, "plant": 106815, "end": 108640},
    },
    "de_inferno": {
        1: {"opening": 9098, "end": 14368},
        3: {"opening": 23033, "refrag": 23136, "plant": 24989, "end": 27040},
        10: {"opening": 67340, "plant": 68896, "end": 71183},
        20: {"opening": 127368, "refrag": 127649, "end": 130947},
    },
}


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".peek_performance" / "peekperformance.db"
    db = ReadOnlyDatabase(path)
    for demo_id, rounds in EXPECTED.items():
        for number in rounds:
            match = load_tactical_match(db, demo_id, number)
            record = match.rounds[0]
            moments = record.moments
            expected = REVIEWED[match.map_name][number]
            assert moments[0].kind == "round_start"
            assert moments[0].start_tick == record.freeze_end_tick
            assert moments[-1].kind == "round_end"
            assert moments[-1].start_tick == expected["end"]
            assert [moment.start_tick for moment in moments] == sorted(
                moment.start_tick for moment in moments
            )
            for kind in ("opening", "refrag"):
                if kind in expected:
                    assert any(moment.kind == kind and moment.start_tick == expected[kind]
                               for moment in moments), (match.map_name, number, kind)
            if "plant" in expected:
                assert any(moment.kind == "bomb" and moment.start_tick == expected["plant"]
                           and any(match.evidence[eid].data.get("event") == "bomb_planted"
                                   for eid in moment.event_ids)
                           for moment in moments), (match.map_name, number, "plant")
            assert all(eid in match.evidence for moment in moments for eid in moment.event_ids)
            print(f"{match.map_name} r{number}: {len(moments)} ordered moments")


if __name__ == "__main__":
    main()
