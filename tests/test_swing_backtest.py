import pytest
from unittest.mock import patch
import pandas as pd
from scraper import run_swing_backtest


def test_run_swing_backtest_empty_signals():
    trades_df, summary, date_summary = run_swing_backtest(signals_by_date={})
    assert trades_df.empty
    assert summary == {}
    assert date_summary.empty


def test_run_swing_backtest_3_tier_targets_and_weights():
    # Construct mock price data for a ticker
    mock_dates = pd.date_range("2026-03-01", periods=6, freq="B")
    mock_df = pd.DataFrame(
        {
            ("Open", "TEST.NS"): [100.0, 100.0, 102.0, 105.0, 108.0, 112.0],
            ("High", "TEST.NS"): [101.0, 104.0, 107.0, 111.0, 115.0, 116.0],
            ("Low", "TEST.NS"):  [99.0,  99.5, 101.0, 104.0, 107.0, 110.0],
            ("Close", "TEST.NS"): [100.5, 103.5, 106.0, 110.0, 114.0, 115.0],
            ("Volume", "TEST.NS"): [1000] * 6,
            ("Open", "^NSEI"): [22000.0] * 6,
            ("High", "^NSEI"): [22100.0] * 6,
            ("Low", "^NSEI"): [21900.0] * 6,
            ("Close", "^NSEI"): [22050.0] * 6,
            ("Volume", "^NSEI"): [5000] * 6,
        },
        index=mock_dates
    )
    mock_df.columns = pd.MultiIndex.from_tuples(mock_df.columns)

    sig_date = mock_dates[0].strftime("%Y-%m-%d")
    signals = {
        sig_date: [{"symbol": "TEST", "name": "Test Company"}]
    }

    with patch("yfinance.download", return_value=mock_df):
        trades_df, summary, date_summary = run_swing_backtest(
            signals_by_date=signals,
            target_1_pct=3.0,
            target_2_pct=6.0,
            target_3_pct=10.0,
            sl_pct=2.0,
            max_holding_days=5,
            num_days=1,
            enable_trailing_sl=True,
            trailing_sl_pct=2.0,
            trail_trigger="After Target 1",
            t1_book_pct=50.0,
            t2_book_pct=30.0
        )

    assert not trades_df.empty
    row = trades_df.iloc[0]
    assert row["Symbol"] == "TEST"
    assert row["Target 1 Price"] == 103.0
    assert row["Target 2 Price"] == 106.0
    assert row["Target 3 Price"] == 110.0
    assert "Target 3 Hits" in date_summary.columns
    assert "t3_hit_count" in summary
