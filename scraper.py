"""
Chartink Screener Scraper Module.
Fetches real-time scanner results from Chartink.com with CSRF token management,
retry handling, and a library of curated technical presets.
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
import time
import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup as bs

CHARTINK_BASE_URL = "https://chartink.com/screener/consolidatedbo"
CHARTINK_PROCESS_URL = "https://chartink.com/screener/process"

# Preset Scanner Clauses
PRESET_SCANNERS: Dict[str, Dict[str, str]] = {
    "Short Term Breakouts": {
        "description": "Short term breakout: 5-day max close > 1.05x 120-day max close with volume > 5 SMA volume and positive close",
        "clause": (
            "( {cash} ( daily max( 5 , daily close ) > 6 days ago max( 120 , daily close ) * 1.05 "
            "and daily volume > daily sma( volume,5 ) and daily close > 1 day ago close ) )"
        ),
        "url": "https://chartink.com/screener/short-term-breakouts"
    },
    "Consolidated Breakout (SMA Convergence)": {
        "description": "Stocks trading within +-3% of 5, 20, 50, 100, and 200 SMAs (Tight Bollinger/MA compression)",
        "clause": (
            "( {57960} ( ( {57960} ( latest sma( latest close , 5 ) "
            "< latest close * 1.03 and latest sma( latest close , 20 ) "
            "< latest close * 1.03 and latest sma( latest close , 50 ) "
            "< latest close * 1.03 and latest sma( latest close , 100 ) "
            "< latest close * 1.03 and latest sma( latest close , 200 ) "
            "< latest close * 1.03 and latest sma( latest close , 5 ) "
            "> latest close * 0.97 and latest sma( latest close , 20 ) "
            "> latest close * 0.97 and latest sma( latest close , 50 ) "
            "> latest close * 0.97 and latest sma( latest close , 100 ) "
            "> latest close * 0.97 and latest sma( latest close , 200 ) "
            "> latest close * 0.97 ) ) ) )"
        ),
    },
    "Volume Shockers (Volume > 2x 20 SMA)": {
        "description": "Stocks gaining with today's volume more than 2x the 20-day average volume",
        "clause": (
            "( {33619} ( latest volume > latest sma( latest volume , 20 ) * 2 "
            "and latest close > latest open "
            "and latest close > 50 ) )"
        ),
    },
    "20 EMA Pullback Bounce": {
        "description": "Stage-2 uptrend stocks testing the 20 EMA and bouncing back above it",
        "clause": (
            "( {33619} ( latest close > latest ema( latest close , 20 ) "
            "and latest low <= latest ema( latest close , 20 ) "
            "and latest ema( latest close , 20 ) > latest ema( latest close , 50 ) "
            "and latest close > latest open ) )"
        ),
    },
    "Bullish Engulfing Pattern": {
        "description": "Daily Bullish Engulfing: Green candle completely engulfs previous red candle body, high, and low",
        "clause": (
            "( {cash} ( 1 day ago close < 1 day ago open and daily close > daily open "
            "and daily open < 1 day ago close and daily close > 1 day ago open "
            "and daily high > 1 day ago high and daily low < 1 day ago low ) )"
        ),
        "url": "https://chartink.com/screener/bullish-engulfing-pattern-1"
    },
    "About to Break (BTST / Bull Run)": {
        "description": "About to breakout: Supertrend(7,1) within ₹10 of close, daily volume > 20 SMA, and 3 consecutive 5-min higher highs with volume",
        "clause": (
            "( {33489} ( latest supertrend( 7,1 ) < latest close + 10 and latest volume > latest sma( volume,20 ) "
            "and latest supertrend( 7,1 ) > latest close and [0] 5 minute close > [-1] 5 minute close "
            "and [0] 5 minute sma( volume,20 ) > [-1] 5 minute sma( volume,20 ) and [-1] 5 minute close > [-2] 5 minute close "
            "and [-1] 5 minute sma( volume,20 ) > [-2] 5 minute sma( volume,20 ) ) )"
        ),
        "url": "https://chartink.com/screener/about-to-break-1"
    },
    "Volatility Contraction Pattern (VCP)": {
        "description": "Mark Minervini VCP: Weekly trend alignment (EMA 13 > 26 > SMA 50), tight compression near 50-week highs",
        "clause": (
            "( {cash} ( weekly ema( close,13 ) > weekly ema( close,26 ) and weekly ema( close,26 ) > weekly sma( close,50 ) "
            "and weekly sma( close,40 ) > 5 weeks ago sma( close,40 ) and latest close >= weekly min( 50 , weekly low * 1.3 ) "
            "and latest close >= weekly max( 50 , weekly high * 0.75 ) and 20 days ago ema( close,13 ) > 20 weeks ago ema( close,26 ) "
            "and 5 weeks ago sma( close,40 ) > 10 weeks ago sma( close,40 ) and latest close > latest sma( close,50 ) "
            "and( weekly wma( close,8 ) - weekly sma( close,8 ) ) * 6 / 29 < 0.5 and latest close > 10 ) )"
        ),
        "url": "https://chartink.com/screener/volatility-compression"
    },
}


def chartink_scraper(
    scan_clause_str: str,
    url: str = CHARTINK_BASE_URL,
    max_retries: int = 3,
    delay: float = 3.0
) -> Tuple[pd.DataFrame, Optional[str]]:
    """
    Retrieves the results of a Chartink scanner query.
    
    Args:
        scan_clause_str: The Chartink scan clause string.
        url: The Chartink webpage URL used to fetch the initial CSRF token.
        max_retries: Number of retries on network or extraction errors.
        delay: Delay in seconds between retries.
        
    Returns:
        (DataFrame with results, error_message or None)
    """
    payload = {"scan_clause": scan_clause_str}
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            with requests.Session() as session:
                # Add browser headers to avoid blocking
                session.headers.update({
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Referer": url,
                })

                # Step 1: Fetch CSRF Token
                response = session.get(url, timeout=15)
                response.raise_for_status()
                soup = bs(response.text, "html.parser")
                token_tag = soup.select_one("[name='csrf-token']")
                if not token_tag or not token_tag.get("content"):
                    raise ValueError("Could not extract CSRF token from Chartink page.")

                csrf = token_tag["content"]

                # Step 2: POST to Screener Process endpoint
                session.headers["x-csrf-token"] = csrf
                session.headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                session.headers["X-Requested-With"] = "XMLHttpRequest"

                post_resp = session.post(CHARTINK_PROCESS_URL, data=payload, timeout=20)
                post_resp.raise_for_status()

                data_json = post_resp.json()
                if "data" in data_json:
                    df = pd.DataFrame.from_dict(data_json["data"])
                    if not df.empty:
                        # Normalize numeric columns
                        for col in ["per_chg", "close", "volume"]:
                            if col in df.columns:
                                df[col] = pd.to_numeric(df[col], errors="coerce")
                        return df, None
                    else:
                        # Empty results is valid (scanner found 0 stocks matching)
                        return pd.DataFrame(), None
                else:
                    raise ValueError("Chartink returned unexpected JSON format without 'data' field.")

        except requests.exceptions.RequestException as exc:
            last_error = f"Network/HTTP error on attempt {attempt}: {exc}"
        except Exception as exc:
            last_error = f"Extraction error on attempt {attempt}: {exc}"

        if attempt < max_retries:
            time.sleep(delay)

    return pd.DataFrame(), last_error


def extract_clause_from_url(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Fetches a Chartink screener URL and parses the scan_clause directly from :scan-json="...".
    
    Returns:
        (scan_clause, screener_name, error_message)
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = bs(resp.text, "html.parser")
        scanner_tag = soup.find("scanner")
        if scanner_tag and scanner_tag.has_attr(":scan-json"):
            data = json.loads(scanner_tag[":scan-json"])
            clause = data.get("atlas_query") or data.get("scan_clause")
            name = data.get("name", "Custom Chartink Screener")
            if clause:
                return clause, name, None
        return None, None, "Could not find scanner definition (:scan-json) in webpage HTML."
    except Exception as e:
        return None, None, str(e)


def run_confluence_scan(
    scanners: Dict[str, Dict[str, Any]],
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    delay_between: float = 0.5
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """
    Executes multiple Chartink scanners and ranks stocks based on how many
    scanners they appear in (confluence / overlap).

    Args:
        scanners: Dict mapping scanner_name -> dict with at least 'clause' (and optional 'url')
        progress_callback: Optional callback func(current_idx, total_count, scanner_name)
        delay_between: Delay in seconds between requests to avoid rate limits

    Returns:
        (aggregated_df, scanner_counts_dict)
    """
    stock_records: Dict[str, Dict[str, Any]] = {}
    scanner_counts: Dict[str, int] = {}
    total = len(scanners)

    for idx, (s_name, s_info) in enumerate(scanners.items(), start=1):
        if progress_callback:
            progress_callback(idx, total, s_name)

        clause = s_info.get("clause", "")
        url = s_info.get("url", CHARTINK_BASE_URL)

        df, err = chartink_scraper(clause, url=url, max_retries=2, delay=1.5)
        count = 0

        if not df.empty and "nsecode" in df.columns:
            count = len(df)
            for _, row in df.iterrows():
                ticker = str(row.get("nsecode", "")).strip().upper()
                if not ticker:
                    continue

                if ticker not in stock_records:
                    stock_records[ticker] = {
                        "nsecode": ticker,
                        "name": row.get("name", ticker),
                        "close": float(row.get("close", 0.0)),
                        "per_chg": float(row.get("per_chg", 0.0)),
                        "volume": int(row.get("volume", 0)),
                        "confluence_count": 1,
                        "scanners": [s_name]
                    }
                else:
                    stock_records[ticker]["confluence_count"] += 1
                    stock_records[ticker]["scanners"].append(s_name)
                    # Update with latest price/volume if available
                    if row.get("close"):
                        stock_records[ticker]["close"] = float(row.get("close", 0.0))
                    if row.get("per_chg"):
                        stock_records[ticker]["per_chg"] = float(row.get("per_chg", 0.0))
                    if row.get("volume"):
                        stock_records[ticker]["volume"] = int(row.get("volume", 0))

        scanner_counts[s_name] = count

        if idx < total and delay_between > 0:
            time.sleep(delay_between)

    if not stock_records:
        return pd.DataFrame(), scanner_counts

    res_df = pd.DataFrame(list(stock_records.values()))
    # Sort primarily by confluence count descending, secondarily by % change descending
    res_df = res_df.sort_values(by=["confluence_count", "per_chg"], ascending=[False, False]).reset_index(drop=True)
    return res_df, scanner_counts

