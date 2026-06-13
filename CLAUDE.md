# Portfolio Analyser

## Project overview
This project analyses a personal UK investment portfolio (ISA + LISA) held with Hargreaves Lansdown.
The portfolio consists primarily of funds and ETFs. All monetary values are in GBP.

## Database
SQLite database at `data/portfolio.db` with five tables:
- `portfolios` — portfolio registry: id, name, created_at
- `holdings` — current positions keyed by (portfolio_id, ticker): name, units, avg_cost_p, total_cost, last_updated
- `prices` — daily closing prices: ticker, date, close
- `macro` — economic context: date, boe_base_rate, cpi_yoy
- `holding_meta` — tags per ticker (shared across portfolios): ticker, asset_class, geographic_focus, sector

Always use the SQLite MCP tool to query the database rather than reading files directly.
When exploring an unfamiliar question, run `list_tables` and `describe_table` first.
When querying holdings across portfolios, join `holdings` to `portfolios` on `portfolio_id`.

## Behaviour rules
- Default date range for analysis is the last 12 months unless the user specifies otherwise
- Always calculate returns as percentage change from first to last adjusted close price
- When comparing to benchmarks, use the same date range as the portfolio data
- Benchmarks available in the prices table: ^FTSE (FTSE 100), VWRL.L (FTSE All-World), ^GSPC (S&P 500 Index), ^IXIC (Nasdaq Composite)
- Frame answers in plain English after showing any numbers
- Always note that past performance does not predict future returns
- If data is missing for a ticker, say so clearly rather than silently skipping it

## Skills
- `analysis` — use for performance, returns, volatility, Sharpe ratio questions
- `benchmark` — use for comparisons against FTSE or other indices
- `macro` — use for questions involving interest rates or inflation context
- `counterfactual` — use for what-if scenarios: swapping holdings, adding new positions, redistributing weights

## MCP servers
Three MCP servers are available (configured in `.mcp.json`):
- `sqlite` — read/write access to `data/portfolio.db`; runs locally via npx; use this for all database queries
- `yfinance` — fetches price history for any Yahoo Finance ticker and inserts it into the prices table; runs in Docker (`portfolio-mcp` image); use the `fetch_ticker_prices` tool when a counterfactual ticker is not yet in the prices table
- `plotting` — generates interactive Plotly charts saved as HTML to `output/charts/`; runs in Docker (`portfolio-mcp` image); use when the user explicitly asks for a chart or visual

## Plotting tools
The plotting MCP server exposes five tools:
- `plot_performance(tickers, label_map, start_date, end_date, title, show_macro)` — normalised price lines for individual tickers; pass `show_macro=True` to overlay BoE base rate and CPI on a second y-axis
- `plot_portfolio_performance(portfolio_id, benchmark_tickers, benchmark_label_map, start_date, end_date, min_coverage)` — aggregate portfolio value (units × price, summed) normalised to 100, with benchmark overlays; excludes holdings below `min_coverage` (default 50%) and warns
- `plot_portfolio_real_vs_nominal(portfolio_id, start_date, end_date, min_coverage)` — aggregate portfolio value as both nominal and CPI-adjusted real return on one chart
- `plot_portfolio_breakdown(portfolio_id, breakdown_by)` — pie chart by holding, sector, or geography
- `plot_real_vs_nominal(tickers, label_map, start_date, end_date)` — nominal vs CPI-adjusted real return lines for individual tickers

If the plotting tools are not available as MCP tools in the current session, run the Docker container directly: `docker run --rm -i -v <absolute-path-to-repo>:/app portfolio-mcp python src/mcp_servers/plotting_server.py`.

## Data ingestion
Run `scripts/ingest.py` to refresh prices and load new HL exports.
Configure portfolios and benchmarks in `config.py` at the project root.
Ticker mappings (HL name fragments → Yahoo Finance tickers) live in `data/ticker_map.json`.
HL CSV exports live in `data/raw/` — file paths are set per portfolio in `config.py`.

## Code layout
```
config.py                        ← portfolios, benchmarks, settings
data/ticker_map.json             ← HL name → Yahoo Finance ticker mappings
scripts/ingest.py                ← thin orchestrator, run this to refresh data
src/pipeline/
    db.py                        ← connection, schema setup, migration, seeding
    parsers/
        hargreaves_lansdown.py   ← HL CSV parsing
        trading212.py            ← future
    loaders/
        prices.py                ← yfinance price history
        macro.py                 ← BoE base rate + ONS CPI
```