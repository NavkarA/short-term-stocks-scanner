"""
BSE Data Provider: Bombay Stock Exchange.
Fetches shareholding pattern disclosures and institutional block/bulk deals.
"""

from typing import List, Optional
from institutional.data_sources.base import InstitutionalDataProvider
from institutional.models import MFHolding, InstitutionalDailyActivity, FIIHolding


class BSEDataProvider(InstitutionalDataProvider):
    """Fetches shareholding pattern and institutional deal records from BSE."""

    def get_source_name(self) -> str:
        return "BSE"

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
