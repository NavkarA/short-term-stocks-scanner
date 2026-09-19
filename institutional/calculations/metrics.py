"""
Core metrics and change calculations for institutional stock holdings.
Enforces strict distinction between:
- Percentage Points (e.g. 5% to 6% is +1.00 percentage point)
- Relative Change (e.g. 5% to 6% is +20.00% relative increase)
- Company Holding % vs Portfolio Weight %
"""

from typing import Optional, Tuple


def calculate_holding_change(current_holding_pct: float, previous_holding_pct: float) -> float:
    """
    Calculates change in percentage points:
    holding_change_pct_points = current_holding_pct - previous_holding_pct
    """
    return round(float(current_holding_pct) - float(previous_holding_pct), 4)


def calculate_relative_change(current_holding_pct: float, previous_holding_pct: float) -> float:
    """
    Calculates relative percentage increase/decrease:
    relative_change = (current / previous - 1) * 100
    Returns 0.0 if previous is 0.
    """
    if previous_holding_pct <= 0:
        return 100.0 if current_holding_pct > 0 else 0.0
    return round(((float(current_holding_pct) / float(previous_holding_pct)) - 1.0) * 100.0, 2)


def calculate_shares_change(
    current_shares: Optional[float],
    previous_shares: Optional[float]
) -> Optional[float]:
    """
    Calculates shares change:
    shares_change = current_shares - previous_shares
    Returns None if either is unavailable.
    """
    if current_shares is None or previous_shares is None:
        return None
    return float(current_shares) - float(previous_shares)


def determine_position_status(
    current_holding_pct: float,
    previous_holding_pct: float,
    threshold: float = 1e-4
) -> str:
    """
    Classifies position movement between two reporting dates:
    - NEW: Previous was 0% and Current > 0%
    - EXITED: Previous > 0% and Current is 0%
    - INCREASED: Current > Previous
    - REDUCED: Current < Previous
    - UNCHANGED: Current == Previous
    """
    curr = float(current_holding_pct)
    prev = float(previous_holding_pct)

    if prev <= threshold and curr > threshold:
        return "NEW"
    elif prev > threshold and curr <= threshold:
        return "EXITED"
    elif curr > prev + threshold:
        return "INCREASED"
    elif curr < prev - threshold:
        return "REDUCED"
    else:
        return "UNCHANGED"


def format_holding_change(current_pct: float, previous_pct: float) -> Tuple[str, str]:
    """
    Returns formatted display strings for UI:
    (Percentage Points String, Relative Percentage String)
    Example: ('+1.00 percentage points', '+20.00%')
    """
    chg_pp = calculate_holding_change(current_pct, previous_pct)
    rel_pct = calculate_relative_change(current_pct, previous_pct)

    sign_pp = "+" if chg_pp > 0 else ""
    sign_rel = "+" if rel_pct > 0 else ""

    str_pp = f"{sign_pp}{chg_pp:.2f} percentage points"
    str_rel = f"{sign_rel}{rel_pct:.2f}%"
    return str_pp, str_rel
