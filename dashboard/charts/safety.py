"""
Chart factories for the Safety & Infrastructure page.

All functions receive a pandas DataFrame and return a
plotly.graph_objects.Figure. No Streamlit imports.

Data source: safety_infrastructure_corr, borough_monthly_trends
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from .theme import (
    BOROUGH_COLORS,
    BOROUGH_ORDER,
    COLORS,
    apply_default_layout,
)


def arrests_permits_scatter(
    df: pd.DataFrame,
    year_month: str,
) -> go.Figure:
    """
    Log-scaled scatter plot of arrests vs permits per zip code.

    Each point is a zip code. Color intensity represents felony percentage.
    Log scale reveals patterns hidden by outlier zip codes with very high counts.

    Parameters
    ----------
    df : pd.DataFrame
        From safety_infrastructure_corr, filtered to a single year_month.
        Must have columns: zip_code, log_arrests, log_permits, felony_pct,
        total_arrests, total_permits_issued.
    year_month : str
        Month for the title.
    """
    # Drop rows where both are zero (no data at all)
    df = df[(df["total_arrests"] > 0) | (df["total_permits_issued"] > 0)].copy()

    # felony_pct can be NULL — fill with 0 for color scale
    df["felony_pct_display"] = df["felony_pct"].fillna(0)

    fig = go.Figure(
        go.Scatter(
            x=df["log_permits"],
            y=df["log_arrests"],
            mode="markers",
            marker=dict(
                size=7,
                color=df["felony_pct_display"],
                colorscale=[
                    [0, COLORS["blue_100"]],
                    [0.5, COLORS["amber_500"]],
                    [1, COLORS["rose_500"]],
                ],
                cmin=0,
                cmax=0.5,
                colorbar=dict(
                    title="Felony %",
                    titlefont=dict(size=10),
                    tickfont=dict(size=9),
                    thickness=12,
                    len=0.6,
                    tickformat=".0%",
                ),
                line=dict(width=0.5, color=COLORS["slate_200"]),
            ),
            text=df["zip_code"],
            hovertemplate=(
                "ZIP %{text}<br>"
                "Arrests: %{customdata[0]:,}<br>"
                "Permits: %{customdata[1]:,}<br>"
                "Felony: %{customdata[2]:.1%}"
                "<extra></extra>"
            ),
            customdata=df[["total_arrests", "total_permits_issued", "felony_pct_display"]].values,
        )
    )

    apply_default_layout(
        fig,
        title=f"Arrests vs Permits by ZIP — {year_month}",
        x_title="Permits (log scale)",
        y_title="Arrests (log scale)",
        show_legend=False,
    )
    return fig


def arrests_trend_line(
    df: pd.DataFrame,
    borough: str | None = None,
) -> go.Figure:
    """
    Arrest category breakdown (felony, misdemeanor, violation) over time.

    Parameters
    ----------
    df : pd.DataFrame
        From borough_monthly_trends.
        Must have columns: year_month, borough, felony_count,
        misdemeanor_count.
    borough : str or None
        If provided, filters to that borough.
    """
    if borough:
        df = df[df["borough"] == borough].copy()
    else:
        df = (
            df.groupby("year_month", as_index=False)
            .agg(
                felony_count=("felony_count", "sum"),
                misdemeanor_count=("misdemeanor_count", "sum"),
                total_arrests=("total_arrests", "sum"),
            )
            .sort_values("year_month")
        )

    df = df.sort_values("year_month")

    categories = [
        ("felony_count", "Felony", COLORS["rose_500"]),
        ("misdemeanor_count", "Misdemeanor", COLORS["amber_500"]),
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
        title=f"Arrest Categories{title_suffix}",
        x_title="Month",
        y_title="Arrest Count",
    )
    return fig


def permits_trend_bar(
    df: pd.DataFrame,
    borough: str | None = None,
) -> go.Figure:
    """
    Stacked bar chart of permit types (new building, alteration, demolition) over time.

    Parameters
    ----------
    df : pd.DataFrame
        From borough_monthly_trends.
        Must have columns: year_month, borough, new_building_count (if available),
        total_permits_issued.
    borough : str or None
        If provided, filters to that borough.
    """
    if borough:
        df = df[df["borough"] == borough].copy()
    else:
        df = (
            df.groupby("year_month", as_index=False)
            .agg(total_permits_issued=("total_permits_issued", "sum"))
            .sort_values("year_month")
        )

    df = df.sort_values("year_month")

    fig = go.Figure(
        go.Bar(
            x=df["year_month"],
            y=df["total_permits_issued"],
            name="Total Permits",
            marker_color=COLORS["teal_500"],
            hovertemplate="%{y:,}<extra>Total Permits</extra>",
        )
    )

    title_suffix = f" — {borough}" if borough else " — All Boroughs"
    apply_default_layout(
        fig,
        title=f"Permit Issuance{title_suffix}",
        x_title="Month",
        y_title="Permits Issued",
        show_legend=False,
    )
    return fig


def arrests_per_permit_heatmap(
    df: pd.DataFrame,
) -> go.Figure:
    """
    Borough x month heatmap of arrests_per_permit ratio.

    Requires the safety_infrastructure_corr data joined with borough info.
    If borough data isn't available, a simplified version is shown.

    Parameters
    ----------
    df : pd.DataFrame
        From borough_monthly_trends with total_arrests and total_permits_issued.
        Must have columns: borough, year_month, total_arrests, total_permits_issued.
    """
    # Compute arrests per permit at borough level
    df = df.copy()
    df["arrests_per_permit"] = df.apply(
        lambda r: round(r["total_arrests"] / r["total_permits_issued"], 2)
        if r["total_permits_issued"] > 0
        else None,
        axis=1,
    )

    # Get recent months for readability
    recent_months = sorted(df["year_month"].unique())[-24:]
    df = df[df["year_month"].isin(recent_months)]

    # Pivot for heatmap
    pivot = df.pivot_table(
        index="borough",
        columns="year_month",
        values="arrests_per_permit",
        aggfunc="first",
    )

    # Reorder boroughs
    ordered = [b for b in BOROUGH_ORDER if b in pivot.index]
    pivot = pivot.reindex(ordered)

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=[b.title() for b in pivot.index.tolist()],
            colorscale=[
                [0, COLORS["teal_100"]],
                [0.5, COLORS["amber_100"]],
                [1, COLORS["rose_500"]],
            ],
            colorbar=dict(
                title="Arrests/Permit",
                titlefont=dict(size=10),
                tickfont=dict(size=9),
                thickness=12,
                len=0.6,
            ),
            hovertemplate=(
                "%{y} — %{x}<br>"
                "Arrests/Permit: %{z:.2f}"
                "<extra></extra>"
            ),
        )
    )

    apply_default_layout(
        fig,
        title="Arrests per Permit Ratio — Borough x Month",
        x_title="Month",
        y_title="",
        show_legend=False,
        height=320,
    )
    fig.update_layout(margin=dict(l=120))
    return fig
