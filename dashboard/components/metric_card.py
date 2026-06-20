"""
Premium metric card component with glassmorphism effects.

Renders custom HTML/CSS KPI cards with colored accent borders,
delta badges, and icon support. Replaces plain st.metric.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st


def _delta_html(delta: Optional[str], delta_color: str = "normal") -> str:
    """Renders a delta badge with colored background."""
    if not delta:
        return ""

    is_positive = delta.startswith("+") or (not delta.startswith("-") and delta != "0")
    is_negative = delta.startswith("-")

    if delta_color == "inverse":
        is_positive, is_negative = is_negative, is_positive

    if is_positive:
        bg = "rgba(16,185,129,0.15)"
        fg = "#34d399"
        arrow = "↑"
    elif is_negative:
        bg = "rgba(244,63,94,0.15)"
        fg = "#fb7185"
        arrow = "↓"
    else:
        bg = "rgba(148,163,184,0.15)"
        fg = "#94a3b8"
        arrow = "→"

    return (
        f"<span style='"
        f"display:inline-block; padding:2px 8px; border-radius:12px; "
        f"font-size:0.72rem; font-weight:600; "
        f"background:{bg}; color:{fg}; margin-top:4px;"
        f"'>{arrow} {delta}</span>"
    )


def render_metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: str = "normal",
    icon: str = "",
    accent_color: str = "#6366f1",
) -> None:
    """
    Renders a premium glassmorphism metric card.

    Parameters
    ----------
    label : str
        Metric label.
    value : str
        Formatted metric value.
    delta : str or None
        Change indicator.
    delta_color : str
        "normal", "inverse", or "off".
    icon : str
        Optional icon/emoji to display.
    accent_color : str
        Left border accent color.
    """
    delta_html = _delta_html(delta, delta_color) if delta else ""
    icon_html = f"<span style='font-size:1.1rem; margin-right:6px;'>{icon}</span>" if icon else ""

    st.markdown(
        f"""<div style="
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-left: 3px solid {accent_color};
            border-radius: 10px;
            padding: 14px 16px 12px;
            transition: all 0.2s ease;
        ">
            <div style="
                font-size: 0.72rem;
                color: #94a3b8;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 6px;
            ">{icon_html}{label}</div>
            <div style="
                font-size: 1.55rem;
                font-weight: 700;
                color: #e2e8f0;
                letter-spacing: -0.02em;
                line-height: 1.2;
            ">{value}</div>
            {delta_html}
        </div>""",
        unsafe_allow_html=True,
    )


def render_metric_row(metrics: list) -> None:
    """
    Renders a horizontal row of premium metric cards.

    Parameters
    ----------
    metrics : list of dict
        Each dict has keys: label, value, and optionally delta, delta_color,
        icon, accent_color.
    """
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            render_metric_card(
                label=m["label"],
                value=m["value"],
                delta=m.get("delta"),
                delta_color=m.get("delta_color", "normal"),
                icon=m.get("icon", ""),
                accent_color=m.get("accent_color", "#6366f1"),
            )
