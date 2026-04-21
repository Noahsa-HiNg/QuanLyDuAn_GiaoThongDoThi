"""
pages/1_home.py — Trang Bản đồ Giao thông Đà Nẵng
Sprint 1 | SCRUM 8,9,10,11,12,13,14
Sprint 2 | SCRUM 22,23,24,25,26,28
v1.2 — Wire Sprint 2 filters (search, congestion, reset)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from config import APP_TITLE, APP_ICON, REFRESH_INTERVAL_MS, APP_VERSION
from shared.utils.css_loader import setup_ui
from shared.components.sidebar import render_sidebar
from shared.components.kpi_cards import render_kpi_cards
from features.map.service import get_traffic_data, build_map_dataframe, filter_dataframe
from features.map.components import render_map
from datetime import datetime, timezone, timedelta


def _fmt_time(iso_str: str) -> str:
    """Convert ISO timestamp → giờ Việt Nam dạng dd/mm HH:MM."""
    try:
        s = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s).astimezone(timezone(timedelta(hours=7)))
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return iso_str


# ── Page config (phải là lệnh Streamlit đầu tiên) ────────────────
st.set_page_config(
    page_title=f"Bản đồ | {APP_TITLE}",
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",   # Luôn mở khi load lần đầu
)

# ── Inject CSS + ambient blobs (PHẢI sau set_page_config) ────────
setup_ui()

# ── Auto-refresh mỗi 60 giây ─────────────────────────────────────
st_autorefresh(interval=REFRESH_INTERVAL_MS, key="traffic_refresh")


def render_header(data_as_of: str) -> None:
    """Header trang + nút làm mới — SCRUM 12."""
    col_title, col_refresh = st.columns([5, 1])

    with col_title:
        st.markdown(f"""
        <div class="page-header">
            <h1>🚦 Bản đồ Giao thông Đà Nẵng</h1>
            <div class="page-meta">
                <span><span class="status-dot"></span>Live</span>
                <span>·</span>
                <span>Cập nhật: <b style="color:#94a3b8">{data_as_of}</b></span>
                <span>·</span>
                <span>Tự làm mới sau 60s</span>
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
    # Chỉ lấy những cột thực sự tồn tại và deduplicate theo street_id
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

    # ── Header ───────────────────────────────────────────────────
    render_header(_fmt_time(traffic.get("data_as_of", "")))
    st.markdown("<hr>", unsafe_allow_html=True)

    # ── KPI Cards (SCRUM 11) — dựa trên toàn bộ data quận ───────
    render_kpi_cards(traffic)

    # ── SCRUM-28: Empty state — backend chưa có data ─────────────
    if not traffic.get("streets"):
        st.warning("⚠️ Chưa có dữ liệu giao thông. Backend đang khởi động?")
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

    # ── Map (SCRUM 8,9,10) ────────────────────────────────────────
    render_map(df, height=560)

    st.markdown("<hr style='margin:12px 0 8px'>", unsafe_allow_html=True)

    # ── Bảng chi tiết (theo data đã filter) ──────────────────────
    render_street_table(df)

    # ── Footer ────────────────────────────────────────────────────
    render_footer()


if __name__ == "__main__":
    main()
