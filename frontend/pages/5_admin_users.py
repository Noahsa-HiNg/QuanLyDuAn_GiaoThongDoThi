"""
pages/5_admin_users.py — Quản lý tài khoản (Admin only)
Sprint 4

Chức năng:
  - Xem danh sách tất cả tài khoản
  - Tạo tài khoản mới (CSGT / Admin)
  - Khóa / Mở khóa tài khoản
  - Vô hiệu hóa tài khoản
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from config import APP_TITLE, APP_ICON, APP_VERSION
from shared.utils.css_loader import setup_ui
from shared.utils.auth_guard import require_admin
from shared.components.sidebar import render_sidebar
from shared.api.client import (
    admin_get_users, admin_create_user,
    admin_lock_user, admin_unlock_user, admin_deactivate_user,
)

# ── Page config ────────────────────────────────────────────────────
setup_ui()
require_admin()   # ← Chỉ Admin

# ── Sidebar ─────────────────────────────────────────────────────
render_sidebar(
    show_map_controls=False,
    brand_icon="👥",
    brand_title="Quản lý tài khoản",
    brand_subtitle="Hệ thống phân quyền RBAC",
)
with st.sidebar:
    st.divider()
    st.markdown("""
    <div style="background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.18);
                border-radius:14px;padding:14px 16px;margin-bottom:4px">
        <div style="font-size:0.82rem;font-weight:700;color:#fbbf24;margin-bottom:8px">
            👑 Phân quyền hệ thống
        </div>
        <div style="font-size:0.77rem;color:#94a3b8;line-height:1.7">
            👑 <b style="color:#e2e8f0">Admin</b> — toàn quyền quản trị<br>
            🚔 <b style="color:#e2e8f0">CSGT</b> — xem dashboard, tìm đường
        </div>
    </div>
    <div style="font-size:0.73rem;color:#475569;padding:6px 2px;line-height:1.7">
        🔒 Khóa tài khoản — vô hiệu hóa thảo lượt đăng nhập<br>
        ⛔ Vô hiệu hóa — nếu không còn sử dụng
    </div>
    """, unsafe_allow_html=True)

# ── CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@keyframes fadeInUp {
  from { opacity:0; transform:translateY(12px); }
  to   { opacity:1; transform:translateY(0); }
}
.admin-page { animation: fadeInUp 0.4s ease-out; }

/* Metric cards */
.metric-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 16px 20px;
    text-align: center;
    backdrop-filter: blur(12px);
}
.metric-value {
    font-size: 2rem;
    font-weight: 800;
    line-height: 1;
    margin-bottom: 4px;
}
.metric-label {
    font-size: 0.78rem;
    color: #64748b;
    letter-spacing: 0.04em;
}

/* User table */
.user-table { width:100%; border-collapse:collapse; font-size:0.84rem; }
.user-table thead tr {
    background: rgba(99,102,241,0.12);
    border-bottom: 1px solid rgba(99,102,241,0.2);
}
.user-table th {
    padding: 10px 14px;
    text-align: left;
    color: #818cf8;
    font-weight: 600;
    font-size: 0.78rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.user-table tbody tr {
    border-bottom: 1px solid rgba(255,255,255,0.04);
    transition: background 0.2s;
}
.user-table tbody tr:hover { background: rgba(255,255,255,0.03); }
.user-table td { padding: 10px 14px; color: #cbd5e1; vertical-align: middle; }
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
}
</style>
""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────────
st.markdown("""
<div class="admin-page">
<h1 style="margin:0 0 4px;font-size:1.6rem;font-weight:800;
           display:flex;align-items:center;gap:10px">
    <span>&#x1F465;</span>
    <span style="background:linear-gradient(135deg,#f1f5f9 30%,#818cf8 100%);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                 background-clip:text">Quản lý tài khoản</span>
</h1>
<p style="color:#64748b;font-size:0.88rem;margin:0 0 24px">
    Tạo, khóa, và quản lý tài khoản CSGT &amp; Admin
