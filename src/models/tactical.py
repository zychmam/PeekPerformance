"""R1 contract: observations, tactical episodes and two separate report scopes."""

from __future__ import annotations

import types
from hashlib import sha256
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from enum import StrEnum
from typing import get_args, get_origin, get_type_hints

TACTICAL_SCHEMA_VERSION = 10


class Status(StrEnum):
    OBSERVED = "observed"
    ABSENT = "verified_absent"
    PARTIAL = "partial"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    NOT_EVALUATED = "not_evaluated"


@dataclass
class Availability:
    status: Status
    reasons: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


@dataclass
class Evidence:
    id: str
    source: str
    round_number: int
    tick: int
    seconds: float | None
    data: dict


@dataclass
class Finding:
    """A claim; interpretation and uncertainty are explicit, not a numeric score."""
    text: str
    kind: str  # observation / interpretation
    evidence_ids: list[str]
    certainty: str = "limited"  # confirmed / limited
    limitations: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.kind not in {"observation", "interpretation"}:
            raise ValueError("Unknown finding kind")
        if not self.evidence_ids:
            raise ValueError("A match claim requires evidence")


@dataclass
class Episode:
    id: str
    kind: str
    start_tick: int
    end_tick: int
    participants: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    related_ids: list[str] = field(default_factory=list)
    status: Status = Status.NOT_EVALUATED
    area: str | None = None

    def __post_init__(self):
        if self.end_tick < self.start_tick:
            raise ValueError("Episode ends before it starts")


@dataclass
class SetupSnapshot:
    seconds: float
    tick: int
    status: Status
    players: list[dict] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    missing_players: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Movement:
    player_id: str
    from_area: str
    to_area: str
    start_tick: int
    arrival_tick: int
    confirmed_tick: int
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class EarlyUtility:
    player_id: str | None
    kind: str
    tick: int
    seconds: float
    area: str | None
    position: dict
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class Preparation:
    status: Status = Status.NOT_EVALUATED
    start_tick: int | None = None
    end_tick: int | None = None
    ten_second_tick: int | None = None
    formation: str | None = None
    tempo: str | None = None
    target_sequence: list[str] = field(default_factory=list)
    snapshot_ids: list[str] = field(default_factory=list)
    utility_ids: list[str] = field(default_factory=list)
    activity_ids: list[str] = field(default_factory=list)
    separated_player_ids: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    snapshots: list[SetupSnapshot] = field(default_factory=list)
    movements: list[Movement] = field(default_factory=list)
    utility: list[EarlyUtility] = field(default_factory=list)
    movement_status: Status = Status.NOT_EVALUATED
    utility_status: Status = Status.NOT_EVALUATED
    interpretation_status: Status = Status.NOT_EVALUATED
    orientation: dict[str, int] = field(default_factory=dict)
    orientation_tick: int | None = None
    bomb_area: str | None = None
    activity: str | None = None
    first_site_presence_seconds: float | None = None
    setup_before_contact: SetupSnapshot | None = None
    thrown_utility_ids: list[str] = field(default_factory=list)
    utility_windows: dict = field(default_factory=dict)


@dataclass
class SourceQuality:
    read_status: str  # ok / not_listed / unsupported / error / not_loaded
    availability: Availability
    rows: int = 0
    fields: dict[str, str] = field(default_factory=dict)


@dataclass
class EquipmentObservation:
    player_id: str
    tick: int
    team_num: int | None
    inventory: dict[str, int] | None
    active_weapon: str | None
    armor: int | None
    helmet: bool | None
    defuse_kit: bool | None
    economy: dict
    evidence_ids: list[str]


@dataclass
class ContactReference:
    tick: int | None = None
    kind: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    status: Status = Status.UNKNOWN


def derived_id(round_number: int, kind: str, *source_ids: str) -> str:
    """Stable round-local identity based on canonical source IDs, never row order."""
    if not source_ids or not all(source_ids):
        raise ValueError("Derived identity requires source IDs")
    digest = sha256("\x00".join(sorted(source_ids)).encode()).hexdigest()[:16]
    return f"r{round_number}:{kind}:{digest}"


@dataclass
class PositionReference:
    """A sampled position at or before an event; missing/stale has no evidence ID."""

    status: Status
    evidence_id: str | None = None
    sample_tick: int | None = None
    age_ticks: int | None = None
    area: str | None = None


