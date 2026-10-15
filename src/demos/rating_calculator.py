"""Approximate, project-specific player rating from normalized CS2 demo events.

The win-probability table is heuristic. The resulting score is not an official
HLTV or Leetify rating; individual figures need validation on real demos.
"""

from __future__ import annotations

import logging
from itertools import chain
from pathlib import Path

import pandas as pd
from demoparser2 import DemoParser

from src.demos.demo_analyzer import (
    _steamid,
    enemy_mask,
    normalize_damage,
    normalize_round_events,
    normalize_rounds,
)
from src.demos.versions import METRICS_VERSION

logger = logging.getLogger(__name__)

# Bump when the formula or normalization changes so stored summaries are refreshed.
RATING_VERSION = METRICS_VERSION

_WP_PRE: dict[tuple[int, int], float] = {
    (5, 5): .530, (5, 4): .750, (5, 3): .900, (5, 2): .970, (5, 1): .995,
    (4, 5): .320, (4, 4): .530, (4, 3): .760, (4, 2): .910, (4, 1): .980,
    (3, 5): .140, (3, 4): .330, (3, 3): .550, (3, 2): .780, (3, 1): .930,
    (2, 5): .050, (2, 4): .140, (2, 3): .330, (2, 2): .550, (2, 1): .820,
    (1, 5): .020, (1, 4): .050, (1, 3): .140, (1, 2): .300, (1, 1): .550,
}
_WP_POST: dict[tuple[int, int], float] = {
    (5, 5): .300, (5, 4): .500, (5, 3): .700, (5, 2): .850, (5, 1): .950,
    (4, 5): .180, (4, 4): .300, (4, 3): .530, (4, 2): .750, (4, 1): .900,
    (3, 5): .080, (3, 4): .180, (3, 3): .330, (3, 2): .580, (3, 1): .800,
    (2, 5): .030, (2, 4): .080, (2, 3): .180, (2, 2): .350, (2, 1): .600,
    (1, 5): .010, (1, 4): .030, (1, 3): .080, (1, 2): .180, (1, 1): .350,
}
for count in range(6):
    _WP_PRE[(count, 0)] = 1.0
    _WP_PRE[(0, count)] = 0.0
    _WP_POST[(count, 0)] = 1.0
    _WP_POST[(0, count)] = 0.0
_WP_PRE[(0, 0)] = 0.5
_WP_POST[(0, 0)] = 0.0

_W_KILL = 0.35
_W_DAMAGE = 0.30
_W_FLASH = 0.15
_W_TRADE = 0.20


def _ct_wp(ct_alive: int, t_alive: int, bomb_planted: bool) -> float:
    ct = max(0, min(5, ct_alive))
    t = max(0, min(5, t_alive))
    return (_WP_POST if bomb_planted else _WP_PRE).get((ct, t), 0.5)


def _optional_event(parser: DemoParser, event: str, **kwargs: object) -> pd.DataFrame:
    try:
        return parser.parse_event(event, **kwargs)
    except Exception:
        logger.debug("Optional event unavailable: %s", event)
        return pd.DataFrame()


