"""Profile-driven observed site crossings; not inferred attack attempts."""

from collections import Counter

import pandas as pd

from src.maps.resolver import entry_route, region_label, region_site, support_sites
from src.models.observations import DetectorConfig, RoundClock

ENTRY_VERSION = 3


def _sample(states, tick, tick_rate=64):
    part = states[states.tick.between(tick - tick_rate, tick)]
    return part[part.tick.eq(part.tick.max())] if not part.empty else part


def _defence(states, roster, tick, site, profile, tick_rate):
    sample = _sample(states, tick, tick_rate)
    ct = sample[sample.team_num.eq(3) & sample.is_alive.eq(True)]
    on_site = ct[ct.region_id.map(lambda rid: region_site(rid, profile) == site)]
    support = ct[ct.region_id.map(lambda rid: site in support_sites(rid, profile))]
    expected = set(roster[roster.team_num.eq(3)].steamid.astype(str)) if not roster.empty else set()
    observed = set(sample[sample.team_num.eq(3)].steamid.astype(str))
    known = sample[sample.steamid.astype(str).isin(expected)]
    complete = (
        bool(expected)
        and expected.issubset(observed)
        and known.is_alive.notna().all()
        and known[known.is_alive.eq(True)].location_status.eq("observed").all()
    )
    return {
        "requested_tick": tick,
        "sample_tick": int(sample.tick.max()) if not sample.empty else None,
        "complete": bool(complete),
        "observed_ct": len(observed),
        "site_count": len(on_site),
        "support_count": len(support),
        "players": [
            {
                "steamid": str(r.steamid),
                "region_id": r.region_id,
                "place": region_label(r.region_id, profile),
                "group": "site"
                if region_site(r.region_id, profile) == site
                else "support"
                if site in support_sites(r.region_id, profile)
                else "other",
            }
            for r in ct.itertuples()
        ],
    }


