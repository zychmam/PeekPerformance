"""Local saved inputs -> tactical contract with observed R2 early preparation."""

from __future__ import annotations

import pandas as pd

from src.demos.bomb_coverage import combined_coverage
from src.demos.early_interpretation import INTERPRETATION_VERSION
from src.demos.early_round import (
    CONFIRM_TICKS,
    EARLY_DETECTOR_VERSION,
    MAX_AGE,
    MAX_GAP,
    enrich_early_round,
)
from src.demos.observations import EFFECTS
from src.demos.round_alive import ALIVE_DETECTOR_VERSION, assign_opening, build_alive_states
from src.demos.round_contacts import (
    CONTACT_DETECTOR_VERSION,
    assign_first_contacts,
    build_round_contacts,
)
from src.demos.round_index import round_state_index
from src.demos.round_refrags import REFRAG_DETECTOR_VERSION, enrich_refrags
from src.demos.round_moments import MOMENTS_VERSION, build_round_moments
from src.demos.tactical_evidence import collect_evidence
from src.maps.registry import get_profile
from src.maps.resolver import resolve_region
from src.models.models import DemoAnalysis
from src.models.observations import DetectorConfig, RoundClock
from src.models.tactical import (
    Availability,
    Episode,
    Evidence,
    PlayerRound,
    Preparation,
    RoundTactics,
    Status,
    TacticalMatch,
)
from src.storage.database import Database

REQUIRED = {
    "kills": {"tick", "attacker_steamid", "user_steamid", "attacker_team_num", "user_team_num"},
    "damage": {"tick", "attacker_steamid", "user_steamid", "enemy_damage"},
    "bombs": {"tick", "event"},
    "blinds": {"tick", "attacker_steamid", "user_steamid", "blind_duration"},
    "utility": {"tick", "kind", "user_steamid", "user_team_num", "x", "y", "z"},
    "states": {"tick", "steamid", "team_num", "is_alive", "X", "Y", "Z", "last_place_name"},
    "shots": {"tick", "user_steamid", "weapon"},
    "smokes": {"tick", "entityid"},
    "equipment": {"tick", "steamid", "team_num"},
    "economy": {"tick", "steamid", "team_num"},
    "throws": {"tick", "user_steamid", "kind"},
    "utility_lifecycles": {"tick", "kind"},
    "bomb_updates": {"tick", "event"},
}
CAPABILITY_INPUTS = {
    "early_preparation": ("clock", "states", "utility"),
    "fights": ("clock", "states", "kills", "damage"),
    "utility_effects": ("utility", "blinds", "damage"),
    "entry_context": ("clock", "states"),
    "rotation_from_contact": ("clock", "states", "damage"),
    "plant_defuse": ("clock", "bombs"),
    "retake": ("clock", "states", "bombs", "kills"),
}


def _capabilities(sources: dict[str, Availability]) -> dict[str, Availability]:
    result = {}
    for name, required in CAPABILITY_INPUTS.items():
        unknown = [key for key in required if sources[key].status == Status.UNKNOWN]
        partial = [key for key in required if sources[key].status == Status.PARTIAL]
        result[name] = Availability(
            Status.UNKNOWN if unknown else Status.PARTIAL if partial else Status.OBSERVED,
            [f"Unknown inputs: {', '.join(unknown)}"]
            if unknown
            else (
                [f"Partial inputs: {', '.join(partial)}"]
                if partial
                else ["Required inputs observed; detection not executed or validated by this flag."]
            ),
        )
    return result


def _team_sets(roster: pd.DataFrame) -> tuple[dict, dict]:
    """Exact roster identity across side switches. Changed membership stays unknown."""
    if not {"total_rounds_played", "team_num", "steamid"}.issubset(roster):
        return {}, {}
    teams = {}
    per_round = {}
    for rnd, group in roster.groupby("total_rounds_played", sort=True):
        sides = {
            side: sorted(set(group[group.team_num.eq(team)].steamid.dropna().astype(str)))
            for side, team in (("T", 2), ("CT", 3))
        }
        if (
            not teams
            and all(len(ids) == 5 for ids in sides.values())
            and not (set(sides["T"]) & set(sides["CT"]))
        ):
            teams = {"team_1": sides["T"], "team_2": sides["CT"]}
        per_round[int(rnd)] = {
            side: next((tid for tid, members in teams.items() if ids == members), None)
            for side, ids in sides.items()
        }
    return teams, per_round


