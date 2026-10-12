"""Adapt fixed historical reference fixtures to current contracts, only in tests."""

import json
import pandas as pd
from src.demos.observations import normalize_states, round_clock, stamp_observation_ids
from src.demos.spatial_service import context_key, get_spatial_context as get_mirage_context
from src.demos.context_summary import snapshot, player_setup_profile
from src.maps.context import enrich_spatial, SpatialContext
from src.models.observations import MatchObservations

annotate_states = normalize_states


class MirageContext:
    def __new__(cls, clock, states, utility, diagnostics, entries=None, **frames):
        states = states.drop(columns=["zone", "place", "region_id"], errors="ignore")
        states = stamp_observation_ids(states, "fixture", "states")
        observations = MatchObservations(
            "fixture",
            "de_mirage",
            "fixture-source",
            clock=clock,
            states=states,
            utility=utility,
            diagnostics=diagnostics,
            **frames,
        )
        if "start_tick" not in observations.clock:
            observations.clock["start_tick"] = observations.clock.freeze_tick
        result = FixtureSpatialContext(
            observations, enrich_spatial(observations).states, enrich_spatial(observations).profile
        )
        result.entries = entries or []
        return result

    @classmethod
    def from_json(cls, payload):
        data = json.loads(payload)
        if "observations" in data:
            return SpatialContext.from_json(payload)
        return cls(
            pd.DataFrame(data["clock"]),
            pd.DataFrame(data["states"]),
            pd.DataFrame(data["utility"]),
            data["diagnostics"],
            data.get("entries"),
            **{
                name: pd.DataFrame(data.get(name, []))
                for name in (
                    "smokes",
                    "shots",
                    "equipment",
                    "economy",
                    "bombs",
                    "throws",
                    "utility_lifecycles",
                )
            },
        )


def entry_route(site, data):
    from src.maps.resolver import entry_route as route
    from src.maps.registry import get_profile

    return route(site, data, get_profile("de_mirage"))


class FixtureSpatialContext(SpatialContext):
    def __setattr__(self, name, value):
        if (
            name not in {"observations", "profile", "entries", "states"}
            and "observations" in self.__dict__
        ):
            if hasattr(self.observations, name):
                setattr(self.observations, name, value)
                return
        super().__setattr__(name, value)


def source_fixture(analysis, context):
    from src.demos.observations import observations_key

    context.observations.cache_key = observations_key(analysis)
    context.observations.demo_id = analysis.content_hash
    return context.observations


def persist_fixture(db, analysis, context):
    from unittest.mock import Mock, patch
    from pathlib import Path

    manager = Mock()
    manager.analysis_path.return_value = Path("fixture.dem")
    with patch(
        "src.demos.spatial_service.extract_observations",
        return_value=source_fixture(analysis, context),
    ):
        return get_mirage_context(db, manager, analysis)
