"""Optional, independently diagnosed parser streams for tactical foundations."""

from collections import Counter

import pandas as pd

from src.demos.demo_analyzer import normalize_round_events

BOMB_EVENTS = (
    "bomb_planted",
    "bomb_defused",
    "bomb_exploded",
    "bomb_pickup",
    "bomb_dropped",
    "bomb_beginplant",
    "bomb_abortplant",
    "bomb_begindefuse",
    "bomb_abortdefuse",
)
EQUIPMENT_GROUPS = {
    "inventory": ["inventory"],
    "weapon": ["active_weapon_name"],
    "armor": ["armor_value", "has_helmet"],
    "defuse": ["has_defuser"],
}
ECONOMY_PROPS = [
    "balance",
    "current_equip_value",
    "cash_spent_this_round",
    "start_balance",
    "round_start_equip_value",
]
EQUIPMENT_PROPS = [p for props in EQUIPMENT_GROUPS.values() for p in props]


def inventory_counts(value):
    if not isinstance(value, (list, tuple)):
        return None
    return dict(sorted(Counter(str(item) for item in value).items()))


def _merge_samples(frames):
    combined = pd.DataFrame()
    for frame in frames:
        if not isinstance(frame, pd.DataFrame) or not {"steamid", "tick"}.issubset(frame):
            continue
        frame = frame.drop_duplicates(["steamid", "tick"]).copy()
        frame["steamid"] = frame.steamid.astype("string")
        if combined.empty:
            combined = frame
        else:
            cols = [col for col in frame if col not in combined or col in {"steamid", "tick"}]
            combined = combined.merge(frame[cols], on=["steamid", "tick"], how="outer")
    return combined


def extract_equipment(parser, ticks, clock, diagnostics, *, economy_reader=None, tick_rate=64):
    """Fast shared read, with group fallback so unsupported props stay isolated."""
    sources = diagnostics.setdefault("sources", {})
    frames = []
    if not ticks:
        return pd.DataFrame(), pd.DataFrame(), {}
    try:
        frame = parser.parse_ticks(["team_num", *EQUIPMENT_PROPS], ticks=ticks)
        if not isinstance(frame, pd.DataFrame):
            raise ValueError("Equipment reader returned no frame")
        frames.append(frame)
        for group in EQUIPMENT_GROUPS:
            sources[f"equipment_{group}"] = "ok"
    except Exception:
        for group, props in EQUIPMENT_GROUPS.items():
            try:
                frame = parser.parse_ticks(["team_num", *props], ticks=ticks)
                if not isinstance(frame, pd.DataFrame):
                    raise ValueError("Equipment reader returned no frame")
                frames.append(frame)
                sources[f"equipment_{group}"] = "ok"
            except Exception as exc:
                sources[f"equipment_{group}"] = f"error: {type(exc).__name__}"
                if len(props) > 1:
                    for prop in props:
                        try:
                            frames.append(parser.parse_ticks(["team_num", prop], ticks=ticks))
                            sources[f"equipment_{group}.{prop}"] = "ok"
                        except Exception as field_exc:
                            sources[f"equipment_{group}.{prop}"] = (
                                f"error: {type(field_exc).__name__}"
                            )
    combined = _merge_samples(frames)
    combined = normalize_round_events(combined, clock)
    coverage = {}
    if not combined.empty:
        combined = combined.sort_values(["total_rounds_played", "steamid", "tick"])
        signature_cols = [col for col in ["team_num", *EQUIPMENT_PROPS] if col in combined]
        keep = []
        for (rnd, pid), group in combined.groupby(["total_rounds_played", "steamid"]):
            previous = None
            last_tick = None
            gaps = []
            for index, row in group.iterrows():
                signature = repr([row.get(col) for col in signature_cols])
                gap = last_tick is not None and row.tick - last_tick > 2 * tick_rate
                if gap:
                    gaps.append([int(last_tick), int(row.tick)])
                if signature != previous or gap:
                    keep.append(index)
                previous, last_tick = signature, int(row.tick)
            coverage.setdefault(int(rnd), {})[str(pid)] = {
                "first_tick": int(group.tick.min()),
                "last_tick": int(group.tick.max()),
                "max_gap_ticks": int(group.tick.diff().max()) if len(group) > 1 else None,
                "gaps": gaps,
                "sample_count": len(group),
            }
        combined = combined.loc[keep].reset_index(drop=True)
    freezes = clock.freeze_tick.dropna().astype(int).tolist()
    try:
        if economy_reader is not None:
            economy = economy_reader(freeze_ticks=freezes, strict=True)
        else:
            economy = (
                parser.parse_ticks(["team_num", *ECONOMY_PROPS], ticks=freezes)
                if freezes
                else pd.DataFrame()
            )
        if not isinstance(economy, pd.DataFrame):
            raise ValueError("Economy reader returned no frame")
        economy = normalize_round_events(economy, clock)
        if "steamid" in economy:
            economy["steamid"] = economy.steamid.astype("string")
        sources["equipment_economy"] = "ok" if freezes else "not_loaded"
    except Exception as exc:
        fields = []
        for prop in ECONOMY_PROPS:
            try:
                if freezes:
                    fields.append(parser.parse_ticks(["team_num", prop], ticks=freezes))
            except Exception:
                continue
        economy = normalize_round_events(_merge_samples(fields), clock)
        sources["equipment_economy"] = f"error: {type(exc).__name__}"
    return combined, economy, coverage


def extract_bomb_events(parser, clock, available, diagnostics):
    sources = diagnostics.setdefault("sources", {})
    frames = []
    requested = [event for event in BOMB_EVENTS if event in available]
    try:
        batch = (
            dict(parser.parse_events(requested, player=["team_num", "X", "Y", "Z"]))
            if requested
            else {}
        )
    except Exception:
        batch = {}
    for event in BOMB_EVENTS:
        if event not in available:
            # The demo's observed event list is not a schema/support declaration.
            sources[event] = "not_listed"
            continue
        try:
            frame = batch.get(event)
            if frame is None:
                frame = parser.parse_event(event, player=["team_num", "X", "Y", "Z"])
            if not isinstance(frame, pd.DataFrame):
                raise ValueError("Event reader returned no frame")
            frame = normalize_round_events(frame, clock)
            frame["event"] = event
            for col in frame:
                if "steamid" in col:
                    frame[col] = frame[col].astype("string")
            frames.append(frame)
            sources[event] = "ok"
        except Exception as exc:
            sources[event] = f"error: {type(exc).__name__}"
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
