"""
Configuration settings for the Institutional Activity module.
Supports environment variables with sensible defaults.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Database configuration
DB_PATH = os.getenv("INSTITUTIONAL_DB_PATH", str(DATA_DIR / "institutional.db"))

# Feature toggles
INSTITUTIONAL_DATA_ENABLED = os.getenv("INSTITUTIONAL_DATA_ENABLED", "true").lower() in ("true", "1", "yes")
MF_UPDATE_ENABLED = os.getenv("MF_UPDATE_ENABLED", "true").lower() in ("true", "1", "yes")
FII_UPDATE_ENABLED = os.getenv("FII_UPDATE_ENABLED", "true").lower() in ("true", "1", "yes")
DII_UPDATE_ENABLED = os.getenv("DII_UPDATE_ENABLED", "true").lower() in ("true", "1", "yes")

# Cache & Rate Limiting
INSTITUTIONAL_CACHE_TTL = int(os.getenv("INSTITUTIONAL_CACHE_TTL", "86400"))  # 24 hours
REQUEST_TIMEOUT_SECONDS = int(os.getenv("INSTITUTIONAL_REQUEST_TIMEOUT", "20"))
MAX_RETRIES = int(os.getenv("INSTITUTIONAL_MAX_RETRIES", "3"))
RETRY_BACKOFF_FACTOR = float(os.getenv("INSTITUTIONAL_BACKOFF_FACTOR", "2.0"))

# Default scoring weights (user-configurable in UI)
DEFAULT_SCORING_WEIGHTS = {
    "holding_increase": 2.0,
    "new_entry": 3.0,
    "holding_decrease": -2.0,
    "exit": -3.0,
    "multiple_funds_increasing": 1.0,
    "multiple_funds_decreasing": -1.0,
    "significant_increase": 2.0,
    "significant_decrease": -2.0,
    "significant_threshold_pct": 1.0,  # 1.0 percentage point change is significant
}
