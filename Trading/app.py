from __future__ import annotations

import io
import json
import os
import zipfile
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from src.analyst_events import (
    DEFAULT_ACTION_WEIGHTS,
    DEFAULT_GRADE_MAPPING_RULES,
    ensure_events_cache,
)
from src.backtest import recommend_next_month, run_backtest
from src.data import (
    fetch_prices_from_yfinance,
    get_or_fetch_benchmark_prices,
    load_universe_csv,
)
from src.finnhub_data import (
    build_finnhub_universe_by_monthly_performance,
    ensure_finnhub_ratings_cache,
)

CONFIG_PATH = Path("config.json")

DEFAULT_CONFIG = {
    "prices_cache_path": "data_out/yfinance_prices_cache.parquet",
    "price_provider": "auto",
    "refresh_prices_cache": False,
    "universe_source": "csv",
    "universe_csv": "data_out/top_1000_tickers.csv",
    "csv_universe_limit": 0,
    "finnhub_universe_candidate_source": "csv_file",
    "finnhub_universe_candidate_csv": "data_out/top_1000_tickers.csv",
    "finnhub_universe_candidate_limit": 0,
    "finnhub_universe_top_n": 100,
    "finnhub_universe_cache_path": "data_out/finnhub_universe_performance.csv",
    "finnhub_universe_window_days": 31,
    "refresh_finnhub_universe_cache": False,
    "analyst_source": "auto_finnhub_then_yfinance",
    "events_cache_path": "ud_events_cache_top1000.csv",
    "finnhub_ratings_cache_path": "data_out/finnhub_analyst_ratings.csv",
    "finnhub_match_backtest_window": True,
    "finnhub_ratings_months_back": 24,
    "refresh_finnhub_ratings_cache": False,
    "finnhub_timeout_seconds": 20,
    "finnhub_retries": 3,
    "finnhub_min_rate_limit_wait_seconds": 30.0,
    "finnhub_max_rate_limit_waits": 0,
    "finnhub_max_symbol_attempts": 5,
    "finnhub_retry_round_cooldown_seconds": 10.0,
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
    "top_n": 50,
    "bottom_n": 0,
    "lookback_days": 90,
    "ranking_mode": "blend_with_consistency",
    "consistency_weight": 0.35,
    "consistency_lookback_months": 12,
    "consistency_min_observations": 3,
    "consistency_top_list_n": 25,
    "stress_remove_short_side": False,
    "stress_randomize_signals": False,
    "stress_random_seed": 42,
    "stress_transaction_cost_bps": 0.0,
    "stress_short_borrow_cost_bps_monthly": 0.0,
    "stress_signal_lag_months": 0,
    "stress_universe_mode": "as_is",
    "stress_universe_quantile": 0.30,
    "benchmark_ticker": "SPY",
    "fetch_benchmark_if_missing": True,
    "throttle_seconds": 0.05,
    "refresh_events_cache": False,
    "auto_fetch_missing_prices": False,
    "auto_fetch_missing_analyst": False,
    "require_analyst_window_coverage": True,
    "grade_mapping_rules": DEFAULT_GRADE_MAPPING_RULES,
    "action_weights": DEFAULT_ACTION_WEIGHTS,
}


def _to_date(value: str, fallback: date) -> date:
    try:
        return pd.Timestamp(value).date()
    except Exception:  # noqa: BLE001
        return fallback


def _load_config(path: Path) -> dict:
    config = DEFAULT_CONFIG.copy()
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                config.update(loaded)
        except Exception:  # noqa: BLE001
            pass
    _save_config(path, config)
    return config


def _save_config(path: Path, config: dict) -> None:
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def _sanitize_grade_rules(frame: pd.DataFrame) -> list[dict[str, object]]:
    if frame is None or frame.empty:
        return DEFAULT_GRADE_MAPPING_RULES

    rules: list[dict[str, object]] = []
    for _, row in frame.iterrows():
        phrase = str(row.get("phrase", "")).strip()
        score_raw = row.get("score")
        if not phrase:
            continue
        try:
            score = int(score_raw)
        except (TypeError, ValueError):
            continue
        rules.append({"phrase": phrase, "score": score})

    return rules if rules else DEFAULT_GRADE_MAPPING_RULES


def _fmt_pct(value: float | int | None) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{100.0 * float(value):.2f}%"


def _fmt_num(value: float | int | None) -> str:
    if value is None or not np.isfinite(value):
        return "n/a"
    return f"{float(value):.3f}"


def _serialize_monthly_table(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["month"] = pd.to_datetime(out["month"]).dt.strftime("%Y-%m-%d")
    return out


def _months_between(start_value: date, end_value: date) -> int:
    start_ts = pd.Timestamp(start_value).normalize()
    end_ts = pd.Timestamp(end_value).normalize()
    months = (end_ts.year - start_ts.year) * 12 + (end_ts.month - start_ts.month) + 1
    return max(1, int(months))


def _format_date(ts: pd.Timestamp | None) -> str:
    if ts is None or pd.isna(ts):
        return "n/a"
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _apply_stress_universe(
    *,
    universe: list[str],
    prices: pd.DataFrame,
    mode: str,
    quantile: float,
    ui_log,
) -> tuple[list[str], dict[str, object]]:
    mode_clean = str(mode or "as_is")
    q = float(np.clip(float(quantile), 0.05, 0.95))
    stats: dict[str, object] = {
        "stress_universe_mode_requested": mode_clean,
        "stress_universe_mode_applied": "as_is",
        "stress_universe_quantile": q,
        "stress_universe_before": len(universe),
        "stress_universe_after": len(universe),
    }
    if mode_clean == "as_is":
        return universe, stats

    subset = prices[prices["ticker"].isin(universe)][["ticker", "adj_close"]].copy()
    if subset.empty:
        ui_log("Stress universe mode skipped: no prices available to build universe proxy.")
        return universe, stats

    score = subset.groupby("ticker", sort=False)["adj_close"].median().dropna()
    if score.empty:
        ui_log("Stress universe mode skipped: no valid price scores available.")
        return universe, stats

    n_pick = max(1, int(round(len(score) * q)))
    selected: set[str]
    if mode_clean == "large_cap_proxy":
        selected = set(score.nlargest(n_pick).index.tolist())
        applied_mode = "large_cap_proxy"
    elif mode_clean == "small_cap_proxy":
        selected = set(score.nsmallest(n_pick).index.tolist())
        applied_mode = "small_cap_proxy"
    elif mode_clean == "international_proxy":
        selected_list = [
            ticker
            for ticker in score.index.astype(str).tolist()
            if any(marker in ticker for marker in [".", ":", "-"])
        ]
        if not selected_list:
            ui_log(
                "International proxy found no ticker suffix matches; keeping original universe."
            )
            return universe, stats
        selected = set(selected_list)
        applied_mode = "international_proxy"
    else:
        ui_log(f"Unknown stress universe mode '{mode_clean}'; keeping original universe.")
        return universe, stats

    filtered = [ticker for ticker in universe if ticker in selected]
    if not filtered:
        ui_log(
            f"Stress universe mode '{mode_clean}' would produce empty universe; keeping original universe."
        )
        return universe, stats

    ui_log(
        f"Stress universe mode '{applied_mode}': selected {len(filtered):,}/{len(universe):,} tickers."
    )
    stats.update(
        {
            "stress_universe_mode_applied": applied_mode,
            "stress_universe_before": len(universe),
            "stress_universe_after": len(filtered),
        }
    )
    return filtered, stats


def _frame_to_csv_bytes(frame: pd.DataFrame) -> bytes:
    if frame is None:
        frame = pd.DataFrame()
    out = frame.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]) or pd.api.types.is_datetime64tz_dtype(out[col]):
            out[col] = pd.to_datetime(out[col], errors="coerce").dt.strftime("%Y-%m-%d")
    return out.to_csv(index=False).encode("utf-8")


