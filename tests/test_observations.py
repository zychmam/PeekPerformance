"""Map-independent extraction, source identity and explicit clock assumptions."""

from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from src.demos.observations import (
    extract_observations,
    normalize_states,
    observations_key,
    round_clock,
    stamp_observation_ids,
    tick_rate_metadata,
)
from src.demos.replay_effects import extract_replay_effects
from src.demos.tactical_evidence import collect_evidence
from src.demos.versions import ANALYSIS_VERSION
from src.models.models import DemoAnalysis
from src.models.observations import MatchObservations, RoundClock


def analysis_fixture():
    return DemoAnalysis(
        "unknown.dem",
        content_hash="source-hash",
        map_name="de_unknown",
        analysis_version=ANALYSIS_VERSION,
        rounds_df=pd.DataFrame(
            [{"total_rounds_played": 1, "start_tick": 0, "tick": 300, "winner": "CT"}]
        ),
        damage_df=pd.DataFrame(
            [{"total_rounds_played": 1, "tick": 170, "enemy_damage": 10, "actual_damage": 10}]
        ),
    )


class PartialParser:
    def __init__(self):
        self.position_ticks = []

    def parse_event(self, event, **kwargs):
        return pd.DataFrame({"tick": [100]}) if event == "round_freeze_end" else pd.DataFrame()

    def parse_ticks(self, props, ticks):
        if "yaw" in props or "has_helmet" in props:
            raise ValueError("unsupported optional property")
        if "X" in props:
            self.position_ticks.append(ticks)
        return pd.DataFrame(
            [
                {
                    "tick": tick,
                    "steamid": "76561198000000001",
                    **{
                        p: {
                            "X": 1,
                            "Y": 2,
                            "Z": 3,
                            "health": 100,
                            "is_alive": True,
                            "team_num": 2,
                            "last_place_name": "UnknownNavigationLabel",
                            "inventory": ["C4", "Flashbang", "Flashbang"],
                        }.get(p, 0)
                        for p in props
                    },
                }
                for tick in ticks
            ]
        )


def test_unknown_map_extracts_raw_sources_with_optional_field_isolation():
    analysis = analysis_fixture()
    parser = PartialParser()
    analyzer = SimpleNamespace(
        _parser=parser,
        get_header=lambda: {"map_name": "de_unknown", "tick_rate": 128},
        list_events=lambda: [],
        get_economy=lambda **kwargs: parser.parse_ticks(["balance"], kwargs["freeze_ticks"]),
    )
    with patch("src.demos.observations.DemoAnalyzer", return_value=analyzer):
        result = extract_observations(analysis, "unknown.dem")
    assert result.map_name == "de_unknown"
    assert result.diagnostics["sample_ticks"] == 13
    assert result.diagnostics["tick_rate_source"] == "header.tick_rate"
    assert not {"zone", "place", "region_id"}.intersection(result.states)
    assert result.states.last_place_name.eq("UnknownNavigationLabel").all()
    assert result.states.has_bomb.all()
    assert "pitch" in result.states and "yaw" not in result.states
    assert {169, 170, 300}.issubset(parser.position_ticks[0])
    assert min(parser.position_ticks[0]) == 100
    assert RoundClock.from_row(result.clock.iloc[0].to_dict()).seconds(228) == 1
    assert MatchObservations.from_json(result.to_json()).to_json() == result.to_json()


def test_header_mismatch_rejected_before_source_reads():
    with patch("src.demos.observations.DemoAnalyzer") as analyzer:
        analyzer.return_value.get_header.return_value = {"map_name": "wrong"}
        with pytest.raises(ValueError, match="Mapa"):
            extract_observations(analysis_fixture(), "wrong.dem")
        analyzer.return_value._parser.parse_event.assert_not_called()


