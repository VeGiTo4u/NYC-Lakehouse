"""
DuckDB in-memory query engine for the NYC Neighborhood Pulse dashboard.

Loads all 5 pre-aggregated KPI Parquet files from dashboard/data/ into
an in-memory DuckDB instance. Provides a simple query_df() interface
for raw SQL and convenience helpers for common filter patterns.

Usage (inside Streamlit):
    from db import get_connection, query_df

    conn = get_connection()
    df = query_df("SELECT * FROM neighborhood_pulse_summary WHERE borough = 'MANHATTAN'")

Architecture Reference:
    Phase 3 — DuckDB Query Layer + Plotly Chart Factories
    High-Level Architecture.md — Section 7.8 (Presentation)
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import duckdb
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent / "data"

TABLE_PARQUET_MAP = {
    "neighborhood_pulse_summary": "neighborhood_pulse_summary.parquet",
    "borough_monthly_trends": "borough_monthly_trends.parquet",
    "safety_infrastructure_corr": "safety_infrastructure_corr.parquet",
    "food_compliance_overview": "food_compliance_overview.parquet",
    "complaint_type_rankings": "complaint_type_rankings.parquet",
}


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    """
    Creates an in-memory DuckDB connection and loads all Parquet exports.

    Cached via @st.cache_resource so the database is initialized once per
    Streamlit process — not per page load or per user session.

    Returns
    -------
    duckdb.DuckDBPyConnection
        Ready-to-query connection with all KPI tables loaded.
    """
    conn = duckdb.connect(database=":memory:")

    loaded = []
    missing = []

    for table_name, parquet_file in TABLE_PARQUET_MAP.items():
        parquet_path = DATA_DIR / parquet_file
        if not parquet_path.exists():
            missing.append(parquet_file)
            continue

        conn.execute(
            f"CREATE TABLE {table_name} AS "
            f"SELECT * FROM read_parquet('{parquet_path}')"
        )
        row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        loaded.append((table_name, row_count))

    if loaded:
        for name, rows in loaded:
            print(f"[INFO] DuckDB loaded: {name} ({rows:,} rows)")

    if missing:
        print(f"[WARN] Missing Parquet files: {', '.join(missing)}")

    return conn


def query_df(sql: str, params: Optional[list] = None) -> pd.DataFrame:
    """
    Executes a SQL query against the DuckDB in-memory database.

    Parameters
    ----------
    sql : str
        DuckDB-compatible SQL statement.
    params : list, optional
        Positional parameters for parameterized queries.

    Returns
    -------
    pd.DataFrame
        Query results as a pandas DataFrame.
    """
    conn = get_connection()
    if params:
        return conn.execute(sql, params).fetchdf()
    return conn.execute(sql).fetchdf()


def get_tables() -> List[str]:
    """Returns the list of tables currently loaded in DuckDB."""
    conn = get_connection()
    result = conn.execute("SHOW TABLES").fetchdf()
    return result["name"].tolist()


def get_boroughs() -> List[str]:
    """Returns distinct borough values from neighborhood_pulse_summary."""
    try:
        df = query_df(
            "SELECT DISTINCT borough FROM neighborhood_pulse_summary "
            "WHERE borough IS NOT NULL ORDER BY borough"
        )
        return df["borough"].tolist()
    except Exception:
        return []


def get_year_months() -> List[str]:
    """Returns distinct year_month values, most recent first."""
    try:
        df = query_df(
            "SELECT DISTINCT year_month FROM neighborhood_pulse_summary "
            "ORDER BY year_month DESC"
        )
        return df["year_month"].tolist()
    except Exception:
        return []


def get_zip_codes(borough: Optional[str] = None) -> List[str]:
    """Returns distinct zip codes, optionally filtered by borough."""
    try:
        if borough:
            df = query_df(
                "SELECT DISTINCT zip_code FROM neighborhood_pulse_summary "
                "WHERE borough = ? ORDER BY zip_code",
                [borough],
            )
        else:
            df = query_df(
                "SELECT DISTINCT zip_code FROM neighborhood_pulse_summary "
                "ORDER BY zip_code"
            )
        return df["zip_code"].tolist()
    except Exception:
        return []
