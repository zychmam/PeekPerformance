"""Persist independent source and spatial stages, shared by all match players."""

from dataclasses import replace
from functools import lru_cache, partial
from threading import RLock

import pandas as pd

from src.demos.observations import extract_observations, observations_key
from src.maps.context import SpatialContext, enrich_spatial
from src.maps.registry import get_profile
from src.maps.resolver import region, region_label, region_site
from src.models.observations import (
    OBSERVATION_FRAMES,
    DetectorConfig,
    MatchObservations,
    canonical_fingerprint,
    frame_records,
)

SPATIAL_VERSION = 2
LOCATION_COLUMNS = (
    "region_id",
    "location_status",
    "location_method",
    "location_candidates",
    "level_id",
)


def selected_profile(analysis, profile=None):
    profile = profile or get_profile(analysis.map_name)
    if profile and profile.map_name != analysis.map_name:
        raise ValueError("Profile map does not match demo")
    return profile


def spatial_key(analysis, profile=None):
    profile = selected_profile(analysis, profile)
    return canonical_fingerprint(
        {
            "sources": observations_key(analysis),
            "map": profile.semantic_fingerprint if profile else None,
            "spatial_version": SPATIAL_VERSION,
        }
    )


def context_key(analysis, profile=None, config=None):
    from src.demos.site_entries import ENTRY_VERSION

    # Refrag is computed from kills after the spatial stage. Keep the pre-M3.3b
    # value in this key so changing its window reuses saved map observations.
    spatial_config = replace(config or DetectorConfig(), refrag_seconds=10.0)
    return canonical_fingerprint(
        {
            "spatial": spatial_key(analysis, profile),
            "entries_version": ENTRY_VERSION,
            "detectors": spatial_config.fingerprint,
        }
    )


@lru_cache(maxsize=64)
def _context_lock(db_path, demo_id):
    return RLock()


def _manifest(analysis, key, numbers, **extra):
    return dict(
        demo_id=analysis.content_hash, cache_key=key, round_numbers=sorted(numbers), **extra
    )


def _source_payloads(observations):
    numbers = observations.clock.total_rounds_played.astype(int).tolist()
    grouped = {}
    for name in OBSERVATION_FRAMES:
        frame = getattr(observations, name)
        grouped[name] = (
            {
                int(n): frame_records(part)
                for n, part in frame.groupby("total_rounds_played", sort=False)
            }
            if "total_rounds_played" in frame
            else {}
        )
    return {n: {name: grouped[name].get(n, []) for name in OBSERVATION_FRAMES} for n in numbers}


def _read_sources(db, analysis, round_number=None):
    key = observations_key(analysis)
    manifest = db.get_stage_manifest(analysis.content_hash, "observations", key)
    if manifest is None:
        return None
    saved = db.get_stage_rounds(analysis.content_hash, "observations", key, round_number)
    expected = manifest["round_numbers"] if round_number is None else [round_number]
    if sorted(saved) != sorted(expected):
        return None
    return MatchObservations(
        demo_id=analysis.content_hash,
        map_name=analysis.map_name,
        cache_key=key,
        diagnostics=manifest["diagnostics"],
        **{
            name: pd.DataFrame([row for payload in saved.values() for row in payload[name]])
            for name in OBSERVATION_FRAMES
        },
    )


def _restore_spatial(observations, saved, profile, saved_entries=None):
    raw = observations.states
    parts = []
    for number, payload in saved.items():
        part = raw[raw.total_rounds_played.eq(number)].copy() if not raw.empty else raw.copy()
        ids = part.event_id.tolist() if not part.empty else []
        if payload["source_ids_fingerprint"] != canonical_fingerprint(ids):
            raise ValueError("Spatial cache does not match source observation order")
        for column in LOCATION_COLUMNS:
            values = payload["locations"][column]
            if len(values) != len(part):
                raise ValueError("Incomplete spatial cache column")
            part[column] = values
        parts.append(part)
    states = pd.concat(parts, ignore_index=True) if parts else raw.copy()
    if not states.empty:
        states["place"] = states.region_id.map(lambda rid: region_label(rid, profile))
        states["zone"] = states.region_id.map(
            lambda rid: (
                region_site(rid, profile)
                or (region(profile, rid).kind if region(profile, rid) else "unknown")
            )
        )
    context = SpatialContext(
        observations,
        states,
        profile,
        [entry for payload in (saved_entries or {}).values() for entry in payload["entries"]],
    )
    return context


def read_context(db, analysis, round_number=None, profile=None, config=None):
    """Read only requested rounds. Never parses, writes, or uses historical payloads."""
    profile = selected_profile(analysis, profile)
    observations = _read_sources(db, analysis, round_number)
    if observations is None:
        return None
    key = spatial_key(analysis, profile)
    if db.get_stage_manifest(analysis.content_hash, "spatial", key) is None:
        return None
    saved = db.get_stage_rounds(analysis.content_hash, "spatial", key, round_number)
    expected = observations.clock.total_rounds_played.astype(int).tolist()
    if sorted(saved) != sorted(expected):
        return None
    entry_key = context_key(analysis, profile, config)
    if db.get_stage_manifest(analysis.content_hash, "entries", entry_key) is None:
        return None
    entry_rounds = db.get_stage_rounds(analysis.content_hash, "entries", entry_key, round_number)
    if sorted(entry_rounds) != sorted(expected):
        return None
    try:
        context = _restore_spatial(observations, saved, profile, entry_rounds)
    except (ValueError, KeyError, TypeError):
        return None
    # Cached analyses contain stable region IDs; presentation uses the current profile.
    from collections import Counter

    for entry in context.entries:
        for participant in entry["participants"]:
            item = region(profile, participant.get("from_region"))
            if item and participant.get("route_known"):
                participant["route"] = item.route_names.get(entry["site"], "Unknown")
        entry["routes"] = dict(Counter(p["route"] for p in entry["participants"]))
        for moment in ("ct_before", "ct_during"):
            for player in entry[moment]["players"]:
                player["place"] = region_label(player.get("region_id"), profile)
    from src.demos.coach_foundations import decode_foundation, foundation_key

    saved_foundations = db.get_stage_rounds(
        analysis.content_hash, "foundations", foundation_key(analysis), round_number
    )
    if sorted(saved_foundations) != sorted(expected):
        return None
    context.foundations = {n: decode_foundation(value)[0] for n, value in saved_foundations.items()}
    from functools import partial
    from src.demos.tactical_actions import actions_key, save_action_rounds
    action_key = actions_key(analysis, profile, config)
    context.tactical_actions = db.get_stage_rounds(analysis.content_hash, "tactical_actions", action_key, round_number)
    context.persist_tactical_actions = partial(save_action_rounds, db, analysis.content_hash, action_key)
    return context


