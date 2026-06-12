---
name: analysis
description: "Use when asked about portfolio or holding performance, returns, risk, volatility, concentration, sector or geographic breakdown, or general analysis questions about the portfolio"
---

# Portfolio analysis skill

## Context

Holdings are in the holdings table. Metadata (asset class, geographic focus, sector) is in
holding_meta — always join these for any breakdown or concentration analysis.
Price history is in the prices table. All monetary values are in GBP.

Benchmarks (^FTSE, VWRL.L) are in the prices table but are NOT holdings — never include
them in portfolio weights, concentration calculations, or aggregate portfolio returns.

## Calculation conventions

**Returns**
- Percentage change from first to last close price in the window
- Default window: last 12 months unless specified
- Portfolio-level return: weight each holding's return by its proportion of total cost

**Volatility**
- Annualised: std dev of daily returns × √252
- Daily return: (close_today − close_yesterday) / close_yesterday

**Sharpe ratio**
- (Annualised return − risk-free rate) / annualised volatility
- Risk-free rate: most recent BoE base rate from macro table

**Drawdown**
- Maximum drawdown: largest peak-to-trough decline in the period
- Worth including for any holding that has underperformed or shown high volatility

## Concentration analysis

When asked about portfolio breakdown or concentration:
- Calculate each holding's weight as a percentage of total portfolio cost
- Break down by geographic_focus and sector from holding_meta
- Flag any single holding above 30% of portfolio as concentrated
- Flag if a single sector or geography exceeds 50% of the portfolio

## Output format

For single holding analysis: metrics first, plain English interpretation below.
For portfolio-level analysis: summary table of all holdings with key metrics,
then aggregate figures, then a short interpretation.
Always state the date range used.
Always note that past performance does not predict future returns.

## Plotting

When the user asks for a chart or visual, use the plotting MCP server tools (call via Python if not available as MCP tools in-session):
- `plot_performance(tickers, label_map, ...)` — normalised price lines for individual holdings
- `plot_portfolio_breakdown(portfolio_id, breakdown_by)` — pie chart by holding, sector, or geography
- `plot_portfolio_performance(portfolio_id, benchmark_tickers, ...)` — aggregate portfolio value vs benchmark

Charts are saved as interactive HTML to `output/charts/` — tell the user to open the file in a browser.