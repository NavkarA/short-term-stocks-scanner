"""
Stock Fundamentals & Financial Metrics Module.
Fetches, caches, and calculates key fundamental valuation metrics,
annual YoY revenue/profit growth, industry benchmarks, and volume expansion
for Indian National Stock Exchange (NSE) equities.
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import yfinance as yf

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, "data", "fundamentals_cache.json")
CACHE_TTL_HOURS = 72  # Refresh fundamentals every 3 days

# Standard Indian Sector / Industry P/E Benchmarks (Source: NSE Sector Indices)
SECTOR_PE_BENCHMARKS: Dict[str, float] = {
    "Financial Services": 16.5,
    "Financials": 16.5,
    "Banks": 15.0,
    "Banking": 15.0,
    "Technology": 28.5,
    "Information Technology": 28.5,
    "IT": 28.5,
    "Healthcare": 34.0,
    "Pharmaceuticals": 34.0,
    "Pharma": 34.0,
    "Consumer Cyclical": 36.0,
    "Automobile": 24.0,
    "Auto": 24.0,
    "Auto Ancillary": 28.0,
    "Consumer Defensive": 42.0,
    "FMCG": 42.0,
    "Basic Materials": 14.5,
    "Metals & Mining": 14.5,
    "Metals": 14.5,
    "Energy": 13.0,
    "Oil & Gas": 13.0,
    "Industrials": 35.0,
    "Capital Goods": 38.0,
    "Aerospace & Defence": 45.0,
    "Defence": 45.0,
    "Utilities": 18.0,
    "Power": 18.0,
    "Real Estate": 26.0,
    "Realty": 26.0,
    "Communication Services": 22.0,
    "Telecom": 22.0,
    "Chemicals": 25.0,
    "Textiles": 20.0,
    "Software - Infrastructure": 28.5,
    "Software - Application": 28.5,
    "Software": 28.5,
    "Construction & Infrastructure": 22.0,
    "Infra": 22.0
}


def load_fundamentals_cache() -> Dict[str, Any]:
    """Loads cached fundamental records from disk."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_fundamentals_cache(cache: Dict[str, Any]) -> None:
    """Persists fundamental records to disk."""
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def resolve_industry_pe(sector: str, industry: str, cached_data: Optional[Dict[str, Any]] = None) -> float:
    """
    Resolves benchmark Industry P/E ratio using sector mapping with fallback
    to industry peer median or the broader market median (~22.0).
    """
    # 1. Dynamic median from cached peers in the same industry/sector if provided
    if cached_data:
        peer_pes = [
            v["pe_ratio"] for v in cached_data.values()
            if isinstance(v, dict) and (v.get("industry") == industry or v.get("sector") == sector)
            and v.get("pe_ratio") and v["pe_ratio"] > 0
        ]
        if peer_pes:
            return round(float(pd.Series(peer_pes).median()), 1)

    # 2. Check specific industry benchmarks (sorted by key length descending)
    for key, val in sorted(SECTOR_PE_BENCHMARKS.items(), key=lambda x: len(x[0]), reverse=True):
        if key.lower() in industry.lower():
            return val

    # 3. Check sector benchmarks
    for key, val in sorted(SECTOR_PE_BENCHMARKS.items(), key=lambda x: len(x[0]), reverse=True):
        if key.lower() in sector.lower():
            return val

    return 22.0  # Nifty 50 long-term median P/E