@dataclass
class Contact:
    id: str
    round_number: int
    tick: int
    kind: str  # damage / kill_only; utility/firearm is classified separately
    attacker_id: str
    victim_id: str
    attacker_side: str
    victim_side: str
    weapon: str | None = None
    actual_damage: float | None = None
    attacker_position: PositionReference = field(default_factory=lambda: PositionReference(Status.UNKNOWN))
    victim_position: PositionReference = field(default_factory=lambda: PositionReference(Status.UNKNOWN))
    evidence_ids: list[str] = field(default_factory=list)
    status: Status = Status.NOT_EVALUATED
    modality: str = "unknown"  # firearm / utility / mixed / unknown


@dataclass
class RefragLink:
    id: str
    round_number: int
    death_id: str  # canonical kill evidence ID
    response_kill_id: str  # canonical kill evidence ID
    delay_ticks: int
    observable_window_ticks: int
    evidence_ids: list[str]
    status: Status = Status.NOT_EVALUATED


@dataclass
class AliveState:
    id: str
    round_number: int
    tick: int
    t_alive: int | None
    ct_alive: int | None
    alive_ids: list[str] = field(default_factory=list)
    dead_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    status: Status = Status.NOT_EVALUATED


@dataclass
class RoundMoment:
    id: str
    round_number: int
    kind: str
    start_tick: int
    end_tick: int
    player_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    contact_ids: list[str] = field(default_factory=list)
    alive_before_id: str | None = None
    alive_after_id: str | None = None
    status: Status = Status.NOT_EVALUATED

    def __post_init__(self):
        if self.end_tick < self.start_tick:
            raise ValueError("Moment ends before it starts")


@dataclass
class RoundFoundation:
    demo_id: str
    round_number: int
    source_fingerprint: str
    clock: dict
    schema_version: int = 2
    equipment_start: list[EquipmentObservation] = field(default_factory=list)
    equipment_changes: list[EquipmentObservation] = field(default_factory=list)
    bomb_event_ids: list[str] = field(default_factory=list)
    shot_event_ids: list[str] = field(default_factory=list)
    utility_lifecycle_ids: list[str] = field(default_factory=list)
    thrown_utility_ids: list[str] = field(default_factory=list)
    contact_references: dict[str, ContactReference] = field(default_factory=dict)
    setup_before_contact: dict[str, SetupSnapshot] = field(default_factory=dict)
    source_quality: dict[str, SourceQuality] = field(default_factory=dict)
    equipment_coverage: dict = field(default_factory=dict)


@dataclass
class Fight:
    episode: Episode
    area: str | None = None
    opening_kill_id: str | None = None
    round_opening: bool | None = None
    response_window_end: int | None = None
    utility_ids: list[str] = field(default_factory=list)
    kill_ids: list[str] = field(default_factory=list)
    damage_ids: list[str] = field(default_factory=list)
    # Pairs refer to the teammate death and the killing of that exact killer.
    refrags: list[dict] = field(default_factory=list)
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)
    space_changes: list[Finding] = field(default_factory=list)
    contact_ids: list[str] = field(default_factory=list)
    opening_kill_ids: list[str] = field(default_factory=list)
    utility_context_ids: list[str] = field(default_factory=list)
    utility_effect_ids: list[str] = field(default_factory=list)


@dataclass
class Attack:
    episode: Episode
    target_site: str | None = None
    fight_ids: list[str] = field(default_factory=list)
    entry_ids: list[str] = field(default_factory=list)
    plant_id: str | None = None
    outcome: str | None = None  # stopped / withdrawn / entered / planted / unknown
    alive_t_at_start: int | None = None
    main_group: list[str] = field(default_factory=list)
    detached_players: list[str] = field(default_factory=list)
    previous_attack_id: str | None = None
    start_seconds: float | None = None
    first_entry_tick: int | None = None
    entry_spread_seconds: float | None = None
    pauses_seconds: float = 0.0
    region_hold_seconds: float = 0.0
    tempo_reference_player_id: str | None = None
    utility_context_ids: list[str] = field(default_factory=list)
    detached_actions: list[dict] = field(default_factory=list)
    entry_outcome: str = "unknown"
    plant_outcome: str = "unknown"
    round_outcome: str | None = None
    start_basis: str | None = None
    end_reason: str | None = None
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.outcome not in {None, "stopped", "withdrawn", "entered", "planted", "unknown"}:
            raise ValueError("Unknown attack outcome")


