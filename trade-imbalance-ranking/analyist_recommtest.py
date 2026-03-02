"""
Analyst Recommendation Backtest (Monthly)

- Pulls analyst recommendation summary (StrongBuy/Buy/Hold/Sell/StrongSell) via yfinance
- Builds a numeric score per ticker
- Each month:
    - ranks universe by score (using latest available recommendation snapshot)
    - buys top N (equal weight)
    - optionally shorts bottom N
    - holds for ~1 month, measures forward return using adjusted prices
- Outputs:
    - monthly portfolio returns
    - simple performance stats
    - optional CSV export

Notes / limitations:
- yfinance recommendation history is not guaranteed deep/complete for all tickers.
- This is a *prototype*; treat results carefully (look-ahead/survivorship bias, etc.).
"""

from __future__ import annotations

import time
import math
import numpy as np
import pandas as pd
import yfinance as yf


# ----------------------------
# Config
# ----------------------------
UNIVERSE = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]  # replace with your list
TOP_N = 3
BOTTOM_N = 0                 # set >0 to do long/short (bottom N short)
START_MONTH = "2024-01-01"   # inclusive
END_MONTH = "2025-01-01"     # exclusive-ish (we generate month starts up to this)
TRADE_AT_OPEN_NEXT_DAY = True
SLEEP_BETWEEN_TICKERS_SEC = 0.1  # be nice to Yahoo


# ----------------------------
# Helpers: dates
# ----------------------------
def month_starts(start: str, end: str) -> list[pd.Timestamp]:
    """Generate month start timestamps from start to end (end not included)."""
    s = pd.Timestamp(start).normalize().replace(day=1)
    e = pd.Timestamp(end).normalize().replace(day=1)
    return list(pd.date_range(s, e, freq="MS", inclusive="left"))


