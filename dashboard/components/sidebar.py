"""
Shared sidebar component for the NYC Neighborhood Pulse dashboard.

Renders filter controls (borough, date range, zip code) that are
consistent across all pages. Returns a dict of selected filter values.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_boroughs, get_year_months, get_zip_codes


def render_sidebar() -> Dict[str, Optional[str]]:
    """
    Renders the shared sidebar and returns current filter selections.

    Returns
    -------
    dict with keys:
        borough : str or None
        year_month : str or None
        zip_code : str or None
    """
    with st.sidebar:
        st.markdown(
            "<h2 style='margin-bottom: 0; color: #0f172a; font-size: 1.15rem;'>"
            "NYC Neighborhood Pulse"
            "</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color: #475569; font-size: 0.8rem; margin-top: 0;'>"
            "Cross-domain urban analytics"
            "</p>",
            unsafe_allow_html=True,
        )

        st.divider()

        # Borough filter
        boroughs = get_boroughs()
        borough_options = ["All Boroughs"] + boroughs
        selected_borough_label = st.selectbox(
            "Borough",
            borough_options,
            index=0,
            key="sidebar_borough",
        )
        selected_borough = (
            None if selected_borough_label == "All Boroughs" else selected_borough_label
        )

        # Month filter
        year_months = get_year_months()
        if year_months:
            selected_year_month = st.selectbox(
                "Month",
                year_months,
                index=0,
                key="sidebar_year_month",
            )
        else:
            selected_year_month = None
            st.caption("No data loaded")

        # Zip code filter
        zip_codes = get_zip_codes(selected_borough)
        zip_options = ["All ZIP Codes"] + zip_codes
        selected_zip_label = st.selectbox(
            "ZIP Code",
            zip_options,
            index=0,
            key="sidebar_zip",
        )
        selected_zip = (
            None if selected_zip_label == "All ZIP Codes" else selected_zip_label
        )

        st.divider()

        # Data freshness
        from lib.data_loader import load_manifest
        manifest = load_manifest()
        if manifest:
            synced_at = manifest.get("synced_at", "unknown")
            # Truncate to date+time
            if "T" in str(synced_at):
                synced_at = str(synced_at).split(".")[0].replace("T", " ")
            st.markdown(
                f"<p style='font-size: 0.72rem; color: #94a3b8;'>"
                f"Data as of {synced_at} UTC"
                f"</p>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<p style='font-size: 0.72rem; color: #f59e0b;'>"
                "No sync manifest found"
                "</p>",
                unsafe_allow_html=True,
            )

    return {
        "borough": selected_borough,
        "year_month": selected_year_month,
        "zip_code": selected_zip,
    }
