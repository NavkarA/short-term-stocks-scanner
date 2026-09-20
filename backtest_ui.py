"""
1-10 Day Swing Strategy Backtest Dashboard Module.
Simulates buying on Day T+1 Open and holding for 1 to 10 days
with customizable Target 1, Target 2, Stop Loss, and Trailing Stop Loss parameters.
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
    Renders the complete 1-10 Day Swing Backtest Dashboard in Streamlit.
    """
    st.markdown("""
        <div>
            <h1 style='font-size: 2.2rem; font-weight: 800; margin-bottom: 0.2rem;'>
                🔬 Swing Strategy Backtest Engine (1–10 Days)
            </h1>
            <p style='font-size: 1.05rem; color: #8b949e; margin-bottom: 1.5rem;'>
                Simulate next-day Open entry (Day T+1) on Chartink screener signals, held for 1 to 10 days
                with customizable profit targets (T1 & T2), risk limits, and dynamic Trailing Stop Loss.
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
        c1, c2 = st.columns([1.1, 1.2])

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

            st.markdown("#### 📅 Backtest Scope & Holding Period")
            lookback_days = st.slider(
                "Historical Trading Days to Evaluate",
                min_value=5,
                max_value=30,
                value=7,
                step=1,
                help="Number of past trading sessions to evaluate (Default: at least 7 days).",
                key="bt_lookback_days"
            )

            max_holding_days = st.slider(
                "Holding Horizon (Trading Days)",
                min_value=1,
                max_value=10,
                value=3,
                step=1,
                help="Maximum holding period in trading days (from 1 day up to 10 days).",
                key="bt_holding_days"
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

            t1_book_pct = st.slider(
                "Target 1 Booking Quantity (%)",
                min_value=10,
                max_value=100,
                value=50,
                step=5,
                help="Portion of total position to book upon hitting Target 1 (default: 50%).",
                key="bt_t1_book_pct"
            )

            target_2_pct = st.slider(
                "Target 2 Gain (%) - Adjustable",
                min_value=2.0,
                max_value=20.0,
                value=6.0,
                step=0.5,
                help="Second profit target for runners (Adjustable).",
                key="bt_target_2"
            )

            max_t2_book = max(0, 100 - t1_book_pct)
            t2_book_pct = st.slider(
                "Target 2 Booking Quantity (%)",
                min_value=0,
                max_value=max(0, max_t2_book),
                value=min(30, max_t2_book),
                step=5,
                help="Portion of total position to book on hitting Target 2. Remainder rides to Target 3.",
                key="bt_t2_book_pct"
            )

            rem_t3 = max(0, 100 - t1_book_pct - t2_book_pct)
            st.caption(f"Allocations: T1: **{t1_book_pct}%** | T2: **{t2_book_pct}%** | Remainder for T3 / Runner: **{rem_t3}%**")

            target_3_pct = st.slider(
                "Target 3 Gain (%)",
                min_value=3.0,
                max_value=30.0,
                value=10.0,
                step=0.5,
                help="Third extended target for strong multi-day momentum swings.",
                key="bt_target_3"
            )

            sl_pct = st.slider(
                "Initial Stop Loss (%)",
                min_value=0.5,
                max_value=10.0,
                value=2.0,
                step=0.5,
                help="Maximum stop loss threshold from entry price (default: 2.0%).",
                key="bt_sl"
            )

            # Trailing Stop Loss Controls
            st.markdown("#### 🛡️ Trailing Stop Loss Options")
            enable_trailing_sl = st.checkbox(
                "Enable Trailing Stop Loss",
                value=False,
                help="Automatically ratchet the stop loss upwards to protect profit.",
                key="bt_enable_trailing"
            )

            if enable_trailing_sl:
                tsl_c1, tsl_c2 = st.columns(2)
                with tsl_c1:
                    trailing_sl_pct = st.slider(
                        "Trailing Offset (%)",
                        min_value=0.5,
                        max_value=5.0,
                        value=2.0,
                        step=0.5,
                        help="Distance below peak high to trail the stop loss.",
                        key="bt_trailing_sl_pct"
                    )
                with tsl_c2:
                    trail_mechanism = st.selectbox(
                        "Trailing Trigger Mechanism",
                        [
                            "Move to Breakeven & Trail after Target 1",
                            "Trail from Entry immediately"
                        ],
                        index=0,
                        help="Breakeven mode eliminates downside risk once Target 1 is touched, then lets runners trail higher.",
                        key="bt_trail_mechanism"
                    )
            else:
                trailing_sl_pct = 2.0
                trail_mechanism = "Move to Breakeven & Trail after Target 1"

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
                f"Rule: Buy at Open of Day $T+1$. Holds for up to **{max_holding_days} day(s)**. "
                f"Targets: +{target_1_pct}% / +{target_2_pct}% / +{target_3_pct}%. Stop Loss: -{sl_pct}%"
                f"{f' with {trailing_sl_pct}% Trailing SL' if enable_trailing_sl else ''}."
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
            update_progress(0.1, "Fetching historical screener signals from Chartink backtest API...")
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

            update_progress(0.3, f"Retrieved {len(signals_by_date)} trading dates. Downloading market data...")

            trail_trigger_val = "After Target 1" if "Breakeven" in trail_mechanism else "From Entry"

            trades_df, summary_metrics, date_summary_df = run_swing_backtest(
                signals_by_date=signals_by_date,
                target_1_pct=target_1_pct,
                target_2_pct=target_2_pct,
                target_3_pct=target_3_pct,
                sl_pct=sl_pct,
                max_holding_days=max_holding_days,
                num_days=lookback_days,
                enable_trailing_sl=enable_trailing_sl,
                trailing_sl_pct=trailing_sl_pct,
                trail_trigger=trail_trigger_val,
                t1_book_pct=t1_book_pct,
                t2_book_pct=t2_book_pct,
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
                "target_3_pct": target_3_pct,
                "sl_pct": sl_pct,
                "max_holding_days": max_holding_days,
                "lookback_days": lookback_days,
                "enable_trailing_sl": enable_trailing_sl,
                "trailing_sl_pct": trailing_sl_pct,
                "trail_mechanism": trail_mechanism,
                "t1_book_pct": t1_book_pct,
                "t2_book_pct": t2_book_pct,
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
        st.info("👋 Click **'🚀 Run Historical Backtest'** above to simulate your swing strategy across historical trading sessions.")
        return

    trades_df: pd.DataFrame = bt["trades_df"]
    summary: Dict[str, Any] = bt["summary"]
    date_summary_df: pd.DataFrame = bt["date_summary_df"]

    st.markdown("---")
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        st.subheader(f"📊 Backtest Results: {bt['scanner_name']}")
        tsl_label = f"🛡️ Trailing SL: {bt['trailing_sl_pct']}% ({bt['trail_mechanism']})" if bt.get("enable_trailing_sl") else "Fixed SL (No Trailing)"
        t1_b = bt.get("t1_book_pct", 50)
        t2_b = bt.get("t2_book_pct", 30)
        t3_b = max(0, 100 - t1_b - t2_b)
        st.caption(
            f"Evaluated Last **{bt['lookback_days']} Trading Days** | "
            f"Target 1: **+{bt['target_1_pct']}%** (Book {t1_b}%) | "
            f"Target 2: **+{bt['target_2_pct']}%** (Book {t2_b}%) | "
            f"Target 3: **+{bt.get('target_3_pct', 10.0)}%** (Runner {t3_b}%) | "
            f"Stop Loss: **-{bt['sl_pct']}%** | Holding Horizon: **Up to {bt['max_holding_days']} Day(s)** | "
            f"{tsl_label} | Run at: `{bt['run_time']}`"
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
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)

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
        t3_rate = summary.get("t3_hit_rate_pct", 0.0)
        st.metric(
            f"Target 3 (+{bt.get('target_3_pct', 10.0)}%)",
            f"{t3_rate:.1f}%",
            f"{summary.get('t3_hit_count', 0)} Hit"
        )
    with m6:
        if bt.get("enable_trailing_sl"):
            trail_rate = summary.get("trail_sl_hit_rate_pct", 0.0)
            sl_rate = summary.get("sl_hit_rate_pct", 0.0)
            st.metric(
                f"Trailing / Fixed SL",
                f"{trail_rate:.1f}% / {sl_rate:.1f}%",
                f"{summary.get('trail_sl_hit_count', 0)} Trail / {summary.get('sl_hit_count', 0)} SL"
            )
        else:
            sl_rate = summary.get("sl_hit_rate_pct", 0.0)
            st.metric(
                f"Stop Loss (-{bt['sl_pct']}%)",
                f"{sl_rate:.1f}%",
                f"{summary.get('sl_hit_count', 0)} Hit",
                delta_color="inverse"
            )
    with m7:
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

        # Color mapping helper
        def get_outcome_color(label: str) -> str:
            if "Target 3" in label:
                return "#76FF03"  # Lime Green
            elif "Target 2" in label:
                return "#00C853"  # Vibrant Green
            elif "Target 1" in label:
                return "#00B0FF"  # Bright Blue
            elif "Trailing SL" in label:
                return "#FFAB00"  # Amber
            elif "Stop Loss" in label:
                return "#FF5252"  # Coral Red
            elif "Exited" in label:
                return "#AB47BC"  # Purple
            return "#9E9E9E"

        color_map = {name: get_outcome_color(name) for name in outcome_counts["Outcome"]}

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
            if "Target 3 Hits" in date_summary_df.columns and date_summary_df["Target 3 Hits"].sum() > 0:
                fig_bar.add_trace(go.Bar(
                    x=date_summary_df["Signal Date"],
                    y=date_summary_df["Target 3 Hits"],
                    name=f"Target 3 (+{bt.get('target_3_pct', 10.0)}%)",
                    marker_color="#76FF03"
                ))
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
            if "Trailing SL Hits" in date_summary_df.columns and date_summary_df["Trailing SL Hits"].sum() > 0:
                fig_bar.add_trace(go.Bar(
                    x=date_summary_df["Signal Date"],
                    y=date_summary_df["Trailing SL Hits"],
                    name="Trailing SL Hits 🛡️",
                    marker_color="#FFAB00"
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
        col_cfg = {
            "Signal Date": st.column_config.TextColumn("Signal Date", width="medium"),
            "Nifty Open": st.column_config.NumberColumn("Nifty Open", format="₹%,.2f"),
            "Nifty Close": st.column_config.NumberColumn("Nifty Close", format="₹%,.2f"),
            "Nifty Chg %": st.column_config.NumberColumn("Nifty Chg %", format="%+.2f%%"),
            "Signals Count": st.column_config.NumberColumn("Stocks Count", format="%d"),
            "Target 1 Hits": st.column_config.NumberColumn("Target 1 Hits 🎯", format="%d"),
            "Target 2 Hits": st.column_config.NumberColumn("Target 2 Hits 🚀", format="%d"),
            "Target 3 Hits": st.column_config.NumberColumn("Target 3 Hits 🏆", format="%d"),
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
        }
        if "Trailing SL Hits" in date_summary_df.columns:
            col_cfg["Trailing SL Hits"] = st.column_config.NumberColumn("Trailing SL Hits 🛡️", format="%d")

        st.dataframe(
            date_summary_df,
            column_config=col_cfg,
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
        "Target 3 Price",
        "Initial SL Price",
        "Final SL Price",
        "Peak High",
        "Peak Gain %",
        "Exit Price",
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
            "Target 3 Price": st.column_config.NumberColumn("T3 Price (₹)", format="₹%.2f"),
            "Initial SL Price": st.column_config.NumberColumn("Initial SL (₹)", format="₹%.2f"),
            "Final SL Price": st.column_config.NumberColumn("Final SL (₹)", format="₹%.2f"),
            "Peak High": st.column_config.NumberColumn("Peak High (₹)", format="₹%.2f"),
            "Peak Gain %": st.column_config.NumberColumn("Peak Gain %", format="%+.2f%%"),
            "Exit Price": st.column_config.NumberColumn("Exit Price (₹)", format="₹%.2f"),
            "Realized Return %": st.column_config.NumberColumn("Realized Return %", format="%+.2f%%"),
            "Holding Days": st.column_config.NumberColumn("Hold (Days)", format="%d"),
        },
        use_container_width=True,
        hide_index=True
    )
