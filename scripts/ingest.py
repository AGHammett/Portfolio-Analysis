"""
ingest.py — Portfolio Analyser data ingestion
Run from the project root:  python scripts/ingest.py

Sources:
  1. HL CSV exports  →  portfolios + holdings tables
  2. yfinance        →  prices table
  3. BoE / ONS CSVs  →  macro table

Configure portfolios and benchmarks in config.py.
Ticker mappings live in data/ticker_map.json.
"""
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.pipeline import db as pipeline_db
from src.pipeline.parsers import hargreaves_lansdown
from src.pipeline.loaders import prices as prices_loader
from src.pipeline.loaders import macro as macro_loader

TICKER_MAP_PATH = PROJECT_ROOT / "data" / "ticker_map.json"

_BROKER_PARSERS = {
    "hargreaves_lansdown": hargreaves_lansdown,
}


def main():
    """Run a full data refresh: load holdings from each portfolio CSV, fetch prices, load macro data."""
    print("Portfolio Analyser — data ingestion")
    print("=" * 40)

    if not TICKER_MAP_PATH.exists():
        print(f"[ERROR] Ticker map not found at {TICKER_MAP_PATH}")
        sys.exit(1)
    with TICKER_MAP_PATH.open(encoding="utf-8") as f:
        ticker_map = json.load(f)

    conn = pipeline_db.get_connection()
    pipeline_db.setup_db(conn)

    all_tickers = []
    for portfolio_id, portfolio_cfg in config.PORTFOLIOS.items():
        pipeline_db.register_portfolio(conn, portfolio_id, portfolio_cfg["name"])
        broker = portfolio_cfg["broker"]
        parser = _BROKER_PARSERS.get(broker)
        if parser is None:
            print(f"\n[SKIP] No parser for broker '{broker}' (portfolio: {portfolio_id})")
            continue
        tickers = parser.load(conn, portfolio_id, portfolio_cfg["file"], ticker_map)
        all_tickers.extend(tickers)

    prices_loader.fetch_prices(
        conn,
        all_tickers,
        config.BENCHMARKS,
        config.SETTINGS["price_history_years"],
    )

    raw_dir = PROJECT_ROOT / "data" / "raw"
    macro_loader.load_boe_rates(conn, raw_dir / "boe_rates.csv")
    macro_loader.load_ons_cpi(conn, raw_dir / "ons_cpi.csv")

    pipeline_db.seed_holding_meta(conn)
    pipeline_db.print_summary(conn)

    conn.close()
    print("\nDone. Run 'claude' in this folder to start your analysis session.")


if __name__ == "__main__":
    main()