def test_evidence_ids_ignore_spatial_labels_and_keep_duplicate_events():
    analysis = analysis_fixture()
    clock = round_clock(analysis.rounds_df, pd.DataFrame({"tick": [100]}))
    states = pd.DataFrame(
        [
            {
                "total_rounds_played": 1,
                "tick": 170,
                "steamid": "76561198000000001",
                "X": 1,
                "Y": 2,
                "Z": 3,
            }
        ]
    )
    shots = pd.DataFrame([{"total_rounds_played": 1, "tick": 170, "weapon": "ak47"}] * 2)
    observations = MatchObservations(
        "source-hash", "de_unknown", "source-key", clock=clock, states=states, shots=shots
    )
    enriched = SimpleNamespace(
        observations=observations, states=states.assign(zone="A", place="Old label")
    )
    before = collect_evidence(analysis, enriched)
    enriched.states = states.assign(zone="B", place="Renamed", level="upper")
    after = collect_evidence(analysis, enriched)
    restored = collect_evidence(analysis, MatchObservations.from_json(observations.to_json()))
    assert set(before[3]) == set(after[3]) == set(restored[3])
    assert before[0]["states"].zone.item() == "A"
    assert all(
        "zone" not in event.data and "place" not in event.data for event in before[3].values()
    )
    assert len([e for e in before[3].values() if e.source == "shots"]) == 2
    assert len({e.id for e in before[3].values() if e.source == "shots"}) == 2
    # Caller without a wrapper also cannot leak derived fields into evidence IDs.
    direct = SimpleNamespace(clock=clock, states=enriched.states, shots=shots)
    assert set(collect_evidence(analysis, direct)[3]) == set(before[3])


def test_clock_fallback_is_explicit_and_missing_freeze_not_invented():
    assert tick_rate_metadata({}) == (64, "assumed_64")
    assert tick_rate_metadata({"tick_rate": float("nan")}) == (64, "assumed_64")
    assert tick_rate_metadata({"tick_interval": 1 / 128}) == (128, "header.tick_interval")
    clock = round_clock(analysis_fixture().rounds_df, pd.DataFrame())
    assert clock.freeze_tick.isna().all()
    assert RoundClock.from_row(clock.iloc[0].to_dict()).seconds(170) is None


def test_stamped_ids_survive_round_partition_and_clock_applies_to_evidence():
    analysis = analysis_fixture()
    analysis.rounds_df = pd.DataFrame(
        [
            {"total_rounds_played": 1, "start_tick": 0, "tick": 300},
            {"total_rounds_played": 2, "start_tick": 301, "tick": 600},
        ]
    )
    clock = round_clock(
        analysis.rounds_df, pd.DataFrame({"tick": [100, 350]}), 128, "header.tick_rate"
    )
    shots = stamp_observation_ids(
        pd.DataFrame(
            [
                {"total_rounds_played": 1, "tick": 228, "weapon": "ak47"},
                {"total_rounds_played": 2, "tick": 478, "weapon": "ak47"},
            ]
        ),
        analysis.content_hash,
        "shots",
    )
    whole = collect_evidence(analysis, SimpleNamespace(clock=clock, shots=shots))[3]
    one = collect_evidence(
        analysis,
        SimpleNamespace(
            clock=clock[clock.total_rounds_played.eq(2)],
            shots=shots[shots.total_rounds_played.eq(2)],
        ),
    )[3]
    eid = shots.event_id.iloc[1]
    assert eid in whole and eid in one
    assert whole[eid].seconds == one[eid].seconds == 1


def test_key_does_not_depend_on_derived_labels_and_states_keep_raw_xyz():
    analysis = analysis_fixture()
    before = observations_key(analysis)
    analysis.damage_df["zone"] = "A"
    analysis.damage_df["place"] = "Any label"
    assert observations_key(analysis) == before
    clock = round_clock(analysis.rounds_df, pd.DataFrame({"tick": [100]}))
    states = normalize_states(
        pd.DataFrame(
            [
                {
                    "tick": 170,
                    "steamid": "1",
                    "X": 1,
                    "Y": 2,
                    "Z": 3,
                    "last_place_name": "AnyRawLabel",
                    "zone": "A",
                }
            ]
        ),
        clock,
    )
    assert states.X.item() == 1 and states.last_place_name.item() == "AnyRawLabel"
    assert "zone" not in states


def test_smoke_visual_estimate_scales_with_explicit_clock_but_is_not_observed_end():
    clock = round_clock(
        analysis_fixture().rounds_df.assign(tick=4000),
        pd.DataFrame({"tick": [100]}),
        128,
        "header.tick_rate",
    )
    utility = pd.DataFrame(
        [
            {
                "tick": 170,
                "total_rounds_played": 1,
                "source_event": "smokegrenade_detonate",
                "kind": "Smoke",
                "entityid": 1,
                "x": 0,
                "y": 0,
                "z": 0,
            }
        ]
    )
    extras = {}
    smokes, _ = extract_replay_effects(
        None, clock, utility, set(), {}, extras=extras, tick_rate=128
    )
    assert smokes.end_tick.item() == 170 + 22 * 128
    assert smokes.observed_end_tick.item() is None
    assert extras["utility_lifecycles"].end_tick.item() is None
