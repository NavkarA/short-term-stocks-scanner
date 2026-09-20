import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from fundamentals import (
    resolve_industry_pe,
    compute_volume_growth_from_series,
    get_stock_fundamentals,
    load_fundamentals_cache,
    save_fundamentals_cache
)


def test_resolve_industry_pe():
    # Known sectors
    assert resolve_industry_pe("Energy", "Oil & Gas") == 13.0
    assert resolve_industry_pe("Technology", "Software") == 28.5
    assert resolve_industry_pe("Healthcare", "Pharmaceuticals") == 34.0
    assert resolve_industry_pe("Financials", "Banking") == 15.0

    # Fallback to default
    assert resolve_industry_pe("Unknown Sector", "Unknown Industry") == 22.0

    # Dynamic median fallback
    mock_cache = {
        "S1": {"sector": "Mining", "industry": "Rare Metals", "pe_ratio": 12.0},
        "S2": {"sector": "Mining", "industry": "Rare Metals", "pe_ratio": 16.0},
        "S3": {"sector": "Mining", "industry": "Rare Metals", "pe_ratio": 20.0},
    }
    assert resolve_industry_pe("Mining", "Rare Metals", cached_data=mock_cache) == 16.0


def test_compute_volume_growth():
    # 1. 25-day volume series with sharp 1W expansion
    # 20 days at 1000, last 5 days at 2500
    v = pd.Series([1000] * 20 + [2500] * 5)
    w1, m1 = compute_volume_growth_from_series(v)
    assert w1 == 150.0
    assert m1 == 37.5

    # 2. Volume contraction
    v_down = pd.Series([2000] * 20 + [1000] * 5)
    w_down, _ = compute_volume_growth_from_series(v_down)
    assert w_down == -50.0

    # 3. Short series (< 6 items) returns 0.0, 0.0
    v_short = pd.Series([100, 200, 300])
    w_s, m_s = compute_volume_growth_from_series(v_short)
    assert w_s == 0.0
    assert m_s == 0.0


def test_get_stock_fundamentals_with_mock():
    mock_info = {
        "trailingPE": 25.4,
        "marketCap": 50000000000,  # 5000 Cr
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "returnOnEquity": 0.185,
        "debtToEquity": 15.2,
        "operatingMargins": 0.224,
        "revenueGrowth": 0.142,
        "earningsGrowth": 0.215
    }

    mock_ticker = MagicMock()
    mock_ticker.info = mock_info
    mock_ticker.financials = None

    with patch("yfinance.Ticker", return_value=mock_ticker):
        data = get_stock_fundamentals("MOCKTECH", force_refresh=True)

    assert data["symbol"] == "MOCKTECH"
    assert data["pe_ratio"] == 25.4
    assert data["industry_pe"] == 28.5
    assert data["market_cap_cr"] == 5000.0
    assert data["roe_pct"] == 18.5
    assert data["debt_to_equity"] == 0.15
    assert data["operating_margin_pct"] == 22.4
    assert data["yoy_revenue_growth_pct"] == 14.2
    assert data["yoy_profit_growth_pct"] == 21.5
