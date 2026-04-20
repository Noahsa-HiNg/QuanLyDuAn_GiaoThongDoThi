"""
shared/utils/css_loader.py — CSS + Component Injection Helper
v1.4 — Cấu trúc mới: assets/style/ và assets/javascript/
Gọi setup_ui() ở đầu MỖI page để đảm bảo theme + toggle luôn áp dụng.
"""

import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_ASSETS = Path(__file__).parent.parent.parent / "assets"
_STYLE  = _ASSETS / "style"
_JS     = _ASSETS / "javascript"


def inject_css() -> None:
    """Load assets/style/main.css → inject vào page hiện tại."""
    css_path = _STYLE / "main.css"
    if css_path.exists():
        with open(css_path, encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def inject_ambient_blobs() -> None:
    """Inject blob màu → glassmorphism backdrop-filter có hiệu quả."""
    st.markdown("""
    <div style="position:fixed;top:-120px;left:-120px;width:560px;height:560px;z-index:0;
        pointer-events:none;filter:blur(40px);
        background:radial-gradient(circle,rgba(102,126,234,.18) 0%,rgba(102,126,234,.05) 45%,transparent 70%);">
    </div>
    <div style="position:fixed;top:35%;right:-80px;width:420px;height:420px;z-index:0;
        pointer-events:none;filter:blur(50px);
        background:radial-gradient(circle,rgba(118,75,162,.14) 0%,rgba(118,75,162,.04) 45%,transparent 70%);">
    </div>
    <div style="position:fixed;bottom:-80px;left:35%;width:380px;height:380px;z-index:0;
        pointer-events:none;filter:blur(60px);
        background:radial-gradient(circle,rgba(34,197,94,.08) 0%,transparent 65%);">
    </div>
    """, unsafe_allow_html=True)


def inject_sidebar_toggle() -> None:
    """
    Đọc assets/javascript/sidebar_toggle.js → inject qua st.components.v1.html().
    JS inject button ☰ vào window.parent.document (same-origin: được phép).
    """
    js_path = _JS / "sidebar_toggle.js"
    if not js_path.exists():
        return
    with open(js_path, encoding="utf-8") as f:
        js_content = f.read()
    components.html(f"<script>{js_content}</script>", height=0, scrolling=False)


def setup_ui() -> None:
    """Shortcut: inject CSS + blobs + sidebar toggle. Gọi ngay sau set_page_config()."""
    inject_css()
    inject_ambient_blobs()
    inject_sidebar_toggle()
