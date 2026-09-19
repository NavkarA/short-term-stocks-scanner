"""
NSE Data Provider: Fetches official daily FII and DII trading statistics.
Implements session cookies, browser headers, retry backoff, and graceful error handling.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional
import requests

from institutional.data_sources.base import InstitutionalDataProvider
from institutional.models import InstitutionalDailyActivity, MFHolding, FIIHolding
from institutional.config import REQUEST_TIMEOUT_SECONDS, MAX_RETRIES

logger = logging.getLogger(__name__)

NSE_HOME_URL = "https://www.nseindia.com"
NSE_FIIDII_API = "https://www.nseindia.com/api/fiidiiTradeReact"


class NSEDataProvider(InstitutionalDataProvider):
    """Fetches daily FII and DII activity from National Stock Exchange of India."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": NSE_HOME_URL,
        })
        self._cookies_initialized = False

    def get_source_name(self) -> str:
        return "NSE"

    def _init_cookies(self) -> bool:
        """Bootstraps NSE session cookies required for API access."""
        try:
            resp = self.session.get(NSE_HOME_URL, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                self._cookies_initialized = True
                return True
        except Exception as e:
            logger.warning(f"Failed to bootstrap NSE session cookies: {e}")
        return False

    def get_fii_dii_daily_live(self) -> List[InstitutionalDailyActivity]:
        """
        Queries NSE fiidiiTradeReact API for today's trading numbers.
        Returns activities for FII and DII.
        """
        results: List[InstitutionalDailyActivity] = []
        if not self._cookies_initialized:
            self._init_cookies()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(NSE_FIIDII_API, timeout=REQUEST_TIMEOUT_SECONDS)
                if resp.status_code == 200:
                    data = resp.json()
                    # NSE API format: list of dicts with category, buyValue, sellValue, netValue, date
                    for item in data:
                        category = item.get("category", "").upper()
                        date_str = item.get("date", datetime.now().strftime("%Y-%m-%d"))
                        try:
                            parsed_date = datetime.strptime(date_str, "%d-%b-%Y").strftime("%Y-%m-%d")
                        except Exception:
                            parsed_date = datetime.now().strftime("%Y-%m-%d")

                        buy_val = float(item.get("buyValue", 0.0))
                        sell_val = float(item.get("sellValue", 0.0))
                        net_val = float(item.get("netValue", buy_val - sell_val))

                        inst_type = None
                        if "FII" in category or "FPI" in category:
                            inst_type = "FII"
                        elif "DII" in category:
                            inst_type = "DII"

                        if inst_type:
                            results.append(InstitutionalDailyActivity(
                                activity_date=parsed_date,
                                institution_type=inst_type,
                                gross_buy=round(buy_val, 2),
                                gross_sell=round(sell_val, 2),
                                net_activity=round(net_val, 2),
                                source="NSE",
                                source_url=NSE_FIIDII_API,
                            ))
                    if results:
                        return results
                elif resp.status_code in (401, 403):
                    # Refresh cookies
                    self._init_cookies()
            except Exception as e:
                logger.warning(f"NSE API fetch attempt {attempt} failed: {e}")

            time.sleep(1.0 * attempt)

        return results

    def get_fii_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        return [a for a in self.get_fii_dii_daily_live() if a.institution_type == "FII"]

    def get_dii_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        return [a for a in self.get_fii_dii_daily_live() if a.institution_type == "DII"]

    def get_mf_daily_activity(self, days: int = 30) -> List[InstitutionalDailyActivity]:
        # Handled primarily by SEBI / AMFI provider
        return []

    def get_mf_holdings(self, reporting_date: Optional[str] = None) -> List[MFHolding]:
        return []

    def get_fii_holdings(self, stock_symbol: Optional[str] = None) -> List[FIIHolding]:
        return []
