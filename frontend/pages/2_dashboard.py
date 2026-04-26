"""
pages/2_dashboard.py — Dashboard Phân tích & Dự báo
Sprint 3 | SCRUM-36 | SCRUM-37 | SCRUM-38 | SCRUM-39

Fixes applied:
  - HTML badge table thay vì st.dataframe (SCRUM-36 bảng đẹp)
  - Bỏ SCRUM số khỏi tab label
  - Emoji 📊 tách ra khỏi gradient span
  - Chart transition animation (Plotly)
  - CSS fadeIn cho toàn trang
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from shared.utils.css_loader import setup_ui
from shared.api.client import (
    get_predictions, get_hourly_trend,
    get_heatmap_data, get_report,
)
from config import APP_TITLE, APP_VERSION

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"Dashboard | {APP_TITLE}",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_ui()

# ── CSS: animation fadeIn + table style ──────────────────────────────────────
st.markdown("""
<style>
@keyframes fadeInUp {
  from { opacity:0; transform:translateY(14px); }
  to   { opacity:1; transform:translateY(0); }
}
.dash-fadein { animation: fadeInUp 0.45s ease-out; }

/* Plotly chart fade-in */
.stPlotlyChart { animation: fadeInUp 0.5s ease-out; }

/* Custom prediction table */
.pred-table { width:100%; border-collapse:collapse; font-size:0.84rem; }
.pred-table thead tr {
  border-bottom: 1px solid rgba(255,255,255,0.07);
}
.pred-table th {
  padding: 10px 14px;
  color: #475569;
  font-weight:600;
  font-size:0.73rem;
  letter-spacing:0.06em;
  text-transform:uppercase;
  text-align:left;
}
.pred-table td {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  color: #cbd5e1;
  vertical-align: middle;
}
.pred-table tbody tr:hover td {
  background: rgba(255,255,255,0.03);
}
.badge {
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:3px 11px;
  border-radius:20px;
  font-size:0.77rem;
  font-weight:600;
  white-space:nowrap;
  min-width:130px;
}
/* Override main.css: giảm right-padding từ 2.5rem xuống 1rem cho dashboard */
.block-container {
  padding-right: 1rem !important;
  padding-left:  1.5rem !important;
}
</style>
""", unsafe_allow_html=True)

# ── Hằng số ──────────────────────────────────────────────────────────────────
_LABEL = {0: "Thông thoáng", 1: "Chậm", 2: "Kẹt xe"}  # bỏ emoji → dùng CSS dot
_BG    = {0: "rgba(34,197,94,0.12)",  1: "rgba(234,179,8,0.12)",  2: "rgba(239,68,68,0.12)"}
_CLR   = {0: "#22c55e",               1: "#eab308",                2: "#ef4444"}
_BDR   = {0: "rgba(34,197,94,0.28)",  1: "rgba(234,179,8,0.28)",  2: "rgba(239,68,68,0.28)"}
_DAY   = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]

_PLOT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0", family="Inter, sans-serif"),
    margin=dict(l=0, r=0, t=40, b=0),
    transition=dict(duration=400, easing="cubic-in-out"),  # ← animation khi filter đổi
)


def _badge(level: int | None) -> str:
    """Badge pill với CSS dot căn chỉnh chuẩn — không dùng emoji."""
    lv = level if level in _LABEL else 0
    dot = (
        f'<span style="width:7px;height:7px;border-radius:50%;'
        f'background:{_CLR[lv]};display:inline-block;'
        f'flex-shrink:0;margin-right:7px"></span>'
    )
    return (
        f'<span class="badge" '
        f'style="background:{_BG[lv]};color:{_CLR[lv]};border:1px solid {_BDR[lv]};'
        f'justify-content:flex-start;padding-left:12px">'
        f'{dot}{_LABEL[lv]}</span>'
    )


def _conf_bar(conf: float) -> str:
    """HTML progress bar cho confidence."""
    pct = int(conf * 100)
    color = "#22c55e" if pct >= 80 else "#eab308" if pct >= 65 else "#ef4444"
    return (
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<div style="flex:1;background:rgba(255,255,255,0.07);border-radius:4px;height:6px">'
        f'<div style="width:{pct}%;background:{color};border-radius:4px;height:6px"></div></div>'
        f'<span style="color:{color};font-size:0.78rem;font-weight:600;min-width:30px">{pct}%</span>'
        f'</div>'
    )


def _trend_cell(cur: int, pred: int) -> str:
    """Cột Xu hướng: text ‘▲ Xấu hơn / ▼ Cải thiện / — Giữ nguyên’ với màu."""
    if pred > cur:
        return '<span style="color:#f87171;font-weight:600;font-size:0.8rem">&#9650; Xấu hơn</span>'
    if pred < cur:
        return '<span style="color:#4ade80;font-weight:600;font-size:0.8rem">&#9660; Cải thiện</span>'
    return '<span style="color:#475569;font-size:0.8rem">— Giữ nguyên</span>'


def _build_pred_table(rows: pd.DataFrame) -> str:
    """Xây dựng HTML table với badge CSS dot + cột Xu hướng riêng."""
    if rows.empty:
        return '<p style="color:#64748b;text-align:center;padding:24px">Không có dữ liệu phù hợp.</p>'

    trs = ""
    for _, r in rows.iterrows():
        cur  = int(r.get("current_level")  or 0)
        pred = int(r.get("predicted_level") or 0)
        trs += (
            f'<tr>'
            f'<td style="font-weight:500;color:#e2e8f0">{r["street_name"]}</td>'
            f'<td style="color:#64748b">{r["district_name"]}</td>'
            f'<td style="text-align:center">{r["current_speed"]} <span style="color:#475569;font-size:0.75rem">km/h</span></td>'
            f'<td style="text-align:center">{_badge(cur)}</td>'
            f'<td style="text-align:center">{_trend_cell(cur, pred)}</td>'
            f'<td style="text-align:center">{_badge(pred)}</td>'
            f'<td style="text-align:center">{r["predicted_speed"]} <span style="color:#475569;font-size:0.75rem">km/h</span></td>'
            f'<td>{_conf_bar(r["confidence"])}</td>'
            f'</tr>'
        )

    header = (
        '<th>Tên đường</th>'
        '<th>Quận</th>'
        '<th style="text-align:center">Tốc độ HT</th>'
        '<th style="text-align:center">Trạng thái HT</th>'
        '<th style="text-align:center">Xu hướng</th>'
        '<th style="text-align:center">Dự báo 30 phút</th>'
        '<th style="text-align:center">Tốc độ DB</th>'
        '<th>&#272;ộ tin cậy</th>'
    )
    return (
        f'<div class="dash-fadein" style="overflow-x:auto;border-radius:14px;'
        f'border:1px solid rgba(255,255,255,0.07);background:rgba(255,255,255,0.02)">'
        f'<table class="pred-table">'
        f'<thead><tr>{header}</tr></thead>'
        f'<tbody>{trs}</tbody>'
        f'</table></div>'
    )


# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dash-fadein" style="padding:20px 0 8px">
  <h1 style="margin:0;font-size:1.9rem;font-weight:800;letter-spacing:-0.03em;color:#f1f5f9">
    <span style="color:#f8fafc">📊</span>
    <span style="background:linear-gradient(135deg,#f1f5f9 30%,#818cf8 100%);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                 background-clip:text">
      Dashboard Phân tích Giao thông
    </span>
  </h1>
</div>
<hr style="border-color:rgba(255,255,255,0.07);margin:0 0 16px">
""", unsafe_allow_html=True)

