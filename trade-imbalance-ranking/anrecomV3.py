"""
True Historical Analyst Backtest (FREE) — Upgrades/Downgrades + Grade-Delta Signal

Implements all improvements:
1) Universe >= 200 tickers (auto-fetch S&P 500 from Wikipedia OR load your own ticker file)
2) LOOKBACK default 90 days
3) Signal uses "grade delta" (toGrade - fromGrade) when available, with robust text parsing
4) You can input how many stocks you want to trade: --top-n (and optionally --bottom-n for shorting)
5) Caching:
   - saves U/D events to CSV so you don't re-download every run
6) Optional benchmark (SPY) + Information Coefficient (IC)

Install:
  pip install yfinance pandas numpy requests lxml

Run examples:
  # Long-only, top 50 each month, S&P 500 universe
  python analyst_backtest_ud.py --top-n 50 --start 2018-01-01 --end 2025-01-01

  # Long/short, top 50 long and bottom 50 short
  python analyst_backtest_ud.py --top-n 50 --bottom-n 50 --start 2018-01-01 --end 2025-01-01

  # Use your own universe file (one ticker per line or CSV with 'ticker' column)
  python analyst_backtest_ud.py --universe-file tickers.csv --top-n 100 --start 2020-01-01 --end 2025-01-01

Notes:
- This is a "true" historical backtest because it only uses events dated before each rebalance.
- Yahoo/yfinance U/D coverage varies by ticker; a larger universe improves signal dispersion.
- This is still a prototype: no borrow fees, no slippage, simple monthly rebalance.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
import requests
import yfinance as yf


# -----------------------------
# Utilities
# -----------------------------
def month_starts(start: str, end: str) -> list[pd.Timestamp]:
    s = pd.Timestamp(start).normalize().replace(day=1)
    e = pd.Timestamp(end).normalize().replace(day=1)
    return list(pd.date_range(s, e, freq="MS", inclusive="left"))


def safe_mean(xs: list[float]) -> float:
    xs = [float(x) for x in xs if isinstance(x, (int, float)) and np.isfinite(x)]
    return float(np.mean(xs)) if xs else float("nan")


def normalize_ticker(t: str) -> str:
    return t.strip().upper().replace("\ufeff", "")


# -----------------------------
# Universe loading (FREE)
# -----------------------------
def fetch_sp500_tickers() -> list[str]:
    """
    Free source: Wikipedia S&P 500 constituents table.
    Requires: requests + pandas read_html (needs lxml installed).
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    html = requests.get(url, timeout=30).text
    tables = pd.read_html(html)
    # First table usually contains constituents with 'Symbol' column
    df = tables[0]
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    tickers = [normalize_ticker(x) for x in df[col].astype(str).tolist()]
    # Yahoo uses BRK-B instead of BRK.B; BF-B instead of BF.B
    tickers = [t.replace(".", "-") for t in tickers]
    return sorted(list(dict.fromkeys(tickers)))  # unique preserve order