def compute_rating(demo_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Parse the demo once for rating inputs, then use the testable event algorithm."""
    parser = DemoParser(str(demo_path))
    round_props = ["total_rounds_played", "is_warmup_period"]
    ends = parser.parse_event("round_end", other=round_props)
    starts = _optional_event(parser, "round_start", other=round_props)
    rounds = normalize_rounds(ends, starts)
    from src.demos.observations import round_clock

    rounds = round_clock(rounds, _optional_event(parser, "round_freeze_end"))
    if rounds.empty:
        return pd.DataFrame(), pd.DataFrame()
    kills = parser.parse_event(
        "player_death", player=["team_num"], other=round_props,
    )
    damage = parser.parse_event(
        "player_hurt", player=["team_num", "health"], other=round_props,
    )
    bomb = _optional_event(parser, "bomb_planted", other=round_props)
    try:
        roster = parser.parse_ticks(
            ["team_num"], ticks=rounds["start_tick"].astype(int).tolist(),
        )
    except Exception:
        logger.warning("Round rosters unavailable; team assignments may be incomplete")
        roster = pd.DataFrame()
    return compute_rating_from_events(
        parser.parse_player_info(), kills, damage, rounds, bomb, roster=roster,
    )


def _add_swing(
    swing: dict[str, dict[int, float]], steamid: str, rnd: int, value: float,
) -> None:
    if steamid in swing:
        swing[steamid][rnd] = swing[steamid].get(rnd, 0.0) + value


def compute_rating_from_events(
    player_info: pd.DataFrame,
    kills: pd.DataFrame,
    damage: pd.DataFrame,
    rounds: pd.DataFrame,
    bomb_planted: pd.DataFrame,
    *,
    roster: pd.DataFrame | None = None,
    tick_rate: int = 64,
    round_clock: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute a heuristic rating from events with explicit round and team context.

    Enemy HP damage excludes friendly fire and overkill. Kills credit opponents
    only; deaths include team kills and world damage. Team side is taken per round
    from the roster, so a side switch does not require guessed assignments.
    """
    from src.demos.rating_window import active_round_events, metric_clock

    rounds = metric_clock(normalize_rounds(rounds), round_clock)
    if rounds.empty:
        return pd.DataFrame(), pd.DataFrame()
    kills = active_round_events(kills, rounds)
    # Rebuild HP after filtering: pre-freeze hurts must not consume the new life.
    damage = normalize_damage(active_round_events(damage, rounds))
    bombs = active_round_events(bomb_planted, rounds)
    if "event" in bombs:
        bombs = bombs[bombs["event"].eq("bomb_planted")]
    if roster is None:
        roster = pd.DataFrame()
    elif not roster.empty and "tick" in roster:
        roster = normalize_round_events(roster, rounds)
    names: dict[str, str] = {}
    if not player_info.empty and {"steamid", "name"}.issubset(player_info):
        names = {
            _steamid(row.steamid): str(row.name)
            for row in player_info[["steamid", "name"]].itertuples(index=False)
        }
    players = set(names)
    teams: dict[tuple[str, int], int] = {}
    if not roster.empty and {"steamid", "team_num", "total_rounds_played"}.issubset(roster):
        for row in roster.itertuples():
            sid = _steamid(row.steamid)
            team = int(row.team_num) if pd.notna(row.team_num) else 0
            if sid and team in (2, 3):
                teams[(sid, int(row.total_rounds_played))] = team
                players.add(sid)
    for row in chain(kills.itertuples(), damage.itertuples()):
        rnd = int(row.total_rounds_played)
        for prefix, sid_attr in (("attacker", "attacker_steamid"), ("user", "user_steamid")):
            sid = _steamid(getattr(row, sid_attr, None))
            team = getattr(row, f"{prefix}_team_num", None)
            if sid:
                players.add(sid)
            if sid and pd.notna(team) and int(team) in (2, 3):
                teams.setdefault((sid, rnd), int(team))
    players.discard("")
    if not players:
        return pd.DataFrame(), pd.DataFrame()
    players = sorted(players)
    round_ids = rounds["total_rounds_played"].astype(int).tolist()
    round_count = {sid: sum((sid, rnd) in teams for rnd in round_ids) for sid in players}
    for sid in players:
        if not round_count[sid]:
            round_count[sid] = len(round_ids)
    swing: dict[str, dict[int, float]] = {sid: {} for sid in players}
    counters: dict[str, dict[str, float]] = {
        sid: dict(kills=0, deaths=0, assists=0, damage=0, survived=0, kast=0, multi=0, hs=0)
        for sid in players
    }
    enemy_kill_flags = enemy_mask(kills) if not kills.empty else pd.Series(dtype=bool)
    if not kills.empty:
        kills = kills.copy()
        kills["is_enemy"] = enemy_kill_flags
    if not bombs.empty:
        bomb_ticks = bombs.groupby("total_rounds_played")["tick"].min().to_dict()
    else:
        bomb_ticks = {}
    trade_window = max(1, int(tick_rate) * 5)

    round_metrics = {}
    clock_status = rounds.set_index("total_rounds_played").metrics_clock_status.to_dict()
    for rnd in round_ids:
        before_counters = {sid: values.copy() for sid, values in counters.items()}
        ct = {sid for sid in players if teams.get((sid, rnd)) == 3}
        t = {sid for sid in players if teams.get((sid, rnd)) == 2}
        alive_ct = set(ct)
        alive_t = set(t)
        round_kills = (
            kills[kills["total_rounds_played"] == rnd].sort_values("tick", kind="stable")
            if not kills.empty else kills
        )
        round_damage = (
            damage[damage["total_rounds_played"] == rnd].sort_values("tick", kind="stable")
            if not damage.empty else damage
        )
        contributions: dict[str, dict[str, float]] = {}
        damage_rows = round_damage.to_dict("records")
        damage_index = 0
        active_kills: dict[str, int] = {}
        kast: set[str] = set()
        recent: list[tuple[int, str, str]] = []
        for event in round_kills.to_dict("records"):
            tick = int(event["tick"])
            while damage_index < len(damage_rows) and damage_rows[damage_index]["tick"] <= tick:
                hit = damage_rows[damage_index]
                attacker = _steamid(hit.get("attacker_steamid"))
                victim = _steamid(hit.get("user_steamid"))
                amount = float(hit["enemy_damage"])
                if attacker in counters:
                    counters[attacker]["damage"] += amount
                if attacker and victim and amount > 0:
                    per_victim = contributions.setdefault(victim, {})
                    per_victim[attacker] = per_victim.get(attacker, 0.0) + amount
                damage_index += 1
            attacker = _steamid(event.get("attacker_steamid"))
            victim = _steamid(event.get("user_steamid"))
            if not victim or victim not in counters:
                continue
            if victim not in alive_ct and victim not in alive_t:
                continue
            planted = rnd in bomb_ticks and tick >= bomb_ticks[rnd]
            before = _ct_wp(len(alive_ct), len(alive_t), planted)
            alive_ct.discard(victim)
            alive_t.discard(victim)
            after = _ct_wp(len(alive_ct), len(alive_t), planted)
            counters[victim]["deaths"] += 1
            enemy_kill = bool(event.get("is_enemy", False)) and attacker in counters
            if not enemy_kill:
                _add_swing(swing, victim, rnd, -abs(after - before) * 100)
                continue
            attacker_is_ct = teams.get((attacker, rnd)) == 3
            delta = (after - before) * 100 if attacker_is_ct else (before - after) * 100
            delta = max(0.0, delta)
            trade_sid = ""
            traded_sids = set()
            for previous_tick, previous_victim, previous_killer in reversed(recent):
                if tick - previous_tick > trade_window:
                    break
                same_team = teams.get((previous_victim, rnd)) == teams.get((attacker, rnd))
                if (0 < tick - previous_tick <= trade_window and previous_killer == victim
                        and same_team and previous_victim != attacker):
                    traded_sids.add(previous_victim)
                    # Keep the existing swing allocation to the most recent death.
                    if not trade_sid:
                        trade_sid = previous_victim
            assister = _steamid(event.get("assister_steamid"))
            if assister not in counters or teams.get((assister, rnd)) != teams.get((attacker, rnd)):
                assister = ""
            flash_sid = assister if bool(event.get("assistedflash", False)) else ""
            weights = {"kill": _W_KILL, "damage": _W_DAMAGE}
            if flash_sid:
                weights["flash"] = _W_FLASH
            if trade_sid:
                weights["trade"] = _W_TRADE
            total_weight = sum(weights.values())
            weights = {key: weight / total_weight for key, weight in weights.items()}
            _add_swing(swing, attacker, rnd, delta * weights["kill"])
            victim_damage = contributions.get(victim, {})
            total_damage = sum(victim_damage.values())
            if total_damage:
                for sid, amount in victim_damage.items():
                    _add_swing(swing, sid, rnd, delta * weights["damage"] * amount / total_damage)
                    if sid != attacker and amount >= 40:
                        kast.add(sid)
            else:
                _add_swing(swing, attacker, rnd, delta * weights["damage"])
            if flash_sid:
                _add_swing(swing, flash_sid, rnd, delta * weights["flash"])
            if trade_sid:
                _add_swing(swing, trade_sid, rnd, delta * weights["trade"])
            kast.update(traded_sids)
            if assister:
                counters[assister]["assists"] += 1
                kast.add(assister)
            counters[attacker]["kills"] += 1
            if bool(event.get("headshot", False)):
                counters[attacker]["hs"] += 1
            active_kills[attacker] = active_kills.get(attacker, 0) + 1
            kast.add(attacker)
            _add_swing(swing, victim, rnd, -delta)
            recent.append((tick, victim, attacker))
        while damage_index < len(damage_rows):
            hit = damage_rows[damage_index]
            attacker = _steamid(hit.get("attacker_steamid"))
            if attacker in counters:
                counters[attacker]["damage"] += float(hit["enemy_damage"])
            damage_index += 1
        for sid in alive_ct | alive_t:
            counters[sid]["survived"] += 1
            kast.add(sid)
        for sid in kast:
            counters[sid]["kast"] += 1
        for sid, count in active_kills.items():
            if count >= 2:
                counters[sid]["multi"] += 1
        for sid in players:
            swing[sid].setdefault(rnd, 0.0)
            delta_stats = {
                key: value - before_counters[sid][key]
                for key, value in counters[sid].items()
            }
            utility = sum(
                float(hit.get("utility_damage", 0)) for hit in damage_rows
                if _steamid(hit.get("attacker_steamid")) == sid
            )
            round_metrics[(sid, rnd)] = {
                "kills": int(delta_stats["kills"]), "deaths": int(delta_stats["deaths"]),
                "assists": int(delta_stats["assists"]), "damage": delta_stats["damage"],
                "hs_kills": int(delta_stats["hs"]), "utility_damage": utility,
                "kast": int(delta_stats["kast"]), "survived": int(delta_stats["survived"]),
                "team_num": teams.get((sid, rnd), 0),
                "metrics_clock_status": clock_status[rnd],
            }

    summary_rows = []
    round_rows = []
    for sid in players:
        c = counters[sid]
        n = round_count[sid]
        k = int(c["kills"])
        d = int(c["deaths"])
        a = int(c["assists"])
        kpr = k / n
        dpr = d / n
        adr = c["damage"] / n
        kast_pct = c["kast"] / n * 100
        multi_pr = c["multi"] / n
        avg_swing = sum(swing[sid].values()) / n
        sub_kill = kpr / .63
        sub_damage = adr / 75
        sub_survival = max(0.0, 1 - dpr) / .37
        sub_kast = kast_pct / 70
        sub_multi = max(0.0, min(2.5, 1 + (multi_pr - .08) * 5))
        sub_swing = max(.15, min(2.5, 1 + avg_swing / 15))
        rating = (
            .20 * sub_kill + .10 * sub_damage + .15 * sub_survival
            + .25 * sub_kast + .10 * sub_multi + .20 * sub_swing
        )
        first_side = next((teams[(sid, rnd)] for rnd in round_ids if (sid, rnd) in teams), 0)
        summary_rows.append({
            "Gracz": names.get(sid, sid),
            "Strona": "CT" if first_side == 3 else "T" if first_side == 2 else "?",
            "Rating": round(rating, 2),
            "Kill": round(sub_kill, 2), "Dmg": round(sub_damage, 2),
            "Surv": round(sub_survival, 2), "KAST": round(sub_kast, 2),
            "Multi": round(sub_multi, 2), "Swing": round(sub_swing, 2),
            "K": k, "A": a, "D": d,
            "K/D": round(k / d, 2) if d else float(k),
            "ADR": round(adr, 1), "KPR": round(kpr, 2), "DPR": round(dpr, 2),
            "HS%": round(c["hs"] / k * 100, 1) if k else 0.0,
            "KAST%": round(kast_pct, 1), "Avg Swing": round(avg_swing, 2),
            "steamid": sid,
            "Rounds": n,
        })
        for rnd in round_ids:
            if any((sid, round_id) in teams for round_id in round_ids) and (sid, rnd) not in teams:
                continue
            round_rows.append({
                "Gracz": names.get(sid, sid), "Runda": rnd,
                "Swing": round(swing[sid][rnd], 2), "steamid": sid,
                **round_metrics[(sid, rnd)],
            })
    summary = (
        pd.DataFrame(summary_rows).sort_values("Rating", ascending=False).reset_index(drop=True)
    )
    return summary, pd.DataFrame(round_rows)


def round_stats_from_rating(per_round: pd.DataFrame) -> pd.DataFrame:
    """The same round counters feed charts, summary metrics and coaching data."""
    if per_round.empty:
        return pd.DataFrame()
    columns = [
        "steamid", "Runda", "kills", "deaths", "assists", "damage", "hs_kills",
        "utility_damage", "kast", "survived", "team_num",
    ]
    return per_round[[c for c in columns if c in per_round]].rename(
        columns={"Runda": "total_rounds_played"}
    ).copy()
