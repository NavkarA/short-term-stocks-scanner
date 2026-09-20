"""
Chartink Screener Scraper Module.
Fetches real-time scanner results from Chartink.com with CSRF token management,
retry handling, and a library of curated technical presets.
"""

from typing import Dict, List, Optional, Tuple, Any, Callable
import time
import json
import re
from datetime import datetime
import requests
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup as bs

from fundamentals import get_stock_fundamentals, compute_volume_growth_from_series

CHARTINK_BASE_URL = "https://chartink.com/screener/consolidatedbo"
CHARTINK_PROCESS_URL = "https://chartink.com/screener/process"
CHARTINK_BACKTEST_URL = "https://chartink.com/backtest/process"

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


def chartink_historical_signals(
    scan_clause_str: str,
    url: str = CHARTINK_BASE_URL,
    max_rows: int = 160,
    max_retries: int = 3,
    delay: float = 2.0
) -> Tuple[Dict[str, List[Dict[str, str]]], Optional[str]]:
    """
    Fetches historical scan signals by date from Chartink's /backtest/process endpoint.
    
    Returns:
        (dict of {date_str: [{'symbol': sym, 'marketcap': mc, 'sector': sec}, ...]}, error_message or None)
    """
    payload = {"scan_clause": scan_clause_str, "max_rows": max_rows}
    last_error = None
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    for attempt in range(1, max_retries + 1):
        try:
            with requests.Session() as session:
                session.headers.update(headers)
                get_resp = session.get(url, timeout=15)
                get_resp.raise_for_status()

                soup = bs(get_resp.text, "html.parser")
                token_tag = soup.find("meta", {"name": "csrf-token"})
                if not token_tag or not token_tag.get("content"):
                    token_tag = soup.select_one("[name='csrf-token']")
                if not token_tag or not token_tag.get("content"):
                    raise ValueError("CSRF token meta tag not found.")

                csrf = token_tag["content"]
                session.headers["x-csrf-token"] = csrf
                session.headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                session.headers["X-Requested-With"] = "XMLHttpRequest"

                post_resp = session.post(CHARTINK_BACKTEST_URL, data=payload, timeout=30)
                post_resp.raise_for_status()
                data = post_resp.json()

                if "metaData" in data and "aggregatedStockList" in data:
                    times = data["metaData"][0].get("tradeTimes", [])
                    stock_lists = data.get("aggregatedStockList", [])
                    results: Dict[str, List[Dict[str, str]]] = {}
                    for idx in range(len(times)):
                        dt_str = datetime.fromtimestamp(times[idx] / 1000).strftime("%Y-%m-%d")
                        items = stock_lists[idx] if idx < len(stock_lists) else []
                        stocks = []
                        for k in range(0, len(items), 3):
                            stocks.append({
                                "symbol": str(items[k]).strip().upper(),
                                "marketcap": str(items[k + 1]) if k + 1 < len(items) else "",
                                "sector": str(items[k + 2]) if k + 2 < len(items) else ""
                            })
                        results[dt_str] = stocks
                    return results, None
                else:
                    raise ValueError("Chartink backtest response missing expected fields.")
        except Exception as exc:
            last_error = f"Backtest retrieval error on attempt {attempt}: {exc}"
            if attempt < max_retries:
                time.sleep(delay)

    return {}, last_error


