"""Read-only M3.3b verification against eight reviewed Mirage/Inferno rounds."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_m3_contacts import EXPECTED, ReadOnlyDatabase
from src.demos.tactical_rounds import load_tactical_match


OPENING_REFRAGS = {
    "de_mirage": {1: (7802, 7874, 72), 6: None,
                  13: (71380, 71436, 56), 20: (105780, 105796, 16)},
    "de_inferno": {1: None, 3: (23033, 23136, 103),
                   10: None, 20: None},
}
OTHER_REFRAGS = {
    "de_inferno": {20: (127565, 127649, 84)},
}


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".peek_performance" / "peekperformance.db"
    db = ReadOnlyDatabase(path)
    for demo_id, rounds in EXPECTED.items():
        for number in rounds:
            match = load_tactical_match(db, demo_id, number)
            record = match.rounds[0]
            links = [
                (match.evidence[link.death_id].tick,
                 match.evidence[link.response_kill_id].tick, link.delay_ticks)
                for link in record.refrag_links
            ]
            opening = [item for link, item in zip(record.refrag_links, links)
                       if link.death_id in record.opening_kill_ids]
            expected = OPENING_REFRAGS[match.map_name][number]
            assert opening == ([expected] if expected else []), (match.map_name, number, opening)
            other = OTHER_REFRAGS.get(match.map_name, {}).get(number)
            if other:
                assert other in links, (match.map_name, number, links)
            assert record.opening_window_end_tick is not None
            assert all(match.evidence[eid].tick <= record.opening_window_end_tick
                       for eid in record.opening_window_kill_ids)
            print(f"{match.map_name} r{number}: {len(links)} refrag(s), "
                  f"{len(record.opening_window_kill_ids)} follow-up kill(s)")


if __name__ == "__main__":
    main()
