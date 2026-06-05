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

# ---------------------------------------------------------------------------
# Ticker map
# ---------------------------------------------------------------------------
# HL doesn't include Yahoo Finance tickers in its export. Map partial
# lowercase holding names to their Yahoo Finance ticker here. Re-run
# ingest.py after adding entries — any unmatched holdings are flagged.
TICKER_MAP = {
    "artemis global income class i - accumula": "0P0000W36K.L",
    "baillie gifford american class b - accum": "0P00000VC9.L",
    "f&c investment trust ord gbp0.0625":       "FCIT.L",
    "hanetf icav future of defence ucits etf ": "NATP.L",
    "legal & general global technology index ": "0P0001FVLM.L",
    "rolls royce holdings plc ordinary 20p sh": "RR.L",
    "vanguard funds plc s&p 500 ucits etf usd": "VUAG.L",
    "amundi nasdaq 100 ucits etf usd":          "NASD.L",   # USD Acc, LSE-listed
    "fundsmith equity class i - accumulation":  "0P0000RU81.L",
    "legal & general clean energy":             "RENG.L",
}
