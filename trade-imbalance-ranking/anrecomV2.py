"""
True historical backtest (FREE) using analyst UPGRADES/DOWNGRADES events from yfinance.

Idea:
- For each month:
  - Build a signal per ticker using only events that happened BEFORE the rebalance date
  - Rank tickers by signal
  - Buy top N (equal weight)
  - Optionally short bottom N
  - Hold until next month
- Compute monthly portfolio returns + summary stats.

Why this is "true historical":
- Upgrades/downgrades are timestamped events, so we don't accidentally use future info.

Requirements:
  pip install yfinance pandas numpy

Notes:
- "Consensus counts" (Strong Buy/Buy/Hold...) are hard to get historically for free at scale.
  This approach uses historical rating-change events instead.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf


# ----------------------------
# CONFIG
# ----------------------------
UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"
    # replace with your universe (can be 100s; be mindful of rate limits)
]

START_MONTH = "2024-01-01"   # inclusive month start
END_MONTH   = "2025-01-01"   # exclusive month start
TOP_N = 5
BOTTOM_N = 0                 # set >0 for long/short

LOOKBACK_DAYS = 30           # event lookback window ending at rebalance date
TRADE_NEXT_TRADING_DAY = True

SLEEP_BETWEEN_TICKERS_SEC = 0.08  # throttle requests
CACHE_CSV = "ud_events_cache.csv"  # persistent cache of events to avoid re-downloading


# ----------------------------
# DATE HELPERS
# ----------------------------
def month_starts(start: str, end: str) -> list[pd.Timestamp]:
    s = pd.Timestamp(start).normalize().replace(day=1)
    e = pd.Timestamp(end).normalize().replace(day=1)
    return list(pd.date_range(s, e, freq="MS", inclusive="left"))


def get_next_trading_close(ticker: str, date: pd.Timestamp) -> Optional[tuple[pd.Timestamp, float]]:
    """
    Find first trading day on/after date and return (timestamp, adjusted close).
    """
    px = yf.download(
        ticker,
        start=(date - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
        end=(date + pd.Timedelta(days=10)).strftime("%Y-%m-%d"),
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

    idx = close.index[close.index >= date]
    if len(idx) == 0:
        return None

    t0 = pd.Timestamp(idx[0]).normalize()
    p0 = float(close.loc[idx[0]])
    if not np.isfinite(p0) or p0 <= 0:
        return None
    return t0, p0


def forward_return(ticker: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> Optional[float]:
    """
    Return from first trading close on/after start_date to first trading close on/after end_date.
    Uses auto_adjust=True.
    """
    a = get_next_trading_close(ticker, start_date)
    b = get_next_trading_close(ticker, end_date)
    if a is None or b is None:
        return None
    _, p0 = a
    _, p1 = b
    r = float(p1 / p0 - 1.0)
    return r if np.isfinite(r) else None


# ----------------------------
# EVENTS CACHE
# ----------------------------
def load_cached_events(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
        return df
    except FileNotFoundError:
        return pd.DataFrame(columns=["ticker", "date", "action", "fromGrade", "toGrade", "firm"])


def save_cached_events(df: pd.DataFrame, path: str) -> None:
    out = df.copy()
    # store naive ISO date
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)


def fetch_ud_events_for_ticker(ticker: str) -> pd.DataFrame:
    """
    Fetch upgrades/downgrades for a ticker from yfinance.
    """
    t = yf.Ticker(ticker)
    df = t.get_upgrades_downgrades()
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=["ticker", "date", "action", "fromGrade", "toGrade", "firm"])

    df = df.copy()

    # yfinance's upgrades/downgrades index is typically datetime
    if not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame(columns=["ticker", "date", "action", "fromGrade", "toGrade", "firm"])

    df = df.reset_index().rename(columns={"index": "date"})
    if "date" not in df.columns:
        return pd.DataFrame(columns=["ticker", "date", "action", "fromGrade", "toGrade", "firm"])

    # normalize columns across versions
    for col in ["action", "fromGrade", "toGrade", "firm"]:
        if col not in df.columns:
            df[col] = None

    df["ticker"] = ticker
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)

    return df[["ticker", "date", "action", "fromGrade", "toGrade", "firm"]]


def ensure_events_cached(universe: list[str], cache_path: str) -> pd.DataFrame:
    """
    Load cache and fetch missing tickers (or update all, your choice).
    For simplicity, this fetches for tickers not yet present in cache.
    """
    cached = load_cached_events(cache_path)
    have = set(cached["ticker"].unique()) if not cached.empty else set()
    missing = [t for t in universe if t not in have]

    if missing:
        new_parts = []
        for tk in missing:
            print(f"Fetching upgrades/downgrades for {tk} ...")
            part = fetch_ud_events_for_ticker(tk)
            if part is not None and not part.empty:
                new_parts.append(part)
            time.sleep(SLEEP_BETWEEN_TICKERS_SEC)

        if new_parts:
            cached = pd.concat([cached, *new_parts], ignore_index=True)

        # de-dup
        if not cached.empty:
            cached = cached.drop_duplicates(subset=["ticker", "date", "action", "fromGrade", "toGrade", "firm"])

        save_cached_events(cached, cache_path)

    return cached


# ----------------------------
# SIGNAL
# ----------------------------
def ud_signal(events: pd.DataFrame, asof: pd.Timestamp, lookback_days: int) -> float:
    """
    Compute signal from events in (asof - lookback_days, asof], higher is more bullish.

    Simple weights:
      upgrade   +1
      downgrade -1
      initiate  +0.25
      reiterate  0
      maintain   0
      resume     0
      (unknown)  0
    """
    if events is None or events.empty:
        return 0.0

    start = asof - pd.Timedelta(days=lookback_days)
    w = events[(events["date"] > start) & (events["date"] <= asof)].copy()
    if w.empty:
        return 0.0

    def weight(action: str) -> float:
        a = (action or "").strip().lower()
        if "upgrade" in a:
            return 1.0
        if "downgrade" in a:
            return -1.0
        if "initiat" in a:  # initiation / initiated
            return 0.25
        if "reiterat" in a:
            return 0.0
        if "maintain" in a:
            return 0.0
        if "resume" in a:
            return 0.0
        return 0.0

    return float(w["action"].map(weight).sum())


# ----------------------------
# PERFORMANCE STATS
# ----------------------------
def performance_stats(r: pd.Series) -> dict:
    r = r.dropna().astype(float)
    if r.empty:
        return {}

    equity = (1.0 + r).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)

    n = len(r)
    cagr = float((equity.iloc[-1]) ** (12.0 / n) - 1.0) if n > 0 else np.nan
    vol = float(r.std(ddof=1) * math.sqrt(12.0)) if n > 1 else np.nan
    sharpe = float((r.mean() * 12.0) / vol) if (np.isfinite(vol) and vol != 0) else np.nan

    peak = equity.cummax()
    dd = equity / peak - 1.0
    max_dd = float(dd.min())

    hit = float((r > 0).mean())

    return {
        "months": n,
        "total_return": total_return,
        "CAGR": cagr,
        "ann_vol": vol,
        "sharpe_approx": sharpe,
        "max_drawdown": max_dd,
        "hit_rate": hit,
    }


# ----------------------------
# BACKTEST
# ----------------------------
def run_backtest() -> pd.DataFrame:
    months = month_starts(START_MONTH, END_MONTH)
    if len(months) < 2:
        raise ValueError("Need at least 2 month starts in range.")

    # Load/fetch events once (cached)
    all_events = ensure_events_cached(UNIVERSE, CACHE_CSV)
    if not all_events.empty:
        all_events["date"] = pd.to_datetime(all_events["date"])

    rows = []

    for i in range(len(months) - 1):
        rebalance = months[i]
        next_month = months[i + 1]

        # Use info available as-of rebalance date (or shift by 1 day to be extra safe)
        asof = rebalance
        if TRADE_NEXT_TRADING_DAY:
            # signal cutoff remains at rebalance (asof), trade happens next trading day
            trade_start = rebalance + pd.Timedelta(days=1)
        else:
            trade_start = rebalance

        # Build signals
        sigs = []
        for tk in UNIVERSE:
            ev = all_events[all_events["ticker"] == tk] if not all_events.empty else pd.DataFrame()
            s = ud_signal(ev, asof=asof, lookback_days=LOOKBACK_DAYS)
            sigs.append((tk, s))

        sig_df = pd.DataFrame(sigs, columns=["ticker", "signal"]).sort_values("signal", ascending=False)
        longs = sig_df.head(TOP_N)["ticker"].tolist() if TOP_N > 0 else []
        shorts = sig_df.tail(BOTTOM_N)["ticker"].tolist() if BOTTOM_N > 0 else []

        # Compute forward returns
        long_rets = []
        for tk in longs:
            r = forward_return(tk, trade_start, next_month)
            if r is not None and np.isfinite(r):
                long_rets.append(float(r))
            time.sleep(SLEEP_BETWEEN_TICKERS_SEC)

        short_rets = []
        for tk in shorts:
            r = forward_return(tk, trade_start, next_month)
            if r is not None and np.isfinite(r):
                short_rets.append(float(r))
            time.sleep(SLEEP_BETWEEN_TICKERS_SEC)

        port = np.nan
        if long_rets:
            port = float(np.mean(long_rets))
        if BOTTOM_N > 0 and short_rets:
            port = (0.0 if np.isnan(port) else port) - float(np.mean(short_rets))

        rows.append({
            "month": rebalance.strftime("%Y-%m-%d"),
            "asof": asof.strftime("%Y-%m-%d"),
            "lookback_days": LOOKBACK_DAYS,
            "longs": ",".join(longs),
            "shorts": ",".join(shorts),
            "portfolio_ret": port,
            "long_ret_mean": float(np.mean(long_rets)) if long_rets else np.nan,
            "short_ret_mean": float(np.mean(short_rets)) if short_rets else np.nan,
            "top_signal": float(sig_df["signal"].iloc[0]) if not sig_df.empty else np.nan,
        })

        print(f"[{rebalance.date()}] top={longs} port_ret={port}")

    out = pd.DataFrame(rows)
    return out


if __name__ == "__main__":
    df = run_backtest()

    print("\nMonthly results:")
    print(df[["month", "portfolio_ret", "longs", "shorts"]].to_string(index=False))

    stats = performance_stats(df["portfolio_ret"])
    print("\nPerformance stats:")
    for k, v in stats.items():
        print(f"{k}: {v}")

    df.to_csv("ud_backtest_results.csv", index=False)
    print("\nSaved: ud_backtest_results.csv")