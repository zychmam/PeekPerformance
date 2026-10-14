"""Read-only check of M3 contacts against reviewed rounds on two real demos."""

import json
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.demos.tactical_rounds import load_tactical_match
from src.storage.database import Database


EXPECTED = {
    "bd296c05d542b9ee5b5fc261394f25190791469f022323152ba8bc8988e70ed0": {
        1: (7556, 7802), 6: (32783, 33055),
        13: (71380, 71380), 20: (105746, 105780),
    },
    "ff928acb836e2137342e874263c6dddb562f360e68865b8c9e68b74917e3e28d": {
        1: (8810, 9098), 3: (22091, 23033),
        10: (66946, 67340), 20: (125826, 127368),
    },
}


class ReadOnlyDatabase(Database):
    def __init__(self, path):
        self._db_path = str(path)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(Path(self._db_path).resolve().as_uri() + "?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".peek_performance" / "peekperformance.db"
    db = ReadOnlyDatabase(path)
    rows = []
    for demo_id, cases in EXPECTED.items():
        for number, (damage_tick, kill_tick) in cases.items():
            match = load_tactical_match(db, demo_id, number)
            rnd = match.rounds[0]
            contacts = rnd.contacts
            observed_damage = min(c.tick for c in contacts if c.kind == "damage")
            observed_kill = min(
                c.tick for c in contacts
                if any(match.evidence[eid].source == "kills" for eid in c.evidence_ids)
            )
            assert (observed_damage, observed_kill) == (damage_tick, kill_tick)
            assert {match.evidence[eid].tick for eid in rnd.opening_kill_ids} == {kill_tick}
            for key in ("first_enemy_damage", "first_firearm_damage", "first_enemy_kill"):
                reference = rnd.foundation.contact_references[key]
                ids = set(rnd.contact_references[key])
                if ids and reference.tick is not None:
                    assert {c.tick for c in contacts if c.id in ids} == {reference.tick}
            assert all(
                position.sample_tick is None or position.sample_tick < contact.tick
                for contact in contacts
                for position in (contact.attacker_position, contact.victim_position)
            )
            positioned = sum(
                position.status == "observed"
                for contact in contacts
                for position in (contact.attacker_position, contact.victim_position)
            )
            state_ticks = [event.tick for event in match.evidence.values()
                           if event.source == "states"]
            rows.append({"map": match.map_name, "round": number,
                         "contacts": len(contacts), "first_damage": observed_damage,
                         "first_kill": observed_kill,
                         "positioned_participants": positioned,
                         "alive_start": [rnd.alive_states[0].t_alive,
                                         rnd.alive_states[0].ct_alive],
                         "alive_end": [rnd.alive_states[-1].t_alive,
                                       rnd.alive_states[-1].ct_alive],
                         "alive_status": str(rnd.alive_status),
                         "first_state_after_freeze": min(
                             (tick - rnd.freeze_end_tick for tick in state_ticks
                              if tick >= rnd.freeze_end_tick), default=None)})
    print(json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
