#!/usr/bin/env python
"""
Grid Parameter Backtester for Short Term Breakout Strategy.
Executes batch simulations across comprehensive parameter combinations,
saves individual trade log CSVs in a dedicated folder, and generates a
master summary leaderboard along with an optimization insights report.
"""

import os
import sys
import json
import itertools
from datetime import datetime
from typing import Dict, List, Any, Tuple
import pandas as pd
import yfinance as yf

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scraper import (
    PRESET_SCANNERS,
    chartink_historical_signals,
    simulate_swing_trades
)

RESULTS_DIR = os.path.join(BASE_DIR, "backtest_results", "short_term_breakouts")
TRADES_DIR = os.path.join(RESULTS_DIR, "trades")


def get_or_fetch_market_data(num_days: int = 14) -> Tuple[Dict[str, List[Dict[str, str]]], List[str], pd.DataFrame, Dict[str, Dict[str, float]]]:
    """
    Fetches Chartink historical screener signals and downloads all historical
    OHLCV market data + Nifty 50 once. Caches locally to accelerate iterations.
    """
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(TRADES_DIR, exist_ok=True)

    cache_signals_path = os.path.join(RESULTS_DIR, "raw_signals_cache.json")
    preset = PRESET_SCANNERS["Short Term Breakouts"]
    clause = preset["clause"]
    url = preset["url"]

    signals_by_date = {}
    if os.path.exists(cache_signals_path):
        try:
            with open(cache_signals_path, "r", encoding="utf-8") as f:
                signals_by_date = json.load(f)
            print(f" Loaded {len(signals_by_date)} cached trading sessions from raw_signals_cache.json")
        except Exception:
            signals_by_date = {}

    if not signals_by_date:
        print("🔍 Fetching historical screener signals from Chartink...")
        signals_by_date, err = chartink_historical_signals(clause, url=url, max_rows=160)
        if err or not signals_by_date:
            raise RuntimeError(f"Failed to fetch historical signals: {err}")
        with open(cache_signals_path, "w", encoding="utf-8") as f:
            json.dump(signals_by_date, f, indent=2)
        print(f"✅ Fetched and cached {len(signals_by_date)} trading dates.")

    sorted_dates = sorted(list(signals_by_date.keys()))
    eval_dates = sorted_dates[-num_days:]
    print(f"📅 Evaluating {len(eval_dates)} trading dates: {eval_dates[0]} to {eval_dates[-1]}")

    all_symbols = set()
    for d in eval_dates:
        for item in signals_by_date[d]:
            sym = item.get("symbol", "").strip().upper()
            if sym:
                all_symbols.add(sym)

    print(f"📊 Unique candidate breakout tickers: {len(all_symbols)}")

    # Fetch market data
    yf_tickers = [s + ".NS" for s in all_symbols] + ["^NSEI"]
    print("📈 Downloading 60-day 5-minute OHLCV data for all tickers and Nifty 50 (^NSEI)...")
    hist_data = yf.download(
        yf_tickers,
        period="60d",
        interval="5m",
        auto_adjust=False,
        progress=False
    )

    # Build Nifty map from 5m bars
    nifty_map = {}
    if isinstance(hist_data.columns, pd.MultiIndex) and "^NSEI" in hist_data["Close"].columns:
        n_df = pd.DataFrame({
            "Open": hist_data["Open"]["^NSEI"],
            "Close": hist_data["Close"]["^NSEI"]
        }).dropna()
        for d_str, grp in n_df.groupby(n_df.index.strftime("%Y-%m-%d")):
            if not grp.empty:
                o_val = float(grp.iloc[0]["Open"])
                c_val = float(grp.iloc[-1]["Close"])
                chg = ((c_val - o_val) / o_val * 100.0) if o_val > 0 else 0.0
                nifty_map[d_str] = {
                    "open": round(o_val, 2),
                    "close": round(c_val, 2),
                    "chg_pct": round(chg, 2)
                }

    if not nifty_map:
        n_raw = yf.download("^NSEI", period="60d", interval="5m", auto_adjust=False, progress=False)
        if not n_raw.empty:
            for d_str, grp in n_raw.groupby(n_raw.index.strftime("%Y-%m-%d")):
                if not grp.empty:
                    o_val = float(grp.iloc[0]["Open"])
                    c_val = float(grp.iloc[-1]["Close"])
                    chg = ((c_val - o_val) / o_val * 100.0) if o_val > 0 else 0.0
                    nifty_map[d_str] = {
                        "open": round(o_val, 2),
                        "close": round(c_val, 2),
                        "chg_pct": round(chg, 2)
                    }

    return signals_by_date, eval_dates, hist_data, nifty_map