@dataclass
class Rotation:
    episode: Episode
    player_id: str
    from_area: str | None = None
    to_area: str | None = None
    information_event_id: str | None = None
    trigger_kind: str | None = None  # damage_contact / spotted / plant; no voice inference
    arrival_tick: int | None = None
    reaction_seconds: float | None = None
    already_moving: bool | None = None
    travel_seconds: float | None = None
    outcome: str = "unknown"
    target_site: str | None = None


@dataclass
class Retake:
    status: Status = Status.NOT_EVALUATED
    episode: Episode | None = None
    plant_id: str | None = None
    outcome: str | None = None  # won / lost / no_attempt / unknown
    defuse_id: str | None = None

    def __post_init__(self):
        if self.outcome not in {None, "won", "lost", "no_attempt", "unknown"}:
            raise ValueError("Unknown retake outcome")


@dataclass
class PlayerRound:
    player_id: str
    team_id: str | None
    side: str | None
    status: Status = Status.NOT_EVALUATED
    first_contact_id: str | None = None
    episode_ids: list[str] = field(default_factory=list)
    utility_ids: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    contact_ids: list[str] = field(default_factory=list)
    contact_references: dict[str, list[str]] = field(default_factory=dict)
    contact_status: Status = Status.NOT_EVALUATED


@dataclass
class RegionStay:
    id: str
    player_id: str
    side: str | None
    area: str | None
    start_tick: int
    end_tick: int
    status: Status
    end_reason: str
    evidence_ids: list[str] = field(default_factory=list)
    previous_area: str | None = None
    next_area: str | None = None
    defense_sector: str | None = None
    forward: bool | None = None


@dataclass
class RegionTransition:
    player_id: str
    from_area: str
    to_area: str
    departure_tick: int
    arrival_tick: int
    evidence_ids: list[str] = field(default_factory=list)


@dataclass
class UtilityContext:
    id: str
    player_id: str | None
    side: str | None
    kind: str
    throw_tick: int | None = None
    origin_area: str | None = None
    effect_tick: int | None = None
    effect_area: str | None = None
    end_tick: int | None = None
    match_status: str = "unknown"
    end_source: str = "unknown"
    evidence_ids: list[str] = field(default_factory=list)
    effect_ids: list[str] = field(default_factory=list)
    candidates: list[str] = field(default_factory=list)
    origin_position: dict = field(default_factory=dict)
    effect_position: dict = field(default_factory=dict)


@dataclass
class RoundTactics:
    number: int
    start_tick: int
    end_tick: int
    freeze_end_tick: int | None
    teams_by_side: dict[str, str | None]
    winner_side: str | None
    winner_team_id: str | None
    end_reason: str | None
    availability: dict[str, Availability]
    event_ids: list[str] = field(default_factory=list)
    t_preparation: Preparation = field(default_factory=Preparation)
    ct_setup: Preparation = field(default_factory=Preparation)
    fights_status: Status = Status.NOT_EVALUATED
    fights: list[Fight] = field(default_factory=list)
    attacks_status: Status = Status.NOT_EVALUATED
    attacks: list[Attack] = field(default_factory=list)
    # Existing detector crossings are evidence, not necessarily attack attempts.
    observed_entries: list[Episode] = field(default_factory=list)
    rotations_status: Status = Status.NOT_EVALUATED
    rotations: list[Rotation] = field(default_factory=list)
    rotation_eligibility: list[dict] = field(default_factory=list)
    bomb_event_ids: list[str] = field(default_factory=list)
    retake: Retake = field(default_factory=Retake)
    team_findings: list[Finding] = field(default_factory=list)
    players: list[PlayerRound] = field(default_factory=list)
    capabilities: dict[str, Availability] = field(default_factory=dict)
    foundation: RoundFoundation | None = None
    contacts_status: Status = Status.NOT_EVALUATED
    contacts: list[Contact] = field(default_factory=list)
    contact_references: dict[str, list[str]] = field(default_factory=dict)
    alive_status: Status = Status.NOT_EVALUATED
    opening_status: Status = Status.NOT_EVALUATED
    opening_kill_ids: list[str] = field(default_factory=list)
    refrag_links: list[RefragLink] = field(default_factory=list)
    refrags_status: Status = Status.NOT_EVALUATED
    opening_window_end_tick: int | None = None
    opening_window_kill_ids: list[str] = field(default_factory=list)
    opening_response_status: Status = Status.NOT_EVALUATED
    alive_states: list[AliveState] = field(default_factory=list)
    moments: list[RoundMoment] = field(default_factory=list)
    movement_status: Status = Status.NOT_EVALUATED
    region_stays: list[RegionStay] = field(default_factory=list)
    region_transitions: list[RegionTransition] = field(default_factory=list)
    movement_gaps: list[dict] = field(default_factory=list)
    utility_context_status: Status = Status.NOT_EVALUATED
    utility_contexts: list[UtilityContext] = field(default_factory=list)
    ct_activity: list[Episode] = field(default_factory=list)
    ct_sectors_before_contact: dict = field(default_factory=dict)
    tactical_version: int = 0
    t_pressure: list[Episode] = field(default_factory=list)


