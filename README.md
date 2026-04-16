# PeekPerformance

Collect and browse CS2 match data from [Leetify](https://leetify.com). Includes demo file analysis and AI-ready data export.

> Data provided by [Leetify](https://leetify.com).

---

## Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.10+ | Excellent ecosystem for data collection, processing, and rapid GUI prototyping |
| **API Client** | `requests` | Simple, well-tested HTTP library for calling the Leetify public REST API |
| **GUI** | `Streamlit` | Minimal-code web-based UI with built-in widgets (tables, charts, selectors) — ideal for data browsing apps |
| **Charts** | `Plotly` | Interactive, publication-quality charts that integrate natively with Streamlit |
| **Data Handling** | `pandas` | Industry-standard tabular data manipulation and filtering |
| **Local Storage** | SQLite (stdlib) | Zero-config embedded database for caching fetched data locally |
| **Demo Parsing** | `demoparser2` | Fast CS2 demo file parser used for offline match analysis |

### Why this stack?

- **Streamlit** eliminates the need for HTML/CSS/JS while providing a modern, responsive web UI that runs locally in the browser. It is purpose-built for data-centric applications.
- **SQLite** provides offline access to previously fetched data with no external database server.
- **Plotly** charts are interactive (zoom, hover, pan) and render natively inside Streamlit.
- The entire stack installs with a single `pip install` command and has no system-level dependencies.

---

## Project Structure

```
PeekPerformance/
├── pyproject.toml           # Build config, dependencies, tool settings
├── requirements.txt         # Pinned dependency list
├── docs/
│   └── data_model.md        # Full data model reference (fields, formats)
├── src/
│   ├── config.py            # Configuration management (API key, paths)
│   ├── api/
│   │   └── leetify_client.py  # Leetify public API client
│   ├── demos/
│   │   ├── demo_analyzer.py   # CS2 demo file parser (demoparser2)
│   │   ├── demo_manager.py    # Demo file upload / disk management
│   │   └── rating_calculator.py  # Per-player rating computation from demos
│   ├── models/
│   │   └── models.py        # Data classes (PlayerProfile, MatchSummary, DemoAnalysis, etc.)
│   ├── storage/
│   │   └── database.py      # SQLite cache layer
│   └── gui/
│       └── app.py           # Streamlit GUI application
└── tests/
    ├── test_config.py
    ├── test_database.py
    ├── test_demo_analyzer.py
    ├── test_demo_manager.py
    └── test_leetify_client.py
```

---

## Quick Start

### 1. Install

```bash
# Clone and install
git clone https://github.com/zychmam/PeekPerformance.git
cd PeekPerformance
pip install -e ".[dev]"
```

### 2. (Optional) Set your Leetify API key

Get a free API key at <https://leetify.com/app/developer> for higher rate limits.

```bash
export LEETIFY_API_KEY="your-key-here"
```

Or enter it in the **Settings** panel inside the app.

### 3. Run the app

```bash
streamlit run src/gui/app.py
```

The app opens in your browser at `http://localhost:8501`.

---

## How to Use

1. **Add a player** — Enter a Steam64 ID in the sidebar and click **Add & Fetch**.
2. **Browse matches** — The *Matches* tab shows a filterable table of all fetched games with K/D, ADR, ratings, etc.
3. **View charts** — The *Charts* tab plots performance metrics over time and by map.
4. **Inspect a match** — The *Match Detail* tab lets you pick any game and view per-player scoreboard stats.
5. **AI Export** — The *AI Export* tab exports match data in JSON, CSV, or compact text format for use with LLMs.
6. **Compare players** — The *Compare Players* tab shows a side-by-side comparison of tracked players.
7. **Demo Analysis** — The *Demo Analysis* tab lets you upload `.dem` / `.dem.gz` files and view parsed per-player stats.

---

## Running Tests

```bash
pytest tests/ -v
```

## Linting

```bash
ruff check src/ tests/
```

---

## API Reference

This project uses the **Leetify Public CS API**:

| Endpoint | Description |
|---|---|
| `GET /v3/profile?steamId=…` | Player profile (ratings, rank) |
| `GET /v3/profile/matches?steamId=…` | Player match history |
| `GET /v2/matches/{gameId}` | Full match detail with all players |

Docs: <https://api-public-docs.cs-prod.leetify.com/>

---

## Demo File Analysis

PeekPerformance pozwala na analizę plików demek CS2 (`.dem`, `.dem.gz`) bezpośrednio w aplikacji (zakładka **Demo Analysis**).

Możliwości:
- Wgrywanie własnych plików demek (również spakowanych)
- Automatyczne parsowanie i wyciąganie statystyk graczy (kills, deaths, assists, ADR, HS%, rating, itp.)
- Szczegółowe dane rundowe: zwycięzcy, powody zakończenia rundy, liczba rozegranych rund
- Analiza obrażeń, oślepień, użycia granatów, ekonomii, bomb (plant/defuse)
- Eksport wyników do CSV/JSON

Przykładowy workflow:
1. Przejdź do zakładki **Demo Analysis**
2. Wgraj plik `.dem` lub `.dem.gz`
3. Po przetworzeniu zobaczysz tabelę z pełnymi statystykami graczy oraz szczegółowe dane rundowe
4. Możesz pobrać wyniki do dalszej analizy lub AI

Analiza oparta jest o bibliotekę `demoparser2` i działa lokalnie – żadne dane nie są wysyłane na zewnątrz.

---

## License

MIT