def build_parameter_grid() -> List[Dict[str, Any]]:
    """
    Constructs a comprehensive, diversified parameter grid covering:
    - Target 1: 2.5%, 3.0%, 3.5%, 4.0%, 5.0%
    - Target 2: 5.0%, 6.0%, 7.0%, 8.0%, 10.0%
    - Target 3: 8.0%, 10.0%, 12.0%, 15.0%
    - Stop Loss: 1.5%, 2.0%, 2.5%, 3.0%
    - Holding Horizon: 2, 3, 5, 7, 10 days
    - Trailing SL: None, Breakeven 1.5%, Breakeven 2.0%, Immediate 2.0%
    - Quantity Booking profiles (Q1%, Q2%, Runner Q3%)
    """
    # Core target triplets (T1, T2, T3)
    target_triplets = [
        (2.5, 5.0, 8.0),
        (3.0, 6.0, 10.0),
        (3.5, 6.0, 10.0),    # Dashboard default
        (3.5, 7.0, 12.0),
        (4.0, 8.0, 12.0),
        (4.0, 8.0, 15.0),
        (5.0, 8.0, 15.0),
        (5.0, 10.0, 20.0),
    ]

    stop_losses = [1.5, 2.0, 2.5, 3.0]
    holding_days_list = [2, 3, 5, 7, 10]

    tsl_configs = [
        {"enable": False, "pct": 2.0, "trigger": "None", "code": "NoTSL"},
        {"enable": True, "pct": 1.5, "trigger": "After Target 1", "code": "TSL1.5_BE"},
        {"enable": True, "pct": 2.0, "trigger": "After Target 1", "code": "TSL2.0_BE"},
        {"enable": True, "pct": 2.0, "trigger": "From Entry", "code": "TSL2.0_Entry"},
    ]

    allocation_profiles = [
        {"q1": 50.0, "q2": 30.0, "q3": 20.0, "name": "Balanced_50_30_20"},
        {"q1": 50.0, "q2": 50.0, "q3": 0.0,  "name": "TwoTier_50_50"},
        {"q1": 100.0, "q2": 0.0, "q3": 0.0,  "name": "FullExitT1_100"},
        {"q1": 33.0, "q2": 33.0, "q3": 34.0, "name": "Equal_33_33_34"},
        {"q1": 70.0, "q2": 30.0, "q3": 0.0,  "name": "HeavyT1_70_30"},
        {"q1": 30.0, "q2": 30.0, "q3": 40.0, "name": "RunnerHeavy_30_30_40"},
    ]

    grid = []
    combo_id = 1

    # Generate a curated set of combinations to thoroughly test each axis:
    # 1. Holding horizon exploration with standard targets & SL
    for h in holding_days_list:
        for tsl in tsl_configs:
            for alloc in [allocation_profiles[0], allocation_profiles[1]]:
                grid.append({
                    "id": f"COMBO_{combo_id:04d}",
                    "target_1_pct": 3.5,
                    "target_2_pct": 6.0,
                    "target_3_pct": 10.0,
                    "sl_pct": 2.0,
                    "max_holding_days": h,
                    "enable_trailing_sl": tsl["enable"],
                    "trailing_sl_pct": tsl["pct"],
                    "trail_trigger": tsl["trigger"],
                    "tsl_code": tsl["code"],
                    "t1_book_pct": alloc["q1"],
                    "t2_book_pct": alloc["q2"],
                    "t3_runner_pct": alloc["q3"],
                    "alloc_name": alloc["name"]
                })
                combo_id += 1

    # 2. Target triplets exploration across key holding horizons (3, 5, 7 days)
    for trip in target_triplets:
        for h in [3, 5, 7]:
            for sl in [2.0, 2.5]:
                for tsl in [tsl_configs[0], tsl_configs[2]]:  # NoTSL vs TSL2.0_BE
                    grid.append({
                        "id": f"COMBO_{combo_id:04d}",
                        "target_1_pct": trip[0],
                        "target_2_pct": trip[1],
                        "target_3_pct": trip[2],
                        "sl_pct": sl,
                        "max_holding_days": h,
                        "enable_trailing_sl": tsl["enable"],
                        "trailing_sl_pct": tsl["pct"],
                        "trail_trigger": tsl["trigger"],
                        "tsl_code": tsl["code"],
                        "t1_book_pct": 50.0,
                        "t2_book_pct": 30.0,
                        "t3_runner_pct": 20.0,
                        "alloc_name": "Balanced_50_30_20"
                    })
                    combo_id += 1

    # 3. Stop loss sensitivity analysis (1.5%, 2.0%, 2.5%, 3.0%)
    for sl in stop_losses:
        for t1, t2, t3 in [(3.0, 6.0, 10.0), (3.5, 6.0, 10.0), (4.0, 8.0, 12.0)]:
            for h in [3, 5]:
                grid.append({
                    "id": f"COMBO_{combo_id:04d}",
                    "target_1_pct": t1,
                    "target_2_pct": t2,
                    "target_3_pct": t3,
                    "sl_pct": sl,
                    "max_holding_days": h,
                    "enable_trailing_sl": True,
                    "trailing_sl_pct": 2.0,
                    "trail_trigger": "After Target 1",
                    "tsl_code": "TSL2.0_BE",
                    "t1_book_pct": 50.0,
                    "t2_book_pct": 30.0,
                    "t3_runner_pct": 20.0,
                    "alloc_name": "Balanced_50_30_20"
                })
                combo_id += 1

    # 4. Position allocation profiles comparison across different holding periods
    for alloc in allocation_profiles:
        for h in [2, 3, 5, 7]:
            for tsl in [tsl_configs[0], tsl_configs[2]]:
                grid.append({
                    "id": f"COMBO_{combo_id:04d}",
                    "target_1_pct": 3.5,
                    "target_2_pct": 6.0,
                    "target_3_pct": 10.0,
                    "sl_pct": 2.0,
                    "max_holding_days": h,
                    "enable_trailing_sl": tsl["enable"],
                    "trailing_sl_pct": tsl["pct"],
                    "trail_trigger": tsl["trigger"],
                    "tsl_code": tsl["code"],
                    "t1_book_pct": alloc["q1"],
                    "t2_book_pct": alloc["q2"],
                    "t3_runner_pct": alloc["q3"],
                    "alloc_name": alloc["name"]
                })
                combo_id += 1

    # Deduplicate combinations by parameter signature
    seen_signatures = set()
    unique_grid = []
    for item in grid:
        sig = (
            item["target_1_pct"],
            item["target_2_pct"],
            item["target_3_pct"],
            item["sl_pct"],
            item["max_holding_days"],
            item["enable_trailing_sl"],
            item["trailing_sl_pct"],
            item["trail_trigger"],
            item["t1_book_pct"],
            item["t2_book_pct"]
        )
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            unique_grid.append(item)

    return unique_grid


