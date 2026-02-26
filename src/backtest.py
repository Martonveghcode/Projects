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


def _build_ratings_by_ticker(ratings: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if ratings is None or ratings.empty:
        return {}
    frame = ratings.copy()
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    frame["period"] = pd.to_datetime(frame["period"], errors="coerce")
    frame["net_score"] = pd.to_numeric(frame["net_score"], errors="coerce")
    frame = frame.dropna(subset=["ticker", "period", "net_score"]).reset_index(drop=True)
    frame = frame.sort_values(["ticker", "period"]).reset_index(drop=True)
    return {
        ticker: part.reset_index(drop=True)
        for ticker, part in frame.groupby("ticker", sort=False)
    }


def _signed(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _rank_to_unit_scale(values: pd.Series) -> pd.Series:
    if values is None or values.empty:
        return pd.Series(dtype=float)
    ranked = values.rank(method="average", pct=True)
    return ranked * 2.0 - 1.0


def _consistency_from_history(
    history_rows: list[dict[str, object]],
    lookback_months: int,
    min_observations: int,
) -> dict[str, object]:
    if not history_rows:
        return {
            "raw_score": np.nan,
            "effective_score": 0.0,
            "observations": 0,
            "hit_rate": np.nan,
            "eligible": False,
            "months_scored": 0,
        }

    rows = history_rows[-lookback_months:] if lookback_months > 0 else history_rows
    directional_scores: list[float] = []
    hits = 0

    for row in rows:
        signal = float(row.get("signal", 0.0))
        next_ret = float(row.get("next_month_ret", 0.0))
        signal_sign = _signed(signal)
        ret_sign = _signed(next_ret)
        if signal_sign == 0 or ret_sign == 0:
            continue
        is_hit = signal_sign == ret_sign
        directional_scores.append(1.0 if is_hit else -1.0)
        if is_hit:
            hits += 1

    observations = int(len(directional_scores))
    raw_score = float(np.mean(directional_scores)) if observations > 0 else np.nan
    hit_rate = float(hits / observations) if observations > 0 else np.nan
    eligible = observations >= int(min_observations)
    effective_score = float(raw_score) if eligible and np.isfinite(raw_score) else 0.0

    return {
        "raw_score": raw_score,
        "effective_score": effective_score,
        "observations": observations,
        "hit_rate": hit_rate,
        "eligible": bool(eligible),
        "months_scored": int(len(rows)),
    }


def _build_consistency_features(
    history_by_ticker: dict[str, list[dict[str, object]]],
    universe: list[str],
    lookback_months: int,
    min_observations: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker in universe:
        stats = _consistency_from_history(
            history_rows=history_by_ticker.get(ticker, []),
            lookback_months=lookback_months,
            min_observations=min_observations,
        )
        rows.append(
            {
                "ticker": ticker,
                "consistency_score_raw": stats["raw_score"],
                "consistency_score": stats["effective_score"],
                "consistency_observations": stats["observations"],
                "consistency_hit_rate": stats["hit_rate"],
                "consistency_eligible": stats["eligible"],
            }
        )
    return pd.DataFrame(rows)


def _build_consistency_table(
    history_by_ticker: dict[str, list[dict[str, object]]],
    min_observations: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker, history_rows in history_by_ticker.items():
        stats = _consistency_from_history(
            history_rows=history_rows,
            lookback_months=0,
            min_observations=min_observations,
        )
        if stats["months_scored"] == 0:
            continue
        ticker_signals = [float(row.get("signal", 0.0)) for row in history_rows]
        ticker_returns = [float(row.get("next_month_ret", np.nan)) for row in history_rows]
        rows.append(
            {
                "ticker": ticker,
                "consistency_score": stats["raw_score"],
                "consistency_hit_rate": stats["hit_rate"],
                "consistency_observations": stats["observations"],
                "eligible": stats["eligible"],
                "months_scored": stats["months_scored"],
                "mean_signal": float(np.nanmean(ticker_signals)) if ticker_signals else np.nan,
                "mean_next_month_ret": float(np.nanmean(ticker_returns)) if ticker_returns else np.nan,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "ticker",
                "consistency_score",
                "consistency_hit_rate",
                "consistency_observations",
                "eligible",
                "months_scored",
                "mean_signal",
                "mean_next_month_ret",
            ]
        )

    output = pd.DataFrame(rows)
    output = output.sort_values(
        by=["eligible", "consistency_score", "consistency_observations", "ticker"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)
    return output


def _signals_from_ratings(
    ratings_by_ticker: dict[str, pd.DataFrame],
    universe: list[str],
    asof: pd.Timestamp,
    lookback_days: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    cutoff = asof - pd.Timedelta(days=lookback_days)
    for ticker in universe:
        ticker_ratings = ratings_by_ticker.get(ticker)
        if ticker_ratings is None or ticker_ratings.empty:
            rows.append({"ticker": ticker, "signal": 0.0, "events_in_window": 0})
            continue

        hist = ticker_ratings[ticker_ratings["period"] <= asof]
        if hist.empty:
            rows.append({"ticker": ticker, "signal": 0.0, "events_in_window": 0})
            continue

        recent = hist[hist["period"] > cutoff]
        if not recent.empty:
            signal = float(recent["net_score"].mean())
            count = int(len(recent))
        else:
            # Fall back to the latest rating <= asof when no recent rating exists.
            signal = float(hist["net_score"].iloc[-1])
            count = 1

        rows.append({"ticker": ticker, "signal": signal, "events_in_window": count})
    return pd.DataFrame(rows)


def run_backtest(
    prices: pd.DataFrame,
    universe: list[str],
    events: pd.DataFrame,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    top_n: int,
    bottom_n: int,
    lookback_days: int,
    signal_source: str = "yfinance_events",
    ranking_mode: str = "signal_only",
    consistency_weight: float = 0.35,
    consistency_lookback_months: int = 12,
    consistency_min_observations: int = 3,
    signal_lag_months: int = 0,
    randomize_signals: bool = False,
    random_seed: int = 42,
    transaction_cost_bps: float = 0.0,
    short_borrow_cost_bps_monthly: float = 0.0,
    finnhub_ratings: pd.DataFrame | None = None,
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
    if signal_source not in {"yfinance_events", "finnhub_ratings"}:
        raise ValueError("signal_source must be one of: yfinance_events, finnhub_ratings")
    if ranking_mode not in {"signal_only", "blend_with_consistency", "consistency_only"}:
        raise ValueError(
            "ranking_mode must be one of: signal_only, blend_with_consistency, consistency_only"
        )
    if consistency_lookback_months < 0:
        raise ValueError("consistency_lookback_months must be >= 0.")
    if consistency_min_observations <= 0:
        raise ValueError("consistency_min_observations must be > 0.")
    if signal_lag_months < 0:
        raise ValueError("signal_lag_months must be >= 0.")
    if transaction_cost_bps < 0:
        raise ValueError("transaction_cost_bps must be >= 0.")
    if short_borrow_cost_bps_monthly < 0:
        raise ValueError("short_borrow_cost_bps_monthly must be >= 0.")

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

    events_by_ticker = build_events_by_ticker(events) if signal_source == "yfinance_events" else {}
    ratings_by_ticker = (
        _build_ratings_by_ticker(finnhub_ratings if finnhub_ratings is not None else pd.DataFrame())
        if signal_source == "finnhub_ratings"
        else {}
    )
    tickers_without_signal_data = [
        ticker
        for ticker in universe_clean
        if (
            (signal_source == "yfinance_events" and (ticker not in events_by_ticker or events_by_ticker[ticker].empty))
            or (signal_source == "finnhub_ratings" and (ticker not in ratings_by_ticker or ratings_by_ticker[ticker].empty))
        )
    ]
    _log(logger, f"Tickers without {signal_source} data: {len(tickers_without_signal_data)}")

    monthly_rows: list[dict[str, object]] = []
    ic_rows: list[dict[str, object]] = []
    history_by_ticker: dict[str, list[dict[str, object]]] = {
        ticker: [] for ticker in universe_clean
    }
    consistency_weight = float(np.clip(consistency_weight, 0.0, 1.0))
    signal_lag_months = int(signal_lag_months)
    random_seed = int(random_seed)
    tc_rate = float(transaction_cost_bps) / 10000.0
    short_borrow_rate = float(short_borrow_cost_bps_monthly) / 10000.0
    prev_longs: list[str] = []
    prev_shorts: list[str] = []

    for month_idx, month in enumerate(boundaries[:-1]):
        signal_asof_idx = month_idx - signal_lag_months
        if signal_asof_idx < 0:
            signal_frame = pd.DataFrame(
                {
                    "ticker": universe_clean,
                    "signal": np.zeros(len(universe_clean), dtype=float),
                    "events_in_window": np.zeros(len(universe_clean), dtype=int),
                }
            )
        else:
            signal_asof = pd.Timestamp(boundaries[signal_asof_idx])
            if signal_source == "finnhub_ratings":
                signal_frame = _signals_from_ratings(
                    ratings_by_ticker=ratings_by_ticker,
                    universe=universe_clean,
                    asof=signal_asof,
                    lookback_days=lookback_days,
                )
            else:
                signal_frame = compute_signals_for_universe(
                    events_by_ticker=events_by_ticker,
                    universe=universe_clean,
                    asof=signal_asof,
                    lookback_days=lookback_days,
                    mapping_rules=grade_mapping_rules or DEFAULT_GRADE_MAPPING_RULES,
                    action_weights=action_weights or DEFAULT_ACTION_WEIGHTS,
                )
        if randomize_signals and not signal_frame.empty:
            rng = np.random.default_rng(random_seed + month_idx)
            shuffled = signal_frame["signal"].to_numpy(dtype=float, copy=True)
            rng.shuffle(shuffled)
            signal_frame["signal"] = shuffled
        consistency_features = _build_consistency_features(
            history_by_ticker=history_by_ticker,
            universe=universe_clean,
            lookback_months=consistency_lookback_months,
            min_observations=consistency_min_observations,
        )
        signal_frame = signal_frame.merge(
            consistency_features,
            how="left",
            on="ticker",
        )
        signal_frame["signal"] = pd.to_numeric(signal_frame["signal"], errors="coerce").fillna(0.0)
        signal_frame["signal_rank_score"] = _rank_to_unit_scale(signal_frame["signal"])
        signal_frame["consistency_score"] = (
            pd.to_numeric(signal_frame["consistency_score"], errors="coerce").fillna(0.0)
        )
        signal_frame["consistency_score_raw"] = pd.to_numeric(
            signal_frame["consistency_score_raw"], errors="coerce"
        )
        signal_frame["consistency_observations"] = (
            pd.to_numeric(signal_frame["consistency_observations"], errors="coerce")
            .fillna(0)
            .astype(int)
        )
        signal_frame["consistency_hit_rate"] = pd.to_numeric(
            signal_frame["consistency_hit_rate"], errors="coerce"
        )

        if ranking_mode == "signal_only":
            signal_frame["rank_score"] = signal_frame["signal_rank_score"]
        elif ranking_mode == "consistency_only":
            signal_frame["rank_score"] = signal_frame["consistency_score"]
        else:
            signal_frame["rank_score"] = (
                (1.0 - consistency_weight) * signal_frame["signal_rank_score"]
                + consistency_weight * signal_frame["consistency_score"]
            )
        # Dedicated short score:
        # 1) bearish analyst estimate (negative signal) is primary,
        # 2) consistency acts as a confidence adjustment, not a hard suppressor.
        signal_frame["bearish_signal_strength"] = (-signal_frame["signal_rank_score"]).clip(lower=0.0)
        signal_frame["consistency_confidence"] = (
            ((signal_frame["consistency_score"] + 1.0) / 2.0).clip(lower=0.0, upper=1.0)
        )
        consistency_multiplier = 0.75 + 0.5 * signal_frame["consistency_confidence"]
        signal_frame["bearish_rank_score"] = (
            signal_frame["bearish_signal_strength"] * consistency_multiplier
        )

        signal_frame = signal_frame.sort_values(
            by=["rank_score", "consistency_score", "signal", "ticker"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)

        longs = signal_frame.head(top_n)["ticker"].tolist() if top_n > 0 else []
        if bottom_n > 0:
            short_candidates = signal_frame[~signal_frame["ticker"].isin(longs)].copy()
            short_candidates = short_candidates.sort_values(
                by=[
                    "bearish_rank_score",
                    "bearish_signal_strength",
                    "signal_rank_score",
                    "consistency_score",
                    "ticker",
                ],
                ascending=[False, False, True, False, True],
            ).reset_index(drop=True)
            short_candidates_pos = short_candidates[short_candidates["bearish_rank_score"] > 0].copy()
            shorts_source = short_candidates_pos if not short_candidates_pos.empty else short_candidates
            shorts = shorts_source.head(bottom_n)["ticker"].tolist()
        else:
            shorts = []

        month_returns = returns_month_map.get(pd.Timestamp(month), pd.Series(dtype=float))
        long_rets = month_returns.reindex(longs).dropna().astype(float).tolist()
        short_rets = month_returns.reindex(shorts).dropna().astype(float).tolist()

        portfolio_ret = np.nan
        if longs and long_rets:
            portfolio_ret = float(np.mean(long_rets))
        if bottom_n > 0 and shorts and short_rets:
            base = 0.0 if np.isnan(portfolio_ret) else portfolio_ret
            portfolio_ret = float(base - np.mean(short_rets))

        long_overlap = len(set(prev_longs) & set(longs))
        short_overlap = len(set(prev_shorts) & set(shorts))
        long_turnover = (
            0.0
            if (len(prev_longs) == 0 and len(longs) == 0)
            else (1.0 - long_overlap / max(len(prev_longs), len(longs), 1))
        )
        short_turnover = (
            0.0
            if (len(prev_shorts) == 0 and len(shorts) == 0)
            else (1.0 - short_overlap / max(len(prev_shorts), len(shorts), 1))
        )
        tx_cost = tc_rate * (long_turnover + short_turnover)
        short_borrow_cost = short_borrow_rate if len(shorts) > 0 else 0.0
        total_cost = tx_cost + short_borrow_cost
        if np.isfinite(portfolio_ret):
            portfolio_ret = float(portfolio_ret - total_cost)

        benchmark_ret = benchmark_map.get(pd.Timestamp(month), np.nan)
        excess_ret = (
            float(portfolio_ret - benchmark_ret)
            if np.isfinite(portfolio_ret) and np.isfinite(benchmark_ret)
            else np.nan
        )

        ic_join = signal_frame[["ticker", "signal", "rank_score"]].merge(
            month_returns.rename("next_month_ret"),
            how="inner",
            left_on="ticker",
            right_index=True,
        )
        ic_join = ic_join.dropna(subset=["rank_score", "next_month_ret"]).copy()
        if (
            len(ic_join) >= 2
            and ic_join["rank_score"].nunique() > 1
            and ic_join["next_month_ret"].nunique() > 1
        ):
            ic_value = float(ic_join["rank_score"].corr(ic_join["next_month_ret"], method="spearman"))
        else:
            ic_value = np.nan

        if (
            len(ic_join) >= 2
            and ic_join["signal"].nunique() > 1
            and ic_join["next_month_ret"].nunique() > 1
        ):
            base_signal_ic = float(ic_join["signal"].corr(ic_join["next_month_ret"], method="spearman"))
        else:
            base_signal_ic = np.nan

        signal_lookup = signal_frame.set_index("ticker")["signal"]
        for ticker, next_ret in month_returns.items():
            signal_value = signal_lookup.get(ticker, np.nan)
            if not np.isfinite(signal_value) or not np.isfinite(next_ret):
                continue
            history_by_ticker.setdefault(ticker, []).append(
                {
                    "month": pd.Timestamp(month),
                    "signal": float(signal_value),
                    "next_month_ret": float(next_ret),
                }
            )

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
                "top_rank_score": float(signal_frame["rank_score"].iloc[0]) if not signal_frame.empty else np.nan,
                "top_consistency_score": (
                    float(signal_frame["consistency_score"].iloc[0]) if not signal_frame.empty else np.nan
                ),
                "top_bearish_rank_score": (
                    float(signal_frame["bearish_rank_score"].max()) if not signal_frame.empty else np.nan
                ),
                "signal_asof": (
                    pd.Timestamp(boundaries[signal_asof_idx]) if signal_asof_idx >= 0 else pd.NaT
                ),
                "signal_lag_months": signal_lag_months,
                "randomized_signals": bool(randomize_signals),
                "long_turnover": float(long_turnover),
                "short_turnover": float(short_turnover),
                "tx_cost": float(tx_cost),
                "short_borrow_cost": float(short_borrow_cost),
                "total_cost": float(total_cost),
                "ranking_mode": ranking_mode,
            }
        )
        ic_rows.append(
            {
                "month": pd.Timestamp(month),
                "ic": ic_value,
                "base_signal_ic": base_signal_ic,
                "n_pairs": int(len(ic_join)),
            }
        )

        _log(
            logger,
            (
                f"{pd.Timestamp(month).date()} | long/short counts {len(longs)}/{len(shorts)} | "
                f"missing long returns {len(longs) - len(long_rets)} | "
                f"missing short returns {len(shorts) - len(short_rets)} | "
                f"cost={100.0 * total_cost:.3f}%"
            ),
        )
        prev_longs = list(longs)
        prev_shorts = list(shorts)

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
    base_signal_ic_non_null = (
        ic_series["base_signal_ic"].dropna().astype(float)
        if ("base_signal_ic" in ic_series.columns and not ic_series.empty)
        else pd.Series(dtype=float)
    )
    ic_summary["mean_base_signal_ic"] = (
        float(base_signal_ic_non_null.mean()) if not base_signal_ic_non_null.empty else np.nan
    )
    ic_summary["median_base_signal_ic"] = (
        float(base_signal_ic_non_null.median()) if not base_signal_ic_non_null.empty else np.nan
    )

    consistency_table = _build_consistency_table(
        history_by_ticker=history_by_ticker,
        min_observations=consistency_min_observations,
    )
    eligible_consistency = consistency_table[consistency_table["eligible"]].copy()
    consistency_summary = {
        "eligible_tickers": int(len(eligible_consistency)),
        "tickers_scored": int(len(consistency_table)),
        "mean_consistency": (
            float(eligible_consistency["consistency_score"].mean())
            if not eligible_consistency.empty
            else np.nan
        ),
        "median_consistency": (
            float(eligible_consistency["consistency_score"].median())
            if not eligible_consistency.empty
            else np.nan
        ),
    }

    diagnostics = {
        "signal_source": signal_source,
        "ranking_mode": ranking_mode,
        "consistency_weight": consistency_weight,
        "consistency_lookback_months": int(consistency_lookback_months),
        "consistency_min_observations": int(consistency_min_observations),
        "signal_lag_months": int(signal_lag_months),
        "randomize_signals": bool(randomize_signals),
        "random_seed": int(random_seed),
        "transaction_cost_bps": float(transaction_cost_bps),
        "short_borrow_cost_bps_monthly": float(short_borrow_cost_bps_monthly),
        "benchmark_ticker": benchmark_ticker,
        "missing_price_tickers_total": len(missing_price_tickers),
        "missing_price_tickers": missing_price_tickers,
        "missing_signal_tickers_total": len(tickers_without_signal_data),
        "missing_signal_tickers": tickers_without_signal_data,
        "months_total": int(len(monthly_results)),
        "months_with_portfolio_return": int(monthly_results["portfolio_ret"].notna().sum()),
        "avg_tx_cost": float(monthly_results["tx_cost"].mean()) if "tx_cost" in monthly_results.columns else np.nan,
        "avg_short_borrow_cost": (
            float(monthly_results["short_borrow_cost"].mean())
            if "short_borrow_cost" in monthly_results.columns
            else np.nan
        ),
        "avg_total_cost": (
            float(monthly_results["total_cost"].mean()) if "total_cost" in monthly_results.columns else np.nan
        ),
        "consistency_tickers_scored": int(consistency_summary["tickers_scored"]),
        "consistency_eligible_tickers": int(consistency_summary["eligible_tickers"]),
    }

    return {
        "monthly_results": monthly_results,
        "equity_curve": equity_curve,
        "drawdown_curve": drawdown_curve,
        "ic_series": ic_series,
        "ic_summary": ic_summary,
        "consistency_table": consistency_table,
        "consistency_summary": consistency_summary,
        "portfolio_stats": portfolio_stats,
        "benchmark_stats": benchmark_stats,
        "diagnostics": diagnostics,
    }
