"""
Page header component with gradient accent and context badges.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st


def render_header(
    title: str,
    subtitle: str = "",
    icon: str = "",
    data_period: Optional[str] = None,
) -> None:
    """
    Renders a premium page header with gradient underline accent.

    Parameters
    ----------
    title : str
        Main page title.
    subtitle : str
        Optional description below the title.
    icon : str
        Optional icon/emoji prefix.
    data_period : str or None
        Badge showing the data period (e.g., "2020-01 to 2020-03").
    """
    icon_html = f"<span style='margin-right:8px;'>{icon}</span>" if icon else ""
    period_badge = ""
    if data_period:
        period_badge = (
            f"<span style='"
            f"display:inline-block; padding:3px 10px; border-radius:12px; "
            f"font-size:0.7rem; font-weight:500; "
            f"background:rgba(99,102,241,0.15); color:#818cf8; "
            f"margin-left:12px; vertical-align:middle;"
            f"'>{data_period}</span>"
        )

    st.markdown(
        f"""<div style="margin-bottom:4px;">
            <h1 style="
                font-size: 1.65rem;
                font-weight: 700;
                color: #e2e8f0;
                margin-bottom: 0;
                letter-spacing: -0.02em;
                display: inline;
            ">{icon_html}{title}</h1>
            {period_badge}
        </div>
        <div style="
            width: 60px; height: 3px; margin: 6px 0 8px;
            background: linear-gradient(90deg, #6366f1, #22d3ee);
            border-radius: 2px;
        "></div>""",
        unsafe_allow_html=True,
    )
    if subtitle:
        st.markdown(
            f"<p style='"
            f"font-size: 0.85rem; color: #94a3b8; margin-top: 0; "
            f"line-height: 1.5; max-width: 720px;"
            f"'>{subtitle}</p>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='height: 0.3rem;'></div>", unsafe_allow_html=True)