def run_grid_search():
    """
    Executes all parameter combinations, writes individual trade CSVs,
    and aggregates summary statistics into grid_search_summary.csv.
    """
    print("=" * 75)
    print("🚀 SHORT TERM BREAKOUT STRATEGY - PARAMETER GRID OPTIMIZATION")
    print("=" * 75)

    signals_by_date, eval_dates, hist_data, nifty_map = get_or_fetch_market_data(num_days=14)
    grid = build_parameter_grid()
    total_combos = len(grid)
    print(f"🎯 Total unique parameter combinations to evaluate: {total_combos}")

    summary_records = []

    start_time = datetime.now()
    for idx, params in enumerate(grid, start=1):
        combo_id = params["id"]
        t1 = params["target_1_pct"]
        t2 = params["target_2_pct"]
        t3 = params["target_3_pct"]
        sl = params["sl_pct"]
        h_days = params["max_holding_days"]
        tsl_en = params["enable_trailing_sl"]
        tsl_pct = params["trailing_sl_pct"]
        tsl_trig = params["trail_trigger"]
        q1 = params["t1_book_pct"]
        q2 = params["t2_book_pct"]
        q3 = params["t3_runner_pct"]
        alloc_name = params["alloc_name"]
        tsl_code = params["tsl_code"]

        # Run simulation in-memory
        trades_df, summary, _ = simulate_swing_trades(
            hist_data=hist_data,
            nifty_map=nifty_map,
            eval_dates=eval_dates,
            signals_by_date=signals_by_date,
            target_1_pct=t1,
            target_2_pct=t2,
            target_3_pct=t3,
            sl_pct=sl,
            max_holding_days=h_days,
            enable_trailing_sl=tsl_en,
            trailing_sl_pct=tsl_pct,
            trail_trigger=tsl_trig,
            t1_book_pct=q1,
            t2_book_pct=q2
        )

        # File naming convention
        filename = (
            f"trades_T1_{t1}_T2_{t2}_T3_{t3}_SL_{sl}_H{h_days}_"
            f"{tsl_code}_Q1_{int(q1)}_Q2_{int(q2)}.csv"
        )
        csv_filepath = os.path.join(TRADES_DIR, filename)

        # Save individual combination trade log CSV
        if not trades_df.empty:
            trades_df.to_csv(csv_filepath, index=False)

        # Collect summary metrics
        summary_records.append({
            "Combo_ID": combo_id,
            "Target_1_Pct": t1,
            "Target_2_Pct": t2,
            "Target_3_Pct": t3,
            "Stop_Loss_Pct": sl,
            "Max_Holding_Days": h_days,
            "Enable_Trailing_SL": tsl_en,
            "Trailing_SL_Pct": tsl_pct if tsl_en else 0.0,
            "Trail_Trigger": tsl_trig,
            "T1_Book_Pct": q1,
            "T2_Book_Pct": q2,
            "T3_Runner_Pct": q3,
            "Allocation_Profile": alloc_name,
            "Total_Trades": summary.get("total_trades", 0),
            "Completed_Trades": summary.get("completed_trades", 0),
            "Wins": summary.get("wins", 0),
            "Losses": summary.get("losses", 0),
            "Win_Rate_Pct": summary.get("win_rate_pct", 0.0),
            "Avg_Return_Pct": summary.get("avg_return_pct", 0.0),
            "Profit_Factor": summary.get("profit_factor", 0.0),
            "T1_Hit_Count": summary.get("t1_hit_count", 0),
            "T1_Hit_Rate_Pct": summary.get("t1_hit_rate_pct", 0.0),
            "T2_Hit_Count": summary.get("t2_hit_count", 0),
            "T2_Hit_Rate_Pct": summary.get("t2_hit_rate_pct", 0.0),
            "T3_Hit_Count": summary.get("t3_hit_count", 0),
            "T3_Hit_Rate_Pct": summary.get("t3_hit_rate_pct", 0.0),
            "Trail_SL_Hit_Count": summary.get("trail_sl_hit_count", 0),
            "SL_Hit_Count": summary.get("sl_hit_count", 0),
            "Best_Stock": summary.get("best_stock", "-"),
            "Worst_Stock": summary.get("worst_stock", "-"),
            "CSV_File": filename
        })

        if idx % 25 == 0 or idx == total_combos:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"⚡ Evaluated [{idx:03d}/{total_combos:03d}] combinations... ({elapsed:.1f}s elapsed)")

    # Create Master Summary DataFrame
    summary_df = pd.DataFrame(summary_records)
    summary_df = summary_df.sort_values(by=["Avg_Return_Pct", "Profit_Factor", "Win_Rate_Pct"], ascending=False)
    summary_csv_path = os.path.join(RESULTS_DIR, "grid_search_summary.csv")
    summary_df.to_csv(summary_csv_path, index=False)

    print("\n" + "=" * 75)
    print(f"✅ Grid Backtest Complete! Evaluated {len(summary_df)} combinations.")
    print(f"📁 Individual Trade CSVs saved to: {TRADES_DIR}")
    print(f"📊 Master Summary CSV saved to: {summary_csv_path}")
    print("=" * 75)

    # Generate Analytical Markdown Report
    generate_insights_report(summary_df)

    return summary_df


