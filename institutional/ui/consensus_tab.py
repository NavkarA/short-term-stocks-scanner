"""
Tab 7: Institutional Consensus & Sector Activity Heatmap.
Synthesizes Mutual Fund, FII, and DII behavior into a descriptive consensus matrix.
Includes sector-level institutional analysis and interactive heatmaps.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from institutional.db.repository import InstitutionalRepository
from institutional.calculations.scoring import calculate_institutional_consensus
from institutional.ui.components import render_freshness_badge, export_dataframe_buttons, TOOLTIPS


def render_consensus_tab(repo: InstitutionalRepository):
    st.subheader("🧠 Institutional Consensus & Sector Flow Analysis")
    st.caption(
        "Multi-institutional consensus synthesizing Mutual Fund, FII, and DII accumulation patterns. "
        "Descriptive diagnostic tool — not financial advice."
    )

    # 1. Stock-Level Institutional Consensus
    st.markdown("#### 🎯 Institutional Consensus by Equity")

    mf_summary_df = repo.get_all_stocks_mf_summary()
    if mf_summary_df.empty:
        st.info("No data available to calculate institutional consensus.")
        return

    # Fetch FII holdings diff
    conn = repo._get_conn()
    try:
        fii_df = pd.read_sql_query("""
        SELECT stock_symbol, reporting_date, holding_percent FROM fii_holdings_history
        ORDER BY stock_symbol ASC, reporting_date DESC
        """, conn)
    finally:
        conn.close()

    fii_diff_map = {}
    if not fii_df.empty:
        for sym, grp in fii_df.groupby("stock_symbol"):
            c_pct = grp.iloc[0]["holding_percent"]
            p_pct = grp.iloc[1]["holding_percent"] if len(grp) > 1 else 0.0
            fii_diff_map[sym] = round(c_pct - p_pct, 2)

    consensus_records = []
    for _, row in mf_summary_df.iterrows():
        sym = row["stock"]
        mf_chg = row["change_pct_points"]
        fii_chg = fii_diff_map.get(sym, 0.0)
        buyers = row["funds_increased"] + row["new_funds"]
        sellers = row["funds_reduced"] + row["exited_funds"]

        cons = calculate_institutional_consensus(
            mf_holding_change_pp=mf_chg,
            fii_holding_change_pp=fii_chg,
            num_mf_buyers=buyers,
            num_mf_sellers=sellers
        )

        consensus_records.append({
            "Stock": sym,
            "Company": row["company_name"],
            "Sector": row["sector"],
            "MF Trend": cons["mf_trend"],
            "FII Trend": cons["fii_trend"],
            "DII Trend": cons["dii_trend"],
            "MF Chg (pp)": f"{mf_chg:+.2f}",
            "FII Chg (pp)": f"{fii_chg:+.2f}",
            "MF Buyers": buyers,
            "MF Sellers": sellers,
            "Institutional Trend": cons["overall_trend"],
            "Composite Score": cons["composite_score"],
            "raw_mf_chg": mf_chg
        })

    cons_df = pd.DataFrame(consensus_records).sort_values(by="Composite Score", ascending=False).reset_index(drop=True)

    # Display Table
    st.dataframe(
        cons_df.drop(columns=["Composite Score", "raw_mf_chg"]),
        column_config={
            "Institutional Trend": st.column_config.TextColumn(
                "Institutional Trend",
                help=TOOLTIPS["institutional_consensus"]
            )
        },
        use_container_width=True,
        hide_index=True
    )
    export_dataframe_buttons(cons_df, "institutional_consensus")

    st.markdown("---")

    # 2. Sector-Level Institutional Activity (Section 40 & 41)
    st.subheader("🏢 Institutional Activity by Sector")
    sector_df = repo.get_sector_institutional_analysis()

    if not sector_df.empty:
        col_sec_tbl, col_sec_chart = st.columns([1, 1])

        with col_sec_tbl:
            st.markdown("##### Sector Accumulation Table")
            st.dataframe(sector_df, use_container_width=True, hide_index=True)
            export_dataframe_buttons(sector_df, "sector_institutional_activity")

        with col_sec_chart:
            st.markdown("##### Sector Net MF Change (Percentage Points)")
            sec_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in sector_df["Net MF Change (pp)"]]
            fig_sec = go.Figure(go.Bar(
                x=sector_df["Net MF Change (pp)"],
                y=sector_df["Sector"],
                orientation="h",
                marker_color=sec_colors
            ))
            fig_sec.update_layout(
                xaxis_title="Net MF Holding Change (pp)",
                yaxis=dict(autorange="reversed"),
                template="plotly_dark",
                height=340,
                margin=dict(l=10, r=10, t=20, b=20)
            )
            st.plotly_chart(fig_sec, use_container_width=True)

        # Interactive Heatmap (Section 41)
        st.markdown("---")
        st.subheader("🗺️ Institutional Sector Heatmap")
        st.caption("Visual distribution of institutional accumulation intensity across market sectors.")

        # Aggregate metrics for heatmap
        heat_data = []
        for _, r in sector_df.iterrows():
            heat_data.append({
                "Sector": r["Sector"],
                "Net MF Exposure": r["Net MF Change (pp)"],
                "Stocks Accumulated": r["Stocks Accumulated"],
                "Stocks Distributed": r["Stocks Distributed"]
            })
        heat_df = pd.DataFrame(heat_data).set_index("Sector")

        fig_heat = px.imshow(
            heat_df[["Net MF Exposure", "Stocks Accumulated", "Stocks Distributed"]],
            labels=dict(x="Institutional Metric", y="Sector", color="Value"),
            x=["Net MF Exposure (pp)", "Stocks Accumulated", "Stocks Distributed"],
            y=heat_df.index,
            color_continuous_scale="Viridis",
            template="plotly_dark",
            aspect="auto"
        )
        fig_heat.update_layout(height=380)
        st.plotly_chart(fig_heat, use_container_width=True)

    render_freshness_badge(
        reporting_date_str=mf_summary_df["current_disclosure_date"].iloc[0],
        source="SEBI / AMFI Disclosures & NSE Filings"
    )
