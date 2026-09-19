"""
NSDL Data Provider: National Securities Depository Limited.
Fetches Foreign Portfolio Investor (FPI / FII) investment trends and sector allocations.
"""

from typing import List, Optional
from institutional.data_sources.base import InstitutionalDataProvider
from institutional.models import MFHolding, InstitutionalDailyActivity, FIIHolding


class NSDLDataProvider(InstitutionalDataProvider):
    """Fetches FPI investment data from NSDL."""

    def get_source_name(self) -> str:
        return "NSDL"

    def get_mf_daily_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        return []

    def get_mf_holdings(self, reporting_date: Optional[str] = None) -> List[MFHolding]:
        return []

    def get_fii_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        return []

    def get_fii_holdings(self, stock_symbol: Optional[str] = None) -> List[FIIHolding]:
        return []

    def get_dii_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        return []
