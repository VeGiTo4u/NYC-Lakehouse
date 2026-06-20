"""
Chart factories for the Neighborhood Explorer page.

Dark theme with vibrant data-ink colors.

Data source: neighborhood_pulse_summary, borough_monthly_trends
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
    delta_color,
    format_number,
    health_tier_color,
    safe_float,
)


def pulse_score_gauge(
    score: float,
    borough_avg: float,
    city_avg: float,
    zip_code: str = "",
) -> go.Figure:
    """
    Pulse score donut indicator with reference markers.
    """
    score = safe_float(score)
    borough_avg = safe_float(borough_avg)
    city_avg = safe_float(city_avg)

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=score,
            delta={
                "reference": borough_avg,
                "increasing": {"color": COLORS["emerald_400"]},
                "decreasing": {"color": COLORS["rose_400"]},
                "suffix": " vs borough",
                "font": {"size": 12, "color": COLORS["text_secondary"]},
            },
            number={"font": {"size": 38, "color": COLORS["text_primary"]}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickwidth": 1,
                    "tickcolor": "rgba(255,255,255,0.1)",
                    "tickfont": {"size": 10, "color": COLORS["text_muted"]},
                },
                "bar": {"color": health_tier_color(score), "thickness": 0.7},
                "bgcolor": "rgba(255,255,255,0.04)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 25], "color": "rgba(244,63,94,0.1)"},
                    {"range": [25, 50], "color": "rgba(251,191,36,0.1)"},
                    {"range": [50, 75], "color": "rgba(99,102,241,0.1)"},
                    {"range": [75, 100], "color": "rgba(16,185,129,0.1)"},
                ],
                "threshold": {
                    "line": {"color": COLORS["text_secondary"], "width": 2},
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
    Pulse score over time with borough avg reference — gradient fill.
    """
    df = df.copy().sort_values("year_month")
    df["neighborhood_pulse_score"] = pd.to_numeric(df["neighborhood_pulse_score"], errors="coerce")
    df[borough_avg_col] = pd.to_numeric(df[borough_avg_col], errors="coerce")

    fig = go.Figure()

    # Borough average
    fig.add_trace(
        go.Scatter(
            x=df["year_month"],
            y=df[borough_avg_col],
            mode="lines",
            name="Borough Avg",
            line=dict(color="rgba(148,163,184,0.5)", width=1.5, dash="dash"),
            hovertemplate="%{y:.1f}<extra>Borough Avg</extra>",
        )
    )

    # Zip-level pulse score
    fig.add_trace(
        go.Scatter(
            x=df["year_month"],
            y=df["neighborhood_pulse_score"],
            mode="lines+markers",
            name=f"ZIP {zip_code}",
            line=dict(color=COLORS["indigo_400"], width=2.5),
            marker=dict(size=4, color=COLORS["indigo_400"]),
            fill="tozeroy",
            fillcolor="rgba(129,140,248,0.08)",
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
            line_color=COLORS["amber_400"],
            line_width=1,
            annotation_text="MTD",
            annotation_font_size=9,
            annotation_font_color=COLORS["amber_400"],
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
    Borough KPI comparison with grouped bars.
    """
    metrics = [
        ("total_complaints", "Complaints"),
        ("total_arrests", "Arrests"),
        ("total_permits_issued", "Permits"),
        ("total_inspections", "Inspections"),
    ]

    df_plot = df.copy()
    df_plot["_sort"] = df_plot["borough"].map(
        {b: i for i, b in enumerate(BOROUGH_ORDER)}
    )
    df_plot = df_plot.sort_values("_sort")

    fig = go.Figure()
    palette = [COLORS["indigo_400"], COLORS["rose_400"], COLORS["cyan_400"], COLORS["amber_400"]]

    for i, (col, label) in enumerate(metrics):
        fig.add_trace(
            go.Bar(
                x=df_plot["borough"].apply(str.title),
                y=df_plot[col],
                name=label,
                marker_color=palette[i],
                marker_line=dict(width=0),
                opacity=0.85,
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
    Horizontal bar chart: zip codes ranked by pulse score with health tier colors.
    """
    df = df.copy()
    df["neighborhood_pulse_score"] = pd.to_numeric(df["neighborhood_pulse_score"], errors="coerce")
    df = df.dropna(subset=["neighborhood_pulse_score"])
    df = df.sort_values("neighborhood_pulse_score", ascending=True).tail(30)
    colors = [health_tier_color(s) for s in df["neighborhood_pulse_score"]]

    fig = go.Figure(
        go.Bar(
            x=df["neighborhood_pulse_score"],
            y=df["zip_code"].astype(str),
            orientation="h",
            marker_color=colors,
            marker_line=dict(width=0),
            hovertemplate="ZIP %{y}: %{x:.1f}<extra></extra>",
        )
    )

    apply_default_layout(
        fig,
        title=f"Pulse Score by ZIP — {borough.title()}, {year_month}",
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
    Big-number indicator with MoM delta.
    """
    score = safe_float(score)
    delta_val = safe_float(delta) if delta is not None else 0

    fig = go.Figure(
        go.Indicator(
            mode="number+delta",
            value=score,
            number={
                "font": {"size": 48, "color": COLORS["text_primary"]},
            },
            delta={
                "reference": score - delta_val,
                "increasing": {"color": COLORS["emerald_400"]},
                "decreasing": {"color": COLORS["rose_400"]},
                "font": {"size": 16},
            },
            title={
                "text": f"ZIP {zip_code}" if zip_code else "Pulse Score",
                "font": {"size": 13, "color": COLORS["text_secondary"]},
            },
        )
    )

    apply_default_layout(fig, height=160, show_legend=False)
    fig.update_layout(margin=dict(l=16, r=16, t=40, b=8))
    return fig


def domain_radar(
    complaints: float,
    arrests: float,
    permits: float,
    inspections: float,
    borough: str = "",
) -> go.Figure:
    """
    Radar chart showing 4-domain balance.
    Values are normalized 0-100 for visual comparison.
    """
    categories = ["Complaints", "Safety", "Infrastructure", "Food Safety"]
    colors_list = [
        DOMAIN_COLORS["complaints"],
        DOMAIN_COLORS["safety"],
        DOMAIN_COLORS["infrastructure"],
        DOMAIN_COLORS["food"],
    ]

    # Normalize: higher is "better" — invert complaints and arrests
    values = [
        max(0, 100 - min(safe_float(complaints), 100)),
        max(0, 100 - min(safe_float(arrests), 100)),
        min(safe_float(permits), 100),
        min(safe_float(inspections), 100),
    ]
    values.append(values[0])  # close the polygon
    categories.append(categories[0])

    fig = go.Figure(
        go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            fillcolor="rgba(129,140,248,0.12)",
            line=dict(color=COLORS["indigo_400"], width=2),
            marker=dict(size=4, color=COLORS["indigo_400"]),
            hovertemplate="%{theta}: %{r:.0f}<extra></extra>",
        )
    )

    title = f"Domain Balance — {borough.title()}" if borough else "Domain Balance"
    apply_default_layout(fig, title=title, show_legend=False, height=340)
    fig.update_layout(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor="rgba(255,255,255,0.06)",
                tickfont=dict(size=8, color=COLORS["text_muted"]),
            ),
            angularaxis=dict(
                gridcolor="rgba(255,255,255,0.06)",
                tickfont=dict(size=10, color=COLORS["text_secondary"]),
            ),
        ),
        margin=dict(l=60, r=60, t=56, b=40),
    )
    return fig
