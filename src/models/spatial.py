"""Declarative map data; geometry and adjacency never assert visibility."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from src.models.observations import canonical_fingerprint

MAP_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RegionBounds:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float | None = None
    z_max: float | None = None
    include_max_x: bool = True
    include_max_y: bool = True
    include_max_z: bool = True
    nav_labels: list[str] = field(default_factory=list)

    def __post_init__(self):
        for axis in ("x", "y", "z"):
            lo, hi = getattr(self, f"{axis}_min"), getattr(self, f"{axis}_max")
            if any(v is not None and not math.isfinite(v) for v in (lo, hi)):
                raise ValueError("Nonfinite geometry")
            if lo is not None and hi is not None and hi < lo:
                raise ValueError("Reversed geometry bounds")

    def contains(self, x: float, y: float, z: float | None = None) -> bool:
        for axis, value in (("x", x), ("y", y), ("z", z)):
            lo, hi = getattr(self, f"{axis}_min"), getattr(self, f"{axis}_max")
            if lo is None and hi is None:
                continue
            if value is None or not math.isfinite(value):
                return False
            if lo is not None and value < lo:
                return False
            if hi is not None and (
                value > hi or (value == hi and not getattr(self, f"include_max_{axis}"))
            ):
                return False
        return True


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    nav_labels: list[str] = field(default_factory=list)
    kind: str = "other"
    site_id: str | None = None
    directions: list[str] = field(default_factory=list)
    support_sites: list[str] = field(default_factory=list)
    forward_sides: list[str] = field(default_factory=list)
    bounds: list[RegionBounds] = field(default_factory=list)
    priority: int = 0
    level_id: str | None = None
    route_names: dict[str, str] = field(default_factory=dict)
    route_requires_geometry: bool = False
    metadata: dict = field(default_factory=dict)
    geometry_required_labels: list[str] = field(default_factory=list)
    # One physical defensive assignment, separate from possible support.
    defense_sector: str | None = None
    forward_bounds: dict[str, list[RegionBounds]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id or not self.name:
            raise ValueError("Region ID and display name are required")
        if self.kind not in {"site", "approach", "connector", "mid", "spawn", "other"}:
            raise ValueError("Unknown physical region kind")
        if self.kind == "site" and not self.site_id:
            raise ValueError("Site region requires site_id")
        if any(side not in {"T", "CT"} for side in self.forward_sides):
            raise ValueError("Unknown tactical side")
        if any(side not in self.forward_sides for side in self.forward_bounds):
            raise ValueError("Forward geometry requires declared side")

    def is_forward(self, side: str, sample: dict) -> bool | None:
        if side not in self.forward_sides:
            return False
        if side not in self.forward_bounds:
            return True
        coordinates = [sample.get(axis, sample.get(axis.lower())) for axis in ("X", "Y", "Z")]
        if any(value is None for value in coordinates[:2]):
            return None
        return any(bound.contains(*coordinates) for bound in self.forward_bounds[side])


@dataclass(frozen=True)
class SpatialConnection:
    from_region: str
    to_region: str
    kind: str = "walk"
    bidirectional: bool = False
    verification: str = "limited"

    def __post_init__(self):
        if self.kind not in {"walk", "ladder", "drop", "jump"}:
            raise ValueError("Unknown movement connection")
        if self.verification not in {"limited", "verified"}:
            raise ValueError("Unknown connection verification")
        if self.from_region == self.to_region:
            raise ValueError("Self connection")


@dataclass(frozen=True)
class RadarLevel:
    id: str
    image: str
    origin_x: float
    origin_y: float
    scale: float
    width: int = 1024
    height: int = 1024
    z_min: float | None = None
    z_max: float | None = None

    def __post_init__(self):
        if not self.id or not self.image:
            raise ValueError("Radar identity and image required")
        if not all(math.isfinite(v) for v in (self.origin_x, self.origin_y, self.scale)):
            raise ValueError("Nonfinite radar transform")
        if self.scale <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError("Invalid radar dimensions or scale")
        if self.z_min is not None and not math.isfinite(self.z_min):
            raise ValueError("Nonfinite radar height")
        if self.z_max is not None and not math.isfinite(self.z_max):
            raise ValueError("Nonfinite radar height")
        if self.z_min is not None and self.z_max is not None and self.z_min > self.z_max:
            raise ValueError("Reversed radar height")

    def project(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.origin_x) / self.scale, (self.origin_y - y) / self.scale


@dataclass(frozen=True)
class MapProfile:
    map_name: str
    profile_version: str
    regions: list[Region]
    connections: list[SpatialConnection] = field(default_factory=list)
    radar_levels: list[RadarLevel] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    compatibility: dict = field(default_factory=dict)
    coverage: dict = field(default_factory=dict)
    schema_version: int = MAP_SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != MAP_SCHEMA_VERSION:
            raise ValueError("Unsupported map schema")
        if not self.map_name or not self.profile_version:
            raise ValueError("Map identity and version required")
        ids = [r.id for r in self.regions]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate region ID")
        levels = [r.id for r in self.radar_levels]
        if len(levels) != len(set(levels)):
            raise ValueError("Duplicate radar level ID")
        sites = {r.site_id for r in self.regions if r.kind == "site"}
        for region in self.regions:
            if region.defense_sector not in sites | {None, "mid"}:
                raise ValueError("Unknown defense sector")
            if region.level_id and region.level_id not in levels:
                raise ValueError("Unknown region radar level")
            if any(site not in sites for site in region.support_sites):
                raise ValueError("Unknown supported site")
            if any(site not in sites for site in region.route_names):
                raise ValueError("Unknown route site")
        edges = set()
        for conn in self.connections:
            if conn.from_region not in ids or conn.to_region not in ids:
                raise ValueError("Connection references unknown region")
            edge = (conn.from_region, conn.to_region, conn.kind)
            if edge in edges:
                raise ValueError("Duplicate connection")
            edges.add(edge)
        # Capabilities are explicit: absence means the detector cannot use them.
        if "radar" in self.capabilities and not self.radar_levels:
            raise ValueError("Radar capability without radar")
        if "site_boundaries" in self.capabilities and not sites:
            raise ValueError("Site capability without sites")

    @property
    def regions_by_id(self) -> dict[str, Region]:
        return {r.id: r for r in self.regions}

    def supports(self, *capabilities: str) -> bool:
        return set(capabilities).issubset(self.capabilities)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> MapProfile:
        values = dict(data)
        regions = values.get("regions", [])
        if isinstance(regions, dict):
            regions = [dict(value, id=key) for key, value in regions.items()]
        values["regions"] = [
            Region(**{**item, "bounds": [RegionBounds(**b) for b in item.get("bounds", [])],
                      "forward_bounds": {side: [RegionBounds(**b) for b in bounds]
                                         for side, bounds in item.get("forward_bounds", {}).items()}})
            for item in regions
        ]
        values["connections"] = [
            SpatialConnection(**item) for item in values.get("connections", [])
        ]
        values["radar_levels"] = [RadarLevel(**item) for item in values.get("radar_levels", [])]
        return cls(**values)

    @property
    def semantic_fingerprint(self) -> str:
        regions = []
        for region in self.regions:
            item = asdict(region)
            for key in ("name", "route_names", "metadata"):
                item.pop(key)
            item["approach_sites"] = sorted(region.route_names)
            regions.append(item)
        return canonical_fingerprint(
            {
                "schema_version": self.schema_version,
                "map_name": self.map_name,
                "regions": sorted(regions, key=lambda r: r["id"]),
                "connections": sorted(
                    (asdict(c) for c in self.connections),
                    key=lambda c: (c["from_region"], c["to_region"], c["kind"]),
                ),
                "capabilities": sorted(c for c in self.capabilities if c != "radar"),
                "compatibility": self.compatibility,
                "coverage": self.coverage,
            }
        )

    @property
    def presentation_fingerprint(self) -> str:
        return canonical_fingerprint(
            {
                "names": {r.id: {"name": r.name, "routes": r.route_names} for r in self.regions},
                "radar_levels": [asdict(r) for r in self.radar_levels],
            }
        )


@dataclass(frozen=True)
class LocationAssignment:
    observation_id: str
    region_id: str | None = None
    candidates: list[str] = field(default_factory=list)
    level_id: str | None = None
    method: str = "none"
    status: str = "unknown"
    profile_fingerprint: str | None = None

    def __post_init__(self):
        if not self.observation_id:
            raise ValueError("Location requires source observation ID")
        if self.status not in {"observed", "partial", "unknown"}:
            raise ValueError("Unknown location status")
        if self.status == "observed" and not self.region_id:
            raise ValueError("Observed location requires region")
        if self.region_id and self.candidates and self.region_id not in self.candidates:
            raise ValueError("Resolved region outside candidates")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> LocationAssignment:
        return cls(**data)


class SpatialRelations:
    """Queries over typed declarations, returning unknown for missing graph edges."""

    def __init__(self, profile: MapProfile):
        self.profile = profile
        self.regions = profile.regions_by_id
        self.edges = {(c.from_region, c.to_region): c for c in profile.connections}
        self.edges.update(
            {(c.to_region, c.from_region): c for c in profile.connections if c.bidirectional}
        )

    def site(self, region_id: str) -> str | None:
        region = self.regions.get(region_id)
        return region.site_id if region and region.kind == "site" else None

    def approaches(self, region_id: str) -> tuple[str, ...]:
        region = self.regions.get(region_id)
        return tuple(region.route_names) if region else ()

    def support(self, region_id: str) -> tuple[str, ...]:
        region = self.regions.get(region_id)
        return tuple(region.support_sites) if region else ()

    def directions(self, region_id: str) -> tuple[str, ...]:
        region = self.regions.get(region_id)
        return tuple(region.directions) if region else ()

    def forward(self, region_id: str, side: str, sample=None) -> bool | None:
        region = self.regions.get(region_id)
        if not region:
            return None
        if sample is None:
            return None if side in region.forward_bounds else side in region.forward_sides
        return region.is_forward(side, sample)

    def connection(self, from_region: str, to_region: str) -> SpatialConnection | None:
        return self.edges.get((from_region, to_region))
