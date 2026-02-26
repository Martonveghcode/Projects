# True Historical Analyst Backtest (Streamlit)

This project now includes a Streamlit app for a monthly analyst upgrades/downgrades backtest using:

- Local parquet prices (`ticker`, `date`, `adj_close`)
- Local universe CSV (`ticker`)
- Free yfinance analyst events (`get_upgrades_downgrades`)

## Files

- `app.py`: Streamlit UI
- `src/data.py`: local data loading, benchmark cache/fetch helpers
- `src/analyst_events.py`: analyst event fetch/cache + signal logic
- `src/backtest.py`: monthly backtest engine + IC + stats
- `backtest_analyst_ud_local_prices.py.py`: CLI wrapper over the same engine
- `requirements.txt`: dependencies
- `config.json`: auto-created and auto-updated with last used settings

## Setup

```bash
python -m pip install -r requirements.txt
```

## Run Streamlit App

```bash
streamlit run app.py
```

Default paths in the sidebar:

- `data_out/prices_top1000_2y_daily.parquet`
- `data_out/top_1000_tickers.csv`
- `ud_events_cache_top1000.csv`

## What the App Does

1. Loads local prices once and universe tickers from the selected file paths.
2. Loads/fetches analyst events and caches them to CSV.
3. Computes monthly signals per ticker using events dated `<= rebalance date` within `lookback_days`.
4. Rebalances monthly:
   - Longs = top `top_n` signals
   - Shorts = bottom `bottom_n` signals (optional)
5. Uses local parquet prices for forward month returns.
6. Computes:
   - Monthly portfolio, benchmark, and excess returns
   - Performance stats (`total_return`, `CAGR`, `ann_vol`, `sharpe_approx`, `max_drawdown`, `hit_rate`)
   - Spearman IC by month + mean/median IC

## Signal Rules

- Primary: sum of `(toGradeScore - fromGradeScore)` across events in lookback window
- Fallback when grade mapping fails: action weights
  - `upgrade`: +1
  - `downgrade`: -1
  - `initiation`: +0.25
  - default: 0

The grade mapping table is editable in the Streamlit sidebar (Advanced section) and saved to `config.json`.

## Benchmark Behavior

- If benchmark ticker exists in local parquet, local data is used.
- If missing:
  - app checks cache in project folder (`benchmark_<TICKER>.parquet` or `.csv`)
  - if still missing and fetch is enabled, app fetches from yfinance once and caches locally

## CLI Usage (Optional)

```bash
python backtest_analyst_ud_local_prices.py.py \
  --prices-parquet data_out/prices_top1000_2y_daily.parquet \
  --universe-csv data_out/top_1000_tickers.csv \
  --events-cache ud_events_cache_top1000.csv \
  --start 2024-01-01 \
  --end 2025-12-31 \
  --top-n 50 \
  --bottom-n 0 \
  --lookback-days 90 \
  --benchmark SPY \
  --fetch-benchmark-if-missing
```

## Notes

- No paid APIs are used.
- Price data for portfolio returns is always local parquet.
- yfinance prices are used only for benchmark when benchmark is missing locally.

