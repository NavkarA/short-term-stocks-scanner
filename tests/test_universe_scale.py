"""
Test scale and performance of the 2,000+ stocks institutional database.
"""

import time
import pytest
from institutional.db.repository import InstitutionalRepository


def test_2000_stocks_universe_query_performance():
    repo = InstitutionalRepository()
    t0 = time.time()
    df = repo.get_all_stocks_mf_summary()
    t1 = time.time()
    elapsed = t1 - t0

    # Ensure at least 2000 stocks are loaded
    assert len(df) >= 2000, f"Expected >= 2000 stocks, got {len(df)}"

    # Ensure performance requirement (< 1.5 seconds)
    assert elapsed < 1.5, f"Query took {elapsed:.2f}s, expected < 1.5s"

    # Ensure expected columns are present
    required_cols = [
        "rank", "stock", "company_name", "sector", "market_cap",
        "current_mf_holding", "previous_mf_holding", "change_pct_points",
        "total_mf_schemes", "funds_increased", "funds_reduced", "new_funds",
        "exited_funds", "accumulation_score", "consensus_score"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