def run_swing_backtest(
    signals_by_date: Dict[str, List[Dict[str, str]]],
    target_1_pct: float = 3.5,
    target_2_pct: float = 6.0,
    target_3_pct: float = 10.0,
    sl_pct: float = 2.0,
    max_holding_days: int = 3,
    num_days: int = 7,
    enable_trailing_sl: bool = False,
    trailing_sl_pct: float = 2.0,
    trail_trigger: str = "After Target 1",
    t1_book_pct: float = 50.0,
    t2_book_pct: float = 30.0,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any], pd.DataFrame]:
    """
    Backtests a swing strategy using historical scanner signals.
    Buys at Day T+1 Open, evaluates Target 1, Target 2, Target 3, Stop Loss,
    Trailing Stop Loss, or Close Exit across 1 to 10 holding days.
    Supports partial quantity booking on Target 1 and Target 2, and records
    Nifty 50 Open/Close for each trade session.

    Returns:
        (trades_df, summary_metrics, date_summary_df)
    """
    if not signals_by_date:
        return pd.DataFrame(), {}, pd.DataFrame()

    sorted_dates = sorted(list(signals_by_date.keys()))
    eval_dates = sorted_dates[-num_days:]

    all_symbols: set = set()
    for d in eval_dates:
        for item in signals_by_date[d]:
            sym = item.get("symbol", "").strip().upper()
            if sym:
                all_symbols.add(sym)

    if not all_symbols:
        return pd.DataFrame(), {}, pd.DataFrame()

    if progress_callback:
        progress_callback(0.2, f"Fetching historical market data for {len(all_symbols)} candidate stocks & Nifty 50...")

    yf_tickers = [s + ".NS" for s in all_symbols] + ["^NSEI"]
    try:
        hist_data = yf.download(yf_tickers, period="3mo", progress=False)
    except Exception:
        hist_data = pd.DataFrame()

    if hist_data.empty:
        return pd.DataFrame(), {}, pd.DataFrame()

    # Extract Nifty 50 historical daily bars
    nifty_map: Dict[str, Dict[str, float]] = {}
    if isinstance(hist_data.columns, pd.MultiIndex) and "^NSEI" in hist_data["Close"].columns:
        n_open_s = hist_data["Open"]["^NSEI"].dropna()
        n_close_s = hist_data["Close"]["^NSEI"].dropna()
        for n_dt, o_val in n_open_s.items():
            dt_str = n_dt.strftime("%Y-%m-%d")
            c_val = n_close_s.get(n_dt, o_val)
            chg = ((c_val - o_val) / o_val * 100.0) if o_val > 0 else 0.0
            nifty_map[dt_str] = {
                "open": round(float(o_val), 2),
                "close": round(float(c_val), 2),
                "chg_pct": round(float(chg), 2)
            }

    if not nifty_map:
        try:
            n_raw = yf.download("^NSEI", period="3mo", progress=False)
            if not n_raw.empty:
                for n_dt, n_row in n_raw.iterrows():
                    dt_str = n_dt.strftime("%Y-%m-%d")
                    o_val = float(n_row["Open"])
                    c_val = float(n_row["Close"])
                    chg = ((c_val - o_val) / o_val * 100.0) if o_val > 0 else 0.0
                    nifty_map[dt_str] = {
                        "open": round(o_val, 2),
                        "close": round(c_val, 2),
                        "chg_pct": round(chg, 2)
                    }
        except Exception:
            pass

    return simulate_swing_trades(
        hist_data=hist_data,
        nifty_map=nifty_map,
        eval_dates=eval_dates,
        signals_by_date=signals_by_date,
        target_1_pct=target_1_pct,
        target_2_pct=target_2_pct,
        target_3_pct=target_3_pct,
        sl_pct=sl_pct,
        max_holding_days=max_holding_days,
        enable_trailing_sl=enable_trailing_sl,
        trailing_sl_pct=trailing_sl_pct,
        trail_trigger=trail_trigger,
        t1_book_pct=t1_book_pct,
        t2_book_pct=t2_book_pct,
        progress_callback=progress_callback
    )


