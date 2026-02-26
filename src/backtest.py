from __future__ import annotations

import math
from typing import Callable

import numpy as np
import pandas as pd

from .analyst_events import (
    DEFAULT_ACTION_WEIGHTS,
    DEFAULT_GRADE_MAPPING_RULES,
    build_events_by_ticker,
    compute_signals_for_universe,
)
from .data import (
    build_month_boundaries,
    clamp_date_range_to_prices,
    compute_interval_returns,
)


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if logger is not None:
        logger(message)


def performance_stats(monthly_returns: pd.Series) -> dict[str, float]:
    returns = monthly_returns.dropna().astype(float)
    if returns.empty:
        return {}

    equity = (1.0 + returns).cumprod()
    months = len(returns)
    total_return = float(equity.iloc[-1] - 1.0)
    cagr = float(equity.iloc[-1] ** (12.0 / months) - 1.0) if months > 0 else np.nan
    ann_vol = float(returns.std(ddof=1) * math.sqrt(12.0)) if months > 1 else np.nan
    sharpe_approx = (
        float((returns.mean() * 12.0) / ann_vol)
        if np.isfinite(ann_vol) and ann_vol != 0
        else np.nan
    )
    drawdown = _drawdown_series(equity)

    return {
        "months": float(months),
        "total_return": total_return,
        "CAGR": cagr,
        "ann_vol": ann_vol,
        "sharpe_approx": sharpe_approx,
        "max_drawdown": float(drawdown.min()) if not drawdown.empty else np.nan,
        "hit_rate": float((returns > 0).mean()),
    }


def _drawdown_series(equity_curve: pd.Series) -> pd.Series:
    if equity_curve.empty:
        return equity_curve.copy()
    peak = equity_curve.cummax()
    return equity_curve / peak - 1.0


def _returns_by_month(returns: pd.DataFrame) -> dict[pd.Timestamp, pd.Series]:
    out: dict[pd.Timestamp, pd.Series] = {}
    if returns is None or returns.empty:
        return out
    for month, part in returns.groupby("month", sort=False):
        out[pd.Timestamp(month)] = part.set_index("ticker")["fwd_ret"]
    return out


