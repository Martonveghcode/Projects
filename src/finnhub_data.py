from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import requests

FINNHUB_API_BASE = "https://finnhub.io/api/v1"
RATINGS_COLUMNS = [
    "ticker",
    "period",
    "strongBuy",
    "buy",
    "hold",
    "sell",
    "strongSell",
    "total_ratings",
    "net_score",
    "fetched_at_utc",
]
PERF_COLUMNS = ["ticker", "asof_date", "monthly_return", "status", "fetched_at_utc", "error"]


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if logger is not None:
        logger(message)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_rate_limited_response(response: requests.Response) -> bool:
    if response.status_code == 429:
        return True
    if response.status_code == 403:
        text = response.text.lower()
        if "rate" in text or "limit" in text or "too many" in text:
            return True
    return False


def rate_limit_wait_seconds(response: requests.Response, min_wait_seconds: float) -> float:
    wait_seconds = float(max(0.0, min_wait_seconds))

    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            wait_seconds = max(wait_seconds, float(retry_after))
        except ValueError:
            pass

    for header_name in ["X-RateLimit-Reset", "x-ratelimit-reset", "RateLimit-Reset"]:
        reset_value = response.headers.get(header_name)
        if not reset_value:
            continue
        try:
            reset_epoch = float(reset_value)
            until_reset = max(0.0, reset_epoch - time.time())
            wait_seconds = max(wait_seconds, until_reset)
            break
        except ValueError:
            continue

    return wait_seconds


def _finnhub_get_json(
    session: requests.Session,
    endpoint: str,
    params: dict[str, object],
    timeout: int,
    retries: int,
    min_rate_limit_wait_sec: float,
    max_rate_limit_waits: int,
    logger: Callable[[str], None] | None = None,
) -> object:
    attempts = 0
    rate_waits = 0
    url = f"{FINNHUB_API_BASE.rstrip('/')}/{endpoint.lstrip('/')}"

    while True:
        attempts += 1
        try:
            response = session.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            if attempts >= max(1, retries):
                raise RuntimeError(f"Network error after {attempts} attempts: {exc}") from exc
            sleep_seconds = min(10.0, float(attempts))
            _log(
                logger,
                f"{endpoint}: network error ({exc}). Retrying in {sleep_seconds:.0f}s.",
            )
            time.sleep(sleep_seconds)
            continue

        if is_rate_limited_response(response):
            rate_waits += 1
            if max_rate_limit_waits > 0 and rate_waits > max_rate_limit_waits:
                raise RuntimeError(
                    f"Rate limit did not clear for {endpoint} after {max_rate_limit_waits} waits."
                )
            wait_seconds = rate_limit_wait_seconds(
                response=response,
                min_wait_seconds=min_rate_limit_wait_sec,
            )
            _log(
                logger,
                f"{endpoint}: rate limited (HTTP {response.status_code}). Waiting {wait_seconds:.0f}s.",
            )
            time.sleep(wait_seconds)
            continue

        if response.status_code >= 500 and attempts < max(1, retries):
            sleep_seconds = min(10.0, float(attempts))
            _log(
                logger,
                (
                    f"{endpoint}: server error {response.status_code}. "
                    f"Retrying in {sleep_seconds:.0f}s."
                ),
            )
            time.sleep(sleep_seconds)
            continue

        if response.status_code >= 400:
            raise RuntimeError(
                f"HTTP {response.status_code} for {endpoint}: {response.text[:200]}"
            )

        return response.json()


def _months_cutoff_start(reference_end: pd.Timestamp, months_back: int) -> pd.Timestamp | None:
    if months_back <= 0:
        return None
    this_month = pd.Timestamp(reference_end).normalize().replace(day=1)
    return this_month - pd.DateOffset(months=max(0, months_back - 1))


