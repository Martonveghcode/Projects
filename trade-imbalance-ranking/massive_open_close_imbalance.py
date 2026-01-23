#!/usr/bin/env python3
"""
Massive (formerly Polygon) — 2-min open + 2-min close trade-imbalance ranker

What it does
- Finds top N tickers by DAILY volume for a given date (US stocks)
- For each ticker:
  - Pulls trades for 09:30–09:32 ET and 15:58–16:00 ET
  - Infers buy/sell direction via tick rule
  - Computes buy vol, sell vol, and imbalance
- Ranks tickers by chosen ranking metric

Auth
- Set env var MASSIVE_API_KEY (do NOT hardcode keys)
  macOS/Linux:
    export MASSIVE_API_KEY="YOUR_KEY"
  Windows PowerShell:
    setx MASSIVE_API_KEY "YOUR_KEY"

Docs:
- Daily Market Summary (grouped): /v2/aggs/grouped/locale/us/market/stocks/{date}
- Trades: /v3/trades/{stockTicker}
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


BASE_URL = "https://api.massive.com"  # Massive REST base
ET = ZoneInfo("America/New_York")


@dataclass
class WindowResult:
    buy_vol: float
    sell_vol: float
    imbalance: float
    total_vol: float
    trades_used: int


@dataclass
class TickerResult:
    ticker: str
    daily_volume: float
    open2m: WindowResult
    close2m: WindowResult


def require_api_key() -> str:
    key = os.getenv("MASSIVE_API_KEY", "").strip()
    if not key:
        print("ERROR: Set MASSIVE_API_KEY in your environment.", file=sys.stderr)
        sys.exit(1)
    return key


def massive_get(
    path_or_url: str,
    api_key: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    Calls Massive endpoints using the apiKey query-string method.
    Massive also supports auth headers, but query-string is simplest here.
    """
    if path_or_url.startswith("http"):
        url = path_or_url
        q = dict(params or {})
        # If next_url already contains apiKey, don't add another.
        if "apiKey=" not in url:
            q["apiKey"] = api_key
    else:
        url = BASE_URL.rstrip("/") + "/" + path_or_url.lstrip("/")
        q = dict(params or {})
        q["apiKey"] = api_key

    r = requests.get(url, params=q, timeout=timeout)
    r.raise_for_status()
    return r.json()


def to_utc_ns(dt_et: datetime) -> int:
    """Convert an ET datetime to UTC nanoseconds since epoch."""
    dt_utc = dt_et.astimezone(timezone.utc)
    return int(dt_utc.timestamp() * 1_000_000_000)


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def previous_weekday(d: date) -> date:
    # Simple fallback (doesn't know market holidays).
    while d.weekday() >= 5:  # Sat/Sun
        d -= timedelta(days=1)
    return d


def get_top_by_daily_volume(api_key: str, trading_date: date, n: int) -> List[Tuple[str, float]]:
    """
    Pulls the grouped daily summary for all US stocks on trading_date, then returns top N by volume.
    Endpoint: /v2/aggs/grouped/locale/us/market/stocks/{date}
    """
    payload = massive_get(f"/v2/aggs/grouped/locale/us/market/stocks/{trading_date.isoformat()}", api_key)
    results = payload.get("results") or []
    # In Massive grouped data: "T" is ticker, "v" is volume. :contentReference[oaicite:3]{index=3}
    vols: List[Tuple[str, float]] = []
    for row in results:
        tkr = row.get("T")
        # Basic sanity filter: common US symbols are 1-5 chars, letters/dots only.
        # Skip obvious junk that can show up in grouped feeds.
        if not (1 <= len(tkr) <= 6):
            continue
        if any(ch.isdigit() for ch in tkr):
            continue
        if not all(ch.isalpha() or ch in ".-" for ch in tkr):
            continue

        vol = row.get("v")
        if not tkr or vol is None:
            continue
        # Skip OTCs unless you want them (grouped endpoint has include_otc flag; default false). :contentReference[oaicite:4]{index=4}
        vols.append((tkr, float(vol)))

    vols.sort(key=lambda x: x[1], reverse=True)
    return vols[:n]


