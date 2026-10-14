"""Map-independent, evidence-linked chronology of one CS2 round."""

from __future__ import annotations

from collections import defaultdict

from src.models.tactical import RoundMoment, Status, derived_id

MOMENTS_VERSION = 1

_ORDER = {
    "round_start": 0, "early_throw": 1, "early_effect": 2,
    "first_contact": 3, "opening": 4, "refrag": 5,
    "kill": 6, "contact": 7, "alive_change": 8,
    "site_entry": 9, "bomb": 10, "round_end": 11,
}


def build_round_moments(record, evidence):
    """Source events are grouped only where their tick itself is shared."""
    number = record.number
    states = sorted(record.alive_states, key=lambda item: item.tick)
    state_at = {state.tick: state for state in states}
    result = []

    def append(kind, tick, *, end_tick=None, events=(), contacts=(), players=(),
               before=None, after=None, status=Status.OBSERVED):
        event_ids = list(dict.fromkeys(events))
        contact_ids = list(dict.fromkeys(contacts))
        source_ids = event_ids or contact_ids or [f"clock:{kind}:{tick}"]
        result.append(RoundMoment(
            derived_id(number, f"moment:{kind}", *source_ids), number, kind,
            int(tick), int(end_tick if end_tick is not None else tick),
            sorted(set(str(player) for player in players if player is not None)),
            event_ids, contact_ids, before.id if before else None,
            after.id if after else None, status,
        ))

    if record.freeze_end_tick is not None:
        start = state_at.get(record.freeze_end_tick)
        append("round_start", record.freeze_end_tick,
               events=start.evidence_ids if start else (), after=start,
               status=start.status if start else Status.PARTIAL)

    for kind, field in (("early_throw", "thrown_utility_ids"),
                        ("early_effect", "utility_ids")):
        ids = set(getattr(record.t_preparation, field)) | set(getattr(record.ct_setup, field))
        grouped = defaultdict(list)
        for eid in ids:
            if eid in evidence:
                grouped[evidence[eid].tick].append(eid)
        for tick, group in grouped.items():
            append(kind, tick, events=sorted(group),
                   players=(evidence[eid].data.get("user_steamid") for eid in group))

    grouped_contacts = defaultdict(list)
    for contact in record.contacts:
        grouped_contacts[contact.tick].append(contact)
    first_tick = min(grouped_contacts) if grouped_contacts else None
    opening = set(record.opening_kill_ids)
    replies = {link.response_kill_id for link in record.refrag_links}
    represented_kills = set()
    for tick, contacts in grouped_contacts.items():
        ids = list(dict.fromkeys(eid for contact in contacts for eid in contact.evidence_ids))
        kill_ids = {eid for eid in ids if evidence[eid].source == "kills"}
        represented_kills.update(kill_ids)
        kind = ("opening" if kill_ids & opening else "refrag" if kill_ids & replies
                else "first_contact" if tick == first_tick else "kill" if kill_ids
                else "contact")
        before = next((state for state in reversed(states) if state.tick < tick), None)
        after = state_at.get(tick)
        append(kind, tick, events=ids, contacts=(contact.id for contact in contacts),
               players=(pid for contact in contacts
                        for pid in (contact.attacker_id, contact.victim_id)),
               before=before, after=after,
               status=Status.OBSERVED if all(contact.status == Status.OBSERVED
                                             for contact in contacts) else Status.PARTIAL)

    # Friendly fire, suicide or an unknown attacker still changes global numbers.
    for state in states:
        ids = [eid for eid in record.event_ids if evidence[eid].source == "kills"
               and evidence[eid].tick == state.tick and eid not in represented_kills]
        if ids:
            before = next((item for item in reversed(states) if item.tick < state.tick), None)
            append("alive_change", state.tick, events=ids,
                   players=(evidence[eid].data.get("user_steamid") for eid in ids),
                   before=before, after=state, status=state.status)

    for entry in record.observed_entries:
        append("site_entry", entry.start_tick, end_tick=entry.end_tick,
               events=entry.evidence_ids, players=entry.participants, status=entry.status)

    grouped_bombs = defaultdict(list)
    for eid in record.bomb_event_ids:
        if (eid in evidence and
                (record.freeze_end_tick is None or evidence[eid].tick >= record.freeze_end_tick)):
            grouped_bombs[evidence[eid].tick].append(eid)
    for tick, ids in grouped_bombs.items():
        append("bomb", tick, events=sorted(set(ids)),
               players=(evidence[eid].data.get("user_steamid") for eid in ids))

    end_events = [eid for eid in record.bomb_event_ids
                  if eid in evidence and evidence[eid].tick == record.end_tick]
    append("round_end", record.end_tick, events=end_events,
           after=state_at.get(record.end_tick),
           status=Status.OBSERVED if end_events else Status.PARTIAL)
    return sorted(result, key=lambda item: (item.start_tick, _ORDER[item.kind], item.id))
