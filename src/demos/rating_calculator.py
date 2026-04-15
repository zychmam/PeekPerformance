"""Approximate Rating calculator (Leetify-style Round Swing + HLTV 3.0 sub-ratings).

Uses win-probability model based on alive counts and bomb state.
Credit distribution follows Leetify: 35% kill / 30% damage / 15% flash / 20% trade.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from demoparser2 import DemoParser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Win probability model (CT round-win %, approximate pro CS2 data)
# ---------------------------------------------------------------------------

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

for _i in range(6):
    _WP_PRE[(_i, 0)] = 1.0
    _WP_PRE[(0, _i)] = 0.0
    _WP_POST[(_i, 0)] = 1.0
    _WP_POST[(0, _i)] = 0.0
_WP_PRE[(0, 0)] = 0.5
_WP_POST[(0, 0)] = 0.0  # bomb planted, no CTs = T wins


def _ct_wp(ct_alive: int, t_alive: int, bomb_planted: bool) -> float:
    ct = max(0, min(5, ct_alive))
    t = max(0, min(5, t_alive))
    return (_WP_POST if bomb_planted else _WP_PRE).get((ct, t), 0.5)


# ---------------------------------------------------------------------------
# Leetify credit weights
# ---------------------------------------------------------------------------

_W_KILL = 0.35
_W_DAMAGE = 0.30
_W_FLASH = 0.15
_W_TRADE = 0.20

_TRADE_TICKS = 5 * 64  # 5 seconds at 64 tick


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_rating(demo_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute approximate player ratings from a demo file.

    Returns:
        (summary_df, round_df)
        summary_df: per-player rating with all sub-ratings
        round_df: per-player per-round swing values
    """
    parser = DemoParser(str(demo_path))

    player_info = parser.parse_player_info()
    kills = parser.parse_event(
        "player_death",
        player=["team_num"],
        other=["total_rounds_played"],
    )
    damage = parser.parse_event("player_hurt", other=["total_rounds_played"])
    rounds_ev = parser.parse_event("round_end", other=["total_rounds_played"])

    try:
        bomb_ev = parser.parse_event("bomb_planted", other=["total_rounds_played"])
    except Exception:
        bomb_ev = pd.DataFrame()

    if kills.empty or rounds_ev.empty:
        return pd.DataFrame(), pd.DataFrame()

    # --- Name map (player_info steamid is int, kills steamid is str) ---
    name_map: dict[str, str] = {}
    if not player_info.empty:
        for _, r in player_info.iterrows():
            name_map[str(r["steamid"])] = r["name"]

    # --- Build team assignments per (steamid, round) ---
    player_team: dict[tuple[str, int], int] = {}  # (steamid, round) -> 2=T / 3=CT
    for _, k in kills.iterrows():
        rnd = int(k["total_rounds_played"])
        for prefix, sid_col in [("attacker", "attacker_steamid"), ("user", "user_steamid")]:
            sid = k.get(sid_col, "")
            team_col = f"{prefix}_team_num"
            if sid and str(sid) != "0" and team_col in k.index and pd.notna(k[team_col]):
                player_team[(str(sid), rnd)] = int(k[team_col])

    all_players = sorted({str(sid) for sid, _ in player_team.keys()})
    all_rounds = sorted(r for r in rounds_ev["total_rounds_played"].unique() if r > 0)
    n_rounds = len(all_rounds)

    if not all_players or n_rounds == 0:
        return pd.DataFrame(), pd.DataFrame()

    # Filter out knife round (round 0) from data
    kills = kills[kills["total_rounds_played"] > 0]
    damage = damage[damage["total_rounds_played"] > 0]

    # Fill missing round assignments by nearest known round
    for sid in all_players:
        known = {rnd: team for (s, rnd), team in player_team.items() if s == sid}
        if not known:
            continue
        sorted_known = sorted(known.keys())
        for rnd in all_rounds:
            if (sid, rnd) not in player_team:
                nearest = min(sorted_known, key=lambda r: abs(r - rnd))
                player_team[(sid, rnd)] = known[nearest]

    # Bomb planted ticks per round
    bomb_ticks: dict[int, int] = {}
    if not bomb_ev.empty:
        for _, b in bomb_ev.iterrows():
            bomb_ticks[int(b["total_rounds_played"])] = int(b["tick"])

    # --- Accumulators ---
    player_swing: dict[str, dict[int, float]] = {sid: {} for sid in all_players}
    p_kills: dict[str, int] = {sid: 0 for sid in all_players}
    p_deaths: dict[str, int] = {sid: 0 for sid in all_players}
    p_damage: dict[str, float] = {sid: 0.0 for sid in all_players}
    p_assists: dict[str, int] = {sid: 0 for sid in all_players}
    p_survived: dict[str, int] = {sid: 0 for sid in all_players}
    p_kast: dict[str, int] = {sid: 0 for sid in all_players}
    p_multikill: dict[str, int] = {sid: 0 for sid in all_players}
    p_hs: dict[str, int] = {sid: 0 for sid in all_players}

    # --- Round-by-round computation ---
    for rnd in all_rounds:
        rnd_kills = kills[kills["total_rounds_played"] == rnd].sort_values("tick")
        rnd_damage = damage[damage["total_rounds_played"] == rnd]

        ct_set = {sid for sid in all_players if player_team.get((sid, rnd)) == 3}
        t_set = {sid for sid in all_players if player_team.get((sid, rnd)) == 2}

        ct_alive = set(ct_set)
        t_alive = set(t_set)
        bomb_planted = False

        # Damage map: victim -> {attacker: total_actual_dmg}
        # Track victim HP (start at 100) to cap overkill damage
        dmg_map: dict[str, dict[str, float]] = {}
        victim_hp: dict[str, int] = {}
        for _, d in rnd_damage.sort_values("tick").iterrows():
            victim = str(d.get("user_steamid", ""))
            attacker = str(d.get("attacker_steamid", ""))
            raw_dmg = int(d.get("dmg_health", 0))
            if not victim or not attacker or victim == attacker or victim == "0" or attacker == "0":
                continue
            hp = victim_hp.get(victim, 100)
            actual = min(raw_dmg, hp)
            victim_hp[victim] = hp - actual
            if actual > 0:
                dmg_map.setdefault(victim, {})[attacker] = (
                    dmg_map.get(victim, {}).get(attacker, 0) + actual
                )
                if attacker in p_damage:
                    p_damage[attacker] += actual

        # Per-round kill counts + trade detection state
        rnd_kill_count: dict[str, int] = {}
        recent_deaths: list[tuple[int, str, str]] = []  # (tick, victim, killer)
        kast_set: set[str] = set()

        for k_row in rnd_kills.itertuples():
            attacker = str(getattr(k_row, "attacker_steamid", ""))
            victim = str(getattr(k_row, "user_steamid", ""))
            tick = int(getattr(k_row, "tick", 0))
            headshot = bool(getattr(k_row, "headshot", False))
            flash_assisted = bool(getattr(k_row, "assistedflash", False))
            assister_sid = str(getattr(k_row, "assister_steamid", "") or "")

            if not attacker or attacker == "0" or not victim or victim == "0":
                ct_alive.discard(victim)
                t_alive.discard(victim)
                continue

            if attacker == victim:
                ct_alive.discard(victim)
                t_alive.discard(victim)
                if victim in all_players:
                    p_deaths[victim] += 1
                continue

            # Check bomb planted before this kill
            if rnd in bomb_ticks and tick >= bomb_ticks[rnd]:
                bomb_planted = True

            # Win probability BEFORE kill
            wp_before = _ct_wp(len(ct_alive), len(t_alive), bomb_planted)

            # Remove victim from alive
            ct_alive.discard(victim)
            t_alive.discard(victim)

            # Win probability AFTER kill
            wp_after = _ct_wp(len(ct_alive), len(t_alive), bomb_planted)

            # Delta from attacker's perspective (positive = good for attacker)
            attacker_is_ct = attacker in ct_set
            if attacker_is_ct:
                delta = (wp_after - wp_before) * 100
            else:
                delta = (wp_before - wp_after) * 100

            # --- Credit distribution ---
            # Trade detection: was victim's killer killed within 5s by victim's team?
            trade_sid = ""
            for d_tick, d_victim, d_killer in recent_deaths:
                if d_killer == victim and tick - d_tick <= _TRADE_TICKS:
                    trade_sid = d_victim  # traded player gets credit
                    break

            flash_sid = assister_sid if flash_assisted and assister_sid and assister_sid != "0" else ""

            victim_dmg = dmg_map.get(victim, {})
            total_dmg = sum(victim_dmg.values())

            # Active components (damage always active since killer always deals damage)
            weights: dict[str, float] = {"kill": _W_KILL, "damage": _W_DAMAGE}
            if flash_sid:
                weights["flash"] = _W_FLASH
            if trade_sid:
                weights["trade"] = _W_TRADE

            # Scale to sum = 1.0
            w_sum = sum(weights.values())
            for key in weights:
                weights[key] /= w_sum

            # Kill credit -> attacker
            if attacker in all_players:
                _add_swing(player_swing, attacker, rnd, delta * weights["kill"])
                p_kills[attacker] += 1
                rnd_kill_count[attacker] = rnd_kill_count.get(attacker, 0) + 1
                kast_set.add(attacker)
                if headshot:
                    p_hs[attacker] += 1

            # Damage credit -> proportional among all who damaged victim
            if total_dmg > 0:
                for dmg_sid, dmg_val in victim_dmg.items():
                    if dmg_sid in all_players:
                        frac = dmg_val / total_dmg
                        _add_swing(player_swing, dmg_sid, rnd, delta * weights["damage"] * frac)
                        if dmg_val >= 40 and dmg_sid != attacker:
                            kast_set.add(dmg_sid)  # KAST: Assist (40+ dmg)
            else:
                # No damage data -> killer gets damage share too
                if attacker in all_players:
                    _add_swing(player_swing, attacker, rnd, delta * weights["damage"])

            # Assist credit (non-flash assister)
            if assister_sid and not flash_assisted and assister_sid in all_players and assister_sid != "0":
                p_assists[assister_sid] += 1
                kast_set.add(assister_sid)

            # Flash credit
            if flash_sid and flash_sid in all_players:
                _add_swing(player_swing, flash_sid, rnd, delta * weights["flash"])
                p_assists[flash_sid] += 1
                kast_set.add(flash_sid)

            # Trade credit
            if trade_sid and trade_sid in all_players:
                _add_swing(player_swing, trade_sid, rnd, delta * weights["trade"])
                kast_set.add(trade_sid)  # KAST: Traded

            # Death punishment -> victim
            if victim in all_players:
                _add_swing(player_swing, victim, rnd, -delta)
                p_deaths[victim] += 1

            recent_deaths.append((tick, victim, attacker))

        # Survival tracking
        for sid in ct_alive | t_alive:
            if sid in all_players:
                p_survived[sid] += 1
                kast_set.add(sid)  # KAST: Survived

        # KAST
        for sid in kast_set:
            if sid in all_players:
                p_kast[sid] += 1

        # Multi-kills
        for sid, cnt in rnd_kill_count.items():
            if cnt >= 2 and sid in all_players:
                p_multikill[sid] += 1

        # Initialize swing for players with no activity this round
        for sid in all_players:
            player_swing[sid].setdefault(rnd, 0.0)

    # --- Build summary DataFrame ---
    # Reference values: approximate CS2 pro averages (from HLTV stats pages)
    _AVG_KPR = 0.63
    _AVG_ADR = 75.0
    _AVG_SURV_RATE = 0.37  # ~37% survival rate (1 - 0.63 DPR)
    _AVG_KAST = 70.0       # ~70% KAST
    _AVG_MULTI_PR = 0.08   # ~8% rounds with multi-kill

    rows = []
    for sid in all_players:
        first_team = player_team.get((sid, all_rounds[0]), 0)
        team_label = "CT" if first_team == 3 else "T" if first_team == 2 else "?"

        k = p_kills[sid]
        d = p_deaths[sid]
        a = p_assists[sid]
        total_swing = sum(player_swing[sid].values())
        avg_swing = total_swing / n_rounds if n_rounds else 0.0

        kpr = k / n_rounds if n_rounds else 0.0
        dpr = d / n_rounds if n_rounds else 0.0
        adr = p_damage[sid] / n_rounds if n_rounds else 0.0
        kast_pct = p_kast[sid] / n_rounds * 100 if n_rounds else 0.0
        multi_pr = p_multikill[sid] / n_rounds if n_rounds else 0.0

        # HLTV Rating 3.0 — 6 sub-ratings, each centered ~1.0 for average
        kill_sr = kpr / _AVG_KPR
        dmg_sr = adr / _AVG_ADR
        surv_sr = (1.0 - dpr) / _AVG_SURV_RATE
        kast_sr = kast_pct / _AVG_KAST
        multi_sr = max(0.0, min(2.5, 1.0 + (multi_pr - _AVG_MULTI_PR) * 5))
        # Round Swing: pro season avg ~0, best ~+4%, single-map more volatile
        swing_sr = max(0.15, min(2.5, 1.0 + avg_swing / 15.0))

        # Combined rating — weights inspired by HLTV structure:
        # KAST historically heaviest, Kill & Swing significant, rest moderate
        hltv_rating = (
            0.20 * kill_sr
            + 0.10 * dmg_sr
            + 0.15 * surv_sr
            + 0.25 * kast_sr
            + 0.10 * multi_sr
            + 0.20 * swing_sr
        )

        rows.append({
            "Gracz": name_map.get(sid, sid),
            "Strona": team_label,
            "Rating": round(hltv_rating, 2),
            "Kill": round(kill_sr, 2),
            "Dmg": round(dmg_sr, 2),
            "Surv": round(surv_sr, 2),
            "KAST": round(kast_sr, 2),
            "Multi": round(multi_sr, 2),
            "Swing": round(swing_sr, 2),
            "K": k,
            "A": a,
            "D": d,
            "K/D": round(k / d, 2) if d > 0 else float(k),
            "ADR": round(adr, 1),
            "KPR": round(kpr, 2),
            "DPR": round(dpr, 2),
            "HS%": round(p_hs[sid] / k * 100, 1) if k > 0 else 0.0,
            "KAST%": round(kast_pct, 1),
            "Avg Swing": round(avg_swing, 2),
            "steamid": sid,
        })

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values("Rating", ascending=False).reset_index(drop=True)

    # --- Build per-round DataFrame ---
    round_rows = []
    for sid in all_players:
        name = name_map.get(sid, sid)
        for rnd in all_rounds:
            round_rows.append({
                "Gracz": name,
                "Runda": int(rnd),
                "Swing": round(player_swing[sid].get(rnd, 0.0), 2),
            })
    round_df = pd.DataFrame(round_rows)

    return summary, round_df


def _add_swing(
    swing: dict[str, dict[int, float]],
    steamid: str,
    rnd: int,
    value: float,
) -> None:
    swing[steamid][rnd] = swing[steamid].get(rnd, 0.0) + value