def _build_results_zip_bytes(
    *,
    result: dict[str, object],
    last_run: dict[str, object],
) -> bytes:
    monthly = result.get("monthly_results", pd.DataFrame())
    equity_curve = result.get("equity_curve", pd.DataFrame())
    drawdown_curve = result.get("drawdown_curve", pd.DataFrame())
    ic_series = result.get("ic_series", pd.DataFrame())
    consistency_table = result.get("consistency_table", pd.DataFrame())

    logs = last_run.get("logs", [])
    settings_used = last_run.get("settings", {})
    diagnostics = result.get("diagnostics", {})
    portfolio_stats = result.get("portfolio_stats", {})
    benchmark_stats = result.get("benchmark_stats", {})
    ic_summary = result.get("ic_summary", {})
    consistency_summary = result.get("consistency_summary", {})
    analyst_stats = last_run.get("analyst_stats", {})
    universe_stats = last_run.get("universe_stats", {})
    price_stats = last_run.get("price_stats", {})

    analyst_errors = analyst_stats.get("errors_df")
    if not isinstance(analyst_errors, pd.DataFrame):
        analyst_errors = pd.DataFrame()
    universe_errors = universe_stats.get("errors_df")
    if not isinstance(universe_errors, pd.DataFrame):
        universe_errors = pd.DataFrame()

    summary_payload = {
        "portfolio_stats": portfolio_stats,
        "benchmark_stats": benchmark_stats,
        "ic_summary": ic_summary,
        "consistency_summary": consistency_summary,
        "diagnostics": diagnostics,
        "benchmark_source": last_run.get("benchmark_source"),
    }

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("monthly_results.csv", _frame_to_csv_bytes(monthly))
        zf.writestr("equity_curve.csv", _frame_to_csv_bytes(equity_curve))
        zf.writestr("drawdown_curve.csv", _frame_to_csv_bytes(drawdown_curve))
        zf.writestr("ic_series.csv", _frame_to_csv_bytes(ic_series))
        zf.writestr("consistency_table.csv", _frame_to_csv_bytes(consistency_table))
        zf.writestr("analyst_errors.csv", _frame_to_csv_bytes(analyst_errors))
        zf.writestr("universe_errors.csv", _frame_to_csv_bytes(universe_errors))
        zf.writestr("settings_used.json", json.dumps(settings_used, indent=2, default=str))
        zf.writestr("summary.json", json.dumps(summary_payload, indent=2, default=str))
        zf.writestr("analyst_stats.json", json.dumps(analyst_stats, indent=2, default=str))
        zf.writestr("universe_stats.json", json.dumps(universe_stats, indent=2, default=str))
        zf.writestr("price_stats.json", json.dumps(price_stats, indent=2, default=str))
        zf.writestr("logs.txt", "\n".join(str(x) for x in logs))

    return buffer.getvalue()


st.set_page_config(
    page_title="True Historical Analyst Backtest",
    page_icon="chart_with_upwards_trend",
    layout="wide",
)

st.title("True Historical Analyst Backtest")
st.caption(
    "Monthly long/short backtest using analyst signals and optional analyst-consistency ranking. "
    "Supports yfinance events or Finnhub ratings with CSV or Finnhub universe selection."
)

config = _load_config(CONFIG_PATH)

if "last_run" not in st.session_state:
    st.session_state["last_run"] = None
if "last_coverage" not in st.session_state:
    st.session_state["last_coverage"] = None
if "last_recommendation" not in st.session_state:
    st.session_state["last_recommendation"] = None
if "recommendation_inputs" not in st.session_state:
    st.session_state["recommendation_inputs"] = None

