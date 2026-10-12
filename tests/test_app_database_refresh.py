"""Old Streamlit database adapters are replaced without removing saved matches."""

from unittest.mock import patch

from src.config import Config
from src.gui import app
from src.models.models import DemoAnalysis
from src.storage.database import Database


def test_missing_spatial_api_refreshes_adapter_and_preserves_data(tmp_path):
    config = Config(db_path=str(tmp_path / "matches.db"))
    stale = Database(config.db_path)
    stale.upsert_demo_analysis(DemoAnalysis(file_name="match.dem", content_hash="match"))
    stale.save_stages("match", {"test": ("version", {"demo_id": "match", "cache_key": "version", "round_numbers": [1]}, {1: {"value": 42}})})
    # Simulate a retained adapter with the old API even if isinstance succeeds.
    stale.get_stage_rounds = None
    session = {"db": stale, "config": config}
    session["current_demo_analysis"] = object()
    session["spatial_old"] = object()
    session["early_old"] = object()
    with patch.object(app.st, "session_state", session):
        refreshed = app._get_db()
        assert refreshed is not stale
        assert refreshed.get_demo_analysis("match") is not None
        assert refreshed.get_stage_rounds("match", "test", "version") == {1: {"value": 42}}
        assert app._get_db() is refreshed
        assert "current_demo_analysis" not in session
        assert "spatial_old" not in session
        assert "early_old" not in session
