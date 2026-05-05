"""
shared/components/sidebar.py — Sidebar Bộ lọc + Chú thích
v3.0 — Sprint 3

SCRUM 22: Tìm kiếm tên đường (client-side filter)
SCRUM 23: Lọc theo mức ùn tắc
SCRUM 24: Lọc theo quận/huyện (giữ từ v1.0, pass district_id lên API)
SCRUM 25: Nút Reset bộ lọc (session_state, không clear cache)
TASK #27: Toggle "Xem dự báo 30 phút" trên bản đồ
TASK #35d: Widget user đã đăng nhập + nút Đăng xuất
"""

import streamlit as st
from shared.api.client import get_weather_current


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


def _do_logout() -> None:
    """Xóa auth session — S3-35d."""
    for key in ("token", "user_name", "user_role", "user_email", "logged_in"):
        st.session_state.pop(key, None)


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
    Render sidebar với bộ lọc (trong expander) + weather widget + auth widget.

    Returns:
        district_id  (int | None) — ID quận đang lọc; None = tất cả
        search_text  (str)        — Từ khoá tìm tên đường; "" = không lọc
        congestion   (int | None) — Mức ùn tắc đang lọc; None = tất cả
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

        # ── Weather widget ────────────────────────────
        _WEATHER_ICONS = {
            0: ("☀️", "Trời quang"),
            1: ("⛅", "Ít mây"),
            2: ("☁️", "Nhiều mây"),
            3: ("🌧️", "Mưa"),
            4: ("⛈️", "Bão dông"),
        }
        w = get_weather_current()
        if w:
            temp       = w.get("temperature", "--")
            humidity   = w.get("humidity", "--")
            wind       = w.get("wind_speed", 0)
            rain       = w.get("rain_1h_mm", 0)
            is_raining = w.get("is_raining", 0)
            grp        = w.get("weather_group", 0)
            icon, desc = _WEATHER_ICONS.get(grp, ("🌡️", "Không rõ"))
            rain_txt   = f"🌧️ {rain:.1f} mm" if is_raining else "☀️ Không mưa"
            st.markdown(f"""
            <div style="
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 16px;
                padding: 12px 16px;
                backdrop-filter: blur(16px);
                -webkit-backdrop-filter: blur(16px);
                box-shadow: 0 4px 24px rgba(0,0,0,0.3),
                            inset 0 1px 0 rgba(255,255,255,0.08);
                margin-bottom: 2px;
            ">
                <div style="display:flex;align-items:center;justify-content:space-between">
                    <div>
                        <div style="font-size:1.5rem;font-weight:800;color:#f1f5f9;line-height:1;
                                    text-shadow: 0 0 12px rgba(255,255,255,0.15)">
                            {icon} {temp:.0f}°C
                        </div>
                        <div style="font-size:0.74rem;color:#94a3b8;margin-top:4px;
                                    letter-spacing:0.04em">{desc}</div>
                    </div>
                    <div style="text-align:right;font-size:0.78rem;color:#64748b;line-height:2.2">
                        <div style="color:#7dd3fc">💧 {humidity}%</div>
                        <div style="color:#93c5fd">💨 {wind:.1f} m/s</div>
                    </div>
                </div>
                <div style="
                    font-size:0.72rem;color:#475569;
                    margin-top:8px;
                    border-top:1px solid rgba(255,255,255,0.06);
                    padding-top:6px;
                    letter-spacing:0.03em;
                ">{rain_txt}</div>
            </div>
            """, unsafe_allow_html=True)
        # Không st.divider() ở đây — tránh 2 kẻ ngang liên tiếp khi chưa login

        # ── S3-35d: User widget ──────────────────────────────
        if st.session_state.get("logged_in") and st.session_state.get("token"):
            user_name = st.session_state.get("user_name", "Người dùng")
            user_role = st.session_state.get("user_role", "")
            role_color = "#f87171" if user_role == "admin" else "#60a5fa"
            role_icon  = "👑" if user_role == "admin" else "🚔"
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);
                        border-radius:12px;padding:10px 14px;margin-bottom:12px">
                <div style="display:flex;align-items:center;gap:8px">
                    <div style="font-size:1.4rem">{role_icon}</div>
                    <div>
                        <div style="font-size:0.82rem;font-weight:700;color:#e2e8f0;line-height:1.2">
                            {user_name}
                        </div>
                        <div style="font-size:0.7rem;color:{role_color};font-weight:600;
                                    letter-spacing:0.04em;margin-top:2px">
                            {user_role.upper()}
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.button(
                "🚪 Đăng xuất",
                use_container_width=True,
                type="secondary",
                key="sidebar_logout",
                on_click=_do_logout,
            )
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

        st.divider()

        # CSS morphia cho expander bộ lọc
        st.markdown("""
        <style>
        div[data-testid="stExpander"] {
            background: rgba(99,102,241,0.06) !important;
            border: 1px solid rgba(99,102,241,0.22) !important;
            border-radius: 14px !important;
            backdrop-filter: blur(12px) !important;
            overflow: hidden !important;
            transition: border-color 0.3s ease !important;
        }
        div[data-testid="stExpander"]:hover {
            border-color: rgba(99,102,241,0.4) !important;
            box-shadow: 0 0 16px rgba(99,102,241,0.08) !important;
        }
        div[data-testid="stExpander"] summary {
            color: #818cf8 !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            letter-spacing: 0.02em !important;
            padding: 10px 14px !important;
        }
        div[data-testid="stExpander"] summary:hover {
            color: #a5b4fc !important;
            background: rgba(99,102,241,0.06) !important;
        }
        div[data-testid="stExpanderDetails"] {
            padding: 4px 10px 12px !important;
            border-top: 1px solid rgba(99,102,241,0.12) !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # ── Bộ lọc bản đồ (trong expander) ──────────────────
        with st.expander("🔍 Bộ lọc bản đồ", expanded=False):
            # SCRUM-22: Tìm kiếm tên đường
            st.markdown('<p style="font-size:0.8rem;color:#94a3b8;margin-bottom:4px">Tìm tên đường</p>',
                        unsafe_allow_html=True)
            search_text: str = st.text_input(
                label="Tìm đường",
                placeholder="VD: Bạch Đằng, Lê Duẩn...",
                key=_KEY_SEARCH,
                label_visibility="collapsed",
            )

            # SCRUM-24: Lọc theo quận
            st.markdown('<p style="font-size:0.8rem;color:#94a3b8;margin:8px 0 4px">Quận/Huyện</p>',
                        unsafe_allow_html=True)
            district_label: str = st.selectbox(
                label="Quận",
                options=list(DISTRICT_OPTIONS.keys()),
                key=_KEY_DISTRICT,
                label_visibility="collapsed",
            )
            district_id = DISTRICT_OPTIONS[district_label]

            # SCRUM-23: Lọc theo mức ùn tắc
            st.markdown('<p style="font-size:0.8rem;color:#94a3b8;margin:8px 0 4px">Mức ùn tắc</p>',
                        unsafe_allow_html=True)
            congestion_label: str = st.selectbox(
                label="Mức kẹt",
                options=list(CONGESTION_OPTIONS.keys()),
                key=_KEY_CONGESTION,
                label_visibility="collapsed",
            )
            congestion_filter = CONGESTION_OPTIONS[congestion_label]

            # SCRUM-25: Nút Reset
            filter_active = _is_filtered()
            st.button(
                "↩️ Reset bộ lọc",
                use_container_width=True,
                disabled=not filter_active,
                type="secondary",
                key="btn_reset_filter",
                help="Đặt lại tất cả bộ lọc về mặc định",
                on_click=_reset_filters,
            )

        st.divider()

        # ── Chú thích màu sắc — reactive theo trạng thái dự báo ──────
        _is_pred = st.session_state.get("home_show_prediction", False)
        if _is_pred:
            st.markdown("""
            <div style="background:rgba(126,34,206,0.08);border:1px solid rgba(168,85,247,0.2);
                        border-radius:10px;padding:7px 12px;margin-bottom:8px;font-size:0.78rem;
                        color:#c084fc;font-weight:600;letter-spacing:0.03em">
                🔮 ĐANG XEM DỰ BÁO AI
            </div>
            """, unsafe_allow_html=True)
            st.markdown("""
            <div style="font-size:0.85rem; line-height:2.2">
                <div><span style="color:#4ade80; font-size:1rem">●</span>
                     <span style="color:#94a3b8"> Dự báo: Sẽ thông thoáng</span></div>
                <div><span style="color:#fbbf24; font-size:1rem">●</span>
                     <span style="color:#94a3b8"> Dự báo: Sẽ chậm</span></div>
                <div><span style="color:#f87171; font-size:1rem">●</span>
                     <span style="color:#94a3b8"> Dự báo: Sẽ kẹt xe</span></div>
                <div><span style="color:#6b7280; font-size:1rem">●</span>
                     <span style="color:#94a3b8"> Chưa có dự báo</span></div>
            </div>
            """, unsafe_allow_html=True)
        else:
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
