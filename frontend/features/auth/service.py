"""features/auth/service.py — Sprint 3: JWT management"""
import streamlit as st


def login(email: str, password: str) -> bool:
    """Gọi POST /api/auth/login → lưu token vào st.session_state."""
    # TODO Sprint 3
    pass


def logout() -> None:
    """Xóa token khỏi session."""
    # TODO Sprint 3
    pass


def is_authenticated() -> bool:
    """Kiểm tra user đã đăng nhập chưa."""
    return bool(st.session_state.get("access_token"))
