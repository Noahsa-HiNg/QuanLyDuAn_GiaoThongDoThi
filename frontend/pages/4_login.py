"""
pages/4_login.py — Đăng nhập JWT
Sprint 3 | TASK #35 v2.0

v2.0:
  - Glassmorphism card với ambient glow + hover animations
  - Input focus glow + float label effect
  - Button shimmer + gradient hover
  - Floating icon animation
  - Sidebar đầy đủ branding (không trống)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from shared.utils.css_loader import setup_ui
from shared.components.sidebar import render_sidebar
from shared.api.client import post_login
from config import APP_TITLE, APP_ICON, APP_VERSION

setup_ui()
render_sidebar(show_map_controls=False)

# ── Helpers ───────────────────────────────────────────────────────
def _do_logout() -> None:
    for key in ("token", "user_name", "user_role", "user_email", "logged_in"):
        st.session_state.pop(key, None)

def _is_logged_in() -> bool:
    return bool(st.session_state.get("logged_in") and st.session_state.get("token"))

# ── Sidebar — nội dung liên quan đến đăng nhập ───────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;padding:10px 0 16px">
        <div style="font-size:1.7rem;line-height:1">🔐</div>
        <div>
            <div style="font-size:1rem;font-weight:700;color:#f1f5f9;line-height:1.3">
                Đăng nhập
            </div>
            <div style="font-size:0.74rem;color:#64748b;margin-top:2px">
                Xác thực JWT · Hệ thống nội bộ
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # User widget nếu đã đăng nhập
    if _is_logged_in():
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
                    <div style="font-size:0.82rem;font-weight:700;color:#e2e8f0">{user_name}</div>
                    <div style="font-size:0.7rem;color:{role_color};font-weight:600;
                                letter-spacing:0.04em;margin-top:2px">{user_role.upper()}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.button("🚪 Đăng xuất", use_container_width=True, type="secondary",
                  key="sidebar_logout_login_page", on_click=_do_logout)
        st.divider()

    st.markdown("**🛡️ Bảo mật hệ thống**")
    st.markdown("""
    <div style="font-size:0.82rem;color:#64748b;line-height:2.2">
        <div>✅ Mã hóa <b style="color:#94a3b8">Bcrypt</b></div>
        <div>✅ Token <b style="color:#94a3b8">JWT</b> có thời hạn</div>
        <div>✅ Khóa sau <b style="color:#94a3b8">5 lần</b> sai</div>
        <div>✅ Phân quyền <b style="color:#94a3b8">Admin / CSGT</b></div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown(f"""
    <div style="font-size:0.75rem;color:#334155;line-height:1.8">
        📌 Chỉ tài khoản được cấp bởi Admin mới có thể đăng nhập.<br>
        Liên hệ quản trị viên nếu quên mật khẩu.
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown(f"""
    <div style="font-size:0.72rem;color:#1e293b;line-height:1.8">
        📦 v{APP_VERSION}
    </div>
    """, unsafe_allow_html=True)


# ── CSS — Glassmorphism + Animations ─────────────────────────────
st.markdown("""
<style>
/* ── Keyframes ── */
@keyframes float {
    0%, 100% { transform: translateY(0px) rotate(-2deg); }
    50%       { transform: translateY(-12px) rotate(2deg); }
}
@keyframes slide-up {
    from { opacity:0; transform:translateY(32px) scale(0.97); }
    to   { opacity:1; transform:translateY(0) scale(1); }
}
@keyframes shimmer {
    0%   { background-position: -200% center; }
    100% { background-position: 200% center; }
}
@keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(99,102,241,0.15), 0 20px 60px rgba(0,0,0,0.4); }
    50%       { box-shadow: 0 0 40px rgba(99,102,241,0.3), 0 20px 60px rgba(0,0,0,0.4); }
}
@keyframes blob-float {
    0%, 100% { transform: translate(0,0) scale(1); }
    33%       { transform: translate(20px,-20px) scale(1.05); }
    66%       { transform: translate(-15px,15px) scale(0.97); }
}

/* ── Ambient blobs ── */
.login-blob-1 {
    position:fixed; top:-100px; left:-100px;
    width:500px; height:500px;
    background: radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%);
    border-radius:50%;
    animation: blob-float 12s ease-in-out infinite;
    pointer-events:none; z-index:0;
}
.login-blob-2 {
    position:fixed; bottom:-80px; right:-80px;
    width:400px; height:400px;
    background: radial-gradient(circle, rgba(168,85,247,0.10) 0%, transparent 70%);
    border-radius:50%;
    animation: blob-float 16s ease-in-out infinite reverse;
    pointer-events:none; z-index:0;
}

