"""
pages/7_csgt_dashboard.py — Dashboard Cảnh Sát Giao Thông
Sprint 4 | SCRUM-48 | SCRUM-49 | SCRUM-50 | SCRUM-51 | SCRUM-52

Layout:
  - KPI Row: 4 thẻ tổng quan (SCRUM-48)
  - Row 2:   Gauge tốc độ (SCRUM-49) + Biểu đồ kẹt theo giờ hôm nay (SCRUM-50)
  - Row 3:   Top 10 đường kẹt nhất (SCRUM-51) + Bản đồ điều động (SCRUM-52)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta

from shared.utils.css_loader import setup_ui
from shared.utils.auth_guard import require_login
from shared.components.sidebar import render_sidebar
from shared.api.client import (
    get_report, get_hourly_trend,
    get_incidents, update_incident_status, create_incident,
    get_traffic_current,
)
from features.map.service import build_map_dataframe
from config import MAP_CENTER_LAT, MAP_CENTER_LON, MAP_STYLE, MAPBOX_TOKEN, APP_VERSION

setup_ui()
require_login()
render_sidebar(show_map_controls=False, brand_icon="🚔", brand_title="CSGT Dashboard",
               brand_subtitle="Điều hành Giao thông")

TZ7 = timezone(timedelta(hours=7))

# ── Hằng số màu ──────────────────────────────────────────────────────────────
_PLOT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0", family="Inter, sans-serif"),
    margin=dict(l=0, r=0, t=36, b=0),
    transition=dict(duration=300, easing="cubic-in-out"),
)
_TYPE_LABEL = {
    "roadblock": "🚧 Lô cốt",
    "accident":  "💥 Tai nạn",
    "event":     "📢 Sự kiện",
    "community": "👥 Cộng đồng",
}
_STATUS_BG = {
    "active":     ("rgba(239,68,68,0.12)",   "#f87171",  "rgba(239,68,68,0.28)"),
    "dispatched": ("rgba(234,179,8,0.12)",    "#fbbf24",  "rgba(234,179,8,0.28)"),
    "resolved":   ("rgba(34,197,94,0.12)",    "#4ade80",  "rgba(34,197,94,0.28)"),
}
_SEV_LABEL = {1: "🟢 Thấp", 2: "🟡 Trung bình", 3: "🔴 Cao"}


def _status_badge(status: str) -> str:
    bg, clr, bdr = _STATUS_BG.get(status, _STATUS_BG["active"])
    labels = {"active": "Đang xảy ra", "dispatched": "Đã điều động", "resolved": "Đã xử lý"}
    return (
        f'<span style="background:{bg};color:{clr};border:1px solid {bdr};'
        f'border-radius:20px;padding:2px 10px;font-size:0.76rem;font-weight:600;'
        f'white-space:nowrap">{labels.get(status, status)}</span>'
    )


def _kpi_card(icon: str, value, label: str, accent: str = "#818cf8",
              delta: str = "") -> str:
    delta_html = (
        f'<div style="font-size:0.72rem;color:#64748b;margin-top:2px">{delta}</div>'
        if delta else ""
    )
    return f"""
    <div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                border-radius:16px;padding:18px 20px;display:flex;align-items:center;gap:14px">
      <div style="font-size:2rem;line-height:1;filter:drop-shadow(0 0 10px {accent}66)">{icon}</div>
      <div>
        <div style="font-size:1.7rem;font-weight:800;color:{accent};line-height:1">{value}</div>
        <div style="font-size:0.78rem;color:#94a3b8;margin-top:3px;font-weight:500">{label}</div>
        {delta_html}
      </div>
    </div>"""


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@keyframes fadeInUp {
  from { opacity:0; transform:translateY(12px); }
  to   { opacity:1; transform:translateY(0); }
}
.csgt-fade { animation: fadeInUp 0.4s ease-out; }
.block-container { padding-right:1rem !important; padding-left:1.5rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
token = st.session_state.get("token", "")
user_role = st.session_state.get("user_role", "")

st.markdown(f"""
<div class="csgt-fade" style="padding:16px 0 6px">
  <h1 style="margin:0;font-size:1.9rem;font-weight:800;letter-spacing:-0.03em">
    <span style="color:#f8fafc">🚔</span>
    <span style="background:linear-gradient(135deg,#f1f5f9 30%,#f87171 100%);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                 background-clip:text">Dashboard CSGT</span>
  </h1>
  <p style="color:#64748b;font-size:0.85rem;margin:4px 0 0">
    Cập nhật: {datetime.now(TZ7).strftime('%H:%M:%S %d/%m/%Y')} +07
  </p>
