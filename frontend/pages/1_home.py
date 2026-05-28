"""
pages/1_home.py — Trang Bản đồ Giao thông Đà Nẵng
Sprint 1 | SCRUM 8,9,10,11,12,13,14
Sprint 2 | SCRUM 22,23,24,25,26,28
v1.3 — FIX 1: Map zoom theo quận + search (SCRUM-22/24)
v1.3 — FIX 4: Countdown timer thực tế (SCRUM-26)
v1.3 — FIX 5: Nút "Thử lại" trong empty state (SCRUM-28)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from config import APP_TITLE, APP_ICON, REFRESH_INTERVAL_MS, APP_VERSION, MAP_CENTER_LAT, MAP_CENTER_LON, MAP_ZOOM
from shared.utils.css_loader import setup_ui
from shared.components.sidebar import render_sidebar
from shared.components.kpi_cards import render_kpi_cards
from shared.api.client import get_predictions
from features.map.service import (
    get_traffic_data, build_map_dataframe, filter_dataframe,
    get_streets_geometry, get_traffic_state, build_map_dataframe_split,
)
from features.map.components import render_map
from datetime import datetime, timezone, timedelta

# Màu dự báo AI — TASK #27: giữ xanh/vàng/đỏ như thực tế
# Người dùng phân biệt "dự báo vs thực tế" qua UI context (toggle ON + banner + legend text)
# KHÔNG dùng tím vì: tím nhạt ≈ tím đậm → không phân biệt được + không có ngữ nghĩa
_PREDICT_COLORS = {
    0: [34,  197,  94, 220],   # Xanh  — dự báo: thông thoáng (= màu thực tế)
    1: [234, 179,   8, 220],   # Vàng  — dự báo: chậm         (= màu thực tế)
    2: [239,  68,  68, 220],   # Đỏ    — dự báo: kẹt xe       (= màu thực tế)
}


# ── Tọa độ trung tâm từng quận — SCRUM-24 map zoom ──────────────────────────
# (lat, lon, zoom)
_DISTRICT_VIEW: dict[int, tuple[float, float, int]] = {
    1: (16.0690, 108.2169, 14),  # Hải Châu
    2: (16.0734, 108.1748, 14),  # Thanh Khê
    3: (16.0954, 108.2456, 13),  # Sơn Trà
    4: (16.0073, 108.2549, 13),  # Ngũ Hành Sơn
    5: (16.0833, 108.1522, 13),  # Liên Chiểu
    6: (16.0237, 108.2136, 13),  # Cẩm Lệ
    7: (16.0065, 107.9948, 11),  # Hòa Vang
    8: (16.4500, 111.8000, 10),  # Hoàng Sa
}

_REFRESH_SECS = REFRESH_INTERVAL_MS // 1000   # 60


def _fmt_time(iso_str: str) -> str:
    """Convert ISO timestamp → giờ Việt Nam dạng dd/mm HH:MM."""
    try:
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s).astimezone(timezone(timedelta(hours=7)))
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return iso_str


def _compute_view(
    district_id: int | None,
    df,
) -> tuple[float, float, int]:
    """
    Tính toán view state cho bản đồ theo filter hiện tại — FIX 1 (SCRUM-22/24).

    Priority:
      1. Quận được chọn → zoom vào trung tâm quận
      2. Search thu hẹp ≤ 10 tuyến → zoom vào centroid khu vực đó
      3. Mặc định → toàn Đà Nẵng
    """
    # Priority 1: filter theo quận
    if district_id and district_id in _DISTRICT_VIEW:
        return _DISTRICT_VIEW[district_id]

    # Priority 2: search kết quả hẹp
    if df is not None and not df.empty:
        unique = df.drop_duplicates("street_id")
        n = len(unique)
        if n <= 10:
            lat = float(unique["lat"].mean())
            lon = float(unique["lon"].mean())
            zoom = 15 if n <= 3 else 14
            return (lat, lon, zoom)

    # Default: toàn Đà Nẵng
    return (MAP_CENTER_LAT, MAP_CENTER_LON, MAP_ZOOM)


# ── Inject CSS + ambient blobs ────────────────────────────────────
setup_ui()

# ── Auto-refresh mỗi 240 giây — FIX 4: lấy count để tính countdown ──
_refresh_count = st_autorefresh(interval=REFRESH_INTERVAL_MS, key="traffic_refresh")

# ── FIX 4: Theo dõi thời điểm refresh gần nhất để tính countdown ──
if (
    "last_refresh_count" not in st.session_state
    or st.session_state.last_refresh_count != _refresh_count
):
    st.session_state.last_refresh_count = _refresh_count
    st.session_state.last_refresh_ts    = time.time()

_elapsed          = time.time() - st.session_state.get("last_refresh_ts", time.time())
_seconds_remaining = max(0, int(_REFRESH_SECS - _elapsed))


def render_header(data_as_of: str, seconds_remaining: int = 60) -> None:
    """Header trang + nút làm mới — SCRUM 12 | FIX 4: countdown thực tế."""
    col_title, col_refresh = st.columns([5, 1])

    with col_title:
        st.markdown(f"""
        <div class="page-header">
            <h1><span style="-webkit-text-fill-color:initial;color:#f8fafc">🚦</span> Bản đồ Giao thông Đà Nẵng</h1>
            <div class="page-meta">
                <span><span class="status-dot"></span>Live</span>
                <span>·</span>
                <span>Data TomTom: <b style="color:#94a3b8">{data_as_of}</b></span>
                <span>·</span>
                <span title="Trang kiểm tra data mới mỗi 240s. Scheduler thu thập từ TomTom mỗi 30 phút.">Kiểm tra lại sau <b style="color:#94a3b8">{seconds_remaining}s</b></span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_refresh:
        st.markdown("<div style='padding-top:18px'>", unsafe_allow_html=True)
        if st.button("🔄 Làm mới", key="btn_refresh"):
            st.cache_data.clear()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_street_table(df) -> None:
    """Bảng chi tiết bên dưới map."""
    st.markdown("""
    <div style="font-size:0.95rem; font-weight:700; color:#e2e8f0;
                margin:8px 0 12px; letter-spacing:-0.01em">
        📋 Chi tiết tuyến đường
    </div>
    """, unsafe_allow_html=True)

    cols = ["name", "district", "avg_speed", "max_speed", "congestion_label", "timestamp_vn"]
    available = [c for c in cols if c in df.columns]
    display_df = (
        df[["street_id"] + available]
        .drop_duplicates("street_id")
        .drop(columns=["street_id"])
        .rename(columns={
            "name"            : "Tên đường",
            "district"        : "Quận",
            "avg_speed"       : "Tốc độ (km/h)",
            "max_speed"       : "Giới hạn (km/h)",
            "congestion_label": "Tình trạng",
            "timestamp_vn"    : "Cập nhật lúc",
        })
        .sort_values("Tốc độ (km/h)")
        .reset_index(drop=True)
    )
    st.dataframe(display_df, width="stretch", hide_index=True)