def fetch_trades_in_window(
    api_key: str,
    ticker: str,
    start_et: datetime,
    end_et: datetime,
    pad_seconds_before: int = 30,
    limit: int = 50000,
) -> List[Dict[str, Any]]:
    """
    Fetches trades for a time window. We also fetch a small pad before the window so the first trade
    can be classified by tick rule using a previous price.
    Trades endpoint: /v3/trades/{stockTicker} :contentReference[oaicite:5]{index=5}

    Note: Massive supports timestamp filtering; the docs state `timestamp` can be a date or nanosecond timestamp. :contentReference[oaicite:6]{index=6}
    Massive (like Polygon) typically supports filter modifiers: timestamp.gte, timestamp.lt, etc.
    """
    pad_start_et = start_et - timedelta(seconds=pad_seconds_before)
    start_ns = to_utc_ns(pad_start_et)
    end_ns = to_utc_ns(end_et)

    params = {
        "limit": limit,
        "timestamp.gte": start_ns,
        "timestamp.lt": end_ns,
        # Leaving sort/order unset because the allowed enum values vary by provider plan/version.
        # We'll sort ourselves by sip_timestamp if present.
    }

    out: List[Dict[str, Any]] = []
    url_or_path = f"/v3/trades/{ticker}"
    while True:
        payload = massive_get(url_or_path, api_key, params=params)
        rows = payload.get("results") or []
        out.extend(rows)
        next_url = payload.get("next_url")
        if not next_url:
            break
        # next_url usually already includes the filter params; we just follow it.
        url_or_path = next_url
        params = None  # next_url already encodes paging
        # Be nice to rate limits
        time.sleep(0.05)

    # Prefer sip_timestamp ordering when present. :contentReference[oaicite:7]{index=7}
    def trade_ts_ns(tr: Dict[str, Any]) -> int:
        return int(tr.get("sip_timestamp") or tr.get("participant_timestamp") or tr.get("trf_timestamp") or 0)

    out.sort(key=trade_ts_ns)
    return out


def tick_rule_imbalance(
    trades: List[Dict[str, Any]],
    window_start_et: datetime,
    window_end_et: datetime,
) -> WindowResult:
    """
    Tick rule:
      price up => buy-initiated
      price down => sell-initiated
      price same => carry forward last direction (or unknown until known)
    We only COUNT volume for trades whose timestamp is inside [window_start, window_end).
    """
    start_ns = to_utc_ns(window_start_et)
    end_ns = to_utc_ns(window_end_et)

    buy_vol = 0.0
    sell_vol = 0.0
    last_price: Optional[float] = None
    last_side: Optional[str] = None  # "B" or "S"
    used = 0

    def trade_ts_ns(tr: Dict[str, Any]) -> int:
        return int(tr.get("sip_timestamp") or tr.get("participant_timestamp") or tr.get("trf_timestamp") or 0)

    for tr in trades:
        p = tr.get("price")
        sz = tr.get("size")
        if p is None or sz is None:
            continue
        p = float(p)
        sz = float(sz)

        ts = trade_ts_ns(tr)
        if ts <= 0:
            continue

        # Determine side using tick rule (based on previous trade price).
        side: Optional[str] = None
        if last_price is None:
            side = None
        else:
            if p > last_price:
                side = "B"
            elif p < last_price:
                side = "S"
            else:
                side = last_side  # may still be None

        # Update last_* for next iteration
        last_price = p
        if side in ("B", "S"):
            last_side = side

        # Only count volume if trade is inside the target window.
        if start_ns <= ts < end_ns and side in ("B", "S"):
            used += 1
            if side == "B":
                buy_vol += sz
            else:
                sell_vol += sz

    total = buy_vol + sell_vol
    return WindowResult(
        buy_vol=buy_vol,
        sell_vol=sell_vol,
        imbalance=buy_vol - sell_vol,
        total_vol=total,
        trades_used=used,
    )


def build_results(api_key: str, trading_date: date, top_n: int) -> List[TickerResult]:
    # Select top tickers by DAILY volume for that date
    top = get_top_by_daily_volume(api_key, trading_date, top_n)

    # Define open and close windows in ET (regular session: 9:30–16:00 ET). :contentReference[oaicite:8]{index=8}
    open_start = datetime(trading_date.year, trading_date.month, trading_date.day, 9, 30, 0, tzinfo=ET)
    open_end = open_start + timedelta(minutes=2)
    close_end = datetime(trading_date.year, trading_date.month, trading_date.day, 16, 0, 0, tzinfo=ET)
    close_start = close_end - timedelta(minutes=2)

    out: List[TickerResult] = []

    for i, (ticker, daily_vol) in enumerate(top, start=1):
        print(f"[{i}/{len(top)}] {ticker}  (daily vol={daily_vol:,.0f})", file=sys.stderr)

        try:
            open_trades = fetch_trades_in_window(api_key, ticker, open_start, open_end, pad_seconds_before=45)
            close_trades = fetch_trades_in_window(api_key, ticker, close_start, close_end, pad_seconds_before=45)

            open_res = tick_rule_imbalance(open_trades, open_start, open_end)
            close_res = tick_rule_imbalance(close_trades, close_start, close_end)

        except requests.exceptions.HTTPError as e:
            # If trades are gated (403), fall back to 1-minute bars proxy
            if getattr(e.response, "status_code", None) == 403:
                print(f"  -> 403 on trades for {ticker}. Falling back to 1m bars proxy.", file=sys.stderr)
                open_bars = fetch_1m_bars(api_key, ticker, open_start, open_end)
                close_bars = fetch_1m_bars(api_key, ticker, close_start, close_end)

                open_res = bar_proxy_imbalance(open_bars)
                close_res = bar_proxy_imbalance(close_bars)
            else:
                raise

        out.append(
            TickerResult(
                ticker=ticker,
                daily_volume=daily_vol,
                open2m=open_res,
                close2m=close_res,
            )
        )

    return out


