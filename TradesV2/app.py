from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from TradesV2.core import (
        TOTAL_INDICATORS,
        backtest,
        build_indicators,
        fetch_alpaca,
        fetch_finnhub,
        fetch_history,
        fetch_snapshot,
        feature_frame,
        safe_float,
        score_series,
        sector_etf,
    )
    from TradesV2.prediction import prediction_from_analogs, simulate_trade_reveal
except ModuleNotFoundError:
    current_dir = Path(__file__).resolve().parent
    root_dir = current_dir.parent
    for path in [str(current_dir), str(root_dir)]:
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        from TradesV2.core import (  # type: ignore
            TOTAL_INDICATORS,
            backtest,
            build_indicators,
            fetch_alpaca,
            fetch_finnhub,
            fetch_history,
            fetch_snapshot,
            feature_frame,
            safe_float,
            score_series,
            sector_etf,
        )
        from TradesV2.prediction import prediction_from_analogs, simulate_trade_reveal  # type: ignore
    except ModuleNotFoundError:
        from core import (  # type: ignore
            TOTAL_INDICATORS,
            backtest,
            build_indicators,
            fetch_alpaca,
            fetch_finnhub,
            fetch_history,
            fetch_snapshot,
            feature_frame,
            safe_float,
            score_series,
            sector_etf,
        )
        from prediction import prediction_from_analogs, simulate_trade_reveal  # type: ignore


def _fmt_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2f}%"


