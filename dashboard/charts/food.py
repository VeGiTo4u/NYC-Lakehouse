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
    safe_float,
)


def grade_distribution_bar(
    df: pd.DataFrame,
    borough: str | None = None,
    year_month: str | None = None,
) -> go.Figure:
    """
    Horizontal stacked bar of grade A/B/C percentages.
    Fixed: properly extracts scalar values from aggregation.
    """
    df = df.copy()

    # Convert grade columns to numeric, handling None/'None'/Decimal
    for col in ["pct_grade_a", "pct_grade_b", "pct_grade_c"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["pct_grade_a"])
    if df.empty:
        fig = go.Figure()
        apply_default_layout(fig, title="No grade data available", height=300, show_legend=False)
        return fig

    # Aggregate to summary level if many zip codes
    if len(df) > 20:
        avg_a = safe_float(df["pct_grade_a"].mean()) * 100
        avg_b = safe_float(df["pct_grade_b"].mean()) * 100
        avg_c = safe_float(df["pct_grade_c"].mean()) * 100

        categories = ["Grade C", "Grade B", "Grade A"]
        values = [round(avg_c, 1), round(avg_b, 1), round(avg_a, 1)]
        colors = [GRADE_COLORS["C"], GRADE_COLORS["B"], GRADE_COLORS["A"]]

        fig = go.Figure(
            go.Bar(
                x=values,
                y=categories,
                orientation="h",
                marker_color=colors,
                marker_line=dict(width=0),
                text=[f"{v:.1f}%" for v in values],
                textposition="inside",
                textfont=dict(color=COLORS["bg_primary"], size=12, family="Plus Jakarta Sans"),
                hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
            )
        )
    else:
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
                    marker_line=dict(width=0),
                    hovertemplate=f"Grade {grade}: " + "%{x:.1f}%<extra></extra>",
                )
            )
        fig.update_layout(barmode="stack")

    title_parts = ["Grade Distribution"]
    if borough:
        title_parts.append(borough.title())
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
    Fixed: titlefont → title_font.
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
            line=dict(color=COLORS["amber_400"], width=2.5),
            fill="tozeroy",
            fillcolor="rgba(251,191,36,0.08)",
            hovertemplate="%{y:,}<extra>Food Complaints</extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=df["year_month"],
            y=df["critical_violation_count"],
            mode="lines",
            name="Critical Violations",
            line=dict(color=COLORS["rose_400"], width=2.5),
            yaxis="y2",
            hovertemplate="%{y:,}<extra>Critical Violations</extra>",
        )
    )

    title_suffix = f" — {borough.title()}" if borough else " — All Boroughs"
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
            tickfont=dict(size=10, color=COLORS["rose_400"]),
            title_font=dict(size=11, color=COLORS["rose_400"]),
        ),
    )
    return fig


def compliance_scatter(
    df: pd.DataFrame,
    year_month: str,
) -> go.Figure:
    """
    Scatter: pct_grade_a vs food_complaints_per_inspection per zip.
    Quadrant labels identify problem areas.
    """
    df = df.copy()
    for col in ["pct_grade_a", "food_complaints_per_inspection"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["pct_grade_a", "food_complaints_per_inspection"])
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
                    lambda v: max(5, min(v / 4, 18))
                ),
                color=COLORS["indigo_400"],
                opacity=0.7,
                line=dict(width=1, color=COLORS["indigo_300"]),
            ),
            text=df["zip_code"],
            hovertemplate=(
                "ZIP %{text}<br>"
                "Grade A: %{x:.1f}%<br>"
                "Complaints/Inspection: %{y:.2f}"
                "<extra></extra>"
            ),
        )
    )

    # Quadrant reference lines
    median_x = df["pct_grade_a"].median() * 100
    median_y = df["food_complaints_per_inspection"].median()

    fig.add_hline(
        y=median_y, line_dash="dot",
        line_color="rgba(255,255,255,0.15)", line_width=1,
    )
    fig.add_vline(
        x=median_x, line_dash="dot",
        line_color="rgba(255,255,255,0.15)", line_width=1,
    )

    # Quadrant annotations
    fig.add_annotation(
        x=95, y=df["food_complaints_per_inspection"].max() * 0.9,
        text="✓ Low Risk", showarrow=False,
        font=dict(size=9, color=COLORS["emerald_400"]),
    )
    fig.add_annotation(
        x=5, y=df["food_complaints_per_inspection"].max() * 0.9,
        text="⚠ High Risk", showarrow=False,
        font=dict(size=9, color=COLORS["rose_400"]),
    )

    apply_default_layout(
        fig,
        title=f"Grade A Rate vs Complaint Density — {year_month}",
        x_title="Grade A Rate (%)",
        y_title="Food Complaints / Inspection",
        show_legend=False,
    )
    return fig


def inspection_volume_bar(
    df: pd.DataFrame,
    borough: str | None = None,
) -> go.Figure:
    """
    Bar + line: monthly inspection volume and unique restaurants inspected.
    Fixed: titlefont → title_font.
    """
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
            marker_color=COLORS["emerald_400"],
            marker_line=dict(width=0),
            opacity=0.8,
            hovertemplate="%{y:,}<extra>Inspections</extra>",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=agg["year_month"],
            y=agg["unique_restaurants_inspected"],
            mode="lines+markers",
            name="Unique Restaurants",
            line=dict(color=COLORS["indigo_400"], width=2.5),
            marker=dict(size=4, color=COLORS["indigo_400"]),
            yaxis="y2",
            hovertemplate="%{y:,}<extra>Unique Restaurants</extra>",
        )
    )

    title_suffix = f" — {borough.title()}" if borough else ""
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
            tickfont=dict(size=10, color=COLORS["indigo_400"]),
            title_font=dict(size=11, color=COLORS["indigo_400"]),
        ),
    )
    return fig


def grade_trend_sparkline(
    df: pd.DataFrame,
    borough: str | None = None,
) -> go.Figure:
    """
    Sparkline showing Grade A rate trend over time.
    """
    df = df.copy()
    df["pct_grade_a"] = pd.to_numeric(df["pct_grade_a"], errors="coerce")
    df = df.dropna(subset=["pct_grade_a"])

    agg = (
        df.groupby("year_month", as_index=False)
        .agg(avg_grade_a=("pct_grade_a", "mean"))
        .sort_values("year_month")
    )

    agg["avg_grade_a"] = agg["avg_grade_a"] * 100

    fig = go.Figure(
        go.Scatter(
            x=agg["year_month"],
            y=agg["avg_grade_a"],
            mode="lines",
            line=dict(color=COLORS["emerald_400"], width=2.5),
            fill="tozeroy",
            fillcolor="rgba(52,211,153,0.08)",
            hovertemplate="%{x}<br>Grade A: %{y:.1f}%<extra></extra>",
        )
    )

    apply_default_layout(
        fig,
        title="Grade A Rate Trend",
        x_title="",
        y_title="Grade A %",
        show_legend=False,
        height=280,
    )
    fig.update_yaxes(range=[0, 100])
    return fig
