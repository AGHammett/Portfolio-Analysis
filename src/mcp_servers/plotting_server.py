"""
MCP plotting server — exposes four chart tools for portfolio analysis.
Charts are saved as interactive HTML files to output/charts/.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import plotly.graph_objects as go
from mcp.server.fastmcp import FastMCP

from src.pipeline.db import get_connection

mcp = FastMCP("plotting")

CHARTS_DIR = PROJECT_ROOT / "output" / "charts"
_COLORS = ["#2196F3", "#FF5722", "#4CAF50", "#9C27B0", "#FF9800", "#00BCD4", "#E91E63", "#795548"]


def _chart_path(tool_name: str) -> Path:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return CHARTS_DIR / f"{tool_name}_{ts}.html"


def _default_dates(start_date: Optional[str], end_date: Optional[str]) -> tuple[str, str]:
    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")
    if start_date is None:
        start_date = (datetime.today() - timedelta(days=365)).strftime("%Y-%m-%d")
    return start_date, end_date


def _common_dates(ticker_date_map: dict[str, list[str]]) -> list[str]:
    """Return sorted dates present in all tickers."""
    sets = [set(dates) for dates in ticker_date_map.values()]
    return sorted(set.intersection(*sets)) if sets else []


def _ffill_macro(common_dates: list[str], macro_rows: list, col_idx: int) -> list[Optional[float]]:
    """Forward-fill a macro column (by col_idx) to align with daily trading dates."""
    lookup = {r[0]: r[col_idx] for r in macro_rows if r[col_idx] is not None}
    sorted_macro_dates = sorted(lookup.keys())
    result: list[Optional[float]] = []
    ptr = 0
    last = None
    for d in common_dates:
        while ptr < len(sorted_macro_dates) and sorted_macro_dates[ptr] <= d:
            last = lookup[sorted_macro_dates[ptr]]
            ptr += 1
        result.append(last)
    return result


def _save_and_respond(fig: go.Figure, tool_name: str) -> str:
    path = _chart_path(tool_name)
    fig.write_html(str(path))
    return f"Chart saved to {path.relative_to(PROJECT_ROOT)} — open in browser to view."


@mcp.tool()
def plot_performance(
    tickers: list[str],
    label_map: Optional[dict[str, str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """Plot normalised price performance for one or more tickers over a date range."""
    start_date, end_date = _default_dates(start_date, end_date)
    label_map = label_map or {}
    title = title or "Performance Comparison"

    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(tickers))
        rows = conn.execute(
            f"SELECT ticker, date, close FROM prices "
            f"WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
            tickers + [start_date, end_date],
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        return "No price data found for the specified tickers and date range."

    ticker_prices: dict[str, dict[str, float]] = {t: {} for t in tickers}
    for ticker, date, close in rows:
        ticker_prices[ticker][date] = close

    common_dates = _common_dates({t: list(d.keys()) for t, d in ticker_prices.items()})
    if len(common_dates) < 2:
        return "Insufficient overlapping price data across all tickers for the specified date range."

    fig = go.Figure()
    for i, ticker in enumerate(tickers):
        closes = [ticker_prices[ticker][d] for d in common_dates]
        normalised = [c / closes[0] * 100 for c in closes]
        label = label_map.get(ticker, ticker)
        fig.add_trace(go.Scatter(
            x=common_dates, y=normalised, mode="lines", name=label,
            line=dict(color=_COLORS[i % len(_COLORS)], width=2),
            hovertemplate=f"<b>{label}</b><br>%{{x}}<br>Value: %{{y:.1f}}<extra></extra>",
        ))

    fig.update_layout(
        title=title, xaxis_title="Date",
        yaxis_title="Normalised Value (100 = start)",
        hovermode="x unified", template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return _save_and_respond(fig, "performance")


@mcp.tool()
def plot_portfolio_breakdown(
    portfolio_id: str,
    breakdown_by: str,
) -> str:
    """Plot a pie chart of portfolio weights by holding, sector, or geography."""
    if breakdown_by not in ("holding", "sector", "geography"):
        return "breakdown_by must be one of: holding, sector, geography"

    conn = get_connection()
    try:
        if breakdown_by == "holding":
            rows = conn.execute(
                "SELECT name, total_cost FROM holdings "
                "WHERE portfolio_id = ? AND total_cost IS NOT NULL",
                (portfolio_id,),
            ).fetchall()
        else:
            meta_col = "sector" if breakdown_by == "sector" else "geographic_focus"
            rows = conn.execute(
                f"SELECT COALESCE(m.{meta_col}, 'Unknown'), SUM(h.total_cost) "
                f"FROM holdings h LEFT JOIN holding_meta m ON h.ticker = m.ticker "
                f"WHERE h.portfolio_id = ? AND h.total_cost IS NOT NULL "
                f"GROUP BY m.{meta_col}",
                (portfolio_id,),
            ).fetchall()
    finally:
        conn.close()

    if not rows:
        return f"No holdings found for portfolio '{portfolio_id}'."

    labels, values = zip(*rows)
    breakdown_title = {"holding": "Holdings", "sector": "Sector", "geography": "Geography"}[breakdown_by]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>Cost: £%{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Portfolio Breakdown by {breakdown_title} — {portfolio_id.upper()}",
        template="plotly_white",
    )
    return _save_and_respond(fig, "breakdown")


@mcp.tool()
def plot_macro_overlay(
    tickers: list[str],
    label_map: Optional[dict[str, str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """Plot normalised price performance alongside BoE base rate and CPI on a dual y-axis chart."""
    start_date, end_date = _default_dates(start_date, end_date)
    label_map = label_map or {}

    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(tickers))
        price_rows = conn.execute(
            f"SELECT ticker, date, close FROM prices "
            f"WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
            tickers + [start_date, end_date],
        ).fetchall()
        # Fetch from before start_date to seed forward-fill
        macro_rows = conn.execute(
            "SELECT date, boe_base_rate, cpi_yoy FROM macro WHERE date <= ? ORDER BY date",
            (end_date,),
        ).fetchall()
    finally:
        conn.close()

    if not price_rows:
        return "No price data found for the specified tickers and date range."

    ticker_prices: dict[str, dict[str, float]] = {t: {} for t in tickers}
    for ticker, date, close in price_rows:
        ticker_prices[ticker][date] = close

    common_dates = _common_dates({t: list(d.keys()) for t, d in ticker_prices.items()})
    if len(common_dates) < 2:
        return "Insufficient overlapping price data across all tickers."

    fig = go.Figure()
    for i, ticker in enumerate(tickers):
        closes = [ticker_prices[ticker][d] for d in common_dates]
        normalised = [c / closes[0] * 100 for c in closes]
        label = label_map.get(ticker, ticker)
        fig.add_trace(go.Scatter(
            x=common_dates, y=normalised, mode="lines", name=label,
            line=dict(color=_COLORS[i % len(_COLORS)], width=2), yaxis="y1",
            hovertemplate=f"<b>{label}</b><br>%{{x}}<br>Value: %{{y:.1f}}<extra></extra>",
        ))

    boe_vals = _ffill_macro(common_dates, macro_rows, col_idx=1)
    cpi_vals = _ffill_macro(common_dates, macro_rows, col_idx=2)

    if any(v is not None for v in boe_vals):
        fig.add_trace(go.Scatter(
            x=common_dates, y=boe_vals, mode="lines", name="BoE Base Rate (%)",
            line=dict(color="#607D8B", width=1.5, dash="dot"), yaxis="y2",
            hovertemplate="<b>BoE Rate</b><br>%{x}<br>%{y:.2f}%<extra></extra>",
        ))
    if any(v is not None for v in cpi_vals):
        fig.add_trace(go.Scatter(
            x=common_dates, y=cpi_vals, mode="lines", name="CPI YoY (%)",
            line=dict(color="#F44336", width=1.5, dash="dash"), yaxis="y2",
            hovertemplate="<b>CPI YoY</b><br>%{x}<br>%{y:.2f}%<extra></extra>",
        ))

    fig.update_layout(
        title="Performance vs Macro Indicators",
        xaxis_title="Date",
        yaxis=dict(title="Normalised Value (100 = start)", side="left"),
        yaxis2=dict(title="Rate / CPI (%)", side="right", overlaying="y", showgrid=False),
        hovermode="x unified", template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return _save_and_respond(fig, "macro_overlay")


@mcp.tool()
def plot_real_vs_nominal(
    tickers: list[str],
    label_map: Optional[dict[str, str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> str:
    """For each ticker, plot both the nominal return and the CPI-adjusted real return normalised to 100."""
    start_date, end_date = _default_dates(start_date, end_date)
    label_map = label_map or {}

    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(tickers))
        price_rows = conn.execute(
            f"SELECT ticker, date, close FROM prices "
            f"WHERE ticker IN ({placeholders}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
            tickers + [start_date, end_date],
        ).fetchall()
        macro_rows = conn.execute(
            "SELECT date, cpi_yoy FROM macro WHERE date <= ? ORDER BY date",
            (end_date,),
        ).fetchall()
    finally:
        conn.close()

    if not price_rows:
        return "No price data found for the specified tickers and date range."
    if not macro_rows:
        return "No CPI data found. Run ingest.py to load macro data."

    ticker_prices: dict[str, dict[str, float]] = {t: {} for t in tickers}
    for ticker, date, close in price_rows:
        ticker_prices[ticker][date] = close

    common_dates = _common_dates({t: list(d.keys()) for t, d in ticker_prices.items()})
    if len(common_dates) < 2:
        return "Insufficient overlapping price data across all tickers."

    # Build cumulative CPI factor for each common date, starting at 1.0 on day 0.
    # Uses forward-filled monthly CPI YoY, converted to a daily compounding rate.
    cpi_ffilled = _ffill_macro(common_dates, [(r[0], r[1]) for r in macro_rows], col_idx=1)
    cumulative_cpi: list[float] = []
    factor = 1.0
    for cpi_yoy in cpi_ffilled:
        cumulative_cpi.append(factor)  # record before compounding so day-0 factor = 1.0
        rate = cpi_yoy if cpi_yoy is not None else 0.0
        daily_rate = (1 + rate / 100) ** (1 / 365) - 1
        factor *= (1 + daily_rate)

    fig = go.Figure()
    for i, ticker in enumerate(tickers):
        closes = [ticker_prices[ticker][d] for d in common_dates]
        base = closes[0]
        nominal = [c / base * 100 for c in closes]
        real = [c / base / cpi * 100 for c, cpi in zip(closes, cumulative_cpi)]
        label = label_map.get(ticker, ticker)
        color = _COLORS[i % len(_COLORS)]

        fig.add_trace(go.Scatter(
            x=common_dates, y=nominal, mode="lines", name=f"{label} (nominal)",
            line=dict(color=color, width=2),
            hovertemplate=f"<b>{label} nominal</b><br>%{{x}}<br>%{{y:.1f}}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=common_dates, y=real, mode="lines", name=f"{label} (real)",
            line=dict(color=color, width=1.5, dash="dash"),
            hovertemplate=f"<b>{label} real</b><br>%{{x}}<br>%{{y:.1f}}<extra></extra>",
        ))

    fig.update_layout(
        title="Real vs Nominal Returns (CPI-adjusted)",
        xaxis_title="Date",
        yaxis_title="Normalised Value (100 = start)",
        hovermode="x unified", template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return _save_and_respond(fig, "real_vs_nominal")


@mcp.tool()
def plot_portfolio_performance(
    portfolio_id: str,
    benchmark_tickers: Optional[list[str]] = None,
    benchmark_label_map: Optional[dict[str, str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_coverage: float = 0.5,
) -> str:
    """Plot aggregate portfolio value normalised to 100, with optional benchmark overlays.

    Holdings with price coverage below min_coverage (default 50%) are excluded and
    reported as warnings in the returned message.
    """
    start_date, end_date = _default_dates(start_date, end_date)
    benchmark_tickers = benchmark_tickers or []
    benchmark_label_map = benchmark_label_map or {}

    conn = get_connection()
    try:
        holding_rows = conn.execute(
            "SELECT ticker, name, units FROM holdings WHERE portfolio_id = ?",
            (portfolio_id,),
        ).fetchall()

        if not holding_rows:
            return f"No holdings found for portfolio '{portfolio_id}'."

        holding_tickers = [r[0] for r in holding_rows]
        units_map = {r[0]: r[2] for r in holding_rows}
        name_map = {r[0]: r[1] for r in holding_rows}

        ph = ",".join("?" * len(holding_tickers))
        price_rows = conn.execute(
            f"SELECT ticker, date, close FROM prices "
            f"WHERE ticker IN ({ph}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
            holding_tickers + [start_date, end_date],
        ).fetchall()

        bench_price_rows = []
        if benchmark_tickers:
            bph = ",".join("?" * len(benchmark_tickers))
            bench_price_rows = conn.execute(
                f"SELECT ticker, date, close FROM prices "
                f"WHERE ticker IN ({bph}) AND date BETWEEN ? AND ? ORDER BY ticker, date",
                benchmark_tickers + [start_date, end_date],
            ).fetchall()
    finally:
        conn.close()

    ticker_prices: dict[str, dict[str, float]] = {t: {} for t in holding_tickers}
    for ticker, date, close in price_rows:
        ticker_prices[ticker][date] = close

    all_dates = sorted({d for prices in ticker_prices.values() for d in prices})
    total_days = len(all_dates)

    if total_days == 0:
        return "No price data found for any holdings in the specified date range."

    warnings: list[str] = []
    valid_tickers: list[str] = []
    for ticker in holding_tickers:
        coverage = len(ticker_prices[ticker]) / total_days
        if coverage < min_coverage:
            warnings.append(
                f"  • {name_map[ticker]} ({ticker}): {coverage * 100:.0f}% price coverage — excluded"
            )
        else:
            valid_tickers.append(ticker)

    if not valid_tickers:
        msg = "No holdings had sufficient price coverage (min_coverage={min_coverage:.0%})."
        if warnings:
            msg += "\n\nExcluded holdings:\n" + "\n".join(warnings)
        return msg

    def _ffill(date_price: dict[str, float], dates: list[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        last: Optional[float] = None
        for d in dates:
            if d in date_price:
                last = date_price[d]
            if last is not None:
                out[d] = last
        return out

    filled = {t: _ffill(ticker_prices[t], all_dates) for t in valid_tickers}

    portfolio_value: dict[str, float] = {}
    for d in all_dates:
        val = sum(
            (units_map[t] or 0) * filled[t][d]
            for t in valid_tickers
            if d in filled[t]
        )
        if val > 0:
            portfolio_value[d] = val

    if len(portfolio_value) < 2:
        return "Insufficient data to plot portfolio value."

    value_dates = sorted(portfolio_value)
    values = [portfolio_value[d] for d in value_dates]
    base = values[0]
    normalised = [v / base * 100 for v in values]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=value_dates, y=normalised, mode="lines",
        name=portfolio_id.upper(),
        line=dict(color=_COLORS[0], width=2.5),
        hovertemplate=f"<b>{portfolio_id.upper()}</b><br>%{{x}}<br>Value: %{{y:.1f}}<extra></extra>",
    ))

    bench_prices: dict[str, dict[str, float]] = {}
    for ticker, date, close in bench_price_rows:
        bench_prices.setdefault(ticker, {})[date] = close

    for i, ticker in enumerate(benchmark_tickers):
        bdata = bench_prices.get(ticker, {})
        if not bdata:
            warnings.append(f"  • Benchmark {ticker}: no price data — excluded")
            continue
        bdates = sorted(bdata)
        bcloses = [bdata[d] for d in bdates]
        label = benchmark_label_map.get(ticker, ticker)
        fig.add_trace(go.Scatter(
            x=bdates, y=[c / bcloses[0] * 100 for c in bcloses],
            mode="lines", name=label,
            line=dict(color=_COLORS[(i + 1) % len(_COLORS)], width=2, dash="dash"),
            hovertemplate=f"<b>{label}</b><br>%{{x}}<br>Value: %{{y:.1f}}<extra></extra>",
        ))

    fig.update_layout(
        title=f"Portfolio Performance — {portfolio_id.upper()} vs Benchmark",
        xaxis_title="Date",
        yaxis_title="Normalised Value (100 = start)",
        hovermode="x unified", template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    result = _save_and_respond(fig, "portfolio_performance")
    if warnings:
        result += "\n\nData warnings:\n" + "\n".join(warnings)
    return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
