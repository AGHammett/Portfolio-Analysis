# Portfolio Analyser

## Project overview
This project analyses a personal UK investment portfolio held with Hargreaves Lansdown.
The portfolio consists primarily of funds and ETFs. All monetary values are in GBP.

## Database
SQLite database at `data/portfolio.db` with four tables:
- `holdings` — current positions: ticker, name, asset_class, region, quantity, avg_cost
- `prices` — daily closing prices: ticker, date, close
- `macro` — economic context: date, boe_base_rate, cpi_yoy
- `holding_meta` — tags for each holding: ticker, asset_class, geographic_focus, sector

Always use the SQLite MCP tool to query the database rather than reading files directly.
When exploring an unfamiliar question, run `list_tables` and `describe_table` first.

## Behaviour rules
- Default date range for analysis is the last 12 months unless the user specifies otherwise
- Always calculate returns as percentage change from first to last adjusted close price
- When comparing to benchmarks, use the same date range as the portfolio data
- Benchmarks available in the prices table: ^FTSE (FTSE 100), VWRL.L (FTSE All-World), ^GSPC (S&P 500 Index), (^IXIC) (Nasdaq Composite)
- Frame answers in plain English after showing any numbers
- Always note that past performance does not predict future returns
- If data is missing for a ticker, say so clearly rather than silently skipping it

## Skills
- `analysis` — use for performance, returns, volatility, Sharpe ratio questions
- `benchmark` — use for comparisons against FTSE or other indices
- `macro` — use for questions involving interest rates or inflation context

## Data ingestion
Run `scripts/ingest.py` to refresh prices and load a new HL export.
The HL CSV export lives in `data/raw/hl_export.csv`.