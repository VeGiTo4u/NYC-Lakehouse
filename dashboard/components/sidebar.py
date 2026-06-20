"""
Premium sidebar component with branding and data health indicators.
"""

from __future__ import annotations

from typing import Dict, Optional

import streamlit as st

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import get_boroughs, get_year_months, get_zip_codes


def render_sidebar() -> Dict[str, Optional[str]]:
    """
    Renders the premium sidebar with branding, filters, and data health.

    Returns
    -------
    dict with keys: borough, year_month, zip_code
    """
    with st.sidebar:
        # ── Branding ──
        st.markdown(
            """<div style="padding: 4px 0 12px;">
                <h2 style="
                    margin: 0;
                    font-size: 1.2rem;
                    font-weight: 700;
                    background: linear-gradient(135deg, #818cf8, #22d3ee);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    letter-spacing: -0.02em;
                ">NYC Neighborhood Pulse</h2>
                <p style="
                    color: #64748b;
                    font-size: 0.73rem;
                    margin: 2px 0 0;
                    letter-spacing: 0.03em;
                ">Cross-domain urban analytics</p>
            </div>""",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<hr style='border-color: rgba(255,255,255,0.06); margin: 4px 0 16px;'>",
            unsafe_allow_html=True,
        )

        # ── Filters ──
        st.markdown(
            "<p style='font-size:0.68rem; color:#64748b; font-weight:600; "
            "text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;'>"
            "Filters</p>",
            unsafe_allow_html=True,
        )

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

        # ── Reset button ──
        if st.button("↺ Reset Filters", use_container_width=True):
            for key in ["sidebar_borough", "sidebar_year_month", "sidebar_zip"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        st.markdown(
            "<hr style='border-color: rgba(255,255,255,0.06); margin: 16px 0 12px;'>",
            unsafe_allow_html=True,
        )

        # ── Data Health ──
        st.markdown(
            "<p style='font-size:0.68rem; color:#64748b; font-weight:600; "
            "text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;'>"
            "Data Health</p>",
            unsafe_allow_html=True,
        )

        datasets = [
            ("311 Complaints", "2020-01 — 2020-03", "#818cf8"),
            ("NYPD Arrests", "2020-01 — 2020-06", "#fb7185"),
            ("DOB Permits", "2020-01 — 2020-06", "#22d3ee"),
            ("Food Inspections", "2015-02 — 2026-06", "#34d399"),
        ]

        for name, period, color in datasets:
            st.markdown(
                f"""<div style="
                    display:flex; align-items:center; gap:8px;
                    padding:3px 0; font-size:0.72rem;
                ">
                    <span style="
                        width:6px; height:6px; border-radius:50%;
                        background:{color}; flex-shrink:0;
                        box-shadow: 0 0 6px {color}40;
                    "></span>
                    <span style="color:#94a3b8; flex:1;">{name}</span>
                    <span style="color:#64748b; font-size:0.65rem;">{period}</span>
                </div>""",
                unsafe_allow_html=True,
            )

        # ── Data freshness ──
        from lib.data_loader import load_manifest
        manifest = load_manifest()
        if manifest:
            synced_at = manifest.get("synced_at", "unknown")
            if "T" in str(synced_at):
                synced_at = str(synced_at).split(".")[0].replace("T", " ")
            st.markdown(
                f"<p style='font-size: 0.65rem; color: #475569; margin-top:10px;'>"
                f"Last sync: {synced_at} UTC"
                f"</p>",
                unsafe_allow_html=True,
            )

    return {
        "borough": selected_borough,
        "year_month": selected_year_month,
        "zip_code": selected_zip,
    }
