"""
Unit tests for institutional calculations, position status classification,
relative vs percentage point changes, accumulation scores, and consensus.
Adheres to Section 55 and Section 56 test specifications.
"""

import pytest
from institutional.calculations.metrics import (
    calculate_holding_change,
    calculate_relative_change,
    calculate_shares_change,
    determine_position_status,
)
from institutional.calculations.scoring import (
    calculate_accumulation_score,
    calculate_institutional_consensus,
)
from institutional.models import AccumulationScoreConfig


def test_holding_change_and_relative_change():
    """
    Test Section 32 & 56:
    Previous: 5.0%
    Current: 7.0%
    Change: +2.00 percentage points
    Relative change: +40.0%
    """
    prev = 5.0
    curr = 7.0
    change_pp = calculate_holding_change(curr, prev)
    rel_change = calculate_relative_change(curr, prev)

    assert change_pp == 2.0
    assert rel_change == 40.0


def test_position_status_new():
    """
    Section 56 Example:
    Previous: Fund C -> BHEL -> 0%
    Current: Fund C -> BHEL -> 2%
    Expected Status: NEW
    """
    status = determine_position_status(current_holding_pct=2.0, previous_holding_pct=0.0)
    assert status == "NEW"


def test_position_status_exited():
    """
    Section 56 Example:
    Previous: Fund B -> BHEL -> 3%
    Current: Fund B -> BHEL -> 0%
    Expected Status: EXITED
    """
    status = determine_position_status(current_holding_pct=0.0, previous_holding_pct=3.0)
    assert status == "EXITED"


def test_position_status_increased():
    """
    Section 56 Example:
    Previous: Fund A -> BHEL -> 5%
    Current: Fund A -> BHEL -> 7%
    Expected: Change +2 pp, Status: INCREASED
    """
    status = determine_position_status(current_holding_pct=7.0, previous_holding_pct=5.0)
    assert status == "INCREASED"


def test_position_status_reduced():
    """
    Previous: 5.0% -> Current: 3.5%
    Expected: REDUCED
    """
    status = determine_position_status(current_holding_pct=3.5, previous_holding_pct=5.0)
    assert status == "REDUCED"


def test_position_status_unchanged():
    """
    Previous: 4.2% -> Current: 4.2%
    Expected: UNCHANGED
    """
    status = determine_position_status(current_holding_pct=4.2, previous_holding_pct=4.2)
    assert status == "UNCHANGED"


def test_shares_change():
    """
    Section 33: shares_change = current_shares - previous_shares
    Returns None if either is None
    """
    assert calculate_shares_change(1000000, 800000) == 200000
    assert calculate_shares_change(None, 500000) is None
    assert calculate_shares_change(500000, None) is None


def test_accumulation_scoring():
    """
    Tests configurable accumulation score logic (Section 6).
    """
    config = AccumulationScoreConfig()
    # High accumulation scenario: +2.5 pp change, 4 funds increased, 1 new entry
    score = calculate_accumulation_score(
        holding_change_pct_points=2.5,
        funds_increased=4,
        funds_reduced=0,
        new_funds=1,
        exited_funds=0,
        config=config
    )
    assert score > 70.0  # Strong accumulation

    # Heavy distribution scenario
    dist_score = calculate_accumulation_score(
        holding_change_pct_points=-2.0,
        funds_increased=0,
        funds_reduced=3,
        new_funds=0,
        exited_funds=2,
        config=config
    )
    assert dist_score < 40.0  # Distribution


def test_institutional_consensus():
    """
    Tests multi-institutional consensus synthesis.
    """
    res = calculate_institutional_consensus(
        mf_holding_change_pp=1.5,
        fii_holding_change_pp=0.8,
        num_mf_buyers=8,
        num_mf_sellers=1
    )
    assert "ACCUMULATING" in res["mf_trend"]
    assert "INCREASING" in res["fii_trend"]
    assert res["overall_trend"] in ("ACCUMULATION", "STRONG ACCUMULATION")
