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
    sl_pct: float = 2.0,
    max_holding_days: int = 2,
    num_days: int = 7,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any], pd.DataFrame]:
    """
    Backtests a 1-2 day swing strategy using historical scanner signals.
    Buys at Day T+1 Open, evaluates Target 1, Target 2, Stop Loss, or Close Exit.

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
        progress_callback(0.2, f"Fetching historical market data for {len(all_symbols)} candidate stocks...")

    yf_tickers = [s + ".NS" for s in all_symbols]
    try:
        hist_data = yf.download(yf_tickers, period="2mo", progress=False)
    except Exception:
        hist_data = pd.DataFrame()

    if hist_data.empty:
        return pd.DataFrame(), {}, pd.DataFrame()

    if progress_callback:
        progress_callback(0.6, "Simulating trades and evaluating Target & Stop Loss hits...")

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

                dates_after = s_df.index[s_df.index > sig_ts]
                if len(dates_after) == 0:
                    trade_rows.append({
                        "Signal Date": sig_date,
                        "Symbol": sym,
                        "Market Cap": mcap,
                        "Sector": sector,
                        "Entry Date": "Pending Next Session",
                        "Entry Price": 0.0,
                        "Target 1 Price": 0.0,
                        "Target 2 Price": 0.0,
                        "Stop Loss Price": 0.0,
                        "Day 1 High": 0.0,
                        "Day 1 Low": 0.0,
                        "Day 1 Close": 0.0,
                        "Day 1 Max Gain %": 0.0,
                        "Day 2 High": 0.0,
                        "Day 2 Max Gain %": 0.0,
                        "Holding Days": 0,
                        "Outcome": "⏳ Pending Entry",
                        "Realized Return %": 0.0,
                        "Status": "Pending"
                    })
                    continue

                # Day 1
                d1_dt = dates_after[0]
                d1_row = s_df.loc[d1_dt]
                entry = float(d1_row["Open"])
                d1_high = float(d1_row["High"])
                d1_low = float(d1_row["Low"])
                d1_close = float(d1_row["Close"])

                if entry <= 0:
                    continue

                t1_price = entry * (1.0 + target_1_pct / 100.0)
                t2_price = entry * (1.0 + target_2_pct / 100.0)
                sl_price = entry * (1.0 - sl_pct / 100.0)

                d1_max_gain = ((d1_high - entry) / entry) * 100.0
                d1_max_loss = ((d1_low - entry) / entry) * 100.0
                d1_close_ret = ((d1_close - entry) / entry) * 100.0

                d2_high = 0.0
                d2_low = 0.0
                d2_close = 0.0
                d2_max_gain = 0.0

                outcome = ""
                realized_ret = 0.0
                hold_days = 1

                # Evaluation logic
                if max_holding_days == 1 or len(dates_after) == 1:
                    # 1-Day holding
                    if d1_low <= sl_price:
                        outcome = "🛑 Stop Loss Hit (Day 1)"
                        realized_ret = -sl_pct
                    elif d1_high >= t2_price:
                        outcome = "🚀 Target 2 Hit (Day 1)"
                        realized_ret = target_2_pct
                    elif d1_high >= t1_price:
                        outcome = "🎯 Target 1 Hit (Day 1)"
                        realized_ret = target_1_pct
                    else:
                        outcome = "⏱️ Exited at Day 1 Close"
                        realized_ret = d1_close_ret
                    hold_days = 1
                else:
                    # 2-Day holding
                    # First check if Day 1 immediately reached Target 2 or SL
                    if d1_low <= sl_price:
                        outcome = "🛑 Stop Loss Hit (Day 1)"
                        realized_ret = -sl_pct
                        hold_days = 1
                    elif d1_high >= t2_price:
                        outcome = "🚀 Target 2 Hit (Day 1)"
                        realized_ret = target_2_pct
                        hold_days = 1
                    else:
                        # Carry into Day 2
                        d2_dt = dates_after[1]
                        d2_row = s_df.loc[d2_dt]
                        d2_high = float(d2_row["High"])
                        d2_low = float(d2_row["Low"])
                        d2_close = float(d2_row["Close"])
                        d2_max_gain = ((d2_high - entry) / entry) * 100.0
                        d2_close_ret = ((d2_close - entry) / entry) * 100.0
                        hold_days = 2

                        if d2_low <= sl_price:
                            outcome = "🛑 Stop Loss Hit (Day 2)"
                            realized_ret = -sl_pct
                        elif d2_high >= t2_price:
                            outcome = "🚀 Target 2 Hit (Day 2)"
                            realized_ret = target_2_pct
                        elif d1_high >= t1_price or d2_high >= t1_price:
                            outcome = "🎯 Target 1 Hit (Day 2)"
                            realized_ret = target_1_pct
                        else:
                            outcome = "⏱️ Exited at Day 2 Close"
                            realized_ret = d2_close_ret

                trade_rows.append({
                    "Signal Date": sig_date,
                    "Symbol": sym,
                    "Market Cap": mcap,
                    "Sector": sector,
                    "Entry Date": d1_dt.strftime("%Y-%m-%d"),
                    "Entry Price": round(entry, 2),
                    "Target 1 Price": round(t1_price, 2),
                    "Target 2 Price": round(t2_price, 2),
                    "Stop Loss Price": round(sl_price, 2),
                    "Day 1 High": round(d1_high, 2),
                    "Day 1 Low": round(d1_low, 2),
                    "Day 1 Close": round(d1_close, 2),
                    "Day 1 Max Gain %": round(d1_max_gain, 2),
                    "Day 2 High": round(d2_high, 2) if hold_days == 2 else None,
                    "Day 2 Max Gain %": round(d2_max_gain, 2) if hold_days == 2 else None,
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
        t1_hits = len(completed[completed["Outcome"].str.contains("Target 1")])
        t2_hits = len(completed[completed["Outcome"].str.contains("Target 2")])
        sl_hits = len(completed[completed["Outcome"].str.contains("Stop Loss")])
        close_exits = len(completed[completed["Outcome"].str.contains("Exited at")])

        # Win is hitting Target 1, Target 2, or positive return on close exit
        wins = len(completed[completed["Realized Return %"] > 0])
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
            "losses": tot_completed - wins,
            "win_rate_pct": round(win_rate, 1),
            "t1_hit_count": t1_hits,
            "t1_hit_rate_pct": round((t1_hits / tot_completed) * 100.0, 1),
            "t2_hit_count": t2_hits,
            "t2_hit_rate_pct": round((t2_hits / tot_completed) * 100.0, 1),
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
            c_t1 = len(grp[grp["Outcome"].str.contains("Target 1")])
            c_t2 = len(grp[grp["Outcome"].str.contains("Target 2")])
            c_sl = len(grp[grp["Outcome"].str.contains("Stop Loss")])
            c_win = len(grp[grp["Realized Return %"] > 0])
            c_wr = (c_win / c_tot) * 100.0 if c_tot > 0 else 0.0
            c_avg_ret = grp["Realized Return %"].mean()

            date_summary_list.append({
                "Signal Date": s_date,
                "Signals Count": c_tot,
                "Target 1 Hits": c_t1,
                "Target 2 Hits": c_t2,
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


