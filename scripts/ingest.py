"""
ingest.py — Portfolio Analyser data ingestion
=============================================
Loads data from three sources into portfolio.db:
  1. Hargreaves Lansdown CSV export  →  holdings + holding_meta tables
  2. yfinance                        →  prices table (holdings + benchmarks)
  3. BoE / ONS CSVs                  →  macro table

Run from the project root:
    python scripts/ingest.py

Re-run any time you want fresh prices or have a new HL export.
"""

import sqlite3
import os
import sys
import csv
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
import yfinance as yf

# ---------------------------------------------------------------------------
# Paths  (all relative to project root)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH      = PROJECT_ROOT / "data" / "portfolio.db"
HL_CSV       = PROJECT_ROOT / "data" / "raw" / "hl_export.csv"
BOE_CSV      = PROJECT_ROOT / "data" / "raw" / "boe_rates.csv"
ONS_CSV      = PROJECT_ROOT / "data" / "raw" / "ons_cpi.csv"

# ---------------------------------------------------------------------------
# Benchmarks fetched automatically alongside your holdings - Note in CLAUDE.md
# ---------------------------------------------------------------------------
BENCHMARKS = {
    "^FTSE":  "FTSE 100",
    "VWRL.L": "Vanguard FTSE All-World ETF",
    "AGBP.L": "iShares Core Global Agg Bond (GBP hedged)",
    "^GSPC":  "S&P 500 Index",
    "^IXIC":  "Nasdaq Composite",
}

# How many years of price history to fetch
PRICE_HISTORY_YEARS = 5

# ---------------------------------------------------------------------------
# HL CSV column mapping
# ---------------------------------------------------------------------------
# Confirmed against actual HL export format (June 2025).
# Update the values on the right if your export differs — do not change keys.
HL_COLUMNS = {
    "name":     "Stock",            # Full name of the holding
    "units":    "Units held",       # Number of units / shares
    "price_p":  "Price (pence)",    # Current price in PENCE
    "value":    "Value (£)",        # Current market value in GBP
    "cost":     "Cost (£)",         # Your total cost in GBP
}