def _fmt_num(value: float | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _build_go_no_go(
    *,
    latest_score: float,
    threshold: float,
    coverage_pct: float,
    prediction: dict[str, object],
    bt_metrics: dict[str, float],
    min_coverage_pct: float,
    min_prediction_score: float,
    min_profit_probability_pct: float,
    min_expected_return_pct: float,
    max_variability_risk_pct: float,
    min_analog_samples: float,
    min_sharpe: float,
    max_drawdown_abs_pct: float,
) -> tuple[str, float, pd.DataFrame]:
    pred_score = safe_float(prediction.get("prediction_score"))
    prob_pct = safe_float(prediction.get("probability_of_profit_pct"))
    exp_ret_pct = safe_float(prediction.get("expected_directional_return_pct"))
    risk_pct = safe_float(prediction.get("return_variability_pct"))
    samples = safe_float(prediction.get("analog_sample_count"))

    sharpe = safe_float(bt_metrics.get("Sharpe"))
    max_dd = safe_float(bt_metrics.get("Max drawdown"))
    max_dd_abs_pct = abs(max_dd * 100.0) if max_dd is not None else None

    checks: list[dict[str, object]] = [
        {
            "Check": "Directional signal active",
            "Rule": f"|score| >= {threshold:.2f}",
            "Actual": f"{latest_score:.2f}",
            "Pass": abs(latest_score) >= float(threshold),
            "Critical": True,
        },
        {
            "Check": "Indicator coverage",
            "Rule": f">= {min_coverage_pct:.1f}%",
            "Actual": f"{coverage_pct:.1f}%",
            "Pass": coverage_pct >= min_coverage_pct,
            "Critical": True,
        },
        {
            "Check": "Prediction score quality",
            "Rule": f">= {min_prediction_score:.1f}",
            "Actual": _fmt_num(pred_score, 2),
            "Pass": pred_score is not None and pred_score >= min_prediction_score,
            "Critical": True,
        },
        {
            "Check": "Profit probability",
            "Rule": f">= {min_profit_probability_pct:.1f}%",
            "Actual": _fmt_pct(prob_pct),
            "Pass": prob_pct is not None and prob_pct >= min_profit_probability_pct,
            "Critical": False,
        },
        {
            "Check": "Expected directional return",
            "Rule": f">= {min_expected_return_pct:.2f}%",
            "Actual": _fmt_pct(exp_ret_pct),
            "Pass": exp_ret_pct is not None and exp_ret_pct >= min_expected_return_pct,
            "Critical": False,
        },
        {
            "Check": "Variability risk cap",
            "Rule": f"<= {max_variability_risk_pct:.2f}%",
            "Actual": _fmt_pct(risk_pct),
            "Pass": risk_pct is not None and risk_pct <= max_variability_risk_pct,
            "Critical": False,
        },
        {
            "Check": "Analog sample depth",
            "Rule": f">= {min_analog_samples:.0f}",
            "Actual": _fmt_num(samples, 0),
            "Pass": samples is not None and samples >= min_analog_samples,
            "Critical": False,
        },
        {
            "Check": "Backtest Sharpe",
            "Rule": f">= {min_sharpe:.2f}",
            "Actual": _fmt_num(sharpe, 2),
            "Pass": sharpe is not None and sharpe >= min_sharpe,
            "Critical": False,
        },
        {
            "Check": "Backtest max drawdown",
            "Rule": f"<= {max_drawdown_abs_pct:.2f}%",
            "Actual": _fmt_pct(max_dd_abs_pct),
            "Pass": max_dd_abs_pct is not None and max_dd_abs_pct <= max_drawdown_abs_pct,
            "Critical": False,
        },
    ]

    total = len(checks)
    passed = sum(1 for x in checks if bool(x["Pass"]))
    pass_ratio = (passed / total) if total > 0 else 0.0
    critical_failed = any((not bool(x["Pass"])) and bool(x["Critical"]) for x in checks)

    if critical_failed or pass_ratio < 0.45:
        decision = "NO-GO"
    elif pass_ratio >= 0.78:
        decision = "GO"
    else:
        decision = "CAUTION"

    out = pd.DataFrame(checks)
    out["Status"] = out["Pass"].map({True: "PASS", False: "FAIL"})
    return decision, pass_ratio * 100.0, out[["Check", "Rule", "Actual", "Status", "Critical"]]


def main() -> None:
    st.set_page_config(page_title="TradesV2 - 250 Indicator Simulator", layout="wide")

    st.title("TradesV2: 250-Indicator Scoring, Simulation, and Prediction")
    st.caption(
        "Walk-forward simulation: trade decision uses data available on the signal date, then compares with future realized move."
    )

    with st.sidebar:
        st.header("Core Inputs")
        manual_ticker = st.text_input("Ticker", value="NVDA").strip().upper()
        start_dt = st.date_input("Start date", value=date(2022, 11, 5), key="v2_start")
        end_dt = st.date_input("End date", value=date(2023, 2, 6), key="v2_end")
        benchmark = st.text_input("Benchmark ticker", value="SPY").strip().upper()
        threshold = st.slider("Signal threshold (score magnitude)", 0.0, 50.0, 10.0, 1.0)
        horizon_bars = st.slider("Prediction/Sim horizon (trading bars)", 5, 120, 20, 1)
        sim_default = min(end_dt - timedelta(days=horizon_bars + 3), end_dt)
        sim_default = max(sim_default, start_dt)
        sim_date = st.date_input(
            "Simulation signal date",
            value=sim_default,
            min_value=start_dt,
            max_value=end_dt,
            key="v2_sim_date",
        )

        st.divider()
        st.header("APIs (Optional)")
        finnhub_key = st.text_input("Finnhub API key", value=os.getenv("FINNHUB_API_KEY", ""), type="password")
        alpaca_key = st.text_input("Alpaca API key", value=os.getenv("ALPACA_API_KEY", ""), type="password")
        alpaca_secret = st.text_input("Alpaca API secret", value=os.getenv("ALPACA_API_SECRET", ""), type="password")

        st.divider()
        st.header("Go / No-Go Rules")
        min_coverage_pct = st.slider("Min coverage (%)", 40.0, 100.0, 75.0, 1.0)
        min_prediction_score = st.slider("Min prediction score (0..100)", 0.0, 100.0, 55.0, 1.0)
        min_profit_probability_pct = st.slider("Min profit probability (%)", 0.0, 100.0, 52.0, 1.0)
        min_expected_return_pct = st.slider("Min expected directional return (%)", -5.0, 10.0, 0.0, 0.1)
        max_variability_risk_pct = st.slider("Max variability risk (%)", 1.0, 30.0, 10.0, 0.5)
        min_analog_samples = st.slider("Min analog samples", 5, 300, 30, 5)
        min_sharpe = st.slider("Min backtest Sharpe", -1.0, 3.0, 0.2, 0.05)
        max_drawdown_abs_pct = st.slider("Max backtest drawdown (%)", 5.0, 80.0, 25.0, 1.0)

        run_btn = st.button("Run Analysis", type="primary")
    active_ticker = manual_ticker

    if not run_btn:
        st.info("Set inputs in the sidebar and click `Run Analysis`.")
        return

    if not active_ticker:
        st.error("Ticker is required.")
        return
    if end_dt <= start_dt:
        st.error("End date must be after start date.")
        return

    lookback = start_dt - timedelta(days=5500)
    with st.spinner("Fetching data and computing 250-indicator score..."):
        prices = fetch_history(active_ticker, lookback, end_dt)
        if prices.empty:
            st.error(f"No price history found for {active_ticker}.")
            return

        benchmark_prices = fetch_history(benchmark, lookback, end_dt)
        features = feature_frame(prices, benchmark_prices if not benchmark_prices.empty else None)
        snapshot = fetch_snapshot(active_ticker)
        finnhub = fetch_finnhub(active_ticker, finnhub_key, end_dt) if finnhub_key else {}
        alpaca = fetch_alpaca(active_ticker, alpaca_key, alpaca_secret) if alpaca_key and alpaca_secret else {}

        benchmark_features = feature_frame(benchmark_prices) if not benchmark_prices.empty else pd.DataFrame()
        sector_symbol = sector_etf(snapshot.get("info", {}))
        sector_prices = fetch_history(sector_symbol, lookback, end_dt) if sector_symbol else pd.DataFrame()
        sector_features = feature_frame(sector_prices) if not sector_prices.empty else pd.DataFrame()

        indicator_df, dynamic_signals, static_signals = build_indicators(
            symbol=active_ticker,
            features=features,
            snapshot=snapshot,
            finnhub=finnhub,
            alpaca=alpaca,
            benchmark_features=benchmark_features,
            sector_features=sector_features,
        )
        mask = (features.index.date >= start_dt) & (features.index.date <= end_dt)
        score_df = score_series(features.loc[mask].index, dynamic_signals, static_signals)
        bt_df, bt_metrics = backtest(features, score_df, start_dt, end_dt, threshold)

    if score_df.empty:
        st.error("No scores were generated for this window.")
        return

    latest = score_df.iloc[-1]
    latest_score = safe_float(latest["score"]) or 0.0
    coverage = safe_float(latest["coverage_pct"]) or 0.0
    available = int(latest.get("available_signals", 0))
    direction = "BUY" if latest_score >= threshold else ("SHORT" if latest_score <= -threshold else "HOLD")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Composite Score (-100..100)", f"{latest_score:.2f}", f"{direction} bias")
    m2.metric("Coverage (count / %)", f"{available}/{TOTAL_INDICATORS}", f"{coverage:.1f}%")
    m3.metric("Ticker", active_ticker)
    m4.metric("Window", f"{start_dt} to {end_dt}")

    prediction = prediction_from_analogs(
        features=features,
        score_df=score_df,
        asof_date=sim_date,
        horizon_bars=horizon_bars,
        threshold=threshold,
    )
    reveal = simulate_trade_reveal(
        features=features,
        score_df=score_df,
        asof_date=sim_date,
        horizon_bars=horizon_bars,
        threshold=threshold,
    )
    decision, decision_conf_pct, decision_df = _build_go_no_go(
        latest_score=latest_score,
        threshold=threshold,
        coverage_pct=coverage,
        prediction=prediction,
        bt_metrics=bt_metrics,
        min_coverage_pct=min_coverage_pct,
        min_prediction_score=min_prediction_score,
        min_profit_probability_pct=min_profit_probability_pct,
        min_expected_return_pct=min_expected_return_pct,
        max_variability_risk_pct=max_variability_risk_pct,
        min_analog_samples=float(min_analog_samples),
        min_sharpe=min_sharpe,
        max_drawdown_abs_pct=max_drawdown_abs_pct,
    )

    tabs = st.tabs(["Prediction & Simulation", "Backtest", "Indicators", "Downloads"])

    with tabs[0]:
        st.subheader("Prediction Score and Historical Trade Simulation")
        st.caption(
            "Prediction score uses only analog setups from dates before the selected signal date. "
            "Then the app reveals what actually happened over the chosen horizon."
        )
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Prediction Score (0..100)", f"{prediction.get('prediction_score', float('nan')):.2f}")
        p2.metric("Profit Probability", _fmt_pct(prediction.get("probability_of_profit_pct")))
        p3.metric("Expected Directional Return", _fmt_pct(prediction.get("expected_directional_return_pct")))
        p4.metric("Return Variability Risk", _fmt_pct(prediction.get("return_variability_pct")))

        g1, g2, g3 = st.columns(3)
        g1.metric("Final Decision", decision)
        g2.metric("Checklist Pass Rate", f"{decision_conf_pct:.1f}%")
        g3.metric("Rules Passed", f"{int((decision_df['Status'] == 'PASS').sum())}/{len(decision_df)}")
        st.caption("Decision combines signal strength, data coverage, prediction quality, risk, and backtest health.")
        st.dataframe(decision_df, use_container_width=True, hide_index=True)

        if reveal:
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Action at Signal Date", str(reveal.get("action", "n/a")))
            r2.metric("Signal Score", f"{float(reveal.get('entry_score', float('nan'))):.2f}")
            r3.metric("Signal Date -> Entry Date", f"{reveal.get('signal_date', 'n/a')} -> {reveal.get('entry_date', 'n/a')}")
            r4.metric("Realized Return (revealed later)", _fmt_pct(reveal.get("realized_return_pct")))
            st.caption(
                f"Trade held for {int(reveal.get('horizon_bars', 0))} bars. "
                f"Entry: {reveal.get('entry_price', float('nan')):.4f} | Exit: {reveal.get('exit_price', float('nan')):.4f}"
                if pd.notna(reveal.get("entry_price")) and pd.notna(reveal.get("exit_price"))
                else "Not enough bars to reveal full trade horizon yet."
            )

        chart = pd.DataFrame(index=score_df["date"])
        chart["Composite Score (-100..100)"] = score_df["score"].values
        chart["Close Price (USD)"] = features["Close"].reindex(score_df["date"]).values
        st.line_chart(chart[["Composite Score (-100..100)"]], height=220)
        st.line_chart(chart[["Close Price (USD)"]], height=220)

    with tabs[1]:
        st.subheader("Walk-Forward Backtest")
        st.caption(
            "Backtest logic: each day, score -> signal (long/short/flat using threshold). "
            "Trade is executed on next bar, daily PnL = position * next-day return."
        )
        st.caption(
            "Strategy equity compounds daily from those PnL values. "
            "Buy-and-hold is the same period using plain daily returns for comparison."
        )
        if bt_df.empty:
            st.warning("No backtest rows available for this window.")
        else:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Strategy Total Return", f"{bt_metrics['Total return'] * 100:.2f}%")
            b2.metric("Buy & Hold Return", f"{bt_metrics['Buy & hold return'] * 100:.2f}%")
            b3.metric("Sharpe (annualized)", f"{bt_metrics['Sharpe']:.2f}")
            b4.metric("Max Drawdown", f"{bt_metrics['Max drawdown'] * 100:.2f}%")

            eq = bt_df.set_index("date")[["strategy_equity", "buy_hold_equity"]]
            eq.columns = ["Strategy Equity (start=1.0)", "BuyHold Equity (start=1.0)"]
            st.line_chart(eq, height=260)

            dd = bt_df.set_index("date")[["strategy_drawdown", "buy_hold_drawdown"]]
            dd.columns = ["Strategy Drawdown", "BuyHold Drawdown"]
            st.area_chart(dd, height=220)

            backtest_table = bt_df.copy()
            backtest_table["strategy_ret"] = backtest_table["strategy_ret"] * 100.0
            backtest_table["buy_hold_ret"] = backtest_table["buy_hold_ret"] * 100.0
            backtest_table = backtest_table.rename(
                columns={
                    "date": "Date",
                    "score": "Score (-100..100)",
                    "position": "Executed Position (-1/0/+1)",
                    "strategy_ret": "Strategy Return (%)",
                    "buy_hold_ret": "BuyHold Return (%)",
                    "strategy_equity": "Strategy Equity",
                    "buy_hold_equity": "BuyHold Equity",
                }
            )
            st.dataframe(
                backtest_table[
                    [
                        "Date",
                        "Score (-100..100)",
                        "Executed Position (-1/0/+1)",
                        "Strategy Return (%)",
                        "BuyHold Return (%)",
                        "Strategy Equity",
                        "BuyHold Equity",
                    ]
                ].tail(200),
                use_container_width=True,
                hide_index=True,
            )

    with tabs[2]:
        st.subheader("250 Indicator Table")
        st.caption(
            f"{int(indicator_df['Available'].sum())}/{TOTAL_INDICATORS} available. "
            "Unavailable indicators remain listed for full transparency."
        )
        summary = (
            indicator_df.groupby("Category", dropna=False)["Available"]
            .agg(["sum", "count"])
            .reset_index()
            .rename(columns={"sum": "Available", "count": "Total"})
        )
        summary["Coverage %"] = 100.0 * summary["Available"] / summary["Total"]
        st.dataframe(summary, use_container_width=True, hide_index=True)
        only_available = st.checkbox("Show only available indicators", value=False)
        table = indicator_df[indicator_df["Available"]].copy() if only_available else indicator_df
        st.dataframe(table, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.subheader("Downloads")
        st.download_button(
            "Indicator Table CSV",
            data=indicator_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{active_ticker}_indicator_table.csv",
            mime="text/csv",
        )
        st.download_button(
            "Score History CSV",
            data=score_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{active_ticker}_score_history.csv",
            mime="text/csv",
        )
        st.download_button(
            "Backtest CSV",
            data=bt_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{active_ticker}_backtest.csv",
            mime="text/csv",
        )


if __name__ == "__main__":
    main()
