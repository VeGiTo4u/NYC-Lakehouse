"""
Visual theme for NYC Neighborhood Pulse dashboard.

Single source of truth for colors, fonts, and Plotly layout defaults.
All chart modules import from here to ensure consistent styling.

Design direction: professional municipal data report aesthetic.
No emojis. No purple gradients. No AI-slop rounded cards.
"""

from __future__ import annotations

import plotly.graph_objects as go

# ── Color Palette ──────────────────────────────────────────────

COLORS = {
    # Slate scale — text, backgrounds, borders
    "slate_900": "#0f172a",
    "slate_700": "#334155",
    "slate_600": "#475569",
    "slate_400": "#94a3b8",
    "slate_200": "#e2e8f0",
    "slate_100": "#f1f5f9",
    "slate_50": "#f8fafc",
    "white": "#ffffff",
    # Accent — primary action, KPI highlights
    "blue_600": "#2563eb",
    "blue_500": "#3b82f6",
    "blue_400": "#60a5fa",
    "blue_100": "#dbeafe",
    # Positive — score up, grade A, healthy
    "teal_600": "#0d9488",
    "teal_500": "#14b8a6",
    "teal_100": "#ccfbf1",
    # Warning — mid-range, grade B, moderate
    "amber_500": "#f59e0b",
    "amber_400": "#fbbf24",
    "amber_100": "#fef3c7",
    # Negative — score down, grade C, high crime
    "rose_500": "#f43f5e",
    "rose_400": "#fb7185",
    "rose_100": "#ffe4e6",
    # Neutral
    "gray_400": "#9ca3af",
    "gray_300": "#d1d5db",
}

# ── Borough Color Mapping ──────────────────────────────────────
# Consistent across every chart in every page.

BOROUGH_COLORS = {
    "MANHATTAN": "#3b82f6",
    "BROOKLYN": "#10b981",
    "BRONX": "#f59e0b",
    "QUEENS": "#8b5cf6",
    "STATEN ISLAND": "#64748b",
}

BOROUGH_ORDER = ["MANHATTAN", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND"]

# ── Grade Colors ───────────────────────────────────────────────

GRADE_COLORS = {
    "A": "#14b8a6",
    "B": "#f59e0b",
    "C": "#f43f5e",
}

# ── Categorical Palette ────────────────────────────────────────
# For multi-series charts where borough colors don't apply.

CATEGORICAL_PALETTE = [
    "#2563eb",  # blue
    "#14b8a6",  # teal
    "#f59e0b",  # amber
    "#f43f5e",  # rose
    "#64748b",  # slate
    "#8b5cf6",  # violet (used sparingly)
    "#06b6d4",  # cyan
    "#ec4899",  # pink
]

# ── Typography ─────────────────────────────────────────────────

FONT_FAMILY = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
TITLE_SIZE = 16
AXIS_LABEL_SIZE = 11
TICK_SIZE = 10

# ── Layout Defaults ────────────────────────────────────────────


def apply_default_layout(
    fig: go.Figure,
    title: str = "",
    height: int = 420,
    show_legend: bool = True,
    x_title: str = "",
    y_title: str = "",
) -> go.Figure:
    """
    Applies the standard professional layout to a Plotly figure.

    Keeps charts clean and data-focused: white background, minimal grid,
    no chartjunk, consistent font sizing.
    """
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(
                family=FONT_FAMILY,
                size=TITLE_SIZE,
                color=COLORS["slate_900"],
            ),
            x=0,
            xanchor="left",
            y=0.98,
            yanchor="top",
        ),
        font=dict(
            family=FONT_FAMILY,
            size=AXIS_LABEL_SIZE,
            color=COLORS["slate_600"],
        ),
        plot_bgcolor=COLORS["white"],
        paper_bgcolor=COLORS["white"],
        height=height,
        margin=dict(l=60, r=24, t=56, b=48),
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.22,
            xanchor="left",
            x=0,
            font=dict(size=TICK_SIZE, color=COLORS["slate_600"]),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            title=dict(
                text=x_title,
                font=dict(size=AXIS_LABEL_SIZE, color=COLORS["slate_600"]),
            ),
            tickfont=dict(size=TICK_SIZE, color=COLORS["slate_600"]),
            gridcolor=COLORS["slate_100"],
            gridwidth=1,
            showline=True,
            linecolor=COLORS["slate_200"],
            linewidth=1,
            zeroline=False,
        ),
        yaxis=dict(
            title=dict(
                text=y_title,
                font=dict(size=AXIS_LABEL_SIZE, color=COLORS["slate_600"]),
            ),
            tickfont=dict(size=TICK_SIZE, color=COLORS["slate_600"]),
            gridcolor=COLORS["slate_100"],
            gridwidth=1,
            showline=False,
            zeroline=False,
        ),
        hoverlabel=dict(
            bgcolor=COLORS["slate_900"],
            font_size=11,
            font_family=FONT_FAMILY,
            font_color=COLORS["white"],
        ),
    )
    return fig


def format_number(n: float | int | None) -> str:
    """
    Human-readable number formatting.

    Examples: 0 -> '0', 1234 -> '1,234', 12345 -> '12.3K', 1234567 -> '1.2M'
    """
    if n is None:
        return "N/A"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 10_000:
        return f"{n / 1_000:.1f}K"
    if isinstance(n, float) and n != int(n):
        return f"{n:,.2f}"
    return f"{int(n):,}"


def health_tier_color(score: float) -> str:
    """Returns a color based on the pulse score health tier."""
    if score >= 75:
        return COLORS["teal_500"]
    if score >= 50:
        return COLORS["blue_500"]
    if score >= 25:
        return COLORS["amber_500"]
    return COLORS["rose_500"]


def delta_color(delta: float | None) -> str:
    """Returns teal for positive, rose for negative, gray for zero/null."""
    if delta is None or delta == 0:
        return COLORS["gray_400"]
    return COLORS["teal_500"] if delta > 0 else COLORS["rose_500"]


def mtd_annotation(fig: go.Figure, x_pos: str, y_pos: float = 0) -> go.Figure:
    """Adds a 'Month-to-Date' annotation at the specified x position."""
    fig.add_annotation(
        x=x_pos,
        y=y_pos,
        text="MTD",
        showarrow=False,
        font=dict(size=9, color=COLORS["amber_500"], family=FONT_FAMILY),
        yshift=12,
    )
    return fig