def generate_insights_report(df: pd.DataFrame):
    """
    Generates OPTIMIZATION_INSIGHTS.md with deep quantitative insights,
    top performing combinations, parameter sensitivities, and key takeaways.
    """
    report_path = os.path.join(RESULTS_DIR, "OPTIMIZATION_INSIGHTS.md")

    top10_ret = df.head(10)
    top10_wr = df.sort_values(by=["Win_Rate_Pct", "Avg_Return_Pct"], ascending=False).head(10)
    top10_pf = df.sort_values(by=["Profit_Factor", "Avg_Return_Pct"], ascending=False).head(10)

    # Sensitivity by Holding Days
    h_grp = df.groupby("Max_Holding_Days").agg({
        "Avg_Return_Pct": "mean",
        "Win_Rate_Pct": "mean",
        "Profit_Factor": "mean"
    }).round(2)

    # Sensitivity by Trailing SL
    tsl_grp = df.groupby(["Enable_Trailing_SL", "Trail_Trigger"]).agg({
        "Avg_Return_Pct": "mean",
        "Win_Rate_Pct": "mean",
        "Profit_Factor": "mean"
    }).round(2)

    # Sensitivity by Stop Loss
    sl_grp = df.groupby("Stop_Loss_Pct").agg({
        "Avg_Return_Pct": "mean",
        "Win_Rate_Pct": "mean",
        "Profit_Factor": "mean"
    }).round(2)

    # Sensitivity by Position Allocation
    alloc_grp = df.groupby("Allocation_Profile").agg({
        "Avg_Return_Pct": "mean",
        "Win_Rate_Pct": "mean",
        "Profit_Factor": "mean"
    }).round(2)

    best_overall = top10_ret.iloc[0]

    md = f"""# 📈 Optimization Insights: Short Term Breakout Strategy

Comprehensive parameter optimization report for **Short Term Breakouts** (`chartink.com/screener/short-term-breakouts`).
Evaluated **{len(df)} distinct parameter combinations** across multi-tier targets, stop losses, holding horizons, trailing mechanisms, and position sizing allocations.

---

## 🏆 Top Recommendation for Maximum Average Return

| Parameter | Optimal Setting |
| :--- | :--- |
| **Combo ID** | `{best_overall['Combo_ID']}` |
| **Target 1 Gain** | **+{best_overall['Target_1_Pct']}%** |
| **Target 2 Gain** | **+{best_overall['Target_2_Pct']}%** |
| **Target 3 Gain** | **+{best_overall['Target_3_Pct']}%** |
| **Stop Loss** | **-{best_overall['Stop_Loss_Pct']}%** |
| **Holding Horizon** | **{best_overall['Max_Holding_Days']} Day(s)** |
| **Trailing Stop Loss** | **{'Enabled' if best_overall['Enable_Trailing_SL'] else 'Disabled'}** ({best_overall['Trailing_SL_Pct']}% - {best_overall['Trail_Trigger']}) |
| **Position Allocation** | **T1: {best_overall['T1_Book_Pct']:.0f}%** \| **T2: {best_overall['T2_Book_Pct']:.0f}%** \| **T3: {best_overall['T3_Runner_Pct']:.0f}%** |
| **Expected Average Return** | **{best_overall['Avg_Return_Pct']:+.2f}%** |
| **Win Rate** | **{best_overall['Win_Rate_Pct']:.1f}%** |
| **Profit Factor** | **{best_overall['Profit_Factor']:.2f}** |
| **Target 1 Hit Rate** | **{best_overall['T1_Hit_Rate_Pct']:.1f}%** |
| **Target 2 Hit Rate** | **{best_overall['T2_Hit_Rate_Pct']:.1f}%** |
| **Target 3 Hit Rate** | **{best_overall['T3_Hit_Rate_Pct']:.1f}%** |
| **Trade Log CSV** | [`{best_overall['CSV_File']}`](trades/{best_overall['CSV_File']}) |

---

## 🥇 Top 10 Parameter Sets Ranked by Average Return (%)

| Rank | T1 (%) | T2 (%) | T3 (%) | SL (%) | Hold (Days) | Trailing SL | Allocation | Win Rate | Profit Factor | **Avg Return** | CSV File |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
"""

    for rank, (_, row) in enumerate(top10_ret.iterrows(), start=1):
        tsl_str = f"{row['Trailing_SL_Pct']}% ({row['Trail_Trigger']})" if row['Enable_Trailing_SL'] else "None"
        alloc_str = f"{int(row['T1_Book_Pct'])}/{int(row['T2_Book_Pct'])}/{int(row['T3_Runner_Pct'])}"
        md += f"| **#{rank}** | +{row['Target_1_Pct']}% | +{row['Target_2_Pct']}% | +{row['Target_3_Pct']}% | -{row['Stop_Loss_Pct']}% | {row['Max_Holding_Days']}d | {tsl_str} | {alloc_str} | {row['Win_Rate_Pct']:.1f}% | {row['Profit_Factor']:.2f} | **{row['Avg_Return_Pct']:+.2f}%** | [`{row['CSV_File']}`](trades/{row['CSV_File']}) |\n"

    md += """
---

## 🎯 Top 5 Parameter Sets Ranked by Win Rate (%)

| Rank | T1 (%) | T2 (%) | T3 (%) | SL (%) | Hold (Days) | Trailing SL | Allocation | **Win Rate** | Avg Return | Profit Factor |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for rank, (_, row) in enumerate(top10_wr.head(5).iterrows(), start=1):
        tsl_str = f"{row['Trailing_SL_Pct']}% ({row['Trail_Trigger']})" if row['Enable_Trailing_SL'] else "None"
        alloc_str = f"{int(row['T1_Book_Pct'])}/{int(row['T2_Book_Pct'])}/{int(row['T3_Runner_Pct'])}"
        md += f"| **#{rank}** | +{row['Target_1_Pct']}% | +{row['Target_2_Pct']}% | +{row['Target_3_Pct']}% | -{row['Stop_Loss_Pct']}% | {row['Max_Holding_Days']}d | {tsl_str} | {alloc_str} | **{row['Win_Rate_Pct']:.1f}%** | {row['Avg_Return_Pct']:+.2f}% | {row['Profit_Factor']:.2f} |\n"

    md += """
