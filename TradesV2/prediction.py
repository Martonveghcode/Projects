from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd


def _safe_float(value: Any) -> float | None:
    try:
        out = float(value)
        if np.isfinite(out):
            return out
    except Exception:
        return None
    return None


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = float(np.sum(weights))
    if total <= 0:
        return float(np.nan)
    return float(np.sum(values * weights) / total)


def _weighted_std(values: np.ndarray, weights: np.ndarray) -> float:
    mean = _weighted_mean(values, weights)
    if not np.isfinite(mean):
        return float(np.nan)
    total = float(np.sum(weights))
    if total <= 0:
        return float(np.nan)
    var = float(np.sum(weights * (values - mean) ** 2) / total)
    return float(np.sqrt(max(0.0, var)))


def build_trade_samples(
    features: pd.DataFrame,
    score_df: pd.DataFrame,
    horizon_bars: int,
) -> pd.DataFrame:
    if features.empty or score_df.empty or horizon_bars <= 0:
        return pd.DataFrame()

    prices = features[["Close"]].copy()
    prices["date"] = prices.index
    score = score_df.copy()
    score["date"] = pd.to_datetime(score["date"], errors="coerce")
    merged = score.merge(prices, on="date", how="inner").sort_values("date").reset_index(drop=True)
    if merged.empty:
        return merged

    merged["fwd_close"] = merged["Close"].shift(-horizon_bars)
    merged["fwd_return"] = merged["fwd_close"] / merged["Close"] - 1.0
    merged = merged.dropna(subset=["score", "fwd_return"]).reset_index(drop=True)
    return merged


def prediction_from_analogs(
    features: pd.DataFrame,
    score_df: pd.DataFrame,
    asof_date: date,
    horizon_bars: int = 20,
    threshold: float = 10.0,
) -> dict[str, float | str]:
    samples = build_trade_samples(features, score_df, horizon_bars=horizon_bars)
    if samples.empty:
        return {
            "prediction_score": np.nan,
            "probability_of_profit_pct": np.nan,
            "expected_directional_return_pct": np.nan,
            "return_variability_pct": np.nan,
            "analog_sample_count": 0.0,
            "action": "HOLD",
            "entry_score": np.nan,
            "trend_variance_risk_pct": np.nan,
        }

    asof_ts = pd.Timestamp(asof_date)
    history = samples[samples["date"] < asof_ts].copy()
    if history.empty:
        return {
            "prediction_score": np.nan,
            "probability_of_profit_pct": np.nan,
            "expected_directional_return_pct": np.nan,
            "return_variability_pct": np.nan,
            "analog_sample_count": 0.0,
            "action": "HOLD",
            "entry_score": np.nan,
            "trend_variance_risk_pct": np.nan,
        }

    current_row = samples[samples["date"] <= asof_ts].tail(1)
    if current_row.empty:
        return {
            "prediction_score": np.nan,
            "probability_of_profit_pct": np.nan,
            "expected_directional_return_pct": np.nan,
            "return_variability_pct": np.nan,
            "analog_sample_count": 0.0,
            "action": "HOLD",
            "entry_score": np.nan,
            "trend_variance_risk_pct": np.nan,
        }

    entry_score = float(current_row["score"].iloc[0])
    if entry_score >= threshold:
        direction = 1.0
        action = "LONG"
    elif entry_score <= -threshold:
        direction = -1.0
        action = "SHORT"
    else:
        direction = 0.0
        action = "HOLD"

    band = max(8.0, abs(entry_score) * 0.35)
    analogs = history[(history["score"] - entry_score).abs() <= band].copy()
    if len(analogs) < 40:
        analogs = history[(history["score"] - entry_score).abs() <= band * 1.75].copy()
    if len(analogs) < 20:
        analogs = history.copy()

    distance = (analogs["score"] - entry_score).abs().values
    weights = np.exp(-(distance / max(1.0, band)))

    if direction == 0.0:
        directional = analogs["fwd_return"].abs().values
    else:
        directional = (direction * analogs["fwd_return"].values)

    prob_profit = _weighted_mean((directional > 0).astype(float), weights)
    exp_ret = _weighted_mean(directional, weights)
    var_ret = _weighted_std(directional, weights)

    recent = history.tail(30)
    score_vol = float(recent["score"].diff().std()) if len(recent) > 3 else np.nan
    score_vol_clean = 0.0 if not np.isfinite(score_vol) else max(0.0, score_vol)
    stability = max(0.0, 1.0 - min(1.0, score_vol_clean / 20.0))
    sample_strength = min(1.0, len(analogs) / 120.0)
    risk_penalty = min(1.0, max(0.0, var_ret) / 0.10) if np.isfinite(var_ret) else 1.0
    confidence = sample_strength * stability * (1.0 - 0.55 * risk_penalty)
    confidence = float(np.clip(confidence, 0.0, 1.0))

    # 0..100 score combining edge and confidence.
    edge = 0.0 if not np.isfinite(prob_profit) else (prob_profit - 0.5) * 2.0
    score_bias = float(np.tanh(entry_score / 55.0))
    prediction_score = 50.0 + 30.0 * edge + 20.0 * score_bias
    prediction_score *= (0.55 + 0.45 * confidence)
    prediction_score = float(np.clip(prediction_score, 0.0, 100.0))

    return {
        "prediction_score": prediction_score,
        "probability_of_profit_pct": float(np.clip(prob_profit * 100.0, 0.0, 100.0)) if np.isfinite(prob_profit) else np.nan,
        "expected_directional_return_pct": float(exp_ret * 100.0) if np.isfinite(exp_ret) else np.nan,
        "return_variability_pct": float(var_ret * 100.0) if np.isfinite(var_ret) else np.nan,
        "analog_sample_count": float(len(analogs)),
        "action": action,
        "entry_score": float(entry_score),
        "trend_variance_risk_pct": float(np.clip(var_ret * 100.0, 0.0, 100.0)) if np.isfinite(var_ret) else np.nan,
    }


