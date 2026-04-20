/**
 * assets/sidebar_toggle.js — Custom Sidebar Toggle Button
 * v1.0
 *
 * Chạy trong iframe (Streamlit component) nhưng inject button vào
 * window.parent.document — cùng origin localhost:8501 nên được phép.
 *
 * Flow:
 *   1. Tạo button ☰ glassmorphism trong parent document (position:fixed)
 *   2. Click → tìm native Streamlit toggle → click programmatically
 *   3. MutationObserver → sync icon ☰ / ✕ theo trạng thái sidebar
 */
(function () {
    'use strict';

    var BUTTON_ID  = 'ca-sidebar-toggle';
    var OPEN_ICON  = '&#9776;';   /* ☰ */
    var CLOSE_ICON = '&#10005;';  /* ✕ */
    var doc;

    /* ── Xác định sidebar đang mở hay đóng ─────────────────────── */
    function isSidebarOpen() {
        var sb = doc.querySelector('[data-testid="stSidebar"]');
        return sb ? sb.offsetWidth > 80 : false;
    }

    /* ── Click native Streamlit sidebar toggle ──────────────────── */
    function clickNativeSidebar() {
        /* Khi sidebar đóng: [collapsedControl] có trong DOM nhưng bị CSS ẩn.
           React yêu cầu element visible để nhận click event.
           Fix: unhide tạm → click → ẩn lại trong 50ms */
        var cc = doc.querySelector('[data-testid="collapsedControl"]');
        if (cc) {
            var prev = cc.style.display;
            cc.style.setProperty('display', 'flex', 'important');
            var btn = cc.querySelector('button') || cc;
            btn.click();
            setTimeout(function () { cc.style.setProperty('display', 'none', 'important'); }, 50);
            return;
        }

        /* Khi sidebar mở: tìm nút collapse bên trong stSidebar */
        var selectors = [
            '[data-testid="stSidebar"] button[data-testid="baseButton-headerNoPadding"]',
            '[data-testid="stSidebar"] button[aria-expanded]',
            '[data-testid="stSidebar"] button:first-of-type',
        ];
        for (var i = 0; i < selectors.length; i++) {
            var el = doc.querySelector(selectors[i]);
            if (el) { el.click(); return; }
        }

        /* Fallback: any button with sidebar aria-label */
        var btns = doc.querySelectorAll('button');
        for (var j = 0; j < btns.length; j++) {
            var label = (btns[j].getAttribute('aria-label') || '').toLowerCase();
            if (label.indexOf('sidebar') !== -1 || label.indexOf('navigation') !== -1) {
                btns[j].click(); return;
            }
        }
    }

    /* ── Sync icon theo trạng thái sidebar ─────────────────────── */
    function syncIcon() {
        var btn = doc.getElementById(BUTTON_ID);
        if (!btn) return;
        btn.innerHTML = isSidebarOpen() ? CLOSE_ICON : OPEN_ICON;
    }

    /* ── Tạo nút ☰ glassmorphism trong parent document ─────────── */
    function createButton() {
        if (doc.getElementById(BUTTON_ID)) return;

        var btn = doc.createElement('button');
        btn.id    = BUTTON_ID;
        btn.title = 'Đóng / Mở Navigation';
        btn.innerHTML = OPEN_ICON;

        btn.style.cssText = [
            'position: fixed',
            'top: 12px',
            'left: 12px',
            'z-index: 9999999',
            'width: 40px',
            'height: 40px',
            'display: flex',
            'align-items: center',
            'justify-content: center',
            'background: rgba(102,126,234,0.12)',
            'border: 1px solid rgba(102,126,234,0.3)',
            'border-radius: 12px',
            'color: #e2e8f0',
            'font-size: 17px',
            'cursor: pointer',
            'backdrop-filter: blur(16px)',
            '-webkit-backdrop-filter: blur(16px)',
            'transition: all 0.25s cubic-bezier(0.25,0.46,0.45,0.94)',
            'box-shadow: 0 4px 20px rgba(0,0,0,0.3)',
            'outline: none',
            'font-family: system-ui, -apple-system, sans-serif',
        ].join('; ');

        /* Hover effects */
        btn.addEventListener('mouseenter', function () {
            btn.style.background  = 'rgba(102,126,234,0.32)';
            btn.style.boxShadow   = '0 6px 28px rgba(102,126,234,0.45)';
            btn.style.transform   = 'scale(1.08)';
            btn.style.borderColor = 'rgba(102,126,234,0.6)';
        });
        btn.addEventListener('mouseleave', function () {
            btn.style.background  = 'rgba(102,126,234,0.12)';
            btn.style.boxShadow   = '0 4px 20px rgba(0,0,0,0.3)';
            btn.style.transform   = 'scale(1)';
            btn.style.borderColor = 'rgba(102,126,234,0.3)';
        });

        /* Click: toggle sidebar + sync icon sau 350ms */
        btn.addEventListener('click', function () {
            clickNativeSidebar();
            setTimeout(syncIcon, 350);
        });

        doc.body.appendChild(btn);
    }

    /* ── Theo dõi sidebar mở/đóng qua MutationObserver ─────────── */
    function watchSidebar() {
        var appContainer = doc.querySelector('[data-testid="stApp"]') || doc.body;
        var observer = new MutationObserver(function () {
            syncIcon();
        });
        observer.observe(appContainer, { childList: true, subtree: true, attributes: true });
    }

    /* ── Entry point ─────────────────────────────────────────────── */
    function init() {
        try {
            doc = window.parent.document;
        } catch (e) {
            /* Fallback nếu không access được parent (unlikely same-origin) */
            doc = document;
        }
        createButton();
        syncIcon();
        watchSidebar();
    }

    /* Chờ Streamlit React components mount xong (~800ms) */
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            setTimeout(init, 800);
        });
    } else {
        setTimeout(init, 800);
    }
})();
