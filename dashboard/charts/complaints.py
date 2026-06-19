"""
Chart factories for the Complaint Intelligence page.

All functions receive a pandas DataFrame and return a
plotly.graph_objects.Figure. No Streamlit imports.

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
)


def top_complaints_bar(
    df: pd.DataFrame,
    borough: str,
    year_month: str,
    top_n: int = 10,
) -> go.Figure:
    """
    Horizontal bar chart of the top N complaint types for a borough+month.

    Parameters
    ----------
    df : pd.DataFrame
        From complaint_type_rankings, filtered to borough + year_month.
        Must have columns: complaint_type, complaint_count, pct_of_borough_total.
    borough : str
        Borough name for the title.
    year_month : str
        Month for the title.
    top_n : int
        Number of complaint types to show.
    """
    df = (
        df.sort_values("complaint_count", ascending=False)
        .head(top_n)
        .sort_values("complaint_count", ascending=True)
    )

    fig = go.Figure(
        go.Bar(
            x=df["complaint_count"],
            y=df["complaint_type"],
            orientation="h",
            marker_color=COLORS["blue_600"],
            text=df["pct_of_borough_total"].apply(lambda v: f"{v * 100:.1f}%"),
            textposition="outside",
            textfont=dict(size=10, color=COLORS["slate_600"]),
            hovertemplate=(
                "%{y}<br>"
                "Count: %{x:,}<br>"
                "<extra></extra>"
            ),
        )
    )

    apply_default_layout(
        fig,
        title=f"Top {top_n} Complaint Types — {borough}, {year_month}",
        x_title="Complaint Count",
        y_title="",
        show_legend=False,
        height=max(360, top_n * 32),
    )
    fig.update_layout(margin=dict(l=220))
    return fig


def complaint_trend_line(
    df: pd.DataFrame,
    borough: str | None = None,
) -> go.Figure:
    """
    Monthly complaint category breakdown over time (noise, food, construction).

    Parameters
    ----------
    df : pd.DataFrame
        From borough_monthly_trends. If borough is provided, pre-filtered.
        Must have columns: year_month, noise_complaint_count,
        food_complaint_count, construction_complaint_count.
    borough : str or None
        Borough name for the title. If None, shows city-wide.
    """
    if borough:
        df = df[df["borough"] == borough].copy()
        # Single borough — just plot its values
        df = df.sort_values("year_month")
    else:
        # City-wide — aggregate across boroughs
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
        ("noise_complaint_count", "Noise", COLORS["blue_600"]),
        ("food_complaint_count", "Food", COLORS["amber_500"]),
        ("construction_complaint_count", "Construction", COLORS["slate_600"]),
    ]

    fig = go.Figure()
    for col, label, color in categories:
        fig.add_trace(
            go.Scatter(
                x=df["year_month"],
                y=df[col],
                mode="lines",
                name=label,
                line=dict(color=color, width=2),
                hovertemplate="%{y:,}<extra>" + label + "</extra>",
            )
        )

    title_suffix = f" — {borough}" if borough else " — All Boroughs"
    apply_default_layout(
        fig,
        title=f"Complaint Categories{title_suffix}",
        x_title="Month",
        y_title="Complaint Count",
    )
    return fig


def borough_comparison_area(
    df: pd.DataFrame,
    metric: str = "total_complaints",
    metric_label: str = "Total Complaints",
) -> go.Figure:
    """
    Stacked area chart of a metric over time, broken down by borough.

    Parameters
    ----------
    df : pd.DataFrame
        From borough_monthly_trends.
        Must have columns: year_month, borough, and the metric column.
    metric : str
        Column name to plot.
    metric_label : str
        Human-readable label for the axis/title.
    """
    fig = go.Figure()

    for borough in BOROUGH_ORDER:
        bdf = df[df["borough"] == borough].sort_values("year_month")
        if bdf.empty:
            continue

        fig.add_trace(
            go.Scatter(
                x=bdf["year_month"],
                y=bdf[metric],
                mode="lines",
                name=borough.title(),
                line=dict(width=0.5, color=BOROUGH_COLORS.get(borough, COLORS["gray_400"])),
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
    Bar + line combo: complaint volume (bars) and average resolution hours (line).

    Parameters
    ----------
    df : pd.DataFrame
        From neighborhood_pulse_summary, aggregated to month level.
        Must have columns: year_month, total_complaints, avg_resolution_hours.
    borough : str or None
        If provided, filters and labels accordingly.
    """
    if borough:
        df = df[df["borough"] == borough].copy()

    # Aggregate to month level
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
            marker_color=COLORS["blue_100"],
            marker_line_color=COLORS["blue_400"],
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
            line=dict(color=COLORS["rose_500"], width=2),
            marker=dict(size=4),
            yaxis="y2",
            hovertemplate="%{y:.1f} hrs<extra></extra>",
        )
    )

    title_suffix = f" — {borough}" if borough else ""
    apply_default_layout(
        fig,
        title=f"Complaint Volume vs Resolution Time{title_suffix}",
        x_title="Month",
        y_title="Complaint Count",
    )
    fig.update_layout(
        yaxis2=dict(
            title="Avg Resolution Hours",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(size=10, color=COLORS["rose_500"]),
            titlefont=dict(size=11, color=COLORS["rose_500"]),
        ),
    )
    return fig