# ---------------------------------------------------------------------------
# Ticker mapping
# ---------------------------------------------------------------------------
# HL doesn't include Yahoo Finance tickers in its export.
# Add your holdings here: "Holding name (partial match)" -> "TICKER"
# The script will try to match by name substring (case-insensitive).
# Any unmatched holdings are flagged at the end — add them then.
TICKER_MAP = {
    "artemis global income class i - accumula": "0P0000W36K.L",
    "baillie gifford american class b - accum": "0P00000VC9.L",
    "f&c investment trust ord gbp0.0625":       "FCIT.L",
    "hanetf icav future of defence ucits etf ": "NATP.L",
    "legal & general global technology index ": "0P0001FVLM.L",
    "rolls royce holdings plc ordinary 20p sh": "RR.L",
    "vanguard funds plc s&p 500 ucits etf usd": "VUAG.L",
}


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def create_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS holdings (
            ticker      TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            units       REAL,
            avg_cost_p  REAL,   -- average cost per unit in pence
            total_cost  REAL,   -- total cost in GBP
            last_updated TEXT
        );

        CREATE TABLE IF NOT EXISTS holding_meta (
            ticker          TEXT PRIMARY KEY,
            asset_class     TEXT,   -- Equity / Bond / Property / Cash / Mixed
            geographic_focus TEXT,  -- Global / UK / US / Europe / EM / etc.
            sector          TEXT,   -- Tech / Financials / Healthcare / Broad / etc.
            notes           TEXT
        );

        CREATE TABLE IF NOT EXISTS prices (
            ticker  TEXT    NOT NULL,
            date    TEXT    NOT NULL,
            close   REAL    NOT NULL,
            PRIMARY KEY (ticker, date)
        );

        CREATE TABLE IF NOT EXISTS macro (
            date            TEXT PRIMARY KEY,
            boe_base_rate   REAL,
            cpi_yoy         REAL
        );
    """)
    conn.commit()
    print("Tables ready.")


# ---------------------------------------------------------------------------
# 1. Load HL CSV
# ---------------------------------------------------------------------------
def load_hl_csv(conn):
    if not HL_CSV.exists():
        print(f"\n[SKIP] HL export not found at {HL_CSV}")
        print("       Export your portfolio from HL and save it there, then re-run.")
        return []

    print(f"\nLoading HL export: {HL_CSV}")

    # HL CSVs often have header rows / summary rows — find the real header
    with open(HL_CSV, encoding="cp1252", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
        raw = list(csv.reader(f, dialect))

    # Find the header row — first cell must be exactly "Stock"
    header_row_idx = None
    for i, row in enumerate(raw):
        if row and row[0].strip() == HL_COLUMNS["name"]:
            header_row_idx = i
            break

    if header_row_idx is None:
        print(f"[ERROR] Could not find header row in {HL_CSV}")
        print(f"        Expected a column called '{HL_COLUMNS['name']}'")
        print(f"        First few rows of your CSV:")
        for row in raw[:5]:
            print(f"          {row}")
        print("\n        Update HL_COLUMNS in ingest.py to match your export.")
        return []

    headers = [h.strip() for h in raw[header_row_idx]]
    data_rows = raw[header_row_idx + 1:]

    # Build column index lookup
    try:
        col = {k: headers.index(v) for k, v in HL_COLUMNS.items()}
    except ValueError as e:
        print(f"[ERROR] Column not found: {e}")
        print(f"        Your CSV headers: {headers}")
        print(f"        Update HL_COLUMNS in ingest.py to match.")
        return []

    tickers_loaded = []
    unmatched = []
    today = datetime.today().strftime("%Y-%m-%d")

    conn.execute("DELETE FROM holdings")  # fresh load each time

    for row in data_rows:
        if not row or not any(row):  # skip blank rows
            continue

        # Skip rows that don't have enough columns (footer/summary rows)
        if len(row) <= max(col.values()):
            continue

        name = row[col["name"]].strip()
        if not name or name.lower().startswith("total"):
            continue

        # Clean numeric fields — HL uses commas and may have 'n/a'
        def clean_num(val):
            val = val.strip().replace(",", "").replace("£", "").replace("%", "")
            try:
                return float(val)
            except (ValueError, AttributeError):
                return None

        units     = clean_num(row[col["units"]])
        price_p   = clean_num(row[col["price_p"]])   # in pence
        value_gbp = clean_num(row[col["value"]])
        cost_gbp  = clean_num(row[col["cost"]])

        # Derive average cost per unit in pence
        avg_cost_p = None
        if units and cost_gbp:
            avg_cost_p = (cost_gbp * 100) / units  # convert £ to pence per unit

        # Match ticker from TICKER_MAP
        ticker = None
        for name_fragment, t in TICKER_MAP.items():
            if name_fragment.lower() in name.lower():
                ticker = t
                break

        if ticker is None:
            # Use sanitised name as fallback so the row isn't lost
            ticker = name[:20].replace(" ", "_").upper()
            unmatched.append((name, ticker))

        conn.execute("""
            INSERT OR REPLACE INTO holdings
            (ticker, name, units, avg_cost_p, total_cost, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticker, name, units, avg_cost_p, cost_gbp, today))

        tickers_loaded.append(ticker)

    conn.commit()
    print(f"  Loaded {len(tickers_loaded)} holdings.")

    if unmatched:
        print(f"\n  [ACTION NEEDED] {len(unmatched)} holdings have no ticker mapping.")
        print("  Add them to TICKER_MAP in ingest.py:")
        for name, fallback in unmatched:
            print(f"    \"{name.lower()[:40]}\": \"TICKER.L\",   # currently using: {fallback}")

    return tickers_loaded


# ---------------------------------------------------------------------------
# 2. Fetch prices via yfinance
# ---------------------------------------------------------------------------
def fetch_prices(conn, holding_tickers):
    all_tickers = list(set(holding_tickers) | set(BENCHMARKS.keys()))
    # Only fetch tickers that look like real Yahoo Finance tickers
    # (skip SEDOL fallbacks which won't resolve)
    fetchable = [t for t in all_tickers if "." in t or t.startswith("^")]

    if not fetchable:
        print("\n[SKIP] No valid Yahoo Finance tickers to fetch.")
        print("       Add ticker mappings to TICKER_MAP and re-run.")
        return

    start_date = (datetime.today() - timedelta(days=365 * PRICE_HISTORY_YEARS)).strftime("%Y-%m-%d")
    print(f"\nFetching price history from {start_date} for: {fetchable}")

    inserted = 0
    failed = []

    for ticker in fetchable:
        try:
            raw = yf.Ticker(ticker).history(start=start_date, auto_adjust=True)
            if raw.empty:
                failed.append(ticker)
                continue

            raw.index = raw.index.tz_localize(None)  # polars requires tz-naive datetimes
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


