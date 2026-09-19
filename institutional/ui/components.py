"""
Reusable UI components, formatters, tooltips, badges, and export helpers.
"""

import io
from datetime import datetime
from typing import Optional, Any
import pandas as pd
import streamlit as st


# ==========================================
# TOOLTIPS & FINANCIAL DEFINITIONS (Section 46)
# ==========================================
TOOLTIPS = {
    "holding_pct": "Percentage of the company's total outstanding equity shares held by the mutual fund / institutional entity.",
    "portfolio_weight": "Percentage of the mutual fund's total portfolio assets allocated to this specific stock.",
    "holding_change": "Difference in percentage points between the current and previous reported disclosure dates.",
    "relative_change": "Relative percentage expansion or contraction in exposure compared to previous reporting date.",
    "new_position": "New Entry: The fund had no reported holding (0%) in the previous disclosure and has entered (>0%) in the current disclosure.",
    "exit_position": "Complete Exit: The fund held shares in the previous disclosure and reports 0% holding in the current disclosure.",
    "accumulation_score": "Descriptive institutional accumulation metric (0-100) based on fund additions, new entries, and percentage point increases.",
    "institutional_consensus": "Descriptive measure of whether tracked mutual funds and institutional investors are collectively expanding or reducing exposure.",
    "exact_date_warning": "Mutual fund portfolio data is published as of monthly disclosure dates. Individual intraday transaction dates are not manufactured.",
}


def render_metric_card(title: str, value_str: str, subtitle: Optional[str] = None, delta_color: str = "normal"):
    """Renders a styled financial terminal metric card."""
    color_style = ""
    if delta_color == "green":
        color_style = "color: #26a69a;"
    elif delta_color == "red":
        color_style = "color: #ef5350;"

    sub_html = f'<div style="font-size: 0.8rem; color: #888;">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div style="background: #1e222d; border: 1px solid #2a2e39; border-radius: 8px; padding: 12px; margin-bottom: 8px;">
        <div style="font-size: 0.85rem; color: #a0a5b5; font-weight: 600;">{title}</div>
        <div style="font-size: 1.4rem; font-weight: 800; {color_style} margin: 4px 0;">{value_str}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


def render_freshness_badge(reporting_date_str: str, source: str, retrieved_at: Optional[str] = None):
    """
    Renders official data transparency and freshness badge (Section 44).
    Green: <= 45 days (standard monthly disclosure cycle).
    Yellow: 46 - 90 days.
    Red: > 90 days.
    """
    badge_color = "🟢 Fresh"
    try:
        r_dt = datetime.strptime(reporting_date_str, "%Y-%m-%d")
        days_ago = (datetime.now() - r_dt).days
        if days_ago > 90:
            badge_color = "🔴 Stale"
        elif days_ago > 45:
            badge_color = "🟡 Delayed"
        else:
            badge_color = "🟢 Fresh"
    except Exception:
        badge_color = "🟢 Active"

    ret_info = f" | Retrieved: `{retrieved_at[:16]}`" if retrieved_at else ""

    st.caption(
        f"**Data Transparency**: Source: **{source}** | Reporting Date: `{reporting_date_str}` | "
        f"Status: **{badge_color}**{ret_info}"
    )


def render_exact_date_limitation_banner(prev_date: str, curr_date: str):
    """
    Renders compliance notice adhering strictly to Section 10:
    Distinguishes Disclosure Date from Transaction Date.
    """
    st.info(
        f"ℹ️ **Disclosure Date Notice**: Mutual fund portfolio disclosures reflect holdings between "
        f"**{prev_date}** and **{curr_date}**. "
        f"Per SEBI/AMFI regulatory guidelines, holding changes represent net accumulation over this reporting window. "
        f"Intraday transaction dates are not inferred."
    )


def export_dataframe_buttons(df: pd.DataFrame, filename_prefix: str, key_suffix: str = ""):
    """Provides CSV and Excel download buttons for tables."""
    if df.empty:
        return

    c1, c2 = st.columns([1, 1])
    # 1. CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    with c1:
        st.download_button(
            label="📥 Export CSV",
            data=csv_bytes,
            file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            key=f"dl_csv_{filename_prefix}_{key_suffix}",
            use_container_width=True
        )

    # 2. Excel
    try:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="InstitutionalData")
        excel_bytes = buffer.getvalue()
        with c2:
            st.download_button(
                label="📊 Export Excel",
                data=excel_bytes,
                file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_xlsx_{filename_prefix}_{key_suffix}",
                use_container_width=True
            )
    except Exception:
        pass
