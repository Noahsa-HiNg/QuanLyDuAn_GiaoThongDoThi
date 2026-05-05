"""
shared/components/sidebar.py — Sidebar Navigation + Bộ lọc + Chú thích
v4.0 — Sprint 4

Phân quyền 3 cấp:
  Guest  (chưa login): Home | Route Finder | Đăng nhập
  CSGT   (đã login)  : [User widget] | Home | Dashboard | Route Finder
  Admin  (đã login)  : [User widget] | Home | Dashboard | Route Finder | ⚙️ Quản trị

SCRUM 22: Tìm kiếm tên đường (client-side filter)
SCRUM 23: Lọc theo mức ùn tắc
SCRUM 24: Lọc theo quận/huyện
SCRUM 25: Nút Reset bộ lọc
TASK #35d: Widget user + Đăng xuất (minimal, đầu sidebar)
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

_KEY_DISTRICT   = "sb_district"
_KEY_CONGESTION = "sb_congestion"
_KEY_SEARCH     = "sb_search"

_DEFAULT_DISTRICT   = list(DISTRICT_OPTIONS.keys())[0]
_DEFAULT_CONGESTION = list(CONGESTION_OPTIONS.keys())[0]
_DEFAULT_SEARCH     = ""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _init_session() -> None:
    defaults = {
        _KEY_DISTRICT  : _DEFAULT_DISTRICT,
        _KEY_CONGESTION: _DEFAULT_CONGESTION,
        _KEY_SEARCH    : _DEFAULT_SEARCH,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _do_logout() -> None:
    for key in ("token", "user_name", "user_role", "user_email", "logged_in"):
        st.session_state.pop(key, None)


def _reset_filters() -> None:
    st.session_state[_KEY_DISTRICT]   = _DEFAULT_DISTRICT
    st.session_state[_KEY_CONGESTION] = _DEFAULT_CONGESTION
    st.session_state[_KEY_SEARCH]     = _DEFAULT_SEARCH


def _is_filtered() -> bool:
    return (
        st.session_state.get(_KEY_DISTRICT,   _DEFAULT_DISTRICT)   != _DEFAULT_DISTRICT
        or st.session_state.get(_KEY_CONGESTION, _DEFAULT_CONGESTION) != _DEFAULT_CONGESTION
        or st.session_state.get(_KEY_SEARCH,     _DEFAULT_SEARCH)     != _DEFAULT_SEARCH
    )


# ── Main render ───────────────────────────────────────────────────────────────

def render_sidebar(
    show_map_controls: bool = True,
    brand_icon: str = "🚦",
    brand_title: str = "Giao thông Đà Nẵng",
    brand_subtitle: str = "Dữ liệu thời gian thực",
) -> tuple[int | None, str, int | None]:
    """
    Render sidebar với navigation theo role + bộ lọc (tuỳ chọn).

    Args:
        show_map_controls : True để hiện weather + filter + legend.
        brand_icon        : Emoji icon hiện ở branding (mặc định 🚦).
        brand_title       : Tiêu đề branding (mặc định "Giao thông Đà Nẵng").
        brand_subtitle    : Phụ đề branding (mặc định "Dữ liệu thời gian thực").
    Returns:
        district_id  (int | None)
        search_text  (str)
        congestion   (int | None)
    """
    _init_session()

    # Giá trị mặc định trả về khi không show controls
    district_id      = None
    search_text      = ""
    congestion_filter = None

    # Đọc trạng thái auth
    logged_in = st.session_state.get("logged_in", False) and bool(st.session_state.get("token"))
    user_role = st.session_state.get("user_role", "")
    user_name = st.session_state.get("user_name", "")

    with st.sidebar:

        # ── 1. CSS: nav link to hơn, bỏ icon tự động ───────────────
        st.markdown("""
        <style>
        /* Tăng cỡ chữ nav link */
        section[data-testid="stSidebar"] [data-testid="stPageLink"] p {
            font-size: 0.97rem !important;
            font-weight: 500 !important;
            letter-spacing: 0.01em;
        }
        section[data-testid="stSidebar"] [data-testid="stPageLink"] {
            padding: 6px 4px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # ── 2. User widget (trên cùng) ────────────────────────────────
        if logged_in:
            role_icon  = "👑" if user_role == "admin" else "🚔"
            role_color = "#fbbf24" if user_role == "admin" else "#60a5fa"
            _col_u, _col_l = st.columns([4, 1])
            with _col_u:
                st.markdown(
                    f'<div style="font-size:0.82rem;color:#e2e8f0;font-weight:600;'
                    f'padding:4px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                    f'{role_icon} <span style="color:{role_color}">{user_name}</span></div>',
                    unsafe_allow_html=True,
                )
            with _col_l:
                st.button(
                    "↩",
                    key="sb_logout_btn",
                    on_click=_do_logout,
                    help="Đăng xuất",
                    use_container_width=True,
                )
        else:
            st.markdown(
                '<div style="font-size:0.78rem;color:#475569;padding:6px 2px">'
                '🔓 Chưa đăng nhập</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ── 3. Navigation theo role ───────────────────────────────────
        st.page_link("pages/1_home.py",         label="Bản đồ giao thông", use_container_width=True)
        st.page_link("pages/3_route_finder.py", label="Tìm đường",         use_container_width=True)

        if not logged_in:
            st.page_link("pages/4_login.py",    label="Đăng nhập",         use_container_width=True)
        else:
            st.page_link("pages/2_dashboard.py", label="Dashboard",        use_container_width=True)
            if user_role == "admin":
                st.markdown("""
                <div style="font-size:0.72rem;color:#475569;font-weight:700;
                            letter-spacing:0.08em;padding:10px 4px 4px;
                            text-transform:uppercase">⚙️ Quản trị</div>
                """, unsafe_allow_html=True)
                st.page_link("pages/5_admin_users.py",     label="Quản lý tài khoản",   use_container_width=True)
                st.page_link("pages/6_admin_scheduler.py", label="Quản lý cào dữ liệu", use_container_width=True)

        st.divider()

        # ── 4. Branding (xuống dưới) ──────────────────────────────────
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:6px 0 10px">
            <div style="font-size:1.5rem;line-height:1">{brand_icon}</div>
            <div>
                <div style="font-size:0.88rem;font-weight:700;color:#f1f5f9;line-height:1.3">
                    {brand_title}
                </div>
                <div style="font-size:0.72rem;color:#64748b;margin-top:2px">
                    {brand_subtitle}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── 5. Weather + Filter + Legend (chỉ khi cần) ────────────────
        if show_map_controls:
            st.divider()

            # Weather widget
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

            st.divider()

            # CSS morphia cho expander
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

            # Bộ lọc bản đồ
            with st.expander("🔍 Bộ lọc bản đồ", expanded=False):
                st.markdown('<p style="font-size:0.8rem;color:#94a3b8;margin-bottom:4px">Tìm tên đường</p>',
                            unsafe_allow_html=True)
                search_text = st.text_input(
                    label="Tìm đường",
                    placeholder="VD: Bạch Đằng, Lê Duẩn...",
                    key=_KEY_SEARCH,
                    label_visibility="collapsed",
                )

                st.markdown('<p style="font-size:0.8rem;color:#94a3b8;margin:8px 0 4px">Quận/Huyện</p>',
                            unsafe_allow_html=True)
                district_label = st.selectbox(
                    label="Quận",
                    options=list(DISTRICT_OPTIONS.keys()),
                    key=_KEY_DISTRICT,
                    label_visibility="collapsed",
                )
                district_id = DISTRICT_OPTIONS[district_label]

                st.markdown('<p style="font-size:0.8rem;color:#94a3b8;margin:8px 0 4px">Mức ùn tắc</p>',
                            unsafe_allow_html=True)
                congestion_label_str = st.selectbox(
                    label="Mức kẹt",
                    options=list(CONGESTION_OPTIONS.keys()),
                    key=_KEY_CONGESTION,
                    label_visibility="collapsed",
                )
                congestion_filter = CONGESTION_OPTIONS[congestion_label_str]

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

            # Chú thích — reactive theo toggle dự báo
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

            st.markdown("""
            <div style="font-size:0.75rem; color:#475569; line-height:1.8">
                📡 Nguồn: TomTom + Goong API<br>
                🔄 Thu thập data: mỗi 30 phút<br>
                🖥️ Trang kiểm tra: mỗi 60 giây<br>
                🗃️ DB: PostgreSQL + PostGIS
            </div>
            """, unsafe_allow_html=True)

    return district_id, search_text.strip(), congestion_filter