def simulate_trade_reveal(
    features: pd.DataFrame,
    score_df: pd.DataFrame,
    asof_date: date,
    horizon_bars: int = 20,
    threshold: float = 10.0,
) -> dict[str, float | str]:
    if features.empty or score_df.empty:
        return {}

    scored = score_df.copy()
    scored["date"] = pd.to_datetime(scored["date"], errors="coerce")
    asof_ts = pd.Timestamp(asof_date)
    row = scored[scored["date"] <= asof_ts].tail(1)
    if row.empty:
        return {}

    signal_date = pd.Timestamp(row["date"].iloc[0])
    entry_score = float(row["score"].iloc[0])

    if entry_score >= threshold:
        direction = 1.0
        action = "LONG"
    elif entry_score <= -threshold:
        direction = -1.0
        action = "SHORT"
    else:
        direction = 0.0
        action = "HOLD"

    px = features.copy()
    px["date"] = px.index
    px = px.sort_values("date").reset_index(drop=True)
    signal_idx_series = px.index[px["date"] >= signal_date]
    if len(signal_idx_series) == 0:
        return {}

    signal_idx = int(signal_idx_series[0])
    entry_idx = signal_idx + 1  # next bar execution
    if entry_idx >= len(px):
        return {
            "action": action,
            "entry_score": entry_score,
            "signal_date": signal_date.strftime("%Y-%m-%d"),
            "entry_date": "n/a",
            "exit_date": "n/a",
            "entry_price": np.nan,
            "exit_price": np.nan,
            "realized_return_pct": np.nan,
            "horizon_bars": float(horizon_bars),
        }

    exit_idx = min(len(px) - 1, entry_idx + max(1, horizon_bars))
    entry_date_ts = pd.Timestamp(px.loc[entry_idx, "date"])
    exit_date_ts = pd.Timestamp(px.loc[exit_idx, "date"])
    entry_price = _safe_float(px.loc[entry_idx, "Open"]) or _safe_float(px.loc[entry_idx, "Close"])
    exit_price = _safe_float(px.loc[exit_idx, "Close"])

    realized_pct = np.nan
    if entry_price and entry_price > 0 and exit_price and direction != 0.0:
        raw = (exit_price / entry_price) - 1.0
        realized_pct = raw * direction * 100.0

    return {
        "action": action,
        "entry_score": float(entry_score),
        "signal_date": signal_date.strftime("%Y-%m-%d"),
        "entry_date": entry_date_ts.strftime("%Y-%m-%d"),
        "exit_date": exit_date_ts.strftime("%Y-%m-%d"),
        "entry_price": float(entry_price) if entry_price is not None else np.nan,
        "exit_price": float(exit_price) if exit_price is not None else np.nan,
        "realized_return_pct": float(realized_pct) if np.isfinite(realized_pct) else np.nan,
        "horizon_bars": float(horizon_bars),
    }
