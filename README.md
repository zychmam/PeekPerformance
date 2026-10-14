# PeekPerformance

Analyze Counter-Strike 2 demo files locally and explore player and match statistics.

Upload a `.dem`, `.dem.gz`, or `.dem.zst` file to inspect player performance, rounds, damage, grenades, economy, and events. Export a versioned JSON match report for manual analysis or an LLM. Demo analysis uses `demoparser2` and runs locally.

## Requirements

- Python 3.11 or newer
- A Counter-Strike 2 demo file (`.dem`, `.dem.gz`, or `.dem.zst`) to analyze

## Quick Start

```bash
git clone https://github.com/zychmam/PeekPerformance.git
cd PeekPerformance
pip install -e ".[dev]"
streamlit run src/gui/app.py
```

Open `http://localhost:8501`, then upload your file. You can also select a previously analyzed demo from the local database. Choose a player from the demo roster and click **Śledź gracza** to track them. The **Mecze gracza** view lists that player's parsed matches with their PeekPerformance rating, kills, deaths, and ADR.

## Demo Analysis

The single-match screen starts with a selected player, four key metrics and a compact five-column player table. **Rundy** shows the winning side, the selected player's round stats and a short kill feed. **Walka** charts enemy damage by round. **Utility i ekonomia** shows HE/fire damage and flash events. Full parser tables, optional samples, raw events and JSON export are under **Dane i eksport**.

Choose **Dane i eksport → Przygotuj raport JSON → Pobierz raport JSON**. The report includes all rounds and players, match/side statistics, M3/M4 tactical data, M5 tendencies, a reading guide, coverage and evidence references. It ignores current view filters. Repeated records use self-describing `columns`/`rows` tables; raw trajectories and individual shots are omitted. Player identifiers are local to the report. See [the export contract](docs/match_report_export.md) and [JSON Schema 1.0](docs/schemas/match_report_v1.schema.json). Excel and CSV exports have been removed.

Match tables, charts, player choices, and exports show nicknames instead of SteamIDs. Identical nicknames receive stable numbered labels within a match; SteamIDs remain internal keys for correctly linking events and matches.

Demo parsing happens locally. Each parsed match is saved by the SHA-256 hash of its decompressed contents, so repeat uploads reuse one database entry. The database stores the full analysis separately from a small match catalog, per-demo player roster, tracked SteamIDs, and one compact rating summary per player and match. The player panel reads indexed catalog entries and stored ratings without loading event tables or reparsing demos. Older imported demos get ratings once when first opened in the panel. A tracked player can only be selected from a parsed demo. On the first launch of this demo-only schema, old API tables and previous demo cache rows are deleted.

Metric definitions and the current synthetic regression fixture are described in [docs/metrics_reference.md](docs/metrics_reference.md). The approximate rating still needs validation against real demos.

Full rating components and per-round counters are persisted with input and metric versions.
The overview, player cards and round charts use the same event counters. Opening a current
saved result does not require the source demo. Old analyses are upgraded once from their
source file to store round rosters; if that file is missing, the app asks for the same demo
again. Updating metric formulas recalculates results from stored events. Input replacement
invalidates derived results, while schema migration preserves saved matches and tracked players.

## Technology

| Component | Technology |
|---|---|
| Demo parsing | `demoparser2` |
| Web interface | `Streamlit` |
| Tables and charts | `pandas`, `Plotly` |
| Local cache | SQLite |
| Match report export | Versioned UTF-8 JSON with a reading guide and JSON Schema |

## Development

Run the tests with `pytest tests/ -v` and check the code with `ruff check src/ tests/`.

## License

MIT
