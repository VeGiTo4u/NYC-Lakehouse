"""
Chart factories for the Food Safety Compliance page.

All functions receive a pandas DataFrame and return a
plotly.graph_objects.Figure. No Streamlit imports.

Data source: food_compliance_overview, borough_monthly_trends
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import (
    BOROUGH_COLORS,
    BOROUGH_ORDER,
    COLORS,
    GRADE_COLORS,
    apply_default_layout,
    format_number,
)


def grade_distribution_bar(
    df: pd.DataFrame,
    borough: str | None = None,
    year_month: str | None = None,
) -> go.Figure:
    """
    Stacked horizontal bar of grade A/B/C percentages across zip codes.

    Parameters
    ----------
    df : pd.DataFrame
        From food_compliance_overview. Optionally pre-filtered.
        Must have columns: zip_code, pct_grade_a, pct_grade_b, pct_grade_c.
    borough : str or None
        For the title.
    year_month : str or None
        For the title.
    """
    # Filter out rows with no grade data
    df = df.dropna(subset=["pct_grade_a"]).copy()
    if df.empty:
        fig = go.Figure()
        apply_default_layout(fig, title="No grade data available", height=300, show_legend=False)
        return fig

    # Aggregate to borough level if many zip codes
    if len(df) > 20:
        agg = df.agg(
            pct_grade_a=("pct_grade_a", "mean"),
            pct_grade_b=("pct_grade_b", "mean"),
            pct_grade_c=("pct_grade_c", "mean"),
        )
        categories = ["Grade A", "Grade B", "Grade C"]
        values = [
            round(agg["pct_grade_a"] * 100, 1),
            round(agg["pct_grade_b"] * 100, 1),
            round(agg["pct_grade_c"] * 100, 1),
        ]
        colors = [GRADE_COLORS["A"], GRADE_COLORS["B"], GRADE_COLORS["C"]]

        fig = go.Figure(
            go.Bar(
                x=values,
                y=categories,
                orientation="h",
                marker_color=colors,
                text=[f"{v:.1f}%" for v in values],
                textposition="inside",
                textfont=dict(color=COLORS["white"], size=12),
                hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            )
        )
    else:
        # Show individual zip codes
        df = df.sort_values("pct_grade_a", ascending=True)

        fig = go.Figure()
        for grade, col, color in [
            ("C", "pct_grade_c", GRADE_COLORS["C"]),
            ("B", "pct_grade_b", GRADE_COLORS["B"]),
            ("A", "pct_grade_a", GRADE_COLORS["A"]),
        ]:
            fig.add_trace(
                go.Bar(
                    x=(df[col] * 100).round(1),
                    y=df["zip_code"].astype(str),
                    orientation="h",
                    name=f"Grade {grade}",
                    marker_color=color,
                    hovertemplate=f"Grade {grade}: " + "%{x:.1f}%<extra></extra>",
                )
            )
        fig.update_layout(barmode="stack")

    title_parts = ["Grade Distribution"]
    if borough:
        title_parts.append(borough)
    if year_month:
        title_parts.append(year_month)
    title = " — ".join(title_parts)

    apply_default_layout(
        fig,
        title=title,
        x_title="Percentage",
        y_title="",
        height=max(320, min(len(df) * 22, 600)),
    )
    fig.update_xaxes(range=[0, 105])
    return fig


def food_complaint_trend(
    df: pd.DataFrame,
    borough: str | None = None,
) -> go.Figure:
    """
    Dual-axis line: food complaints vs critical violations over time.

    Parameters
    ----------
    df : pd.DataFrame
        From borough_monthly_trends.
        Must have columns: year_month, borough, food_complaint_count,
        critical_violation_count.
    borough : str or None
        If provided, filters to that borough.
    """
    if borough:
        df = df[df["borough"] == borough].copy()
    else:
        df = (
            df.groupby("year_month", as_index=False)
            .agg(
                food_complaint_count=("food_complaint_count", "sum"),
                critical_violation_count=("critical_violation_count", "sum"),
            )
        )

    df = df.sort_values("year_month")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["year_month"],
            y=df["food_complaint_count"],
            mode="lines",
            name="Food Complaints (311)",
            line=dict(color=COLORS["amber_500"], width=2),
            hovertemplate="%{y:,}<extra>Food Complaints</extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["year_month"],
            y=df["critical_violation_count"],
            mode="lines",
            name="Critical Violations",
            line=dict(color=COLORS["rose_500"], width=2),
            yaxis="y2",
            hovertemplate="%{y:,}<extra>Critical Violations</extra>",
        )
    )

    title_suffix = f" — {borough}" if borough else " — All Boroughs"
    apply_default_layout(
        fig,
        title=f"Food Complaints vs Critical Violations{title_suffix}",
        x_title="Month",
        y_title="Food Complaints",
    )
    fig.update_layout(
        yaxis2=dict(
            title="Critical Violations",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(size=10, color=COLORS["rose_500"]),
            titlefont=dict(size=11, color=COLORS["rose_500"]),
        ),
    )
    return fig


def compliance_scatter(
    df: pd.DataFrame,
    year_month: str,
) -> go.Figure:
    """
    Scatter: pct_grade_a vs food_complaints_per_inspection per zip.
    Identifies problem areas — low grade A + high complaint density.

    Parameters
    ----------
    df : pd.DataFrame
        From food_compliance_overview, filtered to a single year_month.
        Must have columns: zip_code, pct_grade_a, food_complaints_per_inspection,
        total_inspections.
    year_month : str
        Month for the title.
    """
    df = df.dropna(subset=["pct_grade_a", "food_complaints_per_inspection"]).copy()
    if df.empty:
        fig = go.Figure()
        apply_default_layout(fig, title="No compliance data available", height=300, show_legend=False)
        return fig

    fig = go.Figure(
        go.Scatter(
            x=df["pct_grade_a"] * 100,
            y=df["food_complaints_per_inspection"],
            mode="markers",
            marker=dict(
                size=df["total_inspections"].clip(upper=100).apply(
                    lambda v: max(4, min(v / 5, 16))
                ),
                color=COLORS["blue_500"],
                opacity=0.6,
                line=dict(width=0.5, color=COLORS["slate_200"]),
            ),
            text=df["zip_code"],
            hovertemplate=(
                "ZIP %{text}<br>"
                "Grade A: %{x:.1f}%<br>"
                "Food Complaints/Inspection: %{y:.2f}"
                "<extra></extra>"
            ),
        )
    )

    # Add quadrant reference lines
    fig.add_hline(
        y=df["food_complaints_per_inspection"].median(),
        line_dash="dot",
        line_color=COLORS["gray_400"],
        line_width=1,
    )
    fig.add_vline(
        x=df["pct_grade_a"].median() * 100,
        line_dash="dot",
        line_color=COLORS["gray_400"],
        line_width=1,
    )

    apply_default_layout(
        fig,
        title=f"Food Safety: Grade A Rate vs Complaint Density — {year_month}",
        x_title="Grade A Rate (%)",
        y_title="Food Complaints per Inspection",
        show_legend=False,
    )
    return fig


def inspection_volume_bar(
    df: pd.DataFrame,
    borough: str | None = None,
) -> go.Figure:
    """
    Bar chart of monthly inspection volume and unique restaurants inspected.

    Parameters
    ----------
    df : pd.DataFrame
        From food_compliance_overview, aggregated to month level.
        Must have columns: year_month, total_inspections,
        unique_restaurants_inspected.
    borough : str or None
        For the title.
    """
    # Aggregate to month level
    agg = (
        df.groupby("year_month", as_index=False)
        .agg(
            total_inspections=("total_inspections", "sum"),
            unique_restaurants_inspected=("unique_restaurants_inspected", "sum"),
        )
        .sort_values("year_month")
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=agg["year_month"],
            y=agg["total_inspections"],
            name="Inspections",
            marker_color=COLORS["teal_500"],
            hovertemplate="%{y:,}<extra>Inspections</extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=agg["year_month"],
            y=agg["unique_restaurants_inspected"],
            mode="lines+markers",
            name="Unique Restaurants",
            line=dict(color=COLORS["blue_600"], width=2),
            marker=dict(size=4),
            yaxis="y2",
            hovertemplate="%{y:,}<extra>Unique Restaurants</extra>",
        )
    )

    title_suffix = f" — {borough}" if borough else ""
    apply_default_layout(
        fig,
        title=f"Inspection Volume{title_suffix}",
        x_title="Month",
        y_title="Inspection Count",
    )
    fig.update_layout(
        yaxis2=dict(
            title="Unique Restaurants",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(size=10, color=COLORS["blue_600"]),
            titlefont=dict(size=11, color=COLORS["blue_600"]),
        ),
    )
    return fig
