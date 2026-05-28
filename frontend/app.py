"""
app.py — Entry Point với st.navigation() phân quyền theo role
v2.0 — Sprint 4

Navigation động dựa trên session_state:
  Guest : Home | Tìm đường | Đăng nhập
  CSGT  : Home | Tìm đường | Dashboard
  Admin : Home | Tìm đường | Dashboard + [⚙️ Quản trị: Tài khoản | Cào dữ liệu]
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
from config import APP_TITLE, APP_ICON

# set_page_config phải là lệnh Streamlit đầu tiên — đặt tại đây,
# KHÔNG đặt lại trong từng trang riêng lẻ nữa.
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Đọc trạng thái auth ───────────────────────────────────────────
logged_in = (
    st.session_state.get("logged_in", False)
    and bool(st.session_state.get("token"))
)
user_role = st.session_state.get("user_role", "")

# ── Định nghĩa tất cả pages ───────────────────────────────────────
pg_home       = st.Page("pages/1_home.py",            title="Bản đồ giao thông",   icon="🏠")
pg_route      = st.Page("pages/3_route_finder.py",    title="Tìm đường",           icon="🗺️")
pg_login      = st.Page("pages/4_login.py",           title="Đăng nhập",           icon="🔐")
pg_dashboard  = st.Page("pages/2_dashboard.py",       title="Dashboard",           icon="📊")
pg_csgt       = st.Page("pages/7_csgt_dashboard.py",  title="Dashboard CSGT",      icon="🚔")
pg_incidents  = st.Page("pages/8_incidents.py",       title="Quản lý Sự cố",       icon="🚨")
pg_users      = st.Page("pages/5_admin_users.py",     title="Quản lý tài khoản",   icon="👥")
pg_scheduler  = st.Page("pages/6_admin_scheduler.py", title="Quản lý cào dữ liệu", icon="🔄")

# ── Build danh sách pages theo role ───────────────────────────────
if not logged_in:
    # Guest: chỉ thấy 3 trang công khai
    nav = [pg_home, pg_route, pg_login]

elif user_role == "csgt":
    # CSGT: Home + Tìm đường + Dashboard + CSGT pages
    nav = {
        "Chung"         : [pg_home, pg_route, pg_dashboard],
        "🚔 Điều hành"  : [pg_csgt, pg_incidents],
    }

else:
    # Admin: tất cả — chia 3 section cho gọn
    nav = {
        "Chung"         : [pg_home, pg_route, pg_dashboard],
        "🚔 Điều hành"  : [pg_csgt, pg_incidents],
        "⚙️ Quản trị"   : [pg_users, pg_scheduler],
    }

# ── Khởi chạy navigation ──────────────────────────────────────────
pg = st.navigation(nav)
pg.run()
