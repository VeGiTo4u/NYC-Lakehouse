"""
Chart factories for the Complaint Intelligence page.

Dark theme with gradient fills. Fixed titlefont deprecation.

Data source: complaint_type_rankings, borough_monthly_trends,
             neighborhood_pulse_summary
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import (
    BOROUGH_COLORS,
    BOROUGH_ORDER,
    CATEGORICAL_PALETTE,
    COLORS,
    apply_default_layout,
    format_number,
    safe_float,
)


def top_complaints_bar(
    df: pd.DataFrame,
    borough: str,
    year_month: str,
    top_n: int = 10,
) -> go.Figure:
    """
    Horizontal bar chart of the top N complaint types.
    """
    df = df.copy()
    df["pct_of_borough_total"] = pd.to_numeric(df["pct_of_borough_total"], errors="coerce")

    df = (
        df.sort_values("complaint_count", ascending=False)
        .head(top_n)
        .sort_values("complaint_count", ascending=True)
    )

    # Gradient-like color scale from muted to vibrant
    n = len(df)
    bar_colors = [
        f"rgba(129,140,248,{0.4 + 0.6 * i / max(n - 1, 1)})" for i in range(n)
    ]

    fig = go.Figure(
        go.Bar(
            x=df["complaint_count"],
            y=df["complaint_type"],
            orientation="h",
            marker_color=bar_colors,
            marker_line=dict(width=0),
            text=df["pct_of_borough_total"].apply(
                lambda v: f"{safe_float(v) * 100:.1f}%" if pd.notna(v) else ""
            ),
            textposition="outside",
            textfont=dict(size=10, color=COLORS["text_secondary"]),
            hovertemplate=(
                "%{y}<br>"
                "Count: %{x:,}<br>"
                "<extra></extra>"
            ),
        )
    )

    apply_default_layout(
        fig,
        title=f"Top {top_n} Complaint Types — {borough.title()}, {year_month}",
        x_title="Complaint Count",
        y_title="",
        show_legend=False,
        height=max(360, top_n * 32),
    )
    fig.update_layout(margin=dict(l=200))
    return fig


def complaint_trend_line(
    df: pd.DataFrame,
    borough: str | None = None,
) -> go.Figure:
    """
    Complaint category breakdown over time with gradient fills.
    """
    if borough:
        df = df[df["borough"] == borough].copy()
        df = df.sort_values("year_month")
    else:
        df = (
            df.groupby("year_month", as_index=False)
            .agg(
                noise_complaint_count=("noise_complaint_count", "sum"),
                food_complaint_count=("food_complaint_count", "sum"),
                construction_complaint_count=("construction_complaint_count", "sum"),
            )
            .sort_values("year_month")
        )

    categories = [
        ("noise_complaint_count", "Noise", COLORS["indigo_400"], "rgba(129,140,248,0.08)"),
        ("food_complaint_count", "Food", COLORS["amber_400"], "rgba(251,191,36,0.06)"),
        ("construction_complaint_count", "Construction", COLORS["cyan_400"], "rgba(34,211,238,0.06)"),
    ]

    fig = go.Figure()
    for col, label, color, fill in categories:
        fig.add_trace(
            go.Scatter(
                x=df["year_month"],
                y=df[col],
                mode="lines",
                name=label,
                line=dict(color=color, width=2.5),
                fill="tozeroy",
                fillcolor=fill,
                hovertemplate="%{y:,}<extra>" + label + "</extra>",
            )
        )

    title_suffix = f" — {borough.title()}" if borough else " — All Boroughs"
    apply_default_layout(
        fig,
        title=f"Complaint Categories{title_suffix}",
        x_title="Month",
        y_title="Count",
    )
    return fig


def borough_comparison_area(
    df: pd.DataFrame,
    metric: str = "total_complaints",
    metric_label: str = "Total Complaints",
) -> go.Figure:
    """
    Stacked area chart of a metric over time, broken down by borough.
    """
    fig = go.Figure()

    for borough in BOROUGH_ORDER:
        bdf = df[df["borough"] == borough].sort_values("year_month")
        if bdf.empty:
            continue

        color = BOROUGH_COLORS.get(borough, COLORS["slate_400"])
        fig.add_trace(
            go.Scatter(
                x=bdf["year_month"],
                y=bdf[metric],
                mode="lines",
                name=borough.title(),
                line=dict(width=0.5, color=color),
                stackgroup="one",
                hovertemplate="%{y:,}<extra>" + borough.title() + "</extra>",
            )
        )

    apply_default_layout(
        fig,
        title=f"{metric_label} by Borough",
        x_title="Month",
        y_title=metric_label,
    )
    return fig


def resolution_time_chart(
    df: pd.DataFrame,
    borough: str | None = None,
) -> go.Figure:
    """
    Bar + line: complaint volume (bars) and avg resolution hours (line).
    Fixed: titlefont → title_font.
    """
    if borough:
        df = df[df["borough"] == borough].copy()

    df = df.copy()
    df["avg_resolution_hours"] = pd.to_numeric(df["avg_resolution_hours"], errors="coerce")

    agg = (
        df.groupby("year_month", as_index=False)
        .agg(
            total_complaints=("total_complaints", "sum"),
            avg_resolution_hours=("avg_resolution_hours", "mean"),
        )
        .sort_values("year_month")
    )

    fig = go.Figure()

    # Volume bars
    fig.add_trace(
        go.Bar(
            x=agg["year_month"],
            y=agg["total_complaints"],
            name="Complaints",
            marker_color="rgba(129,140,248,0.3)",
            marker_line_color=COLORS["indigo_400"],
            marker_line_width=1,
            yaxis="y",
            hovertemplate="%{y:,} complaints<extra></extra>",
        )
    )

    # Resolution hours line
    fig.add_trace(
        go.Scatter(
            x=agg["year_month"],
            y=agg["avg_resolution_hours"],
            mode="lines+markers",
            name="Avg Resolution (hrs)",
            line=dict(color=COLORS["rose_400"], width=2.5),
            marker=dict(size=4, color=COLORS["rose_400"]),
            yaxis="y2",
            hovertemplate="%{y:.1f} hrs<extra></extra>",
        )
    )

    title_suffix = f" — {borough.title()}" if borough else ""
    apply_default_layout(
        fig,
        title=f"Volume vs Resolution Time{title_suffix}",
        x_title="Month",
        y_title="Complaint Count",
    )
    fig.update_layout(
        yaxis2=dict(
            title="Avg Resolution Hours",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(size=10, color=COLORS["rose_400"]),
            title_font=dict(size=11, color=COLORS["rose_400"]),
        ),
    )
    return fig


def complaint_treemap(
    df: pd.DataFrame,
    borough: str,
    year_month: str,
    top_n: int = 12,
) -> go.Figure:
    """
    Treemap of complaint type distribution — better for proportional data.
    """
    df = df.copy()
    df = df.sort_values("complaint_count", ascending=False).head(top_n)
    df["pct_of_borough_total"] = pd.to_numeric(df["pct_of_borough_total"], errors="coerce")

    fig = go.Figure(
        go.Treemap(
            labels=df["complaint_type"],
            parents=[""] * len(df),
            values=df["complaint_count"],
            textinfo="label+percent root",
            textfont=dict(size=11, color=COLORS["text_primary"]),
            marker=dict(
                colors=CATEGORICAL_PALETTE[: len(df)],
                line=dict(width=1, color=COLORS["bg_primary"]),
            ),
            hovertemplate=(
                "%{label}<br>"
                "Count: %{value:,}<br>"
                "Share: %{percentRoot:.1%}"
                "<extra></extra>"
            ),
        )
    )

    apply_default_layout(
        fig,
        title=f"Complaint Breakdown — {borough.title()}, {year_month}",
        show_legend=False,
        height=400,
    )
    fig.update_layout(margin=dict(l=8, r=8, t=56, b=8))
    return fig
