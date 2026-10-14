"""Map-independent spatial assignment; derived frames never mutate sources."""

from collections import OrderedDict, defaultdict
from math import isfinite
from threading import RLock

import pandas as pd

from src.models.observations import canonical_fingerprint, frame_records
from src.models.spatial import LocationAssignment, MapProfile

_COMPILED = OrderedDict()
_LOCK = RLock()
MAX_COMPILED = 16
_FINGERPRINTS = OrderedDict()


def _fingerprint(profile):
    # Profiles are immutable contracts; avoid hashing their entire JSON per row.
    with _LOCK:
        key = id(profile)
        entry = _FINGERPRINTS.get(key)
        if entry is not None and entry[0] is profile:
            _FINGERPRINTS.move_to_end(key)
            return entry[1]
        value = profile.semantic_fingerprint
        fingerprint = value() if callable(value) else value
        _FINGERPRINTS[key] = (profile, fingerprint)
        while len(_FINGERPRINTS) > MAX_COMPILED:
            _FINGERPRINTS.popitem(last=False)
        return fingerprint


def _compiled(profile):
    key = _fingerprint(profile)
    with _LOCK:
        if key in _COMPILED:
            _COMPILED.move_to_end(key)
            return _COMPILED[key]
        labels = defaultdict(list)
        geometry = []
        for region in profile.regions:
            for label in region.nav_labels:
                labels[label].append(region.id)
            for bound in region.bounds:
                geometry.append((region.id, region.priority, bound))
        result = (dict(labels), geometry)
        _COMPILED[key] = result
        while len(_COMPILED) > MAX_COMPILED:
            _COMPILED.popitem(last=False)
        return result


def _number(data, key):
    value = data.get(key, data.get(key.lower()))
    try:
        value = float(value)
        return value if isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _within(value, low, high, include_max=True):
    return value is not None and low <= value and (value <= high if include_max else value < high)


def _bounds_match(data, bound, nav):
    if bound.nav_labels and nav not in bound.nav_labels:
        return False
    if not (
        _within(_number(data, "X"), bound.x_min, bound.x_max, bound.include_max_x)
        and _within(_number(data, "Y"), bound.y_min, bound.y_max, bound.include_max_y)
    ):
        return False
    if bound.z_min is not None or bound.z_max is not None:
        z = _number(data, "Z")
        return _within(
            z,
            bound.z_min if bound.z_min is not None else float("-inf"),
            bound.z_max if bound.z_max is not None else float("inf"),
            bound.include_max_z,
        )
    return True


def classify(data: dict, profile: MapProfile | None, observation_id=None) -> LocationAssignment:
    oid = str(
        observation_id
        if observation_id is not None
        else data.get("event_id", data.get("observation_id", data.get("id", "")))
    )
    if not oid:
        # Standalone helper provenance; production frames receive source row IDs.
        oid = "sample:" + canonical_fingerprint(frame_records(pd.DataFrame([data]))[0])
    if profile is None:
        return LocationAssignment(observation_id=oid)
    labels, geometry = _compiled(profile)
    nav = data.get("last_place_name")
    labelled = set(labels.get(nav, []))
    matched = [
        (rid, priority) for rid, priority, bound in geometry if _bounds_match(data, bound, nav)
    ]
    region_map = {r.id: r for r in profile.regions}
    fingerprint = _fingerprint(profile)
    if matched:
        priority = max(p for _, p in matched)
        candidates = {rid for rid, p in matched if p == priority}
        # A priority > 0 explicitly authorizes overriding ambiguous nav labels.
        if labelled and not candidates.intersection(labelled) and priority <= 0:
            candidates |= labelled
        method = "geometry"
    else:
        candidates = labelled
        method = "nav_label"
        # Unqualified geometric regions must not be chosen from a label when
        # coordinates are missing/outside their volume (including stacked floors).
        candidates = {
            rid
            for rid in candidates
            if not region_map[rid].bounds or any(b.nav_labels for b in region_map[rid].bounds)
        }
        candidates = {
            rid for rid in candidates if nav not in region_map[rid].geometry_required_labels
        }
    ordered = sorted(candidates)
    if len(ordered) != 1:
        return LocationAssignment(
            oid,
            candidates=ordered,
            method=method,
            status="partial" if ordered else "unknown",
            profile_fingerprint=fingerprint,
        )
    region = region_map[ordered[0]]
    return LocationAssignment(
        oid,
        region_id=region.id,
        candidates=ordered,
        level_id=region.level_id,
        method=method,
        status="observed",
        profile_fingerprint=fingerprint,
    )


def resolve_region(data, profile):
    if not isinstance(data, dict):
        data = data._asdict() if hasattr(data, "_asdict") else vars(data)
    return classify(data, profile).region_id


def region(profile, region_id):
    return next((r for r in profile.regions if r.id == region_id), None) if profile else None


def region_label(region_id, profile):
    item = region(profile, region_id)
    return item.name if item else "Nieznana strefa"


def region_direction(region_id, profile):
    item = region(profile, region_id)
    return item.directions[0] if item and len(item.directions) == 1 else None


def region_site(region_id, profile):
    item = region(profile, region_id)
    return item.site_id if item and item.kind == "site" else None


def support_sites(region_id, profile):
    item = region(profile, region_id)
    return list(item.support_sites) if item else []


def is_forward(region_id, side, profile, sample=None):
    item = region(profile, region_id)
    if item is None:
        return False
    if sample is None:
        return None if side in item.forward_bounds else side in item.forward_sides
    return item.is_forward(side, sample)


def entry_route(site, data, profile):
    if not isinstance(data, dict):
        data = data._asdict() if hasattr(data, "_asdict") else vars(data)
    assignment = classify(data, profile)
    item = region(profile, assignment.region_id)
    if item and getattr(item, "route_requires_geometry", False) and assignment.method != "geometry":
        return "Nieustalony kierunek"
    return item.route_names.get(site, "Nieustalony kierunek") if item else "Nieustalony kierunek"


def annotate_frame(frame: pd.DataFrame, profile: MapProfile | None) -> pd.DataFrame:
    result = frame.copy()
    rows = frame.to_dict("records")
    assignments = [classify(row, profile) for row in rows]
    result["region_id"] = [a.region_id for a in assignments]
    result["location_status"] = [a.status for a in assignments]
    result["location_method"] = [a.method for a in assignments]
    result["location_candidates"] = [a.candidates for a in assignments]
    result["level_id"] = [a.level_id for a in assignments]
    result["place"] = [region_label(a.region_id, profile) for a in assignments]
    result["zone"] = [
        region_site(a.region_id, profile)
        or (region(profile, a.region_id).kind if a.region_id else "unknown")
        for a in assignments
    ]
    return result


decorate = annotate_frame