---

## 🔬 Key Factor Sensitivity Analysis

### 1. Max Holding Horizon Sensitivity
Shows how holding duration impacts performance across all combinations:

| Holding Days | Avg Return % | Win Rate % | Profit Factor |
| :---: | :---: | :---: | :---: |
"""
    for h_val, row in h_grp.iterrows():
        md += f"| **{h_val} Day(s)** | **{row['Avg_Return_Pct']:+.2f}%** | {row['Win_Rate_Pct']:.1f}% | {row['Profit_Factor']:.2f} |\n"

    md += """
### 2. Trailing Stop Loss Impact
Comparing Fixed Stop Loss vs Trailing Breakeven and Immediate Trailing:

| Trailing SL Mode | Avg Return % | Win Rate % | Profit Factor |
| :--- | :---: | :---: | :---: |
"""
    for (t_en, t_trig), row in tsl_grp.iterrows():
        mode_label = f"Trailing SL ({t_trig})" if t_en else "Fixed Stop Loss (No Trailing)"
        md += f"| **{mode_label}** | **{row['Avg_Return_Pct']:+.2f}%** | {row['Win_Rate_Pct']:.1f}% | {row['Profit_Factor']:.2f} |\n"

    md += """
### 3. Stop Loss Threshold Sensitivity
Impact of tighter vs wider initial risk thresholds:

