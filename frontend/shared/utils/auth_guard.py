"""
shared/utils/auth_guard.py — Route Protection Helpers

Dùng ở đầu mỗi trang cần bảo vệ:
    from shared.utils.auth_guard import require_login, require_admin

Cơ chế: Streamlit st.switch_page() redirect về login nếu chưa đủ quyền.
Không thể bypass bằng cách sửa URL vì guard chạy server-side.
"""

import streamlit as st


def require_login() -> None:
    """
    Yêu cầu đăng nhập. Nếu chưa login → redirect về trang login.
    Gọi ở đầu mọi trang cần xác thực (Dashboard, v.v.)
    """
    if not (st.session_state.get("logged_in") and st.session_state.get("token")):
        st.switch_page("pages/4_login.py")
        st.stop()


def require_admin() -> None:
    """
    Yêu cầu quyền Admin. Nếu chưa login → redirect login.
    Nếu đã login nhưng không phải admin → hiện thông báo lỗi + dừng.
    Gọi ở đầu các trang quản trị (admin users, scheduler, v.v.)
    """
    require_login()
    if st.session_state.get("user_role") != "admin":
        st.error("🚫 Bạn không có quyền truy cập trang này.")
        st.info("Vui lòng liên hệ quản trị viên để được cấp quyền.")
        st.stop()
