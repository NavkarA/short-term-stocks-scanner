"""
1-2 Day Swing Strategy Backtest Dashboard Module.
Simulates buying on Day T+1 Open and holding for 1 to 2 days
with customizable Target 1, Target 2, and Stop Loss parameters.
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from scraper import (
    PRESET_SCANNERS,
    CHARTINK_BASE_URL,
    extract_clause_from_url,
    chartink_historical_signals,
    run_swing_backtest,
)


def render_backtest_dashboard():
    """
    Renders the complete 1-2 Day Swing Backtest Dashboard in Streamlit.
    """
    st.markdown("""
        <div>
            <h1 style='font-size: 2.2rem; font-weight: 800; margin-bottom: 0.2rem;'>
                🔬 1-2 Day Swing Strategy Backtester
            </h1>
            <p style='font-size: 1.05rem; color: #8b949e; margin-bottom: 1.5rem;'>
                Simulate next-day Open entry (Day T+1) on Chartink screener signals, held for 1 or 2 days
                to capture quick momentum breakouts with multi-target and stop loss tracking.
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Initialize Backtest Session States
    if "bt_results" not in st.session_state:
        st.session_state.bt_results = None
    if "bt_signals_cache" not in st.session_state:
        st.session_state.bt_signals_cache = {}

    # ==========================================
    # STRATEGY & PARAMETER CONTROLS
    # ==========================================
    with st.expander("⚙️ Strategy Parameters & Scanner Configuration", expanded=st.session_state.bt_results is None):
        c1, c2 = st.columns([1.2, 1])

        with c1:
            st.markdown("#### 🎯 Scanner Selection")
            scanner_options = list(PRESET_SCANNERS.keys()) + ["🔗 Custom Chartink URL"]
            chosen_scanner = st.selectbox(
                "Select Scanner to Backtest",
                scanner_options,
                index=0,
                key="bt_scanner_select"
            )

            clause_to_backtest = ""
            url_to_backtest = CHARTINK_BASE_URL

            if chosen_scanner == "🔗 Custom Chartink URL":
                custom_url = st.text_input(
                    "Paste Chartink Screener Webpage URL",
                    value="https://chartink.com/screener/short-term-breakouts",
                    key="bt_custom_url_input"
                )
                if custom_url:
                    url_to_backtest = custom_url
                    with st.spinner("Extracting clause from URL..."):
                        c_clause, c_name, c_err = extract_clause_from_url(custom_url)
                        if c_err:
                            st.error(f"URL parsing failed: {c_err}")
                        else:
                            clause_to_backtest = c_clause
                            st.success(f"Loaded: **{c_name}**")
            else:
                clause_to_backtest = PRESET_SCANNERS[chosen_scanner]["clause"]
                url_to_backtest = PRESET_SCANNERS[chosen_scanner].get("url", CHARTINK_BASE_URL)
                st.caption(f"ℹ️ {PRESET_SCANNERS[chosen_scanner]['description']}")

            st.markdown("#### 📅 Backtest Horizon")
            lookback_days = st.slider(
                "Historical Trading Days to Evaluate",
                min_value=5,
                max_value=30,
                value=7,
                step=1,
                help="Number of past trading sessions to evaluate (Default: at least 7 days).",
                key="bt_lookback_days"
            )

        with c2:
            st.markdown("#### 📊 Target & Risk Rules")
            target_1_pct = st.slider(
                "Target 1 Gain (%)",
                min_value=1.0,
                max_value=10.0,
                value=3.5,
                step=0.5,
                help="First profit target (User requested: 3-4%, default 3.5%).",
                key="bt_target_1"
            )

            target_2_pct = st.slider(
                "Target 2 Gain (%) - Adjustable",
                min_value=2.0,
                max_value=20.0,
                value=6.0,
                step=0.5,
                help="Extended breakout target for high-momentum runners (Adjustable).",
                key="bt_target_2"
            )

            sl_pct = st.slider(
                "Stop Loss (%)",
                min_value=0.5,
                max_value=10.0,
                value=2.0,
                step=0.5,
                help="Maximum stop loss threshold from entry price (default: 2.0%).",
                key="bt_sl"
            )

            max_holding_days = st.radio(
                "Maximum Holding Period",
                options=[1, 2],
                index=1,
                format_func=lambda x: f"{x} Day{'s' if x > 1 else ''} (Exit at Day {x} Close if no Target/SL hit)",
                horizontal=True,
                key="bt_holding_days"
            )

        st.markdown("---")
        btn_col1, btn_col2 = st.columns([1, 3])
        with btn_col1:
            run_bt_button = st.button(
                "🚀 Run Historical Backtest",
                use_container_width=True,
                type="primary",
                key="btn_run_backtest"
            )
        with btn_col2:
            st.caption(
                "Rule: Buy at Open of Day $T+1$ following the screener signal. "
                "Evaluates Intraday High/Low for Day 1 and Day 2 to record Target 1, Target 2, or Stop Loss hits."
            )

    # ==========================================
    # BACKTEST EXECUTION ENGINE
    # ==========================================
    if run_bt_button:
        if not clause_to_backtest:
            st.error("No valid scanner clause found. Please select a preset or provide a valid Chartink URL.")
            return

        progress_bar = st.progress(0.05)
        status_text = st.empty()

        def update_progress(pct: float, msg: str):
            progress_bar.progress(pct)
            status_text.markdown(f"⏳ **{msg}**")

        try:
            update_progress(0.1, f"Fetching historical screener signals from Chartink backtest API...")
            signals_by_date, err = chartink_historical_signals(
                clause_to_backtest,
                url=url_to_backtest,
                max_rows=160
            )

            if err or not signals_by_date:
                status_text.empty()
                progress_bar.empty()
                st.error(f"Failed to fetch historical signals from Chartink: {err or 'No signals found'}")
                return

            update_progress(0.3, f"Retrieved {len(signals_by_date)} trading dates from Chartink. Downloading market data...")

            trades_df, summary_metrics, date_summary_df = run_swing_backtest(
                signals_by_date=signals_by_date,
                target_1_pct=target_1_pct,
                target_2_pct=target_2_pct,
                sl_pct=sl_pct,
                max_holding_days=max_holding_days,
                num_days=lookback_days,
                progress_callback=update_progress
            )

            update_progress(1.0, "Backtest completed successfully!")
            time.sleep(0.4)
            status_text.empty()
            progress_bar.empty()

            st.session_state.bt_results = {
                "trades_df": trades_df,
                "summary": summary_metrics,
                "date_summary_df": date_summary_df,
                "scanner_name": chosen_scanner,
                "target_1_pct": target_1_pct,
                "target_2_pct": target_2_pct,
                "sl_pct": sl_pct,
                "max_holding_days": max_holding_days,
                "lookback_days": lookback_days,
                "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.rerun()

        except Exception as e:
            status_text.empty()
            progress_bar.empty()
            st.error(f"An unexpected error occurred during backtesting: {str(e)}")
            return

    # ==========================================
    # DISPLAY BACKTEST RESULTS
    # ==========================================
    bt = st.session_state.bt_results

    if not bt or bt.get("trades_df") is None or bt["trades_df"].empty:
        st.info("👋 Click **'🚀 Run Historical Backtest'** above to simulate the 1-2 day swing strategy over the last 7+ trading sessions.")
        return

    trades_df: pd.DataFrame = bt["trades_df"]
    summary: Dict[str, Any] = bt["summary"]
    date_summary_df: pd.DataFrame = bt["date_summary_df"]

    st.markdown("---")
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.subheader(f"📊 Backtest Results: {bt['scanner_name']}")
        st.caption(
            f"Evaluated Last **{bt['lookback_days']} Trading Days** | "
            f"Target 1: **+{bt['target_1_pct']}%** | Target 2: **+{bt['target_2_pct']}%** | "
            f"Stop Loss: **-{bt['sl_pct']}%** | Holding: **{bt['max_holding_days']} Day(s)** | "
            f"Run at: `{bt['run_time']}`"
        )
    with header_col2:
        csv_bytes = trades_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Backtest CSV",
            data=csv_bytes,
            file_name=f"swing_backtest_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True,
            key="btn_download_bt_csv"
        )

    # ----------------------------------------------------
    # 1. SUMMARY KPI METRIC CARDS
    # ----------------------------------------------------
    m1, m2, m3, m4, m5, m6 = st.columns(6)

    with m1:
        st.metric(
            "Total Signals",
            f"{summary.get('completed_trades', 0)}",
            f"Raw: {summary.get('total_trades', 0)}"
        )
    with m2:
        wr = summary.get("win_rate_pct", 0.0)
        st.metric(
            "Overall Win Rate",
            f"{wr:.1f}%",
            f"{summary.get('wins', 0)}W / {summary.get('losses', 0)}L"
        )
    with m3:
        t1_rate = summary.get("t1_hit_rate_pct", 0.0)
        st.metric(
            f"Target 1 (+{bt['target_1_pct']}%)",
            f"{t1_rate:.1f}%",
            f"{summary.get('t1_hit_count', 0)} Hit"
        )
    with m4:
        t2_rate = summary.get("t2_hit_rate_pct", 0.0)
        st.metric(
            f"Target 2 (+{bt['target_2_pct']}%)",
            f"{t2_rate:.1f}%",
            f"{summary.get('t2_hit_count', 0)} Hit"
        )
    with m5:
        sl_rate = summary.get("sl_hit_rate_pct", 0.0)
        st.metric(
            f"Stop Loss (-{bt['sl_pct']}%)",
            f"{sl_rate:.1f}%",
            f"{summary.get('sl_hit_count', 0)} Hit",
            delta_color="inverse"
        )
    with m6:
        avg_ret = summary.get("avg_return_pct", 0.0)
        pf = summary.get("profit_factor", 1.0)
        st.metric(
            "Average Return",
            f"{avg_ret:+.2f}%",
            f"PF: {pf:.2f}"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # 2. CHARTS: OUTCOME BREAKDOWN & DAILY DISTRIBUTION
    # ----------------------------------------------------
    ch_col1, ch_col2 = st.columns([1, 1.3])

    with ch_col1:
        st.markdown("##### 🥧 Trade Outcomes Breakdown")
        outcome_counts = trades_df["Outcome"].value_counts().reset_index()
        outcome_counts.columns = ["Outcome", "Count"]

        # Color palette for outcomes
        color_map = {
            "🚀 Target 2 Hit (Day 1)": "#00C853",
            "🚀 Target 2 Hit (Day 2)": "#2E7D32",
            "🎯 Target 1 Hit (Day 1)": "#69F0AE",
            "🎯 Target 1 Hit (Day 2)": "#00B0FF",
            "🛑 Stop Loss Hit (Day 1)": "#D50000",
            "🛑 Stop Loss Hit (Day 2)": "#FF5252",
            "⏱️ Exited at Day 1 Close": "#FFD600",
            "⏱️ Exited at Day 2 Close": "#FF9100",
            "⏳ Pending Entry": "#9E9E9E"
        }

        fig_donut = px.pie(
            outcome_counts,
            names="Outcome",
            values="Count",
            hole=0.45,
            color="Outcome",
            color_discrete_map=color_map
        )
        fig_donut.update_traces(textinfo="percent+label", textposition="outside")
        fig_donut.update_layout(
            margin=dict(l=10, r=10, t=20, b=20),
            showlegend=False,
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#E0E0E0")
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with ch_col2:
        st.markdown("##### 📅 Daily Performance (Signals per Date)")
        if not date_summary_df.empty:
            fig_bar = go.Figure()
            fig_bar.add_trace(go.Bar(
                x=date_summary_df["Signal Date"],
                y=date_summary_df["Target 2 Hits"],
                name=f"Target 2 (+{bt['target_2_pct']}%)",
                marker_color="#00C853"
            ))
            fig_bar.add_trace(go.Bar(
                x=date_summary_df["Signal Date"],
                y=date_summary_df["Target 1 Hits"],
                name=f"Target 1 (+{bt['target_1_pct']}%)",
                marker_color="#00B0FF"
            ))
            fig_bar.add_trace(go.Bar(
                x=date_summary_df["Signal Date"],
                y=date_summary_df["Stop Loss Hits"],
                name=f"Stop Loss (-{bt['sl_pct']}%)",
                marker_color="#FF5252"
            ))

            fig_bar.update_layout(
                barmode="stack",
                margin=dict(l=10, r=10, t=20, b=20),
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#E0E0E0"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(title="Signal Date", showgrid=False),
                yaxis=dict(title="Number of Stocks", showgrid=True, gridcolor="#2A2E39")
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No daily distribution available.")

    # ----------------------------------------------------
    # 3. DATE-BY-DATE BREAKDOWN TABLE
    # ----------------------------------------------------
    st.markdown("##### 🗓️ Daily Breakdown & Win Rates")
    if not date_summary_df.empty:
        st.dataframe(
            date_summary_df,
            column_config={
                "Signal Date": st.column_config.TextColumn("Signal Date", width="medium"),
                "Signals Count": st.column_config.NumberColumn("Stocks Count", format="%d"),
                "Target 1 Hits": st.column_config.NumberColumn("Target 1 Hits 🎯", format="%d"),
                "Target 2 Hits": st.column_config.NumberColumn("Target 2 Hits 🚀", format="%d"),
                "Stop Loss Hits": st.column_config.NumberColumn("Stop Loss Hits 🛑", format="%d"),
                "Win Rate %": st.column_config.ProgressColumn(
                    "Win Rate %",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100
                ),
                "Average Return %": st.column_config.NumberColumn(
                    "Avg Return %",
                    format="%+.2f%%"
                ),
            },
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")

    # ----------------------------------------------------
    # 4. DETAILED TRADE LOG & INTERACTIVE FILTERING
    # ----------------------------------------------------
    st.markdown("##### 📋 Stock-by-Stock Trade Log")

    flt_col1, flt_col2, flt_col3 = st.columns([1.5, 1.5, 2])
    with flt_col1:
        all_sig_dates = ["All Dates"] + sorted(list(trades_df["Signal Date"].unique()), reverse=True)
        selected_date_filter = st.selectbox("Filter by Signal Date", all_sig_dates, index=0, key="bt_filter_date")
    with flt_col2:
        all_outcomes = ["All Outcomes"] + sorted(list(trades_df["Outcome"].unique()))
        selected_outcome_filter = st.selectbox("Filter by Outcome", all_outcomes, index=0, key="bt_filter_outcome")
    with flt_col3:
        filter_ticker = st.text_input("Filter Ticker Symbol", "", key="bt_filter_ticker").strip().upper()

    view_df = trades_df.copy()

    if selected_date_filter != "All Dates":
        view_df = view_df[view_df["Signal Date"] == selected_date_filter]
    if selected_outcome_filter != "All Outcomes":
        view_df = view_df[view_df["Outcome"] == selected_outcome_filter]
    if filter_ticker:
        view_df = view_df[view_df["Symbol"].str.contains(filter_ticker, case=False, na=False)]

    st.caption(f"Displaying **{len(view_df)}** trades matching filters.")

    # Add TradingView chart links
    view_df["TradingView"] = view_df["Symbol"].apply(
        lambda s: f"https://in.tradingview.com/chart/?symbol=NSE:{s}"
    )

    # Reorder display columns for maximum clarity
    display_cols = [
        "Signal Date",
        "Entry Date",
        "Symbol",
        "TradingView",
        "Entry Price",
        "Target 1 Price",
        "Target 2 Price",
        "Stop Loss Price",
        "Day 1 High",
        "Day 1 Max Gain %",
        "Day 2 High",
        "Day 2 Max Gain %",
        "Holding Days",
        "Outcome",
        "Realized Return %",
        "Sector"
    ]
    present_cols = [c for c in display_cols if c in view_df.columns]

    st.dataframe(
        view_df[present_cols],
        column_config={
            "TradingView": st.column_config.LinkColumn("TradingView", display_text="📈 Chart"),
            "Entry Price": st.column_config.NumberColumn("Entry (₹)", format="₹%.2f"),
            "Target 1 Price": st.column_config.NumberColumn("T1 Price (₹)", format="₹%.2f"),
            "Target 2 Price": st.column_config.NumberColumn("T2 Price (₹)", format="₹%.2f"),
            "Stop Loss Price": st.column_config.NumberColumn("SL Price (₹)", format="₹%.2f"),
            "Day 1 High": st.column_config.NumberColumn("D1 High (₹)", format="₹%.2f"),
            "Day 1 Max Gain %": st.column_config.NumberColumn("D1 Max Gain %", format="%+.2f%%"),
            "Day 2 High": st.column_config.NumberColumn("D2 High (₹)", format="₹%.2f"),
            "Day 2 Max Gain %": st.column_config.NumberColumn("D2 Max Gain %", format="%+.2f%%"),
            "Realized Return %": st.column_config.NumberColumn("Realized Return %", format="%+.2f%%"),
            "Holding Days": st.column_config.NumberColumn("Hold (Days)", format="%d"),
        },
        use_container_width=True,
        hide_index=True
    )
