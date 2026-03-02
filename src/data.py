from __future__ import annotations

import os
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import requests
import yfinance as yf

REQUIRED_PRICE_COLUMNS = {"ticker", "date", "adj_close"}


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if logger is not None:
        logger(message)


@lru_cache(maxsize=4)
def _read_prices_cached(absolute_path: str) -> pd.DataFrame:
    if not os.path.exists(absolute_path):
        raise FileNotFoundError(f"Prices parquet not found: {absolute_path}")

    frame = pd.read_parquet(absolute_path)
    missing = REQUIRED_PRICE_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(
            f"Prices parquet missing required columns: {sorted(missing)}"
        )

    cleaned = frame[["ticker", "date", "adj_close"]].copy()
    cleaned["ticker"] = cleaned["ticker"].astype(str).str.upper().str.strip()
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce")
    cleaned["adj_close"] = pd.to_numeric(cleaned["adj_close"], errors="coerce")
    cleaned = cleaned.dropna(subset=["ticker", "date", "adj_close"]).reset_index(drop=True)
    cleaned = cleaned[cleaned["adj_close"] > 0].reset_index(drop=True)
    cleaned = cleaned.sort_values(["ticker", "date"]).reset_index(drop=True)
    return cleaned


def load_prices_parquet(path: str) -> pd.DataFrame:
    absolute = str(Path(path).expanduser().resolve())
    return _read_prices_cached(absolute).copy()


def _normalize_prices_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["ticker", "date", "adj_close"])
    out = frame.copy()
    for col in ["ticker", "date", "adj_close"]:
        if col not in out.columns:
            out[col] = np.nan
    out = out[["ticker", "date", "adj_close"]].copy()
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["adj_close"] = pd.to_numeric(out["adj_close"], errors="coerce")
    out = out.dropna(subset=["ticker", "date", "adj_close"]).reset_index(drop=True)
    out = out[out["adj_close"] > 0].reset_index(drop=True)
    out = out.sort_values(["ticker", "date"]).drop_duplicates(
        subset=["ticker", "date"], keep="last"
    )
    return out.reset_index(drop=True)


def _load_prices_cache(cache_path: str) -> pd.DataFrame:
    if not os.path.exists(cache_path):
        return pd.DataFrame(columns=["ticker", "date", "adj_close"])
    if str(cache_path).lower().endswith(".parquet"):
        try:
            return _normalize_prices_frame(pd.read_parquet(cache_path))
        except Exception:  # noqa: BLE001
            csv_fallback = os.path.splitext(cache_path)[0] + ".csv"
            if os.path.exists(csv_fallback):
                return _normalize_prices_frame(pd.read_csv(csv_fallback))
            return pd.DataFrame(columns=["ticker", "date", "adj_close"])
    try:
        return _normalize_prices_frame(pd.read_csv(cache_path))
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=["ticker", "date", "adj_close"])


