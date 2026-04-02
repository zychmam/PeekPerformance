# LeetifyHarvester

Collect and browse CS2 match data from [Leetify](https://leetify.com).

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

### Why this stack?

- **Streamlit** eliminates the need for HTML/CSS/JS while providing a modern, responsive web UI that runs locally in the browser. It is purpose-built for data-centric applications.
- **SQLite** provides offline access to previously fetched data with no external database server.
- **Plotly** charts are interactive (zoom, hover, pan) and render natively inside Streamlit.
- The entire stack installs with a single `pip install` command and has no system-level dependencies.

---

## Project Structure

```
LeetifyHarvester/
├── pyproject.toml           # Build config, dependencies, tool settings
├── requirements.txt         # Pinned dependency list
├── src/
│   ├── config.py            # Configuration management (API key, paths)
│   ├── api/
│   │   └── leetify_client.py  # Leetify public API client
│   ├── models/
│   │   └── models.py        # Data classes (PlayerProfile, MatchSummary, etc.)
│   ├── storage/
│   │   └── database.py      # SQLite cache layer
│   └── gui/
│       └── app.py           # Streamlit GUI application
└── tests/
    ├── test_config.py
    ├── test_database.py
    └── test_leetify_client.py
```

---

## Quick Start

### 1. Install

```bash
# Clone and install
git clone https://github.com/zychmam/LeetifyHarvester.git
cd LeetifyHarvester
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
5. **Compare players** — The *Compare Players* tab shows a side-by-side comparison of tracked players.

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

## License

MIT