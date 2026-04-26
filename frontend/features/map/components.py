"""
features/map/components.py — Map UI Component
v1.1 — FIX 1: render_map() nhận view_lat/lon/zoom để zoom theo filter (SCRUM-22/24)
"""

import pydeck as pdk
import pandas as pd
import streamlit as st

from features.map.layers import build_path_layer, build_scatter_layer, TOOLTIP
from config import MAP_CENTER_LAT, MAP_CENTER_LON, MAP_ZOOM


def render_map(
    df: pd.DataFrame,
    height: int = 580,
    view_lat: float = MAP_CENTER_LAT,
    view_lon: float = MAP_CENTER_LON,
    view_zoom: int = MAP_ZOOM,
) -> None:
    """
    Render Pydeck bản đồ giao thông Đà Nẵng.
    SCRUM 8 + 9 (màu) + 10 (tooltip)
    FIX 1: view_lat/lon/zoom động — zoom theo filter quận hoặc tìm kiếm (SCRUM-22/24)
    """
    if df.empty:
        st.info("ℹ️ Không có dữ liệu bản đồ để hiển thị.")
        return

    layers = [
        l for l in [
            build_path_layer(df),
            build_scatter_layer(df),
        ] if l is not None
    ]

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=view_lat,
            longitude=view_lon,
            zoom=view_zoom,
            pitch=0,
            bearing=0,
        ),
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        tooltip=TOOLTIP,
    )

    st.pydeck_chart(deck, width="stretch", height=height)
