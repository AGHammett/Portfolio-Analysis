# Portfolio Analyser

A personal UK investment portfolio analysis tool. Ingests holdings from Hargreaves Lansdown CSV exports, fetches price history via Yahoo Finance, and stores everything in a local SQLite database for querying and analysis with Claude.

## Features

- Supports multiple portfolios (e.g. ISA and LISA) in a single database
- Fetches 5 years of daily price history for all holdings and benchmarks
- Loads macroeconomic context: BoE base rate and ONS CPI inflation
- Compares portfolio performance against FTSE 100, FTSE All-World, S&P 500, and Nasdaq
- All values in GBP

## Project structure

```
config.py                        ← portfolios, benchmarks, settings, ticker map
.mcp.json.example                ← MCP server config template (copy to .mcp.json)
scripts/
    ingest.py                    ← run this to refresh all data
src/pipeline/
    db.py                        ← database connection, schema, migrations
    parsers/
        hargreaves_lansdown.py   ← HL CSV parsing
        trading212.py            ← future
    loaders/
        prices.py                ← Yahoo Finance price history
        macro.py                 ← BoE base rate + ONS CPI
src/mcp_servers/
    yfinance_server.py           ← MCP server for on-demand price fetching
data/
    portfolio.db                 ← SQLite database (gitignored)
    raw/
        hl_isa.csv               ← HL export for ISA (gitignored)
        hl_lisa.csv              ← HL export for LISA (gitignored)
        boe_rates.csv            ← BoE base rate history (gitignored)
        ons_cpi.csv              ← ONS CPI time series (gitignored)
```

## Database schema

| Table | Key columns | Notes |
|---|---|---|
| `portfolios` | `id`, `name` | One row per portfolio (e.g. `isa`, `lisa`) |
| `holdings` | `portfolio_id`, `ticker`, `units`, `avg_cost_p`, `total_cost` | Refreshed on each ingest run |
| `holding_meta` | `ticker`, `asset_class`, `geographic_focus`, `sector` | Shared across portfolios; fill in once |
| `prices` | `ticker`, `date`, `close` | Daily adjusted close prices |
| `macro` | `date`, `boe_base_rate`, `cpi_yoy` | Monthly macro context |

## Setup

1. Clone the repo and create a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   source .venv/bin/activate   # macOS / Linux
   pip install polars yfinance mcp
   ```

2. Edit `config.py` to match your portfolios and file paths.

3. Export your portfolio from your broker's platform (I use Hargreaves Lansdown) and save the CSV files to `data/raw/`.

4. Download macro data:
   - **BoE base rate**: [bankofengland.co.uk](https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp) → Export → save as `data/raw/boe_rates.csv`
   - **ONS CPI**: [ons.gov.uk](https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23) → Download → save as `data/raw/ons_cpi.csv`

5. Run the ingest script:
   ```
   python scripts/ingest.py
   ```

6. Set up the MCP servers for Claude Code:
   ```
   cp .mcp.json.example .mcp.json   # or copy on Windows
   ```
   Then edit `.mcp.json` and replace the placeholder paths with your actual paths:
   - `sqlite` → absolute path to `data/portfolio.db`
   - `yfinance` → path to your Python executable and to `src/mcp_servers/yfinance_server.py`

   On **macOS/Linux**, change `"command": "npx.cmd"` to `"command": "npx"` in the sqlite entry.

## Adding a new holding

When a holding appears in the HL export but has no Yahoo Finance ticker, ingest will flag it:

```
[ACTION NEEDED] 1 holdings have no ticker mapping.
Add them to TICKER_MAP in config.py:
  "vanguard lifestrategy 80% equity": "TICKER.L",
```

Add the entry to `TICKER_MAP` in `config.py` and re-run ingest.

## Analysis

Open a Claude Code session in this directory (`claude`) and ask questions in plain English. Four specialised skills handle different types of question:

### `/analysis`
Performance, returns, and risk. Use this for questions about how holdings or the overall portfolio have done — total return, volatility, Sharpe ratio, concentration, and sector or geographic breakdown.

- *How has my ISA performed over the last year?*
- *Which holdings have been the biggest drag on returns?*
- *What's my exposure by asset class and geography?*

### `/benchmark`
Relative performance. Compares the portfolio or individual holdings against an index — FTSE 100, FTSE All-World, S&P 500, or Nasdaq — over the same date range.

- *Compare my portfolio against the FTSE 100*
- *Am I beating the market?*
- *How does my ISA compare to a simple VWRL investment?*

### `/macro`
Economic context. Overlays BoE base rate and ONS CPI data to frame returns in terms of the interest rate environment and inflation — useful for understanding real purchasing-power gains or losses.

- *How have my real returns compared to inflation?*
- *How has the rate cycle affected my bond holdings?*
- *What's my portfolio returned above the risk-free rate?*

### `/counterfactual`
What-if scenarios. Simulates how the portfolio would have performed under hypothetical changes — swapping a holding, adding a new position, or redistributing weights — using actual historical prices.

- *How would my ISA have performed if I'd put 10% into AAPL a year ago?*
- *What if I'd swapped RR.L for BA.L six months ago?*
- *How would an equal-weight version of my portfolio have done?*

Past performance does not predict future returns.
