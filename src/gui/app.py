"""PeekPerformance demo-only Streamlit interface."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import Config
from src.demos.demo_analyzer import DemoAnalyzer
from src.demos.demo_manager import DemoManager
from src.demos.presentation import disambiguate_names
from src.demos.rating_calculator import RATING_VERSION, round_stats_from_rating
from src.demos.rating_service import calculate_and_store_rating
from src.demos.versions import ANALYSIS_VERSION
from src.gui.match_dashboard import render_match_dashboard
from src.models.models import DemoAnalysis
from src.storage.database import Database


def _get_config() -> Config:
    if "config" not in st.session_state:
        st.session_state["config"] = Config.load()
    return st.session_state["config"]


def _get_db() -> Database:
    # A live session can retain pre-M1 analyses after the schema reset.
    if st.session_state.get("storage_contract") != 8 and "db" in st.session_state:
        for key in list(st.session_state):
            if key == "current_demo_analysis" or key.startswith(("spatial_", "early_")):
                del st.session_state[key]
    st.session_state["storage_contract"] = 8
    cached = st.session_state.get("db")
    required_methods = ("get_demo_metrics", "get_stage_manifest", "get_stage_rounds", "save_stages")
    if not isinstance(cached, Database) or any(
        not callable(getattr(cached, method, None)) for method in required_methods
    ):
        # A running Streamlit session may retain an instance from before a code
        # update. Recreate the adapter using the current storage contract.
        st.session_state["db"] = Database(_get_config().db_path)
    return st.session_state["db"]


def _get_demo_manager() -> DemoManager:
    if "demo_manager" not in st.session_state:
        st.session_state["demo_manager"] = DemoManager(_get_config().demos_dir)
    return st.session_state["demo_manager"]


def _untrack_selected_player() -> None:
    selected = st.session_state.get("selected_steamid")
    if selected:
        _get_db().untrack_player(selected)
    st.session_state.pop("selected_steamid", None)


def _open_saved_demo(demo_id: str) -> None:
    st.session_state["current_demo_analysis"] = _get_db().get_demo_analysis(
        demo_id, include_grenades=False,
    )
    st.session_state["active_view"] = "Analiza demo"
    st.session_state["match_section"] = "Przegląd"


def _sidebar() -> str | None:
    st.sidebar.title("🎯 PeekPerformance")
    st.sidebar.caption("Mecze pochodzą wyłącznie z przeparsowanych dem.")
    tracked = _get_db().list_tracked_players()
    st.sidebar.subheader("Śledzeni gracze")
    if not tracked:
        st.sidebar.info("Otwórz demo i dodaj gracza z jego listy uczestników.")
        return None
    labels = {row["steamid"]: row for row in tracked}
    display_names = disambiguate_names(
        (row["steamid"], row["name"]) for row in tracked
    )
    selected = st.sidebar.selectbox(
        "Wybierz gracza",
        list(labels),
        format_func=lambda steamid: display_names[steamid],
        key="selected_steamid",
    )
    st.sidebar.caption(f"Sparsowane mecze tego gracza: {labels[selected]['match_count']}")
    st.sidebar.button(
        "Usuń ze śledzonych", key="untrack_player",
        on_click=_untrack_selected_player,
    )
    st.sidebar.radio(
        "Widok", ["Mecze gracza", "Analiza demo"], key="active_view"
    )
    return selected


def _player_matches_panel(steamid: str) -> None:
    """Show only indexed match metadata and materialized rating for this player."""
    db = _get_db()
    tracked = {row["steamid"]: row for row in db.list_tracked_players()}
    if steamid not in tracked:
        st.info("Wybierz śledzonego gracza z panelu bocznego.")
        return
    display_names = disambiguate_names(
        (row["steamid"], row["name"]) for row in tracked.values()
    )
    st.header(f"Mecze gracza: {display_names[steamid]}")
    st.caption("Rating PeekPerformance jest przybliżoną oceną jednego meczu.")
    rows = db.list_player_matches(steamid, RATING_VERSION)
    if not rows:
        st.info("Ten gracz nie występuje w żadnym zapisanym demo.")
        return

    missing = [row for row in rows if row["rating_version"] != RATING_VERSION]
    if missing:
        errors = []
        with st.spinner(f"Obliczanie ratingu dla {len(missing)} zapisanych dem..."):
            for row in missing:
                try:
                    calculate_and_store_rating(
                        db, _get_demo_manager(), row["demo_id"], row["stored_file_name"]
                    )
                except Exception as exc:
                    errors.append(f"{row['file_name']}: {exc}")
        if errors:
            st.warning("Nie udało się obliczyć części ratingów: " + "; ".join(errors))
        rows = db.list_player_matches(steamid, RATING_VERSION)

    table = pd.DataFrame([
        {
            "Mapa": row["map_name"],
            "Demo": row["file_name"],
            "Dodano (UTC)": row["analyzed_at"][:16].replace("T", " "),
            "Peek rating": row["rating"],
            "K": row["kills"],
            "D": row["deaths"],
            "ADR": row["adr"],
        }
        for row in rows
    ])
    st.dataframe(
        table, hide_index=True, use_container_width=True,
        column_config={
            "Peek rating": st.column_config.NumberColumn(format="%.2f"),
            "ADR": st.column_config.NumberColumn(format="%.1f"),
        },
    )
    choices = {row["demo_id"]: row for row in rows}
    selected_demo = st.selectbox(
        "Otwórz mecz",
        list(choices),
        format_func=lambda demo_id: (
            f"{choices[demo_id]['map_name']} | {choices[demo_id]['file_name']}"
        ),
    )
    st.button(
        "Otwórz analizę meczu", on_click=_open_saved_demo, args=(selected_demo,)
    )


def _analyze_demo(file_name: str, data: bytes) -> DemoAnalysis:
    """Save uploaded demo, parse it, cache to DB, return analysis."""
    dm = _get_demo_manager()
    db = _get_db()

    path = dm.save_uploaded(file_name, data)
    analyzer = DemoAnalyzer(path)
    analysis = analyzer.get_full_analysis()
    analysis.file_name = (
        file_name.replace("\\", "/").rsplit("/", 1)[-1]
        .removesuffix(".gz").removesuffix(".zst")
    )
    analysis.content_hash = dm.content_hash(path)
    analysis.stored_file_name = path.name
    db.upsert_demo_analysis(analysis)
    return analysis


def _load_or_parse_demo(content_hash: str) -> DemoAnalysis | None:
    """Return cached analysis from DB if available."""
    db = _get_db()
    return db.get_demo_analysis(content_hash, include_grenades=False)


def _analysis_demo_path(analysis: DemoAnalysis) -> Path | None:
    return _get_demo_manager().analysis_path(
        analysis.stored_file_name or analysis.file_name, analysis.content_hash
    )


def _cached_demo_rating(
    analysis: DemoAnalysis,
) -> tuple[pd.DataFrame, pd.DataFrame] | None:
    """Reuse the computed rating across the overview and rating tabs."""
    clock_manifest = _get_db().get_stage_manifest(analysis.content_hash, "observations")
    clock_key = clock_manifest.get("cache_key", "unknown") if clock_manifest else "unknown"
    cache_key = (
        f"rating_{analysis.content_hash or analysis.file_name}"
        f"_a{ANALYSIS_VERSION}_m{RATING_VERSION}"
        f"_clock{clock_key}"
    )
    if cache_key in st.session_state:
        cached_summary, _ = st.session_state[cache_key]
        if "Rating" not in cached_summary.columns:
            del st.session_state[cache_key]
    if cache_key not in st.session_state:
        with st.spinner("Obliczanie ratingu..."):
            try:
                summary, per_round = calculate_and_store_rating(
                    _get_db(), _get_demo_manager(),
                    analysis.content_hash, analysis.stored_file_name,
                    analysis=analysis,
                )
                st.session_state[cache_key] = (summary, per_round)
            except Exception as exc:
                st.warning(f"Nie udało się obliczyć ratingu: {exc}")
                return None

    result = st.session_state[cache_key]
    analysis.round_stats_df = round_stats_from_rating(result[1])
    return result


def _tab_demo_analysis() -> None:
    """Select a saved demo or upload one, then show the focused match dashboard."""
    st.header("Analiza meczu")
    db = _get_db()
    cached_list = db.list_demo_analyses()
    with st.expander(
        "Wybierz lub wgraj demo",
        expanded=st.session_state.get("current_demo_analysis") is None,
    ):
        uploaded = st.file_uploader(
            "Wgraj plik .dem, .dem.gz lub .dem.zst",
            type=["dem", "gz", "zst"], key="demo_upload",
        )
        if uploaded is not None:
            file_name = uploaded.name
            display_name = file_name.removesuffix(".gz").removesuffix(".zst")
            try:
                data = uploaded.getvalue()
                dm = _get_demo_manager()
                content_hash = dm.upload_hash(file_name, data)
                current = st.session_state.get("current_demo_analysis")
                if current is None or current.content_hash != content_hash:
                    cached = _load_or_parse_demo(content_hash)
                    if cached is not None:
                        if dm.analysis_path(cached.stored_file_name, content_hash) is None:
                            path = dm.save_uploaded(file_name, data)
                            if cached.stored_file_name != path.name:
                                # Preserve auxiliary sources when updating the stored filename.
                                cached = db.get_demo_analysis(content_hash)
                                cached.stored_file_name = path.name
                                db.upsert_demo_analysis(cached)
                        st.session_state["current_demo_analysis"] = cached
                        st.success(f"Załadowano: **{display_name}**")
                    else:
                        with st.spinner(f"Parsowanie demo: {file_name}..."):
                            analysis = _analyze_demo(file_name, data)
                            st.session_state["current_demo_analysis"] = analysis
                            st.success(f"Sparsowano: **{display_name}**")
            except Exception as exc:
                st.error(f"Błąd odczytu lub parsowania demo: {exc}")
                st.stop()

        if cached_list and uploaded is None:
            choices = {row["demo_id"]: row for row in cached_list}
            col_sel, col_del = st.columns([4, 1])
            selected_cached = col_sel.selectbox(
                "Zapisane mecze", [None, *choices],
                format_func=lambda demo_id: (
                    "Wybierz zapisany mecz" if demo_id is None else
                    f"{choices[demo_id]['map_name']} · {choices[demo_id]['file_name']}"
                ), key="cached_demo",
            )
            if col_del.button(
                "Usuń demo", key="delete_cached", use_container_width=True,
                disabled=selected_cached is None,
            ):
                db.delete_demo_analysis(selected_cached)
                current = st.session_state.get("current_demo_analysis")
                if current and current.content_hash == selected_cached:
                    st.session_state.pop("current_demo_analysis", None)
                st.session_state.pop(f"rating_{selected_cached}", None)
                st.rerun()
            if selected_cached:
                current = st.session_state.get("current_demo_analysis")
                if current is None or current.content_hash != selected_cached:
                    st.session_state["current_demo_analysis"] = db.get_demo_analysis(
                        selected_cached, include_grenades=False,
                    )

    analysis = st.session_state.get("current_demo_analysis")
    if analysis is not None and not isinstance(analysis, DemoAnalysis):
        analysis = db.get_demo_analysis(analysis.content_hash, include_grenades=False)
        st.session_state["current_demo_analysis"] = analysis
    if analysis is None:
        st.info("Wgraj plik .dem, .dem.gz lub .dem.zst albo wybierz zapisane demo.")
        return

    rating_result = _cached_demo_rating(analysis)
    summary = rating_result[0] if rating_result is not None else pd.DataFrame()
    from src.demos.map_tendencies_service import get_map_round_facts
    from src.demos.match_report import prepare_match_report
    from src.demos.spatial_service import get_spatial_context

    render_match_dashboard(
        analysis, summary, db.track_player, _analysis_demo_path,
        lambda match, rnd=None: get_spatial_context(db, _get_demo_manager(), match, rnd),
        lambda match: get_map_round_facts(db, _get_demo_manager(), match),
        lambda match: prepare_match_report(db, _get_demo_manager(), match),
    )



def main() -> None:
    st.set_page_config(page_title="PeekPerformance", page_icon="🎯", layout="wide")
    selected = _sidebar()
    if selected and st.session_state.get("active_view") == "Mecze gracza":
        _player_matches_panel(selected)
    else:
        _tab_demo_analysis()


if __name__ == "__main__":
    main()
