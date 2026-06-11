from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "data" / "portfolio.db"

# ---------------------------------------------------------------------------
# Portfolios
# ---------------------------------------------------------------------------
# Each entry maps a short ID to its display name, CSV file path, and broker.
PORTFOLIOS = {
    "isa": {
        "name": "Stocks & Shares ISA",
        "file": PROJECT_ROOT / "data" / "raw" / "hl_isa.csv",
        "broker": "hargreaves_lansdown",
    },
    "lisa": {
        "name": "Lifetime ISA",
        "file": PROJECT_ROOT / "data" / "raw" / "hl_lisa.csv",
        "broker": "hargreaves_lansdown",
    },
}

# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------
BENCHMARKS = [
    {"ticker": "^FTSE",  "name": "FTSE 100"},
    {"ticker": "VWRL.L", "name": "Vanguard FTSE All-World ETF"},
    {"ticker": "AGBP.L", "name": "iShares Core Global Agg Bond (GBP hedged)"},
    {"ticker": "^GSPC",  "name": "S&P 500 Index"},
    {"ticker": "^IXIC",  "name": "Nasdaq Composite"},
]

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
SETTINGS = {
    "price_history_years": 5,
    "default_benchmark": "^FTSE",
    "currency": "GBP",
}

# Ticker mappings live in data/ticker_map.json — edit that file directly.
# Re-run ingest.py after adding entries; any unmatched holdings are flagged.