def rank_results(results: List[TickerResult], metric: str) -> List[TickerResult]:
    """
    metric options:
      - open_imbalance
      - close_imbalance
      - abs_open_imbalance
      - abs_close_imbalance
      - combined_abs (abs(open) + abs(close))
      - combined_signed (open + close)
    """
    if metric == "open_imbalance":
        key = lambda r: r.open2m.imbalance
        reverse = True
    elif metric == "close_imbalance":
        key = lambda r: r.close2m.imbalance
        reverse = True
    elif metric == "abs_open_imbalance":
        key = lambda r: abs(r.open2m.imbalance)
        reverse = True
    elif metric == "abs_close_imbalance":
        key = lambda r: abs(r.close2m.imbalance)
        reverse = True
    elif metric == "combined_signed":
        key = lambda r: (r.open2m.imbalance + r.close2m.imbalance)
        reverse = True
    else:  # combined_abs (default)
        key = lambda r: (abs(r.open2m.imbalance) + abs(r.close2m.imbalance))
        reverse = True

    return sorted(results, key=key, reverse=reverse)


def print_table(results: List[TickerResult], top_k: int = 25) -> None:
    print(
        "rank,ticker,daily_volume,"
        "open_buy_vol,open_sell_vol,open_imbalance,open_trades_used,"
        "close_buy_vol,close_sell_vol,close_imbalance,close_trades_used"
    )
    for idx, r in enumerate(results[:top_k], start=1):
        print(
            f"{idx},{r.ticker},{r.daily_volume:.0f},"
            f"{r.open2m.buy_vol:.0f},{r.open2m.sell_vol:.0f},{r.open2m.imbalance:.0f},{r.open2m.trades_used},"
            f"{r.close2m.buy_vol:.0f},{r.close2m.sell_vol:.0f},{r.close2m.imbalance:.0f},{r.close2m.trades_used}"
        )
def fetch_1m_bars(api_key: str, ticker: str, start_et: datetime, end_et: datetime) -> List[Dict[str, Any]]:
    """
    Fetch 1-minute bars using:
      /v2/aggs/ticker/{ticker}/range/1/minute/{from}/{to}
    We request a small range that covers the window; then we filter locally by timestamp.
    """
    # Massive aggregate endpoints use dates; easiest is request the whole day and slice.
    day = start_et.date().isoformat()
    payload = massive_get(
        f"/v2/aggs/ticker/{ticker}/range/1/minute/{day}/{day}",
        api_key,
        params={"adjusted": "true", "limit": 50000},
    )
    bars = payload.get("results") or []

    # Bars have 't' as ms since epoch (Polygon-style). We'll filter by ET window.
    start_ms = int(start_et.astimezone(timezone.utc).timestamp() * 1000)
    end_ms = int(end_et.astimezone(timezone.utc).timestamp() * 1000)

    sliced = [b for b in bars if isinstance(b.get("t"), int) and start_ms <= b["t"] < end_ms]
    return sliced


def bar_proxy_imbalance(bars: List[Dict[str, Any]]) -> WindowResult:
    """
    Proxy for buy/sell using bars only (no tick direction):
      - Treat up-close bars as 'buy volume', down-close as 'sell volume'
      - For doji bars, split volume half/half
    Not true order flow, but consistent for ranking.
    """
    buy = sell = used = 0.0
    trades_used = 0
    for b in bars:
        o = b.get("o"); c = b.get("c"); v = b.get("v")
        if o is None or c is None or v is None:
            continue
        o = float(o); c = float(c); v = float(v)
        trades_used += 1
        if c > o:
            buy += v
        elif c < o:
            sell += v
        else:
            buy += v / 2.0
            sell += v / 2.0

    total = buy + sell
    return WindowResult(
        buy_vol=buy,
        sell_vol=sell,
        imbalance=buy - sell,
        total_vol=total,
        trades_used=trades_used,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=str, default=None, help="Trading date YYYY-MM-DD (default: previous weekday)")
    parser.add_argument("--top-n", type=int, default=100, help="How many tickers to analyze (top by daily volume)")
    parser.add_argument("--rank-by", type=str, default="combined_abs",
                        choices=[
                            "combined_abs", "combined_signed",
                            "open_imbalance", "close_imbalance",
                            "abs_open_imbalance", "abs_close_imbalance",
                        ],
                        help="Ranking metric")
    parser.add_argument("--print-top", type=int, default=25, help="How many rows to print")
    args = parser.parse_args()

    api_key = require_api_key()

    if args.date:
        d = parse_date(args.date)
    else:
        d = previous_weekday(date.today() - timedelta(days=1))

    # Build + rank
    results = build_results(api_key, d, args.top_n)
    ranked = rank_results(results, args.rank_by)

    print_table(ranked, top_k=args.print_top)


if __name__ == "__main__":
    main()
