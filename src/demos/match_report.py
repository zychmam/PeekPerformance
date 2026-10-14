"""Self-contained manual LLM export, projected from existing M3/M4/M5 results."""

import json
import math
import re
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime

import pandas as pd

from src.demos.demo_analyzer import enemy_mask, normalize_round_events, normalize_rounds
from src.demos.map_tendencies import aggregate_tendencies
from src.demos.rating_calculator import RATING_VERSION, compute_rating_from_events
from src.demos.rating_window import active_round_events, metric_clock
from src.demos.report_format import READING_GUIDE, REPORT_FORMAT, REPORT_SCHEMA_VERSION
from src.demos.round_summary import team_summary
from src.models.observations import DetectorConfig
from src.models.tactical import PlayerRound

_STEAM_ID = re.compile(r"7656\d{13}")
_EXCLUDED_SOURCES = {"states", "shots", "equipment", "economy"}


def _ratio(count, denominator, unit):
    return {
        "count": count,
        "denominator": denominator,
        "unit": unit,
        "percentage": round(count / denominator * 100, 2) if denominator else None,
    }


def _stats(rows, rating=None):
    if rows.empty:
        return None
    n = len(rows)
    totals = rows[
        ["kills", "deaths", "assists", "damage", "hs_kills", "kast", "utility_damage", "survived"]
    ].sum()
    return {
        "rounds_played": n,
        "kills": int(totals.kills),
        "deaths": int(totals.deaths),
        "assists": int(totals.assists),
        "damage": round(float(totals.damage), 2),
        "adr": round(float(totals.damage) / n, 2),
        "headshots": _ratio(int(totals.hs_kills), int(totals.kills), "kills"),
        "kast": _ratio(int(totals.kast), n, "rounds"),
        "survival": _ratio(int(totals.survived), n, "rounds"),
        "utility_damage": round(float(totals.utility_damage), 2),
        "peek_performance_rating": rating,
    }


def _compact_aggregate(report):
    """Round details have one owner; aggregate examples reference their rounds."""

    def compact(value):
        if isinstance(value, dict):
            return {
                k: compact(v)
                for k, v in value.items()
                if k not in {"examples", "equipment", "events", "kills"}
            }
        if isinstance(value, list):
            return [compact(v) for v in value]
        return value

    result = compact(report)
    for key in ("attempts", "activity", "rotations", "retakes", "plants"):
        items = report["actions"][key]
        result["actions"].pop(key, None)
        result["actions"][key + "_references"] = [
            {
                "round": item["round"],
                "id": item.get("id") or (item.get("episode") or {}).get("id"),
                "status": item.get("status"),
            }
            for item in items
        ]
    result["actions"]["detached"] = [
        {k: item[k] for k in ("round", "attack_id", "player_id")}
        for item in report["actions"]["detached"]
    ]
    if report["player_id"] is not None:
        # Team context is already exported once in team_sides.
        return {
            **{k: result[k] for k in ("team_id", "side", "player_id", "rounds", "refrags")},
            "tables": {
                k: result["tables"][k] for k in ("positions", "contacts", "opening", "utility")
            },
            "coverage": {
                k: result["coverage"][k] for k in ("contacts", "opening", "utility", "refrags")
            },
            "participation": {
                k: result["actions"][k]
                for k in (
                    "attempts_references",
                    "activity_references",
                    "rotations_references",
                    "detached",
                    "rotation_summary",
                )
            },
        }
    return result


