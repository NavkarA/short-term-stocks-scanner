"""
Abstract base class interface for institutional data providers.
Allows interchangeable and testable data sources (NSE, AMFI, SEBI, BSE, NSDL).
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from institutional.models import MFHolding, InstitutionalDailyActivity, FIIHolding


class InstitutionalDataProvider(ABC):
    """Abstract interface defining required institutional data fetching protocols."""

    @abstractmethod
    def get_source_name(self) -> str:
        """Returns provider identifier name."""
        pass

    @abstractmethod
    def get_mf_daily_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        """Fetches daily mutual fund equity purchases, sales, and net activity."""
        pass

    @abstractmethod
    def get_mf_holdings(self, reporting_date: Optional[str] = None) -> List[MFHolding]:
        """Fetches mutual fund portfolio disclosures as of reporting date."""
        pass

    @abstractmethod
    def get_fii_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        """Fetches daily FII gross buy, gross sell, and net investment in ₹ Cr."""
        pass

    @abstractmethod
    def get_fii_holdings(self, stock_symbol: Optional[str] = None) -> List[FIIHolding]:
        """Fetches FII stock-level holding percentages."""
        pass

    @abstractmethod
    def get_dii_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        """Fetches daily DII gross buy, gross sell, and net activity in ₹ Cr."""
        pass