# ---------------------------------------------------------------------------
# 3. Load BoE base rate CSV
# ---------------------------------------------------------------------------
def load_boe_rates(conn):
    if not BOE_CSV.exists():
        print(f"\n[SKIP] BoE rates CSV not found at {BOE_CSV}")
        print("       Download from: https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp")
        print("       Save as data/raw/boe_rates.csv")
        return

    print(f"\nLoading BoE base rates: {BOE_CSV}")

    # BoE CSV format: Date, Rate
    # Their export has a text header — we skip non-date rows
    rows = []
    with open(BOE_CSV, encoding="utf-8-sig", newline="") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 2:
                continue
            date_str, rate_str = parts[0].strip().strip('"'), parts[1].strip().strip('"')
            # BoE dates are DD MMM YYYY e.g. "02 Aug 2023"
            for fmt in ("%d %b %y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                    rate = float(rate_str)
                    rows.append((date, rate))
                    break
                except ValueError:
                    continue

    if rows:
        conn.executemany("""
            INSERT OR REPLACE INTO macro (date, boe_base_rate)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET boe_base_rate = excluded.boe_base_rate
        """, rows)
        conn.commit()
        print(f"  Loaded {len(rows)} BoE rate entries.")
    else:
        print("  [WARNING] No valid rows parsed from BoE CSV. Check the file format.")


# ---------------------------------------------------------------------------
# 4. Load ONS CPI CSV
# ---------------------------------------------------------------------------
def load_ons_cpi(conn):
    if not ONS_CSV.exists():
        print(f"\n[SKIP] ONS CPI CSV not found at {ONS_CSV}")
        print("       Download from: https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23")
        print("       Click 'Download' → CSV. Save as data/raw/ons_cpi.csv")
        return

    print(f"\nLoading ONS CPI: {ONS_CSV}")

    # ONS CSV has metadata rows at the top; data rows are YYYY MMM, value
    rows = []
    with open(ONS_CSV, encoding="utf-8-sig", newline="") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 2:
                continue
            date_str = parts[0].strip().strip('"')
            val_str  = parts[1].strip().strip('"')
            # ONS monthly format: "2023 JAN"
            try:
                date = datetime.strptime(date_str, "%Y %b").strftime("%Y-%m-01")
                cpi  = float(val_str)
                rows.append((date, cpi))
            except ValueError:
                continue

    if rows:
        conn.executemany("""
            INSERT OR REPLACE INTO macro (date, cpi_yoy)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET cpi_yoy = excluded.cpi_yoy
        """, rows)
        conn.commit()
        print(f"  Loaded {len(rows)} CPI entries.")
    else:
        print("  [WARNING] No valid rows parsed from ONS CSV. Check the file format.")


# ---------------------------------------------------------------------------
# 5. Seed holding_meta with blanks for any unmapped holdings
# ---------------------------------------------------------------------------
def seed_holding_meta(conn):
    conn.execute("""
        INSERT OR IGNORE INTO holding_meta (ticker, asset_class, geographic_focus, sector, notes)
        SELECT ticker, NULL, NULL, NULL, NULL FROM holdings
    """)
    conn.commit()

    empty = conn.execute("""
        SELECT h.ticker, h.name FROM holdings h
        JOIN holding_meta m ON h.ticker = m.ticker
        WHERE m.asset_class IS NULL
    """).fetchall()

    if empty:
        print(f"\n[ACTION NEEDED] Fill in holding_meta for {len(empty)} holdings.")
        print("  You can do this in a Claude Code session by asking:")
        print("  'Fill in the holding_meta table for my holdings'")
        print("  and Claude will look up each fund and suggest values.")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def print_summary(conn):
    print("\n--- Database summary ---")
    for table in ["holdings", "holding_meta", "prices", "macro"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    # Price coverage
    coverage = conn.execute("""
        SELECT ticker, MIN(date), MAX(date), COUNT(*)
        FROM prices GROUP BY ticker ORDER BY ticker
    """).fetchall()
    if coverage:
        print("\n  Price coverage:")
        for ticker, start, end, n in coverage:
            print(f"    {ticker}: {start} → {end} ({n} days)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("Portfolio Analyser — data ingestion")
    print("=" * 40)

    conn = get_connection()
    create_tables(conn)

    holding_tickers = load_hl_csv(conn)
    fetch_prices(conn, holding_tickers)
    load_boe_rates(conn)
    load_ons_cpi(conn)
    seed_holding_meta(conn)
    print_summary(conn)

    conn.close()
    print("\nDone. Run 'claude' in this folder to start your analysis session.")


if __name__ == "__main__":
    main()