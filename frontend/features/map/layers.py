"""
features/map/layers.py — Pydeck Layer Builders
v1.0
"""

import pydeck as pdk
import pandas as pd


# ── TOOLTIP HTML ───────────────────────────────────────────────────────────
TOOLTIP = {
    "html": """
        <div style="
            background: rgba(10, 15, 30, 0.97);
            padding: 14px 18px;
            border-radius: 12px;
            border-left: 4px solid #667eea;
            font-family: 'Inter', 'Segoe UI', sans-serif;
            min-width: 220px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        ">
            <b style="font-size:15px; color:#f1f5f9">{name}</b><br>
            <span style="color:#64748b; font-size:11px">📍 {district}</span>
            <hr style="border:none; border-top:1px solid rgba(255,255,255,0.08); margin:8px 0">
            <div style="color:#cbd5e1; font-size:13px; line-height:1.8">
                🚗 Tốc độ: <b style="color:#f1f5f9">{avg_speed} km/h</b>
                  / {max_speed} km/h<br>
                🚦 Tình trạng: <b style="color:#f1f5f9">{congestion_label}</b><br>
                🕐 Cập nhật: <span style="color:#64748b">{timestamp_vn}</span>
            </div>
        </div>
    """,
    "style": {"backgroundColor": "transparent", "color": "white"},
}


def build_path_layer(df: pd.DataFrame) -> pdk.Layer | None:
    """
    PathLayer — Vẽ đường giao thông màu theo mức ùn tắc.
    SCRUM 8 (bản đồ) + SCRUM 9 (màu sắc)
    """
    df_path = df[df["path"].notna()].copy()
    if df_path.empty:
        return None

    return pdk.Layer(
        "PathLayer",
        data=df_path,
        get_path="path",           # [[lon, lat], ...]
        get_color="color",         # [R, G, B, A] theo congestion
        get_width=14,              # mét
        width_min_pixels=3,
        width_max_pixels=18,
        pickable=True,             # hover/click
        auto_highlight=True,
        joint_rounded=True,
        cap_rounded=True,
    )


def build_scatter_layer(df: pd.DataFrame) -> pdk.Layer | None:
    """
    ScatterplotLayer — Fallback chấm tròn cho đường chưa có geometry.
    SCRUM 8
    """
    df_no_path = df[df["path"].isna()].copy()
    if df_no_path.empty:
        return None

    return pdk.Layer(
        "ScatterplotLayer",
        data=df_no_path,
        get_position=["lon", "lat"],
        get_radius=250,
        get_fill_color="color",
        pickable=True,
        auto_highlight=True,
        opacity=0.85,
        stroked=True,
        get_line_color=[255, 255, 255, 80],
        line_width_min_pixels=1,
    )
