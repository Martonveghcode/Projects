from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import streamlit as st

from fetch_finnhub_analyst_ratings import run_fetch


st.set_page_config(
    page_title="Finnhub Analyst Ratings Fetcher",
    page_icon="bar_chart",
    layout="wide",
)

st.title("Finnhub Analyst Ratings Fetcher")
st.caption(
    "Fetch analyst recommendation trends with rate-limit aware retries. "
    "Choose top N tickers and a target months-back window."
)

if "fetch_logs" not in st.session_state:
    st.session_state["fetch_logs"] = []
if "fetch_result" not in st.session_state:
    st.session_state["fetch_result"] = None
if "fetch_error" not in st.session_state:
    st.session_state["fetch_error"] = None

with st.sidebar:
    st.header("Fetch Settings")
    api_key = st.text_input(
        "Finnhub API key",
        value=os.getenv("FINNHUB_API_KEY", ""),
        type="password",
    )
    mode_ui = st.radio(
        "Mode",
        options=["Normal (all universe tickers)", "Retry only errors CSV tickers"],
        index=0,
    )
    mode = "normal" if mode_ui.startswith("Normal") else "errors"

    universe_csv = st.text_input("Universe CSV path", value="data_out/top_1000_tickers.csv")
    ticker_column = st.text_input("Ticker column", value="ticker")
    errors_source_csv = st.text_input(
        "Errors source CSV (used in retry mode)",
        value="data_out/finnhub_analyst_ratings_errors.csv",
    )

    out_csv = st.text_input("Ratings output CSV", value="data_out/finnhub_analyst_ratings.csv")
    out_parquet = st.text_input(
        "Ratings output Parquet",
        value="data_out/finnhub_analyst_ratings.parquet",
    )
    errors_csv = st.text_input("Run errors CSV", value="data_out/finnhub_analyst_ratings_errors.csv")
    coverage_csv = st.text_input(
        "Coverage report CSV",
        value="data_out/finnhub_analyst_ratings_coverage.csv",
    )

    months_back = st.number_input(
        "Months to keep (e.g. 24)",
        min_value=0,
        value=24,
        step=1,
        help="0 = keep all periods returned by Finnhub.",
    )
    limit = st.number_input(
        "Top N tickers to fetch (0=all)",
        min_value=0,
        value=50,
        step=1,
    )

    sleep_sec = st.number_input("Sleep between tickers (sec)", min_value=0.0, value=0.15, step=0.05)
    retries = st.number_input("HTTP retries (non-rate-limit)", min_value=1, value=3, step=1)
    timeout = st.number_input("Request timeout (sec)", min_value=5, value=20, step=1)
    min_rate_wait = st.number_input(
        "Min wait on rate-limit (sec)",
        min_value=1.0,
        value=30.0,
        step=1.0,
    )
    max_rate_waits = st.number_input(
        "Max rate-limit waits per ticker (0=unlimited)",
        min_value=0,
        value=0,
        step=1,
    )
    max_symbol_attempts = st.number_input(
        "Max attempts per ticker",
        min_value=1,
        value=5,
        step=1,
    )
    retry_round_cooldown_sec = st.number_input(
        "Retry round cooldown (sec)",
        min_value=0.0,
        value=10.0,
        step=1.0,
    )
    overwrite = st.checkbox("Overwrite outputs instead of merge", value=False)

    run_clicked = st.button("Run Fetch", type="primary", use_container_width=True)

log_placeholder = st.empty()

if run_clicked:
    st.session_state["fetch_logs"] = []
    st.session_state["fetch_result"] = None
    st.session_state["fetch_error"] = None

    def ui_log(message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        st.session_state["fetch_logs"].append(f"[{ts}] {message}")
        log_placeholder.code("\n".join(st.session_state["fetch_logs"][-400:]))

    try:
        with st.spinner("Fetching ratings from Finnhub..."):
            result = run_fetch(
                api_key=api_key,
                mode=mode,
                universe_csv=universe_csv,
                ticker_column=ticker_column,
                errors_source_csv=errors_source_csv,
                out_csv=out_csv,
                out_parquet=out_parquet,
                errors_csv=errors_csv,
                coverage_csv=coverage_csv,
                sleep_sec=float(sleep_sec),
                retries=int(retries),
                timeout=int(timeout),
                min_rate_limit_wait_sec=float(min_rate_wait),
                max_rate_limit_waits=int(max_rate_waits),
                max_symbol_attempts=int(max_symbol_attempts),
                retry_round_cooldown_sec=float(retry_round_cooldown_sec),
                months_back=int(months_back),
                limit=int(limit),
                overwrite=bool(overwrite),
                logger=ui_log,
            )
        st.session_state["fetch_result"] = result
    except Exception as exc:  # noqa: BLE001
        st.session_state["fetch_error"] = str(exc)
        st.error(f"Fetch failed: {exc}")

if st.session_state["fetch_error"]:
    st.error(st.session_state["fetch_error"])

if st.session_state["fetch_logs"]:
    log_placeholder.code("\n".join(st.session_state["fetch_logs"][-400:]))

result = st.session_state["fetch_result"]
if result:
    st.subheader("Run Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mode", str(result["mode"]))
    c2.metric("Requested", str(result["requested_tickers"]))
    c3.metric("Success", str(result["success_tickers"]))
    c4.metric("Failed", str(result["failed_tickers"]))

    st.write(
        {
            "ratings_rows": result["ratings_rows"],
            "wrote_main_output": result["wrote_main_output"],
            "output_csv": result["output_csv"],
            "output_parquet": result["output_parquet"],
            "errors_csv": result["errors_csv"],
            "coverage_csv": result.get("coverage_csv"),
        }
    )

    coverage_df = result.get("coverage_df")
    if isinstance(coverage_df, pd.DataFrame) and not coverage_df.empty:
        incomplete_count = int((~coverage_df["coverage_complete"]).sum())
        if incomplete_count > 0:
            st.warning(
                f"{incomplete_count} ticker(s) have less history than requested months_back. "
                "This is usually a data-provider limit."
            )
        st.subheader("Coverage by Ticker")
        st.dataframe(coverage_df, use_container_width=True)

    errors_df = result.get("errors_df")
    if isinstance(errors_df, pd.DataFrame) and not errors_df.empty:
        st.subheader("Failed Tickers")
        st.dataframe(errors_df, use_container_width=True)
    elif isinstance(errors_df, pd.DataFrame):
        st.success("No failed tickers in this run.")