with st.sidebar:
    st.header("Settings")

    prices_cache_path = st.text_input(
        "Prices cache file (auto-filled from selected provider)",
        value=config.get("prices_cache_path", DEFAULT_CONFIG["prices_cache_path"]),
    )
    price_provider = st.selectbox(
        "Price data provider",
        options=["auto", "yfinance", "alpaca"],
        index={
            "auto": 0,
            "yfinance": 1,
            "alpaca": 2,
        }.get(str(config.get("price_provider", "auto")).lower(), 0),
        help="auto = Alpaca first then yfinance fallback.",
    )
    uses_alpaca = price_provider in {"auto", "alpaca"}
    alpaca_api_key = st.text_input(
        "Alpaca API key",
        value=os.getenv("APCA_API_KEY_ID", os.getenv("ALPACA_API_KEY_ID", "")),
        type="password",
        disabled=not uses_alpaca,
    )
    alpaca_api_secret = st.text_input(
        "Alpaca API secret",
        value=os.getenv("APCA_API_SECRET_KEY", os.getenv("ALPACA_API_SECRET_KEY", "")),
        type="password",
        disabled=not uses_alpaca,
    )
    alpaca_timeout_seconds = st.number_input(
        "Alpaca timeout (sec)",
        min_value=5,
        max_value=120,
        value=20,
        disabled=not uses_alpaca,
    )

    universe_source = st.selectbox(
        "Universe source",
        options=["csv", "finnhub_monthly_performance"],
        index=0 if config.get("universe_source", "csv") == "csv" else 1,
    )
    universe_csv = st.text_input(
        "Universe CSV file (ticker column)",
        value=config.get("universe_csv", DEFAULT_CONFIG["universe_csv"]),
        disabled=universe_source != "csv",
    )
    csv_universe_limit = st.number_input(
        "CSV universe ticker limit (0=all)",
        min_value=0,
        max_value=20000,
        value=int(config.get("csv_universe_limit", 0)),
        disabled=universe_source != "csv",
        help="When using CSV universe source, this limits how many tickers are loaded/fetched.",
    )

    analyst_source = st.selectbox(
        "Analyst signal source",
        options=["auto_finnhub_then_yfinance", "yfinance_events", "finnhub_ratings"],
        index={
            "auto_finnhub_then_yfinance": 0,
            "yfinance_events": 1,
            "finnhub_ratings": 2,
        }.get(str(config.get("analyst_source", "auto_finnhub_then_yfinance")), 0),
    )
    events_cache_path = st.text_input(
        "yfinance events cache CSV path",
        value=config.get("events_cache_path", DEFAULT_CONFIG["events_cache_path"]),
        disabled=analyst_source == "finnhub_ratings",
    )
    finnhub_ratings_cache_path = st.text_input(
        "Finnhub ratings cache CSV path",
        value=config.get("finnhub_ratings_cache_path", DEFAULT_CONFIG["finnhub_ratings_cache_path"]),
        disabled=analyst_source == "yfinance_events",
    )

    start_date = st.date_input(
        "Start date",
        value=_to_date(config.get("start_date", DEFAULT_CONFIG["start_date"]), date(2024, 1, 1)),
    )
    end_date = st.date_input(
        "End date",
        value=_to_date(config.get("end_date", DEFAULT_CONFIG["end_date"]), date(2025, 12, 31)),
    )

    top_n = st.number_input("Top N longs", min_value=0, max_value=1000, value=int(config.get("top_n", 50)))
    bottom_n = st.number_input(
        "Bottom N shorts",
        min_value=0,
        max_value=1000,
        value=int(config.get("bottom_n", 0)),
    )
    lookback_days = st.number_input(
        "Lookback days",
        min_value=1,
        max_value=3650,
        value=int(config.get("lookback_days", 90)),
    )
    ranking_mode = st.selectbox(
        "Ranking mode",
        options=["signal_only", "blend_with_consistency", "consistency_only"],
        index={
            "signal_only": 0,
            "blend_with_consistency": 1,
            "consistency_only": 2,
        }.get(str(config.get("ranking_mode", "blend_with_consistency")), 1),
        help=(
            "signal_only: rank by current analyst signal only. "
            "blend_with_consistency: combine current signal with analyst foresight consistency. "
            "consistency_only: rank only by historical consistency."
        ),
    )
    consistency_weight = st.slider(
        "Consistency weight (blend mode)",
        min_value=0.0,
        max_value=1.0,
        value=float(config.get("consistency_weight", 0.35)),
        step=0.05,
        disabled=ranking_mode != "blend_with_consistency",
        help="In blend mode, higher value gives more weight to historical analyst consistency.",
    )
    consistency_lookback_months = st.number_input(
        "Consistency lookback months (0=all history)",
        min_value=0,
        max_value=240,
        value=int(config.get("consistency_lookback_months", 12)),
        help="How much past history is used to score analyst foresight consistency for each stock.",
    )
    consistency_min_observations = st.number_input(
        "Min observations for consistency",
        min_value=1,
        max_value=120,
        value=int(config.get("consistency_min_observations", 3)),
        help="Minimum directional months required before a stock gets a non-zero consistency score.",
    )
    consistency_top_list_n = st.number_input(
        "Top consistency rows to display",
        min_value=5,
        max_value=500,
        value=int(config.get("consistency_top_list_n", 25)),
    )
    with st.expander("Stress Testing"):
        stress_remove_short_side = st.checkbox(
            "Stress: remove short side",
            value=bool(config.get("stress_remove_short_side", False)),
            help="Sets shorts to 0 during the run to test whether performance depends on short alpha.",
        )
        stress_randomize_signals = st.checkbox(
            "Stress: randomize analyst signals",
            value=bool(config.get("stress_randomize_signals", False)),
            help="Randomly shuffles cross-sectional analyst signals each month.",
        )
        stress_random_seed = st.number_input(
            "Random seed",
            min_value=1,
            max_value=1_000_000,
            value=int(config.get("stress_random_seed", 42)),
            disabled=not stress_randomize_signals,
        )
        stress_signal_lag_months = st.number_input(
            "Signal lag months",
            min_value=0,
            max_value=12,
            value=int(config.get("stress_signal_lag_months", 0)),
            help="Uses analyst signal from prior month(s) when ranking.",
        )
        stress_transaction_cost_bps = st.number_input(
            "Transaction cost (bps per one-way turnover)",
            min_value=0.0,
            max_value=500.0,
            value=float(config.get("stress_transaction_cost_bps", 0.0)),
            step=5.0,
            help="Examples: 50 bps, 100 bps.",
        )
        stress_short_borrow_cost_bps_monthly = st.number_input(
            "Short borrow cost (bps per month)",
            min_value=0.0,
            max_value=500.0,
            value=float(config.get("stress_short_borrow_cost_bps_monthly", 0.0)),
            step=5.0,
            help="Applied each month to active short leg.",
        )
        stress_universe_mode = st.selectbox(
            "Universe stress mode",
            options=["as_is", "large_cap_proxy", "small_cap_proxy", "international_proxy"],
            index={
                "as_is": 0,
                "large_cap_proxy": 1,
                "small_cap_proxy": 2,
                "international_proxy": 3,
            }.get(str(config.get("stress_universe_mode", "as_is")), 0),
            help=(
                "Large/small are price-based proxies from local data. "
                "International proxy uses non-US ticker suffix patterns."
            ),
        )
        stress_universe_quantile = st.slider(
            "Universe proxy quantile",
            min_value=0.05,
            max_value=0.95,
            value=float(config.get("stress_universe_quantile", 0.30)),
            step=0.05,
            disabled=stress_universe_mode not in {"large_cap_proxy", "small_cap_proxy"},
            help="Fraction of universe kept for large/small proxy mode.",
        )

    benchmark_ticker = st.text_input(
        "Benchmark ticker",
        value=str(config.get("benchmark_ticker", "SPY")),
    ).upper()
    fetch_benchmark_if_missing = st.checkbox(
        "Fetch benchmark if missing",
        value=bool(config.get("fetch_benchmark_if_missing", True)),
    )

    throttle_seconds = st.number_input(
        "Base request throttle (sec)",
        min_value=0.0,
        max_value=5.0,
        value=float(config.get("throttle_seconds", 0.05)),
        step=0.01,
    )
    refresh_events_cache = st.checkbox(
        "Refresh yfinance events cache",
        value=bool(config.get("refresh_events_cache", False)),
        disabled=analyst_source == "finnhub_ratings",
    )
    refresh_prices_cache = st.checkbox(
        "Refresh yfinance prices cache",
        value=bool(config.get("refresh_prices_cache", False)),
    )
    auto_fetch_missing_prices = st.checkbox(
        "Auto-fetch missing prices each run",
        value=bool(config.get("auto_fetch_missing_prices", False)),
        help="If disabled, price loading is cache-only unless refresh is enabled.",
    )
    refresh_finnhub_ratings_cache = st.checkbox(
        "Refresh Finnhub ratings cache",
        value=bool(config.get("refresh_finnhub_ratings_cache", False)),
        disabled=analyst_source == "yfinance_events",
    )
    auto_fetch_missing_analyst = st.checkbox(
        "Auto-fetch missing analyst data each run",
        value=bool(config.get("auto_fetch_missing_analyst", False)),
        help="If disabled, analyst loading is cache-only unless refresh is enabled.",
    )
    require_analyst_window_coverage = st.checkbox(
        "Require analyst data in backtest window",
        value=bool(config.get("require_analyst_window_coverage", True)),
        help="If enabled, run stops when analyst data does not overlap selected backtest dates.",
    )

    uses_finnhub = universe_source == "finnhub_monthly_performance" or analyst_source in {
        "finnhub_ratings",
        "auto_finnhub_then_yfinance",
    }
    finnhub_api_key = st.text_input(
        "Finnhub API key",
        value=os.getenv("FINNHUB_API_KEY", ""),
        type="password",
        disabled=not uses_finnhub,
        help="Required when using Finnhub universe or Finnhub analyst ratings.",
    )

    if universe_source == "finnhub_monthly_performance":
        st.markdown("**Finnhub Universe Settings**")
        finnhub_universe_candidate_source = "csv_file"
        finnhub_universe_candidate_csv = st.text_input(
            "Candidate CSV path",
            value=config.get(
                "finnhub_universe_candidate_csv",
                DEFAULT_CONFIG["finnhub_universe_candidate_csv"],
            ),
        )
        finnhub_universe_candidate_limit = st.number_input(
            "Candidate ticker limit (0=all)",
            min_value=0,
            max_value=20000,
            value=int(config.get("finnhub_universe_candidate_limit", 0)),
        )
        finnhub_universe_top_n = st.number_input(
            "Final universe size (tickers to fetch/backtest)",
            min_value=1,
            max_value=5000,
            value=int(config.get("finnhub_universe_top_n", 100)),
        )
        finnhub_universe_window_days = st.number_input(
            "Performance window days",
            min_value=7,
            max_value=120,
            value=int(config.get("finnhub_universe_window_days", 31)),
        )
        finnhub_universe_cache_path = st.text_input(
            "Universe performance cache CSV path",
            value=config.get(
                "finnhub_universe_cache_path",
                DEFAULT_CONFIG["finnhub_universe_cache_path"],
            ),
        )
        refresh_finnhub_universe_cache = st.checkbox(
            "Refresh Finnhub universe cache",
            value=bool(config.get("refresh_finnhub_universe_cache", False)),
        )
    else:
        finnhub_universe_candidate_source = "csv_file"
        finnhub_universe_candidate_csv = config.get(
            "finnhub_universe_candidate_csv",
            DEFAULT_CONFIG["finnhub_universe_candidate_csv"],
        )
        finnhub_universe_candidate_limit = int(config.get("finnhub_universe_candidate_limit", 0))
        finnhub_universe_top_n = int(config.get("finnhub_universe_top_n", 1000))
        finnhub_universe_window_days = int(config.get("finnhub_universe_window_days", 31))
        finnhub_universe_cache_path = config.get(
            "finnhub_universe_cache_path",
            DEFAULT_CONFIG["finnhub_universe_cache_path"],
        )
        refresh_finnhub_universe_cache = bool(config.get("refresh_finnhub_universe_cache", False))

    if analyst_source in {"finnhub_ratings", "auto_finnhub_then_yfinance"}:
        st.markdown("**Finnhub Analyst Ratings Settings**")
        finnhub_match_backtest_window = st.checkbox(
            "Auto-match ratings interval to backtest window",
            value=bool(config.get("finnhub_match_backtest_window", True)),
        )
        auto_months_back = _months_between(start_date, end_date) + 2
        finnhub_ratings_months_back = st.number_input(
            "Ratings months back (0=all available)",
            min_value=0,
            max_value=120,
            value=int(config.get("finnhub_ratings_months_back", 24)),
            disabled=finnhub_match_backtest_window,
        )
        if finnhub_match_backtest_window:
            finnhub_ratings_months_back = int(auto_months_back)
            st.caption(f"Using auto months_back={auto_months_back} from selected backtest dates.")
    else:
        finnhub_match_backtest_window = bool(config.get("finnhub_match_backtest_window", True))
        finnhub_ratings_months_back = int(config.get("finnhub_ratings_months_back", 24))

    if uses_finnhub:
        st.markdown("**Finnhub Rate Limit / Retry Settings**")
        finnhub_timeout_seconds = st.number_input(
            "Finnhub timeout (sec)",
            min_value=5,
            max_value=120,
            value=int(config.get("finnhub_timeout_seconds", 20)),
        )
        finnhub_retries = st.number_input(
            "Finnhub retries",
            min_value=1,
            max_value=10,
            value=int(config.get("finnhub_retries", 3)),
        )
        finnhub_min_rate_limit_wait_seconds = st.number_input(
            "Min wait on rate limit (sec)",
            min_value=1.0,
            max_value=300.0,
            value=float(config.get("finnhub_min_rate_limit_wait_seconds", 30.0)),
            step=1.0,
        )
        finnhub_max_rate_limit_waits = st.number_input(
            "Max rate-limit waits per request (0=unlimited)",
            min_value=0,
            max_value=50,
            value=int(config.get("finnhub_max_rate_limit_waits", 0)),
        )
        finnhub_max_symbol_attempts = st.number_input(
            "Max attempts per ticker",
            min_value=1,
            max_value=20,
            value=int(config.get("finnhub_max_symbol_attempts", 5)),
        )
        finnhub_retry_round_cooldown_seconds = st.number_input(
            "Retry round cooldown (sec)",
            min_value=0.0,
            max_value=300.0,
            value=float(config.get("finnhub_retry_round_cooldown_seconds", 10.0)),
            step=1.0,
        )
    else:
        finnhub_timeout_seconds = int(config.get("finnhub_timeout_seconds", 20))
        finnhub_retries = int(config.get("finnhub_retries", 3))
        finnhub_min_rate_limit_wait_seconds = float(config.get("finnhub_min_rate_limit_wait_seconds", 30.0))
        finnhub_max_rate_limit_waits = int(config.get("finnhub_max_rate_limit_waits", 0))
        finnhub_max_symbol_attempts = int(config.get("finnhub_max_symbol_attempts", 5))
        finnhub_retry_round_cooldown_seconds = float(config.get("finnhub_retry_round_cooldown_seconds", 10.0))

    with st.expander("Advanced: Grade Mapping"):
        grade_rules_df = pd.DataFrame(
            config.get("grade_mapping_rules", DEFAULT_GRADE_MAPPING_RULES)
        )
        if "phrase" not in grade_rules_df.columns:
            grade_rules_df["phrase"] = ""
        if "score" not in grade_rules_df.columns:
            grade_rules_df["score"] = 0

        edited_grade_rules = st.data_editor(
            grade_rules_df[["phrase", "score"]],
            use_container_width=True,
            num_rows="dynamic",
            key="grade_rules_editor",
        )

        st.caption("Fallback action weights used when from/to grades cannot be mapped:")
        aw = config.get("action_weights", DEFAULT_ACTION_WEIGHTS)
        col_aw1, col_aw2 = st.columns(2)
        with col_aw1:
            action_upgrade = st.number_input("upgrade", value=float(aw.get("upgrade", 1.0)), step=0.05)
            action_downgrade = st.number_input("downgrade", value=float(aw.get("downgrade", -1.0)), step=0.05)
        with col_aw2:
            action_initiation = st.number_input("initiation", value=float(aw.get("initiat", 0.25)), step=0.05)
            action_default = st.number_input("default", value=float(aw.get("default", 0.0)), step=0.05)

    coverage_clicked = st.button("Check analyst coverage only", use_container_width=True)
    run_clicked = st.button("Run backtest", type="primary", use_container_width=True)

