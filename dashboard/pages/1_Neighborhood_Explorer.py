"""
Neighborhood Explorer — Page 1

Composite pulse score analysis at zip code level with borough context.
Primary data source: neighborhood_pulse_summary, borough_monthly_trends.
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.header import render_header
from components.metric_card import render_metric_row
from components.sidebar import render_sidebar
from charts.pulse import (
    borough_comparison_bar,
    mom_delta_indicator,
    pulse_score_distribution,
    pulse_score_gauge,
    pulse_time_series,
)
from charts.theme import format_number
from db import query_df

st.set_page_config(page_title="Neighborhood Explorer | NYC Pulse", layout="wide")

# ── Sidebar ──────────────────────────────────────────────────

filters = render_sidebar()

# ── Header ───────────────────────────────────────────────────

render_header(
    title="Neighborhood Explorer",
    subtitle="Composite neighborhood health score across 311 complaints, "
    "NYPD arrests, DOB permits, and restaurant inspections.",
)

# ── Guard: need year_month ───────────────────────────────────

if not filters["year_month"]:
    st.warning("No data available. Ensure KPI exports have been synced.")
    st.stop()

ym = filters["year_month"]
borough = filters["borough"]
zip_code = filters["zip_code"]

# ── KPI Summary Row ─────────────────────────────────────────

if zip_code:
    # Single zip view
    row = query_df(
        "SELECT * FROM neighborhood_pulse_summary "
        "WHERE zip_code = ? AND year_month = ?",
        [zip_code, ym],
    )
    if row.empty:
        st.info(f"No data for ZIP {zip_code} in {ym}.")
        st.stop()

    r = row.iloc[0]
    score = float(r["neighborhood_pulse_score"])
    borough_avg = float(r["borough_avg_pulse_score"]) if r["borough_avg_pulse_score"] else 0
    city_avg = float(r["city_avg_pulse_score"]) if r["city_avg_pulse_score"] else 0
    mom = r["pulse_score_mom_delta"]
    mom_str = f"{mom:+.1f}" if mom and mom == mom else None

    render_metric_row([
        {"label": "Pulse Score", "value": f"{score:.1f}", "delta": mom_str},
        {"label": "Borough Avg", "value": f"{borough_avg:.1f}"},
        {"label": "City Avg", "value": f"{city_avg:.1f}"},
        {"label": "Complaints", "value": format_number(r.get("total_complaints", 0)), "delta_color": "inverse"},
        {"label": "Arrests", "value": format_number(r.get("total_arrests", 0)), "delta_color": "inverse"},
    ])

    st.divider()

    # Gauge + Time series
    col_gauge, col_ts = st.columns([1, 2])

    with col_gauge:
        fig_gauge = pulse_score_gauge(score, borough_avg, city_avg, zip_code)
        st.plotly_chart(fig_gauge, use_container_width=True)

    with col_ts:
        ts_data = query_df(
            "SELECT * FROM neighborhood_pulse_summary "
            "WHERE zip_code = ? ORDER BY year_month",
            [zip_code],
        )
        if not ts_data.empty:
            fig_ts = pulse_time_series(ts_data, zip_code)
            st.plotly_chart(fig_ts, use_container_width=True)

else:
    # Borough/city-wide view
    borough_filter = f"WHERE borough = '{borough}'" if borough else ""

    summary = query_df(
        f"SELECT "
        f"  AVG(neighborhood_pulse_score) AS avg_score, "
        f"  SUM(total_complaints) AS complaints, "
        f"  SUM(total_arrests) AS arrests, "
        f"  SUM(total_permits_issued) AS permits, "
        f"  SUM(total_inspections) AS inspections "
        f"FROM neighborhood_pulse_summary "
        f"{borough_filter + ' AND' if borough_filter else 'WHERE'} year_month = '{ym}'"
    )

    if summary.empty:
        st.info(f"No data for {ym}.")
        st.stop()

    s = summary.iloc[0]

    render_metric_row([
        {"label": "Avg Pulse Score", "value": f"{s['avg_score']:.1f}" if s["avg_score"] else "N/A"},
        {"label": "Total Complaints", "value": format_number(s.get("complaints", 0))},
        {"label": "Total Arrests", "value": format_number(s.get("arrests", 0))},
        {"label": "Permits Issued", "value": format_number(s.get("permits", 0))},
        {"label": "Inspections", "value": format_number(s.get("inspections", 0))},
    ])

    st.divider()

    # Borough comparison + distribution
    col_bar, col_dist = st.columns(2)

    with col_bar:
        trends = query_df(
            f"SELECT * FROM borough_monthly_trends WHERE year_month = '{ym}'"
        )
        if not trends.empty:
            fig_bar = borough_comparison_bar(trends, ym)
            st.plotly_chart(fig_bar, use_container_width=True)

    with col_dist:
        if borough:
            dist_data = query_df(
                "SELECT zip_code, neighborhood_pulse_score "
                "FROM neighborhood_pulse_summary "
                "WHERE borough = ? AND year_month = ?",
                [borough, ym],
            )
            if not dist_data.empty:
                fig_dist = pulse_score_distribution(dist_data, borough, ym)
                st.plotly_chart(fig_dist, use_container_width=True)
        else:
            st.markdown(
                "<p style='color: #475569; font-size: 0.85rem; padding-top: 2rem;'>"
                "Select a borough to see zip-level pulse score distribution.</p>",
                unsafe_allow_html=True,
            )