@dataclass
class TacticalMatch:
    demo_id: str
    map_name: str
    input_version: int
    rounds: list[RoundTactics]
    evidence: dict[str, Evidence]
    teams: dict[str, list[str]]
    schema_version: int = TACTICAL_SCHEMA_VERSION
    parameters: dict = field(default_factory=lambda: {
        "tick_rate_assumption": 64, "early_seconds": 15,
        "response_seconds": 5, "entry_wave_seconds": 8,
    })

    def to_dict(self) -> dict:
        """JSON-compatible contract; no pandas objects, NaN or derived text needed."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> TacticalMatch:
        if data.get("schema_version") != TACTICAL_SCHEMA_VERSION:
            raise ValueError("Unsupported tactical schema version")
        result = _decode(cls, {**data, "schema_version": TACTICAL_SCHEMA_VERSION})
        result.validate()
        return result

    def validate(self) -> None:
        if len({r.number for r in self.rounds}) != len(self.rounds):
            raise ValueError("Duplicate round identity")
        derived_ids: set[str] = set()
        for rnd in self.rounds:
            if rnd.end_tick < rnd.start_tick:
                raise ValueError("Invalid round interval")
            if rnd.freeze_end_tick is not None and not (
                rnd.start_tick <= rnd.freeze_end_tick <= rnd.end_tick
            ):
                raise ValueError("Freeze-end outside round")
            for eid in rnd.event_ids:
                ev = self.evidence[eid]
                if ev.round_number != rnd.number or not rnd.start_tick <= ev.tick <= rnd.end_tick:
                    raise ValueError("Evidence outside its round")
                if ev.data.get("evidence_ids"):
                    _validate_references(ev, self.evidence, rnd.number)
            for entry in rnd.observed_entries:
                if not entry.evidence_ids:
                    raise ValueError("Entry without source samples")
                for eid in entry.evidence_ids:
                    if self.evidence[eid].round_number != rnd.number:
                        raise ValueError("Cross-round episode evidence")
            contacts = {item.id: item for item in rnd.contacts}
            for stay in rnd.region_stays:
                _validate_tick(stay.start_tick, rnd)
                _validate_tick(stay.end_tick, rnd)
                if stay.end_tick < stay.start_tick or not stay.evidence_ids:
                    raise ValueError("Invalid observed region interval")
            for transition in rnd.region_transitions:
                _validate_tick(transition.departure_tick, rnd)
                _validate_tick(transition.arrival_tick, rnd)
                if transition.departure_tick > transition.arrival_tick:
                    raise ValueError("Invalid movement interval")
            for episode in ([f.episode for f in rnd.fights] + [a.episode for a in rnd.attacks]
                            + [r.episode for r in rnd.rotations] + rnd.ct_activity + rnd.t_pressure
                            + ([rnd.retake.episode] if rnd.retake.episode else [])):
                _validate_tick(episode.start_tick, rnd)
                _validate_tick(episode.end_tick, rnd)
            for fight in rnd.fights:
                if any(ref not in contacts for ref in fight.contact_ids):
                    raise ValueError("Unknown fight contact")
            for utility in rnd.utility_contexts:
                for tick in (utility.throw_tick, utility.effect_tick, utility.end_tick):
                    if tick is not None:
                        _validate_tick(tick, rnd)
            alive = {item.id: item for item in rnd.alive_states}
            for group in (rnd.contacts, rnd.refrag_links, rnd.alive_states, rnd.moments):
                for item in group:
                    if item.id in derived_ids:
                        raise ValueError("Duplicate derived identity")
                    derived_ids.add(item.id)
                    if item.round_number != rnd.number:
                        raise ValueError("Derived fact belongs to another round")
            for contact in rnd.contacts:
                _validate_tick(contact.tick, rnd)
                if contact.kind not in {"damage", "kill_only"} or contact.attacker_side == contact.victim_side:
                    raise ValueError("Invalid enemy contact")
                if contact.modality not in {"firearm", "utility", "mixed", "unknown"}:
                    raise ValueError("Invalid contact modality")
                if contact.attacker_side not in {"T", "CT"} or contact.victim_side not in {"T", "CT"}:
                    raise ValueError("Unknown contact side")
                if contact.actual_damage is not None and contact.actual_damage < 0:
                    raise ValueError("Negative contact damage")
                if contact.status == Status.OBSERVED and not contact.evidence_ids:
                    raise ValueError("Observed contact requires evidence")
                if contact.status == Status.OBSERVED and not any(
                    (event := self.evidence.get(eid)) is not None
                    and event.tick == contact.tick
                    and event.source == ("damage" if contact.kind == "damage" else "kills")
                    for eid in contact.evidence_ids
                ):
                    raise ValueError("Contact lacks matching damage or kill evidence")
                for position in (contact.attacker_position, contact.victim_position):
                    _validate_position(position, contact.tick, rnd, self.evidence)
            for link in rnd.refrag_links:
                death = self.evidence.get(link.death_id)
                response = self.evidence.get(link.response_kill_id)
                if not death or not response or any(
                    event.source != "kills" or event.round_number != rnd.number
                    for event in (death, response)
                ):
                    raise ValueError("Refrag requires two kills from one round")
                if not death.tick < response.tick or link.delay_ticks != response.tick - death.tick:
                    raise ValueError("Invalid refrag chronology")
                if link.observable_window_ticks < link.delay_ticks or response.tick > rnd.end_tick:
                    raise ValueError("Invalid refrag window")
                if (str(death.data.get("attacker_steamid")) != str(response.data.get("user_steamid"))
                        or str(death.data.get("user_team_num")) != str(response.data.get("attacker_team_num"))):
                    raise ValueError("Refrag must kill the teammate's exact killer")
                if not {link.death_id, link.response_kill_id}.issubset(link.evidence_ids):
                    raise ValueError("Refrag lacks source evidence")
                if (str(death.data.get("user_steamid")) == str(response.data.get("attacker_steamid"))
                        or str(death.data.get("user_team_num")) != str(response.data.get("attacker_team_num"))):
                    raise ValueError("Refrag response must come from a teammate")
            if rnd.opening_window_end_tick is not None:
                _validate_tick(rnd.opening_window_end_tick, rnd)
                opening_ticks = {self.evidence[eid].tick for eid in rnd.opening_kill_ids}
                if not opening_ticks or rnd.opening_window_end_tick < min(opening_ticks):
                    raise ValueError("Invalid opening response window")
            for eid in rnd.opening_window_kill_ids:
                event = self.evidence.get(eid)
                if (event is None or event.round_number != rnd.number or event.source != "kills"
                        or rnd.opening_window_end_tick is None
                        or not min(self.evidence[ref].tick for ref in rnd.opening_kill_ids)
                        < event.tick <= rnd.opening_window_end_tick):
                    raise ValueError("Invalid opening response kill")
            for state in rnd.alive_states:
                _validate_tick(state.tick, rnd)
                if state.t_alive is not None and state.t_alive < 0:
                    raise ValueError("Invalid T alive count")
                if state.ct_alive is not None and state.ct_alive < 0:
                    raise ValueError("Invalid CT alive count")
                if set(state.alive_ids) & set(state.dead_ids):
                    raise ValueError("Player cannot be alive and dead")
                if state.status == Status.OBSERVED and not state.evidence_ids:
                    raise ValueError("Observed alive state requires evidence")
            for moment in rnd.moments:
                _validate_tick(moment.start_tick, rnd)
                _validate_tick(moment.end_tick, rnd)
                if any(ref not in contacts for ref in moment.contact_ids):
                    raise ValueError("Unknown contact in moment")
                if any(ref is not None and ref not in alive for ref in (moment.alive_before_id, moment.alive_after_id)):
                    raise ValueError("Unknown alive state in moment")
                if moment.status == Status.OBSERVED and not (
                    moment.event_ids or moment.contact_ids or moment.alive_before_id or moment.alive_after_id
                ):
                    raise ValueError("Observed moment requires a source")
            for player in rnd.players:
                if player.first_contact_id is not None and player.first_contact_id not in contacts:
                    raise ValueError("Unknown player first contact")
                if any(ref not in contacts for ref in player.contact_ids):
                    raise ValueError("Unknown player contact")
                if any(ref not in contacts for refs in player.contact_references.values() for ref in refs):
                    raise ValueError("Unknown player contact reference")
            if any(ref not in contacts for refs in rnd.contact_references.values() for ref in refs):
                raise ValueError("Unknown round contact reference")
            for eid in rnd.opening_kill_ids:
                event = self.evidence.get(eid)
                if event is None or event.round_number != rnd.number or event.source != "kills":
                    raise ValueError("Invalid opening kill reference")
            if rnd.opening_status == Status.OBSERVED and not rnd.opening_kill_ids:
                raise ValueError("Observed opening requires a kill")
            _validate_references(rnd, self.evidence, rnd.number)


def _validate_tick(tick: int, rnd: RoundTactics) -> None:
    if not rnd.start_tick <= tick <= rnd.end_tick:
        raise ValueError("Derived fact outside its round")


def _validate_position(position: PositionReference, event_tick: int, rnd: RoundTactics,
                       evidence: dict[str, Evidence]) -> None:
    if position.status == Status.OBSERVED:
        sample = evidence.get(position.evidence_id)
        if (sample is None or sample.source != "states" or sample.round_number != rnd.number
                or sample.tick != position.sample_tick or sample.tick > event_tick
                or position.age_ticks != event_tick - sample.tick):
            raise ValueError("Invalid contact position sample")
    elif position.evidence_id is not None or position.area is not None:
        raise ValueError("Unavailable position cannot carry a sample or area")
    if position.sample_tick is not None and position.sample_tick > event_tick:
        raise ValueError("Future contact position sample")


def _decode(annotation, value):
    """Rehydrate nested dataclasses and enums without accepting executable input."""
    origin = get_origin(annotation)
    if origin is types.UnionType:
        if value is None and type(None) in get_args(annotation):
            return None
        return _decode(next(t for t in get_args(annotation) if t is not type(None)), value)
    if origin is list:
        return [_decode(get_args(annotation)[0], item) for item in value]
    if origin is dict:
        args = get_args(annotation)
        return {key: _decode(args[1], item) for key, item in value.items()} if args else value
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        return annotation(value)
    if is_dataclass(annotation):
        hints = get_type_hints(annotation)
        if set(value) - set(hints):
            raise ValueError("Unknown schema fields")
        return annotation(**{key: _decode(hints[key], item) for key, item in value.items()})
    return value


def _validate_references(obj, evidence: dict[str, Evidence], round_number: int):
    evidence_lists = {"event_ids", "evidence_ids", "snapshot_ids", "utility_ids",
                      "activity_ids", "kill_ids", "damage_ids", "bomb_event_ids",
                      "shot_event_ids", "utility_lifecycle_ids", "thrown_utility_ids",
                      "opening_kill_ids", "opening_window_kill_ids"}
    evidence_lists.update({"effect_ids", "utility_effect_ids"})
    evidence_single = {"information_event_id", "opening_kill_id",
                       "plant_id", "defuse_id"}
    if is_dataclass(obj):
        if (isinstance(obj, Episode) and obj.status in {Status.OBSERVED, Status.PARTIAL}
                and not obj.evidence_ids):
            raise ValueError("Observed episode requires evidence")
        for item in fields(obj):
            value = getattr(obj, item.name)
            refs = value if item.name in evidence_lists else (
                [value] if item.name in evidence_single and value is not None else []
            )
            for ref in refs:
                if ref not in evidence or evidence[ref].round_number != round_number:
                    raise ValueError("Unknown or cross-round evidence reference")
            _validate_references(value, evidence, round_number)
    elif isinstance(obj, list):
        for item in obj:
            _validate_references(item, evidence, round_number)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            refs = value if key in evidence_lists else (
                [value] if key in evidence_single and value is not None else []
            )
            for ref in refs:
                if ref not in evidence or evidence[ref].round_number != round_number:
                    raise ValueError("Unknown or cross-round evidence reference")
            _validate_references(value, evidence, round_number)
