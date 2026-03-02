from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf


DEFAULT_META_CACHE = Path("TradesV2/data/ticker_metadata_cache.csv")


def load_tickers_from_csv(path: str, limit: int = 0) -> list[str]:
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return []
    try:
        frame = pd.read_csv(file_path)
    except Exception:
        return []

    if frame.empty:
        return []
    column = "ticker" if "ticker" in frame.columns else frame.columns[0]
    tickers = (
        frame[column]
        .astype(str)
        .str.upper()
        .str.strip()
        .replace({"": pd.NA})
        .dropna()
        .tolist()
    )
    tickers = list(dict.fromkeys(tickers))
    if limit > 0:
        tickers = tickers[: int(limit)]
    return tickers


def _load_meta_cache(cache_path: Path) -> pd.DataFrame:
    if not cache_path.exists():
        return pd.DataFrame(columns=["ticker", "sector", "industry", "market_cap", "source"])
    try:
        out = pd.read_csv(cache_path)
        for col in ["ticker", "sector", "industry", "market_cap", "source"]:
            if col not in out.columns:
                out[col] = pd.NA
        out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
        return out.drop_duplicates(subset=["ticker"], keep="last").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["ticker", "sector", "industry", "market_cap", "source"])


def _save_meta_cache(frame: pd.DataFrame, cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache_path, index=False)


def _fetch_single_metadata(ticker: str) -> dict[str, object]:
    sector = ""
    industry = ""
    market_cap = pd.NA
    source = "yfinance"
    try:
        info = yf.Ticker(ticker).info
        if isinstance(info, dict):
            sector = str(info.get("sector", "") or "").strip()
            industry = str(info.get("industry", "") or "").strip()
            market_cap = info.get("marketCap", pd.NA)
    except Exception:
        source = "error"
    return {
        "ticker": ticker,
        "sector": sector,
        "industry": industry,
        "market_cap": market_cap,
        "source": source,
    }


def enrich_ticker_metadata(
    tickers: Iterable[str],
    cache_path: str | Path = DEFAULT_META_CACHE,
    max_fetch: int = 300,
    refresh: bool = False,
) -> pd.DataFrame:
    tickers_list = [str(t).upper().strip() for t in tickers if str(t).strip()]
    tickers_list = list(dict.fromkeys(tickers_list))
    cache_path = Path(cache_path)
    cache = pd.DataFrame(columns=["ticker", "sector", "industry", "market_cap", "source"]) if refresh else _load_meta_cache(cache_path)

    known = set(cache["ticker"].astype(str).str.upper().tolist()) if not cache.empty else set()
    missing = [ticker for ticker in tickers_list if ticker not in known]
    to_fetch = missing[: max(0, int(max_fetch))]

    fetched_rows = [_fetch_single_metadata(ticker) for ticker in to_fetch]
    if fetched_rows:
        fetched = pd.DataFrame(fetched_rows)
        cache = pd.concat([cache, fetched], ignore_index=True)
        cache = cache.drop_duplicates(subset=["ticker"], keep="last").reset_index(drop=True)
        _save_meta_cache(cache, cache_path=cache_path)

    if cache.empty:
        return pd.DataFrame(columns=["ticker", "sector", "industry", "market_cap", "source"])

    out = cache[cache["ticker"].isin(tickers_list)].copy()
    order_map = {ticker: idx for idx, ticker in enumerate(tickers_list)}
    out["order"] = out["ticker"].map(order_map)
    out = out.sort_values("order").drop(columns=["order"]).reset_index(drop=True)
    return out


def filter_universe_by_profile(
    metadata: pd.DataFrame,
    sectors: list[str] | None = None,
    industry_query: str = "",
) -> pd.DataFrame:
    if metadata is None or metadata.empty:
        return pd.DataFrame(columns=["ticker", "sector", "industry", "market_cap", "source"])

    out = metadata.copy()
    out["sector"] = out["sector"].astype(str)
    out["industry"] = out["industry"].astype(str)

    if sectors:
        sectors_clean = {s.lower().strip() for s in sectors if str(s).strip()}
        if sectors_clean:
            out = out[out["sector"].str.lower().isin(sectors_clean)].copy()

    query = str(industry_query or "").strip().lower()
    if query:
        out = out[out["industry"].str.lower().str.contains(query, na=False)].copy()

    return out.reset_index(drop=True)
