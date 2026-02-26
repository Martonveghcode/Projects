import argparse
import os
import re
import time
import math
import numpy as np
import pandas as pd
import yfinance as yf

EVENT_COLS = ["ticker", "date", "action", "fromGrade", "toGrade", "firm"]

# -----------------------------
# Helpers: dates
# -----------------------------
def month_starts(start: str, end: str) -> list[pd.Timestamp]:
    s = pd.Timestamp(start).normalize().replace(day=1)
    e = pd.Timestamp(end).normalize().replace(day=1)
    return list(pd.date_range(s, e, freq="MS", inclusive="left"))

def _clean(s):
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())

def grade_to_score(grade_text):
    g = _clean(grade_text)
    if not g:
        return None

    # bullish / top tier
    if any(k in g for k in ["strong buy", "conviction buy", "top pick"]):
        return 2
    if any(k in g for k in ["overweight", "outperform", "market outperform", "add"]):
        return 2

    # buy-ish
    if any(k in g for k in ["buy", "accumulate", "positive"]):
        return 1

    # neutral
    if any(k in g for k in ["hold", "neutral", "market perform", "equal weight", "in-line", "inline", "perform"]):
        return 0

    # bearish
    if any(k in g for k in ["underperform", "underweight", "reduce", "sell", "negative"]):
        return -1

    # strong sell (rare)
    if "strong sell" in g:
        return -2

    return None

def action_fallback_weight(action):
    a = _clean(action)
    if "upgrade" in a:
        return 1.0
    if "downgrade" in a:
        return -1.0
    if "initiat" in a:
        return 0.25
    return 0.0

def grade_delta_signal(events: pd.DataFrame, asof: pd.Timestamp, lookback_days: int) -> float:
    if events is None or events.empty:
        return 0.0
    start = asof - pd.Timedelta(days=lookback_days)
    w = events[(events["date"] > start) & (events["date"] <= asof)]
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
# Events caching
# -----------------------------
def load_cached_events(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=EVENT_COLS)
    df = pd.read_csv(path)
    if df.empty:
        return pd.DataFrame(columns=EVENT_COLS)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    return df[EVENT_COLS]

def save_cached_events(df: pd.DataFrame, path: str):
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)

def fetch_ud_events_for_ticker(ticker: str) -> pd.DataFrame:
    t = yf.Ticker(ticker)
    df = t.get_upgrades_downgrades()
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=EVENT_COLS)
    if not isinstance(df.index, pd.DatetimeIndex):
        return pd.DataFrame(columns=EVENT_COLS)

    df = df.reset_index().rename(columns={"index": "date"})
    for c in ["action", "fromGrade", "toGrade", "firm"]:
        if c not in df.columns:
            df[c] = None
    df["ticker"] = ticker
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
    return df[EVENT_COLS]

def ensure_events_cached(universe: list[str], cache_path: str, sleep_sec: float):
    cached = load_cached_events(cache_path)
    have = set(cached["ticker"].unique()) if not cached.empty else set()
    missing = [t for t in universe if t not in have]

    if missing:
        parts = []
        for i, tk in enumerate(missing, 1):
            print(f"Fetching U/D events [{i}/{len(missing)}]: {tk}")
            part = fetch_ud_events_for_ticker(tk)
            if part is not None and not part.empty:
                parts.append(part)
            time.sleep(sleep_sec)

        if parts:
            cached = pd.concat([cached, *parts], ignore_index=True)

        cached = cached.drop_duplicates(subset=EVENT_COLS)
        save_cached_events(cached, cache_path)

    cached["date"] = pd.to_datetime(cached["date"], errors="coerce")
    cached = cached.dropna(subset=["date"])
    return cached

# -----------------------------
# Local prices: month-to-month return
# -----------------------------
def first_trading_price(prices: pd.DataFrame, ticker: str, date: pd.Timestamp) -> float | None:
    """
    prices: rows for ONE ticker, sorted by date, columns include 'date' and 'adj_close'
    returns adj_close at first trading day >= date
    """
    s = prices[prices["date"] >= date]
    if s.empty:
        return None
    p = float(s["adj_close"].iloc[0])
    return p if np.isfinite(p) and p > 0 else None

def month_forward_returns_from_local(prices_all: pd.DataFrame, tickers: list[str], start: pd.Timestamp, end: pd.Timestamp) -> dict:
    """
    Compute return for each ticker from first trading day >= start to first trading day >= end.
    Uses local parquet prices (adj_close).
    """
    out = {}
    # filter to needed tickers once
    sub = prices_all[prices_all["ticker"].isin(tickers)]
    # group by ticker for speed
    for tk, df in sub.groupby("ticker", sort=False):
        df = df.sort_values("date")
        p0 = first_trading_price(df, tk, start)
        p1 = first_trading_price(df, tk, end)
        if p0 is None or p1 is None:
            continue
        out[tk] = float(p1 / p0 - 1.0)
    return out