settings = {
    "prices_cache_path": prices_cache_path,
    "price_provider": str(price_provider),
    "alpaca_timeout_seconds": int(alpaca_timeout_seconds),
    "refresh_prices_cache": bool(refresh_prices_cache),
    "universe_source": universe_source,
    "universe_csv": universe_csv,
    "csv_universe_limit": int(csv_universe_limit),
    "finnhub_universe_candidate_source": finnhub_universe_candidate_source,
    "finnhub_universe_candidate_csv": finnhub_universe_candidate_csv,
    "finnhub_universe_candidate_limit": int(finnhub_universe_candidate_limit),
    "finnhub_universe_top_n": int(finnhub_universe_top_n),
    "finnhub_universe_cache_path": finnhub_universe_cache_path,
    "finnhub_universe_window_days": int(finnhub_universe_window_days),
    "refresh_finnhub_universe_cache": bool(refresh_finnhub_universe_cache),
    "analyst_source": analyst_source,
    "events_cache_path": events_cache_path,
    "finnhub_ratings_cache_path": finnhub_ratings_cache_path,
    "finnhub_match_backtest_window": bool(finnhub_match_backtest_window),
    "finnhub_ratings_months_back": int(finnhub_ratings_months_back),
    "refresh_finnhub_ratings_cache": bool(refresh_finnhub_ratings_cache),
    "finnhub_timeout_seconds": int(finnhub_timeout_seconds),
    "finnhub_retries": int(finnhub_retries),
    "finnhub_min_rate_limit_wait_seconds": float(finnhub_min_rate_limit_wait_seconds),
    "finnhub_max_rate_limit_waits": int(finnhub_max_rate_limit_waits),
    "finnhub_max_symbol_attempts": int(finnhub_max_symbol_attempts),
    "finnhub_retry_round_cooldown_seconds": float(finnhub_retry_round_cooldown_seconds),
    "start_date": str(start_date),
    "end_date": str(end_date),
    "top_n": int(top_n),
    "bottom_n": int(bottom_n),
    "lookback_days": int(lookback_days),
    "ranking_mode": str(ranking_mode),
    "consistency_weight": float(consistency_weight),
    "consistency_lookback_months": int(consistency_lookback_months),
    "consistency_min_observations": int(consistency_min_observations),
    "consistency_top_list_n": int(consistency_top_list_n),
    "stress_remove_short_side": bool(stress_remove_short_side),
    "stress_randomize_signals": bool(stress_randomize_signals),
    "stress_random_seed": int(stress_random_seed),
    "stress_transaction_cost_bps": float(stress_transaction_cost_bps),
    "stress_short_borrow_cost_bps_monthly": float(stress_short_borrow_cost_bps_monthly),
    "stress_signal_lag_months": int(stress_signal_lag_months),
    "stress_universe_mode": str(stress_universe_mode),
    "stress_universe_quantile": float(stress_universe_quantile),
    "benchmark_ticker": benchmark_ticker,
    "fetch_benchmark_if_missing": bool(fetch_benchmark_if_missing),
    "throttle_seconds": float(throttle_seconds),
    "refresh_events_cache": bool(refresh_events_cache),
    "auto_fetch_missing_prices": bool(auto_fetch_missing_prices),
    "auto_fetch_missing_analyst": bool(auto_fetch_missing_analyst),
    "require_analyst_window_coverage": bool(require_analyst_window_coverage),
    "grade_mapping_rules": _sanitize_grade_rules(edited_grade_rules),
    "action_weights": {
        "upgrade": float(action_upgrade),
        "downgrade": float(action_downgrade),
        "initiat": float(action_initiation),
        "default": float(action_default),
    },
}