</p>
</div>
""", unsafe_allow_html=True)

# ── Load data ──────────────────────────────────────────────────────
token = st.session_state.get("token", "")
users = admin_get_users(token)

# ── Metrics ────────────────────────────────────────────────────────
total   = len(users)
active  = sum(1 for u in users if u.get("is_active") and not u.get("is_locked"))
locked  = sum(1 for u in users if u.get("is_locked"))
admins  = sum(1 for u in users if u.get("role") == "admin")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value" style="color:#f1f5f9">{total}</div>
        <div class="metric-label">Tổng tài khoản</div>
    </div>""", unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value" style="color:#4ade80">{active}</div>
        <div class="metric-label">Đang hoạt động</div>
    </div>""", unsafe_allow_html=True)
with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value" style="color:#f87171">{locked}</div>
        <div class="metric-label">Đang bị khóa</div>
    </div>""", unsafe_allow_html=True)
with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value" style="color:#fbbf24">{admins}</div>
        <div class="metric-label">Quản trị viên</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ── Thêm tài khoản mới ────────────────────────────────────────────
with st.expander("➕ Tạo tài khoản mới", expanded=False):
    with st.form("form_create_user", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            new_email    = st.text_input("Email *", placeholder="csgt@danang.gov.vn")
            new_fullname = st.text_input("Họ tên *", placeholder="Nguyễn Văn A")
        with c2:
            new_password = st.text_input("Mật khẩu *", type="password",
                                         placeholder="Tối thiểu 8 ký tự")
            new_role     = st.selectbox("Vai trò *", ["csgt", "admin"])

        submitted = st.form_submit_button("Tạo tài khoản", type="primary",
                                          use_container_width=True)
        if submitted:
            if not all([new_email, new_password, new_fullname]):
                st.error("⚠️ Vui lòng điền đầy đủ thông tin.")
            elif len(new_password) < 8:
                st.error("⚠️ Mật khẩu tối thiểu 8 ký tự.")
            else:
                with st.spinner("Đang tạo tài khoản..."):
                    result = admin_create_user(
                        token, new_email, new_password, new_fullname, new_role
                    )
                if result.get("ok"):
                    st.success(f"✅ Tạo tài khoản **{new_email}** thành công!")
                    st.rerun()
                else:
                    st.error(f"❌ Lỗi: {result.get('error', 'Không rõ')}")
st.divider()

# ── Header row ─────────────────────────────────────────────────────
st.markdown("""
<div style="display:grid;grid-template-columns:3fr 1.2fr 1.4fr 2fr 1.3fr;
            gap:8px;padding:6px 4px 4px;margin-bottom:2px">
    <div style="font-size:0.72rem;color:#475569;font-weight:700;
                letter-spacing:0.07em;text-transform:uppercase;
                text-align:left;padding-left:14px">Tài khoản</div>
    <div style="font-size:0.72rem;color:#475569;font-weight:700;
                letter-spacing:0.07em;text-transform:uppercase;
                text-align:center">Vai trò</div>
    <div style="font-size:0.72rem;color:#475569;font-weight:700;
                letter-spacing:0.07em;text-transform:uppercase;
                text-align:center">Trạng thái</div>
    <div style="font-size:0.72rem;color:#475569;font-weight:700;
                letter-spacing:0.07em;text-transform:uppercase;
                text-align:left;padding-left:12px">Thời gian</div>
    <div style="font-size:0.72rem;color:#475569;font-weight:700;
                letter-spacing:0.07em;text-transform:uppercase;
                text-align:center">Hành động</div>
</div>
""", unsafe_allow_html=True)

if not users:
    st.info("Chưa có tài khoản nào.")
else:
    for u in users:
        uid        = u.get("id")
        email      = u.get("email", "")
        full_name  = u.get("full_name") or "—"
        role       = u.get("role", "")
        is_active  = u.get("is_active", True)
        is_locked  = u.get("is_locked", False)
        created    = (u.get("created_at") or "")[:10]
        last_login = (u.get("last_login") or "Chưa đăng nhập")[:16]

        # Badge role — chỉ text, không icon
        if role == "admin":
            role_badge = '<span class="badge" style="background:rgba(251,191,36,0.15);color:#fbbf24;border:1px solid rgba(251,191,36,0.3)">ADMIN</span>'
        else:
            role_badge = '<span class="badge" style="background:rgba(96,165,250,0.12);color:#60a5fa;border:1px solid rgba(96,165,250,0.25)">CSGT</span>'

        # Badge trạng thái — chỉ text, không icon
        if is_locked:
            status_badge = '<span class="badge" style="background:rgba(239,68,68,0.12);color:#f87171;border:1px solid rgba(239,68,68,0.25)">Bị khóa</span>'
        elif not is_active:
            status_badge = '<span class="badge" style="background:rgba(107,114,128,0.15);color:#6b7280;border:1px solid rgba(107,114,128,0.3)">Vô hiệu</span>'
        else:
            status_badge = '<span class="badge" style="background:rgba(74,222,128,0.12);color:#4ade80;border:1px solid rgba(74,222,128,0.25)">Hoạt động</span>'

        # Shared cell style — cùng kích thước height cho cả 4 ô
        CELL = ("background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);"
                "border-radius:10px;height:54px;box-sizing:border-box;")

        # ── 5 cột căn thẳng hàng ──────────────────────────────────
        col_name, col_role, col_status, col_date, col_act = st.columns(
            [3, 1.2, 1.4, 2, 1.3]
        )

        # Cột 1: Tên + Email — căn trái, padding chuẩn
        with col_name:
            st.markdown(f"""
            <div style="{CELL}padding:10px 14px;
                        display:flex;flex-direction:column;justify-content:center">
                <div style="font-size:0.87rem;font-weight:600;color:#e2e8f0">{full_name}</div>
                <div style="font-size:0.75rem;color:#64748b;margin-top:2px">{email}</div>
            </div>
            """, unsafe_allow_html=True)

        # Cột 2: Vai trò — căn giữa, chỉ badge
        with col_role:
            st.markdown(f"""
            <div style="{CELL}padding:10px;
                        display:flex;align-items:center;justify-content:center">
                {role_badge}
            </div>
            """, unsafe_allow_html=True)

        # Cột 3: Trạng thái — căn giữa, chỉ badge
        with col_status:
            st.markdown(f"""
            <div style="{CELL}padding:10px;
                        display:flex;align-items:center;justify-content:center">
                {status_badge}
            </div>
            """, unsafe_allow_html=True)

        # Cột 4: Thời gian — căn trái, 2 dòng
        with col_date:
            st.markdown(f"""
            <div style="{CELL}padding:10px 12px;
                        display:flex;flex-direction:column;justify-content:center">
                <div style="font-size:0.74rem;color:#64748b">
                    Tạo: <span style="color:#94a3b8">{created}</span>
                </div>
                <div style="font-size:0.74rem;color:#64748b;margin-top:3px">
                    Đăng nhập: <span style="color:#94a3b8">{last_login[:10]}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Cột 5: Hành động
        with col_act:
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            bc1, bc2 = st.columns(2)
            with bc1:
                if is_locked:
                    if st.button("🔓", key=f"unlock_{uid}", help="Mở khóa",
                                 use_container_width=True):
                        res = admin_unlock_user(token, uid)
                        if res.get("ok"):
                            st.success("Đã mở khóa!")
                            st.rerun()
                        else:
                            st.error(res.get("error"))
                else:
                    if st.button("🔒", key=f"lock_{uid}", help="Khóa tài khoản",
                                 use_container_width=True):
                        res = admin_lock_user(token, uid)
                        if res.get("ok"):
                            st.warning("Đã khóa tài khoản.")
                            st.rerun()
                        else:
                            st.error(res.get("error"))
            with bc2:
                if is_active:
                    if st.button("⛔", key=f"deact_{uid}", help="Vô hiệu hóa",
                                 use_container_width=True):
                        res = admin_deactivate_user(token, uid)
                        if res.get("ok"):
                            st.info("Đã vô hiệu hóa.")
                            st.rerun()
                        else:
                            st.error(res.get("error"))

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
