"""
Database initialization and schema management for Institutional Activity.
"""

import sqlite3
import logging
from typing import Optional
from institutional.config import DB_PATH

logger = logging.getLogger(__name__)


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Creates and returns a SQLite connection with Row factory and foreign keys enabled.
    """
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """
    Initializes all database tables and indexes for institutional data.
    Preserves existing tables and historical data.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    try:
        # 1. Stock metadata (symbol, ISIN, sector, market cap)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_metadata (
            stock_symbol TEXT PRIMARY KEY,
            isin TEXT NOT NULL,
            company_name TEXT NOT NULL,
            sector TEXT,
            market_cap_category TEXT DEFAULT 'Mid Cap'
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_metadata_isin ON stock_metadata(isin)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_metadata_sector ON stock_metadata(sector)")

        # 2. Mutual Fund Holdings History (Section 13)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS mf_holdings_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_id TEXT NOT NULL,
            fund_name TEXT NOT NULL,
            amc_name TEXT NOT NULL,
            stock_symbol TEXT NOT NULL,
            isin TEXT NOT NULL,
            reporting_date DATE NOT NULL,
            shares REAL,
            holding_percent REAL NOT NULL CHECK(holding_percent >= 0.0 AND holding_percent <= 100.0),
            portfolio_weight REAL CHECK(portfolio_weight IS NULL OR (portfolio_weight >= 0.0 AND portfolio_weight <= 100.0)),
            market_value REAL,
            source TEXT DEFAULT 'AMFI',
            source_url TEXT,
            retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fund_id, isin, reporting_date)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mf_stock_symbol ON mf_holdings_history(stock_symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mf_fund_id ON mf_holdings_history(fund_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mf_reporting_date ON mf_holdings_history(reporting_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mf_isin ON mf_holdings_history(isin)")

        # 3. Daily Institutional Activity (FII, DII, MF) (Section 14 & 16)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS institutional_daily_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity_date DATE NOT NULL,
            institution_type TEXT NOT NULL CHECK(institution_type IN ('FII', 'DII', 'MF')),
            gross_buy REAL NOT NULL,
            gross_sell REAL NOT NULL,
            net_activity REAL NOT NULL,
            source TEXT DEFAULT 'NSE',
            source_url TEXT,
            retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(activity_date, institution_type)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_daily_date ON institutional_daily_activity(activity_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inst_daily_type ON institutional_daily_activity(institution_type)")

        # 4. FII Stock Ownership History (Section 15)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS fii_holdings_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_symbol TEXT NOT NULL,
            isin TEXT NOT NULL,
            reporting_date DATE NOT NULL,
            holding_percent REAL NOT NULL CHECK(holding_percent >= 0.0 AND holding_percent <= 100.0),
            source TEXT DEFAULT 'NSE/BSE',
            source_url TEXT,
            retrieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_symbol, reporting_date)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fii_stock_symbol ON fii_holdings_history(stock_symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fii_reporting_date ON fii_holdings_history(reporting_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fii_isin ON fii_holdings_history(isin)")

        # 5. Data Update & Freshness Log (Section 25, 44, 54)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL,
            update_type TEXT NOT NULL,
            status TEXT NOT NULL,
            records_updated INTEGER DEFAULT 0,
            error_message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_update_log_source ON data_update_log(source_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_update_log_timestamp ON data_update_log(timestamp)")

        conn.commit()
        logger.info("Institutional database initialized successfully.")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()