def _normalize_ratings_rows(ticker: str, payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected Finnhub recommendation payload for {ticker}: {payload}")

    fetched_at = _now_utc_iso()
    rows: list[dict[str, object]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        period = row.get("period")
        if not period:
            continue
        strong_buy = int(row.get("strongBuy", 0) or 0)
        buy = int(row.get("buy", 0) or 0)
        hold = int(row.get("hold", 0) or 0)
        sell = int(row.get("sell", 0) or 0)
        strong_sell = int(row.get("strongSell", 0) or 0)
        total = strong_buy + buy + hold + sell + strong_sell
        weighted = 2 * strong_buy + buy - sell - 2 * strong_sell
        net_score = float(weighted / total) if total > 0 else 0.0

        rows.append(
            {
                "ticker": str(ticker).upper().strip(),
                "period": period,
                "strongBuy": strong_buy,
                "buy": buy,
                "hold": hold,
                "sell": sell,
                "strongSell": strong_sell,
                "total_ratings": total,
                "net_score": net_score,
                "fetched_at_utc": fetched_at,
            }
        )
    return rows


def _normalize_ratings_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=RATINGS_COLUMNS)

    out = frame.copy()
    for column in RATINGS_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    out = out[RATINGS_COLUMNS].copy()
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["period"] = pd.to_datetime(out["period"], errors="coerce")
    for col in ["strongBuy", "buy", "hold", "sell", "strongSell", "total_ratings", "net_score"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["ticker", "period"]).reset_index(drop=True)
    out = out.sort_values(["ticker", "period"]).drop_duplicates(
        subset=["ticker", "period"], keep="last"
    )
    return out.reset_index(drop=True)


def load_finnhub_ratings_cache(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=RATINGS_COLUMNS)
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=RATINGS_COLUMNS)
    return _normalize_ratings_frame(frame)


def save_finnhub_ratings_cache(frame: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    out = _normalize_ratings_frame(frame)
    out["period"] = pd.to_datetime(out["period"], errors="coerce").dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)