class _RoundEquipment:
    """Store inventories once; every resource snapshot references that same catalog."""

    def __init__(self, number):
        self.number, self.records, self.keys = number, [], {}

    def reference(self, value):
        if value is None:
            return None
        definition = {
            k: v for k, v in value.items() if k not in {"player_id", "tick", "evidence_ids"}
        }
        key = json.dumps(definition, sort_keys=True, default=str)
        if key not in self.keys:
            oid = f"equipment-r{self.number}-{len(self.records) + 1}"
            self.keys[key] = oid
            self.records.append({"id": oid, **definition})
        return self.keys[key]

    def resource_state(self, state):
        result = {**state}
        local = state.get("local_participants")
        result["players"] = [
            {
                "player_id": pid,
                **{k: v for k, v in item.items() if k != "equipment"},
                "equipment_id": self.reference(item.get("equipment")),
                "equipment_sample_tick": (item.get("equipment") or {}).get("tick"),
            }
            for pid, item in state.get("players", {}).items()
            if local is None or pid in local
        ]
        return result

    def observation(self, item):
        return {
            "player_id": item["player_id"],
            "tick": item["tick"],
            "equipment_id": self.reference(item),
        }

    def changes(self, observations):
        last, result = {}, []
        for observation in observations:
            item = asdict(observation)
            # Active weapon toggles add no inventory change; relevant duel weapon
            # remains in each fight's before/after equipment reference.
            signature = json.dumps(
                {k: item[k] for k in ("inventory", "armor", "helmet", "defuse_kit", "economy")},
                sort_keys=True,
                default=str,
            )
            if last.get(item["player_id"]) != signature:
                result.append(self.observation(item))
                last[item["player_id"]] = signature
        return result


def _preparation(value, contexts, side, early_tick):
    result = asdict(value)
    result.pop("utility", None)
    result["early_utility_context_ids"] = [
        u.id
        for u in contexts
        if u.side == side
        and u.throw_tick is not None
        and early_tick is not None
        and u.throw_tick <= early_tick
    ]
    return result


def _action(item, equipment):
    result = {k: v for k, v in item.items() if k != "utility"}
    if "utility" in item:
        result["utility_context_ids"] = [u["id"] for u in item["utility"]]
        relations = [
            {"utility_id": u["id"], "attack_relations": u["attack_relations"]}
            for u in item["utility"]
            if u.get("attack_relations")
        ]
        if relations:
            result["utility_attack_relations"] = relations
    for key in ("before", "after"):
        if key in result:
            result[key] = equipment.resource_state(result[key])
    return result


def _player_round(player, record, fact, rows):
    prep = record.t_preparation if player.side == "T" else record.ct_setup
    start = next((s for s in prep.snapshots if s.seconds == 0), None)
    end = fact["sides"].get(player.side, {}).get("end_alive_ids")
    return {
        "player_id": player.player_id,
        "team_id": player.team_id,
        "side": player.side,
        "participation_status": "observed"
        if any(p.player_id == player.player_id for p in record.players)
        else "unknown",
        "round_statistics": next(
            (
                {k: v for k, v in row.items() if k not in {"steamid", "Gracz", "Runda"}}
                for row in rows
                if str(row["steamid"]) == player.player_id
            ),
            None,
        ),
        "initial_position": next(
            (p for p in start.players if p["player_id"] == player.player_id), None
        )
        if start
        else None,
        "contacts_status": player.contact_status,
        "first_contacts": player.contact_references,
        "contact_ids": player.contact_ids,
        "utility_context_ids": [
            u.id for u in record.utility_contexts if u.player_id == player.player_id
        ],
        "attack_ids": [
            a.episode.id
            for a in record.attacks
            if player.player_id in a.episode.participants + a.detached_players
        ],
        "detached_attack_ids": [
            a.episode.id for a in record.attacks if player.player_id in a.detached_players
        ],
        "rotation_ids": [r.episode.id for r in record.rotations if r.player_id == player.player_id],
        "ct_activity_ids": [a.id for a in record.ct_activity if player.player_id in a.participants],
        "survived_end": player.player_id in end if end is not None else None,
    }