def _prepare_for_backtest_inputs(
    *,
    settings: dict[str, object],
    finnhub_api_key: str,
    alpaca_api_key: str,
    alpaca_api_secret: str,
    ui_log,
    enforce_coverage: bool,
) -> dict[str, object]:
    universe_stats: dict[str, object] = {"source": settings["universe_source"]}
    if settings["universe_source"] == "finnhub_monthly_performance":
        if not finnhub_api_key.strip():
            raise ValueError("Finnhub API key is required for Finnhub universe source.")

        ui_log("Loading Finnhub universe candidates from CSV...")
        candidate_tickers = load_universe_csv(str(settings["finnhub_universe_candidate_csv"]))
        if int(settings["finnhub_universe_candidate_limit"]) > 0:
            candidate_tickers = candidate_tickers[: int(settings["finnhub_universe_candidate_limit"])]

        ui_log(
            f"Building Finnhub performance universe from {len(candidate_tickers):,} candidates..."
        )
        universe, _finnhub_ranked, universe_stats = build_finnhub_universe_by_monthly_performance(
            candidate_tickers=candidate_tickers,
            api_key=finnhub_api_key.strip(),
            asof_date=str(settings["end_date"]),
            top_n=int(settings["finnhub_universe_top_n"]),
            cache_path=str(settings["finnhub_universe_cache_path"]),
            refresh=bool(settings["refresh_finnhub_universe_cache"]),
            window_days=int(settings["finnhub_universe_window_days"]),
            sleep_seconds=float(settings["throttle_seconds"]),
            timeout=int(settings["finnhub_timeout_seconds"]),
            retries=int(settings["finnhub_retries"]),
            min_rate_limit_wait_sec=float(settings["finnhub_min_rate_limit_wait_seconds"]),
            max_rate_limit_waits=int(settings["finnhub_max_rate_limit_waits"]),
            max_symbol_attempts=int(settings["finnhub_max_symbol_attempts"]),
            retry_round_cooldown_sec=float(settings["finnhub_retry_round_cooldown_seconds"]),
            logger=ui_log,
        )
        ui_log(
            "Finnhub universe ready. "
            f"selected={len(universe):,} | rankable={universe_stats.get('rankable_tickers', 0):,}"
        )
    else:
        ui_log("Loading universe CSV...")
        universe = load_universe_csv(str(settings["universe_csv"]))
        if int(settings["csv_universe_limit"]) > 0:
            universe = universe[: int(settings["csv_universe_limit"])]
        ui_log(f"Loaded {len(universe):,} tickers.")
        universe_stats = {
            "source": "csv",
            "selected_tickers": len(universe),
        }

    if not universe:
        raise RuntimeError("Universe is empty after selected source processing.")
    price_provider = str(settings.get("price_provider", "yfinance")).lower()
    if price_provider == "alpaca" and (not str(alpaca_api_key).strip() or not str(alpaca_api_secret).strip()):
        raise ValueError("Alpaca provider selected but Alpaca API key/secret are missing.")

    prices_tickers = list(dict.fromkeys([*universe, str(settings["benchmark_ticker"]).upper().strip()]))
    ui_log(
        f"Fetching prices for {len(prices_tickers):,} tickers "
        f"({settings['start_date']}..{settings['end_date']}) "
        f"| provider={settings.get('price_provider', 'yfinance')} "
        f"| auto_fetch_missing_prices={bool(settings['auto_fetch_missing_prices'])}..."
    )
    prices, price_stats = fetch_prices_from_yfinance(
        tickers=prices_tickers,
        start_date=str(settings["start_date"]),
        end_date=str(settings["end_date"]),
        cache_path=str(settings["prices_cache_path"]),
        refresh=bool(settings["refresh_prices_cache"]),
        fetch_missing=bool(settings["auto_fetch_missing_prices"]),
        provider=str(settings.get("price_provider", "yfinance")),
        alpaca_api_key=str(alpaca_api_key or ""),
        alpaca_api_secret=str(alpaca_api_secret or ""),
        alpaca_timeout=int(settings.get("alpaca_timeout_seconds", 20)),
        sleep_seconds=float(settings["throttle_seconds"]),
        logger=ui_log,
    )
    ui_log(
        "Price data ready. "
        f"rows={price_stats.get('selected_rows', 0):,}, "
        f"tickers_without_prices={price_stats.get('tickers_without_prices', 0)}"
    )
    universe_before_price_filter = list(universe)
    available_price_tickers = set(prices["ticker"].unique()) if not prices.empty else set()
    benchmark_clean = str(settings["benchmark_ticker"]).upper().strip()
    if benchmark_clean:
        available_price_tickers.add(benchmark_clean)
    universe = [ticker for ticker in universe_before_price_filter if ticker in available_price_tickers]
    removed_no_price = [ticker for ticker in universe_before_price_filter if ticker not in set(universe)]
    if removed_no_price:
        ui_log(
            "Dropping tickers without local cached prices from this run: "
            f"{len(removed_no_price)} removed."
        )
    if not universe:
        raise RuntimeError(
            "No universe tickers have price data after filtering. "
            "Try a smaller universe, different dates, or refresh prices cache."
        )
    universe_stats["selected_tickers_before_price_filter"] = len(universe_before_price_filter)
    universe_stats["selected_tickers"] = len(universe)
    universe_stats["removed_no_price_tickers"] = len(removed_no_price)
    universe_stats["removed_no_price_list"] = removed_no_price[:200]
    stress_mode = str(settings.get("stress_universe_mode", "as_is"))
    universe, stress_universe_stats = _apply_stress_universe(
        universe=universe,
        prices=prices,
        mode=stress_mode,
        quantile=float(settings.get("stress_universe_quantile", 0.30)),
        ui_log=ui_log,
    )
    universe_stats.update(stress_universe_stats)
    universe_stats["selected_tickers"] = len(universe)
    if not universe:
        raise RuntimeError(
            "Universe is empty after stress universe filter. "
            "Switch stress universe mode to 'as_is' or lower quantile."
        )

    events = pd.DataFrame()
    finnhub_ratings = pd.DataFrame()
    analyst_stats: dict[str, object] = {"source": settings["analyst_source"]}
    signal_lag_months = int(settings.get("stress_signal_lag_months", 0))
    lag_offset = pd.DateOffset(months=signal_lag_months)
    backtest_start_ts = pd.Timestamp(settings["start_date"]).normalize()
    backtest_end_ts = pd.Timestamp(settings["end_date"]).normalize()
    coverage_start = backtest_start_ts - lag_offset - pd.Timedelta(days=int(settings["lookback_days"]))
    effective_analyst_source = str(settings["analyst_source"])

    def _load_finnhub(enforce_window: bool) -> int:
        nonlocal finnhub_ratings, analyst_stats
        if not finnhub_api_key.strip():
            raise ValueError("Finnhub API key is required for Finnhub analyst ratings.")
        finnhub_ratings, analyst_stats = ensure_finnhub_ratings_cache(
            universe=universe,
            api_key=finnhub_api_key.strip(),
            cache_path=str(settings["finnhub_ratings_cache_path"]),
            start_date=str(settings["start_date"]),
            end_date=str(settings["end_date"]),
            months_back=int(settings["finnhub_ratings_months_back"]),
            refresh=bool(settings["refresh_finnhub_ratings_cache"]),
            fetch_missing=bool(settings["auto_fetch_missing_analyst"]),
            sleep_seconds=float(settings["throttle_seconds"]),
            timeout=int(settings["finnhub_timeout_seconds"]),
            retries=int(settings["finnhub_retries"]),
            min_rate_limit_wait_sec=float(settings["finnhub_min_rate_limit_wait_seconds"]),
            max_rate_limit_waits=int(settings["finnhub_max_rate_limit_waits"]),
            max_symbol_attempts=int(settings["finnhub_max_symbol_attempts"]),
            retry_round_cooldown_sec=float(settings["finnhub_retry_round_cooldown_seconds"]),
            logger=ui_log,
        )
        ratings_period = pd.to_datetime(finnhub_ratings["period"], errors="coerce")
        ratings_window = finnhub_ratings[
            (ratings_period >= coverage_start) & (ratings_period <= backtest_end_ts)
        ].copy()
        analyst_stats["rows_in_backtest_window"] = int(len(ratings_window))
        analyst_stats["tickers_with_data_in_backtest_window"] = int(
            ratings_window["ticker"].nunique() if not ratings_window.empty else 0
        )
        analyst_stats["coverage_check_start"] = str(coverage_start.date())
        analyst_stats["coverage_check_end"] = str(backtest_end_ts.date())
        ui_log(
            "Finnhub ratings ready. "
            f"rows_selected={analyst_stats.get('cache_rows_selected', 0):,}, "
            f"tickers_without_ratings={analyst_stats.get('tickers_without_ratings', 0)}"
        )
        rows_in_window = int(analyst_stats.get("rows_in_backtest_window", 0) or 0)
        if enforce_window and rows_in_window == 0:
            raise ValueError(
                "No Finnhub analyst ratings overlap the selected backtest window "
                f"{settings['start_date']}..{settings['end_date']}. "
                f"Available cache period is {analyst_stats.get('period_min')}..{analyst_stats.get('period_max')}."
            )
        return rows_in_window

    def _load_yfinance(enforce_window: bool) -> int:
        nonlocal events, analyst_stats
        events, analyst_stats = ensure_events_cache(
            universe=universe,
            cache_path=str(settings["events_cache_path"]),
            sleep_seconds=float(settings["throttle_seconds"]),
            refresh=bool(settings["refresh_events_cache"]),
            fetch_missing=bool(settings["auto_fetch_missing_analyst"]),
            logger=ui_log,
        )
        events_dates = pd.to_datetime(events["date"], errors="coerce")
        events_window = events[
            (events_dates >= coverage_start) & (events_dates <= backtest_end_ts)
        ].copy()
        analyst_stats["rows_in_backtest_window"] = int(len(events_window))
        analyst_stats["tickers_with_data_in_backtest_window"] = int(
            events_window["ticker"].nunique() if not events_window.empty else 0
        )
        analyst_stats["coverage_check_start"] = str(coverage_start.date())
        analyst_stats["coverage_check_end"] = str(backtest_end_ts.date())
        analyst_stats["period_min"] = _format_date(events_dates.min())
        analyst_stats["period_max"] = _format_date(events_dates.max())
        ui_log(
            "yfinance events cache ready. "
            f"Rows: {analyst_stats['cache_rows']:,}, "
            f"tickers without events: {analyst_stats['tickers_without_events']}"
        )
        rows_in_window = int(analyst_stats.get("rows_in_backtest_window", 0) or 0)
        if enforce_window and rows_in_window == 0:
            raise ValueError(
                "No yfinance analyst events overlap required signal window "
                f"{coverage_start.date()}..{backtest_end_ts.date()} "
                "(backtest window plus lookback)."
            )
        return rows_in_window

    if settings["analyst_source"] == "finnhub_ratings":
        _load_finnhub(enforce_window=enforce_coverage)
        effective_analyst_source = "finnhub_ratings"
    elif settings["analyst_source"] == "yfinance_events":
        _load_yfinance(enforce_window=enforce_coverage)
        effective_analyst_source = "yfinance_events"
    else:
        used_finnhub = False
        if finnhub_api_key.strip():
            try:
                rows_finnhub = _load_finnhub(enforce_window=False)
                if rows_finnhub > 0:
                    used_finnhub = True
                    effective_analyst_source = "finnhub_ratings"
                    analyst_stats["source"] = "finnhub_ratings(auto)"
                else:
                    ui_log("Auto analyst source: Finnhub has no rows in window, falling back to yfinance.")
            except Exception as exc:  # noqa: BLE001
                ui_log(f"Auto analyst source: Finnhub failed ({exc}), falling back to yfinance.")
        else:
            ui_log("Auto analyst source: Finnhub API key missing, falling back to yfinance.")

        if not used_finnhub:
            _load_yfinance(enforce_window=enforce_coverage)
            effective_analyst_source = "yfinance_events"
            analyst_stats["source"] = "yfinance_events(auto_fallback)"

    ui_log(f"Effective analyst signal source: {effective_analyst_source}")

    return {
        "prices": prices,
        "price_stats": price_stats,
        "universe": universe,
        "events": events,
        "finnhub_ratings": finnhub_ratings,
        "effective_analyst_source": effective_analyst_source,
        "universe_stats": universe_stats,
        "analyst_stats": analyst_stats,
    }


log_container = st.empty()