def render_footer() -> None:
    """Footer — SCRUM 13."""
    st.markdown(f"""
    <div class="app-footer">
        🚦 <span>Giao thông Đà Nẵng</span>
        &nbsp;·&nbsp; PBL5 – Quản lý Đô thị Thông minh
        &nbsp;·&nbsp; v{APP_VERSION}
        &nbsp;·&nbsp; Dữ liệu: <span>TomTom</span> + PostgreSQL
    </div>
    """, unsafe_allow_html=True)


def main() -> None:
    # ── Sidebar (Sprint 3: trả 3 giá trị, toggle dự báo nằm trong main view) ──
    district_id, search_text, congestion_filter = render_sidebar()

    # -- Geometry: load 1 lan, luu session_state (khong re-fetch moi 60s) ----------
    geo = st.session_state.get("map_geometry")
    if not geo or not geo.get("streets"):
        with st.spinner("⏳ Đang tải bản đồ (lần đầu)..."):
            st.session_state.map_geometry = get_streets_geometry()
    geometry = st.session_state.map_geometry

    if district_id is None and geometry.get("streets"):
        # 2-step: state nhe (~1MB), geometry da cache trong session
        with st.spinner("⏳ Đang cập nhật giao thông..."):
            traffic_state = get_traffic_state()
        df_full, meta = build_map_dataframe_split(geometry, traffic_state)
    else:
        # Fallback cho filter quan hoac geometry chua co
        with st.spinner("⏳ Đang tải dữ liệu giao thông..."):
            traffic = get_traffic_data(district_id)
        df_full = build_map_dataframe(traffic)
        # Normalize key: API tra 'avg_speed', render_kpi_cards can 'avg_speed_city'
        meta = {**traffic, "avg_speed_city": traffic.get("avg_speed_city") or traffic.get("avg_speed", 0)}

    # -- Header -------------------------------------------------------------------
    render_header(_fmt_time(meta.get("data_as_of", "")), _seconds_remaining)
    st.markdown("<hr>", unsafe_allow_html=True)

    # -- KPI Cards ----------------------------------------------------------------
    render_kpi_cards(meta)

    # -- Empty state --------------------------------------------------------------
    if df_full.empty:
        st.warning("⚠️ Chưa có dữ liệu giao thông. Backend đang khởi động?")
        def _retry():
            st.session_state.pop("map_geometry", None)
            st.cache_data.clear()
        st.button("🔄 Thử lại", key="btn_retry", on_click=_retry)
        render_footer()
        return


    # ── SCRUM-22, 23: Áp dụng filter client-side ─────────────────
    df = filter_dataframe(df_full, search=search_text, congestion=congestion_filter)

    # ── Empty state khi filter không có kết quả ──────────────────
    if df.empty and not df_full.empty:
        active_filters = []
        if search_text:
            active_filters.append(f'tên chứa "{search_text}"')
        if congestion_filter is not None:
            labels = {0: "Thông thoáng", 1: "Chậm", 2: "Kẹt xe"}
            active_filters.append(f'mức "{labels[congestion_filter]}"')
        st.info(f"🔍 Không tìm thấy đường nào với bộ lọc: {' + '.join(active_filters)}")
        render_footer()
        return

    # ── FIX 1: Tính view state zoom theo filter (SCRUM-22/24) ────
    view_lat, view_lon, view_zoom = _compute_view(district_id, df)

    # ── TASK #27: Toggle chế độ dự báo — glassmorphism pill ─────────────
    st.markdown("""
    <style>
    /* Container bao quần toggle */
    div[data-testid="stToggle"] {
        background: rgba(139,92,246,0.08);
        border: 1px solid rgba(167,139,250,0.25);
        border-radius: 50px;
        padding: 8px 20px 8px 14px;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.25),
                    inset 0 1px 0 rgba(255,255,255,0.06);
        transition: border-color 0.3s ease, box-shadow 0.3s ease,
                    background 0.3s ease;
        width: fit-content;
    }
    div[data-testid="stToggle"]:hover {
        border-color: rgba(167,139,250,0.5);
        background: rgba(139,92,246,0.15);
        box-shadow: 0 0 28px rgba(139,92,246,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.09);
    }
    /* Nhãn chữ */
    div[data-testid="stToggle"] label p,
    div[data-testid="stToggle"] label span {
        color: #c4b5fd !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        letter-spacing: 0.02em !important;
    }
    /* Track — nền nút gạt khi OFF */
    div[data-testid="stToggle"] [role="switch"] {
        background: rgba(109,40,217,0.35) !important;
        border: 1px solid rgba(167,139,250,0.3) !important;
    }
    /* Track khi ON */
    div[data-testid="stToggle"] [role="switch"][aria-checked="true"] {
        background: rgba(139,92,246,0.85) !important;
        box-shadow: 0 0 10px rgba(139,92,246,0.5) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    _col_toggle, _ = st.columns([2, 5])
    with _col_toggle:
        show_prediction: bool = st.toggle(
            "🔮 Xem dự báo 30 phút tới",
            key="home_show_prediction",
            help="Chuyển bản đồ sang hiển thị dự báo AI thay vì dữ liệu thực tế",
        )

    # ── TASK #27: Nếu toggle dự báo → thay congestion_level + color ──────
    if show_prediction:
        preds = get_predictions()  # list [{street_id, predicted_level, confidence}, ...]
        if preds:
            pred_map = {p["street_id"]: p.get("predicted_level") for p in preds}
            df = df.copy()
            # Ghi đè congestion_level theo dự báo
            df["congestion_level"] = df["street_id"].map(
                lambda sid: pred_map.get(sid, None)
            )
            # BUG FIX: cập nhật cột color — Pydeck đọc color, không đọc congestion_level!
            df["color"] = df["congestion_level"].map(
                lambda lv: _PREDICT_COLORS.get(int(lv), [107, 114, 128, 150])
                if lv is not None and str(lv) != "nan"
                else [107, 114, 128, 150]
            )

        # Banner dự báo — TASK #27d
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, rgba(126,34,206,0.18), rgba(168,85,247,0.10));
            border: 1px solid rgba(168,85,247,0.35);
            border-radius: 12px;
            padding: 10px 18px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.875rem;
        ">
            <span style="font-size:1.2rem">📡</span>
            <span style="color:#c084fc;font-weight:700">CHẾ ĐỘ DỰ BÁO AI</span>
            <span style="color:#94a3b8">· Hiển thị mức ùn tắc dự kiến sau 30 phút.</span>
            <span style="color:#6b7280;font-size:0.78rem;margin-left:auto">Màu tím = dự báo</span>
        </div>
        """, unsafe_allow_html=True)

    # ── Map (SCRUM 8,9,10) ────────────────────────────────────────
    render_map(df, height=560, view_lat=view_lat, view_lon=view_lon, view_zoom=view_zoom)

    st.markdown("<hr style='margin:12px 0 8px'>", unsafe_allow_html=True)

    # ── Bảng chi tiết (theo data đã filter) ──────────────────────
    render_street_table(df)

    # ── Footer ────────────────────────────────────────────────────
    render_footer()


if __name__ == "__main__":
    main()