def _availability(source: str, frame: pd.DataFrame, diagnosed: bool) -> Availability:
    missing = sorted(REQUIRED[source] - set(frame))
    if frame.empty:
        return Availability(
            Status.ABSENT if diagnosed else Status.UNKNOWN,
            [] if diagnosed else ["Empty source without diagnostics is not a verified zero."],
            missing,
        )
    nulls = [col for col in REQUIRED[source] & set(frame) if frame[col].isna().any()]
    if missing or nulls:
        return Availability(
            Status.PARTIAL, [f"Null values: {', '.join(sorted(nulls))}"] if nulls else [], missing
        )
    return Availability(
        Status.OBSERVED, ["Source completeness is not proven."] if not diagnosed else []
    )


def build_tactical_match(
    analysis: DemoAnalysis,
    spatial=None,
    *,
    foundations=None,
    config=None,
    profile=None,
    cached_actions=None,
) -> TacticalMatch:
    config = config or DetectorConfig()
    profile = profile or getattr(spatial, "profile", None) or get_profile(analysis.map_name)
    rounds = analysis.rounds_df
    required_rounds = {"total_rounds_played", "start_tick", "tick"}
    if not required_rounds.issubset(rounds):
        raise ValueError("Round boundaries are required")
    if rounds[list(required_rounds)].isna().any().any():
        raise ValueError("Round boundaries contain missing values")
    collected = collect_evidence(analysis, spatial)
    frames, clocks, bounds, evidence, evidence_by_round, state_index = collected
    from src.demos.coach_foundations import build_foundations

    if foundations is None:
        foundations, _ = build_foundations(analysis, spatial, collected=collected)
    teams, team_rounds = _team_sets(analysis.round_roster_df)
    result = []
    spatial_states = getattr(spatial, "states", pd.DataFrame())
    assigned = (
        {str(row["event_id"]): row.get("region_id") for row in spatial_states.to_dict("records")}
        if "event_id" in spatial_states
        else {}
    )
    for row in rounds.itertuples():
        rnd = int(row.total_rounds_played)
        start, end = bounds[rnd]
        freeze = clocks.get(rnd)
        freeze = int(freeze) if pd.notna(freeze) else None
        clock_frame = getattr(spatial, "clock", pd.DataFrame())
        clock_row = (
            clock_frame[clock_frame.total_rounds_played.eq(rnd)].iloc[0].to_dict()
            if not clock_frame.empty
            else {
                "total_rounds_played": rnd,
                "start_tick": start,
                "freeze_tick": freeze,
                "tick": end,
            }
        )
        round_clock = RoundClock.from_row(clock_row)
        rate = round_clock.tick_rate
        sides = team_rounds.get(rnd, {"T": None, "CT": None})
        winner = {2: "T", 3: "CT", "T": "T", "CT": "CT"}.get(getattr(row, "winner", None))
        availability = {}
        for source, frame in frames.items():
            part = (
                frame[frame.total_rounds_played.eq(rnd)]
                if "total_rounds_played" in frame
                else pd.DataFrame()
            )
            diagnosed = (
                source == "utility"
                and spatial is not None
                and all(
                    spatial.diagnostics.get("sources", {}).get(event) in {"ok", "absent"}
                    for event in EFFECTS
                )
            )
            availability[source] = _availability(source, part, diagnosed)
            if source == "utility" and spatial and not part.empty:
                failures = [
                    event
                    for event in EFFECTS
                    if spatial.diagnostics.get("sources", {}).get(event, "").startswith("error:")
                ]
                if failures:
                    availability[source].status = Status.PARTIAL
                    availability[source].reasons.append(
                        f"Failed utility sources: {', '.join(failures)}",
                    )
        availability["clock"] = Availability(
            Status.OBSERVED if freeze is not None else Status.UNKNOWN,
        )
        availability["team_identity"] = Availability(
            Status.OBSERVED if all(sides.values()) else Status.UNKNOWN,
            [] if all(sides.values()) else ["Incomplete/changed roster; unknown team identity."],
        )
        availability["visibility"] = Availability(Status.UNKNOWN, ["Not collected."])
        availability["bomb_movement"] = Availability(
            Status.PARTIAL
            if any(availability[s].status == Status.OBSERVED for s in ("states", "bombs"))
            else Status.UNKNOWN,
            [
                "Carrier samples and plant/defuse only; pickup/drop events are not persisted.",
            ],
        )
        states = frames["states"]
        if not states.empty and {"total_rounds_played", "steamid", "tick"}.issubset(states):
            part = states[states.total_rounds_played.eq(rnd)]
            roster = analysis.round_roster_df
            expected = set()
            if {"total_rounds_played", "steamid", "team_num"}.issubset(roster):
                expected = set(
                    roster[
                        roster.total_rounds_played.eq(rnd) & roster.team_num.isin([2, 3])
                    ].steamid.astype(str)
                )
            gaps = not expected or not expected.issubset(set(part.steamid.astype(str)))
            for _, samples in part.groupby("steamid"):
                ticks = samples.tick.sort_values()
                gaps |= (
                    freeze is None
                    or ticks.min() > freeze + round_clock.ticks(config.max_sample_age_seconds)
                    or ticks.max() < end - round_clock.ticks(config.max_sample_age_seconds)
                    or ticks.diff().gt(round_clock.ticks(config.max_sample_gap_seconds)).any()
                )
            if gaps and not part.empty:
                availability["states"].status = Status.PARTIAL
                availability["states"].reasons.append("Missing roster members or sampling gaps.")
        ids = sorted(evidence_by_round[rnd], key=lambda eid: evidence[eid].tick)
        # Sorting equal ticks is presentation-only; cross-source causality is unknown.
        early_end = (
            min(end, freeze + round_clock.ticks(config.early_seconds))
            if freeze is not None
            else None
        )
        preparations = []
        for team in (2, 3):
            preparations.append(
                Preparation(
                    status=Status.NOT_EVALUATED if freeze is not None else Status.UNKNOWN,
                    start_tick=freeze,
                    end_tick=early_end,
                    ten_second_tick=min(end, freeze + round_clock.ticks(10))
                    if freeze is not None
                    else None,
                    snapshot_ids=[
                        eid
                        for eid in ids
                        if freeze is not None
                        and freeze <= evidence[eid].tick <= early_end
                        and evidence[eid].source == "states"
                        and evidence[eid].data.get("team_num") == team
                    ],
                    utility_ids=[
                        eid
                        for eid in ids
                        if freeze is not None
                        and freeze <= evidence[eid].tick <= early_end
                        and evidence[eid].source == "utility"
                        and evidence[eid].data.get("user_team_num") == team
                    ],
                )
            )
        roster = analysis.round_roster_df
        players = []
        if {"total_rounds_played", "team_num", "steamid"}.issubset(roster):
            for p in roster[roster.total_rounds_played.eq(rnd)].itertuples():
                side = {2: "T", 3: "CT"}.get(p.team_num)
                players.append(PlayerRound(str(p.steamid), sides.get(side), side))
        rr = RoundTactics(
            rnd,
            start,
            end,
            freeze,
            sides,
            winner,
            sides.get(winner),
            str(getattr(row, "reason", "")) or None,
            availability,
            ids,
            preparations[0],
            preparations[1],
            players=players,
            bomb_event_ids=[
                eid for eid in ids if evidence[eid].source in {"bombs", "bomb_updates"}
            ],
            capabilities=_capabilities(availability),
        )
        for capability, required in {
            "early_preparation": ("regions",),
            "entry_context": ("site_boundaries",),
            "rotation_from_contact": ("regions",),
            "retake": ("site_boundaries",),
        }.items():
            if profile is None or not profile.supports(*required):
                rr.capabilities[capability] = Availability(
                    Status.UNKNOWN,
                    ["Required map capabilities unavailable: " + ", ".join(required)],
                )
        for entry in getattr(spatial, "entries", []):
            if entry["round"] != rnd:
                continue
            refs = [
                state_index.get((rnd, p["steamid"], p[key]))
                for p in entry["participants"]
                for key in ("previous_tick", "tick", "confirmed_tick")
            ]
            known = list(dict.fromkeys(ref for ref in refs if ref))
            if known:
                rr.observed_entries.append(
                    Episode(
                        entry["id"],
                        "site_entry",
                        int(entry["tick"]),
                        max(p["confirmed_tick"] for p in entry["participants"]),
                        [p["steamid"] for p in entry["participants"]],
                        known,
                        status=Status.OBSERVED if all(refs) else Status.PARTIAL,
                        area=entry["site"],
                    )
                )
        early_evidence = dict(evidence)
        for eid in rr.t_preparation.snapshot_ids + rr.ct_setup.snapshot_ids:
            event = evidence[eid]
            rid = assigned.get(eid) or resolve_region(event.data, profile)
            early_evidence[eid] = Evidence(
                event.id,
                event.source,
                event.round_number,
                event.tick,
                event.seconds,
                {**event.data, "region_id": rid},
            )
        enrich_early_round(
            rr, early_evidence, analysis.map_name, profile=profile, config=config, tick_rate=rate
        )
        rr.foundation = foundations.get(rnd)
        if rr.foundation:
            for side, prep in (("T", rr.t_preparation), ("CT", rr.ct_setup)):
                from copy import deepcopy

                snap = deepcopy(rr.foundation.setup_before_contact.get(side))
                if snap:
                    snap.counts = {}
                    for player in snap.players:
                        refs = [
                            eid
                            for eid in snap.evidence_ids
                            if str(evidence[eid].data.get("steamid")) == player["player_id"]
                        ]
                        rid = (
                            (
                                assigned.get(refs[0])
                                or resolve_region(evidence[refs[0]].data, profile)
                            )
                            if refs
                            else None
                        )
                        player["area"] = rid if player["alive"] else None
                        if player["alive"] and rid:
                            snap.counts[rid] = snap.counts.get(rid, 0) + 1
                        elif player["alive"]:
                            snap.missing_players.append(player["player_id"])
                    snap.missing_players = sorted(set(snap.missing_players))
                    if snap.missing_players:
                        snap.status = Status.PARTIAL
                prep.setup_before_contact = snap
                team = 2 if side == "T" else 3
                prep.thrown_utility_ids = [
                    eid
                    for eid in rr.foundation.thrown_utility_ids
                    if freeze is not None
                    and freeze
                    <= evidence[eid].tick
                    <= min(end, freeze + round_clock.ticks(config.early_seconds))
                    and evidence[eid].data.get("user_team_num") == team
                ]
                prep.utility_windows = (
                    {
                        str(seconds): {
                            "throws": [
                                eid
                                for eid in prep.thrown_utility_ids
                                if evidence[eid].tick <= freeze + round_clock.ticks(seconds)
                            ],
                            "effects": [
                                eid
                                for eid in prep.utility_ids
                                if evidence[eid].tick <= freeze + round_clock.ticks(seconds)
                            ],
                        }
                        for seconds in (10, 15)
                    }
                    if freeze is not None
                    else {}
                )
            for source, quality in rr.foundation.source_quality.items():
                rr.availability[source] = quality.availability
            rr.availability["bombs"] = combined_coverage(rr)
            if rr.foundation.source_quality["bomb_pickup"].read_status == "ok":
                rr.availability["bomb_movement"] = Availability(
                    Status.PARTIAL,
                    ["Observed pickup/drop events and carrier samples; gaps remain explicit."],
                )
        indexed_states = round_state_index(rr, evidence)
        rr.contacts, rr.contacts_status = build_round_contacts(
            rr, evidence, tick_rate=rate, config=config, areas=assigned if profile else None,
            state_index=indexed_states,
        )
        assign_first_contacts(rr, evidence)
        assign_opening(rr, evidence)
        rr.alive_states, rr.alive_status = build_alive_states(
            rr, evidence, tick_rate=rate, config=config, state_index=indexed_states,
        )
        enrich_refrags(rr, evidence, tick_rate=rate, response_seconds=config.refrag_seconds)
        rr.moments = build_round_moments(rr, evidence)
        from src.demos.tactical_actions import TACTICAL_ACTIONS_VERSION, enrich_actions
        enrich_actions(rr, evidence, profile, tick_rate=rate, config=config,
                       state_index=indexed_states,
                       cached=(cached_actions or {}).get(rnd))
        result.append(rr)
    match = TacticalMatch(
        analysis.content_hash, analysis.map_name, analysis.analysis_version, result, evidence, teams
    )
    match.parameters.update(
        tactical_actions_version=TACTICAL_ACTIONS_VERSION,
        early_detector_version=EARLY_DETECTOR_VERSION,
        early_interpretation_version=INTERPRETATION_VERSION,
        contact_detector_version=CONTACT_DETECTOR_VERSION,
        alive_detector_version=ALIVE_DETECTOR_VERSION,
        refrag_detector_version=REFRAG_DETECTOR_VERSION,
        moments_version=MOMENTS_VERSION,
        response_seconds=config.refrag_seconds,
        snapshot_max_age_ticks=MAX_AGE,
        movement_max_gap_ticks=MAX_GAP,
        movement_confirm_ticks=CONFIRM_TICKS,
    )
    match.parameters.update(
        detector_config=config.fingerprint,
        profile_fingerprint=profile.semantic_fingerprint if profile else None,
        tick_rate_assumption=None,
        clocks={str(r.number): r.foundation.clock if r.foundation else {} for r in result},
    )
    match.validate()
    return match


def load_tactical_match(db: Database, demo_id: str, round_number=None) -> TacticalMatch:
    """Read current saved stages without opening a demo or converting old formats."""
    from src.demos.coach_foundations import decode_foundation, foundation_key
    from src.demos.spatial_service import read_context, round_analysis

    analysis = db.get_demo_analysis(demo_id, include_auxiliary=False)
    if analysis is None:
        raise ValueError("Unknown demo")
    spatial = read_context(db, analysis, round_number)
    saved = db.get_stage_rounds(demo_id, "foundations", foundation_key(analysis), round_number)
    foundations = {number: decode_foundation(value)[0] for number, value in saved.items()}
    if round_number is not None:
        analysis = round_analysis(analysis, round_number)
    return build_tactical_match(analysis, spatial, foundations=foundations or None,
                               cached_actions=getattr(spatial, "tactical_actions", None))