def run_backtest(
    prices: pd.DataFrame,
    universe: list[str],
    events: pd.DataFrame,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    top_n: int,
    bottom_n: int,
    lookback_days: int,
    benchmark_prices: pd.DataFrame | None = None,
    grade_mapping_rules: list[dict[str, object]] | None = None,
    action_weights: dict[str, float] | None = None,
    logger: Callable[[str], None] | None = None,
) -> dict[str, object]:
    if top_n < 0 or bottom_n < 0:
        raise ValueError("top_n and bottom_n must be >= 0.")
    if top_n == 0 and bottom_n == 0:
        raise ValueError("At least one of top_n or bottom_n must be > 0.")
    if lookback_days <= 0:
        raise ValueError("lookback_days must be > 0.")

    universe_clean = [str(t).upper().strip() for t in universe if str(t).strip()]
    universe_clean = list(dict.fromkeys(universe_clean))
    if not universe_clean:
        raise ValueError("Universe is empty.")

    start_ts, end_ts, prices_min, prices_max = clamp_date_range_to_prices(
        prices=prices,
        start_date=start_date,
        end_date=end_date,
    )
    boundaries = build_month_boundaries(start_date=start_ts, end_date=end_ts)
    _log(
        logger,
        "Backtest date range clamped to "
        f"{start_ts.date()}..{end_ts.date()} (local prices: {prices_min.date()}..{prices_max.date()})",
    )

    price_tickers = set(prices["ticker"].unique())
    missing_price_tickers = [ticker for ticker in universe_clean if ticker not in price_tickers]
    _log(logger, f"Universe size: {len(universe_clean)} | missing price tickers: {len(missing_price_tickers)}")

    forward_returns = compute_interval_returns(
        prices=prices,
        tickers=universe_clean,
        boundaries=boundaries,
    )
    returns_month_map = _returns_by_month(forward_returns)

    benchmark_map: dict[pd.Timestamp, float] = {}
    benchmark_ticker = None
    if benchmark_prices is not None and not benchmark_prices.empty:
        benchmark_ticker = str(benchmark_prices["ticker"].iloc[0]).upper().strip()
        bench_returns = compute_interval_returns(
            prices=benchmark_prices,
            tickers=[benchmark_ticker],
            boundaries=boundaries,
        )
        if not bench_returns.empty:
            benchmark_map = {
                pd.Timestamp(row["month"]): float(row["fwd_ret"])
                for _, row in bench_returns.iterrows()
            }

    events_by_ticker = build_events_by_ticker(events)
    tickers_without_any_events = [
        ticker
        for ticker in universe_clean
        if ticker not in events_by_ticker or events_by_ticker[ticker].empty
    ]
    _log(logger, f"Tickers without cached analyst events: {len(tickers_without_any_events)}")

    monthly_rows: list[dict[str, object]] = []
    ic_rows: list[dict[str, object]] = []

    for month in boundaries[:-1]:
        signal_frame = compute_signals_for_universe(
            events_by_ticker=events_by_ticker,
            universe=universe_clean,
            asof=pd.Timestamp(month),
            lookback_days=lookback_days,
            mapping_rules=grade_mapping_rules or DEFAULT_GRADE_MAPPING_RULES,
            action_weights=action_weights or DEFAULT_ACTION_WEIGHTS,
        )
        signal_frame = signal_frame.sort_values(
            by=["signal", "ticker"], ascending=[False, True]
        ).reset_index(drop=True)

        longs = signal_frame.head(top_n)["ticker"].tolist() if top_n > 0 else []
        shorts = signal_frame.tail(bottom_n)["ticker"].tolist() if bottom_n > 0 else []

        month_returns = returns_month_map.get(pd.Timestamp(month), pd.Series(dtype=float))
        long_rets = month_returns.reindex(longs).dropna().astype(float).tolist()
        short_rets = month_returns.reindex(shorts).dropna().astype(float).tolist()

        portfolio_ret = np.nan
        if longs and long_rets:
            portfolio_ret = float(np.mean(long_rets))
        if bottom_n > 0 and shorts and short_rets:
            base = 0.0 if np.isnan(portfolio_ret) else portfolio_ret
            portfolio_ret = float(base - np.mean(short_rets))

        benchmark_ret = benchmark_map.get(pd.Timestamp(month), np.nan)
        excess_ret = (
            float(portfolio_ret - benchmark_ret)
            if np.isfinite(portfolio_ret) and np.isfinite(benchmark_ret)
            else np.nan
        )

        ic_join = signal_frame[["ticker", "signal"]].merge(
            month_returns.rename("next_month_ret"),
            how="inner",
            left_on="ticker",
            right_index=True,
        )
        ic_join = ic_join.dropna(subset=["signal", "next_month_ret"]).copy()
        if (
            len(ic_join) >= 2
            and ic_join["signal"].nunique() > 1
            and ic_join["next_month_ret"].nunique() > 1
        ):
            ic_value = float(ic_join["signal"].corr(ic_join["next_month_ret"], method="spearman"))
        else:
            ic_value = np.nan

        monthly_rows.append(
            {
                "month": pd.Timestamp(month),
                "portfolio_ret": portfolio_ret,
                "benchmark_ret": benchmark_ret,
                "excess_ret": excess_ret,
                "top_n": int(top_n),
                "bottom_n": int(bottom_n),
                "lookback_days": int(lookback_days),
                "longs": ",".join(longs),
                "shorts": ",".join(shorts),
                "top_signal": float(signal_frame["signal"].iloc[0]) if not signal_frame.empty else np.nan,
            }
        )
        ic_rows.append({"month": pd.Timestamp(month), "ic": ic_value, "n_pairs": int(len(ic_join))})

        _log(
            logger,
            (
                f"{pd.Timestamp(month).date()} | long/short counts {len(longs)}/{len(shorts)} | "
                f"missing long returns {len(longs) - len(long_rets)} | "
                f"missing short returns {len(shorts) - len(short_rets)}"
            ),
        )

    monthly_results = pd.DataFrame(monthly_rows)
    ic_series = pd.DataFrame(ic_rows)

    if monthly_results.empty:
        raise RuntimeError("Backtest produced no monthly rows.")

    portfolio_stats = performance_stats(monthly_results["portfolio_ret"])
    benchmark_stats = performance_stats(monthly_results["benchmark_ret"])

    portfolio_equity = (1.0 + monthly_results["portfolio_ret"].fillna(0.0)).cumprod()
    benchmark_equity = (1.0 + monthly_results["benchmark_ret"].fillna(0.0)).cumprod()
    equity_curve = pd.DataFrame(
        {
            "month": monthly_results["month"],
            "portfolio_equity": portfolio_equity,
            "benchmark_equity": benchmark_equity,
        }
    )
    drawdown_curve = pd.DataFrame(
        {
            "month": monthly_results["month"],
            "portfolio_drawdown": _drawdown_series(portfolio_equity),
            "benchmark_drawdown": _drawdown_series(benchmark_equity),
        }
    )

    ic_non_null = ic_series["ic"].dropna().astype(float) if not ic_series.empty else pd.Series(dtype=float)
    ic_summary = {
        "mean_ic": float(ic_non_null.mean()) if not ic_non_null.empty else np.nan,
        "median_ic": float(ic_non_null.median()) if not ic_non_null.empty else np.nan,
        "months_with_ic": int(ic_non_null.shape[0]),
    }

    diagnostics = {
        "benchmark_ticker": benchmark_ticker,
        "missing_price_tickers_total": len(missing_price_tickers),
        "missing_price_tickers": missing_price_tickers,
        "missing_event_tickers_total": len(tickers_without_any_events),
        "missing_event_tickers": tickers_without_any_events,
        "months_total": int(len(monthly_results)),
        "months_with_portfolio_return": int(monthly_results["portfolio_ret"].notna().sum()),
    }

    return {
        "monthly_results": monthly_results,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "ic_series": ic_series,
        "ic_summary": ic_summary,
        "portfolio_stats": portfolio_stats,
        "benchmark_stats": benchmark_stats,
        "diagnostics": diagnostics,
    }

