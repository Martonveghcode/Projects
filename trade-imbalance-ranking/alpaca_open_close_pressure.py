import os
import sys
import time
import argparse
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
BASE = "https://data.alpaca.markets"

KEY = os.getenv("ALPACA_KEY_ID")
SECRET = os.getenv("ALPACA_SECRET_KEY")
if not KEY or not SECRET:
    print("ERROR: Set ALPACA_KEY_ID and ALPACA_SECRET_KEY env vars.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "APCA-API-KEY-ID": KEY,
    "APCA-API-SECRET-KEY": SECRET,
}

SLEEP = 0.35  # be nice to rate limits


def get_json(url, params=None):
    r = requests.get(url, headers=HEADERS, params=params, timeout=30)
    if r.status_code >= 400:
        raise requests.HTTPError(f"{r.status_code} {r.text}", response=r)
    return r.json()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def pressure_from_bars(bars):
    buy = sell = 0.0
    used = 0
    for b in bars:
        o = b.get("o"); c = b.get("c"); v = b.get("v")
        if o is None or c is None or v is None:
            continue
        used += 1
        if c > o:
            buy += v
        elif c < o:
            sell += v
        else:
            buy += v / 2
            sell += v / 2
    return buy, sell, buy - sell, used


def get_1m_bars(symbols, start_utc: datetime, end_utc: datetime):
    # Alpaca supports multi-symbol bars via /v2/stocks/bars with symbols=...
    url = f"{BASE}/v2/stocks/bars"
    params = {
        "symbols": ",".join(symbols),
        "timeframe": "1Min",
        "start": iso(start_utc),
        "end": iso(end_utc),
        "limit": 10000,
        "adjustment": "raw",
    }
    data = get_json(url, params=params)
    time.sleep(SLEEP)
    return data.get("bars", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYY-MM-DD in US/Eastern (default: previous weekday)")
    ap.add_argument("--top-n", type=int, default=100, help="How many symbols to rank (by daily volume)")
    ap.add_argument("--universe", default="SPY", choices=["SPY", "LIQUID30"],
                    help="Symbol universe: SPY = use SPY holdings list (you provide), LIQUID30 = built-in small list")
    ap.add_argument("--rank-by", default="open", choices=["open", "close", "combined_abs"],
                    help="Ranking metric")
    args = ap.parse_args()

    # Basic liquid universe (works without extra files)
    liquid30 = [
        "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","AMD","NFLX","INTC",
        "JPM","BAC","XOM","CVX","AVGO","ORCL","COST","ADBE","CRM","QCOM",
        "MU","CSCO","PEP","KO","T","VZ","SPY","QQQ","IWM","DIA"
    ]
    symbols = liquid30

    # Choose date (ET), default yesterday (and skip weekends)
    today = datetime.now(ET).date()
    if args.date:
        d = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        d = today - timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)

    market_open_et = datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET)
    market_close_et = datetime(d.year, d.month, d.day, 16, 0, tzinfo=ET)

    # Pull full-day 1m bars (single request for many symbols)
    bars_map = get_1m_bars(
        symbols,
        market_open_et.astimezone(timezone.utc),
        market_close_et.astimezone(timezone.utc),
    )

    # Compute daily volume for ranking top N by volume
    daily_vol = {}
    for sym in symbols:
        sym_bars = bars_map.get(sym, [])
        daily_vol[sym] = sum(b.get("v", 0) for b in sym_bars)

    top = sorted(symbols, key=lambda s: daily_vol.get(s, 0), reverse=True)[:args.top_n]

    # Compute open/close 2-minute windows from the already-fetched day bars
    results = []
    for sym in top:
        sym_bars = bars_map.get(sym, [])
        # Bars have 't' in RFC3339; we’ll slice by ET time boundaries by converting timestamps.
        open_end = market_open_et + timedelta(minutes=2)
        close_start = market_close_et - timedelta(minutes=2)

        open_slice = []
        close_slice = []
        for b in sym_bars:
            ts = b.get("t")
            if not ts:
                continue
            # Parse like "2026-01-22T14:30:00Z"
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(ET)
            if market_open_et <= dt < open_end:
                open_slice.append(b)
            if close_start <= dt < market_close_et:
                close_slice.append(b)

        ob, os, oi, on = pressure_from_bars(open_slice)
        cb, cs, ci, cn = pressure_from_bars(close_slice)

        results.append({
            "symbol": sym,
            "daily_volume": daily_vol.get(sym, 0),
            "open_imbalance": oi,
            "close_imbalance": ci,
            "combined_abs": abs(oi) + abs(ci),
            "open_bars": on,
            "close_bars": cn,
        })

    if args.rank_by == "open":
        results.sort(key=lambda r: r["open_imbalance"], reverse=True)
    elif args.rank_by == "close":
        results.sort(key=lambda r: r["close_imbalance"], reverse=True)
    else:
        results.sort(key=lambda r: r["combined_abs"], reverse=True)

    print("rank,symbol,daily_volume,open_imbalance,close_imbalance,combined_abs,open_bars,close_bars")
    for i, r in enumerate(results, 1):
        print(f"{i},{r['symbol']},{int(r['daily_volume'])},{int(r['open_imbalance'])},{int(r['close_imbalance'])},{int(r['combined_abs'])},{r['open_bars']},{r['close_bars']}")


if __name__ == "__main__":
    main()
