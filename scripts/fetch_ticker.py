"""
fetch_ticker.py — Fetch price history for a single ticker and insert into prices table.
Usage: python scripts/fetch_ticker.py VUAG.L
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.pipeline import db as pipeline_db
from src.pipeline.loaders.prices import fetch_and_store_ticker


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/fetch_ticker.py <TICKER>")
        print("Example: python scripts/fetch_ticker.py VUAG.L")
        sys.exit(1)

    ticker = sys.argv[1].strip()
    start_date = (
        datetime.today() - timedelta(days=365 * config.SETTINGS["price_history_years"])
    ).strftime("%Y-%m-%d")

    print(f"Fetching {config.SETTINGS['price_history_years']} years of price history for {ticker} from {start_date}...")

    conn = pipeline_db.get_connection()
    n = fetch_and_store_ticker(conn, ticker, start_date)
    if n == -1:
        print(f"[ERROR] No data returned for '{ticker}'. Check the symbol is a valid Yahoo Finance ticker.")
        print("        UK stocks use the .L suffix (e.g. VUAG.L). Indices use ^ (e.g. ^FTSE).")
        conn.close()
        sys.exit(1)

    conn.commit()
    conn.close()
    print(f"Inserted {n} rows for {ticker}.")


if __name__ == "__main__":
    main()
