"""
Tab 2: Mutual Fund Daily Activity Dashboard.
Tracks daily MF gross purchases, gross sales, and net investment in ₹ Cr.
Supports 7D, 30D, 3M, 6M, and 1Y filtering, Plotly bar/line charts, and CSV/Excel export.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from institutional.db.repository import InstitutionalRepository
from institutional.ui.components import render_freshness_badge, export_dataframe_buttons


def render_mf_activity_tab(repo: InstitutionalRepository):
    st.subheader("📈 Mutual Fund Daily Investment Activity")
    st.caption("Daily gross equity purchases, gross sales, and net investments by Indian Mutual Funds (Source: SEBI / AMFI).")

    # Timeframe selection
    tf_col1, tf_col2 = st.columns([2, 2])
    with tf_col1:
        timeframe = st.selectbox(
            "Select Time Horizon",
            ["7 Days", "30 Days", "3 Months", "6 Months", "1 Year"],
            index=1,
            key="sel_mf_activity_tf"
        )

    days_map = {
        "7 Days": 7,
        "30 Days": 30,
        "3 Months": 90,
        "6 Months": 180,
        "1 Year": 365
    }
    days_limit = days_map.get(timeframe, 30)

    # Fetch daily data
    df = repo.get_daily_activity_df(institution_type="MF", days_limit=days_limit)

    if df.empty:
        st.info("No Mutual Fund activity data available for the selected period.")
        return

    # Filter to requested window
    df_window = df.tail(days_limit).copy()

    # KPI Summary Row
    tot_net = df_window["net_activity"].sum()
    tot_buy = df_window["gross_buy"].sum()
    tot_sell = df_window["gross_sell"].sum()
    avg_net = df_window["net_activity"].mean()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Net MF Flow", f"₹{tot_net:+,.1f} Cr", delta=f"{len(df_window)} sessions")
    with m2:
        st.metric("Gross Purchases", f"₹{tot_buy:,.1f} Cr")
    with m3:
        st.metric("Gross Sales", f"₹{tot_sell:,.1f} Cr")
    with m4:
        st.metric("Avg Daily Net Flow", f"₹{avg_net:+,.1f} Cr")

    st.markdown("---")

    # Interactive Bar / Line Chart
    colors = ["#26a69a" if val >= 0 else "#ef5350" for val in df_window["net_activity"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_window["activity_date"],
        y=df_window["net_activity"],
        name="Net Investment (₹ Cr)",
        marker_color=colors,
        opacity=0.85
    ))

    fig.update_layout(
        title=f"Mutual Fund Daily Net Investment — {timeframe} (₹ Crores)",
        xaxis_title="Date",
        yaxis_title="Net Investment (₹ Cr)",
        template="plotly_dark",
        height=400,
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

    # Gross Purchases vs Gross Sales Chart
    fig_gross = go.Figure()
    fig_gross.add_trace(go.Scatter(
        x=df_window["activity_date"], y=df_window["gross_buy"],
        name="Gross Purchases", mode="lines+markers", line=dict(color="#64b5f6", width=2)
    ))
    fig_gross.add_trace(go.Scatter(
        x=df_window["activity_date"], y=df_window["gross_sell"],
        name="Gross Sales", mode="lines+markers", line=dict(color="#ffb74d", width=2)
    ))
    fig_gross.update_layout(
        title="Gross Purchases vs Gross Sales (₹ Crores)",
        xaxis_title="Date",
        yaxis_title="Gross Value (₹ Cr)",
        template="plotly_dark",
        height=360,
        hovermode="x unified"
    )
    st.plotly_chart(fig_gross, use_container_width=True)

    st.markdown("---")

    # Data Table
    st.subheader("📋 Daily MF Flow Records")
    display_table = pd.DataFrame({
        "Date": df_window["activity_date"].dt.strftime("%Y-%m-%d"),
        "Gross Purchases (₹ Cr)": df_window["gross_buy"].map("₹{:,.2f}".format),
        "Gross Sales (₹ Cr)": df_window["gross_sell"].map("₹{:,.2f}".format),
        "Net Investment (₹ Cr)": df_window["net_activity"].map("₹{:,.2f}".format),
        "Source": df_window["source"]
    }).sort_values(by="Date", ascending=False).reset_index(drop=True)

    st.dataframe(display_table, use_container_width=True, hide_index=True)

    export_dataframe_buttons(display_table, "mf_daily_activity")

    render_freshness_badge(
        reporting_date_str=df_window["activity_date"].max().strftime("%Y-%m-%d"),
        source="SEBI / AMFI Official Daily Statistics"
    )
