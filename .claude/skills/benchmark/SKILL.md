---
name: benchmark
description: "Use when asked to compare portfolio or holding performance against a benchmark or index, or when asked about relative performance, beating the market, or how holdings compare to FTSE or other indices"
---

# Benchmark comparison skill

## Context

Benchmarks available in the prices table: `^FTSE` (FTSE 100) and `VWRL.L` (Vanguard FTSE All-World).
These are NOT holdings — never include them in portfolio-level calculations or weights.
Holdings are identified by joining the prices table with the holdings table on ticker.

The default benchmark is `^FTSE` unless the user specifies otherwise or the portfolio's
geographic focus makes VWRL.L more appropriate (e.g. for a globally diversified portfolio,
VWRL.L is often the better comparator).

## Approach

Always use the same date range for both the holding/portfolio and the benchmark.
Default to the last 12 months unless the user specifies otherwise.
Use daily close prices from the prices table throughout.

For the risk-free rate in Sharpe ratio calculations, use the most recent BoE base rate
from the macro table. Query it as: SELECT boe_base_rate FROM macro WHERE boe_base_rate
IS NOT NULL ORDER BY date DESC LIMIT 1.

## Metrics to include in every benchmark comparison

**Returns**
- Holding/portfolio total return over the period (percentage change, first to last close)
- Benchmark total return over the same period
- Excess return (holding minus benchmark)

**Volatility**
- Annualised volatility for the holding (std dev of daily returns × √252)
- Annualised volatility for the benchmark
- Higher volatility with lower return than the benchmark is worth flagging explicitly

**Sharpe ratio**
- For both the holding and the benchmark
- Use annualised return and annualised volatility
- Formula: (annualised return − risk-free rate) / annualised volatility
- A Sharpe below the benchmark's Sharpe means worse risk-adjusted performance even
  if raw returns are similar

**Correlation and covariance**
- Pearson correlation of daily returns between the holding and benchmark
- Covariance of daily returns
- Note what the correlation implies: high correlation (>0.8) means the holding moves
  closely with the benchmark and offers limited diversification benefit;
  low correlation suggests more independent behaviour

## Output format

Present results in a comparison table with holding and benchmark side by side, then
a short plain English interpretation covering: did it beat the benchmark, was the
risk worth it (Sharpe), and what does the correlation suggest about diversification.

Always note the exact date range used.
Always note that past performance does not predict future returns.

## Plotting

Only generate a chart if the user explicitly requests one. Do not plot by default.

When plotting is requested, use the plotting MCP server:
- `plot_performance(tickers, label_map, ...)` — normalised price lines for individual holdings vs benchmark tickers
- `plot_portfolio_performance(portfolio_id, benchmark_tickers, benchmark_label_map, ...)` — aggregate portfolio value vs one or more benchmarks

Charts are saved as interactive HTML to `output/charts/`.