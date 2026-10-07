# PeekPerformance

Analyze Counter-Strike 2 demo files locally and explore player and match statistics.

Upload a `.dem` or `.dem.gz` file to inspect player performance, rounds, damage, grenades, economy, and events. Export the analysis to Excel or a ZIP archive of CSV files. Demo analysis uses `demoparser2` and does not require a Leetify account or API key.

> The older Leetify player and match features are still present in the app but are planned for removal. The demo workflow is the focus of this project.

## Requirements

- Python 3.10 or newer
- A Counter-Strike 2 demo file (`.dem` or `.dem.gz`) to analyze

## Quick Start

```bash
git clone https://github.com/zychmam/PeekPerformance.git
cd PeekPerformance
pip install -e ".[dev]"
streamlit run src/gui/app.py
```

Open `http://localhost:8501`, then upload your file in **Demo Analysis**. When no Leetify players are tracked, the demo analysis screen opens directly. You can also select a previously analyzed demo from the local cache.

## Demo Analysis

The app shows player statistics such as kills, deaths, assists, ADR, headshot percentage, and approximate rating. Its detailed views cover rounds, damage, grenades, economy, player states, raw events, and chat and match metadata. You can download an Excel workbook or a ZIP archive containing CSV files.

Demo parsing happens locally. An API key is not needed for uploading, analyzing, or exporting demos.

## Technology

| Component | Technology |
|---|---|
| Demo parsing | `demoparser2` |
| Web interface | `Streamlit` |
| Tables and charts | `pandas`, `Plotly` |
| Local cache | SQLite |
| Excel export | `openpyxl` |

The legacy Leetify integration also uses `requests`. Its export format is documented separately in [docs/data_model.md](docs/data_model.md).

## Current legacy features

The app still includes Leetify player profiles, match browsing, charts, comparison, and match export. These features use the Leetify Public CS API and are planned for removal. If you use them in the meantime, enter a Steam64 ID in the sidebar; an optional Leetify API key can be set in **Settings** for higher rate limits. Data in those views is provided by [Leetify](https://leetify.com).

## Development

Run the tests with `pytest tests/ -v` and check the code with `ruff check src/ tests/`.

## License

MIT
