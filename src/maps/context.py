"""Source observations with an independent, replaceable spatial interpretation."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

import pandas as pd

from src.maps.registry import get_profile
from src.maps.resolver import annotate_frame
from src.models.observations import MatchObservations, observation_id
from src.models.spatial import MapProfile


@dataclass
class SpatialContext:
    observations: MatchObservations
    states: pd.DataFrame
    profile: MapProfile | None = None
    entries: list[dict] = field(default_factory=list)
    load_projectiles: Callable | None = field(default=None, repr=False, compare=False)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "observations"), name)

    def to_json(self):
        return json.dumps(
            {
                "schema_version": 1,
                "observations": self.observations.to_dict(),
                "entries": self.entries,
            },
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, payload):
        data = json.loads(payload)
        if data.get("schema_version") != 1:
            raise ValueError("Unsupported spatial context schema")
        result = enrich_spatial(MatchObservations.from_dict(data["observations"]))
        result.entries = data["entries"]
        return result


def enrich_spatial(
    observations: MatchObservations, profile: MapProfile | None = None
) -> SpatialContext:
    if profile is None:
        profile = get_profile(observations.map_name)
    if profile is not None and profile.map_name != observations.map_name:
        raise ValueError("Map profile does not match source observations")
    raw = observations.states.copy()
    if "event_id" in raw:
        raw["observation_id"] = raw.event_id
    elif "observation_id" not in raw:
        raw["observation_id"] = [
            observation_id(observations.demo_id, "states", observations.cache_key, i)
            for i in range(len(raw))
        ]
    return SpatialContext(observations, annotate_frame(raw, profile), profile)