</div>
<hr style="border-color:rgba(255,255,255,0.07);margin:8px 0 20px">
""", unsafe_allow_html=True)

# ── Fetch data ────────────────────────────────────────────────────────────────
with st.spinner("Đang tải dữ liệu..."):
    report       = get_report()
    trend_data   = get_hourly_trend(7)
    incidents    = get_incidents(token)
    traffic_data = get_traffic_current()

df_trend = pd.DataFrame(trend_data)

# Tính KPI incidents
active_count     = sum(1 for i in incidents if i.get("status") == "active")
dispatched_count = sum(1 for i in incidents if i.get("status") == "dispatched")
resolved_count   = sum(1 for i in incidents if i.get("status") == "resolved")
total_incidents  = len(incidents)

top_street = ""
if report.get("top_congested"):
    top_street = report["top_congested"][0].get("street_name", "—")

avg_spd      = report.get("avg_speed", 0)
total_kẹt    = report.get("red_count", 0)
total_chậm   = report.get("yellow_count", 0)

# ════════════════════════════════════════════════════════════════════════
# SCRUM-48 — 4 KPI Cards
# ════════════════════════════════════════════════════════════════════════
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(_kpi_card("🚨", active_count, "Sự cố đang xảy ra", "#f87171",
                           f"{dispatched_count} đã điều động"), unsafe_allow_html=True)
with c2:
    st.markdown(_kpi_card("🔴", total_kẹt, "Đường kẹt xe", "#ef4444",
                           f"{total_chậm} đường đang chậm"), unsafe_allow_html=True)
with c3:
    spd_color = "#4ade80" if avg_spd >= 40 else "#fbbf24" if avg_spd >= 20 else "#f87171"
    st.markdown(_kpi_card("🚗", f"{avg_spd:.0f} km/h", "Tốc độ TB toàn TP",
                           spd_color), unsafe_allow_html=True)
with c4:
    st.markdown(_kpi_card("📋", total_incidents, "Tổng sự cố hệ thống", "#818cf8",
                           f"{resolved_count} đã xử lý"), unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# SCRUM-49 — Gauge + SCRUM-50 — Biểu đồ kẹt theo giờ
# ════════════════════════════════════════════════════════════════════════
gauge_col, chart_col = st.columns([1, 2])

with gauge_col:
    st.markdown("#### ⚡ Tốc độ Trung Bình Toàn TP")
    bar_color = "#4ade80" if avg_spd >= 40 else "#fbbf24" if avg_spd >= 20 else "#ef4444"
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=avg_spd,
        delta={"reference": 40, "suffix": " km/h",
               "increasing": {"color": "#4ade80"},
               "decreasing": {"color": "#f87171"}},
        number={"suffix": " km/h", "font": {"size": 28, "color": "#e2e8f0"}},
        title={"text": "km/h · Ngưỡng bình thường: 40", "font": {"size": 11, "color": "#64748b"}},
        gauge={
            "axis": {"range": [0, 80], "tickcolor": "#334155",
                     "tickfont": {"color": "#475569", "size": 10}},
            "bar":  {"color": bar_color, "thickness": 0.3},
            "steps": [
                {"range": [0, 20],  "color": "rgba(239,68,68,0.12)"},
                {"range": [20, 40], "color": "rgba(234,179,8,0.08)"},
                {"range": [40, 80], "color": "rgba(34,197,94,0.06)"},
            ],
            "threshold": {"line": {"color": "#818cf8", "width": 2}, "value": 40},
            "bgcolor": "rgba(0,0,0,0)",
        },
    ))
    fig_gauge.update_layout(**_PLOT, height=260)
    st.plotly_chart(fig_gauge, use_container_width=True, config={"displayModeBar": False})

with chart_col:
    st.markdown("#### 📈 Xu hướng Ùn tắc Theo Giờ (7 ngày gần nhất)")
    hour_labels = [f"{h:02d}:00" for h in range(24)]
    fig_trend = go.Figure()

    for col_key, color, name, fill in [
        ("avg_green",  "#22c55e", "🟢 Thông thoáng", "rgba(34,197,94,0.08)"),
        ("avg_yellow", "#eab308", "🟡 Chậm",         "rgba(234,179,8,0.07)"),
        ("avg_red",    "#ef4444", "🔴 Kẹt xe",       "rgba(239,68,68,0.10)"),
    ]:
        if col_key in df_trend.columns:
            fig_trend.add_trace(go.Scatter(
                x=hour_labels, y=df_trend[col_key],
                name=name, mode="lines+markers",
                line=dict(color=color, width=2),
                marker=dict(size=4),
                fill="tozeroy", fillcolor=fill,
                hovertemplate=f"<b>{name}</b><br>%{{x}}: %{{y:.0f}} tuyến<extra></extra>",
            ))

    # Vùng cao điểm
    for s, e, lbl in [(7, 9, "Cao điểm sáng"), (17, 19, "Cao điểm chiều")]:
        fig_trend.add_vrect(
            x0=hour_labels[s], x1=hour_labels[e],
            fillcolor="rgba(251,191,36,0.06)", layer="below", line_width=0,
            annotation_text=lbl, annotation_position="top left",
            annotation_font=dict(size=9, color="#64748b"),
        )

    fig_trend.update_layout(
        **_PLOT,
        xaxis=dict(title="Giờ", gridcolor="rgba(255,255,255,0.04)",
                   tickangle=-30, type="category"),
        yaxis=dict(title="Số tuyến", gridcolor="rgba(255,255,255,0.04)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.01,
                    xanchor="right", x=1, font=dict(size=11)),
        hoverlabel=dict(bgcolor="#1e293b", bordercolor="#334155", font_size=12),
        height=260,
    )
    st.plotly_chart(fig_trend, use_container_width=True, config={"displayModeBar": False})

st.markdown("<hr style='border-color:rgba(255,255,255,0.06);margin:8px 0 16px'>",
            unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════
# SCRUM-51 — Top 10 Đường Kẹt Nhất + SCRUM-52 — Bản đồ Điều Động
# ════════════════════════════════════════════════════════════════════════
top10_col, map_col = st.columns([1, 1.5])

with top10_col:
    st.markdown("#### 🚨 Top 10 Đường Kẹt Nhất")
    top_list = report.get("top_congested", [])[:10]

    if not top_list:
        st.info("Không có dữ liệu đường kẹt.")
    else:
        for i, rd in enumerate(top_list):
            rank_color = "#f87171" if i < 3 else "#fbbf24" if i < 6 else "#94a3b8"
            spd = rd.get("avg_speed", 0)

            c_rd, c_btn = st.columns([3, 1])
            with c_rd:
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
                            border-radius:10px;padding:8px 12px;margin-bottom:4px">
                  <div style="display:flex;align-items:center;gap:8px">
                    <span style="font-size:0.9rem;font-weight:800;color:{rank_color};
                                 min-width:18px">#{i+1}</span>
                    <div>
                      <div style="font-size:0.82rem;font-weight:600;color:#e2e8f0;
                                  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
                                  max-width:180px">{rd.get("street_name","—")}</div>
                      <div style="font-size:0.71rem;color:#64748b">
                        {rd.get("district_name","—")} · {spd} km/h
                      </div>
                    </div>
                  </div>
                </div>""", unsafe_allow_html=True)
            with c_btn:
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                if st.button("🚔 Điều động", key=f"dispatch_top_{i}",
                             help=f"Tạo sự cố điều động cho {rd.get('street_name','')}",
                             use_container_width=True):
                    st.session_state["dispatch_street"] = rd
                    st.session_state["show_dispatch_form"] = True

    # Form nhanh tạo điều động (SCRUM-52 trigger từ bảng)
    if st.session_state.get("show_dispatch_form") and token:
        rd = st.session_state.get("dispatch_street", {})
        with st.expander(f"🚔 Tạo điều động — {rd.get('street_name','?')}", expanded=True):
            _street_id = rd.get("street_id", 1) if "street_id" in rd else 1
            _desc = st.text_area("Ghi chú", placeholder="Tình trạng cụ thể...",
                                 key="dispatch_desc")
            _sev = st.select_slider("Mức độ", options=[1, 2, 3],
                                    format_func=lambda x: _SEV_LABEL[x], key="dispatch_sev")
            if st.button("✅ Xác nhận điều động", key="dispatch_confirm", type="primary"):
                payload = {
                    "street_id": _street_id,
                    "type": "event",
                    "start_time": datetime.now(timezone.utc).isoformat(),
                    "severity": _sev,
                    "description": _desc or f"Điều động xử lý tắc đường {rd.get('street_name','')}",
                    "status": "dispatched",
                    "is_active": True,
                }
                res = create_incident(token, payload)
                if res.get("ok"):
                    st.success("✅ Đã tạo lệnh điều động!")
                    st.session_state["show_dispatch_form"] = False
                    st.rerun()
                else:
                    st.error(f"❌ Lỗi: {res.get('error')}")
            if st.button("Huỷ", key="dispatch_cancel"):
                st.session_state["show_dispatch_form"] = False
                st.rerun()

