"""pages/4_login.py — Đăng nhập JWT (Sprint 3)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from shared.utils.css_loader import setup_ui
from config import APP_TITLE, APP_ICON

st.set_page_config(
    page_title=f"Đăng nhập | {APP_TITLE}",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)
setup_ui()

st.markdown("""
<div style="
    min-height: 70vh;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    animation: float-in 0.6s ease-out;
">
    <div style="
        background: rgba(255,255,255,0.04);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 28px;
        padding: 56px 72px;
        text-align: center;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        max-width: 520px;
    ">
        <div style="font-size:4rem; margin-bottom:20px">🔐</div>
        <h1 style="
            margin: 0 0 12px;
            font-size: 1.8rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            background: linear-gradient(135deg,#f1f5f9 30%,#94a3b8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        ">Đăng nhập hệ thống</h1>
        <p style="color:#64748b; font-size:0.9rem; margin:0 0 24px; line-height:1.6">
            Xác thực JWT cho Cảnh sát Giao thông<br>
            và Quản trị viên hệ thống.<br>
            Sẽ ra mắt trong <strong style="color:#f87171">Sprint 3</strong>.
        </p>
        <div style="
            display: inline-block;
            background: rgba(239,68,68,0.1);
            border: 1px solid rgba(239,68,68,0.22);
            border-radius: 10px;
            padding: 6px 18px;
            font-size: 0.8rem;
            color: #f87171;
            font-weight: 600;
            letter-spacing: 0.05em;
        ">🔒 ĐANG PHÁT TRIỂN</div>
    </div>
</div>
""", unsafe_allow_html=True)
