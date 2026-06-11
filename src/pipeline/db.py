import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config


def get_connection():
    """Open and return a SQLite connection, creating the data directory if needed."""
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(config.DB_PATH)


def setup_db(conn):
    """Check for schema migrations then create any missing tables."""
    _migrate_if_needed(conn)
    _create_tables(conn)
    print("Tables ready.")


def _migrate_if_needed(conn):
    """Drop the legacy holdings table if it predates the portfolio_id column; it will be repopulated by ingest."""
    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "holdings" not in tables:
        return
    cols = {row[1] for row in conn.execute("PRAGMA table_info(holdings)").fetchall()}
    if "portfolio_id" not in cols:
        print("Old holdings schema detected — dropping table (will be repopulated by ingest).")
        conn.execute("DROP TABLE holdings")
        conn.commit()


def _create_tables(conn):
    """Create all five tables if they don't already exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id          TEXT PRIMARY KEY,
            name        TEXT,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS holdings (
            portfolio_id  TEXT NOT NULL,
            ticker        TEXT NOT NULL,
            name          TEXT NOT NULL,
            units         REAL,
            avg_cost_p    REAL,
            total_cost    REAL,
            last_updated  TEXT,
            PRIMARY KEY (portfolio_id, ticker),
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id)
        );

        CREATE TABLE IF NOT EXISTS holding_meta (
            ticker           TEXT PRIMARY KEY,
            asset_class      TEXT,
            geographic_focus TEXT,
            sector           TEXT,
            notes            TEXT
        );

        CREATE TABLE IF NOT EXISTS prices (
            ticker  TEXT NOT NULL,
            date    TEXT NOT NULL,
            close   REAL NOT NULL,
            PRIMARY KEY (ticker, date)
        );

        CREATE TABLE IF NOT EXISTS macro (
            date          TEXT PRIMARY KEY,
            boe_base_rate REAL,
            cpi_yoy       REAL
        );
    """)
    conn.commit()


def register_portfolio(conn, portfolio_id, name):
    """Add a portfolio row if one with this ID doesn't already exist."""
    conn.execute("""
        INSERT OR IGNORE INTO portfolios (id, name, created_at) VALUES (?, ?, ?)
    """, (portfolio_id, name, datetime.today().strftime("%Y-%m-%d")))
    conn.commit()


def seed_holding_meta(conn):
    """Insert a blank holding_meta row for every ticker not yet classified, then flag any gaps."""
    conn.execute("""
        INSERT OR IGNORE INTO holding_meta (ticker, asset_class, geographic_focus, sector, notes)
        SELECT DISTINCT ticker, NULL, NULL, NULL, NULL FROM holdings
    """)
    conn.commit()

    empty = conn.execute("""
        SELECT DISTINCT h.ticker, h.name FROM holdings h
        JOIN holding_meta m ON h.ticker = m.ticker
        WHERE m.asset_class IS NULL
    """).fetchall()

    if empty:
        print(f"\n[ACTION NEEDED] Fill in holding_meta for {len(empty)} holdings.")
        print("  Ask Claude: 'Fill in the holding_meta table for my holdings'")


def print_summary(conn):
    """Print row counts for every table, holdings per portfolio, and price date ranges."""
    print("\n--- Database summary ---")
    for table in ["portfolios", "holdings", "holding_meta", "prices", "macro"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    holdings_by_portfolio = conn.execute("""
        SELECT p.name, COUNT(h.ticker)
        FROM portfolios p
        LEFT JOIN holdings h ON p.id = h.portfolio_id
        GROUP BY p.id
    """).fetchall()
    if holdings_by_portfolio:
        print("\n  Holdings per portfolio:")
        for name, count in holdings_by_portfolio:
            print(f"    {name}: {count}")

    coverage = conn.execute("""
        SELECT ticker, MIN(date), MAX(date), COUNT(*)
        FROM prices GROUP BY ticker ORDER BY ticker
    """).fetchall()
    if coverage:
        print("\n  Price coverage:")
        for ticker, start, end, n in coverage:
            print(f"    {ticker}: {start} -> {end} ({n} days)")
