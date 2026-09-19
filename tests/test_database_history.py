"""
Tests for database historical record preservation and deduplication.
Ensures that reporting date history is preserved and never overwritten.
"""

import tempfile
import os
import pytest
from institutional.db.database import init_db
from institutional.db.repository import InstitutionalRepository
from institutional.models import MFHolding, FIIHolding


@pytest.fixture
def temp_repo():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    repo = InstitutionalRepository(path)
    yield repo
    if os.path.exists(path):
        os.remove(path)


def test_preserve_historical_disclosures(temp_repo):
    """
    Section 24:
    Fund A -> BHEL:
    31-Jul-2024 -> 7.33%
    31-Aug-2024 -> 9.87%
    Both records must remain in the database.
    """
    h_july = MFHolding(
        fund_id="QUANT_PSU",
        fund_name="Quant PSU Fund",
        amc_name="Quant Mutual Fund",
        stock_symbol="BHEL",
        isin="INE257A01026",
        reporting_date="2024-07-31",
        holding_percent=7.33,
        shares=25000000.0
    )
    h_aug = MFHolding(
        fund_id="QUANT_PSU",
        fund_name="Quant PSU Fund",
        amc_name="Quant Mutual Fund",
        stock_symbol="BHEL",
        isin="INE257A01026",
        reporting_date="2024-08-31",
        holding_percent=9.87,
        shares=34000000.0
    )

    ins1, _ = temp_repo.insert_mf_holdings([h_july])
    ins2, _ = temp_repo.insert_mf_holdings([h_aug])
    assert ins1 == 1
    assert ins2 == 1

    # Check that both reporting dates exist
    hist = temp_repo.get_fund_stock_history("QUANT_PSU", "BHEL")
    assert len(hist) == 2
    dates = hist["reporting_date"].tolist()
    assert "2024-07-31" in dates
    assert "2024-08-31" in dates

    # Check deduplication on identical insert
    ins_dup, skp_dup = temp_repo.insert_mf_holdings([h_aug])
    assert ins_dup == 0
    assert skp_dup == 1
    hist_after_dup = temp_repo.get_fund_stock_history("QUANT_PSU", "BHEL")
    assert len(hist_after_dup) == 2