def _save_prices_cache(frame: pd.DataFrame, cache_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
    out = _normalize_prices_frame(frame)
    if str(cache_path).lower().endswith(".parquet"):
        try:
            out.to_parquet(cache_path, index=False)
            return
        except Exception:  # noqa: BLE001
            csv_fallback = os.path.splitext(cache_path)[0] + ".csv"
            out.to_csv(csv_fallback, index=False)
            return
    out.to_csv(cache_path, index=False)


def _missing_prices_cache_path(cache_path: str) -> str:
    path = Path(cache_path).expanduser().resolve()
    suffix = "".join(path.suffixes)
    stem = path.name[: -len(suffix)] if suffix else path.name
    return str(path.with_name(f"{stem}_missing_tickers.csv"))


def _load_missing_price_tickers(cache_path: str) -> set[str]:
    path = _missing_prices_cache_path(cache_path)
    if not os.path.exists(path):
        return set()
    try:
        frame = pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return set()
    if "ticker" not in frame.columns:
        return set()
    tickers = frame["ticker"].astype(str).str.upper().str.strip()
    return {ticker for ticker in tickers if ticker}


def _save_missing_price_tickers(cache_path: str, tickers: set[str]) -> None:
    path = _missing_prices_cache_path(cache_path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    out = pd.DataFrame({"ticker": sorted(tickers)})
    out.to_csv(path, index=False)


def _extract_downloaded_close(history: pd.DataFrame) -> pd.Series | None:
    if history is None or history.empty:
        return None
    if isinstance(history.columns, pd.MultiIndex):
        lvl0 = history.columns.get_level_values(0)
        if "Close" in lvl0:
            sub = history["Close"]
            if isinstance(sub, pd.DataFrame):
                return sub.iloc[:, 0]
            return sub
        if "Adj Close" in lvl0:
            sub = history["Adj Close"]
            if isinstance(sub, pd.DataFrame):
                return sub.iloc[:, 0]
            return sub
        return None
    if "Close" in history.columns:
        return history["Close"]
    if "Adj Close" in history.columns:
        return history["Adj Close"]
    return None


def _fetch_prices_from_alpaca(
    ticker: str,
    start_date: str,
    end_date: str,
    api_key: str,
    api_secret: str,
    timeout: int = 20,
) -> pd.DataFrame:
    if not api_key or not api_secret:
        return pd.DataFrame(columns=["ticker", "date", "adj_close"])

    url = f"https://data.alpaca.markets/v2/stocks/{ticker}/bars"
    headers = {
        "APCA-API-KEY-ID": str(api_key),
        "APCA-API-SECRET-KEY": str(api_secret),
    }
    params = {
        "timeframe": "1Day",
        "start": f"{start_date}T00:00:00Z",
        "end": f"{end_date}T23:59:59Z",
        "adjustment": "all",
        "feed": "iex",
        "limit": 10000,
    }
    response = requests.get(url, headers=headers, params=params, timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"Alpaca HTTP {response.status_code}: {response.text[:200]}")
    payload = response.json()
    bars = payload.get("bars") if isinstance(payload, dict) else None
    if not isinstance(bars, list) or len(bars) == 0:
        return pd.DataFrame(columns=["ticker", "date", "adj_close"])

    rows: list[dict[str, object]] = []
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        timestamp = bar.get("t")
        close = bar.get("c")
        if timestamp is None or close is None:
            continue
        rows.append(
            {
                "ticker": str(ticker).upper().strip(),
                "date": pd.to_datetime(timestamp, errors="coerce", utc=True).tz_convert(None),
                "adj_close": close,
            }
        )

    if not rows:
        return pd.DataFrame(columns=["ticker", "date", "adj_close"])
    return pd.DataFrame(rows, columns=["ticker", "date", "adj_close"])


def fetch_prices_from_yfinance(
    tickers: Iterable[str],
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    cache_path: str = "data_out/yfinance_prices_cache.parquet",
    refresh: bool = False,
    fetch_missing: bool = True,
    provider: str = "yfinance",
    alpaca_api_key: str = "",
    alpaca_api_secret: str = "",
    alpaca_timeout: int = 20,
    sleep_seconds: float = 0.0,
    logger: Callable[[str], None] | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    tickers_clean = [str(t).upper().strip() for t in tickers if str(t).strip()]
    tickers_clean = list(dict.fromkeys(tickers_clean))
    if not tickers_clean:
        raise ValueError("No tickers supplied for yfinance price fetch.")

    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()
    if end_ts <= start_ts:
        raise ValueError("end_date must be after start_date for price fetch.")
    provider_clean = str(provider or "yfinance").strip().lower()
    if provider_clean not in {"yfinance", "alpaca", "auto"}:
        raise ValueError("provider must be one of: yfinance, alpaca, auto")

    cached = pd.DataFrame(columns=["ticker", "date", "adj_close"]) if refresh else _load_prices_cache(cache_path)
    known_missing_tickers = set() if refresh else _load_missing_price_tickers(cache_path)
    fetch_candidates = [ticker for ticker in tickers_clean if ticker not in known_missing_tickers]
    skipped_known_missing = [ticker for ticker in tickers_clean if ticker in known_missing_tickers]

    have_cov: dict[str, bool] = {}
    if not cached.empty:
        span = cached.groupby("ticker")["date"].agg(["min", "max"])
        for ticker in fetch_candidates:
            if ticker in span.index:
                min_d = pd.Timestamp(span.loc[ticker, "min"]).normalize()
                max_d = pd.Timestamp(span.loc[ticker, "max"]).normalize()
                have_cov[ticker] = min_d <= start_ts and max_d >= end_ts
            else:
                have_cov[ticker] = False
    else:
        have_cov = {ticker: False for ticker in fetch_candidates}

    coverage_gap_tickers = [ticker for ticker in fetch_candidates if not have_cov.get(ticker, False)]
    missing = coverage_gap_tickers if fetch_missing else []
    _log(
        logger,
        (
            f"Price cache: {cache_path} | requested={len(tickers_clean)} "
            f"| coverage_gap={len(coverage_gap_tickers)} | missing_fetch={len(missing)} "
            f"| skipped_known_missing={len(skipped_known_missing)} | fetch_missing={bool(fetch_missing)} "
            f"| provider={provider_clean}"
        ),
    )
    if coverage_gap_tickers and not fetch_missing:
        _log(
            logger,
            "Auto-fetch missing prices is disabled; using cached data only for this run.",
        )

    fetched_parts: list[pd.DataFrame] = []
    tickers_with_no_price_data: set[str] = set()
    fetched_success_tickers: set[str] = set()
    fetch_start = (start_ts - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    fetch_end = (end_ts + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    provider_alpaca_attempted = 0
    provider_alpaca_success = 0
    provider_yf_attempted = 0
    provider_yf_success = 0
    for idx, ticker in enumerate(missing, start=1):
        _log(logger, f"Fetching prices [{idx}/{len(missing)}]: {ticker}")
        try:
            part = pd.DataFrame(columns=["ticker", "date", "adj_close"])
            used_provider = None
            if provider_clean in {"alpaca", "auto"} and alpaca_api_key and alpaca_api_secret:
                provider_alpaca_attempted += 1
                try:
                    alpaca_part = _fetch_prices_from_alpaca(
                        ticker=ticker,
                        start_date=fetch_start,
                        end_date=fetch_end,
                        api_key=alpaca_api_key,
                        api_secret=alpaca_api_secret,
                        timeout=int(alpaca_timeout),
                    )
                    if alpaca_part is not None and not alpaca_part.empty:
                        part = alpaca_part
                        used_provider = "alpaca"
                        provider_alpaca_success += 1
                    elif provider_clean == "alpaca":
                        _log(logger, f"Alpaca returned no daily bars for {ticker}.")
                except Exception as exc:  # noqa: BLE001
                    _log(logger, f"Alpaca fetch failed for {ticker}: {exc}")
                    if provider_clean == "alpaca":
                        part = pd.DataFrame(columns=["ticker", "date", "adj_close"])

            if part.empty and provider_clean in {"yfinance", "auto"}:
                provider_yf_attempted += 1
                history = yf.download(
                    ticker,
                    start=fetch_start,
                    end=fetch_end,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
                close = _extract_downloaded_close(history)
                if close is not None and not close.empty:
                    part = close.rename("adj_close").to_frame().reset_index()
                    part = part.rename(columns={part.columns[0]: "date"})
                    part["ticker"] = ticker
                    part = part[["ticker", "date", "adj_close"]]
                    used_provider = "yfinance"
                    provider_yf_success += 1

            if part is None or part.empty:
                tickers_with_no_price_data.add(ticker)
                _log(
                    logger,
                    f"No price data returned for {ticker}; will skip in future runs unless refresh is enabled.",
                )
                continue
            fetched_parts.append(part)
            fetched_success_tickers.add(ticker)
            if used_provider:
                _log(logger, f"{ticker}: fetched from {used_provider}.")
        except Exception as exc:  # noqa: BLE001
            _log(logger, f"Failed prices fetch for {ticker}: {exc}")
        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

    if fetched_parts:
        fetched = _normalize_prices_frame(pd.concat(fetched_parts, ignore_index=True))
        cached = fetched if cached.empty else _normalize_prices_frame(pd.concat([cached, fetched], ignore_index=True))
        _save_prices_cache(cached, cache_path=cache_path)
        _log(logger, f"Saved price cache with {len(cached):,} rows.")
    elif refresh:
        _save_prices_cache(cached, cache_path=cache_path)

    # Persist a list of symbols that consistently return no price history so repeated runs skip them.
    known_missing_tickers = set(known_missing_tickers)
    known_missing_tickers.update(tickers_with_no_price_data)
    known_missing_tickers.difference_update(fetched_success_tickers)
    _save_missing_price_tickers(cache_path=cache_path, tickers=known_missing_tickers)

    selected = cached[cached["ticker"].isin(tickers_clean)].copy()
    selected = selected[
        (selected["date"] >= start_ts - pd.Timedelta(days=7))
        & (selected["date"] <= end_ts + pd.Timedelta(days=7))
    ].copy()
    selected = _normalize_prices_frame(selected)

    covered_tickers = selected.groupby("ticker").size().index.tolist() if not selected.empty else []
    missing_data_tickers = [ticker for ticker in tickers_clean if ticker not in set(covered_tickers)]
    stats = {
        "requested_tickers": len(tickers_clean),
        "fetched_tickers": len(missing),
        "coverage_gap_tickers": len(coverage_gap_tickers),
        "missing_fetch_enabled": bool(fetch_missing),
        "known_missing_tickers_skipped": len(skipped_known_missing),
        "known_missing_tickers_total": len(known_missing_tickers),
        "cache_rows_total": int(len(cached)),
        "selected_rows": int(len(selected)),
        "tickers_with_prices": len(covered_tickers),
        "tickers_without_prices": len(missing_data_tickers),
        "missing_price_tickers": missing_data_tickers,
        "known_missing_price_tickers": sorted(known_missing_tickers),
        "provider": provider_clean,
        "alpaca_attempted": int(provider_alpaca_attempted),
        "alpaca_success": int(provider_alpaca_success),
        "yfinance_attempted": int(provider_yf_attempted),
        "yfinance_success": int(provider_yf_success),
        "cache_path": cache_path,
    }
    return selected.reset_index(drop=True), stats


def load_universe_csv(path: str) -> list[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Universe CSV not found: {path}")
    frame = pd.read_csv(path)
    if "ticker" not in frame.columns:
        raise ValueError("Universe CSV must include a 'ticker' column.")
    tickers = frame["ticker"].astype(str).str.upper().str.strip()
    tickers = [ticker for ticker in tickers if ticker]
    return list(dict.fromkeys(tickers))


def clamp_date_range_to_prices(
    prices: pd.DataFrame,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    prices_min = pd.Timestamp(prices["date"].min()).normalize()
    prices_max = pd.Timestamp(prices["date"].max()).normalize()
    requested_start = pd.Timestamp(start_date).normalize()
    requested_end = pd.Timestamp(end_date).normalize()

    clamped_start = max(prices_min, requested_start)
    clamped_end = min(prices_max, requested_end)
    if clamped_end <= clamped_start:
        raise ValueError(
            "Date range has no overlap with available prices after clamping. "
            f"Requested {requested_start.date()}..{requested_end.date()}, "
            f"available {prices_min.date()}..{prices_max.date()}."
        )
    return clamped_start, clamped_end, prices_min, prices_max


def build_month_boundaries(
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
) -> list[pd.Timestamp]:
    start_ts = pd.Timestamp(start_date).normalize().replace(day=1)
    end_ts = pd.Timestamp(end_date).normalize().replace(day=1)
    last_boundary = end_ts + pd.offsets.MonthBegin(1)
    boundaries = list(pd.date_range(start_ts, last_boundary, freq="MS"))
    if len(boundaries) < 2:
        raise ValueError("Need at least one full monthly interval in the selected range.")
    return boundaries


def compute_interval_returns(
    prices: pd.DataFrame,
    tickers: Iterable[str],
    boundaries: list[pd.Timestamp],
) -> pd.DataFrame:
    tickers_clean = [str(ticker).upper().strip() for ticker in tickers if str(ticker).strip()]
    tickers_clean = list(dict.fromkeys(tickers_clean))
    if len(boundaries) < 2:
        return pd.DataFrame(columns=["month", "ticker", "fwd_ret"])

    subset = prices[prices["ticker"].isin(tickers_clean)].copy()
    if subset.empty:
        return pd.DataFrame(columns=["month", "ticker", "fwd_ret"])

    boundary_values = np.array(boundaries, dtype="datetime64[ns]")
    month_labels = boundaries[:-1]
    parts: list[pd.DataFrame] = []

    for ticker, part in subset.groupby("ticker", sort=False):
        dates = part["date"].to_numpy(dtype="datetime64[ns]")
        adj_close = part["adj_close"].to_numpy(dtype=float)
        if len(dates) == 0:
            continue

        idx = np.searchsorted(dates, boundary_values, side="left")
        boundary_prices = np.full(len(boundary_values), np.nan)
        valid_idx = idx < len(adj_close)
        boundary_prices[valid_idx] = adj_close[idx[valid_idx]]

        rets = boundary_prices[1:] / boundary_prices[:-1] - 1.0
        invalid = (boundary_prices[:-1] <= 0) | (~np.isfinite(rets))
        rets[invalid] = np.nan

        ticker_frame = pd.DataFrame(
            {"month": month_labels, "ticker": ticker, "fwd_ret": rets}
        )
        parts.append(ticker_frame)

    if not parts:
        return pd.DataFrame(columns=["month", "ticker", "fwd_ret"])

    output = pd.concat(parts, ignore_index=True)
    output = output.dropna(subset=["fwd_ret"]).reset_index(drop=True)
    return output


def _benchmark_cache_paths(cache_dir: str, ticker: str) -> tuple[Path, Path]:
    safe_ticker = str(ticker).upper().strip().replace("/", "_")
    base = Path(cache_dir).expanduser().resolve()
    return base / f"benchmark_{safe_ticker}.parquet", base / f"benchmark_{safe_ticker}.csv"


def _load_cached_benchmark(cache_dir: str, ticker: str) -> pd.DataFrame:
    parquet_path, csv_path = _benchmark_cache_paths(cache_dir, ticker)

    if parquet_path.exists():
        try:
            frame = pd.read_parquet(parquet_path)
            return _normalize_benchmark_frame(frame, ticker=ticker)
        except Exception:  # noqa: BLE001
            pass

    if csv_path.exists():
        frame = pd.read_csv(csv_path)
        return _normalize_benchmark_frame(frame, ticker=ticker)

    return pd.DataFrame(columns=["ticker", "date", "adj_close"])


def _save_cached_benchmark(
    benchmark_prices: pd.DataFrame,
    cache_dir: str,
    ticker: str,
    logger: Callable[[str], None] | None = None,
) -> None:
    parquet_path, csv_path = _benchmark_cache_paths(cache_dir, ticker)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    output = benchmark_prices.copy()
    output = output.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)

    try:
        output.to_parquet(parquet_path, index=False)
        _log(logger, f"Saved benchmark cache: {parquet_path}")
    except Exception as exc:  # noqa: BLE001
        _log(logger, f"Could not write parquet benchmark cache ({exc}), writing CSV instead.")
        output.to_csv(csv_path, index=False)
        _log(logger, f"Saved benchmark cache: {csv_path}")


def _normalize_benchmark_frame(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["ticker", "date", "adj_close"])

    output = frame.copy()
    if "date" not in output.columns:
        first_col = output.columns[0]
        output = output.rename(columns={first_col: "date"})
    if "adj_close" not in output.columns:
        if "Close" in output.columns:
            output["adj_close"] = output["Close"]
        elif "close" in output.columns:
            output["adj_close"] = output["close"]
        else:
            return pd.DataFrame(columns=["ticker", "date", "adj_close"])
    output["ticker"] = str(ticker).upper().strip()
    output["date"] = pd.to_datetime(output["date"], errors="coerce")
    output["adj_close"] = pd.to_numeric(output["adj_close"], errors="coerce")
    output = output.dropna(subset=["date", "adj_close"]).reset_index(drop=True)
    output = output[output["adj_close"] > 0].reset_index(drop=True)
    return output[["ticker", "date", "adj_close"]]


def _extract_close_series(history: pd.DataFrame) -> pd.Series | None:
    if history is None or history.empty:
        return None

    if isinstance(history.columns, pd.MultiIndex):
        first_level = history.columns.get_level_values(0)
        for label in ["Close", "Adj Close"]:
            if label in first_level:
                candidate = history[label]
                if isinstance(candidate, pd.DataFrame):
                    return candidate.iloc[:, 0]
                return candidate
        return None

    for label in ["Close", "Adj Close"]:
        if label in history.columns:
            return history[label]
    return None


def _fetch_benchmark_from_yfinance(
    ticker: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    logger: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    padded_start = (start_date - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    padded_end = (end_date + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    _log(
        logger,
        f"Fetching benchmark {ticker} from yfinance for {padded_start}..{padded_end}",
    )
    history = yf.download(
        ticker,
        start=padded_start,
        end=padded_end,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    close = _extract_close_series(history)
    if close is None or close.empty:
        raise RuntimeError(f"No benchmark price data returned for {ticker}.")

    frame = close.rename("adj_close").to_frame().reset_index()
    frame = frame.rename(columns={frame.columns[0]: "date"})
    frame["ticker"] = str(ticker).upper().strip()
    frame = frame[["ticker", "date", "adj_close"]]
    return _normalize_benchmark_frame(frame, ticker=ticker)


def _has_coverage(
    prices: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> bool:
    if prices is None or prices.empty:
        return False
    min_date = pd.Timestamp(prices["date"].min()).normalize()
    max_date = pd.Timestamp(prices["date"].max()).normalize()
    return min_date <= start_date.normalize() and max_date >= end_date.normalize()


def get_or_fetch_benchmark_prices(
    local_prices: pd.DataFrame,
    benchmark_ticker: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    fetch_if_missing: bool = True,
    cache_dir: str = ".",
    logger: Callable[[str], None] | None = None,
) -> tuple[pd.DataFrame, str]:
    ticker = str(benchmark_ticker).upper().strip()
    if not ticker:
        return pd.DataFrame(columns=["ticker", "date", "adj_close"]), "none"

    local_subset = local_prices[local_prices["ticker"] == ticker][
        ["ticker", "date", "adj_close"]
    ].copy()
    if not local_subset.empty:
        _log(logger, f"Using local benchmark prices for {ticker}.")
        return local_subset.sort_values("date").reset_index(drop=True), "local"

    cached = _load_cached_benchmark(cache_dir=cache_dir, ticker=ticker)
    if _has_coverage(cached, start_date=start_date, end_date=end_date):
        _log(logger, f"Using cached benchmark prices for {ticker}.")
        return cached.sort_values("date").reset_index(drop=True), "cache"

    if not fetch_if_missing:
        raise ValueError(
            f"Benchmark {ticker} not found in local parquet or cache, and fetch-if-missing is disabled."
        )

    fetched = _fetch_benchmark_from_yfinance(
        ticker=ticker, start_date=start_date, end_date=end_date, logger=logger
    )
    merged = pd.concat([cached, fetched], ignore_index=True) if not cached.empty else fetched
    merged = _normalize_benchmark_frame(merged, ticker=ticker)
    merged = merged.sort_values("date").drop_duplicates(subset=["date"]).reset_index(drop=True)
    _save_cached_benchmark(merged, cache_dir=cache_dir, ticker=ticker, logger=logger)
    return merged, "fetched"
