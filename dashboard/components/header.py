"""
Page header component for the NYC Neighborhood Pulse dashboard.

Renders a clean, professional page title with optional subtitle.
No emojis. No purple. Just text.
"""

from __future__ import annotations

import streamlit as st


def render_header(title: str, subtitle: str = "") -> None:
    """
    Renders the page header with consistent styling.

    Parameters
    ----------
    title : str
        Main page title.
    subtitle : str
        Optional description below the title.
    """
    st.markdown(
        f"<h1 style='"
        f"font-size: 1.6rem; "
        f"font-weight: 600; "
        f"color: #0f172a; "
        f"margin-bottom: 0.15rem; "
        f"letter-spacing: -0.01em;"
        f"'>{title}</h1>",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f"<p style='"
            f"font-size: 0.88rem; "
            f"color: #475569; "
            f"margin-top: 0;"
            f"'>{subtitle}</p>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)
