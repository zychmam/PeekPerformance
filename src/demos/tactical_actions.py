"""Versioned M4 pipeline and compact per-round storage, shared by all players."""

from dataclasses import asdict
from typing import get_type_hints

from src.demos.round_attacks import ATTACKS_VERSION, enrich_attacks, enrich_detached
from src.demos.round_defense import DEFENSE_VERSION, enrich_defense
from src.demos.round_fights import FIGHTS_VERSION, enrich_fights
from src.demos.round_movement import MOVEMENT_VERSION, MovementIndex, enrich_movement
from src.demos.round_resources import RoundResources
from src.demos.round_utility import UTILITY_CONTEXT_VERSION, enrich_utility
from src.models.observations import DetectorConfig, canonical_fingerprint
from src.models.tactical import TACTICAL_SCHEMA_VERSION, RoundTactics, _decode

TACTICAL_ACTIONS_VERSION = 3
ACTION_FIELDS = (
    "movement_status",
    "region_stays",
    "region_transitions",
    "movement_gaps",
    "utility_context_status",
    "utility_contexts",
    "fights_status",
    "fights",
    "attacks_status",
    "attacks",
    "t_pressure",
    "ct_activity",
    "ct_sectors_before_contact",
    "rotations_status",
    "rotations",
    "rotation_eligibility",
    "retake",
    "tactical_version",
)
VERSIONS = {
    "actions": TACTICAL_ACTIONS_VERSION,
    "movement": MOVEMENT_VERSION,
    "utility": UTILITY_CONTEXT_VERSION,
    "fights": FIGHTS_VERSION,
    "attacks": ATTACKS_VERSION,
    "defense": DEFENSE_VERSION,
}


def enrich_actions(record, evidence, profile, *, tick_rate, config, state_index, cached=None):
    if cached is not None:
        restore_actions(record, cached)
        return
    enrich_movement(
        record, evidence, profile, tick_rate=tick_rate, config=config, state_index=state_index
    )
    movement_index = MovementIndex(record)
    enrich_utility(record, evidence, profile, tick_rate=tick_rate, state_index=state_index)
    resources = RoundResources(record, evidence, state_index, tick_rate=tick_rate, config=config)
    enrich_fights(record, evidence, profile, tick_rate=tick_rate, resources=resources)
    enrich_attacks(
        record,
        evidence,
        profile,
        tick_rate=tick_rate,
        movements=movement_index,
        state_index=state_index,
    )
    for attack in record.attacks:
        attack.before = resources.at(max(record.freeze_end_tick, attack.episode.start_tick - 1))
        attack.after = resources.at(attack.episode.end_tick)
    enrich_detached(
        record,
        evidence,
        profile,
        tick_rate=tick_rate,
        movements=movement_index,
        state_index=state_index,
    )
    enrich_defense(
        record,
        evidence,
        profile,
        tick_rate=tick_rate,
        movements=movement_index,
        state_index=state_index,
    )
    record.tactical_version = TACTICAL_ACTIONS_VERSION


def action_payload(record):
    # No source trajectories, evidence table or generated prose.
    values = asdict(record)
    return {
        "round_number": record.number,
        "versions": VERSIONS,
        "schema_version": TACTICAL_SCHEMA_VERSION,
        "result": {name: values[name] for name in ACTION_FIELDS},
    }


def restore_actions(record, payload):
    if (
        payload.get("round_number") != record.number
        or payload.get("versions") != VERSIONS
        or payload.get("schema_version") != TACTICAL_SCHEMA_VERSION
        or set(payload.get("result", {})) != set(ACTION_FIELDS)
    ):
        raise ValueError("Incompatible tactical action cache")
    hints = get_type_hints(RoundTactics)
    for name, value in payload["result"].items():
        setattr(record, name, _decode(hints[name], value))


def actions_key(analysis, profile=None, config=None):
    from src.demos.coach_foundations import foundation_key
    from src.demos.round_alive import ALIVE_DETECTOR_VERSION
    from src.demos.round_contacts import CONTACT_DETECTOR_VERSION
    from src.demos.round_refrags import REFRAG_DETECTOR_VERSION
    from src.demos.spatial_service import context_key

    return canonical_fingerprint(
        {
            "context": context_key(analysis, profile, config),
            "foundations": foundation_key(analysis),
            "versions": VERSIONS,
            "schema": TACTICAL_SCHEMA_VERSION,
            "contacts": CONTACT_DETECTOR_VERSION,
            "alive": ALIVE_DETECTOR_VERSION,
            "refrags": REFRAG_DETECTOR_VERSION,
            "config": (config or DetectorConfig()).fingerprint,
        }
    )


def save_action_rounds(db, demo_id, key, records):
    from src.demos.spatial_service import _context_lock

    # Read/merge/publish under the existing demo lock, preserving other rounds.
    with _context_lock(db._db_path, demo_id):
        saved = db.get_stage_rounds(demo_id, "tactical_actions", key)
        saved.update({record.number: action_payload(record) for record in records})
        manifest = {
            "demo_id": demo_id,
            "cache_key": key,
            "round_numbers": sorted(saved),
            "versions": VERSIONS,
            "schema_version": TACTICAL_SCHEMA_VERSION,
        }
        db.save_stages(demo_id, {"tactical_actions": (key, manifest, saved)})
