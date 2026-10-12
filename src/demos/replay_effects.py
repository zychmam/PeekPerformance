"""Observed smoke intervals and gunfire; radar footprints remain illustrative."""

import pandas as pd

from src.demos.demo_analyzer import normalize_round_events

NON_GUNS = {
    "hegrenade",
    "flashbang",
    "smokegrenade",
    "molotov",
    "incgrenade",
    "decoy",
    "c4",
    "inferno",
}
SMOKE_VISUAL_RADIUS = 144  # Approximate radar footprint, not collision/visibility geometry.


def extract_replay_effects(
    parser, clock, utility, events, diagnostics, *, extras=None, tick_rate=64,
):
    sources = diagnostics.setdefault("sources", {})
    expires = pd.DataFrame()
    if "smokegrenade_expired" in events:
        try:
            expires = parser.parse_event("smokegrenade_expired")
            sources["smokegrenade_expired"] = "ok"
        except Exception as exc:
            sources["smokegrenade_expired"] = f"error: {type(exc).__name__}"
    else:
        sources["smokegrenade_expired"] = "absent"
    smokes = []
    bounds = clock.set_index("total_rounds_played").tick.to_dict()
    for row in utility.to_dict("records"):
        if row.get("source_event") != "smokegrenade_detonate":
            continue
        match = pd.DataFrame()
        if {"entityid", "tick"}.issubset(expires) and row.get("entityid") is not None:
            match = expires[expires.entityid.eq(row["entityid"]) & expires.tick.gt(row["tick"])]
            # Entity IDs can be reused. Require a matching detonation location too.
            for axis in ("x", "y", "z"):
                if axis in match and pd.notna(row.get(axis)):
                    match = match[(match[axis] - row[axis]).abs().lt(8)]
        # A reused entity cannot inherit the expiry of its next incarnation.
        later = utility[
            (utility.get("source_event") == "smokegrenade_detonate")
            & utility.get("entityid", pd.Series(index=utility.index, dtype=float)).eq(
                row.get("entityid")
            )
            & utility.tick.gt(row["tick"])
        ]
        if not later.empty and not match.empty:
            match = match[match.tick.lt(later.tick.min())]
        expiry = int(match.tick.min()) if not match.empty else int(row["tick"] + 22 * tick_rate)
        smokes.append(
            {
                "total_rounds_played": row["total_rounds_played"],
                "tick": row["tick"],
                "end_tick": min(expiry, bounds[row["total_rounds_played"]]),
                "x": row.get("x"),
                "y": row.get("y"),
                "z": row.get("z"),
                "radius": SMOKE_VISUAL_RADIUS,
                "end_source": "event" if not match.empty else "estimated_22s",
                "observed_end_tick": int(match.tick.min()) if not match.empty else None,
                "entityid": row.get("entityid"),
                "user_steamid": row.get("user_steamid"),
                "user_team_num": row.get("user_team_num"),
                "source_event": "smokegrenade_detonate",
                "expiry_observation": (
                    match.sort_values("tick").iloc[0].to_dict() if not match.empty else None
                ),
            }
        )
    shots = pd.DataFrame()
    throws = pd.DataFrame()
    if "weapon_fire" in events:
        try:
            shots = parser.parse_event("weapon_fire", player=["X", "Y", "Z", "yaw", "team_num"])
            shots = normalize_round_events(shots, clock)
            if not shots.empty:
                weapon = shots.weapon.fillna("").str.removeprefix("weapon_")
                throws = shots[
                    weapon.isin(
                        {"hegrenade", "flashbang", "smokegrenade", "molotov", "incgrenade", "decoy"}
                    )
                ].copy()
                throws["kind"] = weapon.loc[throws.index].map(
                    {
                        "hegrenade": "HE",
                        "flashbang": "Flash",
                        "smokegrenade": "Smoke",
                        "molotov": "Ogień",
                        "incgrenade": "Ogień",
                        "decoy": "Decoy",
                    }
                )
                throws["source_event"] = "weapon_fire"
                throws = throws.reset_index(drop=True)
                shots = shots[
                    weapon.ne("")
                    & ~weapon.isin(NON_GUNS)
                    & ~weapon.str.contains("knife|bayonet", regex=True)
                ].copy()
                shots = shots.reset_index(drop=True)
                for frame in (shots, throws):
                    for column in frame:
                        if "steamid" in column:
                            frame[column] = frame[column].astype("string")
            sources["weapon_fire"] = "ok"
        except Exception as exc:
            sources["weapon_fire"] = f"error: {type(exc).__name__}"
            shots = pd.DataFrame()
    else:
        sources["weapon_fire"] = "absent"
    if extras is not None:
        extras["throws"] = throws
        extras["utility_lifecycles"] = utility_lifecycles(
            parser,
            clock,
            utility,
            pd.DataFrame(smokes),
            throws,
            events,
            diagnostics,
            tick_rate=tick_rate,
        )
    return pd.DataFrame(smokes), shots