def fetch_single_ticker_fundamentals(symbol: str) -> Dict[str, Any]:
    """
    Queries Yahoo Finance for a stock's valuation, financial growth,
    margins, and balance sheet quality ratios.
    """
    sym = symbol.strip().upper().replace(".NS", "")
    yf_symbol = sym + ".NS"

    result: Dict[str, Any] = {
        "symbol": sym,
        "pe_ratio": 0.0,
        "industry_pe": 22.0,
        "market_cap_cr": 0.0,
        "yoy_revenue_growth_pct": 0.0,
        "yoy_profit_growth_pct": 0.0,
        "roe_pct": 0.0,
        "debt_to_equity": 0.0,
        "operating_margin_pct": 0.0,
        "sector": "Other",
        "industry": "Other",
        "updated_at": datetime.now().isoformat()
    }

    try:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info or {}

        # 1. P/E Ratio
        pe = info.get("trailingPE") or info.get("forwardPE")
        if pe and isinstance(pe, (int, float)) and pe > 0:
            result["pe_ratio"] = round(float(pe), 1)

        # 2. Market Cap (Converted to ₹ Crores)
        mcap = info.get("marketCap")
        if mcap and isinstance(mcap, (int, float)) and mcap > 0:
            result["market_cap_cr"] = round(float(mcap) / 1e7, 1)

        # 3. Sector & Industry
        sec = info.get("sector") or "Other"
        ind = info.get("industry") or "Other"
        result["sector"] = sec
        result["industry"] = ind
        result["industry_pe"] = resolve_industry_pe(sec, ind)

        # 4. ROE %
        roe = info.get("returnOnEquity")
        if roe and isinstance(roe, (int, float)):
            result["roe_pct"] = round(float(roe) * 100.0, 1)

        # 5. Debt to Equity
        de = info.get("debtToEquity")
        if de and isinstance(de, (int, float)):
            # yfinance returns debtToEquity as a percentage (e.g. 36.65 for 0.37)
            result["debt_to_equity"] = round(float(de) / 100.0 if de > 3.0 else float(de), 2)

        # 6. Operating Margin %
        opm = info.get("operatingMargins")
        if opm and isinstance(opm, (int, float)):
            result["operating_margin_pct"] = round(float(opm) * 100.0, 1)

        # 7. YoY Revenue & Profit Growth from Audited Financials
        yoy_rev = 0.0
        yoy_pat = 0.0

        try:
            fin = ticker.financials
            if fin is not None and not fin.empty:
                # Revenue Growth (Latest Year vs Previous Year)
                if "Total Revenue" in fin.index and len(fin.columns) >= 2:
                    r_curr = float(fin.loc["Total Revenue"].iloc[0])
                    r_prev = float(fin.loc["Total Revenue"].iloc[1])
                    if r_prev > 0:
                        yoy_rev = ((r_curr - r_prev) / r_prev) * 100.0

                # Net Income / PAT Growth
                if "Net Income" in fin.index and len(fin.columns) >= 2:
                    p_curr = float(fin.loc["Net Income"].iloc[0])
                    p_prev = float(fin.loc["Net Income"].iloc[1])
                    if abs(p_prev) > 0:
                        yoy_pat = ((p_curr - p_prev) / abs(p_prev)) * 100.0
        except Exception:
            pass

        # Fallback to info growth metrics if financials table was unavailable
        if yoy_rev == 0.0 and info.get("revenueGrowth"):
            yoy_rev = float(info["revenueGrowth"]) * 100.0
        if yoy_pat == 0.0 and info.get("earningsGrowth"):
            yoy_pat = float(info["earningsGrowth"]) * 100.0

        result["yoy_revenue_growth_pct"] = round(yoy_rev, 1)
        result["yoy_profit_growth_pct"] = round(yoy_pat, 1)

    except Exception:
        pass

    return result


def get_stock_fundamentals(symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
    """
    Returns fundamental metrics for a single stock with local cache lookaside.
    """
    sym = symbol.strip().upper().replace(".NS", "")
    cache = load_fundamentals_cache()

    if not force_refresh and sym in cache:
        rec = cache[sym]
        up_ts = rec.get("updated_at")
        if up_ts:
            try:
                age_hours = (datetime.now() - datetime.fromisoformat(up_ts)).total_seconds() / 3600.0
                if age_hours < CACHE_TTL_HOURS:
                    return rec
            except Exception:
                pass

    # Fetch fresh
    data = fetch_single_ticker_fundamentals(sym)
    cache[sym] = data
    save_fundamentals_cache(cache)
    return data


def get_batch_fundamentals(symbols: List[str], force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Batch fetches fundamental records for a list of stocks.
    Uses disk cache and queries fresh data for missing or expired entries.
    """
    clean_syms = list(set([s.strip().upper().replace(".NS", "") for s in symbols if s]))
    cache = load_fundamentals_cache()
    result: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []

    for sym in clean_syms:
        if not force_refresh and sym in cache:
            rec = cache[sym]
            up_ts = rec.get("updated_at")
            if up_ts:
                try:
                    age_hours = (datetime.now() - datetime.fromisoformat(up_ts)).total_seconds() / 3600.0
                    if age_hours < CACHE_TTL_HOURS:
                        result[sym] = rec
                        continue
                except Exception:
                    pass
        missing.append(sym)

    if missing:
        for sym in missing:
            data = fetch_single_ticker_fundamentals(sym)
            cache[sym] = data
            result[sym] = data

        save_fundamentals_cache(cache)

    return result


def compute_volume_growth_from_series(volume_series: pd.Series) -> Tuple[float, float]:
    """
    Computes 1-Week Volume Growth % and 1-Month Volume Growth % from a chronological volume series.
    - 1W Vol Growth: Last 5 days average volume vs prior 20 days baseline
    - 1M Vol Growth: Last 20 days average volume vs prior 60 days baseline
    """
    s = volume_series.dropna()
    n = len(s)
    if n < 6:
        return 0.0, 0.0

    # 1. One-Week Volume Expansion (Last 5 Days vs Prior 20 Days)
    recent_5 = float(s.iloc[-5:].mean())
    prior_20 = float(s.iloc[-25:-5].mean()) if n >= 25 else float(s.iloc[:-5].mean())
    vol_growth_1w = round(((recent_5 - prior_20) / prior_20) * 100.0, 1) if prior_20 > 0 else 0.0

    # 2. One-Month Volume Expansion (Last 20 Days vs Prior 60 Days)
    if n >= 25:
        recent_20 = float(s.iloc[-20:].mean())
        prior_60 = float(s.iloc[-80:-20].mean()) if n >= 80 else float(s.iloc[:-20].mean())
        vol_growth_1m = round(((recent_20 - prior_60) / prior_60) * 100.0, 1) if prior_60 > 0 else 0.0
    else:
        vol_growth_1m = vol_growth_1w

    return vol_growth_1w, vol_growth_1m
