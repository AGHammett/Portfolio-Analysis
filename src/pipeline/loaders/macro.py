from datetime import datetime
from pathlib import Path


def load_boe_rates(conn, boe_csv: Path) -> None:
    """Parse a BoE base rate CSV and upsert rows into the macro table."""
    boe_csv = Path(boe_csv)
    if not boe_csv.exists():
        print(f"\n[SKIP] BoE rates CSV not found at {boe_csv}")
        print("       Download from: https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp")
        print("       Save as data/raw/boe_rates.csv")
        return

    print(f"\nLoading BoE base rates: {boe_csv}")

    rows = []
    with open(boe_csv, encoding="utf-8-sig", newline="") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 2:
                continue
            date_str = parts[0].strip().strip('"')
            rate_str = parts[1].strip().strip('"')
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


def load_ons_cpi(conn, ons_csv: Path) -> None:
    """Parse an ONS CPI CSV and upsert year-on-year inflation figures into the macro table."""
    ons_csv = Path(ons_csv)
    if not ons_csv.exists():
        print(f"\n[SKIP] ONS CPI CSV not found at {ons_csv}")
        print("       Download from: https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23")
        print("       Click 'Download' → CSV. Save as data/raw/ons_cpi.csv")
        return

    print(f"\nLoading ONS CPI: {ons_csv}")

    rows = []
    with open(ons_csv, encoding="utf-8-sig", newline="") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 2:
                continue
            date_str = parts[0].strip().strip('"')
            val_str  = parts[1].strip().strip('"')
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
