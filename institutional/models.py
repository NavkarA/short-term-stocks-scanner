"""
Domain data models for Institutional Activity module.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict, Any


@dataclass
class MFHolding:
    fund_id: str
    fund_name: str
    amc_name: str
    stock_symbol: str
    isin: str
    reporting_date: str  # YYYY-MM-DD
    shares: Optional[float] = None
    holding_percent: Optional[float] = None       # % of company held
    portfolio_weight: Optional[float] = None      # % of fund's portfolio
    market_value: Optional[float] = None          # in ₹ Cr
    source: str = "AMFI"
    source_url: str = ""
    retrieved_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class InstitutionalDailyActivity:
    activity_date: str                           # YYYY-MM-DD
    institution_type: str                        # 'FII', 'DII', 'MF'
    gross_buy: float                             # in ₹ Cr
    gross_sell: float                            # in ₹ Cr
    net_activity: float                          # in ₹ Cr (gross_buy - gross_sell)
    source: str = "NSE"
    source_url: str = ""
    retrieved_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FIIHolding:
    stock_symbol: str
    isin: str
    reporting_date: str                          # YYYY-MM-DD
    holding_percent: float                       # % of company held
    source: str = "NSE/BSE"
    source_url: str = ""
    retrieved_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class FundHoldingDiff:
    fund_id: str
    fund_name: str
    amc_name: str
    stock_symbol: str
    isin: str
    current_shares: Optional[float]
    previous_shares: Optional[float]
    change_in_shares: Optional[float]
    current_holding_percent: float
    previous_holding_percent: float
    change_holding_pct_points: float
    relative_change_pct: float
    portfolio_weight: Optional[float]
    market_value: Optional[float]
    status: str                                  # 'NEW', 'INCREASED', 'UNCHANGED', 'REDUCED', 'EXITED'
    previous_reporting_date: str
    current_reporting_date: str
    source: str
    source_url: str


@dataclass
class StockMFSummary:
    stock_symbol: str
    isin: str
    company_name: str
    sector: str
    current_mf_holding_pct: float
    previous_mf_holding_pct: float
    change_pct_points: float
    relative_change_pct: float
    total_funds_count: int
    funds_increased: int
    funds_reduced: int
    new_funds: int
    exited_funds: int
    estimated_holding_value_cr: Optional[float]
    accumulation_score: float
    consensus_score: float
    latest_reporting_date: str
    previous_reporting_date: str


@dataclass
class InstitutionalConsensusSummary:
    stock_symbol: str
    company_name: str
    sector: str
    mf_trend: str                                # 'ACCUMULATING', 'NEUTRAL', 'DISTRIBUTING'
    fii_trend: str                               # 'INCREASING', 'NEUTRAL', 'DECREASING'
    dii_trend: str                               # 'ACCUMULATING', 'NEUTRAL', 'DISTRIBUTING'
    mf_holding_change: float
    fii_holding_change: float
    num_mf_buyers: int
    num_mf_sellers: int
    institutional_score: float
    overall_trend: str                           # 'STRONG ACCUMULATION', 'ACCUMULATION', 'NEUTRAL', 'DISTRIBUTION'
    latest_reporting_date: str


@dataclass
class AccumulationScoreConfig:
    holding_increase: float = 2.0
    new_entry: float = 3.0
    holding_decrease: float = -2.0
    exit: float = -3.0
    multiple_funds_increasing: float = 1.0
    multiple_funds_decreasing: float = -1.0
    significant_increase: float = 2.0
    significant_decrease: float = -2.0
    significant_threshold_pct: float = 1.0