def detect_entries(context, analysis, *, config=None) -> list[dict]:
    """Group confirmed crossings in fixed 8 s windows; retain solo entries.

    Confirmation requires >= 0.5 s observed alive in the site, with no sample
    gap above 2 s. One player's first crossing per round/site is counted once.
    Post-plant movement is excluded when a plant event is available.
    """
    config = config or DetectorConfig()
    profile = context.profile
    if profile is None or not profile.supports("site_boundaries"):
        return []
    results = []
    required = {
        "steamid",
        "tick",
        "team_num",
        "is_alive",
        "last_place_name",
        "total_rounds_played",
        "seconds",
    }
    if not required.issubset(context.states):
        return results
    for clock in context.clock.itertuples():
        if pd.isna(clock.freeze_tick):
            continue
        round_clock = RoundClock.from_row(clock._asdict())
        tick_rate = round_clock.tick_rate
        max_gap = round_clock.ticks(config.max_sample_gap_seconds)
        group_ticks = round_clock.ticks(config.entry_group_seconds)
        confirmation_ticks = round_clock.ticks(config.entry_confirmation_seconds)
        rnd = int(clock.total_rounds_played)
        states = context.states[context.states.total_rounds_played.eq(rnd)].copy()
        if states.empty:
            continue
        states = states.sort_values("tick", kind="stable")
        plants = analysis.bomb_events_df
        plant_tick = None
        if {"event", "total_rounds_played", "tick"}.issubset(plants):
            plant = plants[plants.total_rounds_played.eq(rnd) & plants.event.eq("bomb_planted")]
            if not plant.empty:
                plant_tick = int(plant.tick.min())
        crosses = []
        for sid, samples in states.groupby("steamid", sort=True):
            records = list(samples.itertuples())
            seen = set()
            for index in range(1, len(records)):
                previous, current = records[index - 1], records[index]
                site = region_site(current.region_id, profile)
                if (
                    not site
                    or site in seen
                    or current.team_num != 2
                    or pd.isna(current.is_alive)
                    or not current.is_alive
                    or pd.isna(previous.is_alive)
                    or not previous.is_alive
                    or previous.team_num != 2
                    or current.region_id == previous.region_id
                    or not 0 < current.tick - previous.tick <= max_gap
                    or current.tick < clock.freeze_tick
                    or (plant_tick is not None and current.tick >= plant_tick)
                ):
                    continue
                confirmed = None
                last_tick = current.tick
                for following in records[index + 1 :]:
                    if (
                        following.tick - last_tick > max_gap
                        or pd.isna(following.is_alive)
                        or not following.is_alive
                        or following.team_num != 2
                        or following.region_id != current.region_id
                    ):
                        break
                    if following.tick - current.tick >= confirmation_ticks:
                        confirmed = following.tick
                        break
                    last_tick = following.tick
                if confirmed is None:
                    continue
                seen.add(site)
                crosses.append(
                    {
                        "steamid": str(sid),
                        "site": site,
                        "tick": int(current.tick),
                        "previous_tick": int(previous.tick),
                        "confirmed_tick": int(confirmed),
                        "from_place": str(previous.last_place_name),
                        "from_region": previous.region_id,
                        "route": entry_route(site, previous, profile),
                        "route_known": entry_route(site, previous, profile)
                        != "Nieustalony kierunek",
                        "seconds": float(current.seconds),
                    }
                )
        roster = analysis.round_roster_df
        if {"total_rounds_played", "steamid", "team_num"}.issubset(roster):
            roster = roster[roster.total_rounds_played.eq(rnd)]
        else:
            roster = pd.DataFrame()
        for site in sorted({r.site_id for r in profile.regions if r.kind == "site"}):
            entries = sorted(
                (c for c in crosses if c["site"] == site), key=lambda c: (c["tick"], c["steamid"])
            )
            while entries:
                start = entries[0]["tick"]
                group = [c for c in entries if c["tick"] <= start + group_ticks]
                entries = [c for c in entries if c["tick"] > start + group_ticks]
                at_entry = _sample(states, start, tick_rate)
                carriers = (
                    at_entry[at_entry.has_bomb.eq(True) & at_entry.is_alive.eq(True)]
                    if "has_bomb" in at_entry
                    else at_entry.iloc[:0]
                )
                bomb = [
                    {
                        "steamid": str(r.steamid),
                        "place": str(r.last_place_name),
                        "X": float(r.X),
                        "Y": float(r.Y),
                        "Z": float(r.Z),
                    }
                    for r in carriers.itertuples()
                ]
                utility = context.utility
                if {"total_rounds_played", "tick"}.issubset(utility):
                    utility = utility[
                        utility.total_rounds_played.eq(rnd)
                        & utility.tick.between(max(clock.freeze_tick, start - group_ticks), start)
                    ]
                else:
                    utility = pd.DataFrame()
                utility_rows = []
                for event in utility.to_dict("records"):
                    utility_rows.append(
                        {
                            "tick": int(event["tick"]),
                            "kind": str(event.get("kind", "?")),
                            "steamid": str(event.get("user_steamid", "")),
                            "team": int(event["user_team_num"])
                            if pd.notna(event.get("user_team_num"))
                            else None,
                            "x": event.get("x"),
                            "y": event.get("y"),
                            "z": event.get("z"),
                        }
                    )
                results.append(
                    {
                        "id": f"entry-v{ENTRY_VERSION}:r{rnd}:{site}:{start}",
                        "round": rnd,
                        "site": site,
                        "tick": start,
                        "seconds": (start - clock.freeze_tick) / tick_rate,
                        "participants": group,
                        "routes": dict(Counter(c["route"] for c in group)),
                        "ct_before": _defence(
                            states, roster, start - 2 * tick_rate, site, profile, tick_rate
                        ),
                        "ct_during": _defence(states, roster, start, site, profile, tick_rate),
                        "bomb_carriers": bomb,
                        "utility_before": utility_rows,
                        "plant_tick": plant_tick,
                        "limitations": [
                            "Named navigation regions, not exact geometric gates.",
                            "One crossing per player/site; grouping is not simultaneous headcount.",
                            "Brief entries ending before confirmation can be missed.",
                            "Utility covers the whole map; tactical relevance is not established.",
                            "No carrier observation does not locate a dropped or planted bomb.",
                        ]
                        + (
                            ["Plant event unavailable: post-plant exclusion cannot be confirmed."]
                            if plant_tick is None
                            else []
                        ),
                    }
                )
    return sorted(results, key=lambda e: (e["round"], e["tick"], e["site"]))


def enrich_entries(context, analysis, *, config=None) -> bool:
    """Recompute derived observations from cached samples, never reopen the demo."""
    context.entries = detect_entries(context, analysis, config=config)
    return True
