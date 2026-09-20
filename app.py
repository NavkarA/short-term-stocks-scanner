"""
Chartink Live Scanner Streamlit Dashboard.
Real-time NSE Stock Screener, Multi-Preset Scanners, URL Clause Extractor,
Watchlist Management, and Institutional Activity Module.
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import streamlit as st

from scraper import (
    chartink_scraper,
    PRESET_SCANNERS,
    CHARTINK_BASE_URL,
    extract_clause_from_url,
    chartink_historical_signals,
    run_swing_backtest,
)
from backtest_ui import render_backtest_dashboard
from institutional.ui.main import render_institutional_activity_page
from institutional.db.repository import InstitutionalRepository
from institutional.calculations.scoring import calculate_institutional_consensus

# Page Configuration
st.set_page_config(
    page_title="NSE Terminal | Screener & Institutional Flow",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Financial Terminal CSS
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #999999;
        margin-bottom: 1.2rem;
    }
    .metric-card {
        background: #1e222d;
        border: 1px solid #2a2e39;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .green-badge {
        background-color: rgba(38, 166, 154, 0.15);
        color: #26a69a;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .red-badge {
        background-color: rgba(239, 83, 80, 0.15);
        color: #ef5350;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# Initialize Session State
if "scan_df" not in st.session_state:
    st.session_state.scan_df = pd.DataFrame()
if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None
if "selected_scanner_name" not in st.session_state:
    st.session_state.selected_scanner_name = list(PRESET_SCANNERS.keys())[0]

if "watchlist" not in st.session_state:
    WATCHLIST_FILE = "watchlist.json"
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                st.session_state.watchlist = json.load(f)
        except Exception:
            st.session_state.watchlist = {}
    else:
        st.session_state.watchlist = {}


def save_watchlist():
    try:
        with open("watchlist.json", "w", encoding="utf-8") as f:
            json.dump(st.session_state.watchlist, f, indent=2)
    except Exception:
        pass


# Helper: Format INR Volume / Currency
def format_volume(val: float) -> str:
    if val >= 10_000_000:
        return f"{val / 10_000_000:.2f} Cr"
    elif val >= 100_000:
        return f"{val / 100_000:.2f} L"
    return f"{val:,.0f}"


# ==========================================
# MAIN NAVIGATION (Section 2)
# ==========================================
st.sidebar.title("🧭 Navigation")
nav_module = st.sidebar.radio(
    "Choose Module",
    [
        "⚡ Live Technical Screener",
        "🔬 1-2 Day Swing Backtest",
        "🏦 Institutional Activity"
    ],
    index=0,
    key="sb_main_nav"
)
st.sidebar.markdown("---")


# ==========================================
# ROUTE 1: 🏦 INSTITUTIONAL ACTIVITY
# ==========================================
if nav_module == "🏦 Institutional Activity":
    render_institutional_activity_page()

# ==========================================
# ROUTE 2: 🔬 1-2 DAY SWING BACKTEST
# ==========================================
elif nav_module == "🔬 1-2 Day Swing Backtest":
    render_backtest_dashboard()

# ==========================================
# ROUTE 3: ⚡ LIVE TECHNICAL SCREENER
# ==========================================
else:
    st.sidebar.title("⚡ Scanner Controls")

    scanner_options = list(PRESET_SCANNERS.keys()) + ["🛠️ Custom Scan Clause"]
    selected_scanner = st.sidebar.selectbox(
        "Choose Active Preset",
        scanner_options,
        index=0,
        key="sb_scanner_choice"
    )

    if selected_scanner == "🛠️ Custom Scan Clause":
        st.sidebar.info("Enter or paste your custom scan clause in the 'Custom Scanner Studio' tab.")
    else:
        desc = PRESET_SCANNERS[selected_scanner]["description"]
        st.sidebar.caption(f"ℹ️ **Logic**: {desc}")

    run_scan_btn = st.sidebar.button("🚀 Run Active Scan", use_container_width=True, key="btn_run_scan")

    # Auto Refresh Control
    st.sidebar.markdown("---")
    st.sidebar.subheader("⏱️ Live Monitoring")
    auto_refresh = st.sidebar.checkbox("Enable Auto-Refresh", value=False, key="cb_auto_ref")
    refresh_interval = st.sidebar.selectbox(
        "Refresh Interval",
        [60, 120, 300, 600],
        format_func=lambda x: f"Every {x // 60} min" if x >= 60 else f"{x} sec",
        index=1,
        key="sel_ref_interval"
    )

    # Global Table Filters
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Technical Filters")
    filter_direction = st.sidebar.radio(
        "Filter by % Change",
        ["All Stocks", "🟢 Gainers (> 0%)", "🔴 Losers (< 0%)"],
        index=0,
        key="rad_dir"
    )
    min_price = st.sidebar.number_input("Min Price (₹)", min_value=0.0, value=0.0, step=10.0, key="num_min_p")
    max_price = st.sidebar.number_input("Max Price (₹)", min_value=0.0, value=100000.0, step=500.0, key="num_max_p")
    min_vol = st.sidebar.number_input("Min Volume (Shares)", min_value=0, value=0, step=25000, key="num_min_v")
    search_query = st.sidebar.text_input("Filter Ticker / Company", "", key="txt_search").strip().upper()

    # Institutional Screener Filters (Section 18 & 19)
    st.sidebar.markdown("---")
    with st.sidebar.expander("🏦 Institutional Confirmation (Optional)", expanded=False):
        st.caption("Cross-reference technical breakouts against institutional accumulation.")
        f_mf_inc = st.checkbox("MF Holding Increased", value=False, key="cb_filt_mf_inc")
        f_fii_inc = st.checkbox("FII Holding Increased", value=False, key="cb_filt_fii_inc")
        f_dii_buy = st.checkbox("DII Buying", value=False, key="cb_filt_dii_buy")
        f_mf_cons = st.checkbox("MF Consensus Buying", value=False, key="cb_filt_mf_cons")
        f_new_entry = st.checkbox("New MF Entry", value=False, key="cb_filt_new_mf")
        f_multi_mf = st.checkbox("Multiple MF Funds Accumulating", value=False, key="cb_filt_multi_mf")
        f_inst_acc = st.checkbox("Institutional Accumulation", value=False, key="cb_filt_inst_acc")

        st.markdown("##### Filter Thresholds")
        min_mf_inc_pct = st.number_input("Minimum MF holding increase (%)", value=0.0, step=0.2, key="num_mf_inc_pct")
        min_mf_buyers = st.number_input("Minimum number of MF buyers", value=1, step=1, key="num_mf_buyers")
        min_fii_inc_pct = st.number_input("Minimum FII holding increase (%)", value=0.0, step=0.2, key="num_fii_inc_pct")
        min_mf_cons_score = st.number_input("Minimum MF consensus score", value=0.0, step=5.0, key="num_mf_cons_score")

    # ==========================================
    # SINGLE SCAN EXECUTION LOGIC
    # ==========================================
    def execute_single_scan():
        if selected_scanner != "🛠️ Custom Scan Clause":
            clause = PRESET_SCANNERS[selected_scanner]["clause"]
            url = PRESET_SCANNERS[selected_scanner].get("url", CHARTINK_BASE_URL)
        else:
            clause = st.session_state.get(
                "custom_clause_to_run",
                PRESET_SCANNERS["Short Term Breakouts"]["clause"]
            )
            url = CHARTINK_BASE_URL

        with st.spinner(f"Scraping Chartink for '{selected_scanner}'..."):
            df, err = chartink_scraper(clause, url=url)
            if err:
                st.error(f"Scraper Notice: {err}")
            st.session_state.scan_df = df
            st.session_state.last_scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Run scan if empty or button clicked
    if st.session_state.scan_df.empty or run_scan_btn:
        execute_single_scan()

    # ==========================================
    # TOP HEADER & KPI METRICS
    # ==========================================
    st.markdown('<div class="main-title">⚡ Chartink Live Scanner & Analysis Terminal</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Real-Time Technical Screener for National Stock Exchange (NSE) Equities</div>', unsafe_allow_html=True)

    df_raw = st.session_state.scan_df.copy()

    # Filter Single Scan Data
    filtered_df = df_raw.copy()
    if not filtered_df.empty:
        if "close" in filtered_df.columns:
            filtered_df = filtered_df[(filtered_df["close"] >= min_price) & (filtered_df["close"] <= max_price)]
        if "volume" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["volume"] >= min_vol]
        if "per_chg" in filtered_df.columns:
            if filter_direction == "🟢 Gainers (> 0%)":
                filtered_df = filtered_df[filtered_df["per_chg"] > 0]
            elif filter_direction == "🔴 Losers (< 0%)":
                filtered_df = filtered_df[filtered_df["per_chg"] < 0]
        if search_query:
            mask = (
                filtered_df["nsecode"].astype(str).str.contains(search_query, case=False, na=False) |
                filtered_df["name"].astype(str).str.contains(search_query, case=False, na=False)
            )
            filtered_df = filtered_df[mask]

        # Apply Institutional Filters if any enabled (Section 18 & 19)
        inst_filters_active = any([
            f_mf_inc, f_fii_inc, f_dii_buy, f_mf_cons, f_new_entry, f_multi_mf, f_inst_acc,
            min_mf_inc_pct > 0, min_mf_buyers > 1, min_fii_inc_pct > 0, min_mf_cons_score > 0
        ])

        if inst_filters_active:
            try:
                repo = InstitutionalRepository()
                inst_summary_df = repo.get_all_stocks_mf_summary()
                if not inst_summary_df.empty:
                    inst_summary_df["stock"] = inst_summary_df["stock"].str.upper()

                    # Filter criteria
                    valid_stocks = set(inst_summary_df["stock"])

                    if f_mf_inc or min_mf_inc_pct > 0:
                        threshold = max(0.001, min_mf_inc_pct)
                        valid_stocks &= set(inst_summary_df[inst_summary_df["change_pct_points"] >= threshold]["stock"])

                    if f_new_entry:
                        valid_stocks &= set(inst_summary_df[inst_summary_df["new_funds"] > 0]["stock"])

                    if f_multi_mf or min_mf_buyers > 1:
                        req_buyers = max(min_mf_buyers, 3 if f_multi_mf else 1)
                        valid_stocks &= set(inst_summary_df[inst_summary_df["funds_increased"] >= req_buyers]["stock"])

                    if f_mf_cons or min_mf_cons_score > 0:
                        req_cons = max(min_mf_cons_score, 50.0 if f_mf_cons else 0.0)
                        valid_stocks &= set(inst_summary_df[inst_summary_df["consensus_score"] >= req_cons]["stock"])

                    if f_inst_acc:
                        valid_stocks &= set(inst_summary_df[inst_summary_df["accumulation_score"] >= 60.0]["stock"])

                    filtered_df = filtered_df[filtered_df["nsecode"].astype(str).str.upper().isin(valid_stocks)]
                    st.caption(f"ℹ️ Institutional Filter applied: **{len(filtered_df)}** stocks matched institutional criteria.")
            except Exception as e:
                pass  # Graceful fallback: preserve technical screener behavior if institutional query encounters issues

    # ==========================================
    # MAIN DASHBOARD TABS
    # ==========================================
    tabs = st.tabs([
        "📊 Scanner Results",
        "🛠️ Custom Scanner Studio",
        "📋 Watchlist & Notes"
    ])

    # ----------------------------------------------------
    # TAB 1: 📊 SCANNER RESULTS
    # ----------------------------------------------------
    with tabs[0]:
        st.subheader(f"📊 Results for: {selected_scanner}")

        # Summary KPI Cards
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        with kpi1:
            st.metric("Total Scanned", len(filtered_df), f"Raw: {len(df_raw)}")
        with kpi2:
            if not filtered_df.empty and "per_chg" in filtered_df.columns:
                top_g = filtered_df.loc[filtered_df["per_chg"].idxmax()]
                st.metric("Top Gainer", f"{top_g['nsecode']}", f"{top_g['per_chg']:+.2f}%")
            else:
                st.metric("Top Gainer", "-", "-")
        with kpi3:
            if not filtered_df.empty and "per_chg" in filtered_df.columns:
                top_l = filtered_df.loc[filtered_df["per_chg"].idxmin()]
                st.metric("Top Loser", f"{top_l['nsecode']}", f"{top_l['per_chg']:+.2f}%")
            else:
                st.metric("Top Loser", "-", "-")
        with kpi4:
            if not filtered_df.empty and "per_chg" in filtered_df.columns:
                avg_chg = filtered_df["per_chg"].mean()
                st.metric("Average % Change", f"{avg_chg:+.2f}%")
            else:
                st.metric("Average % Change", "-", "-")
        with kpi5:
            if not filtered_df.empty and "volume" in filtered_df.columns:
                tot_vol = filtered_df["volume"].sum()
                st.metric("Total Traded Volume", format_volume(tot_vol))
            else:
                st.metric("Total Volume", "-", "-")

        if st.session_state.last_scan_time:
            st.caption(f"Last updated: `{st.session_state.last_scan_time}` | Active Scanner: `{selected_scanner}`")

        st.markdown("---")
        st.info("💡 **Swing Strategy Backtester**: Test these signals with next-day open entry & 3-4% targets by selecting **'🔬 1-2 Day Swing Backtest'** in the left sidebar!")

        col_act1, col_act2 = st.columns([3, 1])
        with col_act1:
            st.write(f"Displaying **{len(filtered_df)}** matching stocks.")
        with col_act2:
            if not filtered_df.empty:
                csv_bytes = filtered_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Export Results CSV",
                    data=csv_bytes,
                    file_name=f"chartink_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="btn_export_single_csv"
                )

        if not filtered_df.empty:
            display_df = filtered_df.copy()
            display_df["Turnover_Cr"] = (display_df["close"] * display_df["volume"]) / 10_000_000
            display_df["TV_Chart"] = display_df["nsecode"].apply(
                lambda s: f"https://in.tradingview.com/chart/?symbol=NSE:{s}"
            )
            display_df["Chartink_Link"] = display_df["nsecode"].apply(
                lambda s: f"https://chartink.com/stocks/{s}.html"
            )

            # Enrich with institutional data if available in DB
            repo = InstitutionalRepository()
            inst_map = {}
            try:
                inst_all = repo.get_all_stocks_mf_summary()
                if not inst_all.empty:
                    inst_map = {
                        r["stock"]: {
                            "mf_holding": f"{r['current_mf_holding']:.1f}%",
                            "mf_chg": f"{r['change_pct_points']:+.2f}",
                            "score": f"{r['accumulation_score']:.0f}/100",
                            "trend": "🟢 Accumulating" if r["change_pct_points"] > 0 else ("🔴 Selling" if r["change_pct_points"] < 0 else "🟡 Neutral")
                        }
                        for _, r in inst_all.iterrows()
                    }
            except Exception:
                pass

            display_df["MF_Holding"] = display_df["nsecode"].map(lambda s: inst_map.get(s, {}).get("mf_holding", "-"))
            display_df["MF_Change"] = display_df["nsecode"].map(lambda s: inst_map.get(s, {}).get("mf_chg", "-"))
            display_df["Inst_Trend"] = display_df["nsecode"].map(lambda s: inst_map.get(s, {}).get("trend", "-"))

            formatted_table = pd.DataFrame({
                "Ticker": display_df["nsecode"],
                "Company Name": display_df["name"],
                "Close (₹)": display_df["close"].map("{:,.2f}".format),
                "% Change": display_df["per_chg"].map("{:+.2f}%".format),
                "Volume": display_df["volume"].apply(format_volume),
                "Turnover": display_df["Turnover_Cr"].map("₹{:,.2f} Cr".format),
                "MF Holding": display_df["MF_Holding"],
                "MF Change (pp)": display_df["MF_Change"],
                "Institutional Trend": display_df["Inst_Trend"],
                "TradingView Link": display_df["TV_Chart"],
                "Chartink Link": display_df["Chartink_Link"]
            })

            st.dataframe(
                formatted_table,
                column_config={
                    "TradingView Link": st.column_config.LinkColumn("TradingView", display_text="Open Chart ↗"),
                    "Chartink Link": st.column_config.LinkColumn("Chartink", display_text="View on Chartink ↗"),
                },
                use_container_width=True,
                hide_index=True
            )

            # Quick Add to Watchlist from Results
            st.markdown("---")
            st.markdown("#### 📌 Bookmark Stock to Local Watchlist")
            w_col1, w_col2, w_col3 = st.columns([2, 2, 1])
            with w_col1:
                stock_to_add = st.selectbox("Select Stock to Bookmark", display_df["nsecode"].tolist(), key="sb_add_w_stock")
            with w_col2:
                stock_row = display_df[display_df["nsecode"] == stock_to_add].iloc[0]
                w_note = st.text_input("Trade Note", value=f"Scanned via {selected_scanner}", key="txt_w_note")
            with w_col3:
                st.write("")
                st.write("")
                is_in_w = stock_to_add in st.session_state.watchlist
                if st.button("✓ In Watchlist" if is_in_w else "➕ Add to Watchlist", key="btn_save_to_w", disabled=is_in_w, use_container_width=True):
                    st.session_state.watchlist[stock_to_add] = {
                        "ticker": stock_to_add,
                        "price": float(stock_row.get("close", 0.0)),
                        "added_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "scanner": selected_scanner,
                        "note": w_note
                    }
                    save_watchlist()
                    st.success(f"Added **{stock_to_add}** to Watchlist!")
                    st.rerun()

        else:
            st.info("No stocks currently match the chosen scanner conditions and filter thresholds.")

    # ----------------------------------------------------
    # TAB 2: 🛠️ CUSTOM SCANNER STUDIO & URL PARSER
    # ----------------------------------------------------
    with tabs[1]:
        st.subheader("🛠️ Custom Chartink Scanner Studio & URL Parser")
        st.write(
            "Import any screener from Chartink either by pasting its URL directly or pasting the raw `scan_clause` payload."
        )

        # Feature: Auto-Extract Clause from URL
        st.markdown("#### 🔗 Option A: Auto-Fetch Scanner from Chartink URL")
        st.caption("Paste any Chartink screener URL (e.g., `https://chartink.com/screener/short-term-breakouts` or `https://chartink.com/screener/consolidatedbo`) to pull its clause directly:")
        u_col1, u_col2 = st.columns([3, 1])
        with u_col1:
            chartink_screener_url = st.text_input(
                "Chartink Screener Webpage URL",
                value="https://chartink.com/screener/short-term-breakouts",
                key="txt_screener_url"
            )
        with u_col2:
            st.write("")
            st.write("")
            if st.button("🔍 Fetch Scanner Clause", key="btn_fetch_from_url", use_container_width=True):
                with st.spinner("Extracting screener definition from URL..."):
                    c_clause, c_name, c_err = extract_clause_from_url(chartink_screener_url)
                    if c_err:
                        st.error(f"Failed to extract from URL: {c_err}")
                    else:
                        st.session_state.custom_clause_to_run = c_clause
                        st.success(f"Successfully extracted scanner: **{c_name}**!")

        st.markdown("---")

        # Feature: Direct Scan Clause Input
        st.markdown("#### 📝 Option B: Custom Scan Clause Editor")
        default_text = st.session_state.get(
            "custom_clause_to_run",
            PRESET_SCANNERS["Short Term Breakouts"]["clause"]
        )
        custom_clause = st.text_area(
            "Chartink Scan Clause (Payload string)",
            value=default_text,
            height=180,
            help="Copy the scan clause from Chartink network payload or edit directly.",
            key="txt_custom_clause_area"
        )

        c_btn1, c_btn2 = st.columns([1, 2])
        with c_btn1:
            if st.button("⚡ Test Custom Scan", key="btn_test_custom_studio", use_container_width=True):
                st.session_state.custom_clause_to_run = custom_clause
                t_start = time.time()
                with st.spinner("Executing custom Chartink scan..."):
                    c_df, c_err = chartink_scraper(custom_clause)
                    t_elapsed = time.time() - t_start

                if c_err:
                    st.error(f"Error: {c_err}")
                else:
                    st.success(f"Scan Completed in {t_elapsed:.2f}s! Found **{len(c_df)}** stocks.")
                    st.dataframe(c_df, use_container_width=True)

        with c_btn2:
            st.markdown("""
            **💡 Pro-Tip:**
            - You can test any scanner here.
            - To use your custom scan across the dashboard, select **'🛠️ Custom Scan Clause'** in the sidebar.
            """)

    # ----------------------------------------------------
    # TAB 3: 📋 WATCHLIST & NOTES
    # ----------------------------------------------------
    with tabs[2]:
        st.subheader("📋 Persisted Local Watchlist")

        if st.session_state.watchlist:
            w_items = list(st.session_state.watchlist.values())
            w_df = pd.DataFrame(w_items)
            st.write(f"You have **{len(w_df)}** bookmarked stocks.")

            col_wdl, col_wclear = st.columns([3, 1])
            with col_wdl:
                csv_w = w_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Watchlist CSV",
                    data=csv_w,
                    file_name=f"watchlist_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    key="btn_dl_w"
                )

            st.dataframe(w_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            del_col1, del_col2 = st.columns([3, 1])
            with del_col1:
                sym_to_del = st.selectbox("Select Stock to Remove", list(st.session_state.watchlist.keys()), key="sel_del_w")
            with del_col2:
                if st.button("🗑️ Remove from Watchlist", key="btn_del_w"):
                    del st.session_state.watchlist[sym_to_del]
                    save_watchlist()
                    st.success(f"Removed {sym_to_del} from watchlist.")
                    st.rerun()

        else:
            st.info("Your watchlist is currently empty. Bookmark stocks from the 'Scanner Results' tab!")

    # Auto-refresh loop
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()