with map_col:
    st.markdown("#### 🗺️ Bản đồ Giao thông Thực tế")
    # Build traffic layers
    df_map = build_map_dataframe(traffic_data) if traffic_data.get("streets") else None

    layers = []
    if df_map is not None and not df_map.empty:
        path_layer = pdk.Layer(
            "PathLayer",
            data=df_map[["path", "color", "name", "avg_speed",
                          "congestion_label"]].dropna(subset=["path"]),
            get_path="path",
            get_color="color",
            get_width=4,
            width_scale=1,
            width_min_pixels=2,
            pickable=True,
            auto_highlight=True,
        )
        layers.append(path_layer)

    # Incident markers (nếu có)
    inc_data = [
        {"position": [108.2022, 16.0544], "color": [248, 113, 113, 200]}
    ]  # placeholder nếu incidents không có lat/lon
    # Thực tế incidents không có lat/lon trong schema → dùng scatter từ traffic data làm marker
    # Hiển thị top congested streets dưới dạng scatter đỏ nhấp nháy
    top_scatter = []
    for rd in report.get("top_congested", [])[:10]:
        # Lấy lat/lon từ traffic_data nếu có
        for st_item in traffic_data.get("streets", []):
            if st_item.get("street_name") == rd.get("street_name"):
                top_scatter.append({
                    "position": [st_item.get("lon", 108.2022),
                                 st_item.get("lat", 16.0544)],
                    "color": [239, 68, 68, 200],
                    "name": rd.get("street_name", ""),
                })
                break

    if top_scatter:
        layers.append(pdk.Layer(
            "ScatterplotLayer",
            data=top_scatter,
            get_position="position",
            get_fill_color="color",
            get_radius=60,
            radius_min_pixels=6,
            pickable=True,
        ))

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=MAP_CENTER_LAT,
            longitude=MAP_CENTER_LON,
            zoom=12, pitch=0,
        ),
        map_style=MAP_STYLE,
        api_keys={"mapbox": MAPBOX_TOKEN} if MAPBOX_TOKEN else {},
        tooltip={"html": "<b>{name}</b><br>{congestion_label} · {avg_speed} km/h"},
    )
    st.pydeck_chart(deck, height=420)

    st.markdown("""
    <p style="font-size:0.75rem;color:#475569;margin-top:6px">
    🔴 Điểm đỏ = top đường kẹt nhất · Bấm <b>🚔 Điều động</b> bên trái để gửi lực lượng
    </p>""", unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;color:#1e293b;font-size:0.73rem;
            padding:20px 0 6px;border-top:1px solid rgba(255,255,255,0.05);margin-top:20px">
  🚔 CSGT Dashboard · PBL5 Giao thông Đà Nẵng · v{APP_VERSION}
</div>
""", unsafe_allow_html=True)