# ── Sidebar Dashboard ─────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;padding:10px 0 16px">
            <div style="font-size:1.7rem;line-height:1">📊</div>
            <div>
                <div style="font-size:1rem;font-weight:700;color:#f1f5f9;line-height:1.3">
                    Dashboard
                </div>
                <div style="font-size:0.74rem;color:#64748b;margin-top:2px">
                    Phân tích Giao thông Đà Nẵng
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    st.markdown('<p style="font-size:0.78rem;color:#94a3b8;margin-bottom:4px">📅 Khoảng thời gian</p>',
                unsafe_allow_html=True)
    days_sel = st.selectbox(
        "Khoảng thời gian",
        [7, 14, 30],
        format_func=lambda x: f"{x} ngày gần nhất",
        key="sidebar_days",
        label_visibility="collapsed",
    )

    st.markdown('<p style="font-size:0.78rem;color:#94a3b8;margin:10px 0 4px">🗺️ Lọc theo Quận</p>',
                unsafe_allow_html=True)
    district_filter = st.selectbox(
        "Lọc quận",
        ["Tất cả quận", "Hải Châu", "Sơn Trà", "Thanh Khê",
         "Ngũ Hành Sơn", "Liên Chiểu", "Cẩm Lệ"],
        key="sidebar_district",
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown("""
        <div style="font-size:0.75rem; color:#475569; line-height:1.8">
            🤖 Model: Random Forest<br>
            📊 Dự báo: 30 phút tới<br>
            📈 Dữ liệu: 7–30 ngày lịch sử<br>
            🗃️ DB: PostgreSQL + PostGIS
        </div>
        """, unsafe_allow_html=True)

# ── 4 Tabs ────────────────────────────────────────────────────────────────────
tab36, tab37, tab38, tab39 = st.tabs([
    "🔮 Dự báo AI",
    "📈 Xu hướng",
    "🌡️ Heatmap",
    "📋 Báo cáo",
])


# ════════════════════════════════════════════════════════════════════════
# SCRUM-36 — Trang Dự báo AI
# ════════════════════════════════════════════════════════════════════════
with tab36:
    st.markdown("""
    <div class="dash-fadein" style="background:rgba(99,102,241,0.08);
         border:1px solid rgba(99,102,241,0.2);border-radius:12px;
         padding:11px 18px;margin-bottom:16px;font-size:0.85rem;color:#a5b4fc">
      🤖 <b>Dự báo AI (Random Forest)</b> — Mức ùn tắc dự kiến <b>30 phút tới</b>.
      Độ chính xác model: <b>F1 ≈ 0.81</b>
    </div>""", unsafe_allow_html=True)

    with st.spinner("Đang tải dự báo..."):
        preds = get_predictions()
    df_pred = pd.DataFrame(preds)

    # KPI
    p_green  = int((df_pred["predicted_level"] == 0).sum())
    p_yellow = int((df_pred["predicted_level"] == 1).sum())
    p_red    = int((df_pred["predicted_level"] == 2).sum())
    total    = len(df_pred)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Tổng đường dự báo", total)
    k2.metric("🟢 Sẽ thông thoáng", p_green,
              delta=p_green - int((df_pred["current_level"] == 0).sum()))
    k3.metric("🟡 Sẽ chậm", p_yellow,
              delta=p_yellow - int((df_pred["current_level"] == 1).sum()))
    k4.metric("🔴 Sẽ kẹt xe", p_red,
              delta=p_red - int((df_pred["current_level"] == 2).sum()),
              delta_color="inverse")

    st.markdown("<br>", unsafe_allow_html=True)

    # Bộ lọc
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        search_pred = st.text_input(
            "Tìm đường", placeholder="VD: Hùng Vương...",
            key="pred_search", label_visibility="collapsed",
        )
    with col_f2:
        filter_change = st.selectbox(
            "Lọc thay đổi",
            ["Tất cả", "▲ Xấu hơn", "▼ Cải thiện", "— Giữ nguyên"],
            key="pred_filter", label_visibility="collapsed",
        )

    df_show = df_pred.copy()
    if search_pred:
        df_show = df_show[df_show["street_name"].str.contains(search_pred, case=False, na=False)]
    if filter_change == "▲ Xấu hơn":
        df_show = df_show[df_show["predicted_level"] > df_show["current_level"]]
    elif filter_change == "▼ Cải thiện":
        df_show = df_show[df_show["predicted_level"] < df_show["current_level"]]
    elif filter_change == "— Giữ nguyên":
        df_show = df_show[df_show["predicted_level"] == df_show["current_level"]]

    st.markdown(_build_pred_table(df_show), unsafe_allow_html=True)
    st.caption(f"Hiển thị {len(df_show)}/{total} tuyến đường")


# ════════════════════════════════════════════════════════════════════════
# SCRUM-37 — Biểu đồ xu hướng
# ════════════════════════════════════════════════════════════════════════
with tab37:
    # days_sel được lấy từ sidebar (đã định nghĩa ở trên)

    with st.spinner("Đang tải xu hướng..."):
        trend_data = get_hourly_trend(days_sel)
    df_trend = pd.DataFrame(trend_data)
    hour_labels = [f"{h:02d}:00" for h in range(24)]

    fig_trend = go.Figure()
    for col, color, name, fill_color in [
        ("avg_green",  "#22c55e", "🟢 Thông thoáng", "rgba(34,197,94,0.08)"),
        ("avg_yellow", "#eab308", "🟡 Chậm",         "rgba(234,179,8,0.08)"),
        ("avg_red",    "#ef4444", "🔴 Kẹt xe",       "rgba(239,68,68,0.10)"),
    ]:
        fig_trend.add_trace(go.Scatter(
            x=hour_labels, y=df_trend[col],
            name=name, mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=5, color=color),
            fill="tozeroy", fillcolor=fill_color,
            hovertemplate=f"<b>{name}</b><br>%{{x}}: %{{y}} tuyến<extra></extra>",
        ))

    for start, end, label in [(7, 9, "Cao điểm sáng"), (17, 19, "Cao điểm chiều")]:
        fig_trend.add_vrect(
            x0=hour_labels[start], x1=hour_labels[end],
            fillcolor="rgba(251,191,36,0.05)", layer="below", line_width=0,
            annotation_text=label, annotation_position="top left",
            annotation_font=dict(size=9, color="#64748b"),
        )

    fig_trend.update_layout(
        **_PLOT,
        title=dict(text=f"Số tuyến đường theo mức ùn tắc ({days_sel} ngày gần nhất)",
                   font=dict(size=14)),
        xaxis=dict(title="Giờ trong ngày", gridcolor="rgba(255,255,255,0.04)",
                   tickangle=-30, type="category", range=[-0.4, 23.4]),
        yaxis=dict(title="Số tuyến đường",  gridcolor="rgba(255,255,255,0.04)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#1e293b", bordercolor="#334155", font_size=12),
        height=420,
    )
    st.plotly_chart(fig_trend, width="stretch", config={"displayModeBar": False})

    # Insights
    peak_red   = int(df_trend.loc[df_trend["avg_red"].idxmax(),   "hour"])
    peak_green = int(df_trend.loc[df_trend["avg_green"].idxmax(), "hour"])
    i1, i2, i3 = st.columns(3)
    i1.metric("🔴 Giờ kẹt cao nhất",      f"{peak_red:02d}:00")
    i2.metric("🟢 Giờ thông thoáng nhất", f"{peak_green:02d}:00")
    i3.metric("📅 Phân tích",             f"{days_sel} ngày")


