# True Historical Analyst Backtest (Streamlit)

This project includes a Streamlit app for monthly analyst-signal backtesting using:

- yfinance prices (auto-fetched and cached locally by the app)
- Local universe CSV (`ticker`) or Finnhub-ranked universe
- yfinance analyst events or Finnhub recommendation ratings

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

1. Builds universe from selected source.
2. Lets you choose universe source:
   - CSV universe file
   - Finnhub monthly-performance ranked universe (rate-limit aware + cached)
3. Lets you choose analyst source:
   - yfinance upgrades/downgrades events
   - Finnhub recommendation ratings (rate-limit aware + cached)
4. Loads/fetches and caches the selected analyst source.
5. For Finnhub ratings, you can auto-match `months_back` to backtest date window.
3. Computes monthly signals per ticker using events dated `<= rebalance date` within `lookback_days`.
4. Rebalances monthly:
   - Longs = top `top_n` signals
   - Shorts = bottom `bottom_n` signals (optional)
5. Uses yfinance prices (cached) for forward month returns.
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

## Finnhub Ratings Fetch (Separate Script)

This is a separate fetcher for analyst ratings trend data from Finnhub (`stock/recommendation`).

- Script: `fetch_finnhub_analyst_ratings.py`
- GUI: `finnhub_ratings_gui.py` (Streamlit)

### GUI Run

```bash
python -m streamlit run Trading/finnhub_ratings_gui.py
```

In the GUI you can choose:

- `Normal` mode: fetch all tickers from universe CSV
- `Retry errors` mode: fetch only tickers listed in your errors CSV
- `Top N tickers` to fetch (example: 50)
- `Months to keep` (example: 24)

Rate-limit behavior:

- If Finnhub returns rate-limit response, the fetcher waits at least 30 seconds (or longer if headers indicate) and retries the same ticker.
- Failed transient tickers are retried automatically in additional rounds, so you do not need manual reruns for normal rate-limit/network spikes.

Coverage output:

- `data_out/finnhub_analyst_ratings_coverage.csv` shows requested months vs months returned for each ticker.
- If months returned is lower than requested (for example 4 returned when 24 requested), that is a provider-side history limit for your current plan/data.

Finnhub universe performance mode:

- Backtest UI can rank candidate tickers using Finnhub `stock/metric` monthly-return style fields.
- This uses rate-limit-aware retries and a local cache file (`data_out/finnhub_universe_performance.csv` by default).

### CLI Run (Normal)

```bash
python Trading/fetch_finnhub_analyst_ratings.py \
  --api-key YOUR_FINNHUB_KEY \
  --mode normal \
  --limit 50 \
  --months-back 24
```

### CLI Run (Retry Errors)

```bash
python Trading/fetch_finnhub_analyst_ratings.py \
  --api-key YOUR_FINNHUB_KEY \
  --mode errors \
  --errors-source-csv data_out/finnhub_analyst_ratings_errors.csv
```

## Notes

- No paid APIs are used.
- Price data for portfolio returns is always local parquet.
- yfinance prices are used only for benchmark when benchmark is missing locally.
