"""
Reusable metric card component for the NYC Neighborhood Pulse dashboard.

Renders a clean KPI card with value, label, and optional delta indicator.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st


def render_metric_card(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: str = "normal",
) -> None:
    """
    Renders a styled metric card.

    Parameters
    ----------
    label : str
        Metric label (e.g., "Total Complaints").
    value : str
        Formatted metric value (e.g., "12,345").
    delta : str or None
        Change indicator (e.g., "+3.2" or "-1.5").
    delta_color : str
        One of "normal", "inverse", "off".
        normal: green for positive, red for negative.
        inverse: red for positive, green for negative (e.g., for complaints).
        off: gray for any delta.
    """
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def render_metric_row(metrics: list) -> None:
    """
    Renders a horizontal row of metric cards.

    Parameters
    ----------
    metrics : list of dict
        Each dict has keys: label, value, and optionally delta, delta_color.
    """
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            render_metric_card(
                label=m["label"],
                value=m["value"],
                delta=m.get("delta"),
                delta_color=m.get("delta_color", "normal"),
            )