def _statistics_reconciliation(analysis, facts, match, summary):
    kills = normalize_round_events(analysis.kills_df, analysis.rounds_df)
    source_count = int(enemy_mask(kills).sum())
    reported_count = int(summary.K.sum()) if not summary.empty else 0
    clock = _report_metric_clock(analysis, facts)
    eligible = active_round_events(kills, clock)
    eligible_count = int(enemy_mask(eligible).sum())
    clocks = {f["number"]: f["freeze_tick"] for f in facts}
    seen, repeated = {}, []
    for event in sorted(
        (e for e in match.evidence.values() if e.source == "kills"),
        key=lambda e: (e.round_number, e.tick, e.id),
    ):
        victim = str(event.data.get("user_steamid"))
        key = (event.round_number, victim)
        earlier = seen.get(key)
        if earlier is not None and bool(enemy_mask(pd.DataFrame([event.data])).iloc[0]):
            freeze = clocks.get(event.round_number)
            repeated.append(
                {
                    "round": event.round_number,
                    "player_id": victim,
                    "source_event_id": event.id,
                    "tick": event.tick,
                    "earlier_death_tick": earlier.tick,
                    "earlier_death_before_freeze": earlier.tick < freeze
                    if freeze is not None
                    else None,
                }
            )
        seen.setdefault(key, event)
    return {
        "reported_enemy_kills": reported_count,
        "source_enemy_kills": source_count,
        "active_window_enemy_kills": eligible_count,
        "excluded_prefreeze_enemy_kills": source_count - eligible_count,
        "unknown_clock_rounds": clock.loc[clock.metrics_clock_status.eq("unknown"),
                                         "total_rounds_played"].astype(int).tolist(),
        "difference": eligible_count - reported_count,
        "repeated_death_events": repeated,
        "status": "consistent" if eligible_count == reported_count else "discrepancy",
        "explanation": "Statystyki obejmują zdarzenia od końca freeze do końca rundy "
        "włącznie, maksymalnie jeden aktywny zgon gracza. Zdarzenia sprzed freeze "
        "pozostają w źródłach, ale nie zużywają życia ani HP. Przy nieznanym końcu "
        "freeze zachowujemy całe okno rundy; nie zgadujemy resetów. Powtórne zgony "
        "są wskazówką do kontroli źródeł, a nie automatycznie błędem zawodnika.",
    }


def _report_metric_clock(analysis, facts):
    ends = dict(zip(analysis.rounds_df.total_rounds_played, analysis.rounds_df.tick, strict=True))
    clock = pd.DataFrame([
        {"tick": ends[f["number"]], "freeze_tick": f["freeze_tick"]} for f in facts
    ])
    return metric_clock(analysis.rounds_df, clock)


def _source_event(event):
    keep = {
        "weapon",
        "headshot",
        "enemy_damage",
        "dmg_health",
        "dmg_armor",
        "health",
        "armor",
        "assistedflash",
        "flash_duration",
        "duration",
        "kind",
        "event",
        "source_event",
        "entityid",
        "entity_id",
        "end_tick",
        "end_source",
        "site",
        "X",
        "Y",
        "Z",
        "user_X",
        "user_Y",
        "user_Z",
        "last_place_name",
        "user_last_place_name",
        "hitgroup",
        "is_enemy",
    }
    return {
        "id": event.id,
        "type": event.source,
        "round": event.round_number,
        "tick": event.tick,
        "seconds": event.seconds,
        "details": {
            k: v
            for k, v in event.data.items()
            if k in keep or "steamid" in k or k.endswith("team_num")
        },
    }