def next_trading_day(date: pd.Timestamp, ticker: str) -> pd.Timestamp | None:
    """
    Find the next trading day for 'ticker' on or after 'date' using downloaded prices.
    This avoids assuming calendars.
    """
    # Look ahead a bit to ensure we hit a trading day
    px = yf.download(
        ticker,
        start=(date - pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
        end=(date + pd.Timedelta(days=10)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=False,
    )
    if px is None or px.empty or "Close" not in px.columns:
        return None

    idx = px.index
    # find first trading day >= date
    candidates = idx[idx >= date]
    if len(candidates) == 0:
        return None
    return pd.Timestamp(candidates[0]).normalize()


# ----------------------------
# Helpers: recommendation score
# ----------------------------
def rec_score_from_counts(sb: float, b: float, h: float, s: float, ss: float) -> float | None:
    """
    Convert recommendation counts into a normalized score in [-2, +2] range-ish.

    You can change weights here.
    """
    total = sb + b + h + s + ss
    if total <= 0:
        return None
    score = (2 * sb + 1 * b - 1 * h - 1 * s - 2 * ss) / total
    # score roughly between -2 and +2 but normalized by total -> in [-2,2]
    return float(score)


def latest_rec_snapshot(ticker: str) -> dict | None:
    """
    Get the latest recommendation summary row for a ticker.
    Returns dict with: period, strongBuy, buy, hold, sell, strongSell, score
    """
    t = yf.Ticker(ticker)

    # yfinance offers get_recommendations() returning a DataFrame with:
    # period, strongBuy, buy, hold, sell, strongSell
    df = t.get_recommendations()
    if df is None or len(df) == 0:
        return None

    # Ensure expected columns exist
    needed = ["period", "strongBuy", "buy", "hold", "sell", "strongSell"]
    for c in needed:
        if c not in df.columns:
            return None

    row = df.iloc[0].to_dict()  # usually most recent
    score = rec_score_from_counts(
        sb=float(row.get("strongBuy", 0) or 0),
        b=float(row.get("buy", 0) or 0),
        h=float(row.get("hold", 0) or 0),
        s=float(row.get("sell", 0) or 0),
        ss=float(row.get("strongSell", 0) or 0),
    )
    if score is None:
        return None

    row_out = {
        "ticker": ticker,
        "period": row.get("period"),
        "strongBuy": float(row.get("strongBuy", 0) or 0),
        "buy": float(row.get("buy", 0) or 0),
        "hold": float(row.get("hold", 0) or 0),
        "sell": float(row.get("sell", 0) or 0),
        "strongSell": float(row.get("strongSell", 0) or 0),
        "score": score,
    }
    return row_out


# ----------------------------
# Helpers: returns
# ----------------------------
def forward_return(ticker: str, entry_date: pd.Timestamp, exit_date: pd.Timestamp) -> float | None:
    """
    Compute total return from entry_date to exit_date using auto-adjusted close.
    Returns a float (not a Series).
    """
    px = yf.download(
        ticker,
        start=(entry_date - pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
        end=(exit_date + pd.Timedelta(days=3)).strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=False,
    )
    if px is None or px.empty or "Close" not in px.columns:
        return None

    close = px["Close"].squeeze()
    if not isinstance(close, pd.Series) or close.empty:
        return None

    # Find first trading close on/after entry_date, and first trading close on/after exit_date
    entry_idx = close.index[close.index >= entry_date]
    exit_idx = close.index[close.index >= exit_date]
    if len(entry_idx) == 0 or len(exit_idx) == 0:
        return None

    p0 = float(close.loc[entry_idx[0]])
    p1 = float(close.loc[exit_idx[0]])
    if not (np.isfinite(p0) and np.isfinite(p1)) or p0 <= 0:
        return None

    return float(p1 / p0 - 1.0)


# ----------------------------
# Backtest
# ----------------------------
def run_backtest() -> pd.DataFrame:
    months = month_starts(START_MONTH, END_MONTH)
    if len(months) < 2:
        raise ValueError("Need at least 2 months between START_MONTH and END_MONTH.")

    results = []

    for i in range(len(months) - 1):
        rebalance_month = months[i]
        next_month = months[i + 1]

        # Determine trade dates (avoid look-ahead a bit)
        # Use next trading day after month start (or month start itself if already trading day).
        # Optionally trade at next-day open proxy by shifting one day.
        trade_base = rebalance_month + (pd.Timedelta(days=1) if TRADE_AT_OPEN_NEXT_DAY else pd.Timedelta(days=0))

        # We'll find a valid trading day for each ticker when computing returns,
        # but to keep it simple, use trade_base and next_month as anchors.
        # Build recommendation snapshot (latest available)
        snaps = []
        for tk in UNIVERSE:
            s = latest_rec_snapshot(tk)
            if s is not None and np.isfinite(s["score"]):
                snaps.append(s)
            time.sleep(SLEEP_BETWEEN_TICKERS_SEC)

        if len(snaps) == 0:
            print(f"[{rebalance_month.date()}] No recommendation data. Skipping.")
            continue

        snap_df = pd.DataFrame(snaps).sort_values("score", ascending=False).reset_index(drop=True)

        longs = snap_df.head(TOP_N)["ticker"].tolist() if TOP_N > 0 else []
        shorts = snap_df.tail(BOTTOM_N)["ticker"].tolist() if BOTTOM_N > 0 else []

        # Compute forward returns for each leg
        long_rets = []
        for tk in longs:
            r = forward_return(tk, trade_base, next_month)
            if isinstance(r, (int, float)) and np.isfinite(r):
                long_rets.append(float(r))
            else:
                print(f"[{rebalance_month.date()}] Missing long return for {tk}")
            time.sleep(SLEEP_BETWEEN_TICKERS_SEC)

        short_rets = []
        for tk in shorts:
            r = forward_return(tk, trade_base, next_month)
            if isinstance(r, (int, float)) and np.isfinite(r):
                short_rets.append(float(r))
            else:
                print(f"[{rebalance_month.date()}] Missing short return for {tk}")
            time.sleep(SLEEP_BETWEEN_TICKERS_SEC)

        # Equal weight portfolio:
        # Long-only: mean(long_rets)
        # Long/short: mean(long_rets) - mean(short_rets)
        port_ret = None
        if TOP_N > 0 and len(long_rets) > 0:
            port_ret = float(np.mean(long_rets))
        if BOTTOM_N > 0 and len(short_rets) > 0:
            # subtract short leg returns (short profit when stock drops => -return)
            short_leg = float(np.mean(short_rets))
            port_ret = (port_ret if port_ret is not None else 0.0) - short_leg

        results.append(
            {
                "month": rebalance_month.strftime("%Y-%m-%d"),
                "n_snaps": len(snap_df),
                "longs": ",".join(longs),
                "shorts": ",".join(shorts),
                "long_ret_mean": float(np.mean(long_rets)) if long_rets else np.nan,
                "short_ret_mean": float(np.mean(short_rets)) if short_rets else np.nan,
                "portfolio_ret": port_ret if port_ret is not None else np.nan,
            }
        )

        print(
            f"[{rebalance_month.date()}] longs={longs} "
            f"shorts={shorts} port_ret={port_ret}"
        )

    out = pd.DataFrame(results)
    return out


# ----------------------------
# Stats
# ----------------------------
def performance_stats(monthly_returns: pd.Series) -> dict:
    r = monthly_returns.dropna().astype(float)
    if r.empty:
        return {}

    equity = (1.0 + r).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)

    # Annualization assumes monthly frequency
    n_months = len(r)
    cagr = float((equity.iloc[-1]) ** (12.0 / n_months) - 1.0) if n_months > 0 else np.nan

    vol = float(r.std(ddof=1) * math.sqrt(12.0)) if len(r) > 1 else np.nan
    sharpe = float((r.mean() * 12.0) / vol) if (vol is not None and np.isfinite(vol) and vol != 0) else np.nan

    # Max drawdown
    peak = equity.cummax()
    dd = equity / peak - 1.0
    max_dd = float(dd.min())

    hit_rate = float((r > 0).mean())

    return {
        "months": n_months,
        "total_return": total_return,
        "CAGR": cagr,
        "ann_vol": vol,
        "sharpe_approx": sharpe,
        "max_drawdown": max_dd,
        "hit_rate": hit_rate,
    }


# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
    df = run_backtest()
    print("\nMonthly results:")
    print(df[["month", "portfolio_ret", "longs", "shorts"]].to_string(index=False))

    stats = performance_stats(df["portfolio_ret"])
    print("\nPerformance stats:")
    for k, v in stats.items():
        print(f"{k}: {v}")

    # Optional: save results
    df.to_csv("analyst_rec_backtest_results.csv", index=False)
    print("\nSaved: analyst_rec_backtest_results.csv")