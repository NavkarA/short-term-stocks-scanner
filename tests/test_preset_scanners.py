import pytest
from scraper import PRESET_SCANNERS


def test_new_short_term_screener_exists():
    assert "New Short Term Screener" in PRESET_SCANNERS
    screener = PRESET_SCANNERS["New Short Term Screener"]
    assert "clause" in screener
    assert "description" in screener


def test_new_short_term_screener_clause_rules():
    clause = PRESET_SCANNERS["New Short Term Screener"]["clause"]

    # Rule 1: 5-day max close > 1.05 * 120-day max close (Short Term Breakout base rule)
    assert "daily max( 5 , daily close ) > 6 days ago max( 120 , daily close ) * 1.05" in clause

    # Rule 2: Volume > 5-day SMA volume
    assert "daily volume > daily sma( volume,5 )" in clause

    # Rule 3: Previous day return > 9% (close > 1 day ago close * 1.09)
    assert "daily close > 1 day ago close * 1.09" in clause

    # Rule 4: Market Cap < 3000 Crore
    assert "market cap < 3000" in clause
