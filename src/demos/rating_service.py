"""Materialize a demo's rating once for fast player-history queries."""

from __future__ import annotations

import pandas as pd

from src.demos.demo_analyzer import DemoAnalyzer
from src.demos.demo_manager import DemoManager
from src.demos.rating_calculator import (
    RATING_VERSION,
    compute_rating_from_events,
    round_stats_from_rating,
)
from src.demos.versions import ANALYSIS_VERSION
from src.models.models import DemoAnalysis
from src.storage.database import Database


def calculate_and_store_rating(
    db: Database, manager: DemoManager, demo_id: str, stored_file_name: str,
    *, analysis: DemoAnalysis | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reuse versioned metrics, otherwise calculate from the persisted event model."""
    cached = db.get_demo_metrics(demo_id, ANALYSIS_VERSION, RATING_VERSION)
    if cached is not None:
        if analysis is not None:
            if getattr(analysis, "analysis_version", 0) != ANALYSIS_VERSION:
                restored = db.get_demo_analysis(demo_id)
                if restored is not None:
                    analysis.__dict__.update(restored.__dict__)
            analysis.round_stats_df = round_stats_from_rating(cached[1])
        return cached
    source = analysis if analysis is not None else db.get_demo_analysis(demo_id)
    if source is None:
        raise ValueError("Cannot calculate metrics for an unknown demo")
    source = ensure_current_analysis(db, manager, source)
    summary, per_round = compute_rating_from_events(
        source.player_info, source.kills_df, source.damage_df,
        source.rounds_df, source.bomb_events_df, roster=source.round_roster_df,
    )
    source.round_stats_df = round_stats_from_rating(per_round)
    if analysis is not None and source is not analysis:
        analysis.__dict__.update(source.__dict__)
    db.save_demo_ratings(
        demo_id, summary, RATING_VERSION, per_round=per_round,
        analysis_version=source.analysis_version,
    )
    return summary, per_round


def ensure_current_analysis(
    db: Database, manager: DemoManager, analysis: DemoAnalysis,
) -> DemoAnalysis:
    """Upgrade old parser inputs once; migrations preserve saved matches and tracking."""
    if getattr(analysis, "analysis_version", 0) == ANALYSIS_VERSION:
        return analysis
    path = manager.analysis_path(
        analysis.stored_file_name or analysis.file_name, analysis.content_hash,
    )
    if path is None:
        raise FileNotFoundError(
            "Uzupełnienie danych rund wymaga oryginalnego pliku demo. "
            f"Wgraj ponownie: {analysis.file_name}"
        )
    refreshed = DemoAnalyzer(path).get_full_analysis()
    refreshed.content_hash = analysis.content_hash
    refreshed.file_name = analysis.file_name
    refreshed.stored_file_name = analysis.stored_file_name or path.name
    refreshed.analyzed_at = analysis.analyzed_at
    db.upsert_demo_analysis(refreshed)
    return refreshed
