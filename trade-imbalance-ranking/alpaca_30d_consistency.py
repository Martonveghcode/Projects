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
    print("ERROR: Set ALPACA_KEY_ID and ALPACA_SECRET_KEY", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "APCA-API-KEY-ID": KEY,
    "APCA-API-SECRET-KEY": SECRET,
}

SLEEP = 0.35

UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","AMD","NFLX","INTC",
    "JPM","BAC","XOM","CVX","AVGO","ORCL","COST","ADBE","CRM","QCOM",
    "MU","CSCO","PEP","KO","T","VZ","SPY","QQQ","IWM","DIA"
]


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def get_bars(symbols, start_utc, end_utc):
    r = requests.get(
        f"{BASE}/v2/stocks/bars",
        headers=HEADERS,
        params={
            "symbols": ",".join(symbols),
            "timeframe": "1Min",
            "start": iso(start_utc),
            "end": iso(end_utc),
            "limit": 10000,
            "adjustment": "raw",
        },
        timeout=30,
    )
    if r.status_code >= 400:
        raise requests.HTTPError(r.text, response=r)
    time.sleep(SLEEP)
    return r.json().get("bars", {})


def pressure_from_bars(bars):
    buy = sell = 0
    for b in bars:
        o, c, v = b.get("o"), b.get("c"), b.get("v")
        if o is None or c is None or v is None:
            continue
        if c > o:
            buy += v
        elif c < o:
            sell += v
        else:
            buy += v / 2
            sell += v / 2
    return buy - sell


def last_n_trading_days(n):
    days = []
    d = datetime.now(ET).date() - timedelta(days=1)
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()

    days = last_n_trading_days(args.days)

    stats = {
        s: {
            "open_buy": 0,
            "open_sell": 0,
            "close_buy": 0,
            "close_sell": 0,
            "days": 0,
        }
        for s in UNIVERSE
    }

    for d in days:
        open_et = datetime(d.year, d.month, d.day, 9, 30, tzinfo=ET)
        close_et = datetime(d.year, d.month, d.day, 16, 0, tzinfo=ET)

        bars_map = get_bars(
            UNIVERSE,
            open_et.astimezone(timezone.utc),
            close_et.astimezone(timezone.utc),
        )

        for sym in UNIVERSE:
            bars = bars_map.get(sym, [])
            if not bars:
                continue

            open_end = open_et + timedelta(minutes=2)
            close_start = close_et - timedelta(minutes=2)

            open_bars = []
            close_bars = []

            for b in bars:
                ts = datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET)
                if open_et <= ts < open_end:
                    open_bars.append(b)
                if close_start <= ts < close_et:
                    close_bars.append(b)

            if len(open_bars) < 1 or len(close_bars) < 1:
                continue

            oi = pressure_from_bars(open_bars)
            ci = pressure_from_bars(close_bars)

            stats[sym]["days"] += 1

            if oi > 0:
                stats[sym]["open_buy"] += 1
            elif oi < 0:
                stats[sym]["open_sell"] += 1

            if ci > 0:
                stats[sym]["close_buy"] += 1
            elif ci < 0:
                stats[sym]["close_sell"] += 1

    print("symbol,days,open_buy_pct,open_sell_pct,close_buy_pct,close_sell_pct")
    for s, v in stats.items():
        d = v["days"]
        if d == 0:
            continue
        print(
            f"{s},{d},"
            f"{v['open_buy']/d*100:.1f},"
            f"{v['open_sell']/d*100:.1f},"
            f"{v['close_buy']/d*100:.1f},"
            f"{v['close_sell']/d*100:.1f}"
        )


if __name__ == "__main__":
    main()