# ════════════════════════════════════════════════════════════════════════
# SCRUM-38 — Heatmap thời gian
# ════════════════════════════════════════════════════════════════════════
with tab38:
    with st.spinner("Đang tải heatmap..."):
        heatmap_data = get_heatmap_data()
    df_heat = pd.DataFrame(heatmap_data)

    pivot = df_heat.pivot(index="day_of_week", columns="hour", values="avg_congestion")
    pivot.index = [_DAY[i] for i in pivot.index]

    fig_heat = go.Figure(go.Heatmap(
        z=pivot.values,
        x=[f"{h:02d}h" for h in range(24)],
        y=list(pivot.index),
        colorscale=[
            [0.0,  "#0f172a"],
            [0.25, "#14532d"],
            [0.5,  "#713f12"],
            [0.75, "#7f1d1d"],
            [1.0,  "#450a0a"],
        ],
        zmin=0, zmax=2,
        colorbar=dict(
            title=dict(text="Mức kẹt", font=dict(size=11)),
            tickvals=[0, 1, 2],
            ticktext=["Thông<br>thoáng", "Chậm", "Kẹt xe"],
            thickness=12,
        ),
        hovertemplate="<b>%{y} %{x}</b><br>Mức kẹt TB: %{z:.2f}<extra></extra>",
        xgap=2, ygap=2,
    ))
    fig_heat.update_layout(
        **_PLOT,
        title=dict(text="Bản đồ nhiệt — Mức ùn tắc theo Giờ × Ngày trong tuần",
                   font=dict(size=14)),
        xaxis=dict(title="Giờ trong ngày", side="bottom"),
        yaxis=dict(title="", autorange="reversed"),
        height=360,
    )
    st.plotly_chart(fig_heat, width="stretch", config={"displayModeBar": False})
    st.markdown("""
    <p style="font-size:0.8rem;color:#475569;margin-top:-6px">
    💡 <b>Đọc heatmap:</b>
    <span style="color:#14532d">■</span> Xanh = thông thoáng &nbsp;|&nbsp;
    <span style="color:#713f12">■</span> Cam = chậm &nbsp;|&nbsp;
    <span style="color:#7f1d1d">■</span> Đỏ = kẹt nặng &nbsp;|&nbsp;
    Giờ cao điểm 7–9h và 17–19h ngày thường kẹt nhất.
    </p>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════
# SCRUM-39 — UI Báo cáo & Thống kê
# ════════════════════════════════════════════════════════════════════════
with tab39:
    with st.spinner("Đang tải báo cáo..."):
        report = get_report()

    # KPI tổng quan
    r1, r2, r3, r4, r5 = st.columns(5)
    r1.metric("🛣️ Tổng tuyến",    report["total_streets"])
    r2.metric("🗃️ Records DB",    f'{report["total_records_db"]:,}')
    r3.metric("🟢 Thông thoáng",  report["green_count"])
    r4.metric("🟡 Đang chậm",     report["yellow_count"])
    r5.metric("🔴 Đang kẹt",      report["red_count"])

    st.markdown("<hr style='border-color:rgba(255,255,255,0.06);margin:16px 0'>",
                unsafe_allow_html=True)

    col_chart, col_top = st.columns([1, 1])

    with col_chart:
        st.markdown("#### 🗺️ Phân bổ ùn tắc theo Quận")
        df_dist = pd.DataFrame(report["district_stats"])
        if not df_dist.empty:
            fig_dist = go.Figure()
            for col_key, color, label in [
                ("green",  "#22c55e", "Thông thoáng"),
                ("yellow", "#eab308", "Chậm"),
                ("red",    "#ef4444", "Kẹt xe"),
            ]:
                if col_key in df_dist.columns:
                    fig_dist.add_trace(go.Bar(
                        x=df_dist["district"], y=df_dist[col_key],
                        name=label, marker_color=color, marker_line_width=0,
                        hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y}} tuyến<extra></extra>",
                    ))
            fig_dist.update_layout(
                **_PLOT,
                barmode="stack",
                xaxis=dict(tickangle=-20, gridcolor="rgba(255,255,255,0.04)"),
                yaxis=dict(title="Số tuyến", gridcolor="rgba(255,255,255,0.04)"),
                legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1),
                hoverlabel=dict(bgcolor="#1e293b", bordercolor="#334155", font_size=12),
                height=300,
            )
            st.plotly_chart(fig_dist, width="stretch", config={"displayModeBar": False})

    with col_top:
        st.markdown("#### 🚨 Top đường kẹt nhất")
        df_top = pd.DataFrame(report["top_congested"])
        if not df_top.empty:
            top_html = ""
            for i, (_, r) in enumerate(df_top.iterrows()):
                lv = 2 if "Kẹt" in str(r.get("congestion_label","")) else 1
                top_html += (
                    f'<div style="display:flex;align-items:center;gap:12px;'
                    f'padding:10px 14px;border-radius:10px;margin-bottom:6px;'
                    f'background:rgba(255,255,255,0.03);'
                    f'border:1px solid rgba(255,255,255,0.06)">'
                    f'<span style="font-size:1.1rem;font-weight:800;color:#475569;min-width:20px">#{i+1}</span>'
                    f'<div style="flex:1">'
                    f'<div style="font-weight:600;color:#e2e8f0;font-size:0.88rem">{r["street_name"]}</div>'
                    f'<div style="color:#64748b;font-size:0.76rem">{r["district_name"]}</div>'
                    f'</div>'
                    f'<div style="text-align:right">'
                    f'{_badge(lv)}'
                    f'<div style="color:#64748b;font-size:0.76rem;margin-top:3px">{r["avg_speed"]} km/h</div>'
                    f'</div></div>'
                )
            st.markdown(f'<div class="dash-fadein">{top_html}</div>', unsafe_allow_html=True)

    # Gauge + progress
    st.markdown("<hr style='border-color:rgba(255,255,255,0.06);margin:12px 0'>",
                unsafe_allow_html=True)
    gauge_col, info_col = st.columns([1, 2])
    avg_spd = report["avg_speed"]

    with gauge_col:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=avg_spd,
            delta={"reference": 40, "suffix": " km/h"},
            number={"suffix": " km/h", "font": {"size": 26, "color": "#e2e8f0"}},
            title={"text": "Tốc độ TB toàn TP", "font": {"size": 12, "color": "#94a3b8"}},
            gauge={
                "axis": {"range": [0, 80], "tickcolor": "#334155"},
                "bar":  {"color": "#22c55e" if avg_spd >= 40 else
                                  "#eab308" if avg_spd >= 20 else "#ef4444"},
                "steps": [
                    {"range": [0, 20],  "color": "rgba(239,68,68,0.12)"},
                    {"range": [20, 40], "color": "rgba(234,179,8,0.08)"},
                    {"range": [40, 80], "color": "rgba(34,197,94,0.06)"},
                ],
                "threshold": {"line": {"color": "#64748b", "width": 2}, "value": 40},
                "bgcolor": "rgba(0,0,0,0)",
            },
        ))
        fig_gauge.update_layout(**_PLOT, height=230)
        st.plotly_chart(fig_gauge, width="stretch", config={"displayModeBar": False})

    with info_col:
        total = report["total_streets"]
        pcts = {k: round(report[f"{k}_count"] / total * 100) if total else 0
                for k in ("green", "yellow", "red")}
        status = ("🟢 Giao thông lưu thông tốt" if pcts["red"] < 10 else
                  "🟡 Có điểm ùn tắc cần chú ý" if pcts["red"] < 30 else
                  "🔴 Nhiều điểm kẹt — cần can thiệp")
        # FIX 1: dùng single-line HTML để tránh Markdown parser treat indent ≥ 4 spaces = code block
        def _bar(lbl, clr, pct):
            return (
                f'<div style="margin-bottom:12px">'
                f'<div style="display:flex;justify-content:space-between;font-size:0.8rem;color:#94a3b8;margin-bottom:5px">'
                f'<span>{lbl}</span>'
                f'<span style="color:{clr};font-weight:600">{pct}%</span>'
                f'</div>'
                f'<div style="background:rgba(255,255,255,0.07);border-radius:6px;height:7px">'
                f'<div style="width:{pct}%;background:{clr};border-radius:6px;height:7px"></div>'
                f'</div></div>'
            )

        bars_html = (
            _bar("Thông thoáng", "#22c55e", pcts["green"]) +
            _bar("Đang chậm",   "#eab308", pcts["yellow"]) +
            _bar("Kẹt xe",      "#ef4444", pcts["red"])
        )

        info_html = (
            f'<div style="padding:20px;background:rgba(255,255,255,0.03);border-radius:14px;'
            f'border:1px solid rgba(255,255,255,0.07);min-height:210px;'
            f'display:flex;flex-direction:column;justify-content:center">'
            f'<div style="font-size:1rem;font-weight:700;color:#e2e8f0;margin-bottom:18px">{status}</div>'
            f'{bars_html}'
            f'</div>'
        )
        st.markdown(info_html, unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;color:#1e293b;font-size:0.74rem;
            padding:24px 0 8px;border-top:1px solid rgba(255,255,255,0.05);margin-top:24px">
  📊 Dashboard · PBL5 Giao thông Đà Nẵng · v{APP_VERSION}
</div>
""", unsafe_allow_html=True)
