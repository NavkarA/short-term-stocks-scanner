"""
Tab 1: Institutional Overview Dashboard.
Market-level institutional activity (FII, MF, DII, Total across Today, 5D, 20D, 1M, 3M).
Interactive Plotly daily and cumulative flow charts.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from institutional.db.repository import InstitutionalRepository
from institutional.ui.components import render_freshness_badge, export_dataframe_buttons


def render_overview_tab(repo: InstitutionalRepository):
    st.subheader("🏛️ Market-Level Institutional Flow Summary")
    st.caption("Aggregated institutional equity market flows in ₹ Crores across rolling trading horizons.")

    summary = repo.get_market_overview_summary()

    # Four Metric Summary Cards across timeframes
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        fii_today = summary["FII"]["Today"]
        st.markdown(f"""
        <div style="background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 14px; margin-bottom: 12px;">
            <div style="font-size: 1.05rem; font-weight: 700; color: #64b5f6;">🌍 FII / FPI Net Activity</div>
            <hr style="margin: 8px 0; border-color: #2a2e39;">
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">Today:</span>
                <b style="color: {'#26a69a' if fii_today >= 0 else '#ef5350'};">{'₹+' if fii_today >= 0 else '₹'}{fii_today:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">5 Trading Days:</span>
                <b style="color: {'#26a69a' if summary['FII']['5D'] >= 0 else '#ef5350'};">{'₹+' if summary['FII']['5D'] >= 0 else '₹'}{summary['FII']['5D']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">20 Trading Days:</span>
                <b style="color: {'#26a69a' if summary['FII']['20D'] >= 0 else '#ef5350'};">{'₹+' if summary['FII']['20D'] >= 0 else '₹'}{summary['FII']['20D']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">1 Month:</span>
                <b style="color: {'#26a69a' if summary['FII']['1M'] >= 0 else '#ef5350'};">{'₹+' if summary['FII']['1M'] >= 0 else '₹'}{summary['FII']['1M']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">3 Months:</span>
                <b style="color: {'#26a69a' if summary['FII']['3M'] >= 0 else '#ef5350'};">{'₹+' if summary['FII']['3M'] >= 0 else '₹'}{summary['FII']['3M']:,.1f} Cr</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        mf_today = summary["MF"]["Today"]
        st.markdown(f"""
        <div style="background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 14px; margin-bottom: 12px;">
            <div style="font-size: 1.05rem; font-weight: 700; color: #81c784;">📈 Mutual Funds Net Activity</div>
            <hr style="margin: 8px 0; border-color: #2a2e39;">
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">Today:</span>
                <b style="color: {'#26a69a' if mf_today >= 0 else '#ef5350'};">{'₹+' if mf_today >= 0 else '₹'}{mf_today:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">5 Trading Days:</span>
                <b style="color: {'#26a69a' if summary['MF']['5D'] >= 0 else '#ef5350'};">{'₹+' if summary['MF']['5D'] >= 0 else '₹'}{summary['MF']['5D']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">20 Trading Days:</span>
                <b style="color: {'#26a69a' if summary['MF']['20D'] >= 0 else '#ef5350'};">{'₹+' if summary['MF']['20D'] >= 0 else '₹'}{summary['MF']['20D']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">1 Month:</span>
                <b style="color: {'#26a69a' if summary['MF']['1M'] >= 0 else '#ef5350'};">{'₹+' if summary['MF']['1M'] >= 0 else '₹'}{summary['MF']['1M']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">3 Months:</span>
                <b style="color: {'#26a69a' if summary['MF']['3M'] >= 0 else '#ef5350'};">{'₹+' if summary['MF']['3M'] >= 0 else '₹'}{summary['MF']['3M']:,.1f} Cr</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        dii_today = summary["DII"]["Today"]
        st.markdown(f"""
        <div style="background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 14px; margin-bottom: 12px;">
            <div style="font-size: 1.05rem; font-weight: 700; color: #ffb74d;">🏢 DII Net Activity</div>
            <hr style="margin: 8px 0; border-color: #2a2e39;">
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">Today:</span>
                <b style="color: {'#26a69a' if dii_today >= 0 else '#ef5350'};">{'₹+' if dii_today >= 0 else '₹'}{dii_today:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">5 Trading Days:</span>
                <b style="color: {'#26a69a' if summary['DII']['5D'] >= 0 else '#ef5350'};">{'₹+' if summary['DII']['5D'] >= 0 else '₹'}{summary['DII']['5D']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">20 Trading Days:</span>
                <b style="color: {'#26a69a' if summary['DII']['20D'] >= 0 else '#ef5350'};">{'₹+' if summary['DII']['20D'] >= 0 else '₹'}{summary['DII']['20D']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">1 Month:</span>
                <b style="color: {'#26a69a' if summary['DII']['1M'] >= 0 else '#ef5350'};">{'₹+' if summary['DII']['1M'] >= 0 else '₹'}{summary['DII']['1M']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">3 Months:</span>
                <b style="color: {'#26a69a' if summary['DII']['3M'] >= 0 else '#ef5350'};">{'₹+' if summary['DII']['3M'] >= 0 else '₹'}{summary['DII']['3M']:,.1f} Cr</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        tot_today = summary["Total"]["Today"]
        st.markdown(f"""
        <div style="background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 14px; margin-bottom: 12px;">
            <div style="font-size: 1.05rem; font-weight: 700; color: #ba68c8;">⚖️ Total Institutional Activity</div>
            <hr style="margin: 8px 0; border-color: #2a2e39;">
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">Today:</span>
                <b style="color: {'#26a69a' if tot_today >= 0 else '#ef5350'};">{'₹+' if tot_today >= 0 else '₹'}{tot_today:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">5 Trading Days:</span>
                <b style="color: {'#26a69a' if summary['Total']['5D'] >= 0 else '#ef5350'};">{'₹+' if summary['Total']['5D'] >= 0 else '₹'}{summary['Total']['5D']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">20 Trading Days:</span>
                <b style="color: {'#26a69a' if summary['Total']['20D'] >= 0 else '#ef5350'};">{'₹+' if summary['Total']['20D'] >= 0 else '₹'}{summary['Total']['20D']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">1 Month:</span>
                <b style="color: {'#26a69a' if summary['Total']['1M'] >= 0 else '#ef5350'};">{'₹+' if summary['Total']['1M'] >= 0 else '₹'}{summary['Total']['1M']:,.1f} Cr</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.95rem;">
                <span style="color: #999;">3 Months:</span>
                <b style="color: {'#26a69a' if summary['Total']['3M'] >= 0 else '#ef5350'};">{'₹+' if summary['Total']['3M'] >= 0 else '₹'}{summary['Total']['3M']:,.1f} Cr</b>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Interactive Trend Charts
    st.subheader("📊 Institutional Net Flow Trends (Daily & Cumulative)")

    daily_df = repo.get_daily_activity_df(days_limit=60)
    if not daily_df.empty:
        # Pivot table for plotting
        piv = daily_df.pivot(index="activity_date", columns="institution_type", values="net_activity").fillna(0.0)

        fig = go.Figure()
        if "FII" in piv.columns:
            fig.add_trace(go.Bar(
                x=piv.index, y=piv["FII"], name="FII Net",
                marker_color="#64b5f6", opacity=0.85
            ))
        if "DII" in piv.columns:
            fig.add_trace(go.Bar(
                x=piv.index, y=piv["DII"], name="DII Net",
                marker_color="#ffb74d", opacity=0.85
            ))
        if "MF" in piv.columns:
            fig.add_trace(go.Bar(
                x=piv.index, y=piv["MF"], name="Mutual Funds Net",
                marker_color="#81c784", opacity=0.85
            ))

        fig.update_layout(
            barmode="group",
            title="Daily Net Institutional Investment (₹ Crores)",
            xaxis_title="Date",
            yaxis_title="Net Investment (₹ Cr)",
            template="plotly_dark",
            height=420,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        # Cumulative Flow Chart
        cum_piv = piv.cumsum()
        fig_cum = go.Figure()
        for col, col_color in [("FII", "#64b5f6"), ("DII", "#ffb74d"), ("MF", "#81c784")]:
            if col in cum_piv.columns:
                fig_cum.add_trace(go.Scatter(
                    x=cum_piv.index, y=cum_piv[col], name=f"Cumulative {col}",
                    mode="lines+markers", line=dict(width=2.5, color=col_color)
                ))

        fig_cum.update_layout(
            title="Cumulative Institutional Flow (₹ Crores, Last 60 Trading Days)",
            xaxis_title="Date",
            yaxis_title="Cumulative Net (₹ Cr)",
            template="plotly_dark",
            height=380,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_cum, use_container_width=True)

    render_freshness_badge(
        reporting_date_str=daily_df["activity_date"].max().strftime("%Y-%m-%d") if not daily_df.empty else "N/A",
        source="NSE / SEBI Official Trading Disclosures"
    )
