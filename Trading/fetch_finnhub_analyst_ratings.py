from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from typing import Callable, Literal

import pandas as pd
import requests

FINNHUB_RECOMMENDATION_URL = "https://finnhub.io/api/v1/stock/recommendation"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)


def resolve_input_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    local = os.path.abspath(path)
    if os.path.exists(local):
        return local
    alt = os.path.join(PROJECT_ROOT, path)
    if os.path.exists(alt):
        return alt
    return local


def resolve_output_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_ROOT, path)


def load_universe_tickers(path: str, ticker_column: str) -> list[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Universe CSV not found: {path}")
    frame = pd.read_csv(path)
    if ticker_column not in frame.columns:
        raise ValueError(f"Ticker column '{ticker_column}' not found in {path}")
    tickers = frame[ticker_column].astype(str).str.upper().str.strip()
    tickers = [ticker for ticker in tickers if ticker]
    return list(dict.fromkeys(tickers))


def load_error_tickers(path: str) -> list[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Errors CSV not found: {path}")
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return []
    if frame.empty:
        return []
    if "ticker" not in frame.columns:
        raise ValueError(f"Errors CSV must include a 'ticker' column: {path}")
    tickers = frame["ticker"].astype(str).str.upper().str.strip()
    tickers = [ticker for ticker in tickers if ticker]
    return list(dict.fromkeys(tickers))


def months_cutoff_start(months_back: int) -> pd.Timestamp | None:
    if months_back <= 0:
        return None
    now_utc = pd.Timestamp.now(tz="UTC").tz_localize(None)
    this_month = now_utc.normalize().replace(day=1)
    return this_month - pd.DateOffset(months=max(0, months_back - 1))


def filter_rows_by_months(raw_rows: list[dict], months_back: int) -> list[dict]:
    cutoff = months_cutoff_start(months_back)
    if cutoff is None:
        return raw_rows
    out: list[dict] = []
    for row in raw_rows:
        period = pd.to_datetime(row.get("period"), errors="coerce")
        if pd.isna(period):
            continue
        if pd.Timestamp(period).normalize() >= cutoff:
            out.append(row)
    return out


def is_transient_error_message(message: str) -> bool:
    msg = str(message).lower()
    patterns = [
        "network error",
        "timed out",
        "timeout",
        "rate limit",
        "http 500",
        "http 502",
        "http 503",
        "http 504",
        "temporar",
        "connection aborted",
        "connection reset",
    ]
    return any(pattern in msg for pattern in patterns)


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


def fetch_recommendation_rows(
    session: requests.Session,
    symbol: str,
    api_key: str,
    retries: int = 3,
    timeout: int = 20,
    min_wait_seconds: float = 30.0,
    max_rate_limit_waits: int = 0,
    logger: Callable[[str], None] | None = None,
) -> list[dict]:
    params = {"symbol": symbol, "token": api_key}
    attempts = 0
    rate_wait_count = 0

    while True:
        attempts += 1
        try:
            response = session.get(FINNHUB_RECOMMENDATION_URL, params=params, timeout=timeout)
        except requests.RequestException as exc:
            if attempts >= max(1, retries):
                raise RuntimeError(f"Network error for {symbol}: {exc}") from exc
            sleep_seconds = min(10.0, float(attempts))
            if logger is not None:
                logger(
                    f"{symbol}: network error ({exc}). Retrying in {sleep_seconds:.0f}s "
                    f"[attempt {attempts}/{retries}]"
                )
            time.sleep(sleep_seconds)
            continue

        if is_rate_limited_response(response):
            rate_wait_count += 1
            if max_rate_limit_waits > 0 and rate_wait_count > max_rate_limit_waits:
                raise RuntimeError(
                    f"Rate limit did not clear for {symbol} after {max_rate_limit_waits} waits."
                )
            wait_seconds = rate_limit_wait_seconds(
                response=response,
                min_wait_seconds=min_wait_seconds,
            )
            if logger is not None:
                logger(
                    f"{symbol}: rate limited (HTTP {response.status_code}). "
                    f"Waiting {wait_seconds:.0f}s then retrying same ticker."
                )
            time.sleep(wait_seconds)
            continue

        if response.status_code >= 500 and attempts < max(1, retries):
            sleep_seconds = min(10.0, float(attempts))
            if logger is not None:
                logger(
                    f"{symbol}: Finnhub server error {response.status_code}. "
                    f"Retrying in {sleep_seconds:.0f}s [attempt {attempts}/{retries}]"
                )
            time.sleep(sleep_seconds)
            continue

        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code} for {symbol}: {response.text[:200]}")

        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected payload for {symbol}: {payload}")
        return payload

Mode = Literal["normal", "errors"]


def select_tickers(
    mode: Mode,
    universe_csv: str,
    ticker_column: str,
    errors_source_csv: str,
) -> list[str]:
    if mode == "normal":
        return load_universe_tickers(universe_csv, ticker_column)
    return load_error_tickers(errors_source_csv)


def normalize_rows(symbol: str, raw_rows: list[dict], fetched_at: str) -> list[dict]:
    out: list[dict] = []
    for row in raw_rows:
        period = row.get("period")
        if not period:
            continue
        strong_buy = int(row.get("strongBuy", 0) or 0)
        buy = int(row.get("buy", 0) or 0)
        hold = int(row.get("hold", 0) or 0)
        sell = int(row.get("sell", 0) or 0)
        strong_sell = int(row.get("strongSell", 0) or 0)
        total = strong_buy + buy + hold + sell + strong_sell
        weighted = 2 * strong_buy + 1 * buy + 0 * hold - 1 * sell - 2 * strong_sell
        net_score = (weighted / total) if total > 0 else 0.0

        out.append(
            {
                "ticker": symbol,
                "period": period,
                "strongBuy": strong_buy,
                "buy": buy,
                "hold": hold,
                "sell": sell,
                "strongSell": strong_sell,
                "total_ratings": total,
                "net_score": float(net_score),
                "fetched_at_utc": fetched_at,
            }
        )
    return out


def merge_with_existing(existing_path: str, new_data: pd.DataFrame) -> pd.DataFrame:
    if not os.path.exists(existing_path):
        return new_data
    existing = pd.read_csv(existing_path)
    merged = pd.concat([existing, new_data], ignore_index=True)
    merged = merged.drop_duplicates(subset=["ticker", "period"], keep="last")
    return merged


def run_fetch(
    api_key: str,
    mode: Mode = "normal",
    universe_csv: str = "data_out/top_1000_tickers.csv",
    ticker_column: str = "ticker",
    errors_source_csv: str = "data_out/finnhub_analyst_ratings_errors.csv",
    out_csv: str = "data_out/finnhub_analyst_ratings.csv",
    out_parquet: str = "data_out/finnhub_analyst_ratings.parquet",
    errors_csv: str = "data_out/finnhub_analyst_ratings_errors.csv",
    coverage_csv: str = "data_out/finnhub_analyst_ratings_coverage.csv",
    sleep_sec: float = 0.15,
    retries: int = 3,
    timeout: int = 20,
    min_rate_limit_wait_sec: float = 30.0,
    max_rate_limit_waits: int = 0,
    max_symbol_attempts: int = 5,
    retry_round_cooldown_sec: float = 10.0,
    months_back: int = 0,
    limit: int = 0,
    overwrite: bool = False,
    logger: Callable[[str], None] | None = print,
) -> dict[str, object]:
    if not api_key or not str(api_key).strip():
        raise ValueError("Missing API key. Use --api-key or set FINNHUB_API_KEY.")

    universe_csv = resolve_input_path(universe_csv)
    errors_source_csv = resolve_input_path(errors_source_csv)
    out_csv = resolve_output_path(out_csv)
    out_parquet = resolve_output_path(out_parquet)
    errors_csv = resolve_output_path(errors_csv)
    coverage_csv = resolve_output_path(coverage_csv)
    os.makedirs(os.path.dirname(os.path.abspath(out_csv)), exist_ok=True)

    tickers = select_tickers(
        mode=mode,
        universe_csv=universe_csv,
        ticker_column=ticker_column,
        errors_source_csv=errors_source_csv,
    )
    if limit and limit > 0:
        tickers = tickers[:limit]

    if logger is not None:
        if mode == "normal":
            logger(f"Mode: normal | loaded {len(tickers)} tickers from {universe_csv}")
        else:
            logger(f"Mode: retry errors | loaded {len(tickers)} tickers from {errors_source_csv}")
        logger(
            "Fetching Finnhub stock/recommendation data... "
            f"top_n={limit if limit > 0 else len(tickers)}, months_back={months_back if months_back > 0 else 'all'}"
        )

    session = requests.Session()
    all_rows: list[dict] = []
    errors: list[dict] = []
    coverage_rows: list[dict] = []
    attempt_counts: dict[str, int] = {ticker: 0 for ticker in tickers}
    pending: list[str] = list(tickers)
    processed = 0
    total = len(tickers)
    round_index = 1

    while pending:
        if logger is not None:
            logger(f"Retry round {round_index}: pending tickers={len(pending)}")
        next_pending: list[str] = []

        for symbol in pending:
            attempt_counts[symbol] += 1
            processed += 1
            try:
                payload = fetch_recommendation_rows(
                    session=session,
                    symbol=symbol,
                    api_key=api_key,
                    retries=max(1, retries),
                    timeout=timeout,
                    min_wait_seconds=min_rate_limit_wait_sec,
                    max_rate_limit_waits=max(0, max_rate_limit_waits),
                    logger=logger,
                )
                fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                rows = normalize_rows(symbol=symbol, raw_rows=payload, fetched_at=fetched_at)
                rows = filter_rows_by_months(rows, months_back=months_back)
                all_rows.extend(rows)

                months_returned = (
                    len(
                        {
                            str(pd.to_datetime(row.get("period"), errors="coerce").date())
                            for row in rows
                            if pd.notna(pd.to_datetime(row.get("period"), errors="coerce"))
                        }
                    )
                    if rows
                    else 0
                )
                coverage_rows.append(
                    {
                        "ticker": symbol,
                        "months_requested": int(months_back),
                        "months_returned": int(months_returned),
                        "coverage_complete": bool(months_back <= 0 or months_returned >= months_back),
                    }
                )

                if logger is not None:
                    logger(
                        f"[{processed}] {symbol}: {len(rows)} rows "
                        f"(attempt {attempt_counts[symbol]})"
                    )
            except Exception as exc:  # noqa: BLE001
                error_text = str(exc)
                transient = is_transient_error_message(error_text)
                can_retry = transient and attempt_counts[symbol] < max(1, max_symbol_attempts)

                if can_retry:
                    next_pending.append(symbol)
                    if logger is not None:
                        logger(
                            f"[{processed}] {symbol}: transient error -> {error_text}. "
                            f"Will retry (attempt {attempt_counts[symbol]}/{max_symbol_attempts})."
                        )
                else:
                    errors.append({"ticker": symbol, "error": error_text})
                    if logger is not None:
                        logger(f"[{processed}] {symbol}: ERROR -> {error_text}")

            if sleep_sec > 0:
                time.sleep(float(sleep_sec))

        pending = next_pending
        round_index += 1
        if pending and retry_round_cooldown_sec > 0:
            if logger is not None:
                logger(
                    f"Round cooldown: waiting {retry_round_cooldown_sec:.0f}s before retrying "
                    f"{len(pending)} ticker(s)."
                )
            time.sleep(float(retry_round_cooldown_sec))

    frame = pd.DataFrame(all_rows)
    wrote_main_output = False
    if not frame.empty:
        frame["period"] = pd.to_datetime(frame["period"], errors="coerce")
        frame = frame.dropna(subset=["period"]).copy()
        frame = frame.sort_values(["ticker", "period"]).reset_index(drop=True)
        frame["period"] = frame["period"].dt.strftime("%Y-%m-%d")

        if not overwrite:
            frame = merge_with_existing(out_csv, frame)
            frame["period"] = pd.to_datetime(frame["period"], errors="coerce")
            frame = (
                frame.dropna(subset=["period"])
                .sort_values(["ticker", "period"])
                .reset_index(drop=True)
            )
            frame["period"] = frame["period"].dt.strftime("%Y-%m-%d")

        frame.to_csv(out_csv, index=False)
        wrote_main_output = True
        if logger is not None:
            logger(f"Saved CSV: {out_csv} ({len(frame):,} rows)")

        try:
            parquet_frame = frame.copy()
            parquet_frame["period"] = pd.to_datetime(parquet_frame["period"], errors="coerce")
            parquet_frame.to_parquet(out_parquet, index=False)
            if logger is not None:
                logger(f"Saved Parquet: {out_parquet}")
        except Exception as exc:  # noqa: BLE001
            if logger is not None:
                logger(f"Parquet save skipped ({exc}). CSV already saved.")
    elif logger is not None:
        logger("No rating rows fetched this run. Main ratings output was not modified.")

    err_df = pd.DataFrame(errors, columns=["ticker", "error"])
    err_df.to_csv(errors_csv, index=False)
    if logger is not None:
        logger(f"Saved errors: {errors_csv} ({len(err_df)} tickers)")

    coverage_df = pd.DataFrame(
        coverage_rows,
        columns=["ticker", "months_requested", "months_returned", "coverage_complete"],
    )
    coverage_df.to_csv(coverage_csv, index=False)
    if logger is not None:
        if not coverage_df.empty:
            incomplete = int((~coverage_df["coverage_complete"]).sum())
            logger(
                f"Saved coverage report: {coverage_csv} | incomplete requested coverage: {incomplete}"
            )
        else:
            logger(f"Saved coverage report: {coverage_csv} (0 rows)")

    requested = len(tickers)
    failed = len(err_df)
    ok_tickers = requested - failed
    if logger is not None:
        logger(f"Done. Success tickers: {ok_tickers}, Failed tickers: {failed}")

    return {
        "mode": mode,
        "requested_tickers": requested,
        "success_tickers": ok_tickers,
        "failed_tickers": failed,
        "output_csv": out_csv,
        "output_parquet": out_parquet,
        "errors_csv": errors_csv,
        "coverage_csv": coverage_csv,
        "wrote_main_output": wrote_main_output,
        "ratings_rows": int(len(frame)) if not frame.empty else 0,
        "errors_df": err_df,
        "coverage_df": coverage_df,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch analyst recommendation trends from Finnhub and save to data_out."
    )
    parser.add_argument("--api-key", default=os.getenv("FINNHUB_API_KEY", "").strip())
    parser.add_argument("--mode", choices=["normal", "errors"], default="normal")
    parser.add_argument("--universe-csv", default="data_out/top_1000_tickers.csv")
    parser.add_argument("--ticker-column", default="ticker")
    parser.add_argument(
        "--errors-source-csv",
        default="data_out/finnhub_analyst_ratings_errors.csv",
        help="Used when --mode errors.",
    )
    parser.add_argument("--out-csv", default="data_out/finnhub_analyst_ratings.csv")
    parser.add_argument("--out-parquet", default="data_out/finnhub_analyst_ratings.parquet")
    parser.add_argument("--errors-csv", default="data_out/finnhub_analyst_ratings_errors.csv")
    parser.add_argument("--coverage-csv", default="data_out/finnhub_analyst_ratings_coverage.csv")
    parser.add_argument("--sleep-sec", type=float, default=0.15)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--min-rate-limit-wait-sec", type=float, default=30.0)
    parser.add_argument(
        "--max-rate-limit-waits",
        type=int,
        default=0,
        help="0 means unlimited rate-limit waits per ticker.",
    )
    parser.add_argument("--max-symbol-attempts", type=int, default=5)
    parser.add_argument("--retry-round-cooldown-sec", type=float, default=10.0)
    parser.add_argument("--months-back", type=int, default=0, help="0 means keep all returned months.")
    parser.add_argument("--limit", type=int, default=0, help="0 means all selected tickers.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    run_fetch(
        api_key=args.api_key,
        mode=args.mode,
        universe_csv=args.universe_csv,
        ticker_column=args.ticker_column,
        errors_source_csv=args.errors_source_csv,
        out_csv=args.out_csv,
        out_parquet=args.out_parquet,
        errors_csv=args.errors_csv,
        coverage_csv=args.coverage_csv,
        sleep_sec=args.sleep_sec,
        retries=args.retries,
        timeout=args.timeout,
        min_rate_limit_wait_sec=args.min_rate_limit_wait_sec,
        max_rate_limit_waits=args.max_rate_limit_waits,
        max_symbol_attempts=args.max_symbol_attempts,
        retry_round_cooldown_sec=args.retry_round_cooldown_sec,
        months_back=args.months_back,
        limit=args.limit,
        overwrite=args.overwrite,
        logger=print,
    )


if __name__ == "__main__":
    main()
