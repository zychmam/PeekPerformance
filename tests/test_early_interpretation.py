"""Interpretation thresholds and unsupported tactical conclusions."""

import pytest

from src.demos.early_interpretation import interpret_preparation as _interpret
from src.maps.registry import get_profile

def interpret_preparation(rnd, evidence):
    return _interpret(rnd, evidence, profile=get_profile("de_mirage"))
from src.models.tactical import (
    Episode,
    Evidence,
    Preparation,
    RoundTactics,
    SetupSnapshot,
    Status,
)


def profile(areas, *, complete=True, dead=False):
    players = [{"player_id": f"P{i}", "area": {"A": "site_a", "B": "site_b", "mid": "mid", "spawn / TSpawn": "spawn_t"}.get(area, area), "alive": not (dead and i == 4),
                "has_bomb": i == 0, "sample_tick": 960, "place": "TRamp"}
               for i, area in enumerate(areas)]
    status = Status.OBSERVED if complete else Status.PARTIAL
    evidence = {"s": Evidence("s", "states", 1, 960, 15, {})}
    prep = Preparation(status=status, snapshots=[SetupSnapshot(
        15, 960, status, players, {}, [], ["s"],
    )])
    rnd = RoundTactics(1, 0, 2000, 0, {}, None, None, None, {},
                       t_preparation=prep)
    return rnd, evidence


@pytest.mark.parametrize(("areas", "formation", "separated"), [
    (["A"]*5, "concentrated_5", []),
    (["A"]*4+["B"], "4_plus_1", ["P4"]),
    (["A"]*3+["mid"]*2, "distributed", []),
    (["spawn / TSpawn"]*5, None, []),
])
def test_formation_is_multidimensional_orientation_not_attack_intent(areas, formation, separated):
    rnd, evidence = profile(areas)
    interpret_preparation(rnd, evidence)
    prep = rnd.t_preparation
    assert prep.formation == formation
    assert prep.separated_player_ids == separated
    assert prep.target_sequence == []
    assert prep.tempo is None
    assert all(f.certainty == "limited" and f.limitations
               for f in prep.findings if f.kind == "interpretation")
    assert all(f.evidence_ids for f in prep.findings)


@pytest.mark.parametrize(("complete", "dead"), [(False, False), (True, True)])
def test_missing_or_dead_fifth_is_not_a_lurker_or_four_plus_one(complete, dead):
    rnd, evidence = profile(["A"]*4+["B"], complete=complete, dead=dead)
    interpret_preparation(rnd, evidence)
    assert rnd.t_preparation.formation is None
    assert rnd.t_preparation.separated_player_ids == []


def test_early_entry_does_not_imply_rush_or_execute_and_bomb_is_observed():
    rnd, evidence = profile(["A"]*5)
    rnd.observed_entries = [Episode("entry", "site_entry", 640, 704,
                                    evidence_ids=["s"], area="A", status=Status.OBSERVED)]
    interpret_preparation(rnd, evidence)
    assert rnd.t_preparation.first_site_presence_seconds == 10
    assert rnd.t_preparation.tempo == "early_site_entry"
    assert rnd.t_preparation.bomb_area == "site_a"
    assert rnd.attacks == []
    # Re-evaluation is idempotent, not a second copy of the same report.
    findings = rnd.t_preparation.findings.copy()
    interpret_preparation(rnd, evidence)
    assert rnd.t_preparation.findings == findings


def test_ct_forward_presence_requires_alive_contiguous_confirmation_not_window():
    rnd, evidence = profile(["A"]*5)
    prep = rnd.ct_setup
    for tick, place, alive in ((640, "Underpass", True), (704, "Underpass", True)):
        eid = str(tick)
        evidence[eid] = Evidence(eid, "states", 1, tick, tick/64,
                                 {"steamid": "C1", "last_place_name": place,
                                  "is_alive": alive})
        prep.snapshot_ids.append(eid)
    prep.status = Status.PARTIAL
    interpret_preparation(rnd, evidence)
    assert prep.activity == "forward_presence"  # Positive fact despite gaps elsewhere.
    for change in ("SnipersNest", "CTSpawn", "BombsiteA"):
        for ev in (evidence["640"], evidence["704"]):
            ev.data["last_place_name"] = change
        interpret_preparation(rnd, evidence)
        assert prep.activity is None  # Missing coverage cannot establish absence.
    for ev in (evidence["640"], evidence["704"]):
        ev.data["last_place_name"] = "Underpass"
    evidence["704"].tick = 900
    interpret_preparation(rnd, evidence)
    assert prep.activity is None
    evidence["704"].tick = 704
    evidence["704"].data["is_alive"] = False
    interpret_preparation(rnd, evidence)
    assert prep.activity is None
    prep.status = Status.OBSERVED
    interpret_preparation(rnd, evidence)
    assert prep.activity == "no_confirmed_forward_presence"
