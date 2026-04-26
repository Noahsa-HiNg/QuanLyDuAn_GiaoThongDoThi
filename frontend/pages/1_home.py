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
from features.map.service import get_traffic_data, build_map_dataframe, filter_dataframe
from features.map.components import render_map
from datetime import datetime, timezone, timedelta


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


# ── Page config (phải là lệnh Streamlit đầu tiên) ────────────────
st.set_page_config(
    page_title=f"Bản đồ | {APP_TITLE}",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inject CSS + ambient blobs (PHẢI sau set_page_config) ────────
setup_ui()

# ── Auto-refresh mỗi 60 giây — FIX 4: lấy count để tính countdown ──
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
                <span title="Trang kiểm tra data mới mỗi 60s. Scheduler thu thập từ TomTom mỗi 30 phút.">Kiểm tra lại sau <b style="color:#94a3b8">{seconds_remaining}s</b></span>
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
    # ── Sidebar (Sprint 2: trả tuple 3 giá trị) ──────────────────
    district_id, search_text, congestion_filter = render_sidebar()

    # ── Fetch data (SCRUM 14: spinner) ───────────────────────────
    with st.spinner("⏳ Đang tải dữ liệu giao thông..."):
        traffic = get_traffic_data(district_id)

    # ── Header (FIX 4: countdown thực tế) ────────────────────────
    render_header(_fmt_time(traffic.get("data_as_of", "")), _seconds_remaining)
    st.markdown("<hr>", unsafe_allow_html=True)

    # ── KPI Cards (SCRUM 11) — dựa trên toàn bộ data quận ───────
    render_kpi_cards(traffic)

    # ── SCRUM-28 + FIX 5: Empty state — backend chưa có data ─────
    if not traffic.get("streets"):
        st.warning("⚠️ Chưa có dữ liệu giao thông. Backend đang khởi động?")
        # FIX 5: Nút Thử lại để clear cache và reload
        st.button("🔄 Thử lại", key="btn_retry", on_click=st.cache_data.clear)
        render_footer()
        return

    # ── Build DataFrame đầy đủ ───────────────────────────────────
    df_full = build_map_dataframe(traffic)

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

    # ── Map (SCRUM 8,9,10) ────────────────────────────────────────
    render_map(df, height=560, view_lat=view_lat, view_lon=view_lon, view_zoom=view_zoom)

    st.markdown("<hr style='margin:12px 0 8px'>", unsafe_allow_html=True)

    # ── Bảng chi tiết (theo data đã filter) ──────────────────────
    render_street_table(df)

    # ── Footer ────────────────────────────────────────────────────
    render_footer()


if __name__ == "__main__":
    main()