if coverage_clicked:
    _save_config(CONFIG_PATH, settings)
    logs: list[str] = []

    def ui_log(message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{timestamp}] {message}")
        log_container.code("\n".join(logs[-300:]))

    try:
        with st.spinner("Checking analyst coverage..."):
            prepared = _prepare_for_backtest_inputs(
                settings=settings,
                finnhub_api_key=finnhub_api_key,
                alpaca_api_key=alpaca_api_key,
                alpaca_api_secret=alpaca_api_secret,
                ui_log=ui_log,
                enforce_coverage=False,
            )
            analyst_stats = prepared["analyst_stats"]
            universe_stats = prepared["universe_stats"]
            price_stats = prepared["price_stats"]
            rows_in_window = int(analyst_stats.get("rows_in_backtest_window", 0) or 0)
            st.session_state["last_coverage"] = {
                "logs": logs,
                "settings": settings,
                "analyst_stats": analyst_stats,
                "universe_stats": universe_stats,
                "price_stats": price_stats,
                "coverage_ok": rows_in_window > 0,
                "error": None,
            }
    except Exception as exc:  # noqa: BLE001
        st.session_state["last_coverage"] = {
            "logs": logs,
            "settings": settings,
            "analyst_stats": None,
            "universe_stats": None,
            "price_stats": None,
            "coverage_ok": False,
            "error": str(exc),
        }
        st.error(f"Coverage check failed: {exc}")

if run_clicked:
    _save_config(CONFIG_PATH, settings)
    logs: list[str] = []

    def ui_log(message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{timestamp}] {message}")
        log_container.code("\n".join(logs[-300:]))

    try:
        with st.spinner("Running backtest..."):
            prepared = _prepare_for_backtest_inputs(
                settings=settings,
                finnhub_api_key=finnhub_api_key,
                alpaca_api_key=alpaca_api_key,
                alpaca_api_secret=alpaca_api_secret,
                ui_log=ui_log,
                enforce_coverage=bool(settings["require_analyst_window_coverage"]),
            )
            prices = prepared["prices"]
            price_stats = prepared["price_stats"]
            universe = prepared["universe"]
            events = prepared["events"]
            finnhub_ratings = prepared["finnhub_ratings"]
            effective_analyst_source = str(
                prepared.get("effective_analyst_source", settings["analyst_source"])
            )
            universe_stats = prepared["universe_stats"]
            analyst_stats = prepared["analyst_stats"]

            benchmark_prices, benchmark_source = get_or_fetch_benchmark_prices(
                local_prices=prices,
                benchmark_ticker=settings["benchmark_ticker"],
                start_date=pd.Timestamp(settings["start_date"]),
                end_date=pd.Timestamp(settings["end_date"]),
                fetch_if_missing=settings["fetch_benchmark_if_missing"],
                cache_dir=".",
                logger=ui_log,
            )
            ui_log(
                f"Benchmark source: {benchmark_source} "
                f"| rows: {len(benchmark_prices):,}"
            )
            effective_bottom_n = int(settings["bottom_n"])
            if bool(settings.get("stress_remove_short_side", False)):
                if effective_bottom_n > 0:
                    ui_log("Stress test enabled: removing short side for this run (bottom_n forced to 0).")
                effective_bottom_n = 0
            if int(settings["top_n"]) == 0 and effective_bottom_n == 0:
                raise ValueError(
                    "No positions left after stress settings. Set Top N > 0 or disable remove-short stress."
                )

            result = run_backtest(
                prices=prices,
                universe=universe,
                events=events,
                start_date=settings["start_date"],
                end_date=settings["end_date"],
                top_n=settings["top_n"],
                bottom_n=effective_bottom_n,
                lookback_days=settings["lookback_days"],
                signal_source=effective_analyst_source,
                ranking_mode=settings["ranking_mode"],
                consistency_weight=settings["consistency_weight"],
                consistency_lookback_months=settings["consistency_lookback_months"],
                consistency_min_observations=settings["consistency_min_observations"],
                signal_lag_months=settings["stress_signal_lag_months"],
                randomize_signals=settings["stress_randomize_signals"],
                random_seed=settings["stress_random_seed"],
                transaction_cost_bps=settings["stress_transaction_cost_bps"],
                short_borrow_cost_bps_monthly=settings["stress_short_borrow_cost_bps_monthly"],
                finnhub_ratings=finnhub_ratings,
                benchmark_prices=benchmark_prices,
                grade_mapping_rules=settings["grade_mapping_rules"],
                action_weights=settings["action_weights"],
                logger=ui_log,
            )
            settings_used = dict(settings)
            settings_used["effective_analyst_source"] = effective_analyst_source

        st.session_state["last_run"] = {
            "result": result,
            "logs": logs,
            "settings": settings_used,
            "analyst_stats": analyst_stats,
            "universe_stats": universe_stats,
            "price_stats": price_stats,
            "prepared_inputs": {
                "prices": prices,
                "universe": universe,
                "events": events,
                "finnhub_ratings": finnhub_ratings,
                "effective_analyst_source": effective_analyst_source,
            },
            "benchmark_source": benchmark_source,
            "error": None,
        }
        st.session_state["recommendation_inputs"] = {
            "prices": prices,
            "universe": universe,
            "events": events,
            "finnhub_ratings": finnhub_ratings,
            "effective_analyst_source": effective_analyst_source,
        }
    except Exception as exc:  # noqa: BLE001
        st.session_state["last_run"] = {
            "result": None,
            "logs": logs,
            "settings": settings,
            "analyst_stats": None,
            "universe_stats": None,
            "price_stats": None,
            "prepared_inputs": None,
            "benchmark_source": None,
            "error": str(exc),
        }
        st.error(f"Run failed: {exc}")

last_run = st.session_state.get("last_run")
last_coverage = st.session_state.get("last_coverage")

if last_coverage is not None:
    st.subheader("Coverage Check")
    if last_coverage.get("error"):
        st.error(last_coverage["error"])
    else:
        analyst_stats = last_coverage.get("analyst_stats") or {}
        universe_stats = last_coverage.get("universe_stats") or {}
        price_stats = last_coverage.get("price_stats") or {}
        coverage_ok = bool(last_coverage.get("coverage_ok"))
        if coverage_ok:
            st.success("Coverage check passed: analyst data overlaps selected backtest window.")
        else:
            st.warning("Coverage check failed: no analyst data overlaps selected backtest window.")
        st.write(
            {
                "universe_source": universe_stats.get("source"),
                "universe_selected_tickers": universe_stats.get("selected_tickers"),
                "price_provider": (last_coverage.get("settings") or {}).get("price_provider"),
                "price_tickers_with_data": price_stats.get("tickers_with_prices"),
                "price_tickers_without_data": price_stats.get("tickers_without_prices"),
                "price_provider_alpaca_success": price_stats.get("alpaca_success"),
                "price_provider_yfinance_success": price_stats.get("yfinance_success"),
                "analyst_source": analyst_stats.get("source"),
                "analyst_rows_selected": analyst_stats.get("cache_rows_selected", analyst_stats.get("cache_rows")),
                "analyst_rows_in_backtest_window": analyst_stats.get("rows_in_backtest_window"),
                "analyst_tickers_in_backtest_window": analyst_stats.get("tickers_with_data_in_backtest_window"),
                "analyst_coverage_check_start": analyst_stats.get("coverage_check_start"),
                "analyst_coverage_check_end": analyst_stats.get("coverage_check_end"),
                "analyst_period_min": analyst_stats.get("period_min"),
                "analyst_period_max": analyst_stats.get("period_max"),
            }
        )
        coverage_logs = last_coverage.get("logs", [])
        if coverage_logs:
            st.code("\n".join(coverage_logs[-200:]))

if last_run is None:
    st.info("Configure settings in the sidebar and click Run backtest.")
