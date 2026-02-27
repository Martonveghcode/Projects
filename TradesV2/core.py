from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf


INDICATOR_GROUPS: dict[str, list[str]] = {
    "Price & Trend Indicators": [
        "Current stock price",
        "Daily % change",
        "Weekly % change",
        "Monthly % change",
        "Quarterly % change",
        "Year-to-date (YTD) return",
        "1-year return",
        "3-year return",
        "5-year return",
        "10-year return",
        "20-day moving average",
        "50-day moving average",
        "100-day moving average",
        "200-day moving average",
        "Exponential moving average (EMA)",
        "Weighted moving average (WMA)",
        "Moving average convergence divergence (MACD)",
        "MACD signal line",
        "MACD histogram",
        "Relative strength index (RSI)",
        "Stochastic oscillator",
        "Stochastic RSI",
        "Average directional index (ADX)",
        "Parabolic SAR",
        "Bollinger Bands",
        "Bollinger Band width",
        "Ichimoku Cloud",
        "Donchian Channel",
        "Keltner Channel",
        "Commodity channel index (CCI)",
        "Williams %R",
        "Rate of change (ROC)",
        "Momentum indicator",
        "On-balance volume (OBV)",
        "Accumulation/distribution line",
        "Chaikin money flow",
        "Average true range (ATR)",
        "Pivot points",
        "Fibonacci retracement levels",
        "Volume-weighted average price (VWAP)",
    ],
    "Volume & Liquidity Indicators": [
        "Daily trading volume",
        "Average daily volume",
        "Volume change %",
        "Turnover ratio",
        "Free float shares",
        "Float turnover",
        "Bid-ask spread",
        "Market depth",
        "Block trades volume",
        "Insider trading volume",
        "Institutional ownership %",
        "Retail ownership %",
        "Short interest",
        "Short interest ratio (days to cover)",
        "Securities lending rate",
        "Dark pool volume",
        "Relative volume (RVOL)",
        "Liquidity ratio (market based)",
        "Trade count",
        "Order imbalance",
    ],
    "Valuation Metrics": [
        "Market capitalization",
        "Enterprise value (EV)",
        "Price-to-earnings (P/E) ratio",
        "Forward P/E",
        "Trailing P/E",
        "Price-to-book (P/B)",
        "Price-to-sales (P/S)",
        "Price-to-cash flow",
        "EV/EBITDA",
        "EV/Revenue",
        "EV/EBIT",
        "PEG ratio",
        "Dividend yield",
        "Dividend payout ratio",
        "Dividend growth rate",
        "Earnings yield",
        "Book value per share",
        "Tangible book value",
        "Revenue per share",
        "Free cash flow yield",
    ],
    "Profitability Metrics": [
        "Revenue",
        "Revenue growth rate",
        "Gross profit",
        "Gross margin",
        "Operating income",
        "Operating margin",
        "EBITDA",
        "EBITDA margin",
        "Net income",
        "Net margin",
        "Earnings per share (EPS)",
        "Diluted EPS",
        "Return on equity (ROE)",
        "Return on assets (ROA)",
        "Return on invested capital (ROIC)",
        "Return on capital employed (ROCE)",
        "Cost of goods sold (COGS)",
        "SG&A expense",
        "R&D expense",
        "Interest expense",
    ],
    "Balance Sheet Metrics": [
        "Total assets",
        "Total liabilities",
        "Total equity",
        "Debt-to-equity ratio",
        "Debt-to-assets ratio",
        "Net debt",
        "Current ratio",
        "Quick ratio",
        "Cash ratio",
        "Working capital",
        "Inventory turnover",
        "Receivables turnover",
        "Payables turnover",
        "Asset turnover",
        "Goodwill",
        "Intangible assets",
        "Long-term debt",
        "Short-term debt",
        "Deferred revenue",
        "Shareholders' equity growth",
    ],
    "Cash Flow Indicators": [
        "Operating cash flow",
        "Investing cash flow",
        "Financing cash flow",
        "Free cash flow",
        "Capital expenditures (CapEx)",
        "Free cash flow growth",
        "Cash conversion cycle",
        "Cash flow per share",
        "Dividend coverage ratio",
        "Interest coverage ratio",
    ],
    "Risk & Volatility Measures": [
        "Beta",
        "Alpha",
        "Standard deviation",
        "Historical volatility",
        "Implied volatility",
        "Sharpe ratio",
        "Sortino ratio",
        "Treynor ratio",
        "Value at risk (VaR)",
        "Conditional VaR",
        "Downside deviation",
        "Maximum drawdown",
        "Correlation with index",
        "Tracking error",
        "Information ratio",
    ],
    "Market & Sector Context": [
        "Sector performance",
        "Industry performance",
        "Index inclusion",
        "Relative strength vs index",
        "Relative strength vs sector",
        "Market share",
        "Competitive positioning index",
        "Analyst rating consensus",
        "Target price",
        "Earnings surprise",
        "Revenue surprise",
        "Guidance revisions",
        "Earnings revisions trend",
        "Insider buying/selling",
        "ESG score",
    ],
    "Corporate Actions": [
        "Stock splits",
        "Reverse splits",
        "Share buybacks",
        "Secondary offerings",
        "Dividend announcements",
        "Mergers & acquisitions",
        "Spin-offs",
        "IPO date",
        "Lock-up expiration",
        "Management changes",
    ],
    "Macroeconomic Exposure": [
        "Interest rate sensitivity",
        "Inflation sensitivity",
        "Currency exposure",
        "GDP sensitivity",
        "Commodity price sensitivity",
        "Credit spread sensitivity",
        "Consumer confidence index impact",
        "Purchasing Managers' Index (PMI) sensitivity",
        "Unemployment rate exposure",
        "Regulatory risk index",
    ],
    "Derivatives & Options Metrics": [
        "Options volume",
        "Open interest",
        "Put/call ratio",
        "Implied volatility skew",
        "Implied volatility rank",
        "Gamma exposure",
        "Delta exposure",
        "Vega exposure",
        "Theta decay",
        "Max pain level",
    ],
    "Credit & Fixed Income Indicators": [
        "Credit rating",
        "Credit default swap (CDS) spread",
        "Bond yield",
        "Yield to maturity",
        "Yield spread vs Treasuries",
        "Bond duration",
        "Convexity",
        "Interest coverage trend",
        "Refinancing risk",
        "Debt maturity schedule",
    ],
    "Sentiment & Alternative Data": [
        "News sentiment score",
        "Social media sentiment",
        "Google search trends",
        "Website traffic",
        "App downloads",
        "Customer reviews score",
        "Employee satisfaction score",
        "Glassdoor rating",
        "Supply chain disruption index",
        "Patent filings",
    ],
    "Growth & Forward Indicators": [
        "Backlog orders",
        "Contract wins",
        "Pipeline value",
        "Customer acquisition rate",
        "Churn rate",
        "Lifetime value (LTV)",
        "LTV/CAC ratio",
        "Same-store sales",
        "User growth",
        "ARPU (average revenue per user)",
    ],
    "Ownership & Structure": [
        "Shares outstanding",
        "Float percentage",
        "Insider ownership",
        "Institutional ownership",
        "ETF ownership",
        "Top 10 holders concentration",
        "Foreign ownership",
        "Voting rights structure",
        "Dual-class share structure",
        "Treasury shares",
    ],
    "Performance Benchmarks": [
        "CAGR (compound annual growth rate)",
        "Rolling returns",
        "Earnings consistency",
        "Revenue consistency",
        "Profit volatility",
        "Operating leverage",
        "Financial leverage",
        "Break-even point",
        "Margin stability",
        "Dividend consistency",
    ],
    "Miscellaneous Indicators": [
        "Analyst coverage count",
        "Short squeeze potential",
        "Price gap frequency",
        "Insider lock-ups",
        "Litigation risk",
        "Tax rate",
        "Deferred tax assets",
        "Off-balance sheet liabilities",
        "Corporate governance score",
        "Sustainability reporting score",
    ],
}

ALL_INDICATORS: list[tuple[str, str]] = [
    (category, name)
    for category, names in INDICATOR_GROUPS.items()
    for name in names
]
TOTAL_INDICATORS = len(ALL_INDICATORS)

SECTOR_ETF_MAP = {
    "basic materials": "XLB",
    "communication services": "XLC",
    "consumer cyclical": "XLY",
    "consumer defensive": "XLP",
    "energy": "XLE",
    "financial services": "XLF",
    "healthcare": "XLV",
    "industrials": "XLI",
    "real estate": "XLRE",
    "technology": "XLK",
    "utilities": "XLU",
}


def safe_float(value: Any) -> float | None:
    try:
        out = float(value)
        if np.isfinite(out):
            return out
    except Exception:
        return None
    return None


