"""
Tab 6: FII / FPI Activity Dashboard & Stock Ownership Tracker.
Monitors Foreign Institutional Investor gross purchases, gross sales,
cumulative flows, and equity-level shareholding percentages from official NSE reports.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from institutional.db.repository import InstitutionalRepository
from institutional.ui.components import render_freshness_badge, export_dataframe_buttons


def render_fii_activity_tab(repo: InstitutionalRepository):
    st.subheader("🌍 FII / FPI Investment Activity & Equity Holdings")
    st.caption("Daily foreign institutional equity trading flows (Source: NSE) and quarterly FII shareholding patterns.")

    # Timeframe selection
    tf_col1, tf_col2 = st.columns([2, 2])
    with tf_col1:
        timeframe = st.selectbox(
            "Select Time Horizon",
            ["7 Days", "30 Days", "3 Months", "6 Months", "1 Year"],
            index=1,
            key="sel_fii_activity_tf"
        )

    days_map = {"7 Days": 7, "30 Days": 30, "3 Months": 90, "6 Months": 180, "1 Year": 365}
    days_limit = days_map.get(timeframe, 30)

    # Fetch daily FII data
    df = repo.get_daily_activity_df(institution_type="FII", days_limit=days_limit)

    if df.empty:
        st.info("No FII activity data available for the selected period.")
        return

    df_window = df.tail(days_limit).copy()

    # KPI Summary Row
    tot_net = df_window["net_activity"].sum()
    tot_buy = df_window["gross_buy"].sum()
    tot_sell = df_window["gross_sell"].sum()
    avg_net = df_window["net_activity"].mean()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total FII Net Flow", f"₹{tot_net:+,.1f} Cr", delta=f"{len(df_window)} sessions")
    with m2:
        st.metric("Gross Purchases", f"₹{tot_buy:,.1f} Cr")
    with m3:
        st.metric("Gross Sales", f"₹{tot_sell:,.1f} Cr")
    with m4:
        st.metric("Avg Daily Net Flow", f"₹{avg_net:+,.1f} Cr")

    st.markdown("---")

    # Interactive Bar Chart: Daily Net FII Flow
    colors = ["#26a69a" if val >= 0 else "#ef5350" for val in df_window["net_activity"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_window["activity_date"],
        y=df_window["net_activity"],
        name="Net FII Activity (₹ Cr)",
        marker_color=colors,
        opacity=0.85
    ))
    fig.update_layout(
        title=f"Daily Net FII / FPI Flow — {timeframe} (₹ Crores)",
        xaxis_title="Date",
        yaxis_title="Net Investment (₹ Cr)",
        template="plotly_dark",
        height=380,
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

    # Cumulative FII Flow Chart
    cum_flow = df_window["net_activity"].cumsum()
    fig_cum = go.Figure()
    fig_cum.add_trace(go.Scatter(
        x=df_window["activity_date"],
        y=cum_flow,
        name="Cumulative Net Flow",
        mode="lines+markers",
        line=dict(color="#64b5f6", width=2.5)
    ))
    fig_cum.update_layout(
        title="Cumulative FII / FPI Equity Flow (₹ Crores)",
        xaxis_title="Date",
        yaxis_title="Cumulative Net (₹ Cr)",
        template="plotly_dark",
        height=350,
        hovermode="x unified"
    )
    st.plotly_chart(fig_cum, use_container_width=True)

    st.markdown("---")

    # FII Stock Ownership Section (Section 15)
    st.subheader("📋 Stock-Level FII Ownership & Disclosures")
    st.caption("FII equity ownership percentages reported in regulatory shareholding disclosures.")

    conn = repo._get_conn()
    try:
        fii_holdings_df = pd.read_sql_query("""
        SELECT f.stock_symbol, s.company_name, s.sector, f.reporting_date, f.holding_percent, f.source
        FROM fii_holdings_history f
        LEFT JOIN stock_metadata s ON f.stock_symbol = s.stock_symbol
        ORDER BY f.stock_symbol ASC, f.reporting_date DESC
        """, conn)
    finally:
        conn.close()

    if not fii_holdings_df.empty:
        # Group by stock to find current and previous
        stock_groups = fii_holdings_df.groupby("stock_symbol")
        fii_records = []
        for sym, grp in stock_groups:
            c_row = grp.iloc[0]
            p_row = grp.iloc[1] if len(grp) > 1 else None

            c_pct = c_row["holding_percent"]
            p_pct = p_row["holding_percent"] if p_row is not None else 0.0
            chg = round(c_pct - p_pct, 2)

            fii_records.append({
                "Stock": sym,
                "Company Name": c_row["company_name"] or sym,
                "Sector": c_row["sector"] or "Diversified",
                "Current FII %": f"{c_pct:.2f}%",
                "Previous FII %": f"{p_pct:.2f}%",
                "Change (pp)": f"{chg:+.2f}",
                "Latest Disclosure": c_row["reporting_date"],
                "Source": c_row["source"]
            })

        fii_table = pd.DataFrame(fii_records).sort_values(by="Stock").reset_index(drop=True)
        st.dataframe(fii_table, use_container_width=True, hide_index=True)
        export_dataframe_buttons(fii_table, "fii_stock_ownership")
    else:
        st.info("No stock-level FII holdings recorded yet.")

    render_freshness_badge(
        reporting_date_str=df_window["activity_date"].max().strftime("%Y-%m-%d"),
        source="NSE Official FII Disclosures"
    )
