"""
Tab 3: Mutual Fund Stock Scanner & Accumulation Tracker.
Identifies stocks where mutual funds are actively accumulating, distributing,
entering newly, or completely exiting.
Includes configurable scoring engine, multi-fund accumulation filters, and export.
"""

import streamlit as st
import pandas as pd
from institutional.db.repository import InstitutionalRepository
from institutional.models import AccumulationScoreConfig
from institutional.ui.components import (
    render_freshness_badge,
    render_exact_date_limitation_banner,
    export_dataframe_buttons,
    TOOLTIPS,
)


def render_mf_scanner_tab(repo: InstitutionalRepository):
    st.subheader("🔍 Mutual Fund Stock Scanner & Accumulation Engine")
    st.caption(
        "Institutional accumulation scanner comparing latest reported AMFI mutual fund portfolio disclosures. "
        "Tracks net fund movements, fresh entries, and multi-scheme consensus."
    )

    # Configurable Accumulation Scoring Engine (Section 6)
    with st.expander("⚙️ Customize Accumulation Scoring Engine Parameters", expanded=False):
        st.caption("Adjust model weights for the descriptive Institutional Accumulation Metric (0-100 scale).")
        w_col1, w_col2, w_col3 = st.columns(3)
        with w_col1:
            w_inc = st.number_input("Weight: MF Holding Increase", value=2.0, step=0.5, key="w_inc")
            w_new = st.number_input("Weight: New MF Entry", value=3.0, step=0.5, key="w_new")
            w_multi_inc = st.number_input("Weight: Each Fund Increasing", value=1.0, step=0.5, key="w_m_inc")
        with w_col2:
            w_dec = st.number_input("Weight: MF Holding Decrease", value=-2.0, step=0.5, key="w_dec")
            w_exit = st.number_input("Weight: Complete MF Exit", value=-3.0, step=0.5, key="w_exit")
            w_multi_dec = st.number_input("Weight: Each Fund Decreasing", value=-1.0, step=0.5, key="w_m_dec")
        with w_col3:
            w_sig_inc = st.number_input("Weight: Significant Increase (>1.0%)", value=2.0, step=0.5, key="w_sig_inc")
            w_sig_dec = st.number_input("Weight: Significant Decrease (>1.0%)", value=-2.0, step=0.5, key="w_sig_dec")
            sig_thresh = st.number_input("Significant Threshold (pp)", value=1.0, step=0.25, key="sig_thresh")

    score_config = AccumulationScoreConfig(
        holding_increase=w_inc,
        new_entry=w_new,
        holding_decrease=w_dec,
        exit=w_exit,
        multiple_funds_increasing=w_multi_inc,
        multiple_funds_decreasing=w_multi_dec,
        significant_increase=w_sig_inc,
        significant_decrease=w_sig_dec,
        significant_threshold_pct=sig_thresh,
    )

    # Fetch summary for all stocks
    df = repo.get_all_stocks_mf_summary(config=score_config)

    if df.empty:
        st.info("No Mutual Fund portfolio disclosure data found in database. Please click '🔄 Update Institutional Data' in the History tab.")
        return

    # Disclosure compliance banner
    curr_date = df["current_disclosure_date"].iloc[0] if "current_disclosure_date" in df.columns else "N/A"
    prev_date = df["previous_disclosure_date"].iloc[0] if "previous_disclosure_date" in df.columns else "N/A"
    render_exact_date_limitation_banner(prev_date, curr_date)

    # Sub-sections / views
    sub_views = st.radio(
        "Scanner Perspectives:",
        [
            "🔥 All Stocks / Accumulation Ranking",
            "🧲 Multi-Fund Accumulation (>= N Funds)",
            "🆕 New MF Positions",
            "🚪 MF Exits",
            "🔻 MF Distribution",
        ],
        horizontal=True,
        key="rad_mf_scanner_views"
    )

    # Filters Toolbar
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)
    with f_col1:
        sectors_list = ["All Sectors"] + sorted(list(df["sector"].dropna().unique()))
        selected_sector = st.selectbox("Sector Filter", sectors_list, key="sb_mf_sec")
    with f_col2:
        caps_list = ["All Market Caps"] + sorted(list(df["market_cap"].dropna().unique()))
        selected_cap = st.selectbox("Market Cap Filter", caps_list, key="sb_mf_cap")
    with f_col3:
        search_sym = st.text_input("Filter Ticker / Company", "", key="txt_mf_sym").strip().upper()
    with f_col4:
        min_chg = st.number_input("Min Holding Change (pp)", value=-10.0, step=0.5, key="num_min_chg")

    # Filter base df
    filtered_df = df.copy()
    if selected_sector != "All Sectors":
        filtered_df = filtered_df[filtered_df["sector"] == selected_sector]
    if selected_cap != "All Market Caps":
        filtered_df = filtered_df[filtered_df["market_cap"] == selected_cap]
    if search_sym:
        filtered_df = filtered_df[
            filtered_df["stock"].str.contains(search_sym, na=False) |
            filtered_df["company_name"].str.contains(search_sym, case=False, na=False)
        ]
    if min_chg > -10.0:
        filtered_df = filtered_df[filtered_df["change_pct_points"] >= min_chg]

    # Specific sub-view handling
    if sub_views == "🔥 All Stocks / Accumulation Ranking":
        st.markdown("#### 🔥 Institutional Accumulation Ranking")
        view_df = filtered_df.sort_values(by="accumulation_score", ascending=False).reset_index(drop=True)

    elif sub_views == "🧲 Multi-Fund Accumulation (>= N Funds)":
        st.markdown("#### 🧲 Stocks Being Accumulated by Multiple Mutual Funds")
        c_n1, c_n2 = st.columns([2, 2])
        with c_n1:
            n_option = st.selectbox(
                "Minimum Funds Increasing Exposure (N)",
                [2, 3, 5, 10, 15, 20, "Custom"],
                index=0,
                key="sel_multi_n"
            )
        if n_option == "Custom":
            with c_n2:
                n_val = st.number_input("Enter custom N value", min_value=1, value=4, key="num_custom_n")
        else:
            n_val = int(n_option)

        view_df = filtered_df[filtered_df["funds_increased"] >= n_val].sort_values(
            by=["funds_increased", "change_pct_points"], ascending=[False, False]
        ).reset_index(drop=True)

    elif sub_views == "🆕 New MF Positions":
        st.markdown("#### 🆕 Fresh Mutual Fund Entries (Previous: 0% → Current: > 0%)")
        view_df = filtered_df[filtered_df["new_funds"] > 0].sort_values(
            by=["new_funds", "current_mf_holding"], ascending=[False, False]
        ).reset_index(drop=True)

    elif sub_views == "🚪 MF Exits":
        st.markdown("#### 🚪 Complete Mutual Fund Exits (Previous: > 0% → Current: 0%)")
        view_df = filtered_df[filtered_df["exited_funds"] > 0].sort_values(
            by=["exited_funds", "change_pct_points"], ascending=[False, True]
        ).reset_index(drop=True)

    else:  # 🔻 MF Distribution
        st.markdown("#### 🔻 Mutual Fund Distribution / Exposure Reduction")
        view_df = filtered_df[filtered_df["change_pct_points"] < 0].sort_values(
            by=["funds_reduced", "change_pct_points"], ascending=[False, True]
        ).reset_index(drop=True)

    # Format table for display
    if not view_df.empty:
        st.write(f"Displaying **{len(view_df)}** matching candidate stocks.")

        # Recalculate rank for current view
        view_df["rank"] = range(1, len(view_df) + 1)

        formatted_df = pd.DataFrame({
            "Rank": view_df["rank"],
            "Stock": view_df["stock"],
            "Company": view_df["company_name"],
            "Sector": view_df["sector"],
            "Current MF %": view_df["current_mf_holding"].map("{:.2f}%".format),
            "Previous MF %": view_df["previous_mf_holding"].map("{:.2f}%".format),
            "Change (pp)": view_df["change_pct_points"].map("{:+.2f}".format),
            "Rel Chg %": view_df["relative_change_pct"].map("{:+.1f}%".format),
            "Total Schemes": view_df["total_mf_schemes"],
            "Funds Increased": view_df["funds_increased"],
            "Funds Reduced": view_df["funds_reduced"],
            "New Funds": view_df["new_funds"],
            "Exited Funds": view_df["exited_funds"],
            "Est Value (₹ Cr)": view_df["estimated_holding_value_cr"].apply(lambda v: f"₹{v:,.1f}" if pd.notnull(v) else "N/A"),
            "Accumulation Score": view_df["accumulation_score"].map("{:.1f}".format),
            "Consensus Score": view_df["consensus_score"].map("{:.1f}".format)
        })

        st.dataframe(
            formatted_df,
            column_config={
                "Accumulation Score": st.column_config.ProgressColumn(
                    "Accumulation Score",
                    help=TOOLTIPS["accumulation_score"],
                    format="%.1f",
                    min_value=0,
                    max_value=100
                ),
            },
            use_container_width=True,
            hide_index=True
        )

        export_dataframe_buttons(formatted_df, "mf_scanner_results", key_suffix=sub_views[:3])

    else:
        st.info("No stocks match the chosen scanner conditions and thresholds.")

    render_freshness_badge(
        reporting_date_str=curr_date,
        source="AMFI Official Monthly Portfolio Disclosures"
    )
