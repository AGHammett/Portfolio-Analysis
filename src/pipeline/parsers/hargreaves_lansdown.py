import csv
from datetime import datetime
from pathlib import Path

# Confirmed against HL export format (June 2025).
# Update values on the right if your export columns differ.
_HL_COLUMNS = {
    "name":    "Stock",
    "units":   "Units held",
    "price_p": "Price (pence)",
    "value":   "Value (£)",
    "cost":    "Cost (£)",
}


def load(conn, portfolio_id: str, csv_path, ticker_map: dict) -> list:
    """Parse an HL CSV export and upsert holdings for the given portfolio, returning the list of tickers loaded."""
    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"\n[SKIP] HL export not found at {csv_path}")
        print("       Export your portfolio from HL and save it there, then re-run.")
        return []

    print(f"\nLoading HL export ({portfolio_id}): {csv_path}")

    with open(csv_path, encoding="cp1252", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
        raw = list(csv.reader(f, dialect))

    header_row_idx = None
    for i, row in enumerate(raw):
        if row and row[0].strip() == _HL_COLUMNS["name"]:
            header_row_idx = i
            break

    if header_row_idx is None:
        print(f"[ERROR] Could not find header row in {csv_path}")
        print(f"        Expected a column called '{_HL_COLUMNS['name']}'")
        print("        First few rows of your CSV:")
        for row in raw[:5]:
            print(f"          {row}")
        print("\n        Update _HL_COLUMNS in hargreaves_lansdown.py to match your export.")
        return []

    headers = [h.strip() for h in raw[header_row_idx]]
    data_rows = raw[header_row_idx + 1:]

    try:
        col = {k: headers.index(v) for k, v in _HL_COLUMNS.items()}
    except ValueError as e:
        print(f"[ERROR] Column not found: {e}")
        print(f"        Your CSV headers: {headers}")
        print("        Update _HL_COLUMNS in hargreaves_lansdown.py to match.")
        return []

    tickers_loaded = []
    unmatched = []
    today = datetime.today().strftime("%Y-%m-%d")

    conn.execute("DELETE FROM holdings WHERE portfolio_id = ?", (portfolio_id,))

    for row in data_rows:
        if not row or not any(row):
            continue
        if len(row) <= max(col.values()):
            continue

        name = row[col["name"]].strip()
        if not name or name.lower().startswith("total"):
            continue

        def clean_num(val):
            val = val.strip().replace(",", "").replace("£", "").replace("%", "")
            try:
                return float(val)
            except (ValueError, AttributeError):
                return None

        units    = clean_num(row[col["units"]])
        cost_gbp = clean_num(row[col["cost"]])

        avg_cost_p = None
        if units and cost_gbp:
            avg_cost_p = (cost_gbp * 100) / units

        ticker = None
        for fragment, t in ticker_map.items():
            if fragment.lower() in name.lower():
                ticker = t
                break

        if ticker is None:
            ticker = name[:20].replace(" ", "_").upper()
            unmatched.append((name, ticker))

        conn.execute("""
            INSERT OR REPLACE INTO holdings
                (portfolio_id, ticker, name, units, avg_cost_p, total_cost, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (portfolio_id, ticker, name, units, avg_cost_p, cost_gbp, today))

        tickers_loaded.append(ticker)

    conn.commit()
    print(f"  Loaded {len(tickers_loaded)} holdings.")

    if unmatched:
        print(f"\n  [ACTION NEEDED] {len(unmatched)} holdings have no ticker mapping.")
        print("  Add them to TICKER_MAP in config.py:")
        for name, fallback in unmatched:
            print(f"    \"{name.lower()[:40]}\": \"TICKER.L\",   # currently using: {fallback}")

    return tickers_loaded
