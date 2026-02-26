from __future__ import annotations

import os
import re
import time
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import yfinance as yf

EVENT_COLUMNS = ["ticker", "date", "action", "fromGrade", "toGrade", "firm"]

DEFAULT_GRADE_MAPPING_RULES = [
    {"phrase": "strong buy", "score": 2},
    {"phrase": "conviction buy", "score": 2},
    {"phrase": "top pick", "score": 2},
    {"phrase": "market outperform", "score": 2},
    {"phrase": "overweight", "score": 2},
    {"phrase": "outperform", "score": 2},
    {"phrase": "add", "score": 2},
    {"phrase": "strong sell", "score": -2},
    {"phrase": "underperform", "score": -1},
    {"phrase": "underweight", "score": -1},
    {"phrase": "reduce", "score": -1},
    {"phrase": "negative", "score": -1},
    {"phrase": "sell", "score": -1},
    {"phrase": "hold", "score": 0},
    {"phrase": "neutral", "score": 0},
    {"phrase": "equal weight", "score": 0},
    {"phrase": "market perform", "score": 0},
    {"phrase": "in-line", "score": 0},
    {"phrase": "inline", "score": 0},
    {"phrase": "perform", "score": 0},
    {"phrase": "buy", "score": 1},
    {"phrase": "accumulate", "score": 1},
    {"phrase": "positive", "score": 1},
]

DEFAULT_ACTION_WEIGHTS = {
    "upgrade": 1.0,
    "downgrade": -1.0,
    "initiat": 0.25,
    "default": 0.0,
}


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if logger is not None:
        logger(message)


def normalize_text(value: object) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def grade_to_score(
    grade_text: object,
    mapping_rules: list[dict[str, object]] | None = None,
) -> int | None:
    rules = mapping_rules if mapping_rules is not None else DEFAULT_GRADE_MAPPING_RULES
    normalized_grade = normalize_text(grade_text)
    if not normalized_grade:
        return None

    for rule in rules:
        phrase = normalize_text(rule.get("phrase", ""))
        if not phrase:
            continue
        if phrase in normalized_grade:
            try:
                return int(rule.get("score", 0))
            except (TypeError, ValueError):
                continue
    return None


def action_weight(
    action_text: object,
    action_weights: dict[str, float] | None = None,
) -> float:
    weights = action_weights if action_weights is not None else DEFAULT_ACTION_WEIGHTS
    normalized_action = normalize_text(action_text)
    if not normalized_action:
        return float(weights.get("default", 0.0))
    for key, weight in weights.items():
        if key == "default":
            continue
        if key in normalized_action:
            return float(weight)
    return float(weights.get("default", 0.0))


def event_signal_value(
    row: pd.Series,
    mapping_rules: list[dict[str, object]] | None = None,
    action_weights: dict[str, float] | None = None,
) -> float:
    from_score = grade_to_score(row.get("fromGrade"), mapping_rules=mapping_rules)
    to_score = grade_to_score(row.get("toGrade"), mapping_rules=mapping_rules)
    if from_score is not None and to_score is not None:
        return float(to_score - from_score)
    return float(action_weight(row.get("action"), action_weights=action_weights))


def grade_delta_signal(
    ticker_events: pd.DataFrame,
    asof: pd.Timestamp,
    lookback_days: int,
    mapping_rules: list[dict[str, object]] | None = None,
    action_weights: dict[str, float] | None = None,
) -> tuple[float, int]:
    if ticker_events is None or ticker_events.empty:
        return 0.0, 0
    lookback_start = asof - pd.Timedelta(days=lookback_days)
    window = ticker_events[
        (ticker_events["date"] > lookback_start) & (ticker_events["date"] <= asof)
    ]
    if window.empty:
        return 0.0, 0

    values = [
        event_signal_value(
            row,
            mapping_rules=mapping_rules,
            action_weights=action_weights,
        )
        for _, row in window.iterrows()
    ]
    return float(np.sum(values)), int(len(window))


