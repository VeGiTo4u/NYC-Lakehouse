"""
Chart factories for the Neighborhood Explorer page.

All functions receive a pandas DataFrame and return a
plotly.graph_objects.Figure. No Streamlit imports.

Data source: neighborhood_pulse_summary, borough_monthly_trends
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import (
    BOROUGH_COLORS,
    BOROUGH_ORDER,
    COLORS,
    apply_default_layout,
    delta_color,
    format_number,
    health_tier_color,
)


def pulse_score_gauge(
    score: float,
    borough_avg: float,
    city_avg: float,
    zip_code: str = "",
) -> go.Figure:
    """
    Single-zip pulse score gauge with borough and city reference markers.

    Parameters
    ----------
    score : float
        Current zip's neighborhood pulse score (0-100).
    borough_avg : float
        Borough-level average for context.
    city_avg : float
        City-wide average for context.
    zip_code : str
        Zip code label for the title.
    """
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=score,
            delta={
                "reference": borough_avg,
                "increasing": {"color": COLORS["teal_500"]},
                "decreasing": {"color": COLORS["rose_500"]},
                "suffix": " vs borough",
                "font": {"size": 12},
            },
            number={"font": {"size": 36, "color": COLORS["slate_900"]}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": COLORS["slate_200"],
                    "tickfont": {"size": 10, "color": COLORS["slate_600"]},
                },
                "bar": {"color": health_tier_color(score), "thickness": 0.7},
                "bgcolor": COLORS["slate_100"],
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 25], "color": COLORS["rose_100"]},
                    {"range": [25, 50], "color": COLORS["amber_100"]},
                    {"range": [50, 75], "color": COLORS["blue_100"]},
                    {"range": [75, 100], "color": COLORS["teal_100"]},
                ],
                "threshold": {
                    "line": {"color": COLORS["slate_700"], "width": 2},
                    "thickness": 0.8,
                    "value": city_avg,
                },
            },
        )
    )

    title = f"Pulse Score — {zip_code}" if zip_code else "Pulse Score"
    apply_default_layout(fig, title=title, height=280, show_legend=False)
    fig.update_layout(margin=dict(l=32, r=32, t=56, b=16))
    return fig


def pulse_time_series(
    df: pd.DataFrame,
    zip_code: str,
    borough_avg_col: str = "borough_avg_pulse_score",
) -> go.Figure:
    """
    Pulse score over time for a single zip code with borough avg reference.

    Parameters
    ----------
    df : pd.DataFrame
        Filtered to a single zip_code from neighborhood_pulse_summary.
        Must have columns: year_month, neighborhood_pulse_score,
        borough_avg_pulse_score, is_complete_month.
    zip_code : str
        Label for the title.
    borough_avg_col : str
        Column name for the borough average line.
    """
    df = df.sort_values("year_month")

    fig = go.Figure()

    # Borough average — dashed reference line
    fig.add_trace(
        go.Scatter(
            x=df["year_month"],
            y=df[borough_avg_col],
            mode="lines",
            name="Borough Avg",
            line=dict(color=COLORS["gray_400"], width=1.5, dash="dash"),
            hovertemplate="%{y:.1f}<extra>Borough Avg</extra>",
        )
    )

    # Zip-level pulse score — primary line
    fig.add_trace(
        go.Scatter(
            x=df["year_month"],
            y=df["neighborhood_pulse_score"],
            mode="lines+markers",
            name=f"ZIP {zip_code}",
            line=dict(color=COLORS["blue_600"], width=2),
            marker=dict(size=4, color=COLORS["blue_600"]),
            hovertemplate="%{y:.1f}<extra>ZIP " + zip_code + "</extra>",
        )
    )

    # Mark MTD months
    mtd_rows = df[df["is_complete_month"] == False]  # noqa: E712
    if not mtd_rows.empty:
        last_ym = mtd_rows["year_month"].iloc[-1]
        fig.add_vline(
            x=last_ym,
            line_dash="dot",
            line_color=COLORS["amber_500"],
            line_width=1,
            annotation_text="MTD",
            annotation_font_size=9,
            annotation_font_color=COLORS["amber_500"],
        )

    apply_default_layout(
        fig,
        title=f"Pulse Score Trend — ZIP {zip_code}",
        x_title="Month",
        y_title="Pulse Score",
    )
    fig.update_yaxes(range=[0, 105])
    return fig


def borough_comparison_bar(
    df: pd.DataFrame,
    year_month: str,
) -> go.Figure:
    """
    Side-by-side comparison of borough-level KPI totals for a given month.

    Parameters
    ----------
    df : pd.DataFrame
        From borough_monthly_trends, filtered to a single year_month.
        Must have columns: borough, total_complaints, total_arrests,
        total_permits_issued, total_inspections.
    year_month : str
        Label for the title.
    """
    metrics = [
        ("total_complaints", "Complaints"),
        ("total_arrests", "Arrests"),
        ("total_permits_issued", "Permits"),
        ("total_inspections", "Inspections"),
    ]

    # Normalize each metric to 0-100 scale for comparable bars
    df_plot = df.copy()
    for col, _ in metrics:
        max_val = df_plot[col].max()
        if max_val > 0:
            df_plot[f"{col}_norm"] = (df_plot[col] / max_val * 100).round(1)
        else:
            df_plot[f"{col}_norm"] = 0

    # Sort boroughs in canonical order
    df_plot["_sort"] = df_plot["borough"].map(
        {b: i for i, b in enumerate(BOROUGH_ORDER)}
    )
    df_plot = df_plot.sort_values("_sort")

    fig = go.Figure()
    palette = [COLORS["blue_600"], COLORS["rose_500"], COLORS["teal_500"], COLORS["amber_500"]]

    for i, (col, label) in enumerate(metrics):
        fig.add_trace(
            go.Bar(
                x=df_plot["borough"],
                y=df_plot[col],
                name=label,
                marker_color=palette[i],
                hovertemplate="%{x}: %{y:,}<extra>" + label + "</extra>",
            )
        )

    apply_default_layout(
        fig,
        title=f"Borough Comparison — {year_month}",
        x_title="",
        y_title="Count",
    )
    fig.update_layout(barmode="group")
    return fig


def pulse_score_distribution(
    df: pd.DataFrame,
    borough: str,
    year_month: str,
) -> go.Figure:
    """
    Horizontal bar chart: all zip codes in a borough ranked by pulse score.

    Parameters
    ----------
    df : pd.DataFrame
        From neighborhood_pulse_summary, filtered to borough + year_month.
        Must have columns: zip_code, neighborhood_pulse_score.
    borough : str
        Borough name for the title.
    year_month : str
        Month for the title.
    """
    df = df.sort_values("neighborhood_pulse_score", ascending=True).tail(30)
    colors = [health_tier_color(s) for s in df["neighborhood_pulse_score"]]

    fig = go.Figure(
        go.Bar(
            x=df["neighborhood_pulse_score"],
            y=df["zip_code"].astype(str),
            orientation="h",
            marker_color=colors,
            hovertemplate="ZIP %{y}: %{x:.1f}<extra></extra>",
        )
    )

    apply_default_layout(
        fig,
        title=f"Pulse Score by ZIP — {borough}, {year_month}",
        x_title="Pulse Score",
        y_title="",
        show_legend=False,
        height=max(360, len(df) * 18),
    )
    fig.update_xaxes(range=[0, 105])
    return fig


def mom_delta_indicator(
    score: float,
    delta: float | None,
    zip_code: str = "",
) -> go.Figure:
    """
    Big-number indicator showing current pulse score and month-over-month change.

    Parameters
    ----------
    score : float
        Current pulse score.
    delta : float | None
        Month-over-month change. None for earliest month.
    zip_code : str
        Label for the title.
    """
    fig = go.Figure(
        go.Indicator(
            mode="number+delta",
            value=score,
            number={
                "font": {"size": 48, "color": COLORS["slate_900"]},
                "suffix": "",
            },
            delta={
                "reference": score - (delta if delta else 0),
                "increasing": {"color": COLORS["teal_500"]},
                "decreasing": {"color": COLORS["rose_500"]},
                "font": {"size": 16},
            },
            title={
                "text": f"ZIP {zip_code}" if zip_code else "Pulse Score",
                "font": {"size": 13, "color": COLORS["slate_600"]},
            },
        )
    )

    apply_default_layout(fig, height=160, show_legend=False)
    fig.update_layout(margin=dict(l=16, r=16, t=40, b=8))
    return fig
