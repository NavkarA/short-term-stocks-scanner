"""
Tab 5: Stock-Level Institutional Explorer.
Provides detailed mutual fund and FII breakdown for any selected Indian stock.
Shows fund-by-fund breakdown, status badges, shares change, portfolio weights,
and interactive historical ownership charts with exact-date compliance.
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


def render_stock_explorer_tab(repo: InstitutionalRepository):
    st.subheader("🔬 Stock Institutional Ownership & Fund Breakdown")
    st.caption(
        "Inspect company-level institutional ownership, fund-by-fund share allocations, "
        "and multi-period holding trends for Indian equities."
    )

    # Stock search input
    conn = repo._get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT stock_symbol, company_name FROM stock_metadata ORDER BY stock_symbol ASC")
        available_stocks = [f"{r['stock_symbol']} — {r['company_name']}" for r in cur.fetchall()]
    finally:
        conn.close()

    if not available_stocks:
        available_stocks = ["BHEL — Bharat Heavy Electricals Ltd.", "BEL — Bharat Electronics Ltd."]

    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        chosen_option = st.selectbox(
            "Search Stock Ticker / Company",
            available_stocks,
            index=0,
            key="sb_stock_explorer_choice"
        )
        selected_ticker = chosen_option.split(" — ")[0].strip().upper()

    # Fetch breakdown and summary
    breakdown_df, summary = repo.get_stock_mf_breakdown(selected_ticker)

    # Header & Metric Cards
    st.markdown(f"### {summary['company_name']} (`{selected_ticker}`)")
    st.caption(f"**Sector**: {summary['sector']} | **ISIN**: `{summary['isin']}`")

    # Ownership Metric Summary
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        mf_curr = summary["current_mf_holding"]
        mf_chg = summary["mf_change_pp"]
        st.metric("Total Mutual Fund Holding", f"{mf_curr:.2f}%", f"{mf_chg:+.2f} pp")
    with c2:
        fii_curr = summary["current_fii_holding"]
        fii_chg = summary["fii_change_pp"]
        st.metric("FII / FPI Holding", f"{fii_curr:.2f}%", f"{fii_chg:+.2f} pp")
    with c3:
        st.metric("Total MF Schemes Holding", summary["total_funds"])
    with c4:
        st.metric("Latest Disclosure Date", summary["current_disclosure_date"])

    # Strict compliance banner for exact date limitation (Section 10)
    render_exact_date_limitation_banner(summary["previous_disclosure_date"], summary["current_disclosure_date"])

    st.markdown("---")

    # Fund Breakdown Table
    st.subheader(f"📊 Mutual Funds Holding {selected_ticker}")
    st.caption(
        "Note: **Holding %** is the scheme's share of company equity; **Portfolio Weight %** is the stock's weight inside the fund's portfolio."
    )

    if not breakdown_df.empty:
        # Format columns for display
        display_df = pd.DataFrame({
            "Mutual Fund Scheme": breakdown_df["fund_name"],
            "AMC": breakdown_df["amc_name"],
            "Status": breakdown_df["status"],
            "Current Holding %": breakdown_df["current_holding_percent"].map("{:.2f}%".format),
            "Previous Holding %": breakdown_df["previous_holding_percent"].map("{:.2f}%".format),
            "Change (pp)": breakdown_df["change_holding_pct_points"].map("{:+.2f}".format),
            "Portfolio Weight %": breakdown_df["portfolio_weight"].apply(lambda v: f"{v:.2f}%" if pd.notnull(v) else "N/A"),
            "Market Value (₹ Cr)": breakdown_df["market_value_cr"].apply(lambda v: f"₹{v:,.1f}" if pd.notnull(v) else "N/A"),
            "Current Shares": breakdown_df["current_shares"].apply(lambda v: f"{v:,.0f}" if pd.notnull(v) else "N/A"),
            "Previous Shares": breakdown_df["previous_shares"].apply(lambda v: f"{v:,.0f}" if pd.notnull(v) else "N/A"),
            "Change in Shares": breakdown_df["change_in_shares"].apply(lambda v: f"{v:+,.0f}" if pd.notnull(v) else "N/A"),
            "Disclosure Period": breakdown_df.apply(
                lambda r: f"{r['previous_disclosure_date']} → {r['current_disclosure_date']}", axis=1
            ),
            "Source": breakdown_df["source"]
        })

        st.dataframe(
            display_df,
            column_config={
                "Status": st.column_config.TextColumn("Status"),
                "Current Holding %": st.column_config.TextColumn("Holding % (Company)", help=TOOLTIPS["holding_pct"]),
                "Portfolio Weight %": st.column_config.TextColumn("Portfolio Weight % (Fund)", help=TOOLTIPS["portfolio_weight"]),
            },
            use_container_width=True,
            hide_index=True
        )

        export_dataframe_buttons(display_df, f"{selected_ticker}_mf_breakdown")
    else:
        st.info(f"No mutual funds currently report holding {selected_ticker}.")

    st.markdown("---")

    # Interactive Historical Ownership Chart
    st.subheader(f"📈 Historical Institutional Ownership — {selected_ticker}")
    hist_df = repo.get_stock_historical_ownership(selected_ticker)

    if not hist_df.empty:
        fig = go.Figure()
        if "mf_holding_pct" in hist_df.columns:
            fig.add_trace(go.Scatter(
                x=hist_df["reporting_date"],
                y=hist_df["mf_holding_pct"],
                name="Mutual Fund Ownership %",
                mode="lines+markers",
                line=dict(color="#81c784", width=3),
                marker=dict(size=8)
            ))
        if "fii_holding_pct" in hist_df.columns:
            fig.add_trace(go.Scatter(
                x=hist_df["reporting_date"],
                y=hist_df["fii_holding_pct"],
                name="FII / FPI Ownership %",
                mode="lines+markers",
                line=dict(color="#64b5f6", width=3),
                marker=dict(size=8)
            ))

        fig.update_layout(
            title=f"Institutional Holding Trend for {selected_ticker} (Reporting Dates)",
            xaxis_title="Reporting Disclosure Date",
            yaxis_title="Total Equity Ownership (%)",
            template="plotly_dark",
            height=380,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

    render_freshness_badge(
        reporting_date_str=summary["current_disclosure_date"],
        source="AMFI Disclosures & NSE Shareholding Patterns"
    )
