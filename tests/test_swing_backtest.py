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
    assert "Prev Day Return %" in row
    assert "Target 3 Hits" in date_summary.columns
    assert "t3_hit_count" in summary


def test_intraday_ambiguity_conservative_vs_optimistic():
    # Day 0: Signal Day
    # Day 1: Entry Day with wide whipsaw: High touches +4%, Low touches -3%
    mock_dates = pd.date_range("2026-03-01", periods=3, freq="B")
    mock_df = pd.DataFrame(
        {
            ("Open", "TEST.NS"): [100.0, 100.0, 100.0],
            ("High", "TEST.NS"): [101.0, 104.5, 102.0],  # Day 1 touches +4.5% (above Target 1 3.5%)
            ("Low", "TEST.NS"):  [99.0,  97.0,  99.0],   # Day 1 touches -3.0% (below SL 2.0%)
            ("Close", "TEST.NS"): [100.0, 101.0, 100.0],
            ("Volume", "TEST.NS"): [1000, 1000, 1000],
            ("Open", "^NSEI"): [22000.0] * 3,
            ("High", "^NSEI"): [22100.0] * 3,
            ("Low", "^NSEI"): [21900.0] * 3,
            ("Close", "^NSEI"): [22050.0] * 3,
            ("Volume", "^NSEI"): [5000] * 3,
        },
        index=mock_dates
    )
    mock_df.columns = pd.MultiIndex.from_tuples(mock_df.columns)
    sig_date = mock_dates[0].strftime("%Y-%m-%d")
    signals = {sig_date: [{"symbol": "TEST", "name": "Test Company"}]}

    # 1. Conservative Mode: Stop loss must be assumed hit first
    with patch("yfinance.download", return_value=mock_df):
        trades_cons, _, _ = run_swing_backtest(
            signals_by_date=signals,
            target_1_pct=3.5,
            sl_pct=2.0,
            intraday_ambiguity="Conservative (SL First)"
        )
    assert not trades_cons.empty
    row_cons = trades_cons.iloc[0]
    assert "Stop Loss Hit" in row_cons["Outcome"]
    assert row_cons["Realized Return %"] == -2.0

    # 2. Optimistic Mode: Target must be assumed hit first
    with patch("yfinance.download", return_value=mock_df):
        trades_opt, _, _ = run_swing_backtest(
            signals_by_date=signals,
            target_1_pct=3.5,
            sl_pct=2.0,
            intraday_ambiguity="Optimistic (Target First)"
        )
    assert not trades_opt.empty
    row_opt = trades_opt.iloc[0]
    # In optimistic mode, T1 was booked first
    assert "T1" in row_opt["Outcome"] or "Target 1" in row_opt["Outcome"]
    assert row_opt["Realized Return %"] > -2.0


def test_intraday_ambiguity_proximity():
    # Day 1: Open 100.0. Target +1.0% (101.0), SL -3.0% (97.0).
    # High touches 102.0, Low touches 96.0.
    # Open is closer to Target (1.0 vs 3.0), so proximity should choose Target first!
    mock_dates = pd.date_range("2026-03-01", periods=3, freq="B")
    mock_df = pd.DataFrame(
        {
            ("Open", "TEST.NS"): [100.0, 100.0, 100.0],
            ("High", "TEST.NS"): [101.0, 102.0, 100.0],
            ("Low", "TEST.NS"):  [99.0,  96.0,  99.0],
            ("Close", "TEST.NS"): [100.0, 100.0, 100.0],
            ("Volume", "TEST.NS"): [1000, 1000, 1000],
            ("Open", "^NSEI"): [22000.0] * 3,
            ("High", "^NSEI"): [22100.0] * 3,
            ("Low", "^NSEI"): [21900.0] * 3,
            ("Close", "^NSEI"): [22050.0] * 3,
            ("Volume", "^NSEI"): [5000] * 3,
        },
        index=mock_dates
    )
    mock_df.columns = pd.MultiIndex.from_tuples(mock_df.columns)
    sig_date = mock_dates[0].strftime("%Y-%m-%d")
    signals = {sig_date: [{"symbol": "TEST", "name": "Test Company"}]}

    with patch("yfinance.download", return_value=mock_df):
        trades_prox, _, _ = run_swing_backtest(
            signals_by_date=signals,
            target_1_pct=1.0,
            sl_pct=3.0,
            intraday_ambiguity="Proximity (Closer Level First)"
        )
    assert not trades_prox.empty
    row_prox = trades_prox.iloc[0]
    # Since target was closer to Open, target was hit first
    assert "T1" in row_prox["Outcome"] or "Target 1" in row_prox["Outcome"]


def test_5m_candles_pinpoint_entry_and_intraday_sequence():
    # Day 0: 2026-03-02 (Signal day)
    # Day 1: 2026-03-03 (Entry day with 5-minute candles)
    # Bar 0 (09:15): Open 34.40, High 34.50, Low 34.30, Close 34.45 (Entry pinpoint at 34.40!)
    # Bar 1 (09:20): Open 34.45, High 34.45, Low 33.60, Close 33.65 (Dips below SL -2% = 33.71!)
    # Bar 10 (10:05): Later rallies to 36.00 (above Target 1) - But was already stopped out at 09:20!
    times = [
        "2026-03-02 09:15", "2026-03-02 15:25",
        "2026-03-03 09:15", "2026-03-03 09:20", "2026-03-03 10:05"
    ]
    mock_idx = pd.to_datetime(times)
    mock_df = pd.DataFrame(
        {
            ("Open", "GEEK.NS"):  [32.0, 33.0, 34.40, 34.45, 35.50],
            ("High", "GEEK.NS"):  [32.5, 33.5, 34.50, 34.45, 36.00],
            ("Low", "GEEK.NS"):   [31.8, 32.8, 34.30, 33.60, 35.40],
            ("Close", "GEEK.NS"): [32.2, 33.4, 34.45, 33.65, 35.80],
            ("Volume", "GEEK.NS"): [1000, 1000, 5000, 2000, 3000],
            ("Open", "^NSEI"):  [22000.0] * 5,
            ("High", "^NSEI"):  [22100.0] * 5,
            ("Low", "^NSEI"):   [21900.0] * 5,
            ("Close", "^NSEI"): [22050.0] * 5,
            ("Volume", "^NSEI"): [5000] * 5,
        },
        index=mock_idx
    )
    mock_df.columns = pd.MultiIndex.from_tuples(mock_df.columns)
    signals = {"2026-03-02": [{"symbol": "GEEK", "name": "Geek Corp"}]}

    with patch("yfinance.download", return_value=mock_df):
        trades_df, summary, _ = run_swing_backtest(
            signals_by_date=signals,
            target_1_pct=3.5,
            sl_pct=2.0
        )

    assert not trades_df.empty
    trade = trades_df.iloc[0]
    # Pinpoint entry at exact 09:15 opening price 34.40
    assert trade["Entry Price"] == 34.40
    # Stopped out at 09:20 before later rally
    assert "09:20" in trade["Outcome"]
    assert "Stop Loss Hit" in trade["Outcome"]