else:
    if last_run.get("error"):
        st.error(last_run["error"])

    logs_to_show = last_run.get("logs", [])
    if logs_to_show:
        log_container.code("\n".join(logs_to_show[-300:]))

    result = last_run.get("result")
    if result:
        monthly = result["monthly_results"].copy()
        equity_curve = result["equity_curve"].copy()
        drawdown_curve = result["drawdown_curve"].copy()
        ic_series = result["ic_series"].copy()
        ic_summary = result["ic_summary"]
        consistency_table = result.get("consistency_table", pd.DataFrame()).copy()
        consistency_summary = result.get("consistency_summary", {})
        portfolio_stats = result["portfolio_stats"]
        benchmark_stats = result["benchmark_stats"]
        diagnostics = result["diagnostics"]
        analyst_stats = last_run.get("analyst_stats") or {}

        if (
            diagnostics.get("signal_source") == "finnhub_ratings"
            and int(analyst_stats.get("rows_in_backtest_window", 0) or 0) == 0
        ):
            st.warning(
                "Finnhub ratings in cache do not overlap your backtest dates. "
                "Signals may be mostly zero for this run."
            )

        st.subheader("Summary Stats")
        stat_cols = st.columns(6)
        stat_cols[0].metric("Total Return", _fmt_pct(portfolio_stats.get("total_return")))
        stat_cols[1].metric("CAGR", _fmt_pct(portfolio_stats.get("CAGR")))
        stat_cols[2].metric("Ann Vol", _fmt_pct(portfolio_stats.get("ann_vol")))
        stat_cols[3].metric("Sharpe Approx", _fmt_num(portfolio_stats.get("sharpe_approx")))
        stat_cols[4].metric("Max Drawdown", _fmt_pct(portfolio_stats.get("max_drawdown")))
        stat_cols[5].metric("Hit Rate", _fmt_pct(portfolio_stats.get("hit_rate")))

        settings_used = last_run.get("settings", {})
        export_bytes = _build_results_zip_bytes(result=result, last_run=last_run)
        export_start = str(settings_used.get("start_date", "start")).replace("-", "")
        export_end = str(settings_used.get("end_date", "end")).replace("-", "")
        export_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = f"backtest_results_{export_start}_{export_end}_{export_stamp}.zip"
        st.download_button(
            "Download all results (.zip)",
            data=export_bytes,
            file_name=export_file,
            mime="application/zip",
            use_container_width=True,
        )
        with st.expander("Robustness and Bias Warnings"):
            warnings: list[str] = []
            if float(settings_used.get("stress_transaction_cost_bps", 0.0) or 0.0) <= 0:
                warnings.append(
                    "Transaction costs are set to 0 bps. Stress with 50-100 bps to test cost sensitivity."
                )
            if int(settings_used.get("bottom_n", 0) or 0) > 0 and float(
                settings_used.get("stress_short_borrow_cost_bps_monthly", 0.0) or 0.0
            ) <= 0:
                warnings.append(
                    "Short borrow costs are 0 bps/month. Short-side results may be overstated."
                )
            if int(settings_used.get("stress_signal_lag_months", 0) or 0) == 0:
                warnings.append(
                    "Signal lag is 0 months. Test lag=1 month to reduce timing-leakage risk."
                )
            universe_csv_used = str(settings_used.get("universe_csv", "")).lower()
            if str(settings_used.get("universe_source", "")) == "csv" and (
                "top_1000" in universe_csv_used or "sp500" in universe_csv_used
            ):
                warnings.append(
                    "Universe appears static/current-membership based; survivorship bias is possible."
                )
            if (
                np.isfinite(portfolio_stats.get("sharpe_approx", np.nan))
                and float(portfolio_stats.get("sharpe_approx")) > 2.0
            ) or (
                np.isfinite(portfolio_stats.get("CAGR", np.nan))
                and float(portfolio_stats.get("CAGR")) > 0.50
            ):
                warnings.append(
                    "Very high Sharpe/CAGR detected. Validate with random signals, lag, and higher costs."
                )
            if warnings:
                for warning_text in warnings:
                    st.warning(warning_text)
            else:
                st.success("No major robustness flags triggered by current settings.")

        st.subheader("Next Month Recommendations")
        rec_col1, rec_col2, rec_col3 = st.columns(3)
        default_signal_month = pd.Timestamp(settings_used.get("end_date", datetime.now().date())).normalize()
        default_signal_month = default_signal_month.replace(day=1)
        recommendation_signal_month = rec_col1.date_input(
            "Input month (signal month)",
            value=default_signal_month.date(),
            key="recommendation_signal_month",
            help="Example: input February 2026 to request recommendations for March 2026.",
        )
        recommendation_top_n = rec_col2.number_input(
            "Recommendation Top N",
            min_value=1,
            max_value=1000,
            value=int(settings_used.get("top_n", 10)),
            key="recommendation_top_n",
        )
        recommendation_bottom_n = rec_col3.number_input(
            "Recommendation Bottom N",
            min_value=0,
            max_value=1000,
            value=int(settings_used.get("bottom_n", 0)),
            key="recommendation_bottom_n",
        )
        recommendation_months_ahead = st.number_input(
            "Months ahead",
            min_value=1,
            max_value=6,
            value=2,
            key="recommendation_months_ahead",
            help="How many future portfolio months to generate from the input signal month.",
        )
        rec_btn_col1, rec_btn_col2 = st.columns(2)
        refresh_latest_button = rec_btn_col1.button(
            "Refresh latest data now",
            key="recommendation_refresh_latest_button",
            help="Refresh price + analyst caches before generating recommendations.",
        )
        rec_button = rec_btn_col2.button("Generate next-month picks", key="recommendation_run_button")

        if refresh_latest_button:
            rec_logs: list[str] = []

            def rec_ui_log(message: str) -> None:
                timestamp = datetime.now().strftime("%H:%M:%S")
                rec_logs.append(f"[{timestamp}] {message}")
                log_container.code("\n".join(rec_logs[-300:]))

            try:
                refresh_settings = dict(settings_used)
                refresh_settings["refresh_prices_cache"] = True
                refresh_settings["auto_fetch_missing_prices"] = True
                refresh_settings["auto_fetch_missing_analyst"] = True
                refresh_analyst_source = str(
                    refresh_settings.get("analyst_source", "yfinance_events")
                )
                if refresh_analyst_source == "finnhub_ratings":
                    refresh_settings["refresh_finnhub_ratings_cache"] = True
                elif refresh_analyst_source == "yfinance_events":
                    refresh_settings["refresh_events_cache"] = True
                else:
                    refresh_settings["refresh_finnhub_ratings_cache"] = True
                    refresh_settings["refresh_events_cache"] = True

                with st.spinner("Refreshing latest data for recommendations..."):
                    latest_prepared = _prepare_for_backtest_inputs(
                        settings=refresh_settings,
                        finnhub_api_key=finnhub_api_key,
                        alpaca_api_key=alpaca_api_key,
                        alpaca_api_secret=alpaca_api_secret,
                        ui_log=rec_ui_log,
                        enforce_coverage=False,
                    )
                st.session_state["recommendation_inputs"] = {
                    "prices": latest_prepared["prices"],
                    "universe": latest_prepared["universe"],
                    "events": latest_prepared["events"],
                    "finnhub_ratings": latest_prepared["finnhub_ratings"],
                    "effective_analyst_source": latest_prepared.get(
                        "effective_analyst_source",
                        refresh_settings.get("analyst_source", "yfinance_events"),
                    ),
                }
                st.success("Latest data refreshed. You can now generate recommendations.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Latest data refresh failed: {exc}")

        if rec_button:
            prepared_inputs = (
                st.session_state.get("recommendation_inputs")
                or last_run.get("prepared_inputs")
                or {}
            )
            prices_in = prepared_inputs.get("prices")
            universe_in = prepared_inputs.get("universe")
            events_in = prepared_inputs.get("events")
            finnhub_in = prepared_inputs.get("finnhub_ratings")
            effective_rec_signal_source = str(
                prepared_inputs.get(
                    "effective_analyst_source",
                    settings_used.get(
                        "effective_analyst_source",
                        settings_used.get("analyst_source", "yfinance_events"),
                    ),
                )
            )
            if effective_rec_signal_source not in {"yfinance_events", "finnhub_ratings"}:
                effective_rec_signal_source = "yfinance_events"
            if prices_in is None or universe_in is None or events_in is None:
                st.error("Run a backtest first to prepare inputs for recommendations.")
            else:
                try:
                    effective_rec_bottom_n = int(recommendation_bottom_n)
                    if bool(settings_used.get("stress_remove_short_side", False)):
                        effective_rec_bottom_n = 0
                    recommendation = recommend_next_month(
                        prices=prices_in,
                        universe=universe_in,
                        events=events_in,
                        signal_month=pd.Timestamp(recommendation_signal_month),
                        months_ahead=int(recommendation_months_ahead),
                        top_n=int(recommendation_top_n),
                        bottom_n=int(effective_rec_bottom_n),
                        lookback_days=int(settings_used.get("lookback_days", 90)),
                        signal_source=effective_rec_signal_source,
                        ranking_mode=str(settings_used.get("ranking_mode", "blend_with_consistency")),
                        consistency_weight=float(settings_used.get("consistency_weight", 0.35)),
                        consistency_lookback_months=int(settings_used.get("consistency_lookback_months", 12)),
                        consistency_min_observations=int(settings_used.get("consistency_min_observations", 3)),
                        signal_lag_months=int(settings_used.get("stress_signal_lag_months", 0)),
                        randomize_signals=bool(settings_used.get("stress_randomize_signals", False)),
                        random_seed=int(settings_used.get("stress_random_seed", 42)),
                        transaction_cost_bps=float(settings_used.get("stress_transaction_cost_bps", 0.0)),
                        short_borrow_cost_bps_monthly=float(
                            settings_used.get("stress_short_borrow_cost_bps_monthly", 0.0)
                        ),
                        finnhub_ratings=finnhub_in,
                        grade_mapping_rules=settings_used.get("grade_mapping_rules"),
                        action_weights=settings_used.get("action_weights"),
                    )
                    st.session_state["last_recommendation"] = recommendation
                except Exception as exc:  # noqa: BLE001
                    st.session_state["last_recommendation"] = None
                    st.error(f"Recommendation generation failed: {exc}")

        recommendation_state = st.session_state.get("last_recommendation")
        if recommendation_state:
            rec_signal_month = pd.Timestamp(recommendation_state["signal_month"]).strftime("%Y-%m")
            rec_count = int(recommendation_state.get("months_ahead", 1))
            st.success(
                f"Generated {rec_count} month(s) of recommendations from signal month {rec_signal_month}."
            )
            rec_blocks = recommendation_state.get("recommendations", [])
            rec_rows: list[dict[str, object]] = []
            fallback_months: list[str] = []
            for block in rec_blocks:
                rec_month = pd.Timestamp(block["recommendation_month_requested"]).strftime("%Y-%m")
                signal_month_used = pd.Timestamp(block["signal_month_used"]).strftime("%Y-%m")
                exact_match = bool(block.get("exact_month_match", False))
                if not exact_match:
                    fallback_months.append(rec_month)
                for idx, ticker in enumerate(block.get("longs", []), start=1):
                    rec_rows.append(
                        {
                            "recommendation_month": rec_month,
                            "signal_month_used": signal_month_used,
                            "exact_signal_month_match": exact_match,
                            "side": "LONG",
                            "rank": idx,
                            "ticker": ticker,
                        }
                    )
                for idx, ticker in enumerate(block.get("shorts", []), start=1):
                    rec_rows.append(
                        {
                            "recommendation_month": rec_month,
                            "signal_month_used": signal_month_used,
                            "exact_signal_month_match": exact_match,
                            "side": "SHORT",
                            "rank": idx,
                            "ticker": ticker,
                        }
                    )
            if fallback_months:
                st.warning(
                    "Some requested months used the latest available signal month due data limits: "
                    + ", ".join(sorted(set(fallback_months)))
                )
            rec_df = pd.DataFrame(
                rec_rows,
                columns=[
                    "recommendation_month",
                    "signal_month_used",
                    "exact_signal_month_match",
                    "side",
                    "rank",
                    "ticker",
                ],
            )
            st.dataframe(rec_df, use_container_width=True)
            st.download_button(
                "Download recommendation CSV",
                data=rec_df.to_csv(index=False).encode("utf-8"),
                file_name=f"recommendation_{rec_signal_month}_plus_{rec_count}m.csv",
                mime="text/csv",
                key="recommendation_download_button",
            )

        st.subheader("Equity Curve")
        eq_for_chart = equity_curve.copy().set_index("month")[["portfolio_equity", "benchmark_equity"]]
        st.line_chart(eq_for_chart, use_container_width=True)

        st.subheader("Monthly Returns")
        monthly_chart = monthly.copy().set_index("month")[["portfolio_ret", "benchmark_ret", "excess_ret"]]
        st.bar_chart(monthly_chart, use_container_width=True)

        st.subheader("Drawdown")
        dd_for_chart = drawdown_curve.copy().set_index("month")[["portfolio_drawdown", "benchmark_drawdown"]]
        st.line_chart(dd_for_chart, use_container_width=True)

        st.subheader("Information Coefficient")
        ic_col1, ic_col2, ic_col3, ic_col4 = st.columns(4)
        ic_col1.metric("Mean IC", _fmt_num(ic_summary.get("mean_ic")))
        ic_col2.metric("Median IC", _fmt_num(ic_summary.get("median_ic")))
        ic_col3.metric("Months with IC", str(ic_summary.get("months_with_ic", 0)))
        ic_col4.metric("Mean Base Signal IC", _fmt_num(ic_summary.get("mean_base_signal_ic")))
        if not ic_series.empty:
            st.line_chart(ic_series.set_index("month")[["ic"]], use_container_width=True)
        else:
            st.info("No IC points available.")

        st.subheader("Most Consistent Stocks vs Analyst Calls")
        cs_col1, cs_col2, cs_col3 = st.columns(3)
        cs_col1.metric("Eligible Tickers", str(consistency_summary.get("eligible_tickers", 0)))
        cs_col2.metric("Mean Consistency", _fmt_num(consistency_summary.get("mean_consistency")))
        cs_col3.metric("Median Consistency", _fmt_num(consistency_summary.get("median_consistency")))
        if consistency_table is not None and not consistency_table.empty:
            display_n = int(last_run.get("settings", {}).get("consistency_top_list_n", 25))
            consistency_view = consistency_table.head(display_n).copy()
            consistency_view["consistency_hit_rate"] = consistency_view["consistency_hit_rate"].apply(
                _fmt_pct
            )
            consistency_view["mean_next_month_ret"] = consistency_view["mean_next_month_ret"].apply(
                _fmt_pct
            )
            st.dataframe(consistency_view, use_container_width=True)
        else:
            st.info("No consistency history available yet for selected run.")

        st.subheader("Monthly Results Table")
        filter_col1, filter_col2 = st.columns(2)
        month_filter = filter_col1.text_input("Filter month (YYYY-MM contains)", value="")
        ticker_filter = filter_col2.text_input("Filter ticker in longs/shorts", value="")

        monthly_table = _serialize_monthly_table(monthly)
        if month_filter:
            monthly_table = monthly_table[
                monthly_table["month"].str.contains(month_filter, case=False, na=False)
            ]
        if ticker_filter:
            mask = (
                monthly_table["longs"].str.contains(ticker_filter, case=False, na=False)
                | monthly_table["shorts"].str.contains(ticker_filter, case=False, na=False)
            )
            monthly_table = monthly_table[mask]

        st.dataframe(monthly_table, use_container_width=True)

        with st.expander("Benchmark Stats"):
            st.write(
                {
                    "total_return": _fmt_pct(benchmark_stats.get("total_return")),
                    "CAGR": _fmt_pct(benchmark_stats.get("CAGR")),
                    "ann_vol": _fmt_pct(benchmark_stats.get("ann_vol")),
                    "sharpe_approx": _fmt_num(benchmark_stats.get("sharpe_approx")),
                    "max_drawdown": _fmt_pct(benchmark_stats.get("max_drawdown")),
                    "hit_rate": _fmt_pct(benchmark_stats.get("hit_rate")),
                }
            )

        st.subheader("Logging and Diagnostics")
        analyst_stats = last_run.get("analyst_stats") or {}
        universe_stats = last_run.get("universe_stats") or {}
        price_stats = last_run.get("price_stats") or {}
        st.write(
            {
                "benchmark_source": last_run.get("benchmark_source"),
                "signal_source": diagnostics.get("signal_source"),
                "ranking_mode": diagnostics.get("ranking_mode"),
                "consistency_weight": diagnostics.get("consistency_weight"),
                "consistency_lookback_months": diagnostics.get("consistency_lookback_months"),
                "consistency_min_observations": diagnostics.get("consistency_min_observations"),
                "stress_remove_short_side": settings_used.get("stress_remove_short_side"),
                "stress_randomize_signals": diagnostics.get("randomize_signals"),
                "stress_signal_lag_months": diagnostics.get("signal_lag_months"),
                "stress_transaction_cost_bps": diagnostics.get("transaction_cost_bps"),
                "stress_short_borrow_cost_bps_monthly": diagnostics.get("short_borrow_cost_bps_monthly"),
                "stress_universe_mode_applied": universe_stats.get("stress_universe_mode_applied"),
                "stress_universe_after": universe_stats.get("stress_universe_after"),
                "consistency_tickers_scored": diagnostics.get("consistency_tickers_scored"),
                "consistency_eligible_tickers": diagnostics.get("consistency_eligible_tickers"),
                "missing_price_tickers_total": diagnostics.get("missing_price_tickers_total"),
                "missing_signal_tickers_total": diagnostics.get("missing_signal_tickers_total"),
                "months_total": diagnostics.get("months_total"),
                "months_with_portfolio_return": diagnostics.get("months_with_portfolio_return"),
                "universe_source": universe_stats.get("source"),
                "universe_selected_tickers": universe_stats.get("selected_tickers"),
                "price_tickers_with_data": price_stats.get("tickers_with_prices"),
                "price_tickers_without_data": price_stats.get("tickers_without_prices"),
                "analyst_source": analyst_stats.get("source"),
                "analyst_rows_selected": analyst_stats.get("cache_rows_selected", analyst_stats.get("cache_rows")),
                "analyst_rows_in_backtest_window": analyst_stats.get("rows_in_backtest_window"),
                "analyst_tickers_in_backtest_window": analyst_stats.get("tickers_with_data_in_backtest_window"),
                "analyst_coverage_check_start": analyst_stats.get("coverage_check_start"),
                "analyst_coverage_check_end": analyst_stats.get("coverage_check_end"),
                "analyst_period_min": analyst_stats.get("period_min"),
                "analyst_period_max": analyst_stats.get("period_max"),
                "analyst_tickers_without_data": analyst_stats.get("tickers_without_ratings", analyst_stats.get("tickers_without_events")),
            }
        )

        analyst_errors = analyst_stats.get("errors_df")
        if isinstance(analyst_errors, pd.DataFrame) and not analyst_errors.empty:
            st.caption("Analyst fetch errors (current run)")
            st.dataframe(analyst_errors, use_container_width=True)

        universe_errors = universe_stats.get("errors_df")
        if isinstance(universe_errors, pd.DataFrame) and not universe_errors.empty:
            st.caption("Universe fetch errors (current run)")
            st.dataframe(universe_errors, use_container_width=True)

        if logs_to_show:
            st.code("\n".join(logs_to_show[-300:]))
