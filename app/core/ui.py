"""Shared "app, not spreadsheet" UI theme: one CSS injection plus small HTML component helpers
(icon badges, metric cards, section headers, a disclaimer banner) reused across every page so the
whole app has one consistent, clean, card-based look instead of raw st.data_editor tables everywhere.

No AI-image-generation tool is available in this environment, so the "clip image" look the user asked
for is approximated with colored circular icon badges (emoji on a solid color disc) built from the
same CATEGORY_COLORS palette already used by every chart in the app — consistent, lightweight, and
easy to swap for real illustrations later if the user supplies them.
"""
import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

from .style import CATEGORY_COLORS

ICONS_DIR = Path(__file__).resolve().parents[1] / "assets" / "icons"


@lru_cache(maxsize=None)
def _icon_data_uri(name: str) -> str:
    """Base64-encode one of the app's tab-illustration PNGs (app/assets/icons/<name>.png) for inline use
    in HTML — these are cropped from the reference illustrations the user supplied, one per tab."""
    path = ICONS_DIR / f"{name}.png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"

# A few extra accent colors beyond the 4 category colors, for pages/sections that need more variety.
ACCENT_COLORS = {
    "blue": "#2a78d6",
    "orange": "#eb6834",
    "aqua": "#1baf7a",
    "yellow": "#eda100",
    "purple": "#7a5cd6",
    "pink": "#d65c9e",
    "gray": "#6b6b6b",
}


def inject_theme() -> None:
    """Call once near the top of every page. Safe to call multiple times (idempotent CSS)."""
    st.markdown(
        """
        <style>
        /* Cards */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 14px !important;
        }
        .app-card {
            background: var(--background-color, #ffffff);
            border: 1px solid #e6e5df;
            border-radius: 16px;
            padding: 1.1rem 1.3rem;
            margin-bottom: 0.9rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .app-card h4 { margin-top: 0; }

        /* Icon badges */
        .icon-badge-row { display:flex; align-items:center; gap:0.7rem; margin-bottom:0.3rem; }
        .icon-badge {
            display:inline-flex; align-items:center; justify-content:center;
            width:46px; height:46px; min-width:46px; border-radius:50%;
            font-size:22px; color:white; box-shadow: 0 2px 6px rgba(0,0,0,0.12);
        }
        .icon-badge-title { font-weight:700; font-size:1.15rem; line-height:1.2; }
        .icon-badge-subtitle { font-size:0.86rem; color:#898781; line-height:1.2; }

        /* Metric-style cards (grid of stat tiles) */
        .stat-tile {
            border-radius: 14px; padding: 0.9rem 1rem; text-align:left;
            color: white; box-shadow: 0 2px 6px rgba(0,0,0,0.10);
        }
        .stat-tile .stat-icon { font-size:1.3rem; }
        .stat-tile .stat-label { font-size:0.78rem; opacity:0.92; margin-top:0.15rem; }
        .stat-tile .stat-value { font-size:1.35rem; font-weight:750; margin-top:0.1rem; }

        /* Disclaimer banner */
        .disclaimer-banner {
            background: #fff4e0; border: 1px solid #eda100; border-radius: 12px;
            padding: 0.75rem 1rem; font-size: 0.88rem; color:#5c4600; margin-bottom:1rem;
        }

        /* Nicer buttons */
        .stButton>button, .stDownloadButton>button {
            border-radius: 10px !important; font-weight:600;
        }

        /* Tabs look more like segmented app controls */
        .stTabs [data-baseweb="tab-list"] { gap: 4px; }
        .stTabs [data-baseweb="tab"] {
            border-radius: 10px 10px 0 0; padding: 6px 16px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(icon: str, title: str, subtitle: str = "", color: str = ACCENT_COLORS["blue"]) -> None:
    """Icon-badge page header, replacing the plain st.title()+st.caption() everywhere for a more
    app-like first impression."""
    st.markdown(
        f"""
        <div class="icon-badge-row">
            <div class="icon-badge" style="background:{color};">{icon}</div>
            <div>
                <div class="icon-badge-title">{title}</div>
                <div class="icon-badge-subtitle">{subtitle}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header_image(icon_name: str, title: str, subtitle: str = "") -> None:
    """Page header using one of the six custom tab illustrations (app/assets/icons/<icon_name>.png)
    instead of an emoji badge — the "clip image" look the user asked for, in the dashed-circle pastel
    style of their reference screenshots."""
    uri = _icon_data_uri(icon_name)
    st.markdown(
        f"""
        <div class="icon-badge-row">
            <img src="{uri}" style="width:64px;height:64px;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.12);" />
            <div>
                <div class="icon-badge-title" style="font-size:1.3rem;">{title}</div>
                <div class="icon-badge-subtitle">{subtitle}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(icon: str, title: str, color: str = ACCENT_COLORS["gray"]) -> None:
    """Smaller inline icon header for a subsection within a page (replaces st.subheader() for a
    more consistent, colorful visual rhythm)."""
    st.markdown(
        f"""
        <div class="icon-badge-row" style="margin-top:0.4rem;">
            <div class="icon-badge" style="width:34px;height:34px;min-width:34px;font-size:16px;background:{color};">{icon}</div>
            <div class="icon-badge-title" style="font-size:1.02rem;">{title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def stat_tile_html(icon: str, label: str, value: str, color: str = ACCENT_COLORS["blue"]) -> str:
    return (
        f'<div class="stat-tile" style="background:{color};">'
        f'<div class="stat-icon">{icon}</div>'
        f'<div class="stat-value">{value}</div>'
        f'<div class="stat-label">{label}</div>'
        f'</div>'
    )


def stat_tiles(tiles: list) -> None:
    """Render a responsive row of colored stat tiles instead of a plain st.metric()/table row.
    `tiles` is a list of (icon, label, value, color) tuples."""
    cols = st.columns(len(tiles))
    for col, (icon, label, value, color) in zip(cols, tiles):
        with col:
            st.markdown(stat_tile_html(icon, label, value, color), unsafe_allow_html=True)


def disclaimer_banner() -> None:
    st.markdown(
        """
        <div class="disclaimer-banner">
        ⚠️ <b>Academic project.</b> This app is a university/academic exercise in off-grid rural
        electrification planning. Figures, defaults, and assumptions are illustrative and simplified —
        they are <b>not</b> validated for real-world investment, engineering, or financial decisions.
        </div>
        """,
        unsafe_allow_html=True,
    )


def category_color(category: str) -> str:
    return CATEGORY_COLORS.get(category, ACCENT_COLORS["gray"])
