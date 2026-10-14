"""One preparation per match; UI filters aggregate compact saved round facts."""

from src.demos.map_round_facts import ROUND_FACTS_VERSION, build_round_fact
from src.maps.registry import get_profile
from src.models.observations import DetectorConfig, canonical_fingerprint


def round_facts_key(analysis, profile=None):
    from src.demos.early_interpretation import INTERPRETATION_VERSION
    from src.demos.early_round import EARLY_DETECTOR_VERSION
    from src.demos.tactical_actions import actions_key

    return canonical_fingerprint(
        {
            "actions": actions_key(analysis, profile or get_profile(analysis.map_name)),
            "round_facts": ROUND_FACTS_VERSION,
            "early": EARLY_DETECTOR_VERSION,
            "interpretation": INTERPRETATION_VERSION,
        }
    )


def get_map_round_facts(db, manager, analysis):
    from src.demos.spatial_service import _context_lock, get_spatial_context
    from src.demos.tactical_rounds import build_tactical_match

    key = round_facts_key(analysis)
    numbers = sorted(analysis.rounds_df.total_rounds_played.astype(int).tolist())
    with _context_lock(db._db_path, analysis.content_hash):
        saved = db.get_stage_rounds(analysis.content_hash, "map_round_facts", key)
        if sorted(saved) == numbers:
            return list(saved.values())
        context = get_spatial_context(db, manager, analysis)
        match = build_tactical_match(
            analysis,
            context,
            foundations=context.foundations,
            cached_actions=context.tactical_actions,
        )
        metadata = {
            int(row["total_rounds_played"]): row for row in analysis.rounds_df.to_dict("records")
        }
        facts = {
            record.number: build_round_fact(
                record,
                match.evidence,
                context.profile,
                metadata=metadata[record.number],
                early_seconds=DetectorConfig().early_seconds,
            )
            for record in match.rounds
        }
        if sorted(context.tactical_actions) != numbers:
            context.persist_tactical_actions(match.rounds)
        db.save_stages(
            analysis.content_hash,
            {
                "map_round_facts": (
                    key,
                    {
                        "demo_id": analysis.content_hash,
                        "cache_key": key,
                        "round_numbers": numbers,
                        "version": ROUND_FACTS_VERSION,
                    },
                    facts,
                )
            },
        )
        return list(facts.values())
