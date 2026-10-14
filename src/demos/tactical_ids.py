"""Deterministic action identity including labelled scalar dimensions."""

from src.models.observations import canonical_fingerprint
from src.models.tactical import derived_id


def action_id(kind, round_number, *parts):
    return derived_id(round_number, kind, canonical_fingerprint(list(parts)))
