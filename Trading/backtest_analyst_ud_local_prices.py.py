from __future__ import annotations

import argparse
import json

import pandas as pd

from src.analyst_events import (
    DEFAULT_ACTION_WEIGHTS,
    DEFAULT_GRADE_MAPPING_RULES,
    ensure_events_cache,
)
from src.backtest import run_backtest
from src.data import (
    get_or_fetch_benchmark_prices,
    load_prices_parquet,
    load_universe_csv,
)


def _print_stats(title: str, stats: dict[str, float]) -> None:
    print(f"\n{title}")
    if not stats:
        print("No stats available.")
        return
    for key, value in stats.items():
        print(f"{key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI wrapper for the True Historical Analyst U/D backtest engine."
    )
    parser.add_argument("--prices-parquet", default="data_out/prices_top1000_2y_daily.parquet")
    parser.add_argument("--universe-csv", default="data_out/top_1000_tickers.csv")
    parser.add_argument("--events-cache", default="ud_events_cache_top1000.csv")
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--top-n", type=int, default=50)
    parser.add_argument("--bottom-n", type=int, default=0)
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--sleep-sec", type=float, default=0.05)
    parser.add_argument("--refresh-events-cache", action="store_true")
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--fetch-benchmark-if-missing", action="store_true")
    parser.add_argument("--benchmark-cache-dir", default=".")
    parser.add_argument("--config-json", default="")
    parser.add_argument("--out", default="analyst_ud_backtest_local_prices.csv")
    args = parser.parse_args()

    print("Loading prices and universe...")
    prices = load_prices_parquet(args.prices_parquet)
    universe = load_universe_csv(args.universe_csv)

    print("Ensuring analyst events cache...")
    events, event_stats = ensure_events_cache(
        universe=universe,
        cache_path=args.events_cache,
        sleep_seconds=args.sleep_sec,
        refresh=args.refresh_events_cache,
        logger=print,
    )
    print(
        "Event cache summary: "
        f"rows={event_stats['cache_rows']}, "
        f"tickers_without_events={event_stats['tickers_without_events']}"
    )

    benchmark_prices, benchmark_source = get_or_fetch_benchmark_prices(
        local_prices=prices,
        benchmark_ticker=args.benchmark,
        start_date=pd.Timestamp(args.start),
        end_date=pd.Timestamp(args.end),
        fetch_if_missing=args.fetch_benchmark_if_missing,
        cache_dir=args.benchmark_cache_dir,
        logger=print,
    )
    print(f"Benchmark source: {benchmark_source}")

    grade_mapping = DEFAULT_GRADE_MAPPING_RULES
    action_weights = DEFAULT_ACTION_WEIGHTS
    if args.config_json:
        with open(args.config_json, "r", encoding="utf-8") as handle:
            cfg = json.load(handle)
        if isinstance(cfg, dict):
            grade_mapping = cfg.get("grade_mapping_rules", grade_mapping)
            action_weights = cfg.get("action_weights", action_weights)

    result = run_backtest(
        prices=prices,
        universe=universe,
        events=events,
        start_date=args.start,
        end_date=args.end,
        top_n=args.top_n,
        bottom_n=args.bottom_n,
        lookback_days=args.lookback_days,
        benchmark_prices=benchmark_prices,
        grade_mapping_rules=grade_mapping,
        action_weights=action_weights,
        logger=print,
    )

    monthly = result["monthly_results"].copy()
    monthly["month"] = pd.to_datetime(monthly["month"]).dt.strftime("%Y-%m-%d")
    monthly.to_csv(args.out, index=False)
    print(f"\nSaved monthly results to: {args.out}")
    print(monthly.head(12).to_string(index=False))

    _print_stats("Portfolio stats", result["portfolio_stats"])
    _print_stats("Benchmark stats", result["benchmark_stats"])
    print("\nIC summary")
    for key, value in result["ic_summary"].items():
        print(f"{key}: {value}")
    print("\nDiagnostics")
    for key, value in result["diagnostics"].items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()

