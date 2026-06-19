"""
Food Safety Compliance — Page 4

Restaurant grade distribution, food complaint overlap, and inspection volume.
Primary data source: food_compliance_overview, borough_monthly_trends.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.header import render_header
from components.metric_card import render_metric_row
from components.sidebar import render_sidebar
from charts.food import (
    compliance_scatter,
    food_complaint_trend,
    grade_distribution_bar,
    inspection_volume_bar,
)
from charts.theme import format_number
from db import query_df

st.set_page_config(page_title="Food Compliance | NYC Pulse", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────

filters = render_sidebar()

# ── Header ───────────────────────────────────────────────────

render_header(
    title="Food Safety Compliance",
    subtitle="Restaurant inspection grades, violation trends, and food safety complaints.",
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
    f"  SUM(total_inspections) AS inspections, "
    f"  SUM(unique_restaurants_inspected) AS unique_restaurants, "
    f"  SUM(food_complaint_count) AS food_complaints "
    f"FROM food_compliance_overview "
    f"WHERE year_month = '{ym}' {borough_clause}"
)

# Get grade distribution for KPIs
grade_summary = query_df(
    f"SELECT "
    f"  AVG(pct_grade_a) AS avg_pct_a "
    f"FROM food_compliance_overview "
    f"WHERE year_month = '{ym}' {borough_clause}"
)

if summary.empty or summary.iloc[0]["inspections"] is None:
    st.info(f"No food compliance data for {ym}.")
    st.stop()

s = summary.iloc[0]
g = grade_summary.iloc[0]
avg_grade_a_pct = (g["avg_pct_a"] * 100) if g["avg_pct_a"] is not None else 0

render_metric_row([
    {"label": "Total Inspections", "value": format_number(s["inspections"])},
    {"label": "Unique Restaurants", "value": format_number(s["unique_restaurants"])},
    {"label": "Avg Grade A Rate", "value": f"{avg_grade_a_pct:.1f}%"},
    {"label": "Food Complaints", "value": format_number(s["food_complaints"]), "delta_color": "inverse"},
])

st.divider()

# ── Grade Distribution + Compliance Scatter ──────────────────

col_dist, col_scatter = st.columns(2)

with col_dist:
    food_data = query_df(
        f"SELECT * FROM food_compliance_overview "
        f"WHERE year_month = '{ym}' {borough_clause}"
    )
    if not food_data.empty:
        fig_dist = grade_distribution_bar(food_data, borough, ym)
        st.plotly_chart(fig_dist, use_container_width=True)
    else:
        st.info(f"No grade data for {ym}.")

with col_scatter:
    if not food_data.empty:
        fig_scatter = compliance_scatter(food_data, ym)
        st.plotly_chart(fig_scatter, use_container_width=True)

# ── Inspection Volume + Complaint Trend ──────────────────────

st.divider()

col_vol, col_trend = st.columns(2)

with col_vol:
    all_food_data = query_df(
        f"SELECT * FROM food_compliance_overview "
        f"WHERE 1=1 {borough_clause}"
    )
    if not all_food_data.empty:
        fig_vol = inspection_volume_bar(all_food_data, borough)
        st.plotly_chart(fig_vol, use_container_width=True)

with col_trend:
    trends = query_df("SELECT * FROM borough_monthly_trends")
    if not trends.empty:
        fig_trend = food_complaint_trend(trends, borough)
        st.plotly_chart(fig_trend, use_container_width=True)
