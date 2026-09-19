"""
Tab 4: Mutual Fund Scheme Explorer.
Enables deep-dive analysis into specific mutual fund schemes:
AUM, equity allocation, new entries, increased/reduced/exited positions,
and historical holding trajectories for individual stocks within the fund.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from institutional.db.repository import InstitutionalRepository
from institutional.ui.components import (
    render_freshness_badge,
    render_exact_date_limitation_banner,
    export_dataframe_buttons,
    TOOLTIPS,
)


def render_fund_explorer_tab(repo: InstitutionalRepository):
    st.subheader("🏛️ Mutual Fund Scheme Explorer")
    st.caption("Inspect individual fund portfolios, equity allocation, fresh positions, and historical stock weights.")

    funds = repo.get_all_funds_list()
    if not funds:
        st.info("No mutual funds found in the database. Please initialize or update institutional data.")
        return

    # Fund selector
    fund_options = {f"{f['fund_name']} ({f['amc_name']})": f["fund_id"] for f in funds}
    selected_label = st.selectbox(
        "🔍 Search & Select Mutual Fund Scheme",
        list(fund_options.keys()),
        index=0,
        key="sb_selected_fund"
    )
    selected_fund_id = fund_options[selected_label]

    # Fetch fund summary and positions
    summary, positions = repo.get_fund_summary_and_positions(selected_fund_id)

    if not summary:
        st.warning(f"No portfolio records found for fund ID: {selected_fund_id}")
        return

    # Fund Header & KPI Cards
    st.markdown(f"### {summary['fund_name']}")
    st.caption(f"**AMC**: {summary['amc_name']} | **Reporting Date**: `{summary['latest_disclosure']}`")

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Estimated Equity AUM", f"₹{summary['aum_cr']:,.1f} Cr")
    with k2:
        st.metric("Total Equity Holdings", summary["number_of_holdings"])
    with k3:
        st.metric("Equity Allocation", f"{summary['equity_allocation_pct']:.1f}%")
    with k4:
        st.metric("Latest Disclosure", summary["latest_disclosure"])

    render_exact_date_limitation_banner(summary["previous_disclosure"], summary["latest_disclosure"])

    st.markdown("---")

    # 4 Position Sub-Tabs
    f_tabs = st.tabs([
        f"🆕 New Positions ({len(positions['new'])})",
        f"📈 Increased Positions ({len(positions['increased'])})",
        f"📉 Reduced Positions ({len(positions['reduced'])})",
        f"🚪 Exited Positions ({len(positions['exited'])})",
        "📊 Stock Trajectory in Fund"
    ])

    with f_tabs[0]:
        st.markdown("#### 🆕 New Stocks Added to Fund Portfolio")
        if not positions["new"].empty:
            st.dataframe(positions["new"], use_container_width=True, hide_index=True)
            export_dataframe_buttons(positions["new"], f"{selected_fund_id}_new_positions")
        else:
            st.info("No brand new positions reported in this disclosure period.")

    with f_tabs[1]:
        st.markdown("#### 📈 Stocks Where Fund Increased Exposure")
        if not positions["increased"].empty:
            st.dataframe(positions["increased"], use_container_width=True, hide_index=True)
            export_dataframe_buttons(positions["increased"], f"{selected_fund_id}_increased_positions")
        else:
            st.info("No increased positions reported in this disclosure period.")

    with f_tabs[2]:
        st.markdown("#### 📉 Stocks Where Fund Reduced Exposure")
        if not positions["reduced"].empty:
            st.dataframe(positions["reduced"], use_container_width=True, hide_index=True)
            export_dataframe_buttons(positions["reduced"], f"{selected_fund_id}_reduced_positions")
        else:
            st.info("No reduced positions reported in this disclosure period.")

    with f_tabs[3]:
        st.markdown("#### 🚪 Stocks Completely Exited by Fund")
        if not positions["exited"].empty:
            st.dataframe(positions["exited"], use_container_width=True, hide_index=True)
            export_dataframe_buttons(positions["exited"], f"{selected_fund_id}_exited_positions")
        else:
            st.info("No exited positions reported in this disclosure period.")

    with f_tabs[4]:
        st.markdown("#### 📊 Historical Stock Weight Trajectory Within Fund")
        # Combine all stocks in fund
        all_stocks = []
        for key in ["new", "increased", "reduced"]:
            if not positions[key].empty and "Stock" in positions[key].columns:
                all_stocks.extend(positions[key]["Stock"].tolist())
        all_stocks = sorted(list(set(all_stocks)))

        if all_stocks:
            stock_pick = st.selectbox("Select Stock to Inspect Historical Trend", all_stocks, key="sb_fund_stock_pick")
            hist_df = repo.get_fund_stock_history(selected_fund_id, stock_pick)

            if not hist_df.empty:
                st.write(f"Historical holding trajectory of **{stock_pick}** in **{summary['fund_name']}**:")

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=hist_df["reporting_date"],
                    y=hist_df["holding_percent"],
                    name="Holding in Company (%)",
                    mode="lines+markers",
                    line=dict(color="#26a69a", width=2.5),
                    marker=dict(size=8)
                ))
                if "portfolio_weight" in hist_df.columns and hist_df["portfolio_weight"].notnull().any():
                    fig.add_trace(go.Scatter(
                        x=hist_df["reporting_date"],
                        y=hist_df["portfolio_weight"],
                        name="Fund Portfolio Weight (%)",
                        mode="lines+markers",
                        line=dict(color="#64b5f6", width=2, dash="dot"),
                        marker=dict(size=7)
                    ))

                fig.update_layout(
                    title=f"{stock_pick} Allocation in {summary['fund_name']}",
                    xaxis_title="Reporting Disclosure Date",
                    yaxis_title="Percentage (%)",
                    template="plotly_dark",
                    height=380,
                    hovermode="x unified"
                )
                st.plotly_chart(fig, use_container_width=True)

                st.dataframe(hist_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"No historical records found for {stock_pick} in this fund.")
        else:
            st.info("No stocks available to chart.")

    render_freshness_badge(
        reporting_date_str=summary["latest_disclosure"],
        source="AMFI Scheme Portfolio Disclosures"
    )
