"""
Chart factories for the Safety & Infrastructure page.

Dark theme. Fixed titlefont deprecation.

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
    safe_float,
)


def arrests_permits_scatter(
    df: pd.DataFrame,
    year_month: str,
) -> go.Figure:
    """
    Scatter of arrests vs permits per zip code.
    Color = felony percentage. Dark theme with glow markers.
    """
    df = df[(df["total_arrests"] > 0) | (df["total_permits_issued"] > 0)].copy()
    df["felony_pct_display"] = pd.to_numeric(df["felony_pct"], errors="coerce").fillna(0)

    fig = go.Figure(
        go.Scatter(
            x=df["log_permits"],
            y=df["log_arrests"],
            mode="markers",
            marker=dict(
                size=8,
                color=df["felony_pct_display"],
                colorscale=[
                    [0, COLORS["cyan_400"]],
                    [0.5, COLORS["amber_400"]],
                    [1, COLORS["rose_400"]],
                ],
                cmin=0,
                cmax=0.5,
                colorbar=dict(
                    title=dict(text="Felony %", font=dict(size=10, color=COLORS["text_secondary"])),
                    tickfont=dict(size=9, color=COLORS["text_muted"]),
                    thickness=12,
                    len=0.6,
                    tickformat=".0%",
                    bgcolor="rgba(0,0,0,0)",
                    borderwidth=0,
                ),
                line=dict(width=1, color="rgba(255,255,255,0.15)"),
                opacity=0.85,
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
    Arrest category breakdown over time with area fills.
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
        ("felony_count", "Felony", COLORS["rose_400"], "rgba(251,113,133,0.1)"),
        ("misdemeanor_count", "Misdemeanor", COLORS["amber_400"], "rgba(251,191,36,0.08)"),
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
    Monthly permit issuance volume with gradient bars.
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
            marker_color=COLORS["cyan_400"],
            marker_line=dict(width=0),
            opacity=0.8,
            hovertemplate="%{y:,}<extra>Total Permits</extra>",
        )
    )

    title_suffix = f" — {borough.title()}" if borough else " — All Boroughs"
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
    Borough × month heatmap of arrests per permit ratio.
    """
    df = df.copy()
    df["arrests_per_permit"] = df.apply(
        lambda r: round(safe_float(r["total_arrests"]) / safe_float(r["total_permits_issued"], 1), 2)
        if safe_float(r["total_permits_issued"]) > 0
        else None,
        axis=1,
    )

    recent_months = sorted(df["year_month"].unique())[-24:]
    df = df[df["year_month"].isin(recent_months)]

    pivot = df.pivot_table(
        index="borough",
        columns="year_month",
        values="arrests_per_permit",
        aggfunc="first",
    )

    ordered = [b for b in BOROUGH_ORDER if b in pivot.index]
    pivot = pivot.reindex(ordered)

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=[b.title() for b in pivot.index.tolist()],
            colorscale=[
                [0, "rgba(34,211,238,0.2)"],
                [0.5, "rgba(251,191,36,0.5)"],
                [1, COLORS["rose_400"]],
            ],
            colorbar=dict(
                title=dict(text="Arrests/Permit", font=dict(size=10, color=COLORS["text_secondary"])),
                tickfont=dict(size=9, color=COLORS["text_muted"]),
                thickness=12,
                len=0.6,
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
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
        title="Arrests per Permit — Borough × Month",
        x_title="Month",
        y_title="",
        show_legend=False,
        height=320,
    )
    fig.update_layout(margin=dict(l=120))
    return fig


def crime_composition_donut(
    felonies: int,
    misdemeanors: int,
    violations: int,
) -> go.Figure:
    """
    Donut chart showing felony/misdemeanor/violation composition.
    """
    labels = ["Felonies", "Misdemeanors", "Violations"]
    values = [int(felonies), int(misdemeanors), int(violations)]
    colors = [COLORS["rose_400"], COLORS["amber_400"], COLORS["slate_400"]]

    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.6,
            marker=dict(
                colors=colors,
                line=dict(color=COLORS["bg_primary"], width=2),
            ),
            textinfo="percent+label",
            textfont=dict(size=10, color=COLORS["text_primary"]),
            hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>",
        )
    )

    apply_default_layout(
        fig,
        title="Crime Composition",
        show_legend=False,
        height=320,
    )
    fig.update_layout(margin=dict(l=16, r=16, t=56, b=16))
    return fig