def load_universe_from_file(path: str) -> list[str]:
    """
    Supports:
    - CSV with a 'ticker' column OR first column as tickers
    - TXT with one ticker per line
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    if path.lower().endswith((".csv", ".tsv")):
        sep = "," if path.lower().endswith(".csv") else "\t"
        df = pd.read_csv(path, sep=sep)
        if "ticker" in df.columns:
            tickers = df["ticker"].astype(str).tolist()
        else:
            tickers = df.iloc[:, 0].astype(str).tolist()
    else:
        with open(path, "r", encoding="utf-8") as f:
            tickers = [line.strip() for line in f if line.strip()]

    tickers = [normalize_ticker(t).replace(".", "-") for t in tickers]
    tickers = [t for t in tickers if t and t != "NAN"]
    return sorted(list(dict.fromkeys(tickers)))


# -----------------------------
# Price helpers (monthly forward returns)
# -----------------------------
def get_next_trading_close(ticker: str, date: pd.Timestamp) -> Optional[tuple[pd.Timestamp, float]]:
    """
    First trading close on/after date. Uses adjusted close (auto_adjust=True).
    """
    px = yf.download(
        ticker,
        start=(date - pd.Timedelta(days=7)).strftime("%Y-%m-%d"),
        end=(date + pd.Timedelta(days=14)).strftime("%Y-%m-%d"),
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
    a = get_next_trading_close(ticker, start_date)
    b = get_next_trading_close(ticker, end_date)
    if a is None or b is None:
        return None
    _, p0 = a
    _, p1 = b
    r = float(p1 / p0 - 1.0)
    return r if np.isfinite(r) else None


# -----------------------------
# U/D events cache
# -----------------------------
EVENT_COLS = ["ticker", "date", "action", "fromGrade", "toGrade", "firm"]


def load_cached_events(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=EVENT_COLS)
    df = pd.read_csv(path)
    if df.empty:
        return pd.DataFrame(columns=EVENT_COLS)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    return df[EVENT_COLS]


def save_cached_events(df: pd.DataFrame, path: str) -> None:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)


def fetch_ud_events_for_ticker(ticker: str) -> pd.DataFrame:
    t = yf.Ticker(ticker)
    df = t.get_upgrades_downgrades()
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=EVENT_COLS)

    df = df.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame(columns=EVENT_COLS)

    df = df.reset_index().rename(columns={"index": "date"})
    if "date" not in df.columns:
        return pd.DataFrame(columns=EVENT_COLS)

    for c in ["action", "fromGrade", "toGrade", "firm"]:
        if c not in df.columns:
            df[c] = None

    df["ticker"] = ticker
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)

    return df[EVENT_COLS]


def ensure_events_cached(universe: list[str], cache_path: str, sleep_sec: float, refresh: bool) -> pd.DataFrame:
    """
    If refresh=True, refetch everything (slow).
    Otherwise fetch only missing tickers.
    """
    cached = load_cached_events(cache_path)
    have = set(cached["ticker"].unique()) if not cached.empty else set()

    to_fetch = universe if refresh else [t for t in universe if t not in have]
    if not to_fetch:
        return cached

    new_parts = []
    for i, tk in enumerate(to_fetch, 1):
        print(f"Fetching U/D events [{i}/{len(to_fetch)}]: {tk}")
        part = fetch_ud_events_for_ticker(tk)
        if part is not None and not part.empty:
            new_parts.append(part)
        time.sleep(sleep_sec)

    if new_parts:
        cached = pd.concat([cached, *new_parts], ignore_index=True)

    if not cached.empty:
        cached = cached.drop_duplicates(subset=EVENT_COLS)

    save_cached_events(cached, cache_path)
    return cached


# -----------------------------
# Grade parsing & signal (grade-delta + fallback)
# -----------------------------
def _clean_grade(s: Optional[str]) -> str:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def grade_to_score(grade_text: Optional[str]) -> Optional[int]:
    """
    Map messy analyst grades into a simple ordinal score:
      +2 Strong Buy
      +1 Buy
       0 Hold/Neutral
      -1 Sell/Underperform
      -2 Strong Sell

    This is heuristic (because firms use many labels).
    """
    g = _clean_grade(grade_text)
    if not g:
        return None

    # Strong buy / top tier
    if any(k in g for k in ["strong buy", "conviction buy", "top pick", "overweight", "outperform", "market outperform", "add"]):
        # 'overweight'/'outperform' isn't always "strong buy" but is bullish; we treat as strong-ish
        return 2

    # Buy-ish
    if any(k in g for k in ["buy", "accumulate", "positive", "sector outperform", "peer outperform"]):
        return 1

    # Hold / neutral-ish
    if any(k in g for k in ["hold", "neutral", "market perform", "equal weight", "in-line", "inline", "perform", "sector perform"]):
        return 0

    # Sell-ish / bearish
    if any(k in g for k in ["sell", "underperform", "reduce", "negative", "underweight"]):
        return -1

    # Strong sell-ish
    if any(k in g for k in ["strong sell"]):
        return -2

    return None


def action_fallback_weight(action: Optional[str]) -> float:
    a = _clean_grade(action)
    if "upgrade" in a:
        return 1.0
    if "downgrade" in a:
        return -1.0
    if "initiat" in a:
        return 0.25
    return 0.0


def grade_delta_signal(events: pd.DataFrame, asof: pd.Timestamp, lookback_days: int) -> float:
    """
    Sum of (score(toGrade) - score(fromGrade)) for events in (asof-lookback, asof].
    If from/to parsing fails, fallback to action-based weight.
    """
    if events is None or events.empty:
        return 0.0

    start = asof - pd.Timedelta(days=lookback_days)
    w = events[(events["date"] > start) & (events["date"] <= asof)].copy()
    if w.empty:
        return 0.0

    total = 0.0
    for _, row in w.iterrows():
        fg = grade_to_score(row.get("fromGrade"))
        tg = grade_to_score(row.get("toGrade"))
        if fg is not None and tg is not None:
            total += float(tg - fg)
        else:
            total += float(action_fallback_weight(row.get("action")))
    return float(total)


# -----------------------------
# Metrics: stats + Information Coefficient (IC)
# -----------------------------
def performance_stats(r: pd.Series) -> dict:
    r = r.dropna().astype(float)
    if r.empty:
        return {}

    equity = (1.0 + r).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)

    n = len(r)
    cagr = float((equity.iloc[-1]) ** (12.0 / n) - 1.0) if n > 0 else float("nan")
    vol = float(r.std(ddof=1) * math.sqrt(12.0)) if n > 1 else float("nan")
    sharpe = float((r.mean() * 12.0) / vol) if (np.isfinite(vol) and vol != 0) else float("nan")

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


def spearman_ic(signals: pd.Series, fwd_returns: pd.Series) -> float:
    """
    Cross-sectional Spearman rank correlation between signals and next-month returns.
    """
    df = pd.DataFrame({"s": signals, "r": fwd_returns}).dropna()
    if len(df) < 10:
        return float("nan")
    return float(df["s"].rank().corr(df["r"].rank()))


# -----------------------------
# Backtest
# -----------------------------
def run_backtest(
    universe: list[str],
    start: str,
    end: str,
    top_n: int,
    bottom_n: int,
    lookback_days: int,
    trade_next_day: bool,
    sleep_sec: float,
    cache_path: str,
    refresh_cache: bool,
    benchmark: Optional[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    months = month_starts(start, end)
    if len(months) < 2:
        raise ValueError("Need at least 2 month starts between start/end.")

    events = ensure_events_cached(universe, cache_path, sleep_sec=sleep_sec, refresh=refresh_cache)
    if not events.empty:
        events["date"] = pd.to_datetime(events["date"], errors="coerce")
        events = events.dropna(subset=["date"])

    results = []
    ic_rows = []

    for i in range(len(months) - 1):
        rebalance = months[i]
        next_month = months[i + 1]
        asof = rebalance
        trade_start = rebalance + pd.Timedelta(days=1) if trade_next_day else rebalance

        # Build signals (only using events dated <= asof)
        sigs = []
        for tk in universe:
            ev = events[events["ticker"] == tk] if not events.empty else pd.DataFrame(columns=EVENT_COLS)
            s = grade_delta_signal(ev, asof=asof, lookback_days=lookback_days)
            sigs.append((tk, s))

        sig_df = pd.DataFrame(sigs, columns=["ticker", "signal"]).sort_values("signal", ascending=False)
        longs = sig_df.head(top_n)["ticker"].tolist() if top_n > 0 else []
        shorts = sig_df.tail(bottom_n)["ticker"].tolist() if bottom_n > 0 else []

        # Forward returns for IC (cross-sectional): compute for all tickers (can be slow)
        # To keep it usable, we compute IC on a capped subset if universe is huge:
        #   - if universe <= 300: compute all
        #   - else: compute on top/bottom + a random sample
        fwd = {}
        ic_universe = universe
        if len(universe) > 300:
            rng = np.random.default_rng(42 + i)
            remaining = list(set(universe) - set(longs) - set(shorts))
            sample = rng.choice(remaining, size=min(200, len(remaining)), replace=False).tolist()
            ic_universe = list(dict.fromkeys(longs + shorts + sample))

        for tk in ic_universe:
            r = forward_return(tk, trade_start, next_month)
            if r is not None and np.isfinite(r):
                fwd[tk] = float(r)
            time.sleep(sleep_sec)

        sig_series = sig_df.set_index("ticker")["signal"]
        fwd_series = pd.Series(fwd, name="fwd_return")
        month_ic = spearman_ic(sig_series.reindex(fwd_series.index), fwd_series)

        # Portfolio returns
        long_rets = [fwd.get(tk) for tk in longs if tk in fwd]
        short_rets = [fwd.get(tk) for tk in shorts if tk in fwd]

        port = float("nan")
        if long_rets:
            port = safe_mean([r for r in long_rets if r is not None])
        if bottom_n > 0 and short_rets:
            port = (0.0 if np.isnan(port) else port) - safe_mean([r for r in short_rets if r is not None])

        bench_ret = float("nan")
        if benchmark:
            br = forward_return(benchmark, trade_start, next_month)
            bench_ret = float(br) if br is not None else float("nan")

        results.append(
            {
                "month": rebalance.strftime("%Y-%m-%d"),
                "asof": asof.strftime("%Y-%m-%d"),
                "lookback_days": lookback_days,
                "universe_size": len(universe),
                "top_n": top_n,
                "bottom_n": bottom_n,
                "longs": ",".join(longs),
                "shorts": ",".join(shorts),
                "portfolio_ret": port,
                "benchmark": benchmark or "",
                "benchmark_ret": bench_ret,
                "excess_ret": (port - bench_ret) if (np.isfinite(port) and np.isfinite(bench_ret)) else float("nan"),
                "top_signal": float(sig_df["signal"].iloc[0]) if not sig_df.empty else float("nan"),
                "ic_spearman": month_ic,
                "ic_n": int(len(fwd_series)),
            }
        )

        ic_rows.append({"month": rebalance.strftime("%Y-%m-%d"), "ic_spearman": month_ic, "n": int(len(fwd_series))})

        print(
            f"[{rebalance.date()}] "
            f"top_signal={results[-1]['top_signal']:.2f} "
            f"IC={month_ic:.3f} (n={len(fwd_series)}) "
            f"port_ret={port:.4f} "
            f"{'bench_ret=' + str(round(bench_ret,4)) if benchmark else ''}"
        )

    res_df = pd.DataFrame(results)
    ic_df = pd.DataFrame(ic_rows)
    return res_df, ic_df


# -----------------------------
# CLI
# -----------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--top-n", type=int, default=50, help="How many stocks to LONG each month.")
    p.add_argument("--bottom-n", type=int, default=0, help="How many stocks to SHORT each month (0 = long-only).")
    p.add_argument("--start", type=str, default="2018-01-01")
    p.add_argument("--end", type=str, default="2025-01-01")
    p.add_argument("--lookback-days", type=int, default=90)
    p.add_argument("--trade-next-day", action="store_true", help="Trade on next day after month start.")
    p.add_argument("--sleep-sec", type=float, default=0.05, help="Throttle requests to avoid rate limits.")

    p.add_argument("--universe-file", type=str, default="", help="Path to tickers file (csv/txt). If empty, uses S&P 500.")
    p.add_argument("--universe-limit", type=int, default=0, help="If >0, only use first N tickers from the universe list.")

    p.add_argument("--cache", type=str, default="ud_events_cache.csv")
    p.add_argument("--refresh-cache", action="store_true", help="Refetch events for all tickers (slow).")

    p.add_argument("--benchmark", type=str, default="SPY", help="Benchmark ticker (e.g., SPY). Use '' to disable.")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.universe_file:
        universe = load_universe_from_file(args.universe_file)
    else:
        universe = fetch_sp500_tickers()

    if args.universe_limit and args.universe_limit > 0:
        universe = universe[: args.universe_limit]

    if len(universe) < 50:
        print(f"WARNING: universe size {len(universe)} is small; signals may have little variation.")

    benchmark = args.benchmark.strip().upper()
    if benchmark == "":
        benchmark = None

    res_df, ic_df = run_backtest(
        universe=universe,
        start=args.start,
        end=args.end,
        top_n=args.top_n,
        bottom_n=args.bottom_n,
        lookback_days=args.lookback_days,
        trade_next_day=args.trade_next_day,
        sleep_sec=args.sleep_sec,
        cache_path=args.cache,
        refresh_cache=args.refresh_cache,
        benchmark=benchmark,
    )

    print("\nMonthly results (head):")
    cols = ["month", "portfolio_ret", "benchmark_ret", "excess_ret", "ic_spearman", "ic_n", "longs", "shorts"]
    print(res_df[cols].head(12).to_string(index=False))

    stats = performance_stats(res_df["portfolio_ret"])
    print("\nPortfolio performance stats:")
    for k, v in stats.items():
        print(f"{k}: {v}")

    if benchmark:
        bstats = performance_stats(res_df["benchmark_ret"])
        print("\nBenchmark performance stats:")
        for k, v in bstats.items():
            print(f"{k}: {v}")

        ex_stats = performance_stats(res_df["excess_ret"])
        print("\nExcess return stats (portfolio - benchmark):")
        for k, v in ex_stats.items():
            print(f"{k}: {v}")

    ic_mean = float(np.nanmean(ic_df["ic_spearman"])) if not ic_df.empty else float("nan")
    ic_median = float(np.nanmedian(ic_df["ic_spearman"])) if not ic_df.empty else float("nan")
    print(f"\nIC summary (Spearman): mean={ic_mean:.4f} median={ic_median:.4f}")

    out_csv = "analyst_ud_grade_delta_backtest.csv"
    res_df.to_csv(out_csv, index=False)
    print(f"\nSaved results to: {out_csv}")

    ic_csv = "analyst_ud_ic.csv"
    ic_df.to_csv(ic_csv, index=False)
    print(f"Saved IC to: {ic_csv}")


if __name__ == "__main__":
    main()