class _PublicIds:
    def __init__(self, player_ids, evidence):
        self.players = {pid: f"p{i:02d}" for i, pid in enumerate(sorted(player_ids), 1)}
        self.events = {
            e.id: f"e{i:05d}"
            for i, e in enumerate(
                sorted(
                    (e for e in evidence.values() if e.source not in _EXCLUDED_SOURCES),
                    key=lambda e: (e.round_number, e.tick, e.source, e.id),
                ),
                1,
            )
        }
        self.excluded = {e.id for e in evidence.values() if e.source in _EXCLUDED_SOURCES}
        self.derived = {}

    def register(self, value):
        if isinstance(value, dict):
            oid = value.get("id")
            if isinstance(oid, str) and oid not in self.events and oid not in self.excluded:
                self.derived.setdefault(oid, f"d{len(self.derived) + 1:05d}")
            for item in value.values():
                self.register(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                self.register(item)

    def text(self, value):
        if value in self.excluded:
            return None
        if value in self.players:
            return self.players[value]
        if value in self.events:
            return self.events[value]
        if value in self.derived:
            return self.derived[value]
        return _STEAM_ID.sub(lambda match: self.players.get(match[0], "unknown_player"), value)

    def convert(self, value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if isinstance(item, str) and item in self.excluded:
                    continue
                public_key = str(key).replace("steamid", "player_id")
                public_key = self.text(public_key).replace("verified_absent", "absent")
                result[public_key] = self.convert(item)
            return result
        if isinstance(value, (list, tuple)):
            return [
                self.convert(v) for v in value if not isinstance(v, str) or v not in self.excluded
            ]
        if isinstance(value, str):
            return self.text(value).replace("verified_absent", "absent")
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, int):
            return self.players.get(str(value), value)
        if isinstance(value, float):
            return round(value, 4) if math.isfinite(value) else None
        if hasattr(value, "item"):
            return self.convert(value.item())
        return None


def build_match_report(analysis, facts, match, profile, *, generated_at=None):
    if sorted(f["number"] for f in facts) != sorted(r.number for r in match.rounds):
        raise ValueError("Incomplete round data for report")
    normalized = normalize_rounds(analysis.rounds_df)
    original_numbers = dict(
        zip(analysis.rounds_df.tick, analysis.rounds_df.total_rounds_played, strict=True)
    )
    numbers = {
        int(row.total_rounds_played): int(original_numbers[row.tick])
        for row in normalized.itertuples()
    }
    roster = analysis.round_roster_df.copy()
    if "total_rounds_played" in roster:
        reverse = {original: norm for norm, original in numbers.items()}
        roster["total_rounds_played"] = roster.total_rounds_played.map(reverse)
        roster = roster.dropna(subset=["total_rounds_played"])
    summary, per_round = compute_rating_from_events(
        analysis.player_info,
        analysis.kills_df,
        analysis.damage_df,
        analysis.rounds_df,
        analysis.bomb_events_df,
        roster=roster,
        round_clock=_report_metric_clock(analysis, facts),
    )
    if not per_round.empty:
        per_round["Runda"] = per_round.Runda.map(numbers)
    players = {str(p.player_id) for r in match.rounds for p in r.players}
    names = {}
    for row in analysis.player_info.to_dict("records"):
        pid = str(row.get("steamid"))
        if pid and pid != "None":
            players.add(pid)
            names[pid] = str(row.get("name") or "Nieznany gracz")
    for event in match.evidence.values():
        if event.source not in _EXCLUDED_SOURCES:
            for key, value in event.data.items():
                if "steamid" in key and value is not None and _STEAM_ID.fullmatch(str(value)):
                    players.add(str(value))
    ids = _PublicIds(players, match.evidence)
    fact_by_round = {f["number"]: f for f in facts}
    ratings = {str(r.steamid): r.Rating for r in summary.itertuples()}
    player_rows = []
    for pid in sorted(players):
        rows = (
            per_round[per_round.steamid.astype(str).eq(pid)] if not per_round.empty else per_round
        )
        player_rows.append(
            {
                "player_id": pid,
                "nickname": names.get(pid, "Nieznany gracz"),
                "team_ids": sorted(
                    {
                        p.team_id
                        for r in match.rounds
                        for p in r.players
                        if p.player_id == pid and p.team_id is not None
                    }
                ),
                "match_statistics": _stats(rows, ratings.get(pid)),
                "side_statistics": {
                    side: _stats(rows[rows.team_num.eq(number)]) if not rows.empty else None
                    for side, number in (("T", 2), ("CT", 3))
                },
                "unknown_side_statistics": _stats(rows[~rows.team_num.isin([2, 3])])
                if not rows.empty
                else None,
            }
        )
    teams = sorted({tid for r in match.rounds for tid in r.teams_by_side.values() if tid})
    team_rows, map_teams, map_players = [], [], []
    for team in teams:
        own = [f for f in facts if any(s["team_id"] == team for s in f["sides"].values())]
        team_rows.append(
            {
                "team_id": team,
                "player_ids": sorted(
                    {
                        pid
                        for f in own
                        for s in f["sides"].values()
                        if s["team_id"] == team
                        for pid in s["roster"]
                    }
                ),
                "rounds_won": sum(f["winner_team_id"] == team for f in own),
                "known_result_rounds": sum(f["winner_team_id"] is not None for f in own),
                "by_side": {
                    side: {
                        "rounds_played": sum(f["sides"][side]["team_id"] == team for f in own),
                        "rounds_won": sum(
                            f["sides"][side]["team_id"] == team and f["winner_team_id"] == team
                            for f in own
                        ),
                    }
                    for side in ("T", "CT")
                },
            }
        )
        for side in ("T", "CT"):
            report = aggregate_tendencies(facts, team_id=team, side=side)
            map_teams.append(_compact_aggregate(report))
            roster = sorted(
                {
                    pid
                    for f in facts
                    if f["sides"][side]["team_id"] == team
                    for pid in f["sides"][side]["roster"]
                }
            )
            for pid in roster:
                map_players.append(
                    _compact_aggregate(
                        aggregate_tendencies(facts, team_id=team, side=side, player_id=pid)
                    )
                )
    round_rows = []
    for record in sorted(match.rounds, key=lambda r: r.number):
        fact = fact_by_round[record.number]
        foundation = record.foundation
        stats = per_round[per_round.Runda.eq(record.number)] if not per_round.empty else per_round
        round_players = list(record.players)
        present = {p.player_id for p in round_players}
        for row in stats.to_dict("records"):
            if str(row["steamid"]) not in present:
                side = {2: "T", 3: "CT"}.get(row["team_num"])
                round_players.append(
                    PlayerRound(str(row["steamid"]), record.teams_by_side.get(side), side)
                )
        equipment = _RoundEquipment(record.number)
        early_tick = (
            record.freeze_end_tick + fact["early_seconds"] * fact["tick_rate"]
            if record.freeze_end_tick is not None
            else None
        )
        round_rows.append(
            {
                "number": record.number,
                "clock": {
                    "start_tick": record.start_tick,
                    "freeze_tick": record.freeze_end_tick,
                    "end_tick": record.end_tick,
                    "tick_rate": fact["tick_rate"],
                },
                "teams_by_side": record.teams_by_side,
                "result": {
                    "winner_side": record.winner_side,
                    "winner_team_id": record.winner_team_id,
                    "end_reason": record.end_reason,
                    "plants": fact["plants"],
                    "retake": asdict(record.retake),
                    "end_alive": {s: fact["sides"][s]["end_alive_ids"] for s in ("T", "CT")},
                },
                "resources": {
                    "by_side": {
                        s: {
                            "start_alive": fact["sides"][s]["start_alive"],
                            "equipment": fact["sides"][s]["equipment"],
                        }
                        for s in ("T", "CT")
                    },
                    "equipment_records": equipment.records,
                    "equipment_start": [
                        equipment.observation(asdict(e)) for e in foundation.equipment_start
                    ]
                    if foundation
                    else [],
                    "equipment_changes": equipment.changes(foundation.equipment_changes)
                    if foundation
                    else [],
                },
                "preparation": {
                    "T": _preparation(
                        record.t_preparation, record.utility_contexts, "T", early_tick
                    ),
                    "CT": _preparation(record.ct_setup, record.utility_contexts, "CT", early_tick),
                    "ct_sectors_before_contact": record.ct_sectors_before_contact,
                },
                "combat": {
                    "contacts_status": record.contacts_status,
                    "contacts": [asdict(c) for c in record.contacts],
                    "opening_status": record.opening_status,
                    "opening_kill_ids": record.opening_kill_ids,
                    "refrags_status": record.refrags_status,
                    "refrags": [asdict(r) for r in record.refrag_links],
                    "fights_status": record.fights_status,
                    "fights": [_action(asdict(f), equipment) for f in record.fights],
                    "alive_states": [asdict(a) for a in record.alive_states],
                    "moments": [asdict(m) for m in record.moments],
                },
                "attacks": {
                    "status": record.attacks_status,
                    "complete": fact["attacks_complete"],
                    "attempts": [_action(a, equipment) for a in fact["attacks"]],
                    "pressure": [asdict(e) for e in record.t_pressure],
                },
                "defense": {
                    "movement_status": record.movement_status,
                    "activity": [_action(a, equipment) for a in fact["ct_activity"]],
                    "rotation_status": record.rotations_status,
                    "rotations": fact["rotations"],
                    "rotation_eligibility": record.rotation_eligibility,
                },
                "utility": {
                    "status": record.utility_context_status,
                    "contexts": [asdict(u) for u in record.utility_contexts],
                },
                "players": [
                    _player_round(p, record, fact, stats.to_dict("records")) for p in round_players
                ],
                "summary": {
                    "basis": "rule_based",
                    "items": [
                        asdict(item)
                        for item in team_summary(
                            record, match.evidence, names, profile, fact["tick_rate"], 5
                        )
                    ],
                },
                "coverage": {
                    "sources": {k: asdict(v) for k, v in record.availability.items()},
                    "source_quality": {k: asdict(v) for k, v in foundation.source_quality.items()}
                    if foundation
                    else {},
                    "movement_gaps": record.movement_gaps,
                },
            }
        )
    report = {
        "header": {
            "format": REPORT_FORMAT,
            "schema_version": REPORT_SCHEMA_VERSION,
            "language": "pl",
            "generated_at": generated_at or datetime.now(UTC).isoformat(),
            "demo_file": analysis.file_name,
            "map": analysis.map_name,
            "round_count": len(round_rows),
            "player_count": len(players),
            "scope": "entire_match_all_players",
            "score": {t["team_id"]: t["rounds_won"] for t in team_rows},
            "unknown_result_rounds": [f["number"] for f in facts if f["winner_team_id"] is None],
            "versions": {
                "analysis": analysis.analysis_version,
                "rating": RATING_VERSION,
                "tactical_schema": match.schema_version,
                "detector_parameters": match.parameters,
            },
            "map_profile": {
                "version": profile.profile_version if profile else None,
                "regions": [
                    {
                        "id": r.id,
                        "name": r.name,
                        "kind": r.kind,
                        "site_id": r.site_id,
                        "defense_sector": r.defense_sector,
                        "directions": r.directions,
                        "support_sites": r.support_sites,
                    }
                    for r in profile.regions
                ]
                if profile
                else [],
            },
        },
        "reading_guide": READING_GUIDE,
        "teams": team_rows,
        "players": player_rows,
        "map_analysis": {
            "snapshot_seconds": 10,
            "early_seconds": DetectorConfig().early_seconds,
            "team_sides": map_teams,
            "player_sides": map_players,
        },
        "rounds": round_rows,
        "source_events": [
            _source_event(e) for e in match.evidence.values() if e.source not in _EXCLUDED_SOURCES
        ],
        "limitations": {
            "statistics_reconciliation": _statistics_reconciliation(
                analysis, facts, match, summary
            ),
            "profile": profile.coverage if profile else {"status": "unsupported_map"},
            "omitted": [
                "Surowe trajektorie co 0,1 s, strzały, czat, convars i dane tożsamości Steam.",
                "Rating osobno T/CT nie jest liczony; wartości null pozostają jawne.",
            ],
            "interpretation": READING_GUIDE["interpretation_rules"],
            "coverage_status_counts": dict(Counter(str(r.contacts_status) for r in match.rounds)),
        },
    }
    ids.register(report["rounds"])
    ids.register(report["source_events"])
    ids.register(report["map_analysis"])
    result = _pack_tables(ids.convert(report))
    # Guarantee strict JSON, including pandas missing/numpy values and infinity.
    json.dumps(result, allow_nan=False)
    return result


def encode_match_report(report):
    """Readable section headers and one table row per line, without whitespace inflation."""
    validate_match_report(report)

    def scalar(value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))

    def render(value, depth=0):
        pad, inner = "  " * depth, "  " * (depth + 1)
        if isinstance(value, dict):
            if set(value) == {"columns", "rows"}:
                rows = (",\n" + inner + "  ").join(scalar(row) for row in value["rows"])
                return (
                    "{\n"
                    + inner
                    + '"columns": '
                    + scalar(value["columns"])
                    + ",\n"
                    + inner
                    + '"rows": [\n'
                    + inner
                    + "  "
                    + rows
                    + "\n"
                    + inner
                    + "]\n"
                    + pad
                    + "}"
                )
            return (
                "{\n"
                + ",\n".join(
                    inner + scalar(k) + ": " + render(v, depth + 1) for k, v in value.items()
                )
                + "\n"
                + pad
                + "}"
            )
        if isinstance(value, list) and any(isinstance(v, dict) for v in value):
            return (
                "[\n" + ",\n".join(inner + render(v, depth + 1) for v in value) + "\n" + pad + "]"
            )
        return scalar(value)

    return (render(report) + "\n").encode("utf-8")


