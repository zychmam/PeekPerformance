"""Bomb stream coverage is specific to the event needed by each measurement."""

from src.models.tactical import Availability, Status

KNOWN = {Status.OBSERVED, Status.ABSENT}
CORE_EVENTS = ("bomb_planted", "bomb_defused", "bomb_exploded")


def event_coverage(record, name):
    # Older/synthetic contracts can supply only a diagnosed combined stream.
    # An explicit unknown event must never inherit a known combined status.
    fallback = record.availability.get("bombs", Availability(Status.UNKNOWN))
    return record.availability.get(name, fallback)


def event_known(record, name):
    return event_coverage(record, name).status in KNOWN


def combined_coverage(record):
    sources = [event_coverage(record, name) for name in CORE_EVENTS]
    if all(source.status in KNOWN for source in sources):
        return Availability(Status.OBSERVED if any(s.status == Status.OBSERVED for s in sources)
                            else Status.ABSENT)
    observed = any(source.status in {Status.OBSERVED, Status.PARTIAL} for source in sources)
    return Availability(Status.PARTIAL if observed else Status.UNKNOWN,
                        [f"{name}: {source.status}"
                         for name, source in zip(CORE_EVENTS, sources, strict=True)
                         if source.status not in KNOWN])
