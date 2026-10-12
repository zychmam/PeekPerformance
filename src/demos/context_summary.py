"""Presentation helpers for observed round context on any profiled map."""

import pandas as pd

from src.demos.demo_analyzer import enemy_mask
from src.maps.resolver import region_label, resolve_region
from src.models.observations import RoundClock

SETUP_SECONDS = 12


def snapshot(context, round_number: int, seconds: float) -> pd.DataFrame:
    """Last common sample <= requested time, at most 1 s old; never carry dead players."""
    states = context.states
    if states.empty:
        return states.copy()
    clock = RoundClock.from_row(
        context.clock[context.clock.total_rounds_played.eq(round_number)].iloc[0].to_dict()
    )
    target = clock.tick_at(seconds)
    if target is None:
        return states.iloc[:0].copy()
    part = states[
        states.total_rounds_played.eq(round_number)
        & states.tick.between(target - clock.ticks(1), target)
    ]
    if part.empty:
        return part
    return part[
        part.tick.eq(part.tick.max()) & part.is_alive.eq(True) & part.team_num.isin([2, 3])
    ].copy()


def round_observations(context, analysis) -> pd.DataFrame:
    rows = []
    for row in context.clock.itertuples():
        rnd = int(row.total_rounds_played)
        setup = snapshot(context, rnd, SETUP_SECONDS)
        counts = {}
        for side, team in (("CT", 3), ("T", 2)):
            group = setup[setup.team_num.eq(team)] if not setup.empty else setup
            counts[side] = dict(group.place.value_counts()) if not group.empty else {}
        item = {
            "round": rnd,
            "winner": row.winner,
            "reason": getattr(row, "reason", ""),
            "setup_ct": counts["CT"],
            "setup_t": counts["T"],
            "setup_observed_alive": len(setup),
            "opening_tick": None,
            "contact_tick": None,
            "opening_attacker_place": None,
            "opening_victim_place": None,
        }
        for frame, prefix in ((analysis.kills_df, "opening"), (analysis.damage_df, "contact")):
            if frame.empty or "total_rounds_played" not in frame:
                continue
            part = frame[frame.total_rounds_played.eq(rnd) & enemy_mask(frame)]
            if prefix == "contact" and "enemy_damage" in part:
                part = part[part.enemy_damage.gt(0)]
            if part.empty:
                continue
            first = part.sort_values("tick", kind="stable").iloc[0]
            item[f"{prefix}_tick"] = int(first.tick)
            if prefix == "opening":
                item["opening_same_tick_count"] = int(part.tick.eq(first.tick).sum())
                for participant, output in (("attacker", "attacker"), ("user", "victim")):
                    place = first.get(f"{participant}_last_place_name")
                    item[f"opening_{output}_place"] = region_label(
                        resolve_region({"last_place_name": place}, context.profile), context.profile
                    )
        rows.append(item)
    return pd.DataFrame(rows)


def player_setup_profile(context, player_id: str) -> pd.DataFrame:
    """One observation per round, so extra contact samples do not bias frequency."""
    rows = []
    for rnd in context.clock.total_rounds_played:
        frame = snapshot(context, int(rnd), SETUP_SECONDS)
        if frame.empty:
            continue
        player = frame[frame.steamid.eq(str(player_id))]
        if not player.empty:
            item = player.iloc[0]
            rows.append({"Strona": "CT" if item.team_num == 3 else "T", "Pozycja": item.place})
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .groupby(["Strona", "Pozycja"])
        .size()
        .rename("Rundy z obserwacją")
        .reset_index()
        .sort_values("Rundy z obserwacją", ascending=False)
    )
