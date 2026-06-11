---
name: counterfactual
description: "Use when asked about hypothetical portfolio changes, what-if scenarios, how the portfolio would look with different holdings, redistributing weights, swapping one holding for another, or adding a new position"
---

# Counterfactual analysis skill

## Context

Counterfactual queries ask how the portfolio would have performed under different
conditions. Two types:

1. **Full swap** — "what if I'd held AAPL instead of Fundsmith"
   Replace one holding entirely with another over the same period

2. **Weight redistribution** — "what if I'd put 5% into AAPL"
   Reduce existing holdings proportionally to fund a new position,
   or shift weight between existing holdings

The counterfactual ticker may or may not be in the prices table. Always check first:
SELECT COUNT(*) FROM prices WHERE ticker = 'TICKER'. If it returns 0, use the
fetch_ticker_prices tool from the yfinance MCP server to fetch it automatically
before proceeding with the analysis. Do not ask the user to do this manually.

## Date range

Default to the longest period for which both the actual and counterfactual tickers
have price data. If the counterfactual ticker has a shorter history than the holding
being replaced, note this clearly and use the overlapping period only.

## Full swap calculation

1. Get the actual holding's return over the period from the prices table
2. Get the counterfactual ticker's return over the same period
3. Recalculate portfolio return substituting the counterfactual return for the
   actual holding's return, keeping all other holdings and weights unchanged
4. Compare actual vs counterfactual: total return, annualised volatility, Sharpe ratio

Weight the counterfactual holding at the same cost weight as the holding it replaces.
Use total_cost from the holdings table to calculate weights.

## Weight redistribution calculation

For "add X% into TICKER":
- The new position takes X% of total portfolio cost
- Reduce all other holdings proportionally by their share of the remaining (100-X)%
- Recalculate portfolio return with new weights applied
- If X% would require selling part of a specific holding (e.g. "take 5% from Fundsmith
  and put it into AAPL"), apply the reduction only to that holding

For partial weight shifts, always state the implied trade clearly:
"This would mean reducing [holding] from X% to Y% of the portfolio"

## Output format

Present a side-by-side comparison table:

| Metric            | Actual portfolio | Counterfactual |
|-------------------|-----------------|----------------|
| Total return      |                 |                |
| Annualised vol    |                 |                |
| Sharpe ratio      |                 |                |
| Best month        |                 |                |
| Worst month       |                 |                |

Follow with a plain English summary covering:
- Whether the counterfactual would have been better or worse and by how much
- Whether the risk profile changes materially
- Any caveats (e.g. shorter data history, different asset class characteristics)

Always note that this is backward-looking and past outperformance does not imply
it would outperform in future. Never frame the output as a recommendation.