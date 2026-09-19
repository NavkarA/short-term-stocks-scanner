"""
Data sources abstraction package for institutional data.
"""
from institutional.data_sources.base import InstitutionalDataProvider
from institutional.data_sources.nse import NSEDataProvider
from institutional.data_sources.amfi import AMFIDataProvider
from institutional.data_sources.sebi import SEBIDataProvider
from institutional.data_sources.bse import BSEDataProvider
from institutional.data_sources.nsdl import NSDLDataProvider
from institutional.data_sources.manager import InstitutionalDataManager

__all__ = [
    "InstitutionalDataProvider",
    "NSEDataProvider",
    "AMFIDataProvider",
    "SEBIDataProvider",
    "BSEDataProvider",
    "NSDLDataProvider",
    "InstitutionalDataManager",
]
