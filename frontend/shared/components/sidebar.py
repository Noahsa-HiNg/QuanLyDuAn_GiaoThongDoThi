"""
shared/components/sidebar.py — Sidebar Bộ lọc + Chú thích
v2.0 — Sprint 2

SCRUM 22: Tìm kiếm tên đường (client-side filter)
SCRUM 23: Lọc theo mức ùn tắc
SCRUM 24: Lọc theo quận/huyện (giữ từ v1.0, pass district_id lên API)
SCRUM 25: Nút Reset bộ lọc (session_state, không clear cache)
"""

import streamlit as st


# ── Dữ liệu tuỳ chọn ──────────────────────────────────────────────────────────

DISTRICT_OPTIONS: dict[str, int | None] = {
    "🗺️ Tất cả quận/huyện": None,
    "Hải Châu"             : 1,
    "Thanh Khê"            : 2,
    "Sơn Trà"              : 3,
    "Ngũ Hành Sơn"         : 4,
    "Liên Chiểu"           : 5,
    "Cẩm Lệ"               : 6,
    "Hòa Vang"             : 7,
    "Hoàng Sa"             : 8,
}

CONGESTION_OPTIONS: dict[str, int | None] = {
    "🔵 Tất cả mức"   : None,
    "🟢 Thông thoáng" : 0,
    "🟡 Chậm"         : 1,
    "🔴 Kẹt xe"       : 2,
}

# Session state keys — prefix "sb_" tránh xung đột với widget khác
_KEY_DISTRICT   = "sb_district"
_KEY_CONGESTION = "sb_congestion"
_KEY_SEARCH     = "sb_search"

_DEFAULT_DISTRICT   = list(DISTRICT_OPTIONS.keys())[0]    # "🗺️ Tất cả quận/huyện"
_DEFAULT_CONGESTION = list(CONGESTION_OPTIONS.keys())[0]   # "🔵 Tất cả mức"
_DEFAULT_SEARCH     = ""


# ── Session state helpers ──────────────────────────────────────────────────────

def _init_session() -> None:
    """Khởi tạo session state mặc định nếu chưa tồn tại."""
    defaults = {
        _KEY_DISTRICT   : _DEFAULT_DISTRICT,
        _KEY_CONGESTION : _DEFAULT_CONGESTION,
        _KEY_SEARCH     : _DEFAULT_SEARCH,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _reset_filters() -> None:
    """Đặt lại tất cả bộ lọc về mặc định — SCRUM 25."""
    st.session_state[_KEY_DISTRICT]   = _DEFAULT_DISTRICT
    st.session_state[_KEY_CONGESTION] = _DEFAULT_CONGESTION
    st.session_state[_KEY_SEARCH]     = _DEFAULT_SEARCH


def _is_filtered() -> bool:
    """True nếu có ít nhất 1 bộ lọc đang hoạt động."""
    return (
        st.session_state.get(_KEY_DISTRICT,   _DEFAULT_DISTRICT)   != _DEFAULT_DISTRICT
        or st.session_state.get(_KEY_CONGESTION, _DEFAULT_CONGESTION) != _DEFAULT_CONGESTION
        or st.session_state.get(_KEY_SEARCH,     _DEFAULT_SEARCH)     != _DEFAULT_SEARCH
    )


# ── Main render ───────────────────────────────────────────────────────────────

def render_sidebar() -> tuple[int | None, str, int | None]:
    """
    Render sidebar với bộ lọc đầy đủ Sprint 2.

    Returns:
        district_id (int | None) — ID quận đang lọc; None = tất cả
        search_text (str)        — Từ khoá tìm tên đường; "" = không lọc
        congestion  (int | None) — Mức ùn tắc đang lọc; None = tất cả
    """
    _init_session()

    with st.sidebar:

        # ── Header ──────────────────────────────────────────
        st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;padding:10px 0 16px">
            <div style="font-size:1.7rem;line-height:1">🚦</div>
            <div>
                <div style="font-size:1rem;font-weight:700;color:#f1f5f9;line-height:1.3">
                    Giao thông Đà Nẵng
                </div>
                <div style="font-size:0.74rem;color:#64748b;margin-top:2px">
                    Dữ liệu thời gian thực
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── SCRUM-22: Tìm kiếm tên đường ────────────────────
        st.markdown("**🔍 Tìm kiếm tên đường**")
        search_text: str = st.text_input(
            label="Tìm đường",
            placeholder="VD: Bạch Đằng, Lê Duẩn...",
            key=_KEY_SEARCH,
            label_visibility="collapsed",
        )

        # ── SCRUM-24: Lọc theo quận ──────────────────────────
        st.markdown("**📍 Lọc theo quận/huyện**")
        district_label: str = st.selectbox(
            label="Quận",
            options=list(DISTRICT_OPTIONS.keys()),
            key=_KEY_DISTRICT,
            label_visibility="collapsed",
        )
        district_id = DISTRICT_OPTIONS[district_label]

        # ── SCRUM-23: Lọc theo mức ùn tắc ──────────────────
        st.markdown("**🚦 Lọc theo mức ùn tắc**")
        congestion_label: str = st.selectbox(
            label="Mức kẹt",
            options=list(CONGESTION_OPTIONS.keys()),
            key=_KEY_CONGESTION,
            label_visibility="collapsed",
        )
        congestion_filter = CONGESTION_OPTIONS[congestion_label]

        # ── SCRUM-25: Nút Reset bộ lọc ──────────────────────
        # Dùng on_click callback thay vì set session_state bên trong if-block.
        # Lý do: Streamlit không cho sửa session_state[key] sau khi widget
        # với key đó đã được render trong cùng 1 script run.
        # on_click chạy trước render tiếp theo → không xảy ra conflict.
        filter_active = _is_filtered()
        st.button(
            "↩️ Reset bộ lọc",
            use_container_width=True,
            disabled=not filter_active,
            type="secondary",
            key="btn_reset_filter",
            help="Đặt lại tất cả bộ lọc về mặc định",
            on_click=_reset_filters,   # ← callback chạy trước render kế tiếp
        )

        st.divider()

        # ── Chú thích màu sắc ────────────────────────────────
        st.markdown("**🎨 Chú thích**")
        st.markdown("""
        <div style="font-size:0.85rem; line-height:2.2">
            <div><span style="color:#4ade80; font-size:1rem">●</span>
                 <span style="color:#94a3b8"> Thông thoáng (≥70% vận tốc)</span></div>
            <div><span style="color:#fbbf24; font-size:1rem">●</span>
                 <span style="color:#94a3b8"> Chậm (40–70% vận tốc)</span></div>
            <div><span style="color:#f87171; font-size:1rem">●</span>
                 <span style="color:#94a3b8"> Kẹt xe (&lt;40% vận tốc)</span></div>
            <div><span style="color:#6b7280; font-size:1rem">●</span>
                 <span style="color:#94a3b8"> Chưa có dữ liệu</span></div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── Info ─────────────────────────────────────────────
        st.markdown("""
        <div style="font-size:0.75rem; color:#475569; line-height:1.8">
            📡 Nguồn: TomTom + Goong API<br>
            🔄 Thu thập data: mỗi 30 phút<br>
            🖥️ Trang kiểm tra: mỗi 60 giây<br>
            🗃️ DB: PostgreSQL + PostGIS
        </div>
        """, unsafe_allow_html=True)

    return district_id, search_text.strip(), congestion_filter
