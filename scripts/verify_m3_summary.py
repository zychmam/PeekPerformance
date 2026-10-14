"""Read-only M3 team/player narration check on eight reviewed demo rounds."""

from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_m3_contacts import EXPECTED, ReadOnlyDatabase
from src.demos.round_summary import player_summary, team_summary
from src.demos.round_index import round_state_index
from src.demos.tactical_rounds import load_tactical_match
from src.maps.registry import get_profile


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".peek_performance" / "peekperformance.db"
    db = ReadOnlyDatabase(path)
    for demo_id, rounds in EXPECTED.items():
        for number in rounds:
            start = perf_counter()
            match = load_tactical_match(db, demo_id, number)
            record = match.rounds[0]
            rate = record.foundation.clock["tick_rate"]
            labels = {player.player_id: f"Gracz {i + 1}" for i, player in enumerate(record.players)}
            team = team_summary(record, match.evidence, labels, get_profile(match.map_name), rate)
            first_tick = min((c.tick for c in record.contacts), default=None)
            if first_tick is not None:
                for item in team:
                    if item.title in {"Początek · T", "Początek · CT"}:
                        assert item.tick is None or first_tick - rate <= item.tick < first_tick
                        assert "przed pierwszym zarejestrowanym kontaktem" in item.text or "Brak świeżego" in item.text
            state_index = round_state_index(record, match.evidence)
            players = [player_summary(record, match.evidence, player.player_id, labels,
                                      get_profile(match.map_name), rate, state_index=state_index)
                       for player in record.players]
            for item in team + [item for summary in players for item in summary]:
                assert all(eid in match.evidence for eid in item.evidence_ids), (
                    match.map_name, number, item.title
                )
                assert not any(player.player_id in item.text for player in record.players), (
                    match.map_name, number, item.title
                )
            assert {"Początek · T", "Początek · CT", "Pierwszy kontakt", "Koniec"}.issubset(
                {item.title for item in team}
            )
            print(f"{match.map_name} r{number}: {len(team)} faktów drużyny, "
                  f"{sum(map(len, players))} faktów graczy, {perf_counter() - start:.2f} s")


if __name__ == "__main__":
    main()
