"""
Tests for data validation rules:
- Invalid percentages (< 0 or > 100)
- Missing required fields (ISIN, fund_id, reporting_date)
- Duplicate row deduplication
"""

import tempfile
import os
import pytest
from institutional.db.database import init_db
from institutional.db.repository import InstitutionalRepository
from institutional.models import MFHolding, InstitutionalDailyActivity, FIIHolding


@pytest.fixture
def temp_repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    repo = InstitutionalRepository(path)
    yield repo
    if os.path.exists(path):
        os.remove(path)


def test_reject_invalid_holding_percentage(temp_repo):
    """Holding percentage outside [0, 100] must be skipped."""
    invalid_holding_high = MFHolding(
        fund_id="F1",
        fund_name="Test Fund",
        amc_name="Test AMC",
        stock_symbol="BHEL",
        isin="INE257A01026",
        reporting_date="2024-08-31",
        holding_percent=105.0  # Invalid > 100%
    )
    invalid_holding_low = MFHolding(
        fund_id="F1",
        fund_name="Test Fund",
        amc_name="Test AMC",
        stock_symbol="BHEL",
        isin="INE257A01026",
        reporting_date="2024-08-31",
        holding_percent=-2.0  # Invalid < 0%
    )
    valid_holding = MFHolding(
        fund_id="F1",
        fund_name="Test Fund",
        amc_name="Test AMC",
        stock_symbol="BHEL",
        isin="INE257A01026",
        reporting_date="2024-08-31",
        holding_percent=5.25
    )

    ins, skp = temp_repo.insert_mf_holdings([invalid_holding_high, invalid_holding_low, valid_holding])
    assert ins == 1
    assert skp == 2


def test_reject_missing_required_fields(temp_repo):
    """Missing ISIN, fund_id, or reporting_date must be skipped."""
    missing_isin = MFHolding(
        fund_id="F1",
        fund_name="Test Fund",
        amc_name="Test AMC",
        stock_symbol="BHEL",
        isin="",
        reporting_date="2024-08-31",
        holding_percent=5.0
    )
    ins, skp = temp_repo.insert_mf_holdings([missing_isin])
    assert ins == 0
    assert skp == 1
