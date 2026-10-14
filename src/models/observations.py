"""Map independent source contracts and fingerprints for coach processing."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from hashlib import sha256

import pandas as pd

OBSERVATIONS_SCHEMA_VERSION = 1


def canonical_fingerprint(value: object) -> str:
    """Hash JSON data, rejecting NaN and using deterministic key ordering."""
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def frame_records(frame: pd.DataFrame) -> list[dict]:
    safe = frame.copy()
    for column in safe:
        if str(column).lower().replace("_", "").endswith("steamid"):
            safe[column] = safe[column].astype("string")
    rows = json.loads(safe.to_json(orient="records"))
    for row in rows:
        for key, value in row.items():
            if isinstance(value, float) and value.is_integer():
                row[key] = int(value)
    return rows


@dataclass(frozen=True)
class RoundClock:
    round_number: int
    start_tick: int
    freeze_end_tick: int | None
    end_tick: int
    tick_rate: float = 64.0
    time_source: str = "assumed_64"

    def __post_init__(self):
        if self.end_tick < self.start_tick:
            raise ValueError("Round ends before it starts")
        if self.freeze_end_tick is not None and not (
            self.start_tick <= self.freeze_end_tick <= self.end_tick
        ):
            raise ValueError("Freeze end outside round")
        if not math.isfinite(self.tick_rate) or self.tick_rate <= 0:
            raise ValueError("Tick rate must be positive and finite")
        if not self.time_source:
            raise ValueError("Time source or explicit assumption is required")
        if self.time_source == "assumed_64" and self.tick_rate != 64:
            raise ValueError("assumed_64 requires a 64 tick rate")

    def seconds(self, tick: int) -> float | None:
        if self.freeze_end_tick is None:
            return None
        return (tick - self.freeze_end_tick) / self.tick_rate

    def ticks(self, seconds: float) -> int:
        if not math.isfinite(seconds):
            raise ValueError("Nonfinite time")
        return round(seconds * self.tick_rate)

    def tick_at(self, seconds: float) -> int | None:
        return None if self.freeze_end_tick is None else self.freeze_end_tick + self.ticks(seconds)

    def contains(self, tick: int) -> bool:
        return self.start_tick <= tick <= self.end_tick

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> RoundClock:
        return cls(**data)

    @classmethod
    def from_row(cls, row: dict) -> RoundClock:
        freeze = row.get("freeze_end_tick", row.get("freeze_tick"))
        return cls(
            round_number=int(row.get("round_number", row.get("total_rounds_played"))),
            start_tick=int(row["start_tick"]),
            freeze_end_tick=int(freeze) if pd.notna(freeze) else None,
            end_tick=int(row.get("end_tick", row.get("tick"))),
            tick_rate=float(row.get("tick_rate", 64)),
            time_source=str(row.get("time_source", "assumed_64")),
        )


@dataclass(frozen=True)
class DetectorConfig:
    version: int = 1
    early_seconds: float = 15.0
    snapshot_seconds: tuple[float, ...] = (0, 5, 10, 15)
    refrag_seconds: float = 5.0
    fight_idle_seconds: float = 5.0
    entry_group_seconds: float = 8.0
    entry_confirmation_seconds: float = 0.5
    max_sample_age_seconds: float = 1.0
    max_sample_gap_seconds: float = 2.0

    def __post_init__(self):
        if self.version != 1:
            raise ValueError("Unsupported detector config")
        for key, value in asdict(self).items():
            if key in {"version", "snapshot_seconds"}:
                continue
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"Invalid detector threshold {key}")
        if any(not math.isfinite(v) or v < 0 for v in self.snapshot_seconds):
            raise ValueError("Invalid snapshot threshold")

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(asdict(self))


@dataclass(frozen=True)
class StageManifest:
    stage: str
    schema_version: int
    algorithm_version: str
    dependencies: dict[str, str]
    status: str = "observed"
    reasons: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.stage or self.schema_version < 1 or not self.algorithm_version:
            raise ValueError("Invalid stage identity")
        statuses = {"observed", "partial", "unknown", "verified_absent", "not_evaluated"}
        if self.status not in statuses:
            raise ValueError("Unknown stage status")

    @property
    def cache_key(self) -> str:
        return canonical_fingerprint(
            {
                "stage": self.stage,
                "schema_version": self.schema_version,
                "algorithm_version": self.algorithm_version,
                "dependencies": self.dependencies,
            }
        )

    def to_dict(self) -> dict:
        return asdict(self)


OBSERVATION_FRAMES = (
    "clock",
    "states",
    "utility",
    "smokes",
    "shots",
    "equipment",
    "economy",
    "bombs",
    "throws",
    "utility_lifecycles",
)


@dataclass
class MatchObservations:
    demo_id: str
    map_name: str
    cache_key: str
    clock: pd.DataFrame = field(default_factory=pd.DataFrame)
    states: pd.DataFrame = field(default_factory=pd.DataFrame)
    utility: pd.DataFrame = field(default_factory=pd.DataFrame)
    diagnostics: dict = field(default_factory=dict)
    smokes: pd.DataFrame = field(default_factory=pd.DataFrame)
    shots: pd.DataFrame = field(default_factory=pd.DataFrame)
    equipment: pd.DataFrame = field(default_factory=pd.DataFrame)
    economy: pd.DataFrame = field(default_factory=pd.DataFrame)
    bombs: pd.DataFrame = field(default_factory=pd.DataFrame)
    throws: pd.DataFrame = field(default_factory=pd.DataFrame)
    utility_lifecycles: pd.DataFrame = field(default_factory=pd.DataFrame)
    schema_version: int = OBSERVATIONS_SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != OBSERVATIONS_SCHEMA_VERSION:
            raise ValueError("Unsupported observations schema")
        if not self.demo_id or not self.map_name or not self.cache_key:
            raise ValueError("Observations require demo, map and source identity")
        if {"zone", "place", "region_id", "direction"}.intersection(self.states.columns):
            raise ValueError("Source states contain derived spatial labels")

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "demo_id": self.demo_id,
            "map_name": self.map_name,
            "cache_key": self.cache_key,
            "diagnostics": self.diagnostics,
            **{name: frame_records(getattr(self, name)) for name in OBSERVATION_FRAMES},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), allow_nan=False, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict) -> MatchObservations:
        return cls(
            **{key: value for key, value in data.items() if key not in OBSERVATION_FRAMES},
            **{name: pd.DataFrame(data.get(name, [])) for name in OBSERVATION_FRAMES},
        )

    @classmethod
    def from_json(cls, payload: str) -> MatchObservations:
        return cls.from_dict(json.loads(payload))


def source_key(
    demo_id: str, extraction_version: int, parser_version: str, inputs: dict | None = None
) -> str:
    """Source cache has no map profile, detector, or presentation dependency."""
    return canonical_fingerprint(
        {
            "demo_id": demo_id,
            "extraction_version": extraction_version,
            "parser_version": parser_version,
            "inputs": inputs or {},
        }
    )


def observation_id(demo_id: str, source: str, source_fingerprint: str, index: int) -> str:
    """Source row position deliberately distinguishes identical same-tick rows."""
    if index < 0 or not all((demo_id, source, source_fingerprint)):
        raise ValueError("Invalid source observation identity")
    return f"{demo_id}:{source}:{source_fingerprint}:{index}"
