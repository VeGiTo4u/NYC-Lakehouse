"""
Safety & Infrastructure — Page 3

NYPD arrests vs DOB permits correlation, crime category trends,
and permit issuance patterns.
Primary data source: safety_infrastructure_corr, borough_monthly_trends.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.header import render_header
from components.metric_card import render_metric_row
from components.sidebar import render_sidebar
from charts.safety import (
    arrests_per_permit_heatmap,
    arrests_permits_scatter,
    arrests_trend_line,
    permits_trend_bar,
)
from charts.theme import format_number
from db import query_df

st.set_page_config(page_title="Safety & Infrastructure | NYC Pulse", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────

filters = render_sidebar()

# ── Header ───────────────────────────────────────────────────

render_header(
    title="Safety & Infrastructure",
    subtitle="Correlation between NYPD arrest activity and DOB permit issuance "
    "at zip code level.",
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
    f"  SUM(total_arrests) AS arrests, "
    f"  SUM(total_permits_issued) AS permits, "
    f"  SUM(felony_count) AS felonies, "
    f"  SUM(misdemeanor_count) AS misdemeanors "
    f"FROM borough_monthly_trends "
    f"WHERE year_month = '{ym}' {borough_clause}"
)

if summary.empty or summary.iloc[0]["arrests"] is None:
    st.info(f"No safety data for {ym}.")
    st.stop()

s = summary.iloc[0]
arrests_per_permit = (
    round(s["arrests"] / s["permits"], 2) if s["permits"] and s["permits"] > 0 else 0
)

render_metric_row([
    {"label": "Total Arrests", "value": format_number(s["arrests"])},
    {"label": "Permits Issued", "value": format_number(s["permits"])},
    {"label": "Felonies", "value": format_number(s["felonies"])},
    {"label": "Misdemeanors", "value": format_number(s["misdemeanors"])},
    {"label": "Arrests / Permit", "value": f"{arrests_per_permit:.2f}"},
])

st.divider()

# ── Scatter + Arrest Trends ──────────────────────────────────

col_scatter, col_arrests = st.columns(2)

with col_scatter:
    scatter_data = query_df(
        "SELECT * FROM safety_infrastructure_corr WHERE year_month = ?",
        [ym],
    )
    if not scatter_data.empty:
        fig_scatter = arrests_permits_scatter(scatter_data, ym)
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info(f"No correlation data for {ym}.")

with col_arrests:
    trends = query_df("SELECT * FROM borough_monthly_trends")
    if not trends.empty:
        fig_arrests = arrests_trend_line(trends, borough)
        st.plotly_chart(fig_arrests, use_container_width=True)

# ── Permits + Heatmap ────────────────────────────────────────

st.divider()

col_permits, col_heat = st.columns(2)

with col_permits:
    if not trends.empty:
        fig_permits = permits_trend_bar(trends, borough)
        st.plotly_chart(fig_permits, use_container_width=True)

with col_heat:
    if not trends.empty:
        fig_heat = arrests_per_permit_heatmap(trends)
        st.plotly_chart(fig_heat, use_container_width=True)
