"""
Institutional scoring models: Accumulation Score & Institutional Consensus.
Descriptive metrics only — explicitly not financial advice or price predictions.
"""

from institutional.models import AccumulationScoreConfig


def calculate_accumulation_score(
    holding_change_pct_points: float,
    funds_increased: int,
    funds_reduced: int,
    new_funds: int,
    exited_funds: int,
    config: AccumulationScoreConfig
) -> float:
    """
    Computes a configurable accumulation score:
    - MF holding increase: +config.holding_increase
    - New MF entry: +config.new_entry * new_funds
    - MF holding decrease: +config.holding_decrease (negative)
    - MF exit: +config.exit * exited_funds (negative)
    - Multiple funds increasing: +config.multiple_funds_increasing * funds_increased
    - Multiple funds decreasing: +config.multiple_funds_decreasing * funds_reduced
    - Significant holding increase: +config.significant_increase
    - Significant holding decrease: +config.significant_decrease

    Returns:
    Normalized metric between 0.0 and 100.0 (50 is neutral).
    """
    raw_score = 0.0

    # Overall holding direction
    if holding_change_pct_points > 0:
        raw_score += config.holding_increase
    elif holding_change_pct_points < 0:
        raw_score += config.holding_decrease

    # Significant threshold
    if abs(holding_change_pct_points) >= config.significant_threshold_pct:
        if holding_change_pct_points > 0:
            raw_score += config.significant_increase
        else:
            raw_score += config.significant_decrease

    # Fund entries and exits
    raw_score += new_funds * config.new_entry
    raw_score += exited_funds * config.exit

    # Multi-fund additions/reductions
    raw_score += funds_increased * config.multiple_funds_increasing
    raw_score += funds_reduced * config.multiple_funds_decreasing

    # Normalize to 0 - 100 range with baseline 50
    # Sigmoidal / linear bounded scaling
    normalized = 50.0 + (raw_score * 2.5)
    clamped = max(0.0, min(100.0, normalized))
    return round(clamped, 1)


def calculate_institutional_consensus(
    mf_holding_change_pp: float,
    fii_holding_change_pp: float,
    num_mf_buyers: int,
    num_mf_sellers: int,
) -> dict:
    """
    Combines MF, FII, and DII patterns to determine descriptive institutional trend.
    """
    # MF Trend
    if mf_holding_change_pp >= 0.2 and num_mf_buyers > num_mf_sellers:
        mf_trend = "🟢 ACCUMULATING"
        mf_val = 1
    elif mf_holding_change_pp <= -0.2 and num_mf_sellers > num_mf_buyers:
        mf_trend = "🔴 DISTRIBUTING"
        mf_val = -1
    else:
        mf_trend = "🟡 NEUTRAL"
        mf_val = 0

    # FII Trend
    if fii_holding_change_pp >= 0.2:
        fii_trend = "🟢 INCREASING"
        fii_val = 1
    elif fii_holding_change_pp <= -0.2:
        fii_trend = "🔴 DECREASING"
        fii_val = -1
    else:
        fii_trend = "🟡 NEUTRAL"
        fii_val = 0

    # DII Trend (derived from MF + general DII flow)
    dii_trend = "🟢 ACCUMULATING" if mf_val > 0 else ("🔴 DISTRIBUTING" if mf_val < 0 else "🟡 NEUTRAL")

    # Combined score
    composite = (mf_val * 2) + (fii_val * 2) + (1 if num_mf_buyers >= 5 else 0)

    if composite >= 3:
        overall = "STRONG ACCUMULATION"
    elif composite >= 1:
        overall = "ACCUMULATION"
    elif composite <= -3:
        overall = "STRONG DISTRIBUTION"
    elif composite <= -1:
        overall = "DISTRIBUTION"
    else:
        overall = "NEUTRAL"

    return {
        "mf_trend": mf_trend,
        "fii_trend": fii_trend,
        "dii_trend": dii_trend,
        "overall_trend": overall,
        "composite_score": composite
    }
