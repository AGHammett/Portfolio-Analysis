"""
fetch_ticker.py — Fetch price history for a single ticker and insert into prices table.
Usage: python scripts/fetch_ticker.py VUAG.L
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import polars as pl
import yfinance as yf

import config
from src.pipeline import db as pipeline_db


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/fetch_ticker.py <TICKER>")
        print("Example: python scripts/fetch_ticker.py VUAG.L")
        sys.exit(1)

    ticker = sys.argv[1].strip()
    price_history_years = config.SETTINGS["price_history_years"]
    start_date = (
        datetime.today() - timedelta(days=365 * price_history_years)
    ).strftime("%Y-%m-%d")

    print(f"Fetching {price_history_years} years of price history for {ticker} from {start_date}...")

    raw = yf.Ticker(ticker).history(start=start_date, auto_adjust=True)
    if raw.empty:
        print(f"[ERROR] No data returned for '{ticker}'. Check the symbol is a valid Yahoo Finance ticker.")
        print("        UK stocks use the .L suffix (e.g. VUAG.L). Indices use ^ (e.g. ^FTSE).")
        sys.exit(1)

    raw.index = raw.index.tz_localize(None)
    df = (
        pl.from_pandas(raw.reset_index()[["Date", "Close"]])
        .rename({"Date": "date", "Close": "close"})
        .with_columns([
            pl.lit(ticker).alias("ticker"),
            pl.col("date").dt.strftime("%Y-%m-%d"),
            pl.col("close").round(4),
        ])
        .filter(pl.col("close").is_not_null())
        .select(["ticker", "date", "close"])
    )

    rows = df.rows()
    conn = pipeline_db.get_connection()
    conn.executemany(
        "INSERT OR REPLACE INTO prices (ticker, date, close) VALUES (?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()

    print(f"Inserted {len(rows)} rows for {ticker}.")


if __name__ == "__main__":
    main()