def ensure_finnhub_ratings_cache(
    universe: Iterable[str],
    api_key: str,
    cache_path: str,
    start_date: str | pd.Timestamp,
    end_date: str | pd.Timestamp,
    months_back: int = 0,
    refresh: bool = False,
    fetch_missing: bool = True,
    sleep_seconds: float = 0.15,
    timeout: int = 20,
    retries: int = 3,
    min_rate_limit_wait_sec: float = 30.0,
    max_rate_limit_waits: int = 0,
    max_symbol_attempts: int = 5,
    retry_round_cooldown_sec: float = 10.0,
    logger: Callable[[str], None] | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if not api_key or not str(api_key).strip():
        raise ValueError("Finnhub API key is required for Finnhub analyst ratings.")

    tickers = [str(t).upper().strip() for t in universe if str(t).strip()]
    tickers = list(dict.fromkeys(tickers))
    cached = pd.DataFrame(columns=RATINGS_COLUMNS) if refresh else load_finnhub_ratings_cache(cache_path)

    start_ts = pd.Timestamp(start_date).normalize()
    end_ts = pd.Timestamp(end_date).normalize()
    cutoff = _months_cutoff_start(reference_end=end_ts, months_back=months_back)
    if cutoff is not None:
        start_ts = max(start_ts, cutoff)

    end_month = end_ts.replace(day=1)
    have_latest = (
        cached.groupby("ticker")["period"].max().to_dict() if not cached.empty else {}
    )

    pending: list[str] = []
    for ticker in tickers:
        latest = have_latest.get(ticker)
        if latest is None or pd.Timestamp(latest).normalize() < end_month:
            pending.append(ticker)
    pending_all = list(pending)
    if not fetch_missing:
        pending = []

    _log(
        logger,
        (
            f"Finnhub ratings cache: {cache_path} | universe={len(tickers)} | "
            f"pending fetch={len(pending_all)} | fetch_missing={bool(fetch_missing)}"
        ),
    )
    if pending_all and not fetch_missing:
        _log(
            logger,
            "Auto-fetch missing Finnhub ratings is disabled; using cached ratings only for this run.",
        )

    session = requests.Session()
    fetched_rows: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    attempt_counts: dict[str, int] = {ticker: 0 for ticker in pending}
    round_index = 1

    while pending:
        _log(logger, f"Finnhub ratings retry round {round_index}: pending={len(pending)}")
        next_pending: list[str] = []
        for idx, ticker in enumerate(pending, start=1):
            attempt_counts[ticker] += 1
            try:
                payload = _finnhub_get_json(
                    session=session,
                    endpoint="stock/recommendation",
                    params={"symbol": ticker, "token": api_key},
                    timeout=timeout,
                    retries=retries,
                    min_rate_limit_wait_sec=min_rate_limit_wait_sec,
                    max_rate_limit_waits=max_rate_limit_waits,
                    logger=logger,
                )
                rows = _normalize_ratings_rows(ticker=ticker, payload=payload)
                fetched_rows.extend(rows)
                _log(
                    logger,
                    f"Finnhub ratings [{idx}/{len(pending)}] {ticker}: {len(rows)} rows",
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                transient = any(
                    token in message.lower()
                    for token in [
                        "rate limit",
                        "network",
                        "timeout",
                        "timed out",
                        "http 500",
                        "http 502",
                        "http 503",
                        "http 504",
                    ]
                )
                if transient and attempt_counts[ticker] < max(1, max_symbol_attempts):
                    next_pending.append(ticker)
                    _log(
                        logger,
                        (
                            f"Finnhub ratings {ticker}: transient error ({message}). "
                            f"retry {attempt_counts[ticker]}/{max_symbol_attempts}"
                        ),
                    )
                else:
                    errors.append({"ticker": ticker, "error": message})
                    _log(logger, f"Finnhub ratings {ticker}: ERROR {message}")
            if sleep_seconds > 0:
                time.sleep(float(sleep_seconds))

        pending = next_pending
        round_index += 1
        if pending and retry_round_cooldown_sec > 0:
            _log(
                logger,
                (
                    f"Finnhub ratings cooldown: waiting {retry_round_cooldown_sec:.0f}s "
                    f"before next retry round."
                ),
            )
            time.sleep(float(retry_round_cooldown_sec))

    if fetched_rows:
        fetched_df = _normalize_ratings_frame(pd.DataFrame(fetched_rows))
        cached = (
            fetched_df
            if cached.empty
            else _normalize_ratings_frame(pd.concat([cached, fetched_df], ignore_index=True))
        )
        save_finnhub_ratings_cache(cached, path=cache_path)
        _log(logger, f"Saved Finnhub ratings cache with {len(cached):,} rows.")
    elif refresh:
        save_finnhub_ratings_cache(cached, path=cache_path)

    selected = cached[cached["ticker"].isin(tickers)].copy()
    in_range = selected[
        (selected["period"] <= end_ts) & (selected["period"] >= start_ts - pd.Timedelta(days=370))
    ].copy()
    rows_by_ticker = selected.groupby("ticker").size().to_dict() if not selected.empty else {}
    missing = [ticker for ticker in tickers if rows_by_ticker.get(ticker, 0) == 0]
    period_min = str(selected["period"].min().date()) if not selected.empty else None
    period_max = str(selected["period"].max().date()) if not selected.empty else None

    errors_df = pd.DataFrame(errors, columns=["ticker", "error"])
    stats = {
        "source": "finnhub_ratings",
        "requested_tickers": len(tickers),
        "pending_tickers_in_cache": len(pending_all),
        "missing_fetch_enabled": bool(fetch_missing),
        "fetched_tickers": len({row["ticker"] for row in fetched_rows}),
        "cache_rows_total": int(len(cached)),
        "cache_rows_selected": int(len(selected)),
        "rows_in_backtest_window": int(len(in_range)),
        "period_min": period_min,
        "period_max": period_max,
        "tickers_without_ratings": len(missing),
        "missing_ratings_tickers": missing,
        "errors_df": errors_df,
    }
    return selected.reset_index(drop=True), stats


def _normalize_perf_cache(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=PERF_COLUMNS)
    out = frame.copy()
    for column in PERF_COLUMNS:
        if column not in out.columns:
            out[column] = np.nan
    out = out[PERF_COLUMNS].copy()
    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["asof_date"] = pd.to_datetime(out["asof_date"], errors="coerce")
    out["monthly_return"] = pd.to_numeric(out["monthly_return"], errors="coerce")
    out = out.dropna(subset=["ticker", "asof_date"]).reset_index(drop=True)
    out = out.sort_values(["asof_date", "ticker"]).drop_duplicates(
        subset=["ticker", "asof_date"], keep="last"
    )
    return out.reset_index(drop=True)


def _load_perf_cache(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=PERF_COLUMNS)
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=PERF_COLUMNS)
    return _normalize_perf_cache(frame)


def _save_perf_cache(frame: pd.DataFrame, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    out = _normalize_perf_cache(frame)
    out["asof_date"] = pd.to_datetime(out["asof_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False)


def _fetch_monthly_return_for_ticker(
    session: requests.Session,
    ticker: str,
    api_key: str,
    asof_date: pd.Timestamp,
    window_days: int,
    timeout: int,
    retries: int,
    min_rate_limit_wait_sec: float,
    max_rate_limit_waits: int,
    logger: Callable[[str], None] | None = None,
) -> tuple[float, str]:
    metric_payload = _finnhub_get_json(
        session=session,
        endpoint="stock/metric",
        params={
            "symbol": ticker,
            "metric": "all",
            "token": api_key,
        },
        timeout=timeout,
        retries=retries,
        min_rate_limit_wait_sec=min_rate_limit_wait_sec,
        max_rate_limit_waits=max_rate_limit_waits,
        logger=logger,
    )
    if isinstance(metric_payload, dict):
        metric = metric_payload.get("metric")
        if isinstance(metric, dict):
            mtd = metric.get("monthToDatePriceReturnDaily")
            if mtd is not None and np.isfinite(float(mtd)):
                # Finnhub metric returns percentages (e.g. 2.5 means +2.5%).
                return float(mtd) / 100.0, "ok_mtd_metric"
            q13 = metric.get("13WeekPriceReturnDaily")
            if q13 is not None and np.isfinite(float(q13)):
                # Fallback proxy: quarterly return / 3.
                return (float(q13) / 100.0) / 3.0, "ok_13w_proxy"

    # Final fallback: use current daily return from quote endpoint.
    quote_payload = _finnhub_get_json(
        session=session,
        endpoint="quote",
        params={
            "symbol": ticker,
            "token": api_key,
        },
        timeout=timeout,
        retries=retries,
        min_rate_limit_wait_sec=min_rate_limit_wait_sec,
        max_rate_limit_waits=max_rate_limit_waits,
        logger=logger,
    )
    if not isinstance(quote_payload, dict):
        raise RuntimeError(f"Unexpected quote payload for {ticker}: {quote_payload}")
    current = quote_payload.get("c")
    prev_close = quote_payload.get("pc")
    if current is None or prev_close is None:
        raise RuntimeError(f"No quote data for {ticker}.")
    current = float(current)
    prev_close = float(prev_close)
    if not np.isfinite(current) or not np.isfinite(prev_close) or prev_close <= 0:
        raise RuntimeError(f"Invalid quote data for {ticker}.")
    return float(current / prev_close - 1.0), "ok_daily_quote_proxy"


def build_finnhub_universe_by_monthly_performance(
    candidate_tickers: Iterable[str],
    api_key: str,
    asof_date: str | pd.Timestamp,
    top_n: int,
    cache_path: str,
    refresh: bool = False,
    window_days: int = 31,
    sleep_seconds: float = 0.15,
    timeout: int = 20,
    retries: int = 3,
    min_rate_limit_wait_sec: float = 30.0,
    max_rate_limit_waits: int = 0,
    max_symbol_attempts: int = 3,
    retry_round_cooldown_sec: float = 10.0,
    logger: Callable[[str], None] | None = None,
) -> tuple[list[str], pd.DataFrame, dict[str, object]]:
    if not api_key or not str(api_key).strip():
        raise ValueError("Finnhub API key is required for Finnhub universe selection.")
    if top_n <= 0:
        raise ValueError("top_n must be > 0 for Finnhub universe selection.")

    tickers = [str(t).upper().strip() for t in candidate_tickers if str(t).strip()]
    tickers = list(dict.fromkeys(tickers))
    asof_ts = pd.Timestamp(asof_date).normalize()

    cache = pd.DataFrame(columns=PERF_COLUMNS) if refresh else _load_perf_cache(cache_path)
    asof_rows = cache[cache["asof_date"] == asof_ts].copy() if not cache.empty else pd.DataFrame(columns=PERF_COLUMNS)
    have = set(asof_rows["ticker"].unique()) if not asof_rows.empty else set()
    pending = [ticker for ticker in tickers if ticker not in have]

    _log(
        logger,
        (
            f"Finnhub universe perf cache: {cache_path} | candidates={len(tickers)} | "
            f"cached_for_asof={len(have)} | pending={len(pending)}"
        ),
    )

    session = requests.Session()
    fetched_rows: list[dict[str, object]] = []
    attempt_counts: dict[str, int] = {ticker: 0 for ticker in pending}
    errors: list[dict[str, str]] = []
    round_index = 1

    while pending:
        _log(logger, f"Finnhub universe retry round {round_index}: pending={len(pending)}")
        next_pending: list[str] = []
        for idx, ticker in enumerate(pending, start=1):
            attempt_counts[ticker] += 1
            try:
                monthly_return, status = _fetch_monthly_return_for_ticker(
                    session=session,
                    ticker=ticker,
                    api_key=api_key,
                    asof_date=asof_ts,
                    window_days=window_days,
                    timeout=timeout,
                    retries=retries,
                    min_rate_limit_wait_sec=min_rate_limit_wait_sec,
                    max_rate_limit_waits=max_rate_limit_waits,
                    logger=logger,
                )
                fetched_rows.append(
                    {
                        "ticker": ticker,
                        "asof_date": asof_ts,
                        "monthly_return": monthly_return,
                        "status": status,
                        "fetched_at_utc": _now_utc_iso(),
                        "error": "",
                    }
                )
                _log(
                    logger,
                    f"Finnhub universe [{idx}/{len(pending)}] {ticker}: {monthly_return:.4f}",
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                transient = any(
                    token in message.lower()
                    for token in [
                        "rate limit",
                        "network",
                        "timeout",
                        "timed out",
                        "http 500",
                        "http 502",
                        "http 503",
                        "http 504",
                    ]
                )
                if transient and attempt_counts[ticker] < max(1, max_symbol_attempts):
                    next_pending.append(ticker)
                    _log(
                        logger,
                        (
                            f"Finnhub universe {ticker}: transient error ({message}). "
                            f"retry {attempt_counts[ticker]}/{max_symbol_attempts}"
                        ),
                    )
                else:
                    fetched_rows.append(
                        {
                            "ticker": ticker,
                            "asof_date": asof_ts,
                            "monthly_return": np.nan,
                            "status": "error",
                            "fetched_at_utc": _now_utc_iso(),
                            "error": message,
                        }
                    )
                    errors.append({"ticker": ticker, "error": message})
                    _log(logger, f"Finnhub universe {ticker}: ERROR {message}")

            if sleep_seconds > 0:
                time.sleep(float(sleep_seconds))

        pending = next_pending
        round_index += 1
        if pending and retry_round_cooldown_sec > 0:
            _log(
                logger,
                (
                    f"Finnhub universe cooldown: waiting {retry_round_cooldown_sec:.0f}s "
                    f"before next retry round."
                ),
            )
            time.sleep(float(retry_round_cooldown_sec))

    if fetched_rows:
        fetched_df = _normalize_perf_cache(pd.DataFrame(fetched_rows))
        cache = (
            fetched_df
            if cache.empty
            else _normalize_perf_cache(pd.concat([cache, fetched_df], ignore_index=True))
        )
        _save_perf_cache(cache, cache_path)
        _log(logger, f"Saved Finnhub universe perf cache with {len(cache):,} rows.")
    elif refresh:
        _save_perf_cache(cache, cache_path)

    asof_rows = cache[cache["asof_date"] == asof_ts].copy()
    ranked = asof_rows[
        (asof_rows["status"].astype(str).str.startswith("ok"))
        & (asof_rows["monthly_return"].notna())
    ].copy()
    ranked = ranked.sort_values("monthly_return", ascending=False).reset_index(drop=True)
    universe = ranked.head(top_n)["ticker"].astype(str).tolist()

    stats = {
        "source": "finnhub_monthly_performance",
        "asof_date": str(asof_ts.date()),
        "candidate_tickers": len(tickers),
        "rankable_tickers": int(len(ranked)),
        "selected_tickers": len(universe),
        "errors_df": pd.DataFrame(errors, columns=["ticker", "error"]),
        "cache_path": cache_path,
    }
    return universe, ranked, stats
