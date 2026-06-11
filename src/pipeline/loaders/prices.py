from datetime import datetime, timedelta

import polars as pl
import yfinance as yf


def fetch_prices(conn, holding_tickers: list, benchmarks: list, price_history_years: int) -> None:
    """Fetch adjusted close prices from Yahoo Finance for all holding tickers and benchmarks."""
    benchmark_tickers = [b["ticker"] for b in benchmarks]
    all_tickers = list(set(holding_tickers) | set(benchmark_tickers))
    fetchable = [t for t in all_tickers if "." in t or t.startswith("^")]

    if not fetchable:
        print("\n[SKIP] No valid Yahoo Finance tickers to fetch.")
        print("       Add ticker mappings to data/ticker_map.json and re-run.")
        return

    start_date = (
        datetime.today() - timedelta(days=365 * price_history_years)
    ).strftime("%Y-%m-%d")
    print(f"\nFetching price history from {start_date} for: {fetchable}")

    inserted = 0
    failed = []

    for ticker in fetchable:
        try:
            yf_ticker = yf.Ticker(ticker)
            raw = yf_ticker.history(start=start_date, auto_adjust=True)
            if raw.empty:
                failed.append(ticker)
                continue

            # yfinance returns LSE stocks in GBp (pence) but some ETFs/funds in GBP (pounds).
            # Normalise everything to pence so it's consistent with avg_cost_p in holdings.
            currency = (yf_ticker.fast_info or {}).get("currency", "GBp")
            gbp_to_pence = currency == "GBP"

            raw.index = raw.index.tz_localize(None)
            df = (
                pl.from_pandas(raw.reset_index()[["Date", "Close"]])
                .rename({"Date": "date", "Close": "close"})
                .with_columns([
                    pl.lit(ticker).alias("ticker"),
                    pl.col("date").dt.strftime("%Y-%m-%d"),
                    (pl.col("close") * (100 if gbp_to_pence else 1)).round(4),
                ])
                .filter(pl.col("close").is_not_null())
                .select(["ticker", "date", "close"])
            )
            if gbp_to_pence:
                print(f"  {ticker}: GBP→GBp conversion applied")

            rows = df.rows()
            conn.executemany(
                "INSERT OR REPLACE INTO prices (ticker, date, close) VALUES (?, ?, ?)",
                rows,
            )
            inserted += len(rows)
            print(f"  {ticker}: {len(rows)} days")

        except Exception as e:
            failed.append(ticker)
            print(f"  {ticker}: FAILED — {e}")

    conn.commit()
    print(f"  Total price rows inserted: {inserted}")

    if failed:
        print(f"\n  [WARNING] Failed to fetch: {failed}")
        print("  Check the tickers are correct Yahoo Finance symbols.")
        print("  UK stocks use the .L suffix (e.g. ISF.L), funds use .L too.")
