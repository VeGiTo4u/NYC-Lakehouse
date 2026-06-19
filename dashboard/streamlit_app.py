"""
NYC Neighborhood Pulse — Streamlit Dashboard Entry Point.

Multi-page application serving cross-domain urban analytics at
zip code + month grain. Uses Streamlit's native page routing via
the pages/ directory.

Architecture Reference:
    High-Level Architecture.md — Section 7.8 (Presentation)
    CLAUDE.md — Section 9 (DuckDB + Plotly Chart Layer)
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Ensure dashboard modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from db import get_connection, get_tables
from lib.data_loader import EXPORT_FILES, load_manifest

# ── Page config ──────────────────────────────────────────────

st.set_page_config(
    page_title="NYC Neighborhood Pulse",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────
# Professional look: tighter spacing, Inter font, no emoji artifacts

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* Tighter header spacing */
    .stMainBlockContainer { padding-top: 1.5rem; }

    /* Metric card styling */
    [data-testid="stMetric"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 0.75rem 1rem;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.78rem;
        color: #475569;
        font-weight: 500;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.5rem;
        font-weight: 600;
        color: #0f172a;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    section[data-testid="stSidebar"] .stSelectbox label {
        font-size: 0.8rem;
        font-weight: 500;
        color: #334155;
    }

    /* Clean dividers */
    hr { border-color: #e2e8f0; }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { background: transparent; }

    /* Plotly chart container */
    .stPlotlyChart { border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Data validation ──────────────────────────────────────────

data_dir = Path(__file__).parent / "data"
missing = [f for f in EXPORT_FILES if not (data_dir / f).exists()]

if missing:
    st.markdown(
        "<h1 style='font-size: 1.6rem; color: #0f172a;'>NYC Neighborhood Pulse</h1>",
        unsafe_allow_html=True,
    )
    st.error(
        "Missing data files. Run the KPI export pipeline or trigger the "
        "GitHub Actions sync workflow.\n\n"
        + "\n".join(f"- `{f}`" for f in missing)
    )
    st.info(
        "To sync manually:\n"
        "```bash\n"
        "python scripts/export/sync_kpi_from_s3.py\n"
        "```"
    )
    st.stop()

# ── Initialize DuckDB ───────────────────────────────────────

conn = get_connection()
tables = get_tables()

# ── Landing page ─────────────────────────────────────────────

st.markdown(
    "<h1 style='font-size: 1.6rem; font-weight: 600; color: #0f172a; "
    "letter-spacing: -0.01em;'>NYC Neighborhood Pulse</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='font-size: 0.88rem; color: #475569; margin-top: 0;'>"
    "Cross-domain neighborhood health analytics across 311 complaints, "
    "NYPD arrests, DOB permits, and restaurant inspections "
    "at zip code + month grain.</p>",
    unsafe_allow_html=True,
)

# Data freshness
manifest = load_manifest()
if manifest:
    synced_at = manifest.get("synced_at", "unknown")
    if "T" in str(synced_at):
        synced_at = str(synced_at).split(".")[0].replace("T", " ")
    st.markdown(
        f"<p style='font-size: 0.75rem; color: #94a3b8;'>"
        f"Data synced at {synced_at} UTC</p>",
        unsafe_allow_html=True,
    )

st.divider()

# Dataset summary
col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Data Tables", f"{len(tables)}")

with col2:
    from db import query_df
    try:
        total_rows = query_df(
            "SELECT SUM(cnt) AS total FROM ("
            "SELECT COUNT(*) AS cnt FROM neighborhood_pulse_summary "
            "UNION ALL SELECT COUNT(*) FROM borough_monthly_trends "
            "UNION ALL SELECT COUNT(*) FROM safety_infrastructure_corr "
            "UNION ALL SELECT COUNT(*) FROM food_compliance_overview "
            "UNION ALL SELECT COUNT(*) FROM complaint_type_rankings"
            ")"
        )["total"].iloc[0]
        st.metric("Total Records", f"{int(total_rows):,}")
    except Exception:
        st.metric("Total Records", "N/A")

with col3:
    try:
        boroughs = query_df(
            "SELECT COUNT(DISTINCT borough) AS n FROM neighborhood_pulse_summary"
        )["n"].iloc[0]
        st.metric("Boroughs", f"{int(boroughs)}")
    except Exception:
        st.metric("Boroughs", "N/A")

st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

# Navigation hint
st.markdown(
    "<p style='font-size: 0.85rem; color: #475569;'>"
    "Use the sidebar to navigate between pages and apply filters.</p>",
    unsafe_allow_html=True,
)

page_descriptions = [
    ("Neighborhood Explorer", "Composite pulse score, zip-level KPI breakdown, borough comparison"),
    ("Complaint Intelligence", "311 complaint trends, top types, resolution time analysis"),
    ("Safety & Infrastructure", "NYPD arrests vs DOB permits correlation, crime category trends"),
    ("Food Safety Compliance", "Restaurant grade distribution, food complaint overlap, inspection volume"),
]

for title, desc in page_descriptions:
    st.markdown(
        f"<div style='padding: 0.5rem 0;'>"
        f"<span style='font-weight: 500; color: #0f172a; font-size: 0.9rem;'>"
        f"{title}</span>"
        f"<span style='color: #94a3b8; font-size: 0.9rem;'> — {desc}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