def get_spatial_context(db, manager, analysis, round_number=None, profile=None, config=None):
    """Prepare missing stages; changing map semantics reuses stored source observations."""
    with _context_lock(db._db_path, analysis.content_hash):
        cached = read_context(db, analysis, round_number, profile, config)
        if cached is not None:
            _bind_viewer(cached, db, manager, analysis)
            return cached
        profile = selected_profile(analysis, profile)
        observations = _read_sources(db, analysis)
        stages = {}
        if observations is None:
            path = manager.analysis_path(analysis.stored_file_name, analysis.content_hash)
            if path is None:
                raise FileNotFoundError(
                    "Do przygotowania danych potrzebny jest oryginalny plik demo."
                )
            observations = extract_observations(analysis, path)
            payloads = _source_payloads(observations)
            stages["observations"] = (
                observations.cache_key,
                _manifest(
                    analysis,
                    observations.cache_key,
                    payloads,
                    diagnostics=observations.diagnostics,
                    schema_version=1,
                ),
                payloads,
            )
        loc_key = spatial_key(analysis, profile)
        loc_manifest = db.get_stage_manifest(analysis.content_hash, "spatial", loc_key)
        if loc_manifest:
            saved_locations = db.get_stage_rounds(analysis.content_hash, "spatial", loc_key)
            try:
                if sorted(saved_locations) != sorted(
                    observations.clock.total_rounds_played.astype(int)
                ):
                    raise ValueError("Incomplete spatial generation")
                context = _restore_spatial(observations, saved_locations, profile)
            except (ValueError, KeyError, TypeError):
                loc_manifest = None
        if not loc_manifest:
            context = enrich_spatial(observations, profile)
        from src.demos.site_entries import enrich_entries

        enrich_entries(context, analysis, config=config)
        key = context_key(analysis, profile, config)
        payloads = {}
        for n in observations.clock.total_rounds_played.astype(int):
            part = context.states
            part = part[part.total_rounds_played.eq(n)] if not part.empty else part
            rows = frame_records(part[list(LOCATION_COLUMNS)]) if not part.empty else []
            payloads[n] = {
                "source_ids_fingerprint": canonical_fingerprint(
                    part.event_id.tolist() if not part.empty else []
                ),
                "locations": {column: [row[column] for row in rows] for column in LOCATION_COLUMNS},
            }
        if not loc_manifest:
            stages["spatial"] = (
                loc_key,
                _manifest(
                    analysis,
                    loc_key,
                    payloads,
                    schema_version=2,
                    observations_key=observations.cache_key,
                    profile_fingerprint=profile.semantic_fingerprint if profile else None,
                ),
                payloads,
            )
        entry_payloads = {
            n: {"entries": [entry for entry in context.entries if entry["round"] == n]}
            for n in payloads
        }
        stages["entries"] = (
            key,
            _manifest(analysis, key, entry_payloads, schema_version=1, spatial_key=loc_key),
            entry_payloads,
        )
        from src.demos.coach_foundations import (
            build_foundations,
            foundation_key,
            foundation_payload,
        )

        fkey = foundation_key(analysis)
        saved_foundations = db.get_stage_rounds(analysis.content_hash, "foundations", fkey)
        if sorted(saved_foundations) != sorted(payloads):
            foundations, evidence = build_foundations(analysis, observations)
            foundation_rounds = {
                n: foundation_payload(value, evidence) for n, value in foundations.items()
            }
            stages["foundations"] = (
                fkey,
                _manifest(analysis, fkey, foundation_rounds, schema_version=1),
                foundation_rounds,
            )
        db.save_stages(analysis.content_hash, stages)
        context = read_context(db, analysis, round_number, profile, config)
        if context is not None:
            _bind_viewer(context, db, manager, analysis)
        return context


def _bind_viewer(context, db, manager, analysis):
    from src.demos.viewer_projectiles import get_round_projectiles

    context.load_projectiles = partial(
        get_round_projectiles, db, manager, analysis, context.observations.cache_key,
    )


def round_analysis(analysis, round_number):
    """Base IDs are stamped before slicing, keeping cross-round evidence stable."""
    from dataclasses import replace

    from src.demos.coach_data import build_coach_inputs

    base = build_coach_inputs(analysis)
    changes = {}
    for name, source in (
        ("rounds_df", "rounds"),
        ("kills_df", "kills"),
        ("damage_df", "damage"),
        ("bomb_events_df", "bombs"),
        ("player_blinds_df", "blinds"),
    ):
        frame = base.frames[source]
        changes[name] = (
            frame[frame.total_rounds_played.eq(round_number)]
            if "total_rounds_played" in frame
            else frame
        )
    return replace(analysis, **changes)
