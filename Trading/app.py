from __future__ import annotations

import json
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
from src.backtest import run_backtest
from src.data import (
    get_or_fetch_benchmark_prices,
    load_prices_parquet,
    load_universe_csv,
)

CONFIG_PATH = Path("config.json")

DEFAULT_CONFIG = {
    "prices_parquet": "data_out/prices_top1000_2y_daily.parquet",
    "universe_csv": "data_out/top_1000_tickers.csv",
    "events_cache_path": "ud_events_cache_top1000.csv",
    "start_date": "2024-01-01",
    "end_date": "2025-12-31",
    "top_n": 50,
    "bottom_n": 0,
    "lookback_days": 90,
    "benchmark_ticker": "SPY",
    "fetch_benchmark_if_missing": True,
    "throttle_seconds": 0.05,
    "refresh_events_cache": False,
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


st.set_page_config(
    page_title="True Historical Analyst Backtest",
    page_icon="chart_with_upwards_trend",
    layout="wide",
)

st.title("True Historical Analyst Backtest")
st.caption("Monthly long/short backtest using local parquet prices + free yfinance upgrades/downgrades events.")

config = _load_config(CONFIG_PATH)

if "last_run" not in st.session_state:
    st.session_state["last_run"] = None

with st.sidebar:
    st.header("Settings")

    prices_parquet = st.text_input(
        "Prices parquet file",
        value=config.get("prices_parquet", DEFAULT_CONFIG["prices_parquet"]),
    )
    universe_csv = st.text_input(
        "Universe CSV file (ticker column)",
        value=config.get("universe_csv", DEFAULT_CONFIG["universe_csv"]),
    )
    events_cache_path = st.text_input(
        "Events cache CSV path",
        value=config.get("events_cache_path", DEFAULT_CONFIG["events_cache_path"]),
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

    benchmark_ticker = st.text_input(
        "Benchmark ticker",
        value=str(config.get("benchmark_ticker", "SPY")),
    ).upper()
    fetch_benchmark_if_missing = st.checkbox(
        "Fetch benchmark if missing",
        value=bool(config.get("fetch_benchmark_if_missing", True)),
    )

    throttle_seconds = st.number_input(
        "yfinance fetch throttle (sec)",
        min_value=0.0,
        max_value=5.0,
        value=float(config.get("throttle_seconds", 0.05)),
        step=0.01,
    )
    refresh_events_cache = st.checkbox(
        "Refresh events cache",
        value=bool(config.get("refresh_events_cache", False)),
    )

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

    run_clicked = st.button("Run backtest", type="primary", use_container_width=True)

settings = {
    "prices_parquet": prices_parquet,
    "universe_csv": universe_csv,
    "events_cache_path": events_cache_path,
    "start_date": str(start_date),
    "end_date": str(end_date),
    "top_n": int(top_n),
    "bottom_n": int(bottom_n),
    "lookback_days": int(lookback_days),
    "benchmark_ticker": benchmark_ticker,
    "fetch_benchmark_if_missing": bool(fetch_benchmark_if_missing),
    "throttle_seconds": float(throttle_seconds),
    "refresh_events_cache": bool(refresh_events_cache),
    "grade_mapping_rules": _sanitize_grade_rules(edited_grade_rules),
    "action_weights": {
        "upgrade": float(action_upgrade),
        "downgrade": float(action_downgrade),
        "initiat": float(action_initiation),
        "default": float(action_default),
    },
}

log_container = st.empty()

if run_clicked:
    _save_config(CONFIG_PATH, settings)
    logs: list[str] = []

    def ui_log(message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{timestamp}] {message}")
        log_container.code("\n".join(logs[-300:]))

    try:
        with st.spinner("Running backtest..."):
            ui_log("Loading prices parquet...")
            prices = load_prices_parquet(settings["prices_parquet"])
            ui_log(f"Loaded {len(prices):,} price rows.")

            ui_log("Loading universe CSV...")
            universe = load_universe_csv(settings["universe_csv"])
            ui_log(f"Loaded {len(universe):,} tickers.")

            events, event_stats = ensure_events_cache(
                universe=universe,
                cache_path=settings["events_cache_path"],
                sleep_seconds=settings["throttle_seconds"],
                refresh=settings["refresh_events_cache"],
                logger=ui_log,
            )
            ui_log(
                "Events cache ready. "
                f"Rows: {event_stats['cache_rows']:,}, "
                f"tickers without events: {event_stats['tickers_without_events']}"
            )

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

            result = run_backtest(
                prices=prices,
                universe=universe,
                events=events,
                start_date=settings["start_date"],
                end_date=settings["end_date"],
                top_n=settings["top_n"],
                bottom_n=settings["bottom_n"],
                lookback_days=settings["lookback_days"],
                benchmark_prices=benchmark_prices,
                grade_mapping_rules=settings["grade_mapping_rules"],
                action_weights=settings["action_weights"],
                logger=ui_log,
            )

        st.session_state["last_run"] = {
            "result": result,
            "logs": logs,
            "settings": settings,
            "event_stats": event_stats,
            "benchmark_source": benchmark_source,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        st.session_state["last_run"] = {
            "result": None,
            "logs": logs,
            "settings": settings,
            "event_stats": None,
            "benchmark_source": None,
            "error": str(exc),
        }
        st.error(f"Run failed: {exc}")

last_run = st.session_state.get("last_run")
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
        portfolio_stats = result["portfolio_stats"]
        benchmark_stats = result["benchmark_stats"]
        diagnostics = result["diagnostics"]

        st.subheader("Summary Stats")
        stat_cols = st.columns(6)
        stat_cols[0].metric("Total Return", _fmt_pct(portfolio_stats.get("total_return")))
        stat_cols[1].metric("CAGR", _fmt_pct(portfolio_stats.get("CAGR")))
        stat_cols[2].metric("Ann Vol", _fmt_pct(portfolio_stats.get("ann_vol")))
        stat_cols[3].metric("Sharpe Approx", _fmt_num(portfolio_stats.get("sharpe_approx")))
        stat_cols[4].metric("Max Drawdown", _fmt_pct(portfolio_stats.get("max_drawdown")))
        stat_cols[5].metric("Hit Rate", _fmt_pct(portfolio_stats.get("hit_rate")))

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
        ic_col1, ic_col2, ic_col3 = st.columns(3)
        ic_col1.metric("Mean IC", _fmt_num(ic_summary.get("mean_ic")))
        ic_col2.metric("Median IC", _fmt_num(ic_summary.get("median_ic")))
        ic_col3.metric("Months with IC", str(ic_summary.get("months_with_ic", 0)))
        if not ic_series.empty:
            st.line_chart(ic_series.set_index("month")[["ic"]], use_container_width=True)
        else:
            st.info("No IC points available.")

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
        event_stats = last_run.get("event_stats") or {}
        st.write(
            {
                "benchmark_source": last_run.get("benchmark_source"),
                "missing_price_tickers_total": diagnostics.get("missing_price_tickers_total"),
                "missing_event_tickers_total": diagnostics.get("missing_event_tickers_total"),
                "months_total": diagnostics.get("months_total"),
                "months_with_portfolio_return": diagnostics.get("months_with_portfolio_return"),
                "events_cache_rows": event_stats.get("cache_rows"),
                "events_tickers_without_data": event_stats.get("tickers_without_events"),
            }
        )
        if logs_to_show:
            st.code("\n".join(logs_to_show[-300:]))

