"""
Complaint Intelligence — Page 2

311 complaint trends, top complaint types, resolution time analysis.
Primary data source: complaint_type_rankings, borough_monthly_trends,
                     neighborhood_pulse_summary.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.header import render_header
from components.metric_card import render_metric_row
from components.sidebar import render_sidebar
from charts.complaints import (
    borough_comparison_area,
    complaint_trend_line,
    resolution_time_chart,
    top_complaints_bar,
)
from charts.theme import format_number
from db import query_df

st.set_page_config(page_title="Complaint Intelligence | NYC Pulse", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────

filters = render_sidebar()

# ── Header ───────────────────────────────────────────────────

render_header(
    title="Complaint Intelligence",
    subtitle="311 complaint trends, top types by borough, and resolution time analysis.",
)

# ── Guard ────────────────────────────────────────────────────

if not filters["year_month"]:
    st.warning("No data available.")
    st.stop()

ym = filters["year_month"]
borough = filters["borough"]

# ── KPI Summary ──────────────────────────────────────────────

borough_clause = f"AND borough = '{borough}'" if borough else ""

summary = query_df(
    f"SELECT "
    f"  SUM(total_complaints) AS total, "
    f"  SUM(noise_complaint_count) AS noise, "
    f"  SUM(food_complaint_count) AS food, "
    f"  SUM(construction_complaint_count) AS construction "
    f"FROM neighborhood_pulse_summary "
    f"WHERE year_month = '{ym}' {borough_clause}"
)

if summary.empty or summary.iloc[0]["total"] is None:
    st.info(f"No complaint data for {ym}.")
    st.stop()

s = summary.iloc[0]

render_metric_row([
    {"label": "Total Complaints", "value": format_number(s["total"])},
    {"label": "Noise", "value": format_number(s["noise"])},
    {"label": "Food", "value": format_number(s["food"])},
    {"label": "Construction", "value": format_number(s["construction"])},
])

st.divider()

# ── Top Complaints + Trend Line ──────────────────────────────

col_top, col_trend = st.columns(2)

with col_top:
    target_borough = borough or "MANHATTAN"
    ranking_data = query_df(
        "SELECT * FROM complaint_type_rankings "
        "WHERE borough = ? AND year_month = ?",
        [target_borough, ym],
    )
    if not ranking_data.empty:
        fig_top = top_complaints_bar(ranking_data, target_borough, ym)
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info(f"No ranking data for {target_borough} in {ym}.")

with col_trend:
    trends = query_df("SELECT * FROM borough_monthly_trends")
    if not trends.empty:
        fig_trend = complaint_trend_line(trends, borough)
        st.plotly_chart(fig_trend, use_container_width=True)

# ── Borough Area + Resolution Time ───────────────────────────

st.divider()

col_area, col_res = st.columns(2)

with col_area:
    if not trends.empty:
        fig_area = borough_comparison_area(trends)
        st.plotly_chart(fig_area, use_container_width=True)

with col_res:
    pulse_data = query_df("SELECT * FROM neighborhood_pulse_summary")
    if not pulse_data.empty:
        fig_res = resolution_time_chart(pulse_data, borough)
        st.plotly_chart(fig_res, use_container_width=True)
