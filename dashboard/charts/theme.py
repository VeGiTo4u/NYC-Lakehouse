"""
Visual theme for NYC Neighborhood Pulse dashboard.

Premium dark-first design system with glassmorphism effects,
gradient accents, and vibrant data-ink colors optimized for
dark backgrounds.

All chart modules import from here to ensure consistent styling.
"""

from __future__ import annotations

import plotly.graph_objects as go

# ── Color Palette — Dark First ─────────────────────────────────

COLORS = {
    # Background scale — deep navy to near-black
    "bg_primary": "#0f0f1a",
    "bg_card": "#1a1a2e",
    "bg_elevated": "#232342",
    "bg_hover": "#2a2a4a",
    # Text scale
    "text_primary": "#e2e8f0",
    "text_secondary": "#94a3b8",
    "text_muted": "#64748b",
    "text_faint": "#475569",
    # Borders & surfaces
    "border": "rgba(255,255,255,0.08)",
    "border_active": "rgba(99,102,241,0.4)",
    "glass": "rgba(255,255,255,0.04)",
    "glass_hover": "rgba(255,255,255,0.08)",
    "white": "#ffffff",
    # Primary — Indigo
    "indigo_500": "#6366f1",
    "indigo_400": "#818cf8",
    "indigo_300": "#a5b4fc",
    "indigo_600": "#4f46e5",
    "indigo_100": "rgba(99,102,241,0.15)",
    # Accent — Cyan
    "cyan_400": "#22d3ee",
    "cyan_500": "#06b6d4",
    "cyan_300": "#67e8f9",
    "cyan_100": "rgba(6,182,212,0.15)",
    # Positive — Emerald
    "emerald_400": "#34d399",
    "emerald_500": "#10b981",
    "emerald_300": "#6ee7b7",
    "emerald_100": "rgba(16,185,129,0.15)",
    # Warning — Amber
    "amber_400": "#fbbf24",
    "amber_500": "#f59e0b",
    "amber_300": "#fcd34d",
    "amber_100": "rgba(245,158,11,0.15)",
    # Danger — Rose
    "rose_400": "#fb7185",
    "rose_500": "#f43f5e",
    "rose_300": "#fda4af",
    "rose_100": "rgba(244,63,94,0.15)",
    # Violet
    "violet_400": "#a78bfa",
    "violet_500": "#8b5cf6",
    # Pink
    "pink_400": "#f472b6",
    # Neutral
    "slate_400": "#94a3b8",
    "slate_300": "#cbd5e1",
    "slate_600": "#475569",
}

# ── Borough Color Mapping ──────────────────────────────────────
# Vivid, saturated colors that pop on dark backgrounds

BOROUGH_COLORS = {
    "MANHATTAN": "#818cf8",   # indigo
    "BROOKLYN": "#34d399",    # emerald
    "BRONX": "#fbbf24",       # amber
    "QUEENS": "#a78bfa",      # violet
    "STATEN ISLAND": "#94a3b8",  # slate
}

BOROUGH_ORDER = ["MANHATTAN", "BROOKLYN", "QUEENS", "BRONX", "STATEN ISLAND"]

# ── Grade Colors ───────────────────────────────────────────────

GRADE_COLORS = {
    "A": "#34d399",  # emerald
    "B": "#fbbf24",  # amber
    "C": "#fb7185",  # rose
}

# ── Categorical Palette ────────────────────────────────────────

CATEGORICAL_PALETTE = [
    "#818cf8",  # indigo
    "#34d399",  # emerald
    "#fbbf24",  # amber
    "#fb7185",  # rose
    "#22d3ee",  # cyan
    "#a78bfa",  # violet
    "#f472b6",  # pink
    "#94a3b8",  # slate
]

# ── Domain Colors (for radar/composite views) ──────────────────

DOMAIN_COLORS = {
    "complaints": "#818cf8",
    "safety": "#fb7185",
    "infrastructure": "#22d3ee",
    "food": "#34d399",
}

# ── Typography ─────────────────────────────────────────────────

FONT_FAMILY = (
    "'Plus Jakarta Sans', Inter, -apple-system, BlinkMacSystemFont, "
    "'Segoe UI', Roboto, sans-serif"
)
TITLE_SIZE = 15
SUBTITLE_SIZE = 12
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
    Applies the dark professional layout to a Plotly figure.

    Dark backgrounds, subtle grid, vibrant data-ink colors.
    """
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(
                family=FONT_FAMILY,
                size=TITLE_SIZE,
                color=COLORS["text_primary"],
            ),
            x=0,
            xanchor="left",
            y=0.98,
            yanchor="top",
        ),
        font=dict(
            family=FONT_FAMILY,
            size=AXIS_LABEL_SIZE,
            color=COLORS["text_secondary"],
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=60, r=24, t=56, b=48),
        showlegend=show_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.22,
            xanchor="left",
            x=0,
            font=dict(size=TICK_SIZE, color=COLORS["text_secondary"]),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            title=dict(
                text=x_title,
                font=dict(size=AXIS_LABEL_SIZE, color=COLORS["text_muted"]),
            ),
            tickfont=dict(size=TICK_SIZE, color=COLORS["text_muted"]),
            gridcolor="rgba(255,255,255,0.06)",
            gridwidth=1,
            showline=True,
            linecolor="rgba(255,255,255,0.1)",
            linewidth=1,
            zeroline=False,
        ),
        yaxis=dict(
            title=dict(
                text=y_title,
                font=dict(size=AXIS_LABEL_SIZE, color=COLORS["text_muted"]),
            ),
            tickfont=dict(size=TICK_SIZE, color=COLORS["text_muted"]),
            gridcolor="rgba(255,255,255,0.06)",
            gridwidth=1,
            showline=False,
            zeroline=False,
        ),
        hoverlabel=dict(
            bgcolor=COLORS["bg_elevated"],
            font_size=11,
            font_family=FONT_FAMILY,
            font_color=COLORS["text_primary"],
            bordercolor=COLORS["border_active"],
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
    try:
        n = float(n)
    except (ValueError, TypeError):
        return "N/A"
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 10_000:
        return f"{n / 1_000:.1f}K"
    if isinstance(n, float) and n != int(n):
        return f"{n:,.1f}"
    return f"{int(n):,}"


def health_tier_color(score: float) -> str:
    """Returns a color based on the pulse score health tier."""
    try:
        score = float(score)
    except (ValueError, TypeError):
        return COLORS["slate_400"]
    if score >= 75:
        return COLORS["emerald_400"]
    if score >= 50:
        return COLORS["cyan_400"]
    if score >= 25:
        return COLORS["amber_400"]
    return COLORS["rose_400"]


def delta_color(delta: float | None) -> str:
    """Returns emerald for positive, rose for negative, slate for zero/null."""
    if delta is None or delta == 0:
        return COLORS["slate_400"]
    return COLORS["emerald_400"] if delta > 0 else COLORS["rose_400"]


def safe_float(val, default=0.0) -> float:
    """Safely convert a value (possibly Decimal/Series) to float."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default
