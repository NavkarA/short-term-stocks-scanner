"""
Main entry point for Institutional Activity UI module.
Renders header, navigation between the 8 institutional tabs, and initializes data.
"""

import streamlit as st
from institutional.db.repository import InstitutionalRepository
from institutional.data_sources.manager import InstitutionalDataManager

from institutional.ui.overview_tab import render_overview_tab
from institutional.ui.mf_activity_tab import render_mf_activity_tab
from institutional.ui.mf_scanner_tab import render_mf_scanner_tab
from institutional.ui.fund_explorer_tab import render_fund_explorer_tab
from institutional.ui.stock_explorer_tab import render_stock_explorer_tab
from institutional.ui.fii_activity_tab import render_fii_activity_tab
from institutional.ui.consensus_tab import render_consensus_tab
from institutional.ui.history_tab import render_history_tab


def render_institutional_activity_page():
    """Renders the comprehensive 🏦 Institutional Activity module."""

    # Initialize data repository & seed baseline if not yet seeded
    if "inst_data_manager" not in st.session_state:
        manager = InstitutionalDataManager()
        manager.initialize_and_seed()
        st.session_state.inst_data_manager = manager
        st.session_state.inst_repo = manager.repo
    else:
        manager = st.session_state.inst_data_manager
        repo = st.session_state.inst_repo

    # Top Header
    st.markdown('<div class="main-title">🏦 Institutional Activity & Smart Money Flow</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-title">Track Mutual Fund Portfolios, FII/FPI Trends, DII Net Activity, and Institutional Consensus</div>',
        unsafe_allow_html=True
    )

    # 8 Main Tabs (Section 2)
    inst_tabs = st.tabs([
        "1. Overview",
        "2. MF Activity",
        "3. MF Stock Scanner",
        "4. Fund Explorer",
        "5. Stock Explorer",
        "6. FII Activity",
        "7. Institutional Consensus",
        "8. Historical Data"
    ])

    with inst_tabs[0]:
        render_overview_tab(st.session_state.inst_repo)

    with inst_tabs[1]:
        render_mf_activity_tab(st.session_state.inst_repo)

    with inst_tabs[2]:
        render_mf_scanner_tab(st.session_state.inst_repo)

    with inst_tabs[3]:
        render_fund_explorer_tab(st.session_state.inst_repo)

    with inst_tabs[4]:
        render_stock_explorer_tab(st.session_state.inst_repo)

    with inst_tabs[5]:
        render_fii_activity_tab(st.session_state.inst_repo)

    with inst_tabs[6]:
        render_consensus_tab(st.session_state.inst_repo)

    with inst_tabs[7]:
        render_history_tab(st.session_state.inst_repo, manager)