def simulate_swing_trades(
    hist_data: pd.DataFrame,
    nifty_map: Dict[str, Dict[str, float]],
    eval_dates: List[str],
    signals_by_date: Dict[str, List[Dict[str, str]]],
    target_1_pct: float = 3.5,
    target_2_pct: float = 6.0,
    target_3_pct: float = 10.0,
    sl_pct: float = 2.0,
    max_holding_days: int = 3,
    enable_trailing_sl: bool = False,
    trailing_sl_pct: float = 2.0,
    trail_trigger: str = "After Target 1",
    t1_book_pct: float = 50.0,
    t2_book_pct: float = 30.0,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any], pd.DataFrame]:
    """
    Executes in-memory swing trading simulation given historical OHLCV data and signals.
    Highly optimized for grid backtesting and real-time dashboard execution.
    """
    if hist_data.empty or not eval_dates or not signals_by_date:
        return pd.DataFrame(), {}, pd.DataFrame()

    if progress_callback:
        progress_callback(0.6, "Simulating trades and evaluating Target & Stop Loss hits...")

    # Multi-tier partial quantity weights
    w1 = min(max(float(t1_book_pct) / 100.0, 0.0), 1.0)
    w2 = min(max(float(t2_book_pct) / 100.0, 0.0), 1.0 - w1)
    w3 = max(1.0 - w1 - w2, 0.0)

    trade_rows: List[Dict[str, Any]] = []

    for d_idx, sig_date in enumerate(eval_dates, start=1):
        stock_list = signals_by_date[sig_date]
        sig_ts = pd.Timestamp(sig_date)

        for stock_info in stock_list:
            sym = stock_info["symbol"]
            ticker_ns = sym + ".NS"
            mcap = stock_info.get("marketcap", "")
            sector = stock_info.get("sector", "")

            try:
                # Extract ticker dataframe
                if isinstance(hist_data.columns, pd.MultiIndex):
                    if ticker_ns in hist_data["Close"].columns:
                        s_df = pd.DataFrame({
                            "Open": hist_data["Open"][ticker_ns],
                            "High": hist_data["High"][ticker_ns],
                            "Low": hist_data["Low"][ticker_ns],
                            "Close": hist_data["Close"][ticker_ns],
                            "Volume": hist_data["Volume"][ticker_ns]
                        }).dropna()
                    else:
                        continue
                else:
                    s_df = hist_data.dropna()

                if s_df.empty:
                    continue

                f_info = get_stock_fundamentals(sym)
                vol_series_sig = s_df.loc[s_df.index <= sig_ts, "Volume"] if "Volume" in s_df.columns else pd.Series(dtype=float)
                vol_1w, vol_1m = compute_volume_growth_from_series(vol_series_sig)

                dates_after = s_df.index[s_df.index > sig_ts]
                if len(dates_after) == 0:
                    prior_dates = s_df.index[s_df.index <= sig_ts]
                    p_ret = 0.0
                    if len(prior_dates) >= 2:
                        p_close = float(s_df.loc[prior_dates[-2], "Close"])
                        s_close = float(s_df.loc[prior_dates[-1], "Close"])
                        if p_close > 0:
                            p_ret = round(((s_close - p_close) / p_close) * 100.0, 2)
                    elif len(prior_dates) == 1:
                        s_open = float(s_df.loc[prior_dates[-1], "Open"])
                        s_close = float(s_df.loc[prior_dates[-1], "Close"])
                        if s_open > 0:
                            p_ret = round(((s_close - s_open) / s_open) * 100.0, 2)

                    trade_rows.append({
                        "Signal Date": sig_date,
                        "Entry Date": "Pending Next Session",
                        "Symbol": sym,
                        "Market Cap": mcap,
                        "Market Cap (₹ Cr)": f_info.get("market_cap_cr", 0.0),
                        "Sector": sector or f_info.get("sector", "Other"),
                        "Industry": f_info.get("industry", "Other"),
                        "P/E Ratio": f_info.get("pe_ratio", 0.0),
                        "Industry P/E": f_info.get("industry_pe", 22.0),
                        "YoY Rev Growth %": f_info.get("yoy_revenue_growth_pct", 0.0),
                        "YoY Profit Growth %": f_info.get("yoy_profit_growth_pct", 0.0),
                        "Volume Growth 1W %": vol_1w,
                        "Volume Growth 1M %": vol_1m,
                        "ROE %": f_info.get("roe_pct", 0.0),
                        "Debt to Equity": f_info.get("debt_to_equity", 0.0),
                        "Operating Margin %": f_info.get("operating_margin_pct", 0.0),
                        "Prev Day Return %": p_ret,
                        "Nifty Open": 0.0,
                        "Nifty Close": 0.0,
                        "Nifty Chg %": 0.0,
                        "Entry Price": 0.0,
                        "Target 1 Price": 0.0,
                        "Target 2 Price": 0.0,
                        "Target 3 Price": 0.0,
                        "Initial SL Price": 0.0,
                        "Final SL Price": 0.0,
                        "Peak High": 0.0,
                        "Peak Gain %": 0.0,
                        "Exit Price": 0.0,
                        "Holding Days": 0,
                        "Outcome": "⏳ Pending Entry",
                        "Realized Return %": 0.0,
                        "Status": "Pending"
                    })
                    continue

                d1_dt = dates_after[0]
                entry_date_str = d1_dt.strftime("%Y-%m-%d")
                d1_row = s_df.loc[d1_dt]
                entry = float(d1_row["Open"])

                if entry <= 0:
                    continue

                # Stock's previous day return (breakout day / signal day return relative to prior close)
                prior_dates = s_df.index[s_df.index < d1_dt]
                prev_day_return_pct = 0.0
                if len(prior_dates) >= 2:
                    p_close = float(s_df.loc[prior_dates[-2], "Close"])
                    s_close = float(s_df.loc[prior_dates[-1], "Close"])
                    if p_close > 0:
                        prev_day_return_pct = round(((s_close - p_close) / p_close) * 100.0, 2)
                elif len(prior_dates) == 1:
                    s_open = float(s_df.loc[prior_dates[-1], "Open"])
                    s_close = float(s_df.loc[prior_dates[-1], "Close"])
                    if s_open > 0:
                        prev_day_return_pct = round(((s_close - s_open) / s_open) * 100.0, 2)

                t1_price = entry * (1.0 + target_1_pct / 100.0)
                t2_price = entry * (1.0 + target_2_pct / 100.0)
                t3_price = entry * (1.0 + target_3_pct / 100.0)
                initial_sl_price = entry * (1.0 - sl_pct / 100.0)
                current_sl = initial_sl_price

                peak_high = entry
                t1_hit = False
                t2_hit = False
                t3_hit = False
                outcome = ""
                realized_ret = 0.0
                exit_price = 0.0
                hold_days = 0

                booked_return = 0.0
                active_weight = 1.0

                days_to_simulate = min(max_holding_days, len(dates_after))
                final_close = entry

                for day_idx in range(days_to_simulate):
                    cur_dt = dates_after[day_idx]
                    cur_row = s_df.loc[cur_dt]
                    cur_day = day_idx + 1

                    d_high = float(cur_row["High"])
                    d_low = float(cur_row["Low"])
                    d_close = float(cur_row["Close"])
                    final_close = d_close

                    if d_high > peak_high:
                        peak_high = d_high

                    # Check Target 1 hit
                    if not t1_hit and d_high >= t1_price:
                        t1_hit = True
                        if w1 > 0:
                            booked_return += w1 * target_1_pct
                            active_weight = max(0.0, active_weight - w1)
                        if enable_trailing_sl and trail_trigger == "After Target 1":
                            current_sl = max(current_sl, entry)  # Move SL to Breakeven

                    # Check Target 2 hit
                    if t1_hit and not t2_hit and d_high >= t2_price:
                        t2_hit = True
                        if w2 > 0 and active_weight > 0:
                            booked_return += w2 * target_2_pct
                            active_weight = max(0.0, active_weight - w2)
                        if enable_trailing_sl:
                            current_sl = max(current_sl, t1_price)  # Ratchet SL to Target 1 price

                    # Check Target 3 hit
                    if (t2_hit or d_high >= t3_price) and not t3_hit and d_high >= t3_price:
                        t3_hit = True
                        if active_weight > 0:
                            booked_return += active_weight * target_3_pct
                            active_weight = 0.0
                        hold_days = cur_day
                        exit_price = round(t3_price, 2)
                        realized_ret = booked_return
                        outcome = f"🚀 Target 3 Hit (Day {cur_day})"
                        break

                    # Check if all position has been booked (e.g. w1 + w2 == 100% and T2 hit)
                    if active_weight <= 0:
                        hold_days = cur_day
                        realized_ret = booked_return
                        if t2_hit:
                            exit_price = round(t2_price, 2)
                            outcome = f"🚀 Target 2 Hit ({t1_book_pct:.0f}% T1 + {t2_book_pct:.0f}% T2) (Day {cur_day})"
                        elif t1_hit:
                            exit_price = round(t1_price, 2)
                            outcome = f"🎯 Target 1 Hit (Day {cur_day})"
                        break

                    # Update trailing SL if enabled
                    if enable_trailing_sl:
                        if trail_trigger == "After Target 1":
                            if t1_hit:
                                trail_candidate = peak_high * (1.0 - trailing_sl_pct / 100.0)
                                current_sl = max(current_sl, trail_candidate)
                        else:  # "From Entry"
                            trail_candidate = peak_high * (1.0 - trailing_sl_pct / 100.0)
                            current_sl = max(current_sl, trail_candidate)

                    # Check Stop Loss / Trailing Stop Loss
                    eff_sl = current_sl if enable_trailing_sl else initial_sl_price
                    if d_low <= eff_sl:
                        hold_days = cur_day
                        exit_price = round(eff_sl, 2)
                        rem_ret = ((eff_sl - entry) / entry) * 100.0
                        booked_return += active_weight * rem_ret
                        active_weight = 0.0
                        realized_ret = booked_return

                        if t2_hit:
                            outcome = f"🎯 T1 & T2 Booked + Trailing SL Hit (Day {cur_day})"
                        elif t1_hit:
                            if eff_sl >= entry:
                                outcome = f"🛡️ Trailing SL Hit (T1 Booked) (Day {cur_day})"
                            else:
                                outcome = f"🛑 SL Hit on Remainder (T1 Booked) (Day {cur_day})"
                        else:
                            outcome = f"🛑 Stop Loss Hit (Day {cur_day})"
                        break

                # If holding period expires (Day Close exit)
                if not outcome:
                    hold_days = days_to_simulate
                    exit_price = round(final_close, 2)
                    if active_weight > 0:
                        close_ret = ((final_close - entry) / entry) * 100.0
                        booked_return += active_weight * close_ret
                        active_weight = 0.0
                    realized_ret = booked_return

                    if t2_hit:
                        outcome = f"🚀 T1 & T2 Booked + Exited Day {hold_days} Close"
                    elif t1_hit:
                        outcome = f"🎯 Target 1 Booked ({t1_book_pct:.0f}%) + Exited Day {hold_days} Close"
                    else:
                        outcome = f"⏱️ Exited at Day {hold_days} Close"

                peak_gain_pct = ((peak_high - entry) / entry) * 100.0

                # Nifty metrics for Entry Day
                n_info = nifty_map.get(entry_date_str, {})
                n_open = n_info.get("open", 0.0)
                n_close = n_info.get("close", 0.0)
                n_chg = n_info.get("chg_pct", 0.0)

                trade_rows.append({
                    "Signal Date": sig_date,
                    "Entry Date": entry_date_str,
                    "Symbol": sym,
                    "Market Cap": mcap,
                    "Market Cap (₹ Cr)": f_info.get("market_cap_cr", 0.0),
                    "Sector": sector or f_info.get("sector", "Other"),
                    "Industry": f_info.get("industry", "Other"),
                    "P/E Ratio": f_info.get("pe_ratio", 0.0),
                    "Industry P/E": f_info.get("industry_pe", 22.0),
                    "YoY Rev Growth %": f_info.get("yoy_revenue_growth_pct", 0.0),
                    "YoY Profit Growth %": f_info.get("yoy_profit_growth_pct", 0.0),
                    "Volume Growth 1W %": vol_1w,
                    "Volume Growth 1M %": vol_1m,
                    "ROE %": f_info.get("roe_pct", 0.0),
                    "Debt to Equity": f_info.get("debt_to_equity", 0.0),
                    "Operating Margin %": f_info.get("operating_margin_pct", 0.0),
                    "Prev Day Return %": prev_day_return_pct,
                    "Nifty Open": n_open,
                    "Nifty Close": n_close,
                    "Nifty Chg %": n_chg,
                    "Entry Price": round(entry, 2),
                    "Target 1 Price": round(t1_price, 2),
                    "Target 2 Price": round(t2_price, 2),
                    "Target 3 Price": round(t3_price, 2),
                    "Initial SL Price": round(initial_sl_price, 2),
                    "Final SL Price": round(current_sl, 2),
                    "Peak High": round(peak_high, 2),
                    "Peak Gain %": round(peak_gain_pct, 2),
                    "Exit Price": exit_price,
                    "Holding Days": hold_days,
                    "Outcome": outcome,
                    "Realized Return %": round(realized_ret, 2),
                    "Status": "Completed"
                })

            except Exception:
                continue

    if progress_callback:
        progress_callback(0.9, "Aggregating metrics and performance statistics...")

    trades_df = pd.DataFrame(trade_rows)
    if trades_df.empty:
        return pd.DataFrame(), {}, pd.DataFrame()

    # Calculate summary metrics
    completed = trades_df[trades_df["Status"] == "Completed"]
    tot_completed = len(completed)

    if tot_completed > 0:
        t1_hits = len(completed[completed["Outcome"].str.contains("Target 1") | completed["Outcome"].str.contains("T1")])
        t2_hits = len(completed[completed["Outcome"].str.contains("Target 2") | completed["Outcome"].str.contains("T2")])
        t3_hits = len(completed[completed["Outcome"].str.contains("Target 3")])
        trail_sl_hits = len(completed[completed["Outcome"].str.contains("Trailing SL")])
        sl_hits = len(completed[completed["Outcome"].str.contains("Stop Loss")])
        close_exits = len(completed[completed["Outcome"].str.contains("Exited")])

        wins = len(completed[completed["Realized Return %"] > 0])
        losses = len(completed[completed["Realized Return %"] < 0])
        breakevens = len(completed[completed["Realized Return %"] == 0])
        win_rate = (wins / tot_completed) * 100.0

        avg_return = float(completed["Realized Return %"].mean())

        gross_profit = float(completed[completed["Realized Return %"] > 0]["Realized Return %"].sum())
        gross_loss = float(abs(completed[completed["Realized Return %"] < 0]["Realized Return %"].sum()))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        best_row = completed.loc[completed["Realized Return %"].idxmax()]
        worst_row = completed.loc[completed["Realized Return %"].idxmin()]

        summary = {
            "total_trades": len(trades_df),
            "completed_trades": tot_completed,
            "wins": wins,
            "losses": losses,
            "breakevens": breakevens,
            "win_rate_pct": round(win_rate, 1),
            "t1_hit_count": t1_hits,
            "t1_hit_rate_pct": round((t1_hits / tot_completed) * 100.0, 1),
            "t2_hit_count": t2_hits,
            "t2_hit_rate_pct": round((t2_hits / tot_completed) * 100.0, 1),
            "t3_hit_count": t3_hits,
            "t3_hit_rate_pct": round((t3_hits / tot_completed) * 100.0, 1),
            "trail_sl_hit_count": trail_sl_hits,
            "trail_sl_hit_rate_pct": round((trail_sl_hits / tot_completed) * 100.0, 1),
            "sl_hit_count": sl_hits,
            "sl_hit_rate_pct": round((sl_hits / tot_completed) * 100.0, 1),
            "close_exit_count": close_exits,
            "avg_return_pct": round(avg_return, 2),
            "profit_factor": round(profit_factor, 2),
            "best_stock": f"{best_row['Symbol']} ({best_row['Realized Return %']:+.2f}%)",
            "worst_stock": f"{worst_row['Symbol']} ({worst_row['Realized Return %']:+.2f}%)",
            "evaluated_dates_count": len(eval_dates)
        }

        # Date-by-date summary
        date_groups = completed.groupby("Signal Date")
        date_summary_list = []
        for s_date, grp in date_groups:
            c_tot = len(grp)
            c_t1 = len(grp[grp["Outcome"].str.contains("Target 1") | grp["Outcome"].str.contains("T1")])
            c_t2 = len(grp[grp["Outcome"].str.contains("Target 2") | grp["Outcome"].str.contains("T2")])
            c_t3 = len(grp[grp["Outcome"].str.contains("Target 3")])
            c_trail_sl = len(grp[grp["Outcome"].str.contains("Trailing SL")])
            c_sl = len(grp[grp["Outcome"].str.contains("Stop Loss")])
            c_win = len(grp[grp["Realized Return %"] > 0])
            c_wr = (c_win / c_tot) * 100.0 if c_tot > 0 else 0.0
            c_avg_ret = grp["Realized Return %"].mean()

            # Nifty data for this Signal Date (or Entry Date fallback)
            n_info = nifty_map.get(s_date, {})
            if not n_info and not grp.empty:
                e_date = str(grp["Entry Date"].iloc[0])
                n_info = nifty_map.get(e_date, {})

            n_open = n_info.get("open", 0.0)
            n_close = n_info.get("close", 0.0)
            n_chg = n_info.get("chg_pct", 0.0)

            date_summary_list.append({
                "Signal Date": s_date,
                "Nifty Open": n_open,
                "Nifty Close": n_close,
                "Nifty Chg %": n_chg,
                "Signals Count": c_tot,
                "Target 1 Hits": c_t1,
                "Target 2 Hits": c_t2,
                "Target 3 Hits": c_t3,
                "Trailing SL Hits": c_trail_sl,
                "Stop Loss Hits": c_sl,
                "Win Rate %": round(c_wr, 1),
                "Average Return %": round(c_avg_ret, 2)
            })

        date_summary_df = pd.DataFrame(date_summary_list).sort_values("Signal Date", ascending=False)
    else:
        summary = {
            "total_trades": len(trades_df),
            "completed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate_pct": 0.0,
            "t1_hit_count": 0,
            "t1_hit_rate_pct": 0.0,
            "t2_hit_count": 0,
            "t2_hit_rate_pct": 0.0,
            "sl_hit_count": 0,
            "sl_hit_rate_pct": 0.0,
            "close_exit_count": 0,
            "avg_return_pct": 0.0,
            "profit_factor": 0.0,
            "best_stock": "-",
            "worst_stock": "-",
            "evaluated_dates_count": len(eval_dates)
        }
        date_summary_df = pd.DataFrame()

    if progress_callback:
        progress_callback(1.0, "Backtest complete!")

    return trades_df, summary, date_summary_df