# -----------------------------
# Stats
# -----------------------------
def performance_stats(r: pd.Series) -> dict:
    r = r.dropna().astype(float)
    if r.empty:
        return {}
    equity = (1.0 + r).cumprod()
    total_return = float(equity.iloc[-1] - 1.0)
    n = len(r)
    cagr = float((equity.iloc[-1]) ** (12.0 / n) - 1.0) if n else np.nan
    vol = float(r.std(ddof=1) * math.sqrt(12.0)) if n > 1 else np.nan
    sharpe = float((r.mean() * 12.0) / vol) if np.isfinite(vol) and vol != 0 else np.nan
    peak = equity.cummax()
    dd = equity / peak - 1.0
    return {
        "months": n,
        "total_return": total_return,
        "CAGR": cagr,
        "ann_vol": vol,
        "sharpe_approx": sharpe,
        "max_drawdown": float(dd.min()),
        "hit_rate": float((r > 0).mean()),
    }

# -----------------------------
# Backtest
# -----------------------------
def run_backtest(prices_parquet: str, universe_csv: str, start: str, end: str,
                 top_n: int, bottom_n: int, lookback_days: int, sleep_sec: float,
                 events_cache: str):
    # load universe
    universe = pd.read_csv(universe_csv)["ticker"].astype(str).str.upper().tolist()

    # load prices
    prices = pd.read_parquet(prices_parquet)
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    prices = prices.dropna(subset=["date"])
    prices = prices.sort_values(["ticker", "date"])

    # restrict months to available price range
    min_d = prices["date"].min()
    max_d = prices["date"].max()
    start_ts = max(pd.Timestamp(start), min_d)
    end_ts = min(pd.Timestamp(end), max_d + pd.Timedelta(days=1))

    months = month_starts(start_ts.strftime("%Y-%m-%d"), end_ts.strftime("%Y-%m-%d"))
    if len(months) < 2:
        raise ValueError("Not enough monthly range within your price data. Adjust start/end.")

    # ensure events cached
    events = ensure_events_cached(universe, events_cache, sleep_sec=sleep_sec)

    rows = []
    for i in range(len(months) - 1):
        rebalance = months[i]
        next_month = months[i + 1]
        asof = rebalance

        # signals
        sigs = []
        for tk in universe:
            ev = events[events["ticker"] == tk] if not events.empty else pd.DataFrame(columns=EVENT_COLS)
            s = grade_delta_signal(ev, asof=asof, lookback_days=lookback_days)
            sigs.append((tk, s))

        sig_df = pd.DataFrame(sigs, columns=["ticker", "signal"]).sort_values("signal", ascending=False)
        longs = sig_df.head(top_n)["ticker"].tolist() if top_n > 0 else []
        shorts = sig_df.tail(bottom_n)["ticker"].tolist() if bottom_n > 0 else []

        # forward returns from local prices
        needed = list(dict.fromkeys(longs + shorts))
        fwd = month_forward_returns_from_local(prices, needed, rebalance, next_month)

        long_rets = [fwd.get(tk) for tk in longs if tk in fwd]
        short_rets = [fwd.get(tk) for tk in shorts if tk in fwd]

        port = np.nan
        if long_rets:
            port = float(np.mean(long_rets))
        if bottom_n > 0 and short_rets:
            port = (0.0 if np.isnan(port) else port) - float(np.mean(short_rets))

        rows.append({
            "month": rebalance.strftime("%Y-%m-%d"),
            "top_n": top_n,
            "bottom_n": bottom_n,
            "lookback_days": lookback_days,
            "longs": ",".join(longs),
            "shorts": ",".join(shorts),
            "portfolio_ret": port,
            "top_signal": float(sig_df["signal"].iloc[0]) if len(sig_df) else np.nan,
        })

        print(f"[{rebalance.date()}] port_ret={port:.4f} top_signal={rows[-1]['top_signal']:.2f}")

    res = pd.DataFrame(rows)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices-parquet", required=True)
    ap.add_argument("--universe-csv", required=True)
    ap.add_argument("--start", default="2020-11-01")
    ap.add_argument("--end", default="2022-11-15")
    ap.add_argument("--top-n", type=int, default=50)
    ap.add_argument("--bottom-n", type=int, default=0)
    ap.add_argument("--lookback-days", type=int, default=90)
    ap.add_argument("--sleep-sec", type=float, default=0.05)
    ap.add_argument("--events-cache", default="ud_events_cache_top1000.csv")
    ap.add_argument("--out", default="analyst_ud_backtest_local_prices.csv")
    args = ap.parse_args()

    df = run_backtest(
        prices_parquet=args.prices_parquet,
        universe_csv=args.universe_csv,
        start=args.start,
        end=args.end,
        top_n=args.top_n,
        bottom_n=args.bottom_n,
        lookback_days=args.lookback_days,
        sleep_sec=args.sleep_sec,
        events_cache=args.events_cache,
    )

    print("\nMonthly results (head):")
    print(df[["month", "portfolio_ret", "top_signal"]].head(12).to_string(index=False))

    stats = performance_stats(df["portfolio_ret"])
    print("\nPerformance stats:")
    for k, v in stats.items():
        print(f"{k}: {v}")

    df.to_csv(args.out, index=False)
    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()