"""
yfinance_server.py — MCP server exposing yfinance price fetching as a tool.
Run via: python src/mcp_servers/yfinance_server.py  (stdio transport)
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import polars as pl
import yfinance as yf
from mcp.server.fastmcp import FastMCP

from src.pipeline import db as pipeline_db

mcp = FastMCP("yfinance")


@mcp.tool()
def fetch_ticker_prices(ticker: str, years: int = 5) -> str:
    """Fetch daily price history for a ticker and insert into the prices table.

    Args:
        ticker: Yahoo Finance ticker symbol (e.g. VUAG.L, ^FTSE, NVDA).
        years: Number of years of history to fetch (default 5).
    """
    start_date = (
        datetime.today() - timedelta(days=365 * years)
    ).strftime("%Y-%m-%d")

    raw = yf.Ticker(ticker).history(start=start_date, auto_adjust=True)
    if raw.empty:
        return (
            f"Error: no data returned for '{ticker}'. "
            "Check the symbol is a valid Yahoo Finance ticker. "
            "UK stocks use the .L suffix (e.g. VUAG.L); indices use ^ (e.g. ^FTSE)."
        )

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

    return f"Inserted {len(rows)} rows for {ticker}."


if __name__ == "__main__":
    mcp.run()