def build_events_by_ticker(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if events is None or events.empty:
        return {}
    events_sorted = events.sort_values(["ticker", "date"]).copy()
    return {
        ticker: part.reset_index(drop=True)
        for ticker, part in events_sorted.groupby("ticker", sort=False)
    }


def compute_signals_for_universe(
    events_by_ticker: dict[str, pd.DataFrame],
    universe: Iterable[str],
    asof: pd.Timestamp,
    lookback_days: int,
    mapping_rules: list[dict[str, object]] | None = None,
    action_weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker in universe:
        ticker_events = events_by_ticker.get(ticker)
        signal, event_count = grade_delta_signal(
            ticker_events=ticker_events,
            asof=asof,
            lookback_days=lookback_days,
            mapping_rules=mapping_rules,
            action_weights=action_weights,
        )
        rows.append({"ticker": ticker, "signal": signal, "events_in_window": event_count})
    return pd.DataFrame(rows)


def _normalize_event_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    frame = raw.copy()
    if isinstance(frame.index, pd.DatetimeIndex):
        frame = frame.reset_index()

    # yfinance often names this column GradeDate (not "date"), so normalize robustly.
    if "date" not in frame.columns:
        normalized_col_lookup = {
            re.sub(r"[\s_]", "", col).lower(): col for col in frame.columns
        }
        date_source = (
            normalized_col_lookup.get("date")
            or normalized_col_lookup.get("gradedate")
            or normalized_col_lookup.get("datetime")
            or normalized_col_lookup.get("timestamp")
        )
        if date_source:
            frame = frame.rename(columns={date_source: "date"})
        elif len(frame.columns) > 0:
            # Fallback: first column after reset_index is usually the timestamp field.
            first_col = frame.columns[0]
            parsed_first = pd.to_datetime(frame[first_col], errors="coerce", utc=True)
            if parsed_first.notna().any():
                frame = frame.rename(columns={first_col: "date"})

    if "date" not in frame.columns:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    normalized_col_lookup = {
        re.sub(r"[\s_]", "", col).lower(): col for col in frame.columns
    }
    col_map = {}
    for canonical, alias in {
        "action": "action",
        "fromGrade": "fromgrade",
        "toGrade": "tograde",
        "firm": "firm",
    }.items():
        source = normalized_col_lookup.get(alias)
        if source:
            col_map[canonical] = source

    output = pd.DataFrame()
    output["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True).dt.tz_convert(
        None
    )
    output["ticker"] = str(ticker).upper().strip()
    for column in ["action", "fromGrade", "toGrade", "firm"]:
        source_col = col_map.get(column)
        output[column] = frame[source_col] if source_col else None

    output = output.dropna(subset=["date"]).reset_index(drop=True)
    return output[EVENT_COLUMNS]


def fetch_ud_events_for_ticker(
    ticker: str,
    logger: Callable[[str], None] | None = None,
) -> pd.DataFrame:
    ticker_clean = str(ticker).upper().strip()
    try:
        _log(logger, f"Fetching analyst events for {ticker_clean}")
        raw = yf.Ticker(ticker_clean).get_upgrades_downgrades()
        return _normalize_event_frame(raw, ticker=ticker_clean)
    except Exception as exc:  # noqa: BLE001
        _log(logger, f"Failed to fetch analyst events for {ticker_clean}: {exc}")
        return pd.DataFrame(columns=EVENT_COLUMNS)


def load_events_cache(cache_path: str) -> pd.DataFrame:
    if not os.path.exists(cache_path):
        return pd.DataFrame(columns=EVENT_COLUMNS)

    frame = pd.read_csv(cache_path)
    if frame.empty:
        return pd.DataFrame(columns=EVENT_COLUMNS)

    for column in EVENT_COLUMNS:
        if column not in frame.columns:
            frame[column] = None

    frame = frame[EVENT_COLUMNS].copy()
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).reset_index(drop=True)
    return frame


def save_events_cache(events: pd.DataFrame, cache_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(cache_path)), exist_ok=True)
    output = events.copy()
    output = output[EVENT_COLUMNS]
    output["date"] = pd.to_datetime(output["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    output.to_csv(cache_path, index=False)


def ensure_events_cache(
    universe: Iterable[str],
    cache_path: str,
    sleep_seconds: float = 0.05,
    refresh: bool = False,
    fetch_missing: bool = True,
    logger: Callable[[str], None] | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    tickers = [str(t).upper().strip() for t in universe if str(t).strip()]
    tickers = list(dict.fromkeys(tickers))

    cached = load_events_cache(cache_path)
    if refresh:
        _log(logger, "Refresh enabled: refetching analyst events for all tickers.")
        cached = pd.DataFrame(columns=EVENT_COLUMNS)

    cached_have = set(cached["ticker"].unique()) if not cached.empty else set()
    missing_tickers_all = [ticker for ticker in tickers if ticker not in cached_have]
    missing_tickers = missing_tickers_all if fetch_missing else []
    _log(
        logger,
        (
            f"Analyst events cache path: {cache_path} | missing tickers: {len(missing_tickers_all)} "
            f"| fetch_missing={bool(fetch_missing)}"
        ),
    )
    if missing_tickers_all and not fetch_missing:
        _log(
            logger,
            "Auto-fetch missing analyst events is disabled; using cached events only for this run.",
        )

    fetched_parts: list[pd.DataFrame] = []
    for index, ticker in enumerate(missing_tickers, start=1):
        _log(logger, f"Fetching {index}/{len(missing_tickers)}: {ticker}")
        part = fetch_ud_events_for_ticker(ticker=ticker, logger=logger)
        if part is not None and not part.empty:
            fetched_parts.append(part)
        if sleep_seconds > 0:
            time.sleep(float(sleep_seconds))

    if fetched_parts:
        cached = (
            pd.concat(fetched_parts, ignore_index=True)
            if cached.empty
            else pd.concat([cached, *fetched_parts], ignore_index=True)
        )
        cached = cached.drop_duplicates(subset=EVENT_COLUMNS).reset_index(drop=True)
        save_events_cache(cached, cache_path)
        _log(logger, f"Saved analyst events cache with {len(cached)} rows.")
    elif refresh:
        save_events_cache(cached, cache_path)

    cached["date"] = pd.to_datetime(cached["date"], errors="coerce")
    cached = cached.dropna(subset=["date"]).reset_index(drop=True)

    coverage = (
        cached.groupby("ticker").size().to_dict() if not cached.empty else {}
    )
    missing_event_tickers = [ticker for ticker in tickers if coverage.get(ticker, 0) == 0]

    stats = {
        "requested_tickers": len(tickers),
        "missing_tickers_in_cache": len(missing_tickers_all),
        "fetched_tickers": len(missing_tickers),
        "cache_rows": int(len(cached)),
        "tickers_without_events": len(missing_event_tickers),
        "missing_event_tickers": missing_event_tickers,
    }
    return cached[EVENT_COLUMNS], stats
