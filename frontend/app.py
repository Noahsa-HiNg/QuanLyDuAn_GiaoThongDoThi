"""
app.py — Entry Point
v1.1 — Removed dead _load_css() (CSS handled per-page via setup_ui())
"""

import streamlit as st
from config import APP_TITLE, APP_ICON

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Chuyển thẳng đến trang bản đồ
st.switch_page("pages/1_home.py")
