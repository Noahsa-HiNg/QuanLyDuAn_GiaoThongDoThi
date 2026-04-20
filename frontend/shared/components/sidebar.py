"""
shared/components/sidebar.py — Sidebar Bộ lọc + Chú thích
v1.0
"""

import streamlit as st


DISTRICT_OPTIONS: dict[str, int | None] = {
    "🗺️ Tất cả quận/huyện": None,
    "Hải Châu"      : 1,
    "Thanh Khê"     : 2,
    "Sơn Trà"       : 3,
    "Ngũ Hành Sơn"  : 4,
    "Liên Chiểu"    : 5,
    "Cẩm Lệ"        : 6,
    "Hòa Vang"      : 7,
    "Hoàng Sa"      : 8,
}


def render_sidebar() -> int | None:
    """
    Render sidebar với:
      - Logo + trạng thái hệ thống
      - Selectbox chọn quận
      - Chú thích màu sắc
      - Nút làm mới
    Trả về district_id đang chọn (None = tất cả).
    """
    with st.sidebar:
        # ── Header ──────────────────────────────────────────
        st.markdown("""
        <div style="text-align:center; padding: 8px 0 20px">
            <div style="font-size:2.4rem">🚦</div>
            <div style="font-size:1.1rem; font-weight:700; color:#f1f5f9; margin:4px 0">
                Giao thông Đà Nẵng
            </div>
            <div style="font-size:0.75rem; color:#64748b">
                <span class="status-dot"></span>Dữ liệu thời gian thực
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── Bộ lọc quận ─────────────────────────────────────
        st.markdown("**🔽 Lọc theo quận/huyện**")
        selected = st.selectbox(
            label="Quận",
            options=list(DISTRICT_OPTIONS.keys()),
            label_visibility="collapsed",
        )
        district_id = DISTRICT_OPTIONS[selected]

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
            📡 Nguồn: TomTom Traffic API<br>
            🔄 Cập nhật: mỗi 60 giây<br>
            🗃️ DB: PostgreSQL + PostGIS
        </div>
        """, unsafe_allow_html=True)

    return district_id
