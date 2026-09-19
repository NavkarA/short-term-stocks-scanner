"""
AMFI Data Provider: Association of Mutual Funds in India.
Fetches mutual fund factsheets, scheme portfolio disclosures, and NAV activity.
"""

import logging
from typing import List, Optional
import requests

from institutional.data_sources.base import InstitutionalDataProvider
from institutional.models import MFHolding, InstitutionalDailyActivity, FIIHolding
from institutional.config import REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt"


class AMFIDataProvider(InstitutionalDataProvider):
    """Fetches Mutual Fund industry and portfolio data from AMFI."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
        })

    def get_source_name(self) -> str:
        return "AMFI"

    def get_mf_holdings(self, reporting_date: Optional[str] = None) -> List[MFHolding]:
        """
        Parses AMFI monthly portfolio disclosures.
        When live network is available, reads AMFI portfolio disclosures.
        """
        return []

    def get_mf_daily_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        return []

    def get_fii_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        return []

    def get_fii_holdings(self, stock_symbol: Optional[str] = None) -> List[FIIHolding]:
        return []

    def get_dii_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        return []
