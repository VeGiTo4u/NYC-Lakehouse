"""
Chart factories for the Executive Landing Page.

Provides city-wide overview visualizations: health donut,
domain comparison, and data coverage timeline.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import (
    BOROUGH_COLORS,
    BOROUGH_ORDER,
    COLORS,
    DOMAIN_COLORS,
    apply_default_layout,
    safe_float,
)


def city_health_donut(score: float) -> go.Figure:
    """
    Overall city health score as an animated donut.
    """
    score = safe_float(score)
    remaining = max(0, 100 - score)
    color = (
        COLORS["emerald_400"] if score >= 70 else
        COLORS["indigo_400"] if score >= 50 else
        COLORS["amber_400"] if score >= 30 else
        COLORS["rose_400"]
    )

    fig = go.Figure(
        go.Pie(
            values=[score, remaining],
            hole=0.75,
            marker=dict(
                colors=[color, "rgba(255,255,255,0.04)"],
                line=dict(width=0),
            ),
            textinfo="none",
            hoverinfo="skip",
            direction="clockwise",
            sort=False,
        )
    )

    # Central score annotation
    fig.add_annotation(
        text=f"<b>{score:.0f}</b>",
        x=0.5, y=0.55,
        font=dict(size=42, color=COLORS["text_primary"], family="Plus Jakarta Sans"),
        showarrow=False,
        xref="paper", yref="paper",
    )
    fig.add_annotation(
        text="City Pulse",
        x=0.5, y=0.38,
        font=dict(size=11, color=COLORS["text_muted"]),
        showarrow=False,
        xref="paper", yref="paper",
    )

    fig.update_layout(
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=220,
        margin=dict(l=16, r=16, t=8, b=8),
    )
    return fig


def borough_pulse_bars(df: pd.DataFrame) -> go.Figure:
    """
    Horizontal bars showing avg pulse score per borough.
    Colored by health tier.
    """
    from .theme import health_tier_color

    df = df.copy()
    df["avg_pulse_score"] = pd.to_numeric(df["avg_pulse_score"], errors="coerce")
    df = df.dropna(subset=["avg_pulse_score"])

    # Get latest month
    latest_month = df["year_month"].max()
    df = df[df["year_month"] == latest_month]

    df = df.sort_values("avg_pulse_score", ascending=True)
    colors = [health_tier_color(s) for s in df["avg_pulse_score"]]

    fig = go.Figure(
        go.Bar(
            x=df["avg_pulse_score"],
            y=df["borough"].apply(str.title),
            orientation="h",
            marker_color=colors,
            marker_line=dict(width=0),
            text=df["avg_pulse_score"].apply(lambda v: f"{v:.1f}"),
            textposition="inside",
            textfont=dict(size=12, color=COLORS["bg_primary"], family="Plus Jakarta Sans"),
            hovertemplate="%{y}: %{x:.1f}<extra></extra>",
        )
    )

    apply_default_layout(
        fig,
        title="Borough Health Scores",
        x_title="Pulse Score",
        y_title="",
        show_legend=False,
        height=280,
    )
    fig.update_xaxes(range=[0, 100])
    return fig


def domain_summary_bars(
    complaints: float,
    arrests: float,
    permits: float,
    inspections: float,
) -> go.Figure:
    """
    Horizontal bars showing domain-level totals with distinct colors.
    """
    domains = ["Food Inspections", "DOB Permits", "NYPD Arrests", "311 Complaints"]
    values = [
        safe_float(inspections),
        safe_float(permits),
        safe_float(arrests),
        safe_float(complaints),
    ]
    colors = [
        DOMAIN_COLORS["food"],
        DOMAIN_COLORS["infrastructure"],
        DOMAIN_COLORS["safety"],
        DOMAIN_COLORS["complaints"],
    ]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=domains,
            orientation="h",
            marker_color=colors,
            marker_line=dict(width=0),
            opacity=0.85,
            text=[f"{v:,.0f}" for v in values],
            textposition="inside",
            textfont=dict(size=11, color=COLORS["bg_primary"], family="Plus Jakarta Sans"),
            hovertemplate="%{y}: %{x:,}<extra></extra>",
        )
    )

    apply_default_layout(
        fig,
        title="Domain Activity — Selected Period",
        x_title="",
        y_title="",
        show_legend=False,
        height=250,
    )
    return fig


def monthly_activity_line(df: pd.DataFrame) -> go.Figure:
    """
    Multi-line chart showing all domain activities over time.
    """
    # City-wide aggregation
    agg = (
        df.groupby("year_month", as_index=False)
        .agg(
            total_complaints=("total_complaints", "sum"),
            total_arrests=("total_arrests", "sum"),
            total_permits_issued=("total_permits_issued", "sum"),
            total_inspections=("total_inspections", "sum"),
        )
        .sort_values("year_month")
    )

    domains = [
        ("total_complaints", "311 Complaints", DOMAIN_COLORS["complaints"], "rgba(129,140,248,0.06)"),
        ("total_arrests", "NYPD Arrests", DOMAIN_COLORS["safety"], "rgba(251,113,133,0.06)"),
        ("total_permits_issued", "DOB Permits", DOMAIN_COLORS["infrastructure"], "rgba(34,211,238,0.06)"),
        ("total_inspections", "Food Inspections", DOMAIN_COLORS["food"], "rgba(52,211,153,0.06)"),
    ]

    fig = go.Figure()
    for col, label, color, fill in domains:
        fig.add_trace(
            go.Scatter(
                x=agg["year_month"],
                y=agg[col],
                mode="lines",
                name=label,
                line=dict(color=color, width=2),
                hovertemplate="%{y:,}<extra>" + label + "</extra>",
            )
        )

    apply_default_layout(
        fig,
        title="Cross-Domain Activity Over Time",
        x_title="Month",
        y_title="Count",
        height=350,
    )
    return fig