def clip(value: float | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(np.clip(value, -1.0, 1.0))


def tanh(value: float | pd.Series | None, scale: float = 1.0) -> float | pd.Series | None:
    if scale == 0:
        return None
    if isinstance(value, pd.Series):
        return np.tanh(value / scale).clip(-1.0, 1.0)
    if value is None or not np.isfinite(value):
        return None
    return clip(float(np.tanh(value / scale)))


def pct(current: float | None, prev: float | None) -> float | None:
    if current is None or prev is None or prev == 0:
        return None
    return (current / prev) - 1.0


def to_pct(value: float | None) -> float | None:
    return value * 100.0 if value is not None else None


def normalize(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def find_row(frame: pd.DataFrame | None, options: list[str]) -> pd.Series | None:
    if frame is None or frame.empty:
        return None
    labels = [str(x) for x in frame.index]
    nmap = {normalize(x): x for x in labels}
    for opt in options:
        key = normalize(opt)
        if key in nmap:
            s = pd.to_numeric(frame.loc[nmap[key]], errors="coerce").dropna()
            return s if not s.empty else None
    for opt in options:
        key = normalize(opt)
        for lbl in labels:
            if key in normalize(lbl):
                s = pd.to_numeric(frame.loc[lbl], errors="coerce").dropna()
                return s if not s.empty else None
    return None


def latest_prev(frame: pd.DataFrame | None, options: list[str]) -> tuple[float | None, float | None]:
    row = find_row(frame, options)
    if row is None or row.empty:
        return None, None
    values = row.dropna()
    curr = safe_float(values.iloc[0]) if len(values) else None
    prev = safe_float(values.iloc[1]) if len(values) > 1 else None
    return curr, prev


def rolling_wma(series: pd.Series, window: int) -> pd.Series:
    weights = np.arange(1, window + 1, dtype=float)
    return series.rolling(window).apply(lambda v: float(np.dot(v, weights) / weights.sum()), raw=True)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat(
        [(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100.0 * pd.Series(plus_dm, index=high.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    minus_di = 100.0 * pd.Series(minus_dm, index=high.index).ewm(alpha=1 / period, adjust=False).mean() / atr
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean()


def psar(high: pd.Series, low: pd.Series, step: float = 0.02, max_step: float = 0.2) -> pd.Series:
    out = pd.Series(index=high.index, dtype=float)
    if high.empty:
        return out
    bull = True
    af = step
    ep = high.iloc[0]
    out.iloc[0] = low.iloc[0]
    for i in range(1, len(high)):
        prev = out.iloc[i - 1]
        if bull:
            val = prev + af * (ep - prev)
            val = min(val, low.iloc[i - 1], low.iloc[i - 2] if i > 1 else low.iloc[i - 1])
            if low.iloc[i] < val:
                bull = False
                val = ep
                ep = low.iloc[i]
                af = step
            elif high.iloc[i] > ep:
                ep = high.iloc[i]
                af = min(max_step, af + step)
        else:
            val = prev + af * (ep - prev)
            val = max(val, high.iloc[i - 1], high.iloc[i - 2] if i > 1 else high.iloc[i - 1])
            if high.iloc[i] > val:
                bull = True
                val = ep
                ep = high.iloc[i]
                af = step
            elif low.iloc[i] < ep:
                ep = low.iloc[i]
                af = min(max_step, af + step)
        out.iloc[i] = val
    return out


@st.cache_data(show_spinner=False, ttl=900)
def fetch_history(symbol: str, start_dt: date, end_dt: date) -> pd.DataFrame:
    try:
        tk = yf.Ticker(symbol)
        hist = tk.history(
            start=start_dt.strftime("%Y-%m-%d"),
            end=(end_dt + timedelta(days=1)).strftime("%Y-%m-%d"),
            auto_adjust=False,
            actions=True,
        )
    except Exception:
        return pd.DataFrame()
    if hist is None or hist.empty:
        return pd.DataFrame()
    out = hist.copy()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out = out.sort_index()
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_snapshot(symbol: str) -> dict[str, Any]:
    tk = yf.Ticker(symbol)
    data: dict[str, Any] = {
        "info": {},
        "financials": pd.DataFrame(),
        "quarterly_financials": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "quarterly_balance_sheet": pd.DataFrame(),
        "cashflow": pd.DataFrame(),
        "dividends": pd.Series(dtype=float),
        "splits": pd.Series(dtype=float),
        "institutional_holders": pd.DataFrame(),
        "major_holders": pd.DataFrame(),
        "calls": pd.DataFrame(),
        "puts": pd.DataFrame(),
        "expiry": None,
    }
    try:
        info = tk.info
        if isinstance(info, dict):
            data["info"] = info
    except Exception:
        pass
    for key, attr in [
        ("financials", "financials"),
        ("quarterly_financials", "quarterly_financials"),
        ("balance_sheet", "balance_sheet"),
        ("quarterly_balance_sheet", "quarterly_balance_sheet"),
        ("cashflow", "cashflow"),
        ("dividends", "dividends"),
        ("splits", "splits"),
        ("institutional_holders", "institutional_holders"),
        ("major_holders", "major_holders"),
    ]:
        try:
            val = getattr(tk, attr)
            if val is not None:
                data[key] = val
        except Exception:
            pass
    try:
        exps = tk.options
        if exps:
            chain = tk.option_chain(exps[0])
            data["expiry"] = exps[0]
            data["calls"] = chain.calls if chain and chain.calls is not None else pd.DataFrame()
            data["puts"] = chain.puts if chain and chain.puts is not None else pd.DataFrame()
    except Exception:
        pass
    return data


def finnhub_get(endpoint: str, params: dict[str, Any], key: str) -> Any:
    if not key:
        return None
    url = f"https://finnhub.io/api/v1/{endpoint.lstrip('/')}"
    q = dict(params)
    q["token"] = key
    try:
        r = requests.get(url, params=q, timeout=12)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


@st.cache_data(show_spinner=False, ttl=900)
def fetch_finnhub(symbol: str, key: str, end_dt: date) -> dict[str, Any]:
    if not key:
        return {}
    from_dt = (end_dt - timedelta(days=365)).strftime("%Y-%m-%d")
    to_dt = end_dt.strftime("%Y-%m-%d")
    return {
        "recommendation": finnhub_get("stock/recommendation", {"symbol": symbol}, key),
        "price_target": finnhub_get("stock/price-target", {"symbol": symbol}, key),
        "earnings": finnhub_get("stock/earnings", {"symbol": symbol, "limit": 4}, key),
        "news": finnhub_get("news-sentiment", {"symbol": symbol}, key),
        "social": finnhub_get("stock/social-sentiment", {"symbol": symbol}, key),
        "insider_sentiment": finnhub_get(
            "stock/insider-sentiment", {"symbol": symbol, "from": from_dt, "to": to_dt}, key
        ),
        "insider_transactions": finnhub_get(
            "stock/insider-transactions", {"symbol": symbol, "from": from_dt, "to": to_dt}, key
        ),
        "metric": finnhub_get("stock/metric", {"symbol": symbol, "metric": "all"}, key),
        "esg": finnhub_get("stock/esg", {"symbol": symbol}, key),
        "sp500": finnhub_get("index/constituents", {"symbol": "^GSPC"}, key),
    }


@st.cache_data(show_spinner=False, ttl=300)
def fetch_alpaca(symbol: str, api_key: str, api_secret: str) -> dict[str, Any]:
    if not api_key or not api_secret:
        return {}
    h = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
    out: dict[str, Any] = {}
    try:
        q = requests.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/quotes/latest", headers=h, timeout=10)
        if q.status_code == 200:
            out["quote"] = q.json().get("quote", {})
    except Exception:
        pass
    try:
        t = requests.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/trades/latest", headers=h, timeout=10)
        if t.status_code == 200:
            out["trade"] = t.json().get("trade", {})
    except Exception:
        pass
    return out


def feature_frame(prices: pd.DataFrame, benchmark: pd.DataFrame | None = None) -> pd.DataFrame:
    if prices.empty:
        return prices.copy()
    df = prices.copy()
    c = df["Close"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]
    df["ret1"] = c.pct_change()
    df["ret5"] = c.pct_change(5)
    df["ret21"] = c.pct_change(21)
    df["ret63"] = c.pct_change(63)
    df["ret252"] = c.pct_change(252)
    df["ret756"] = c.pct_change(756)
    df["ret1260"] = c.pct_change(1260)
    df["ret2520"] = c.pct_change(2520)
    ytd_start = c.groupby(df.index.year).transform("first")
    df["retytd"] = c / ytd_start - 1.0

    df["sma20"] = c.rolling(20).mean()
    df["sma50"] = c.rolling(50).mean()
    df["sma100"] = c.rolling(100).mean()
    df["sma200"] = c.rolling(200).mean()
    df["ema20"] = c.ewm(span=20, adjust=False).mean()
    df["wma20"] = rolling_wma(c, 20)

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    delta = c.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    rs = up.ewm(alpha=1 / 14, adjust=False).mean() / down.ewm(alpha=1 / 14, adjust=False).mean().replace(0, np.nan)
    df["rsi"] = 100.0 - 100.0 / (1 + rs)
    hh14 = h.rolling(14).max()
    ll14 = l.rolling(14).min()
    df["stoch"] = 100.0 * (c - ll14) / (hh14 - ll14).replace(0, np.nan)
    rmin = df["rsi"].rolling(14).min()
    rmax = df["rsi"].rolling(14).max()
    df["stoch_rsi"] = 100.0 * (df["rsi"] - rmin) / (rmax - rmin).replace(0, np.nan)
    df["adx"] = adx(h, l, c, 14)
    df["psar"] = psar(h, l)

    bbm = c.rolling(20).mean()
    bbs = c.rolling(20).std()
    df["bb_up"] = bbm + 2 * bbs
    df["bb_dn"] = bbm - 2 * bbs
    df["bb_width"] = (df["bb_up"] - df["bb_dn"]) / bbm.replace(0, np.nan)
    df["bb_pos"] = (c - df["bb_dn"]) / (df["bb_up"] - df["bb_dn"]).replace(0, np.nan)

    tenkan = (h.rolling(9).max() + l.rolling(9).min()) / 2
    kijun = (h.rolling(26).max() + l.rolling(26).min()) / 2
    senkou_a = ((tenkan + kijun) / 2).shift(26)
    senkou_b = ((h.rolling(52).max() + l.rolling(52).min()) / 2).shift(26)
    cloud_mid = (senkou_a + senkou_b) / 2
    cloud_w = (senkou_a - senkou_b).abs().replace(0, np.nan)
    df["ichimoku_pos"] = (c - cloud_mid) / cloud_w

    dch = h.rolling(20).max()
    dcl = l.rolling(20).min()
    df["donchian_pos"] = (c - dcl) / (dch - dcl).replace(0, np.nan)

    tr = pd.concat([(h - l), (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()
    df["atr_pct"] = df["atr"] / c.replace(0, np.nan)
    kmid = c.ewm(span=20, adjust=False).mean()
    kup = kmid + 2 * df["atr"]
    kdn = kmid - 2 * df["atr"]
    df["keltner_pos"] = (c - kdn) / (kup - kdn).replace(0, np.nan)

    tp = (h + l + c) / 3
    sma_tp = tp.rolling(20).mean()
    mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df["cci"] = (tp - sma_tp) / (0.015 * mad).replace(0, np.nan)
    df["williams_r"] = -100 * (hh14 - c) / (hh14 - ll14).replace(0, np.nan)
    df["roc"] = c.pct_change(12)
    df["mom"] = c - c.shift(10)

    direction = np.sign(c.diff()).fillna(0)
    df["obv"] = (direction * v.fillna(0)).cumsum()
    df["obv_slope"] = df["obv"].diff(20)
    mfm = ((c - l) - (h - c)) / (h - l).replace(0, np.nan)
    mfv = mfm.fillna(0) * v.fillna(0)
    df["adl"] = mfv.cumsum()
    df["adl_slope"] = df["adl"].diff(20)
    df["cmf"] = mfv.rolling(20).sum() / v.rolling(20).sum().replace(0, np.nan)
    df["pivot"] = (h.shift(1) + l.shift(1) + c.shift(1)) / 3
    fib_h = h.rolling(252).max()
    fib_l = l.rolling(252).min()
    df["fib_pos"] = (c - fib_l) / (fib_h - fib_l).replace(0, np.nan)
    df["vwap"] = (tp * v).cumsum() / v.replace(0, np.nan).cumsum()

    df["avg_vol"] = v.rolling(20).mean()
    df["vol_chg"] = v.pct_change()
    df["rvol"] = v / df["avg_vol"].replace(0, np.nan)
    df["dollar_vol"] = c * v
    df["drawdown"] = (1 + df["ret1"].fillna(0)).cumprod()
    df["drawdown"] = df["drawdown"] / df["drawdown"].cummax() - 1
    df["max_dd"] = df["drawdown"].expanding().min()

    if benchmark is not None and not benchmark.empty:
        b = benchmark["Close"].reindex(df.index).ffill()
        br = b.pct_change()
        win = 126
        cov = df["ret1"].rolling(win).cov(br)
        var = br.rolling(win).var()
        beta = cov / var.replace(0, np.nan)
        diff = df["ret1"] - br
        std = df["ret1"].rolling(win).std()
        te = diff.rolling(win).std() * np.sqrt(252)
        df["beta"] = beta
        df["alpha"] = (df["ret1"].rolling(win).mean() - beta * br.rolling(win).mean()) * 252
        df["std"] = std
        df["hist_vol"] = std * np.sqrt(252)
        down_dev = df["ret1"].where(df["ret1"] < 0, 0).rolling(win).std() * np.sqrt(252)
        df["down_dev"] = down_dev
        df["sharpe"] = (df["ret1"].rolling(win).mean() * 252) / (std * np.sqrt(252)).replace(0, np.nan)
        df["sortino"] = (df["ret1"].rolling(win).mean() * 252) / down_dev.replace(0, np.nan)
        df["treynor"] = (df["ret1"].rolling(win).mean() * 252) / beta.replace(0, np.nan)
        df["var95"] = df["ret1"].rolling(win).quantile(0.05)
        df["cvar95"] = df["ret1"].rolling(win).apply(lambda x: x[x <= np.quantile(x, 0.05)].mean(), raw=False)
        df["corr"] = df["ret1"].rolling(win).corr(br)
        df["track_err"] = te
        df["info_ratio"] = (diff.rolling(win).mean() * 252) / te.replace(0, np.nan)
        df["rel_strength_idx"] = df["ret63"] - b.pct_change(63)
    return df


def fmt(value: Any, unit: str | None = None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, (float, int, np.floating, np.integer)):
        x = float(value)
        if not np.isfinite(x):
            return "n/a"
        if unit == "%":
            return f"{x:.2f}%"
        if abs(x) >= 1_000_000_000:
            return f"{x / 1_000_000_000:.2f}B"
        if abs(x) >= 1_000_000:
            return f"{x / 1_000_000:.2f}M"
        if abs(x) >= 1_000:
            return f"{x:,.2f}"
        if abs(x) >= 1:
            return f"{x:.4f}"
        return f"{x:.6f}"
    return str(value)


def register(
    store: dict[tuple[str, str], dict[str, Any]],
    category: str,
    name: str,
    value: Any,
    signal: float | None,
    source: str,
    unit: str | None = None,
    note: str = "",
) -> None:
    if value is None:
        return
    sig = clip(signal)
    store[(category, name)] = {
        "value": value,
        "signal": sig,
        "source": source,
        "unit": unit,
        "note": note,
    }


def max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float | None:
    if calls is None or puts is None or calls.empty or puts.empty:
        return None
    c = calls.copy()
    p = puts.copy()
    for f in [c, p]:
        for col in ["strike", "openInterest"]:
            if col not in f.columns:
                return None
            f[col] = pd.to_numeric(f[col], errors="coerce")
        f.dropna(subset=["strike", "openInterest"], inplace=True)
    if c.empty or p.empty:
        return None
    strikes = np.sort(np.unique(np.concatenate([c["strike"].values, p["strike"].values])))
    best = None
    best_loss = None
    for s in strikes:
        call_loss = ((c["strike"] - s).clip(lower=0) * c["openInterest"]).sum()
        put_loss = ((s - p["strike"]).clip(lower=0) * p["openInterest"]).sum()
        loss = call_loss + put_loss
        if best_loss is None or loss < best_loss:
            best_loss = loss
            best = s
    return safe_float(best)


def build_indicators(
    symbol: str,
    features: pd.DataFrame,
    snapshot: dict[str, Any],
    finnhub: dict[str, Any],
    alpaca: dict[str, Any],
    benchmark_features: pd.DataFrame,
    sector_features: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[tuple[str, str], pd.Series], dict[tuple[str, str], float]]:
    reg: dict[tuple[str, str], dict[str, Any]] = {}
    dynamic_signals: dict[tuple[str, str], pd.Series] = {}
    static_signals: dict[tuple[str, str], float] = {}
    if features.empty:
        return pd.DataFrame(), dynamic_signals, static_signals

    info = snapshot.get("info", {}) or {}
    financials = snapshot.get("financials", pd.DataFrame())
    q_financials = snapshot.get("quarterly_financials", pd.DataFrame())
    bs = snapshot.get("balance_sheet", pd.DataFrame())
    cf = snapshot.get("cashflow", pd.DataFrame())
    dividends = snapshot.get("dividends", pd.Series(dtype=float))
    splits = snapshot.get("splits", pd.Series(dtype=float))
    calls = snapshot.get("calls", pd.DataFrame())
    puts = snapshot.get("puts", pd.DataFrame())

    last = features.iloc[-1]
    close = safe_float(last.get("Close"))
    ret63 = safe_float(last.get("ret63"))

    def add_dyn(cat: str, name: str, value_series: pd.Series, signal_series: pd.Series, src: str, unit: str | None = None) -> None:
        key = (cat, name)
        dynamic_signals[key] = signal_series.astype(float).clip(-1, 1)
        lv = safe_float(value_series.dropna().iloc[-1]) if not value_series.dropna().empty else None
        ls = safe_float(signal_series.dropna().iloc[-1]) if not signal_series.dropna().empty else None
        register(reg, cat, name, lv, ls, src, unit)

    c = "Price & Trend Indicators"
    add_dyn(c, "Current stock price", features["Close"], tanh((features["Close"] / features["sma50"] - 1.0) / 0.05), "yfinance")
    add_dyn(c, "Daily % change", features["ret1"] * 100, tanh(features["ret1"] / 0.02), "yfinance", "%")
    add_dyn(c, "Weekly % change", features["ret5"] * 100, tanh(features["ret5"] / 0.04), "yfinance", "%")
    add_dyn(c, "Monthly % change", features["ret21"] * 100, tanh(features["ret21"] / 0.08), "yfinance", "%")
    add_dyn(c, "Quarterly % change", features["ret63"] * 100, tanh(features["ret63"] / 0.12), "yfinance", "%")
    add_dyn(c, "Year-to-date (YTD) return", features["retytd"] * 100, tanh(features["retytd"] / 0.20), "yfinance", "%")
    add_dyn(c, "1-year return", features["ret252"] * 100, tanh(features["ret252"] / 0.25), "yfinance", "%")
    add_dyn(c, "3-year return", features["ret756"] * 100, tanh(features["ret756"] / 0.40), "yfinance", "%")
    add_dyn(c, "5-year return", features["ret1260"] * 100, tanh(features["ret1260"] / 0.60), "yfinance", "%")
    add_dyn(c, "10-year return", features["ret2520"] * 100, tanh(features["ret2520"] / 1.00), "yfinance", "%")
    add_dyn(c, "20-day moving average", features["sma20"], tanh((features["Close"] / features["sma20"] - 1.0) / 0.03), "yfinance")
    add_dyn(c, "50-day moving average", features["sma50"], tanh((features["Close"] / features["sma50"] - 1.0) / 0.05), "yfinance")
    add_dyn(c, "100-day moving average", features["sma100"], tanh((features["Close"] / features["sma100"] - 1.0) / 0.07), "yfinance")
    add_dyn(c, "200-day moving average", features["sma200"], tanh((features["Close"] / features["sma200"] - 1.0) / 0.10), "yfinance")
    add_dyn(c, "Exponential moving average (EMA)", features["ema20"], tanh((features["Close"] / features["ema20"] - 1.0) / 0.04), "yfinance")
    add_dyn(c, "Weighted moving average (WMA)", features["wma20"], tanh((features["Close"] / features["wma20"] - 1.0) / 0.04), "yfinance")
    add_dyn(c, "Moving average convergence divergence (MACD)", features["macd"], tanh(features["macd"] / (features["Close"] * 0.02)), "yfinance")
    add_dyn(c, "MACD signal line", features["macd_signal"], tanh(features["macd_signal"] / (features["Close"] * 0.02)), "yfinance")
    add_dyn(c, "MACD histogram", features["macd_hist"], tanh(features["macd_hist"] / (features["Close"] * 0.01)), "yfinance")
    add_dyn(c, "Relative strength index (RSI)", features["rsi"], ((features["rsi"] - 50.0) / 25.0).clip(-1, 1), "yfinance")
    add_dyn(c, "Stochastic oscillator", features["stoch"], ((features["stoch"] - 50.0) / 25.0).clip(-1, 1), "yfinance")
    add_dyn(c, "Stochastic RSI", features["stoch_rsi"], ((features["stoch_rsi"] - 50.0) / 25.0).clip(-1, 1), "yfinance")
    add_dyn(c, "Average directional index (ADX)", features["adx"], (np.sign(features["Close"] - features["sma50"]) * (features["adx"] / 40)).clip(-1, 1), "yfinance")
    add_dyn(c, "Parabolic SAR", features["psar"], np.sign(features["Close"] - features["psar"]).clip(-1, 1), "yfinance")
    add_dyn(c, "Bollinger Bands", features["bb_pos"] * 100, ((features["bb_pos"] - 0.5) / 0.3).clip(-1, 1), "yfinance")
    add_dyn(c, "Bollinger Band width", features["bb_width"] * 100, tanh(-(features["bb_width"] - features["bb_width"].rolling(126).mean()) / 0.15), "yfinance", "%")
    add_dyn(c, "Ichimoku Cloud", features["ichimoku_pos"], tanh(features["ichimoku_pos"] / 0.5), "yfinance")
    add_dyn(c, "Donchian Channel", features["donchian_pos"] * 100, ((features["donchian_pos"] - 0.5) / 0.3).clip(-1, 1), "yfinance")
    add_dyn(c, "Keltner Channel", features["keltner_pos"] * 100, ((features["keltner_pos"] - 0.5) / 0.3).clip(-1, 1), "yfinance")
    add_dyn(c, "Commodity channel index (CCI)", features["cci"], tanh(features["cci"] / 100), "yfinance")
    add_dyn(c, "Williams %R", features["williams_r"], (-(features["williams_r"] + 50.0) / 50.0).clip(-1, 1), "yfinance")
    add_dyn(c, "Rate of change (ROC)", features["roc"] * 100, tanh(features["roc"] / 0.08), "yfinance", "%")
    add_dyn(c, "Momentum indicator", features["mom"], tanh(features["mom"] / (features["Close"] * 0.05)), "yfinance")
    add_dyn(c, "On-balance volume (OBV)", features["obv"], tanh(features["obv_slope"] / (features["Volume"].rolling(20).sum() + 1e-9)), "yfinance")
    add_dyn(c, "Accumulation/distribution line", features["adl"], tanh(features["adl_slope"] / (features["Volume"].rolling(20).sum() + 1e-9)), "yfinance")
    add_dyn(c, "Chaikin money flow", features["cmf"], tanh(features["cmf"] / 0.2), "yfinance")
    add_dyn(c, "Average true range (ATR)", features["atr"], tanh(-(features["atr_pct"] - 0.02) / 0.015), "yfinance")
    add_dyn(c, "Pivot points", features["pivot"], np.sign(features["Close"] - features["pivot"]).clip(-1, 1), "yfinance")
    add_dyn(c, "Fibonacci retracement levels", features["fib_pos"] * 100, ((features["fib_pos"] - 0.5) / 0.3).clip(-1, 1), "yfinance")
    add_dyn(c, "Volume-weighted average price (VWAP)", features["vwap"], tanh((features["Close"] / features["vwap"] - 1.0) / 0.03), "yfinance")

    c = "Volume & Liquidity Indicators"
    add_dyn(c, "Daily trading volume", features["Volume"], tanh((features["Volume"] / features["avg_vol"] - 1) / 0.6), "yfinance")
    add_dyn(c, "Average daily volume", features["avg_vol"], tanh((features["avg_vol"] / features["avg_vol"].rolling(60).mean() - 1) / 0.4), "yfinance")
    add_dyn(c, "Volume change %", features["vol_chg"] * 100, tanh(features["vol_chg"] / 0.3), "yfinance", "%")
    add_dyn(c, "Relative volume (RVOL)", features["rvol"], tanh((features["rvol"] - 1) / 0.8), "yfinance")

    shares = safe_float(info.get("sharesOutstanding"))
    float_shares = safe_float(info.get("floatShares"))
    mcap = safe_float(info.get("marketCap"))
    held_inst = safe_float(info.get("heldPercentInstitutions"))
    held_insider = safe_float(info.get("heldPercentInsiders"))
    short_interest = safe_float(info.get("sharesShort"))
    short_ratio = safe_float(info.get("shortRatio"))

    if shares and shares > 0:
        add_dyn(c, "Turnover ratio", features["Volume"] / shares * 100, tanh((features["Volume"] / shares * 100 - 0.5) / 1.0), "derived", "%")
    register(reg, c, "Free float shares", float_shares, tanh(np.log10((float_shares or 1) / 1_000_000)), "yfinance")
    if float_shares and float_shares > 0:
        add_dyn(c, "Float turnover", features["Volume"] / float_shares * 100, tanh((features["Volume"] / float_shares * 100 - 0.7) / 1.2), "derived", "%")
    bid = ask = None
    q = alpaca.get("quote", {}) if isinstance(alpaca, dict) else {}
    if isinstance(q, dict):
        bid = safe_float(q.get("bp"))
        ask = safe_float(q.get("ap"))
    if bid is None or ask is None:
        bid = safe_float(info.get("bid"))
        ask = safe_float(info.get("ask"))
    if bid is not None and ask is not None and close:
        spread_pct = (ask - bid) / close * 100
        register(reg, c, "Bid-ask spread", spread_pct, tanh(-spread_pct / 0.2), "alpaca/yfinance", "%")
    register(reg, c, "Institutional ownership %", to_pct(held_inst), tanh((held_inst or 0) / 0.5) if held_inst is not None else None, "yfinance", "%")
    if held_inst is not None and held_insider is not None:
        retail = max(0.0, 1 - held_inst - held_insider)
        register(reg, c, "Retail ownership %", retail * 100, tanh((retail - 0.2) / 0.3), "derived", "%")
    register(reg, c, "Short interest", short_interest, tanh(-(np.log10((short_interest or 1) + 1) - 6)), "yfinance")
    register(reg, c, "Short interest ratio (days to cover)", short_ratio, tanh(-((short_ratio or 0) - 4) / 3), "yfinance")
    if mcap and mcap > 0:
        add_dyn(c, "Liquidity ratio (market based)", features["dollar_vol"] / mcap * 100, tanh((features["dollar_vol"] / mcap * 100 - 0.15) / 0.25), "derived", "%")

    c = "Risk & Volatility Measures"
    if "beta" in features.columns:
        add_dyn(c, "Beta", features["beta"], tanh(-abs(features["beta"] - 1.0) / 0.8), "derived")
        add_dyn(c, "Alpha", features["alpha"], tanh(features["alpha"] / 0.12), "derived")
        add_dyn(c, "Standard deviation", features["std"] * 100, tanh(-features["std"] / 0.03), "derived", "%")
        add_dyn(c, "Historical volatility", features["hist_vol"] * 100, tanh(-features["hist_vol"] / 0.4), "derived", "%")
        add_dyn(c, "Sharpe ratio", features["sharpe"], tanh(features["sharpe"] / 1.5), "derived")
        add_dyn(c, "Sortino ratio", features["sortino"], tanh(features["sortino"] / 2), "derived")
        add_dyn(c, "Treynor ratio", features["treynor"], tanh(features["treynor"] / 0.2), "derived")
        add_dyn(c, "Value at risk (VaR)", features["var95"] * 100, tanh(features["var95"] / 0.04), "derived", "%")
        add_dyn(c, "Conditional VaR", features["cvar95"] * 100, tanh(features["cvar95"] / 0.05), "derived", "%")
        add_dyn(c, "Downside deviation", features["down_dev"] * 100, tanh(-features["down_dev"] / 0.3), "derived", "%")
        add_dyn(c, "Maximum drawdown", features["max_dd"] * 100, tanh(features["max_dd"] / 0.35), "derived", "%")
        add_dyn(c, "Correlation with index", features["corr"], tanh(features["corr"] / 1.0), "derived")
        add_dyn(c, "Tracking error", features["track_err"] * 100, tanh(-features["track_err"] / 0.15), "derived", "%")
        add_dyn(c, "Information ratio", features["info_ratio"], tanh(features["info_ratio"] / 1.2), "derived")
    iv = safe_float(info.get("impliedVolatility"))
    register(reg, c, "Implied volatility", to_pct(iv), tanh(-(iv or 0) / 0.45) if iv is not None else None, "yfinance", "%")

    c = "Valuation Metrics"
    ev = safe_float(info.get("enterpriseValue"))
    pe = safe_float(info.get("trailingPE"))
    fpe = safe_float(info.get("forwardPE"))
    pb = safe_float(info.get("priceToBook"))
    ps = safe_float(info.get("priceToSalesTrailing12Months"))
    ev_ebitda = safe_float(info.get("enterpriseToEbitda"))
    ev_rev = safe_float(info.get("enterpriseToRevenue"))
    peg = safe_float(info.get("pegRatio"))
    div_yield = safe_float(info.get("dividendYield"))
    payout = safe_float(info.get("payoutRatio"))
    book_ps = safe_float(info.get("bookValue"))
    rev_ps = safe_float(info.get("revenuePerShare"))
    fcf_info = safe_float(info.get("freeCashflow"))
    op_cf_info = safe_float(info.get("operatingCashflow"))
    op_inc, _ = latest_prev(financials, ["Operating Income", "EBIT"])
    ev_ebit = ev / op_inc if (ev and op_inc) else None
    p_cf = mcap / op_cf_info if (mcap and op_cf_info) else None
    earnings_yield = 1 / pe if pe not in [None, 0] else None
    fcf_yield = fcf_info / mcap if (fcf_info and mcap) else None
    total_equity, _ = latest_prev(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest"])
    goodwill, _ = latest_prev(bs, ["Goodwill"])
    intangible, _ = latest_prev(bs, ["Other Intangible Assets", "Intangible Assets"])
    tang_book = total_equity - (goodwill or 0) - (intangible or 0) if total_equity is not None else None
    div_growth = None
    if isinstance(dividends, pd.Series) and not dividends.empty:
        annual = dividends.groupby(dividends.index.year).sum()
        if len(annual) > 1 and annual.iloc[-2] != 0:
            div_growth = annual.iloc[-1] / annual.iloc[-2] - 1
    register(reg, c, "Market capitalization", mcap, tanh(np.log10((mcap or 1) / 1_000_000_000)), "yfinance")
    register(reg, c, "Enterprise value (EV)", ev, tanh(np.log10((ev or 1) / 1_000_000_000)), "yfinance")
    register(reg, c, "Price-to-earnings (P/E) ratio", pe, tanh(-((pe or 20) - 20) / 15) if pe is not None else None, "yfinance")
    register(reg, c, "Forward P/E", fpe, tanh(-((fpe or 18) - 18) / 12) if fpe is not None else None, "yfinance")
    register(reg, c, "Trailing P/E", pe, tanh(-((pe or 20) - 20) / 15) if pe is not None else None, "yfinance")
    register(reg, c, "Price-to-book (P/B)", pb, tanh(-((pb or 3) - 3) / 3) if pb is not None else None, "yfinance")
    register(reg, c, "Price-to-sales (P/S)", ps, tanh(-((ps or 4) - 4) / 4) if ps is not None else None, "yfinance")
    register(reg, c, "Price-to-cash flow", p_cf, tanh(-((p_cf or 15) - 15) / 10) if p_cf is not None else None, "derived")
    register(reg, c, "EV/EBITDA", ev_ebitda, tanh(-((ev_ebitda or 12) - 12) / 8) if ev_ebitda is not None else None, "yfinance")
    register(reg, c, "EV/Revenue", ev_rev, tanh(-((ev_rev or 5) - 5) / 4) if ev_rev is not None else None, "yfinance")
    register(reg, c, "EV/EBIT", ev_ebit, tanh(-((ev_ebit or 14) - 14) / 10) if ev_ebit is not None else None, "derived")
    register(reg, c, "PEG ratio", peg, tanh(-((peg or 1.5) - 1.5) / 1.2) if peg is not None else None, "yfinance")
    register(reg, c, "Dividend yield", to_pct(div_yield), tanh((div_yield or 0) / 0.04) if div_yield is not None else None, "yfinance", "%")
    register(reg, c, "Dividend payout ratio", to_pct(payout), tanh(-abs((payout or 0) - 0.45) / 0.25) if payout is not None else None, "yfinance", "%")
    register(reg, c, "Dividend growth rate", to_pct(div_growth), tanh((div_growth or 0) / 0.12) if div_growth is not None else None, "derived", "%")
    register(reg, c, "Earnings yield", to_pct(earnings_yield), tanh((earnings_yield or 0) / 0.06) if earnings_yield is not None else None, "derived", "%")
    register(reg, c, "Book value per share", book_ps, tanh((book_ps or 0) / 20) if book_ps is not None else None, "yfinance")
    register(reg, c, "Tangible book value", tang_book, tanh((tang_book / mcap)) if (tang_book is not None and mcap) else None, "derived")
    register(reg, c, "Revenue per share", rev_ps, tanh((rev_ps or 0) / 25) if rev_ps is not None else None, "yfinance")
    register(reg, c, "Free cash flow yield", to_pct(fcf_yield), tanh((fcf_yield or 0) / 0.06) if fcf_yield is not None else None, "derived", "%")

    c = "Profitability Metrics"
    rev, rev_prev = latest_prev(financials, ["Total Revenue"])
    gp, _ = latest_prev(financials, ["Gross Profit"])
    op, _ = latest_prev(financials, ["Operating Income", "EBIT"])
    ebitda, _ = latest_prev(financials, ["EBITDA"])
    ni, _ = latest_prev(financials, ["Net Income"])
    cogs, _ = latest_prev(financials, ["Cost Of Revenue", "Cost of Revenue"])
    sga, _ = latest_prev(financials, ["Selling General And Administration", "Selling General Administrative"])
    rnd, _ = latest_prev(financials, ["Research And Development"])
    int_exp, _ = latest_prev(financials, ["Interest Expense"])
    eps = safe_float(info.get("trailingEps"))
    deps = safe_float(info.get("epsTrailingTwelveMonths")) or eps
    roe = safe_float(info.get("returnOnEquity"))
    roa = safe_float(info.get("returnOnAssets"))
    roic = None
    metric = finnhub.get("metric")
    if isinstance(metric, dict) and isinstance(metric.get("metric"), dict):
        roic = safe_float(metric["metric"].get("roicTTM")) or safe_float(metric["metric"].get("roicAnnual"))
    ta, _ = latest_prev(bs, ["Total Assets"])
    clia, _ = latest_prev(bs, ["Current Liabilities"])
    cap_emp = ta - clia if (ta and clia is not None) else None
    roce = op / cap_emp if (op and cap_emp and cap_emp != 0) else None
    rev_g = pct(rev, rev_prev)
    gm = gp / rev if (gp and rev) else None
    om = op / rev if (op and rev) else None
    em = ebitda / rev if (ebitda and rev) else None
    nm = ni / rev if (ni and rev) else None
    cogs_r = cogs / rev if (cogs and rev) else None
    sga_r = sga / rev if (sga and rev) else None
    rnd_r = rnd / rev if (rnd and rev) else None
    int_r = int_exp / rev if (int_exp and rev) else None
    register(reg, c, "Revenue", rev, tanh((rev / mcap)) if (rev and mcap) else None, "yfinance")
    register(reg, c, "Revenue growth rate", to_pct(rev_g), tanh((rev_g or 0) / 0.1) if rev_g is not None else None, "yfinance", "%")
    register(reg, c, "Gross profit", gp, tanh((gp / rev)) if (gp and rev) else None, "yfinance")
    register(reg, c, "Gross margin", to_pct(gm), tanh((gm or 0) / 0.4) if gm is not None else None, "derived", "%")
    register(reg, c, "Operating income", op, tanh((op / rev)) if (op and rev) else None, "yfinance")
    register(reg, c, "Operating margin", to_pct(om), tanh((om or 0) / 0.2) if om is not None else None, "derived", "%")
    register(reg, c, "EBITDA", ebitda, tanh((ebitda / rev)) if (ebitda and rev) else None, "yfinance")
    register(reg, c, "EBITDA margin", to_pct(em), tanh((em or 0) / 0.25) if em is not None else None, "derived", "%")
    register(reg, c, "Net income", ni, tanh((ni / rev)) if (ni and rev) else None, "yfinance")
    register(reg, c, "Net margin", to_pct(nm), tanh((nm or 0) / 0.18) if nm is not None else None, "derived", "%")
    register(reg, c, "Earnings per share (EPS)", eps, tanh((eps or 0) / 4) if eps is not None else None, "yfinance")
    register(reg, c, "Diluted EPS", deps, tanh((deps or 0) / 4) if deps is not None else None, "yfinance")
    register(reg, c, "Return on equity (ROE)", to_pct(roe), tanh((roe or 0) / 0.2) if roe is not None else None, "yfinance", "%")
    register(reg, c, "Return on assets (ROA)", to_pct(roa), tanh((roa or 0) / 0.1) if roa is not None else None, "yfinance", "%")
    register(reg, c, "Return on invested capital (ROIC)", to_pct(roic), tanh((roic or 0) / 0.15) if roic is not None else None, "finnhub", "%")
    register(reg, c, "Return on capital employed (ROCE)", to_pct(roce), tanh((roce or 0) / 0.15) if roce is not None else None, "derived", "%")
    register(reg, c, "Cost of goods sold (COGS)", to_pct(cogs_r), tanh(-(cogs_r or 0) / 0.7) if cogs_r is not None else None, "derived", "%")
    register(reg, c, "SG&A expense", to_pct(sga_r), tanh(-(sga_r or 0) / 0.25) if sga_r is not None else None, "derived", "%")
    register(reg, c, "R&D expense", to_pct(rnd_r), tanh((rnd_r or 0) / 0.12) if rnd_r is not None else None, "derived", "%")
    register(reg, c, "Interest expense", to_pct(int_r), tanh(-(int_r or 0) / 0.08) if int_r is not None else None, "derived", "%")

    c = "Balance Sheet Metrics"
    tl, _ = latest_prev(bs, ["Total Liabilities Net Minority Interest", "Total Liab"])
    te, te_prev = latest_prev(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest"])
    ltd, _ = latest_prev(bs, ["Long Term Debt"])
    stdt, _ = latest_prev(bs, ["Current Debt", "Short Long Term Debt"])
    cash, _ = latest_prev(bs, ["Cash And Cash Equivalents", "Cash"])
    ca, _ = latest_prev(bs, ["Current Assets"])
    inv, _ = latest_prev(bs, ["Inventory"])
    recv, _ = latest_prev(bs, ["Accounts Receivable"])
    pay, _ = latest_prev(bs, ["Accounts Payable"])
    def_rev, _ = latest_prev(bs, ["Deferred Revenue"])
    debt = (ltd or 0) + (stdt or 0)
    dte = debt / te if (debt and te) else None
    dta = debt / ta if (debt and ta) else None
    net_debt = debt - (cash or 0) if debt else None
    curr = ca / clia if (ca and clia) else None
    quick = (ca - (inv or 0)) / clia if (ca and clia) else None
    cash_r = cash / clia if (cash and clia) else None
    wc = ca - clia if (ca and clia) else None
    inv_turn = cogs / inv if (cogs and inv) else None
    rec_turn = rev / recv if (rev and recv) else None
    pay_turn = cogs / pay if (cogs and pay) else None
    asset_turn = rev / ta if (rev and ta) else None
    eq_growth = pct(te, te_prev)
    register(reg, c, "Total assets", ta, tanh(np.log10((ta or 1) / 1_000_000_000)), "yfinance")
    register(reg, c, "Total liabilities", tl, tanh(-(tl / ta)) if (tl and ta) else None, "yfinance")
    register(reg, c, "Total equity", te, tanh((te / ta)) if (te and ta) else None, "yfinance")
    register(reg, c, "Debt-to-equity ratio", dte, tanh(-((dte or 0) - 0.7) / 0.8) if dte is not None else None, "derived")
    register(reg, c, "Debt-to-assets ratio", dta, tanh(-((dta or 0) - 0.4) / 0.3) if dta is not None else None, "derived")
    register(reg, c, "Net debt", net_debt, tanh(-(net_debt / mcap)) if (net_debt is not None and mcap) else None, "derived")
    register(reg, c, "Current ratio", curr, tanh(-abs((curr or 0) - 1.8) / 1.0) if curr is not None else None, "derived")
    register(reg, c, "Quick ratio", quick, tanh(-abs((quick or 0) - 1.2) / 0.8) if quick is not None else None, "derived")
    register(reg, c, "Cash ratio", cash_r, tanh(-abs((cash_r or 0) - 0.5) / 0.5) if cash_r is not None else None, "derived")
    register(reg, c, "Working capital", wc, tanh((wc / ta)) if (wc and ta) else None, "derived")
    register(reg, c, "Inventory turnover", inv_turn, tanh((inv_turn or 0) / 6) if inv_turn is not None else None, "derived")
    register(reg, c, "Receivables turnover", rec_turn, tanh((rec_turn or 0) / 6) if rec_turn is not None else None, "derived")
    register(reg, c, "Payables turnover", pay_turn, tanh((pay_turn or 0) / 6) if pay_turn is not None else None, "derived")
    register(reg, c, "Asset turnover", asset_turn, tanh((asset_turn or 0) / 1.0) if asset_turn is not None else None, "derived")
    register(reg, c, "Goodwill", goodwill, tanh(-(goodwill / ta)) if (goodwill and ta) else None, "yfinance")
    register(reg, c, "Intangible assets", intangible, tanh(-(intangible / ta)) if (intangible and ta) else None, "yfinance")
    register(reg, c, "Long-term debt", ltd, tanh(-(ltd / mcap)) if (ltd and mcap) else None, "yfinance")
    register(reg, c, "Short-term debt", stdt, tanh(-(stdt / mcap)) if (stdt and mcap) else None, "yfinance")
    register(reg, c, "Deferred revenue", def_rev, tanh((def_rev / rev)) if (def_rev and rev) else None, "yfinance")
    register(reg, c, "Shareholders' equity growth", to_pct(eq_growth), tanh((eq_growth or 0) / 0.08) if eq_growth is not None else None, "derived", "%")

    c = "Cash Flow Indicators"
    opcf, opcf_prev = latest_prev(cf, ["Operating Cash Flow"])
    invcf, _ = latest_prev(cf, ["Investing Cash Flow"])
    fincf, _ = latest_prev(cf, ["Financing Cash Flow"])
    capex, capex_prev = latest_prev(cf, ["Capital Expenditure"])
    div_paid, _ = latest_prev(cf, ["Cash Dividends Paid", "Dividends Paid"])
    fcf = opcf + capex if (opcf is not None and capex is not None) else None
    fcf_prev = opcf_prev + capex_prev if (opcf_prev is not None and capex_prev is not None) else None
    fcf_g = pct(fcf, fcf_prev)
    ccc = None
    if inv_turn and rec_turn and pay_turn:
        ccc = 365 / inv_turn + 365 / rec_turn - 365 / pay_turn
    cf_share = opcf / shares if (opcf and shares) else None
    div_cov = fcf / abs(div_paid) if (fcf is not None and div_paid not in [None, 0]) else None
    int_cov = op / abs(int_exp) if (op and int_exp not in [None, 0]) else None
    register(reg, c, "Operating cash flow", opcf, tanh((opcf / mcap)) if (opcf and mcap) else None, "yfinance")
    register(reg, c, "Investing cash flow", invcf, tanh(-(invcf / mcap)) if (invcf and mcap) else None, "yfinance")
    register(reg, c, "Financing cash flow", fincf, tanh(-(fincf / mcap)) if (fincf and mcap) else None, "yfinance")
    register(reg, c, "Free cash flow", fcf, tanh((fcf / mcap)) if (fcf and mcap) else None, "derived")
    register(reg, c, "Capital expenditures (CapEx)", capex, tanh((capex / abs(opcf))) if (capex is not None and opcf not in [None, 0]) else None, "yfinance")
    register(reg, c, "Free cash flow growth", to_pct(fcf_g), tanh((fcf_g or 0) / 0.15) if fcf_g is not None else None, "derived", "%")
    register(reg, c, "Cash conversion cycle", ccc, tanh(-(ccc or 0) / 80) if ccc is not None else None, "derived")
    register(reg, c, "Cash flow per share", cf_share, tanh((cf_share or 0) / 4) if cf_share is not None else None, "derived")
    register(reg, c, "Dividend coverage ratio", div_cov, tanh(((div_cov or 0) - 1.5) / 1.5) if div_cov is not None else None, "derived")
    register(reg, c, "Interest coverage ratio", int_cov, tanh((int_cov or 0) / 8) if int_cov is not None else None, "derived")

    c = "Market & Sector Context"
    rel_idx = safe_float(last.get("rel_strength_idx")) if "rel_strength_idx" in features.columns else None
    sector_perf = None
    rel_sector = None
    if sector_features is not None and not sector_features.empty:
        sector_perf = safe_float(sector_features["Close"].pct_change(63).iloc[-1])
        if ret63 is not None and sector_perf is not None:
            rel_sector = ret63 - sector_perf
    register(reg, c, "Sector performance", to_pct(sector_perf), tanh((sector_perf or 0) / 0.1) if sector_perf is not None else None, "yfinance", "%")
    register(reg, c, "Industry performance", to_pct(sector_perf), tanh((sector_perf or 0) / 0.1) if sector_perf is not None else None, "sector-proxy", "%")
    register(reg, c, "Relative strength vs index", to_pct(rel_idx), tanh((rel_idx or 0) / 0.08) if rel_idx is not None else None, "derived", "%")
    register(reg, c, "Relative strength vs sector", to_pct(rel_sector), tanh((rel_sector or 0) / 0.08) if rel_sector is not None else None, "derived", "%")
    comp = 0.6 * (rel_idx or 0) + 0.4 * (om or 0) if (rel_idx is not None and om is not None) else None
    register(reg, c, "Competitive positioning index", comp, tanh((comp or 0) / 0.1) if comp is not None else None, "derived")

    rec = finnhub.get("recommendation")
    analyst_score = None
    coverage = None
    rev_trend = None
    if isinstance(rec, list) and rec:
        a0 = rec[0] if isinstance(rec[0], dict) else {}
        sb = safe_float(a0.get("strongBuy")) or 0
        b = safe_float(a0.get("buy")) or 0
        hld = safe_float(a0.get("hold")) or 0
        s = safe_float(a0.get("sell")) or 0
        ss = safe_float(a0.get("strongSell")) or 0
        total = sb + b + hld + s + ss
        coverage = total
        analyst_score = (2 * sb + b - s - 2 * ss) / total if total > 0 else None
        if len(rec) > 1 and isinstance(rec[1], dict):
            p0 = rec[1]
            psb = safe_float(p0.get("strongBuy")) or 0
            pb = safe_float(p0.get("buy")) or 0
            ph = safe_float(p0.get("hold")) or 0
            ps = safe_float(p0.get("sell")) or 0
            pss = safe_float(p0.get("strongSell")) or 0
            ptotal = psb + pb + ph + ps + pss
            prev_score = (2 * psb + pb - ps - 2 * pss) / ptotal if ptotal > 0 else None
            if prev_score is not None and analyst_score is not None:
                rev_trend = analyst_score - prev_score
    register(reg, c, "Analyst rating consensus", analyst_score, tanh((analyst_score or 0) / 0.7) if analyst_score is not None else None, "finnhub")

    pt = finnhub.get("price_target")
    tgt = safe_float(pt.get("targetMean")) if isinstance(pt, dict) else safe_float(info.get("targetMeanPrice"))
    upside = tgt / close - 1 if (tgt and close) else None
    register(reg, c, "Target price", tgt, tanh((upside or 0) / 0.2) if upside is not None else None, "finnhub")

    e = finnhub.get("earnings")
    e_sur = r_sur = None
    if isinstance(e, list) and e and isinstance(e[0], dict):
        e_sur = safe_float(e[0].get("surprisePercent"))
        r_sur = safe_float(e[0].get("revenueSurprisePercent"))
    register(reg, c, "Earnings surprise", e_sur, tanh((e_sur or 0) / 12) if e_sur is not None else None, "finnhub", "%")
    register(reg, c, "Revenue surprise", r_sur, tanh((r_sur or 0) / 8) if r_sur is not None else None, "finnhub", "%")
    register(reg, c, "Earnings revisions trend", rev_trend, tanh((rev_trend or 0) / 0.3) if rev_trend is not None else None, "finnhub")

    ins = finnhub.get("insider_sentiment")
    ins_score = None
    if isinstance(ins, dict) and isinstance(ins.get("data"), list):
        vals = [safe_float(x.get("mspr")) for x in ins["data"][:12] if isinstance(x, dict)]
        vals = [x for x in vals if x is not None]
        if vals:
            ins_score = float(np.mean(vals))
    register(reg, c, "Insider buying/selling", ins_score, tanh((ins_score or 0) / 1.0) if ins_score is not None else None, "finnhub")

    esg = finnhub.get("esg")
    esg_score = gov_score = sus_score = None
    if isinstance(esg, dict):
        if isinstance(esg.get("esgScore"), (float, int)):
            esg_score = safe_float(esg.get("esgScore"))
            gov_score = safe_float(esg.get("governanceScore"))
            sus_score = esg_score
        elif isinstance(esg.get("data"), list) and esg["data"] and isinstance(esg["data"][0], dict):
            row = esg["data"][0]
            esg_score = safe_float(row.get("totalEsg"))
            gov_score = safe_float(row.get("governance"))
            sus_score = esg_score
    register(reg, c, "ESG score", esg_score, tanh((esg_score or 0) / 50) if esg_score is not None else None, "finnhub")

    sp = finnhub.get("sp500")
    in_idx = None
    if isinstance(sp, dict) and isinstance(sp.get("constituents"), list):
        in_idx = symbol.upper() in {str(x).upper() for x in sp["constituents"]}
    register(reg, c, "Index inclusion", 1.0 if in_idx else (0.0 if in_idx is not None else None), 1.0 if in_idx else (-0.2 if in_idx is not None else None), "finnhub")

    c = "Corporate Actions"
    if isinstance(splits, pd.Series) and not splits.empty:
        register(reg, c, "Stock splits", float((splits > 1).sum()), tanh(-float((splits > 1).sum()) / 2), "yfinance")
        register(reg, c, "Reverse splits", float((splits < 1).sum()), tanh(-float((splits < 1).sum()) * 2), "yfinance")
    repurch, _ = latest_prev(cf, ["Repurchase Of Capital Stock", "Repurchase of Capital Stock"])
    buybacks = abs(repurch) if repurch is not None else None
    register(reg, c, "Share buybacks", buybacks, tanh((buybacks / mcap)) if (buybacks and mcap) else None, "yfinance")
    shares_now, shares_prev = latest_prev(bs, ["Ordinary Shares Number", "Share Issued"])
    sec = pct(shares_now, shares_prev)
    register(reg, c, "Secondary offerings", to_pct(sec), tanh(-(sec or 0) / 0.1) if sec is not None else None, "derived", "%")
    if isinstance(dividends, pd.Series) and not dividends.empty:
        recent = dividends[dividends.index >= dividends.index.max() - pd.Timedelta(days=365)]
        register(reg, c, "Dividend announcements", float(recent.count()), tanh(float(recent.count()) / 4), "yfinance")
    epoch = safe_float(info.get("firstTradeDateEpochUtc"))
    if epoch:
        ipo_str = datetime.utcfromtimestamp(epoch).date().isoformat()
        register(reg, c, "IPO date", ipo_str, tanh((datetime.utcnow().year - int(ipo_str[:4])) / 20), "yfinance")

    c = "Macroeconomic Exposure"
    try:
        start = features.index.min().date()
        end = features.index.max().date()
        tnx = fetch_history("^TNX", start, end)
        dxy = fetch_history("DX-Y.NYB", start, end)
        cl = fetch_history("CL=F", start, end)
        hyg = fetch_history("HYG", start, end)
        if not tnx.empty:
            ir = safe_float(features["ret1"].corr(tnx["Close"].pct_change().reindex(features.index)))
            register(reg, c, "Interest rate sensitivity", ir, tanh(-(ir or 0) / 0.6) if ir is not None else None, "macro-proxy")
            register(reg, c, "Inflation sensitivity", ir, tanh(-(ir or 0) / 0.6) if ir is not None else None, "macro-proxy")
        if not dxy.empty:
            fx = safe_float(features["ret1"].corr(dxy["Close"].pct_change().reindex(features.index)))
            register(reg, c, "Currency exposure", fx, tanh(-(fx or 0) / 0.6) if fx is not None else None, "macro-proxy")
        if not cl.empty:
            cm = safe_float(features["ret1"].corr(cl["Close"].pct_change().reindex(features.index)))
            register(reg, c, "Commodity price sensitivity", cm, tanh((cm or 0) / 0.6) if cm is not None else None, "macro-proxy")
        if not hyg.empty:
            cs = safe_float(features["ret1"].corr(hyg["Close"].pct_change().reindex(features.index)))
            register(reg, c, "Credit spread sensitivity", cs, tanh(-(cs or 0) / 0.6) if cs is not None else None, "macro-proxy")
    except Exception:
        pass

    c = "Derivatives & Options Metrics"
    if isinstance(calls, pd.DataFrame) and isinstance(puts, pd.DataFrame) and not calls.empty and not puts.empty:
        for frame in [calls, puts]:
            for col in ["volume", "openInterest", "impliedVolatility", "strike"]:
                frame[col] = pd.to_numeric(frame.get(col), errors="coerce")
        opts_vol = safe_float(calls["volume"].fillna(0).sum() + puts["volume"].fillna(0).sum())
        coi = safe_float(calls["openInterest"].fillna(0).sum())
        poi = safe_float(puts["openInterest"].fillna(0).sum())
        oi = (coi or 0) + (poi or 0)
        pcr = poi / coi if (poi is not None and coi not in [None, 0]) else None
        register(reg, c, "Options volume", opts_vol, tanh(np.log10((opts_vol or 1) / 1000)), "yfinance-options")
        register(reg, c, "Open interest", oi, tanh(np.log10((oi or 1) / 5000)), "yfinance-options")
        register(reg, c, "Put/call ratio", pcr, tanh(-((pcr or 1) - 0.9) / 0.5) if pcr is not None else None, "yfinance-options")
        if close:
            otm_put = puts[puts["strike"] < close * 0.98]["impliedVolatility"].dropna()
            otm_call = calls[calls["strike"] > close * 1.02]["impliedVolatility"].dropna()
            if not otm_put.empty and not otm_call.empty:
                skew = safe_float(otm_put.mean() - otm_call.mean())
                register(reg, c, "Implied volatility skew", skew, tanh(-(skew or 0) / 0.1) if skew is not None else None, "yfinance-options")
            atm = calls.iloc[(calls["strike"] - close).abs().argsort()[:5]]
            curr_iv = safe_float(atm["impliedVolatility"].mean())
            hv = safe_float(last.get("hist_vol"))
            ivr = (curr_iv - hv) / abs(hv) if (curr_iv is not None and hv not in [None, 0]) else None
            register(reg, c, "Implied volatility rank", ivr, tanh(-(ivr or 0) / 0.8) if ivr is not None else None, "derived")
        mp = max_pain(calls, puts)
        register(reg, c, "Max pain level", mp, tanh((mp / close - 1) / 0.1) if (mp and close) else None, "derived")

    c = "Credit & Fixed Income Indicators"
    by = safe_float(info.get("yield"))
    register(reg, c, "Bond yield", to_pct(by), tanh((by or 0) / 0.04) if by is not None else None, "yfinance", "%")
    refinance = debt / opcf if (debt and opcf not in [None, 0]) else None
    register(reg, c, "Refinancing risk", refinance, tanh(-(refinance or 0) / 5) if refinance is not None else None, "derived")
    if isinstance(q_financials, pd.DataFrame) and not q_financials.empty:
        q_ebit = find_row(q_financials, ["Operating Income", "EBIT"])
        q_int = find_row(q_financials, ["Interest Expense"])
        if q_ebit is not None and q_int is not None:
            cov = (q_ebit / q_int.abs().replace(0, np.nan)).dropna()
            if len(cov) >= 3:
                slope = safe_float(np.polyfit(np.arange(len(cov)), cov.values, 1)[0])
                register(reg, c, "Interest coverage trend", slope, tanh((slope or 0) / 0.5) if slope is not None else None, "derived")

    c = "Sentiment & Alternative Data"
    news = finnhub.get("news")
    news_score = safe_float(news.get("companyNewsScore")) if isinstance(news, dict) else None
    register(reg, c, "News sentiment score", news_score, tanh((news_score or 0) / 0.4) if news_score is not None else None, "finnhub")
    social = finnhub.get("social")
    social_score = None
    if isinstance(social, dict):
        vals = []
        for key in ["reddit", "twitter"]:
            arr = social.get(key)
            if isinstance(arr, list):
                for row in arr[:20]:
                    if isinstance(row, dict):
                        sv = safe_float(row.get("score"))
                        if sv is not None:
                            vals.append(sv)
        if vals:
            social_score = float(np.mean(vals))
    register(reg, c, "Social media sentiment", social_score, tanh((social_score or 0) / 0.3) if social_score is not None else None, "finnhub")

    c = "Growth & Forward Indicators"
    register(reg, c, "Customer acquisition rate", to_pct(rev_g), tanh((rev_g or 0) / 0.08) if rev_g is not None else None, "revenue-proxy", "%")
    register(reg, c, "Churn rate", to_pct(-rev_g) if rev_g is not None else None, tanh((rev_g or 0) / 0.08) if rev_g is not None else None, "revenue-proxy", "%")
    if isinstance(metric, dict) and isinstance(metric.get("metric"), dict):
        eps_g = safe_float(metric["metric"].get("epsGrowthTTMYoy"))
        rev_g_ttm = safe_float(metric["metric"].get("revenueGrowthTTMYoy"))
        register(reg, c, "User growth", to_pct(eps_g), tanh((eps_g or 0) / 0.1) if eps_g is not None else None, "finnhub-proxy", "%")
        register(reg, c, "ARPU (average revenue per user)", to_pct(rev_g_ttm), tanh((rev_g_ttm or 0) / 0.1) if rev_g_ttm is not None else None, "finnhub-proxy", "%")

    c = "Ownership & Structure"
    float_pct = float_shares / shares if (float_shares and shares) else None
    register(reg, c, "Shares outstanding", shares, tanh(np.log10((shares or 1) / 50_000_000)) if shares else None, "yfinance")
    register(reg, c, "Float percentage", to_pct(float_pct), tanh((float_pct or 0) / 0.6) if float_pct is not None else None, "yfinance", "%")
    register(reg, c, "Insider ownership", to_pct(held_insider), tanh((held_insider or 0) / 0.15) if held_insider is not None else None, "yfinance", "%")
    register(reg, c, "Institutional ownership", to_pct(held_inst), tanh((held_inst or 0) / 0.5) if held_inst is not None else None, "yfinance", "%")
    holders = snapshot.get("institutional_holders", pd.DataFrame())
    if isinstance(holders, pd.DataFrame) and not holders.empty and shares:
        sc = None
        for col in holders.columns:
            if "shares" in str(col).lower():
                sc = col
                break
        if sc:
            held = pd.to_numeric(holders[sc], errors="coerce").dropna()
            if not held.empty:
                top10 = safe_float(held.head(10).sum() / shares)
                register(reg, c, "Top 10 holders concentration", to_pct(top10), tanh(-(top10 or 0) / 0.6) if top10 is not None else None, "yfinance", "%")
    treasury, _ = latest_prev(bs, ["Treasury Shares Number"])
    register(reg, c, "Treasury shares", treasury, tanh(-(treasury / shares)) if (treasury and shares) else None, "yfinance")

    c = "Performance Benchmarks"
    if len(features) >= 252:
        start_price = safe_float(features["Close"].dropna().iloc[0])
        end_price = safe_float(features["Close"].dropna().iloc[-1])
        years = len(features) / 252
        cagr = (end_price / start_price) ** (1 / years) - 1 if (start_price and end_price and years > 0) else None
        register(reg, c, "CAGR (compound annual growth rate)", to_pct(cagr), tanh((cagr or 0) / 0.15) if cagr is not None else None, "derived", "%")
    register(reg, c, "Rolling returns", to_pct(ret63), tanh((ret63 or 0) / 0.12) if ret63 is not None else None, "derived", "%")
    if isinstance(q_financials, pd.DataFrame) and not q_financials.empty:
        q_eps = find_row(q_financials, ["Diluted EPS", "Basic EPS"])
        q_rev = find_row(q_financials, ["Total Revenue"])
        q_ni = find_row(q_financials, ["Net Income"])
        q_op = find_row(q_financials, ["Operating Income", "EBIT"])
        if q_eps is not None and len(q_eps) >= 4:
            ec = -safe_float(q_eps.std() / (abs(q_eps.mean()) + 1e-9))
            register(reg, c, "Earnings consistency", ec, tanh((ec or 0) / 0.4) if ec is not None else None, "derived")
        if q_rev is not None and len(q_rev) >= 4:
            rc = -safe_float(q_rev.std() / (abs(q_rev.mean()) + 1e-9))
            register(reg, c, "Revenue consistency", rc, tanh((rc or 0) / 0.4) if rc is not None else None, "derived")
        if q_ni is not None and len(q_ni) >= 4:
            pv = safe_float(q_ni.std() / (abs(q_ni.mean()) + 1e-9))
            register(reg, c, "Profit volatility", pv, tanh(-(pv or 0) / 0.8) if pv is not None else None, "derived")
        if q_rev is not None and q_op is not None and len(q_rev) >= 2 and len(q_op) >= 2:
            rg = pct(safe_float(q_rev.iloc[0]), safe_float(q_rev.iloc[1]))
            og = pct(safe_float(q_op.iloc[0]), safe_float(q_op.iloc[1]))
            ol = og / rg if (rg not in [None, 0] and og is not None) else None
            register(reg, c, "Operating leverage", ol, tanh((ol or 0) / 2) if ol is not None else None, "derived")
        if q_ni is not None and q_rev is not None:
            margins = (q_ni / q_rev.replace(0, np.nan)).dropna()
            if len(margins) >= 4:
                ms = -safe_float(margins.std())
                register(reg, c, "Margin stability", ms, tanh((ms or 0) / 0.08) if ms is not None else None, "derived")
    fin_lev = ta / te if (ta and te) else None
    register(reg, c, "Financial leverage", fin_lev, tanh(-((fin_lev or 0) - 2) / 1.5) if fin_lev is not None else None, "derived")
    if isinstance(dividends, pd.Series) and not dividends.empty:
        qd = dividends.groupby(pd.Grouper(freq="QE")).sum()
        if len(qd) >= 4:
            dc = float((qd > 0).tail(8).mean())
            register(reg, c, "Dividend consistency", to_pct(dc), tanh((dc or 0) / 0.6), "yfinance", "%")

    c = "Miscellaneous Indicators"
    short_pct = safe_float(info.get("shortPercentOfFloat"))
    squeeze = short_pct * short_ratio if (short_pct is not None and short_ratio is not None) else None
    register(reg, c, "Analyst coverage count", coverage, tanh(np.log10((coverage or 1) / 5)) if coverage is not None else None, "finnhub")
    register(reg, c, "Short squeeze potential", to_pct(squeeze), tanh((squeeze or 0) / 0.3) if squeeze is not None else None, "derived", "%")
    gap = (features["Open"] / features["Close"].shift(1) - 1).abs()
    gapf = safe_float((gap > 0.02).tail(252).mean())
    register(reg, c, "Price gap frequency", to_pct(gapf), tanh(-((gapf or 0) - 0.08) / 0.07) if gapf is not None else None, "derived", "%")
    tax, _ = latest_prev(financials, ["Tax Rate For Calcs", "Tax Rate"])
    dta, _ = latest_prev(bs, ["Deferred Tax Assets"])
    register(reg, c, "Tax rate", to_pct(tax), tanh(-(tax or 0) / 0.28) if tax is not None else None, "yfinance", "%")
    register(reg, c, "Deferred tax assets", dta, tanh((dta / ta)) if (dta and ta) else None, "yfinance")
    register(reg, c, "Corporate governance score", gov_score, tanh((gov_score or 0) / 50) if gov_score is not None else None, "finnhub")
    register(reg, c, "Sustainability reporting score", sus_score, tanh((sus_score or 0) / 50) if sus_score is not None else None, "finnhub")

    rows: list[dict[str, Any]] = []
    for cat, name in ALL_INDICATORS:
        key = (cat, name)
        if key not in reg:
            rows.append(
                {
                    "Category": cat,
                    "Indicator": name,
                    "Value": "n/a",
                    "RawValue": np.nan,
                    "Signal": np.nan,
                    "Available": False,
                    "Source": "Unavailable via selected/free data source",
                    "Note": "",
                }
            )
            continue
        d = reg[key]
        sig = d.get("signal")
        if sig is not None and np.isfinite(sig):
            static_signals[key] = float(sig)
        raw = d.get("value")
        rows.append(
            {
                "Category": cat,
                "Indicator": name,
                "Value": fmt(raw, d.get("unit")),
                "RawValue": raw if isinstance(raw, (int, float, np.floating, np.integer)) else np.nan,
                "Signal": sig,
                "Available": True,
                "Source": d.get("source", ""),
                "Note": d.get("note", ""),
            }
        )
    return pd.DataFrame(rows), dynamic_signals, static_signals


def score_series(
    dates: pd.DatetimeIndex,
    dynamic_signals: dict[tuple[str, str], pd.Series],
    static_signals: dict[tuple[str, str], float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for ts in dates:
        vals: list[float] = []
        for v in static_signals.values():
            if v is not None and np.isfinite(v):
                vals.append(float(v))
        for s in dynamic_signals.values():
            if ts in s.index:
                val = safe_float(s.loc[ts])
                if val is not None and np.isfinite(val):
                    vals.append(float(np.clip(val, -1.0, 1.0)))
        n = len(vals)
        score = float(np.mean(vals) * 100.0) if n > 0 else np.nan
        rows.append(
            {
                "date": ts,
                "score": score,
                "available_signals": n,
                "coverage_pct": (n / TOTAL_INDICATORS) * 100.0,
            }
        )
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def backtest(
    features: pd.DataFrame,
    score_df: pd.DataFrame,
    start_dt: date,
    end_dt: date,
    threshold: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    if features.empty or score_df.empty:
        return pd.DataFrame(), {}
    mask = (features.index.date >= start_dt) & (features.index.date <= end_dt)
    px = features.loc[mask].copy()
    if px.empty:
        return pd.DataFrame(), {}
    bt = pd.DataFrame(index=px.index)
    bt["close"] = px["Close"]
    bt["ret"] = bt["close"].pct_change().fillna(0.0)
    bt = bt.join(score_df.set_index("date")[["score", "coverage_pct"]], how="left")
    bt["score"] = bt["score"].ffill()
    bt["coverage_pct"] = bt["coverage_pct"].ffill()
    bt["signal"] = np.where(bt["score"] >= threshold, 1, np.where(bt["score"] <= -threshold, -1, 0))
    bt["position"] = bt["signal"].shift(1).fillna(0).astype(int)
    bt["strategy_ret"] = bt["position"] * bt["ret"]
    bt["buy_hold_ret"] = bt["ret"]
    bt["strategy_equity"] = (1 + bt["strategy_ret"]).cumprod()
    bt["buy_hold_equity"] = (1 + bt["buy_hold_ret"]).cumprod()
    bt["strategy_drawdown"] = bt["strategy_equity"] / bt["strategy_equity"].cummax() - 1
    bt["buy_hold_drawdown"] = bt["buy_hold_equity"] / bt["buy_hold_equity"].cummax() - 1

    r = bt["strategy_ret"]
    total = safe_float(bt["strategy_equity"].iloc[-1] - 1.0)
    bh = safe_float(bt["buy_hold_equity"].iloc[-1] - 1.0)
    yrs = len(bt) / 252 if len(bt) else np.nan
    cagr = safe_float(bt["strategy_equity"].iloc[-1] ** (1 / yrs) - 1) if yrs and yrs > 0 else None
    vol = safe_float(r.std(ddof=1) * np.sqrt(252))
    sharpe = safe_float((r.mean() * 252) / vol) if vol not in [None, 0] else None
    mdd = safe_float(bt["strategy_drawdown"].min())
    hit = safe_float((r > 0).mean())
    trades = int((bt["position"] != bt["position"].shift(1)).sum())
    metrics = {
        "Total return": total if total is not None else np.nan,
        "Buy & hold return": bh if bh is not None else np.nan,
        "CAGR": cagr if cagr is not None else np.nan,
        "Annualized volatility": vol if vol is not None else np.nan,
        "Sharpe": sharpe if sharpe is not None else np.nan,
        "Max drawdown": mdd if mdd is not None else np.nan,
        "Hit rate": hit if hit is not None else np.nan,
        "Trades": float(trades),
    }
    bt_out = bt.reset_index()
    if "date" not in bt_out.columns:
        first_col = bt_out.columns[0]
        bt_out = bt_out.rename(columns={first_col: "date"})
    bt_out["date"] = pd.to_datetime(bt_out["date"], errors="coerce")
    return bt_out, metrics


def sector_etf(info: dict[str, Any]) -> str | None:
    sector = str(info.get("sector", "")).strip().lower()
    if not sector:
        return None
    return SECTOR_ETF_MAP.get(sector)


def main() -> None:
    st.set_page_config(page_title="250 Indicator Score", layout="wide")
    st.title("250 Indicator Score + Backtest (Streamlit)")
    st.caption("Score range: -100 (short bias) to +100 (buy bias). Uses all listed indicators when data is available.")

    with st.sidebar:
        ticker = st.text_input("Ticker", "NVDA").strip().upper()
        c1, c2 = st.columns(2)
        with c1:
            start_dt = st.date_input("Start date", date(2022, 11, 5))
        with c2:
            end_dt = st.date_input("End date", date(2023, 2, 6))
        benchmark = st.text_input("Benchmark", "SPY").strip().upper()
        threshold = st.slider("Trade threshold", 0.0, 50.0, 10.0, 1.0)
        st.divider()
        finnhub_key = st.text_input("Finnhub API key", value=os.getenv("FINNHUB_API_KEY", ""), type="password")
        alpaca_key = st.text_input("Alpaca API key", value=os.getenv("ALPACA_API_KEY", ""), type="password")
        alpaca_secret = st.text_input("Alpaca API secret", value=os.getenv("ALPACA_API_SECRET", ""), type="password")
        run_btn = st.button("Run analysis", type="primary")

    if not run_btn:
        st.info("Set inputs and click `Run analysis`.")
        return
    if not ticker:
        st.error("Ticker is required.")
        return
    if end_dt <= start_dt:
        st.error("End date must be after start date.")
        return
    if TOTAL_INDICATORS != 250:
        st.warning(f"Indicator catalog count is {TOTAL_INDICATORS}, expected 250.")

    lookback = start_dt - timedelta(days=5500)
    with st.spinner("Fetching data and computing indicators..."):
        prices = fetch_history(ticker, lookback, end_dt)
        if prices.empty:
            st.error(f"No history found for {ticker}.")
            return
        bench = fetch_history(benchmark, lookback, end_dt)
        features = feature_frame(prices, bench if not bench.empty else None)
        snapshot = fetch_snapshot(ticker)
        finnhub = fetch_finnhub(ticker, finnhub_key, end_dt) if finnhub_key else {}
        alpaca = fetch_alpaca(ticker, alpaca_key, alpaca_secret) if alpaca_key and alpaca_secret else {}
        bench_features = feature_frame(bench) if not bench.empty else pd.DataFrame()
        sec_px = pd.DataFrame()
        sec_symbol = sector_etf(snapshot.get("info", {}))
        if sec_symbol:
            sec_px = fetch_history(sec_symbol, lookback, end_dt)
        sec_features = feature_frame(sec_px) if not sec_px.empty else pd.DataFrame()

        indicator_df, dyn_signals, static_signals = build_indicators(
            ticker,
            features,
            snapshot,
            finnhub,
            alpaca,
            bench_features,
            sec_features,
        )
        mask = (features.index.date >= start_dt) & (features.index.date <= end_dt)
        dates = features.loc[mask].index
        score_df = score_series(dates, dyn_signals, static_signals)
        bt_df, bt_metrics = backtest(features, score_df, start_dt, end_dt, threshold)

    if score_df.empty:
        st.error("Unable to build score series for this window.")
        return

    latest = score_df.iloc[-1]
    score = safe_float(latest.get("score")) or 0.0
    cov = safe_float(latest.get("coverage_pct")) or 0.0
    avail = int(latest.get("available_signals", 0))
    bias = "BUY" if score >= threshold else ("SHORT" if score <= -threshold else "HOLD")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Composite score (-100 to +100)", f"{score:.2f}", f"{bias} bias")
    m2.metric("Indicator coverage (count / %)", f"{avail}/{TOTAL_INDICATORS}", f"{cov:.1f}% available")
    m3.metric("Ticker", ticker)
    m4.metric("Backtest window", f"{start_dt} to {end_dt}")

    tabs = st.tabs(["Results", "Backtest", "Indicators", "Downloads"])

    with tabs[0]:
        st.subheader("Results")
        chart = pd.DataFrame(index=score_df["date"])
        chart["Composite Score (-100 to +100)"] = score_df["score"].values
        chart["Close Price (USD)"] = features["Close"].reindex(score_df["date"]).values
        st.caption("Score > 0 indicates bullish bias, Score < 0 indicates bearish bias. Thresholds are applied in Backtest tab.")
        st.line_chart(chart[["Composite Score (-100 to +100)"]], height=240)
        st.caption("Daily close price in USD for the selected ticker.")
        st.line_chart(chart[["Close Price (USD)"]], height=240)
        score_display = score_df.rename(
            columns={
                "date": "Date",
                "score": "Composite Score (-100 to +100)",
                "available_signals": "Available Indicators (count)",
                "coverage_pct": "Coverage (%)",
            }
        )
        st.dataframe(score_display.tail(100), use_container_width=True, hide_index=True)

    with tabs[1]:
        st.subheader("Backtest")
        if bt_df.empty:
            st.warning("No backtest data in selected range.")
        else:
            b1, b2, b3, b4 = st.columns(4)
            b1.metric("Strategy total return (%)", f"{bt_metrics['Total return'] * 100:.2f}%")
            b2.metric("Buy & hold return (%)", f"{bt_metrics['Buy & hold return'] * 100:.2f}%")
            b3.metric("Sharpe ratio (annualized)", f"{bt_metrics['Sharpe']:.2f}")
            b4.metric("Max drawdown (%)", f"{bt_metrics['Max drawdown'] * 100:.2f}%")

            st.caption(
                "Position rule: long when score >= threshold, short when score <= -threshold, otherwise flat. "
                "Position is shifted by 1 bar (next-day execution)."
            )

            eq = bt_df.set_index("date")[["strategy_equity", "buy_hold_equity"]]
            eq.columns = ["Strategy Equity (start=1.0)", "BuyHold Equity (start=1.0)"]
            st.line_chart(eq, height=280)

            st.caption("Drawdown series = equity / running peak - 1. Lower is worse.")
            dd = bt_df.set_index("date")[["strategy_drawdown", "buy_hold_drawdown"]]
            dd.columns = ["Strategy Drawdown", "BuyHold Drawdown"]
            st.area_chart(dd, height=220)

            bt_display = bt_df.rename(
                columns={
                    "date": "Date",
                    "score": "Score (-100 to +100)",
                    "position": "Executed Position (-1/0/+1)",
                    "strategy_ret": "Strategy Return (daily %)",
                    "buy_hold_ret": "BuyHold Return (daily %)",
                    "strategy_equity": "Strategy Equity",
                    "buy_hold_equity": "BuyHold Equity",
                }
            ).copy()
            bt_display["Strategy Return (daily %)"] = bt_display["Strategy Return (daily %)"] * 100.0
            bt_display["BuyHold Return (daily %)"] = bt_display["BuyHold Return (daily %)"] * 100.0
            st.dataframe(
                bt_display[
                    [
                        "Date",
                        "Score (-100 to +100)",
                        "Executed Position (-1/0/+1)",
                        "Strategy Return (daily %)",
                        "BuyHold Return (daily %)",
                        "Strategy Equity",
                        "BuyHold Equity",
                    ]
                ].tail(200),
                use_container_width=True,
                hide_index=True,
            )

    with tabs[2]:
        st.subheader("Indicator Table")
        st.caption(
            f"{int(indicator_df['Available'].sum())}/{TOTAL_INDICATORS} indicators available. "
            "Unavailable rows are still shown to preserve the full 250-indicator structure."
        )
        summary = (
            indicator_df.groupby("Category", dropna=False)["Available"]
            .agg(["sum", "count"])
            .reset_index()
            .rename(columns={"sum": "Available", "count": "Total"})
        )
        summary["Coverage %"] = 100.0 * summary["Available"] / summary["Total"]
        st.dataframe(summary, use_container_width=True, hide_index=True)
        only_avail = st.checkbox("Show only available indicators", value=False)
        show_df = indicator_df[indicator_df["Available"]].copy() if only_avail else indicator_df
        st.dataframe(show_df, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.subheader("Downloads")
        st.download_button(
            "Indicators CSV",
            data=indicator_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{ticker}_indicator_table.csv",
            mime="text/csv",
        )
        st.download_button(
            "Score history CSV",
            data=score_df.to_csv(index=False).encode("utf-8"),
            file_name=f"{ticker}_score_history.csv",
            mime="text/csv",
        )
        if not bt_df.empty:
            st.download_button(
                "Backtest CSV",
                data=bt_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{ticker}_backtest.csv",
                mime="text/csv",
            )


if __name__ == "__main__":
    main()