/* ── Glass card — target toàn bộ stForm container ── */
div[data-testid="stForm"] {
    animation: slide-up 0.6s cubic-bezier(0.16,1,0.3,1), glow-pulse 4s ease-in-out infinite 0.6s !important;
    background: rgba(255,255,255,0.04) !important;
    backdrop-filter: blur(28px) saturate(180%) !important;
    -webkit-backdrop-filter: blur(28px) saturate(180%) !important;
    border: 1px solid rgba(255,255,255,0.09) !important;
    border-radius: 28px !important;
    padding: 44px 52px 36px !important;
    box-shadow: 0 20px 60px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.08) !important;
    position: relative !important;
    overflow: hidden !important;
}
div[data-testid="stForm"]::before {
    content: '';
    position: absolute; top:0; left:-100%;
    width:60%; height:100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.03), transparent);
    transition: left 0.8s ease;
    pointer-events: none;
}
div[data-testid="stForm"]:hover::before { left: 200%; }

/* ── Icon float ── */
.lock-icon {
    font-size: 3.5rem;
    display: block;
    text-align: center;
    margin-bottom: 18px;
    animation: float 3s ease-in-out infinite;
    filter: drop-shadow(0 0 16px rgba(99,102,241,0.5));
}

/* ── Title gradient ── */
.login-title {
    margin: 0 0 6px;
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: -0.04em;
    text-align: center;
    background: linear-gradient(135deg, #f1f5f9 20%, #818cf8 60%, #c084fc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

/* ── Streamlit input override ── */
div[data-testid="stTextInput"] input {
    background: rgba(255,255,255,0.05) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    border-radius: 12px !important;
    color: #f1f5f9 !important;
    padding: 12px 16px !important;
    font-size: 0.95rem !important;
    transition: all 0.3s ease !important;
}
/* Nhường chỗ cho icon mắt ở password field — tránh bị đè */
div[data-testid="stTextInput"] input[type="password"],
div[data-testid="stTextInput"] input[type="text"]:not([aria-label*="mail"]) {
    padding-right: 52px !important;
}
/* Ẩn hint "Press Enter to submit" — bị đè lên icon mắt */
div[data-testid="stTextInput"] [data-testid="InputInstructions"] {
    display: none !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: rgba(99,102,241,0.6) !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15),
                0 0 20px rgba(99,102,241,0.1) !important;
    background: rgba(255,255,255,0.07) !important;
    outline: none !important;
}
div[data-testid="stTextInput"] input:hover {
    border-color: rgba(255,255,255,0.20) !important;
}

/* ── Login button ── */
div[data-testid="stForm"] button[kind="primaryFormSubmit"],
button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7) !important;
    background-size: 200% auto !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.02em !important;
    padding: 12px !important;
    transition: all 0.4s ease !important;
    box-shadow: 0 4px 20px rgba(99,102,241,0.35) !important;
}
div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
button[data-testid="baseButton-primary"]:hover {
    background-position: right center !important;
    box-shadow: 0 8px 30px rgba(99,102,241,0.5) !important;
    transform: translateY(-2px) !important;
    animation: shimmer 1.5s linear infinite !important;
}