def utility_lifecycles(
    parser, clock, utility, smokes, throws, events, diagnostics, *, tick_rate=64,
):
    """Keep raw observations; temporal matching remains explicitly limited."""
    import json

    expired = pd.DataFrame()
    sources = diagnostics.setdefault("sources", {})
    if "inferno_expire" in events:
        try:
            expired = parser.parse_event("inferno_expire")
            if not isinstance(expired, pd.DataFrame):
                raise ValueError("No event frame")
            sources["inferno_expire"] = "ok"
        except Exception as exc:
            sources["inferno_expire"] = f"error: {type(exc).__name__}"
    else:
        sources["inferno_expire"] = "not_listed"
    results, candidates = [], []
    for effect in json.loads(utility.to_json(orient="records")):
        row = {
            **effect,
            "effect_tick": int(effect["tick"]),
            "throw_tick": None,
            "throw_observation": None,
            "throw_match": "unknown",
            "end_tick": None,
            "end_source": "unknown",
            "expiry_observation": None,
        }
        if effect.get("kind") == "Smoke" and not smokes.empty:
            match = smokes[smokes.tick.eq(effect["tick"])]
            if "entityid" in smokes:
                match = match[match.entityid.eq(effect.get("entityid"))]
            if len(match) == 1:
                smoke = match.iloc[0]
                row.update(
                    end_tick=(
                        int(smoke.observed_end_tick) if pd.notna(smoke.observed_end_tick) else None
                    ),
                    end_source="event" if smoke.end_source == "event" else "unknown",
                    expiry_observation=smoke.expiry_observation,
                    display_end_tick=int(smoke.end_tick),
                    display_end_source=smoke.end_source,
                )
        elif effect.get("kind") == "Ogień" and {"entityid", "tick"}.issubset(expired):
            match = expired[
                expired.entityid.eq(effect.get("entityid")) & expired.tick.gt(effect["tick"])
            ]
            later = utility[
                utility.source_event.eq("inferno_startburn")
                & utility.entityid.eq(effect.get("entityid"))
                & utility.tick.gt(effect["tick"])
            ]
            if not later.empty:
                match = match[match.tick.lt(later.tick.min())]
            if not match.empty:
                raw = json.loads(match.sort_values("tick").head(1).to_json(orient="records"))[0]
                row.update(end_tick=int(raw["tick"]), end_source="event", expiry_observation=raw)
        elif effect.get("kind") in {"Flash", "HE"}:
            row.update(end_tick=int(effect["tick"]), end_source="instant_effect")
        candidate = []
        if not throws.empty and effect.get("user_steamid") is not None:
            candidate = throws.index[
                throws.kind.eq(effect.get("kind"))
                & throws.user_steamid.eq(str(effect["user_steamid"]))
                & throws.total_rounds_played.eq(effect["total_rounds_played"])
                & throws.tick.between(effect["tick"] - 20 * tick_rate, effect["tick"])
            ].tolist()
        candidates.append(candidate)
        results.append(row)
    # Require uniqueness in both directions; do not force consecutive flashes to match.
    from collections import Counter

    usage = Counter(index for indexes in candidates for index in indexes)
    for row, indexes in zip(results, candidates, strict=True):
        if len(indexes) == 1 and usage[indexes[0]] == 1:
            raw = json.loads(throws.loc[[indexes[0]]].to_json(orient="records"))[0]
            row.update(
                throw_tick=int(raw["tick"]),
                throw_observation=raw,
                throw_match="unique_temporal_limited",
            )
    return pd.DataFrame(results)
