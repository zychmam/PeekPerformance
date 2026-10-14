"""Observed grenade flight, normalized once and stored independently of map profiles."""

from functools import lru_cache
from threading import RLock

import numpy as np
import pandas as pd

from src.models.observations import canonical_fingerprint

PROJECTILES_VERSION = 1
KINDS = {
    "CFlashbangProjectile": "Flash",
    "CHEGrenadeProjectile": "HE",
    "CSmokeGrenadeProjectile": "Smoke",
    "CMolotovProjectile": "Ogień",
    "CDecoyProjectile": "Decoy",
}


def _thin(samples, step):
    """Keep sharp turns, both sides of gaps, endpoints, and regular samples."""
    if len(samples) < 3:
        return samples
    xyz = samples[["x", "y", "z"]].to_numpy(float)
    vectors = np.diff(xyz, axis=0)
    lengths = np.linalg.norm(vectors, axis=1)
    denom = lengths[:-1] * lengths[1:]
    cosines = np.ones(len(denom))
    np.divide((vectors[:-1] * vectors[1:]).sum(axis=1), denom, out=cosines, where=denom > 0.0001)
    turns = set((np.flatnonzero(cosines < 0.96) + 1).tolist())
    keep, last = [0], int(samples.tick.iloc[0])
    for i, tick in enumerate(samples.tick.iloc[1:-1], 1):
        if i in turns or int(tick) - last >= step:
            keep.append(i)
            last = int(tick)
    keep.append(len(samples) - 1)
    return samples.iloc[keep]


def normalize_projectiles(raw, clock, effects):
    """Split reused entities/teleports/gaps; never infer a flight from endpoints."""
    result = {int(r): {"projectiles": []} for r in clock.total_rounds_played}
    needed = {"grenade_type", "grenade_entity_id", "tick", "x", "y", "z"}
    if raw.empty or not needed.issubset(raw):
        return result
    raw = raw[raw.grenade_type.isin(KINDS)].copy()
    for name in ("tick", "x", "y", "z"):
        raw[name] = pd.to_numeric(raw[name], errors="coerce")
    raw = raw[np.isfinite(raw[["tick", "x", "y", "z"]]).all(axis=1)]
    if "steamid" not in raw:
        raw["steamid"] = ""
    raw["steamid"] = raw.steamid.astype("string").fillna("")
    clocks = {int(row.total_rounds_played): row for row in clock.itertuples()}
    effect_rows = effects.to_dict("records")
    grouped = raw.groupby(
        ["grenade_type", "grenade_entity_id", "steamid"],
        sort=False,
        dropna=False,
    )
    for (type_name, entity, owner), group in grouped:
        group = group.sort_values("tick", kind="stable").drop_duplicates("tick")
        delta = group[["x", "y", "z"]].diff()
        breaks = group.tick.diff().gt(2) | np.sqrt((delta * delta).sum(axis=1)).gt(200)
        for _, segment in group.groupby(breaks.cumsum(), sort=False):
            start, last = int(segment.tick.iloc[0]), int(segment.tick.iloc[-1])
            candidates = [
                e
                for e in effect_rows
                if e.get("entityid") == entity
                and e.get("kind") == KINDS[type_name]
                and owner
                and str(e.get("user_steamid")) == owner
                and start <= e.get("tick", -1) <= last + 2
            ]
            effect_tick = min((int(e["tick"]) for e in candidates), default=None)
            flight_end = effect_tick if effect_tick is not None else last + 1
            # End the physical flight before splitting by round, so a smoke
            # still present next round does not become a newly flying grenade.
            for number, bounds in clocks.items():
                rate = float(getattr(bounds, "tick_rate", 64))
                freeze = getattr(bounds, "freeze_tick", None)
                if pd.isna(freeze) or freeze >= flight_end or bounds.tick < start:
                    continue
                end = min(int(bounds.tick) + 1, flight_end)
                part = segment[segment.tick.ge(freeze) & segment.tick.lt(end)]
                if part.empty:
                    continue
                thinned = _thin(part, max(1, round(rate * 0.1)))
                result[number]["projectiles"].append(
                    {
                        "kind": KINDS[type_name],
                        "owner": str(owner),
                        "start_tick": int(part.tick.iloc[0]),
                        "end_tick": end,
                        "end_source": "effect_entity_owner"
                        if effect_tick is not None
                        else "last_sample",
                        "max_gap_seconds": max(2 / rate, round(rate * 0.1) / rate) * 1.5,
                        "samples": [
                            [int(r.tick), float(r.x), float(r.y), float(r.z)]
                            for r in thinned.itertuples()
                        ],
                    }
                )
    for payload in result.values():
        payload["projectiles"].sort(key=lambda p: p["start_tick"])
    return result


@lru_cache(maxsize=32)
def _lock(db_path, demo_id):
    return RLock()


def get_round_projectiles(db, manager, analysis, source_key, round_number):
    key = canonical_fingerprint(
        {"demo": analysis.content_hash, "sources": source_key, "version": PROJECTILES_VERSION}
    )
    with _lock(db._db_path, analysis.content_hash):
        if db.get_stage_manifest(analysis.content_hash, "viewer_projectiles", key):
            saved = db.get_stage_rounds(
                analysis.content_hash, "viewer_projectiles", key, round_number
            )
            if round_number in saved:
                return saved[round_number]
        clock = db.get_observation_clock(analysis.content_hash, source_key)
        if clock.empty:
            raise ValueError("Brak zapisanego zegara dla torów granatów")
        effects = db.get_observation_frame(analysis.content_hash, source_key, "utility")
        raw = analysis.grenades_df
        if raw.empty:
            raw = db.get_demo_projectiles(analysis.content_hash)
        if raw.empty:
            path = manager.analysis_path(analysis.stored_file_name, analysis.content_hash)
            if path:
                from demoparser2 import DemoParser

                raw = DemoParser(str(path)).parse_grenades(grenades=False)
        payloads = normalize_projectiles(raw, clock, effects)
        manifest = {
            "demo_id": analysis.content_hash,
            "cache_key": key,
            "round_numbers": sorted(payloads),
            "schema_version": PROJECTILES_VERSION,
        }
        db.save_stages(analysis.content_hash, {"viewer_projectiles": (key, manifest, payloads)})
        return payloads.get(round_number, {"projectiles": []})