/* ── Success user card ── */
.user-card {
    animation: slide-up 0.5s cubic-bezier(0.16,1,0.3,1);
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(24px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 28px;
    padding: 48px 56px 40px;
    text-align: center;
    box-shadow: 0 20px 60px rgba(0,0,0,0.35);
}
</style>

<div class="login-blob-1"></div>
<div class="login-blob-2"></div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# TRƯỜNG HỢP 1: ĐÃ ĐĂNG NHẬP
# ─────────────────────────────────────────────────────────────────
if _is_logged_in():
    user_name  = st.session_state.get("user_name",  "Người dùng")
    user_email = st.session_state.get("user_email", "")
    user_role  = st.session_state.get("user_role",  "")

    role_badge_bg    = "rgba(239,68,68,0.12)"  if user_role == "admin" else "rgba(59,130,246,0.12)"
    role_badge_color = "#f87171"               if user_role == "admin" else "#60a5fa"
    role_badge_text  = "👑 ADMIN"              if user_role == "admin" else "🚔 CSGT"

    _, col, _ = st.columns([1, 1.8, 1])
    with col:
        st.markdown(f"""
        <div class="user-card">
            <div style="font-size:3.8rem;margin-bottom:14px;
                        filter:drop-shadow(0 0 20px rgba(99,102,241,0.5))">✅</div>
            <h2 style="margin:0 0 6px;font-size:1.5rem;font-weight:800;
                       background:linear-gradient(135deg,#f1f5f9 30%,#818cf8 100%);
                       -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                       background-clip:text">Đã đăng nhập</h2>
            <p style="color:#94a3b8;margin:0 0 4px;font-size:0.95rem;font-weight:600">{user_name}</p>
            <p style="color:#64748b;margin:0 0 18px;font-size:0.82rem">{user_email}</p>
            <div style="display:inline-block;background:{role_badge_bg};color:{role_badge_color};
                        border:1px solid {role_badge_color}33;border-radius:8px;
                        padding:4px 16px;font-size:0.78rem;font-weight:700;
                        letter-spacing:0.06em;margin-bottom:28px">
                {role_badge_text}
            </div>
            <p style="color:#475569;font-size:0.8rem;line-height:1.7;margin:0 0 20px">
                Bạn có thể truy cập <b style="color:#94a3b8">Dashboard</b> và các
                tính năng dành cho <b style="color:{role_badge_color}">{user_role.upper()}</b>.
            </p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        if st.button("🚪 Đăng xuất", use_container_width=True, type="secondary", key="btn_logout_main"):
            _do_logout()
            st.rerun()

    st.stop()


# ─────────────────────────────────────────────────────────────────
# TRƯỜNG HỢP 2: CHƯA ĐĂNG NHẬP
# ─────────────────────────────────────────────────────────────────
_, col, _ = st.columns([1, 1.8, 1])

with col:
    # ── Form — icon + title BÊN TRONG form để glass card bọc tất cả ──
    with st.form("login_form", clear_on_submit=False):
        # Header bên trong form
        st.markdown("""
        <span class="lock-icon">🔐</span>
        <h1 class="login-title">Đăng nhập hệ thống</h1>
        <p style="color:#64748b;font-size:0.85rem;text-align:center;
                  margin:0 0 28px;line-height:1.6">
            Dành cho Cảnh sát Giao thông &amp; Quản trị viên
        </p>
        """, unsafe_allow_html=True)

        email = st.text_input(
            "Email",
            placeholder="your@email.com",
            key="input_email",
        )
        password = st.text_input(
            "Mật khẩu",
            type="password",
            placeholder="••••••••",
            key="input_password",
        )
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button(
            "Đăng nhập",
            use_container_width=True,
            type="primary",
        )

        # Divider footer bên trong form
        st.markdown("""
        <div style="display:flex;align-items:center;gap:12px;margin:20px 0 0">
            <div style="flex:1;height:1px;background:rgba(255,255,255,0.06)"></div>
            <span style="color:#334155;font-size:0.72rem;white-space:nowrap">HỆ THỐNG QUẢN LÝ NỘI BỘ</span>
            <div style="flex:1;height:1px;background:rgba(255,255,255,0.06)"></div>
        </div>
        <p style="text-align:center;color:#334155;font-size:0.72rem;margin:8px 0 0">
            Liên hệ Admin để được cấp tài khoản
        </p>
        """, unsafe_allow_html=True)

    # ── Xử lý submit ─────────────────────────────────────────────
    if submitted:
        if not email.strip() or not password.strip():
            st.error("⚠️ Vui lòng nhập đầy đủ email và mật khẩu.")
        else:
            with st.spinner("Đang xác thực..."):
                result = post_login(email.strip(), password.strip())

            if result.get("access_token"):
                user_info = result.get("user", {})
                st.session_state["token"]      = result["access_token"]
                st.session_state["user_name"]  = user_info.get("full_name", email)
                st.session_state["user_email"] = user_info.get("email", email)
                st.session_state["user_role"]  = user_info.get("role", "")
                st.session_state["logged_in"]  = True
                st.success(f"✅ Xin chào, **{st.session_state['user_name']}**!")
                st.switch_page("pages/1_home.py")   # ← chuyển về Home ngay sau login
            else:
                st.markdown("""
                <div style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.25);
                            border-radius:12px;padding:12px 16px;margin-top:8px;
                            color:#fca5a5;font-size:0.875rem;line-height:1.5">
                    ❌ <b>Đăng nhập thất bại.</b><br>
                    <span style="color:#94a3b8;font-size:0.82rem">
                    Email/mật khẩu không đúng hoặc tài khoản đang bị khóa.
                    Liên hệ Admin để được hỗ trợ.
                    </span>
                </div>
                """, unsafe_allow_html=True)


