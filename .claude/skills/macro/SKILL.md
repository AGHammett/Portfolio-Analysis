---
name: macro
description: "Use when asked about the effect of interest rates, inflation, or macroeconomic conditions on the portfolio or holdings, or when asked about real returns, purchasing power, or how the economic environment has affected performance"
---

# Macro overlay skill

## Context

The macro table contains two series:
- `boe_base_rate`: Bank of England base rate at each change date (not daily — forward-fill
  to match against daily price data)
- `cpi_yoy`: ONS CPI year-on-year inflation rate, monthly frequency

When joining macro data to price data, forward-fill the most recent macro value to cover
dates between observations. The base rate only changes periodically; CPI is monthly.

## Key macro periods in the dataset

Be aware of these regimes when interpreting results — they are highly relevant context:
- Pre-2022: base rate near zero (0.1%), low inflation
- 2022-2023: rapid rate rises from 0.25% to 5.25%, CPI peaking above 11%
- 2024-2026: gradual rate cuts from 5.25% toward current level

These shifts are the most significant macro events in the dataset and should be
referenced when they're relevant to the analysis period.

## Real returns

When calculating real returns:
- Nominal return: percentage price change over the period
- Real return: adjust for cumulative CPI inflation over the same period
- Formula: real return = ((1 + nominal return) / (1 + cumulative inflation)) − 1
- Always present both nominal and real return side by side so the impact is clear

## Rate sensitivity framing

When asked how rate changes affected holdings:
- Pull base rate history and price history over the same window
- Identify the key rate change dates and note price behaviour around them
- Do not claim direct causation — note correlation and flag other confounding factors
- Growth and technology holdings (Baillie Gifford, L&G Tech) are generally more
  sensitive to rate rises due to duration effects on valuations
- Defence and broad equity holdings tend to be less rate-sensitive
- Use holding_meta sector and geographic_focus to contextualise sensitivity

## Inflation context

When discussing purchasing power or real returns:
- Note if real returns were negative even when nominal returns were positive
- The 2022 inflation spike is likely to have produced negative real returns on most
  holdings — this is worth surfacing explicitly if the analysis window includes it
- CPI data is monthly; interpolate or use month-start values when aligning with daily prices

## Output format

Lead with the macro context (what rates and inflation were doing over the period),
then present how the portfolio or holding performed within that context.
Always show both nominal and real returns when inflation is relevant.
Plain English interpretation should explain what the macro environment meant for
this specific portfolio given its composition — not generic macro commentary.

## Plotting

When the user asks for a chart or visual, use the plotting MCP server:
- `plot_performance(tickers, label_map, ..., show_macro=True)` — normalised price performance with BoE base rate and CPI on a dual y-axis
- `plot_real_vs_nominal(tickers, label_map, ...)` — nominal vs CPI-adjusted real return lines per ticker

Charts are saved as interactive HTML to `output/charts/`.