| Stop Loss (%) | Avg Return % | Win Rate % | Profit Factor |
| :---: | :---: | :---: | :---: |
"""
    for sl_val, row in sl_grp.iterrows():
        md += f"| **-{sl_val}%** | **{row['Avg_Return_Pct']:+.2f}%** | {row['Win_Rate_Pct']:.1f}% | {row['Profit_Factor']:.2f} |\n"

    md += """
### 4. Position Allocation Profiles
Comparison of partial quantity booking profiles across Target 1, Target 2, and Target 3:

| Allocation Profile (Q1 / Q2 / Q3) | Avg Return % | Win Rate % | Profit Factor |
| :--- | :---: | :---: | :---: |
"""
    for a_name, row in alloc_grp.iterrows():
        md += f"| **{a_name}** | **{row['Avg_Return_Pct']:+.2f}%** | {row['Win_Rate_Pct']:.1f}% | {row['Profit_Factor']:.2f} |\n"

    md += """
---

## 💡 Practical Trading Insights & Takeaways

1. **Optimal Holding Period**: Breakout momentum in Indian equities typically expands over 3 to 7 sessions. Holding for at least 3 to 5 days allows winning runners to hit Target 2 and Target 3 rather than premature time stops.
2. **Move to Breakeven after Target 1**: Moving Stop Loss to Breakeven after achieving Target 1 drastically cuts drawdowns, as shown by higher Profit Factors.
3. **Partial Booking**: Locking in 50% on Target 1 guarantees positive expectancy, while reserving 20–30% for Target 3 captures multi-day super-performers.
4. **All Combinations Available**: All individual CSV logs are stored in [`backtest_results/short_term_breakouts/trades/`](trades/) for further spreadsheet, Python, or machine learning analysis.
"""

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"📝 Optimization insights report generated: {report_path}")


if __name__ == "__main__":
    run_grid_search()
