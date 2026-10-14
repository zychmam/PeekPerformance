"""Normalize one round's enemy damage and kills into source-backed contacts."""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from src.demos.coach_foundations import FIREARMS
from src.demos.demo_analyzer import _UTILITY_WEAPONS
from src.demos.round_index import round_state_index
from src.models.tactical import Contact, PositionReference, Status, derived_id

CONTACT_DETECTOR_VERSION = 2


def _side(value) -> str | None:
    try:
        return {2: "T", 3: "CT"}.get(int(value))
    except (TypeError, ValueError):
        return None


def _player(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    player = str(value)
    return player if player not in {"", "0", "None", "nan", "<NA>"} else None


def _enemy_pair(event):
    row = event.data
    attacker, victim = _player(row.get("attacker_steamid")), _player(row.get("user_steamid"))
    a_side, v_side = _side(row.get("attacker_team_num")), _side(row.get("user_team_num"))
    if not attacker or not victim or attacker == victim or not a_side or not v_side or a_side == v_side:
        return None
    return event.tick, attacker, victim, a_side, v_side


def _modality(event):
    weapon = str(event.data.get("weapon") or "").removeprefix("weapon_")
    if weapon in FIREARMS:
        return "firearm"
    if weapon in _UTILITY_WEAPONS:
        return "utility"
    return "unknown"


def _first(contacts, predicate):
    matches = [contact for contact in contacts if predicate(contact)]
    if not matches:
        return []
    tick = min(contact.tick for contact in matches)
    return sorted(contact.id for contact in matches if contact.tick == tick)


def assign_first_contacts(round_tactics, evidence):
    """Refer to all tied first events; do not invent a same-tick order."""
    contacts = round_tactics.contacts
    def has_source(contact, source, modality=None):
        return any(
            evidence[eid].source == source
            and (modality is None or _modality(evidence[eid]) == modality)
            for eid in contact.evidence_ids
        )
    round_tactics.contact_references = {
        "first_enemy_damage": _first(contacts, lambda c: has_source(c, "damage")),
        "first_firearm_damage": _first(contacts, lambda c: has_source(c, "damage", "firearm")),
        "first_utility_damage": _first(contacts, lambda c: has_source(c, "damage", "utility")),
        "first_enemy_kill": _first(contacts, lambda c: has_source(c, "kills")),
        "first_firearm_contact": _first(contacts, lambda c: any(
            _modality(evidence[eid]) == "firearm" for eid in c.evidence_ids)),
        "first_utility_contact": _first(contacts, lambda c: any(
            _modality(evidence[eid]) == "utility" for eid in c.evidence_ids)),
    }
    for player in round_tactics.players:
        own = [c for c in contacts if player.player_id in {c.attacker_id, c.victim_id}]
        player.contact_ids = [c.id for c in own]
        player.contact_references = {
            "first_any": _first(own, lambda c: True),
            "first_dealt": _first(own, lambda c: c.attacker_id == player.player_id),
            "first_received": _first(own, lambda c: c.victim_id == player.player_id),
            "first_firearm": _first(own, lambda c: any(
                _modality(evidence[eid]) == "firearm" for eid in c.evidence_ids)),
            "first_utility": _first(own, lambda c: any(
                _modality(evidence[eid]) == "utility" for eid in c.evidence_ids)),
        }
        first = player.contact_references["first_any"]
        player.first_contact_id = first[0] if len(first) == 1 else None
        player.contact_status = (
            round_tactics.contacts_status if player.contact_ids
            else Status.UNKNOWN if round_tactics.contacts_status != Status.ABSENT
            else Status.ABSENT
        )


def _position(index, player_id, tick, *, max_age_ticks, max_gap_ticks, areas):
    # A state emitted at the event tick could describe its aftermath.
    sample = index.before(
        tick, player_id=player_id, max_age_ticks=max_age_ticks - 1,
        max_gap_ticks=max_gap_ticks,
    )
    if sample.row is None:
        return PositionReference(
            Status.UNKNOWN, sample_tick=sample.sample_tick,
            age_ticks=tick - sample.sample_tick if sample.sample_tick is not None else None,
        )
    eid = sample.row.get("event_id")
    if not eid:
        return PositionReference(Status.UNKNOWN)
    return PositionReference(
        Status.OBSERVED, str(eid), sample.sample_tick, tick - sample.sample_tick,
        areas.get(str(eid)),
    )


def build_round_contacts(round_tactics, evidence, *, tick_rate, config, areas=None,
                         state_index=None):
    """One pass over damage/kills, then indexed position lookups for each contact.

    Damage events at one tick for one ordered pair become one contact with summed
    actual HP loss. A kill at that exact tick/pair is linked to it; otherwise the
    kill becomes a kill-only contact with unknown HP. Source evidence is immutable.
    """
    areas = areas or {}
    freeze = round_tactics.freeze_end_tick
    if freeze is None:
        return [], Status.UNKNOWN
    source_events = [
        evidence[eid] for eid in round_tactics.event_ids
        if evidence[eid].source in {"damage", "kills"}
    ]
    index = state_index or round_state_index(round_tactics, evidence)
    groups = defaultdict(lambda: {"damage": [], "kills": []})
    for event in source_events:
        if event.source not in {"damage", "kills"} or event.tick < freeze:
            continue
        pair = _enemy_pair(event)
        if pair is None:
            continue
        if event.source == "damage":
            try:
                amount = float(event.data.get("enemy_damage") or 0)
            except (TypeError, ValueError):
                continue
            if not 0 < amount < float("inf"):
                continue
        groups[pair][event.source].append(event)
    age = max(1, round(tick_rate * config.max_sample_age_seconds))
    gap = max(1, round(tick_rate * config.max_sample_gap_seconds))
    contacts = []
    for (tick, attacker, victim, a_side, v_side), events in sorted(groups.items()):
        damages, kills = events["damage"], events["kills"]
        source = damages or kills
        refs = sorted({event.id for event in damages + kills})
        weapons = {str(event.data["weapon"]) for event in damages if event.data.get("weapon")}
        if not weapons:
            weapons = {str(event.data["weapon"]) for event in kills if event.data.get("weapon")}
        modalities = {_modality(event) for event in source}
        contacts.append(Contact(
            id=derived_id(round_tactics.number, "contact", *(event.id for event in source)),
            round_number=round_tactics.number,
            tick=tick,
            kind="damage" if damages else "kill_only",
            attacker_id=attacker,
            victim_id=victim,
            attacker_side=a_side,
            victim_side=v_side,
            weapon=next(iter(weapons)) if len(weapons) == 1 else None,
            actual_damage=sum(float(event.data["enemy_damage"]) for event in damages) if damages else None,
            attacker_position=_position(index, attacker, tick, max_age_ticks=age,
                                        max_gap_ticks=gap, areas=areas),
            victim_position=_position(index, victim, tick, max_age_ticks=age,
                                      max_gap_ticks=gap, areas=areas),
            evidence_ids=refs,
            status=Status.OBSERVED,
            modality=next(iter(modalities)) if len(modalities) == 1 else "mixed",
        ))
    complete = all(
        round_tactics.availability.get(name) is not None
        and round_tactics.availability[name].status in {Status.OBSERVED, Status.ABSENT}
        for name in ("damage", "kills")
    )
    if contacts:
        return contacts, Status.OBSERVED if complete else Status.PARTIAL
    return [], Status.ABSENT if complete else Status.UNKNOWN