_TABLE_FIELDS = {
    "source_events",
    "contacts",
    "fights",
    "alive_states",
    "moments",
    "equipment_records",
    "equipment_start",
    "equipment_changes",
    "snapshots",
    "players",
    "movements",
    "attempts",
    "pressure",
    "activity",
    "rotations",
    "rotation_eligibility",
    "contexts",
    "items",
    "detached_actions",
    "intervals",
    "utility",
    "detached",
    "pairs",
    "summaries",
    "attempts_references",
    "activity_references",
    "rotations_references",
    "retakes_references",
    "plants_references",
    "sites",
    "executions",
    "bomb_observations",
}


def _pack_tables(value, path=()):
    if isinstance(value, dict):
        return {k: _pack_tables(v, (*path, k)) for k, v in value.items()}
    if not isinstance(value, list):
        return value
    rows = [_pack_tables(v, (*path, "[]")) for v in value]
    if (
        path
        and path[-1] in _TABLE_FIELDS
        and path != ("players",)
        and value
        and all(isinstance(v, dict) for v in value)
    ):
        columns = list(dict.fromkeys(k for v in value for k in v))
        return {"columns": columns, "rows": [[v.get(k) for k in columns] for v in rows]}
    return rows


def table_records(value):
    """Decode either a self-describing table or an empty collection."""
    if isinstance(value, list):
        return value
    return [dict(zip(value["columns"], row, strict=True)) for row in value["rows"]]


def validate_match_report(report):
    """Validate critical counts, strict JSON, privacy and table/reference integrity."""
    required = {
        "header",
        "reading_guide",
        "teams",
        "players",
        "map_analysis",
        "rounds",
        "source_events",
        "limitations",
    }
    if set(report) != required or report["header"]["schema_version"] != REPORT_SCHEMA_VERSION:
        raise ValueError("Unsupported match report schema")
    if report["header"]["round_count"] != len(report["rounds"]):
        raise ValueError("Round count does not match report")
    if report["header"]["player_count"] != len(report["players"]):
        raise ValueError("Player count does not match report")
    if _STEAM_ID.search(json.dumps(report, ensure_ascii=False, allow_nan=False)):
        raise ValueError("Report contains a private player identifier")

    def objects(value):
        if isinstance(value, dict):
            if set(value) == {"columns", "rows"}:
                if len(value["columns"]) != len(set(value["columns"])):
                    raise ValueError("Duplicate table columns")
                for row in table_records(value):
                    yield from objects(row)
            else:
                yield value
                for item in value.values():
                    yield from objects(item)
        elif isinstance(value, list):
            for item in value:
                yield from objects(item)

    rows = list(objects(report))
    event_ids = {e["id"] for e in table_records(report["source_events"])}
    for item in rows:
        for key in (
            "evidence_ids",
            "event_ids",
            "kill_ids",
            "damage_ids",
            "opening_kill_ids",
            "opening_window_kill_ids",
            "effect_ids",
            "utility_effect_ids",
        ):
            if isinstance(item.get(key), list) and not set(item[key]) <= event_ids:
                raise ValueError(f"Unresolved source references: {key}")
    definitions = {row["id"] for row in rows if isinstance(row.get("id"), str)}
    for row in report["rounds"]:
        equipment_ids = {e["id"] for e in table_records(row["resources"]["equipment_records"])}
        for item in objects(row):
            if item.get("equipment_id") is not None and item["equipment_id"] not in equipment_ids:
                raise ValueError("Unresolved round equipment reference")
            for key, value in item.items():
                if key.endswith("_ids") and isinstance(value, list):
                    for ref in value:
                        if (
                            isinstance(ref, str)
                            and re.fullmatch(r"d\d{5,}", ref)
                            and ref not in definitions
                        ):
                            raise ValueError(f"Unresolved derived reference: {key}")


def prepare_match_report(db, manager, analysis):
    from src.demos.map_tendencies_service import get_map_round_facts
    from src.demos.spatial_service import get_spatial_context
    from src.demos.tactical_rounds import build_tactical_match

    facts = get_map_round_facts(db, manager, analysis)
    context = get_spatial_context(db, manager, analysis)
    match = build_tactical_match(
        analysis, context, foundations=context.foundations, cached_actions=context.tactical_actions
    )
    return build_match_report(analysis, facts, match, context.profile)


def report_cache_key(analysis):
    from src.demos.map_tendencies_service import round_facts_key

    return f"report_{REPORT_SCHEMA_VERSION}_{RATING_VERSION}_{round_facts_key(analysis)}"
