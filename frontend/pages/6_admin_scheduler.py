"""
pages/6_admin_scheduler.py — Quản lý Cào dữ liệu Tự động (Admin only)
Sprint 4

Chức năng:
  - Xem trạng thái APScheduler (running / paused / stopped)
  - Danh sách các jobs đang được lên lịch
  - Kích hoạt cào thủ công ngay lập tức
  - Tạm dừng / Tiếp tục scheduler
  - Xem trạng thái lần cào gần nhất
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from config import APP_TITLE, APP_VERSION
from shared.utils.css_loader import setup_ui
from shared.utils.auth_guard import require_admin
from shared.components.sidebar import render_sidebar
from shared.api.client import (
    admin_get_schedule_state, admin_get_schedule_jobs,
    admin_pause_schedule, admin_resume_schedule,
    admin_crawl_now, admin_get_crawl_status,
)

# ── Page config ────────────────────────────────────────────────────
setup_ui()
require_admin()

# ── Sidebar ─────────────────────────────────────────────────────
render_sidebar(
    show_map_controls=False,
    brand_icon="🔄",
    brand_title="Quản lý cào dữ liệu",
    brand_subtitle="APScheduler — tự động hóa",
)
with st.sidebar:
    st.divider()
    st.markdown("""
    <div style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.18);
                border-radius:14px;padding:14px 16px;margin-bottom:4px">
        <div style="font-size:0.82rem;font-weight:700;color:#4ade80;margin-bottom:8px">
            ⏱️ Scheduler
        </div>
        <div style="font-size:0.77rem;color:#94a3b8;line-height:1.7">
            ⏰ Cào định kỳ theo lịch APScheduler<br>
            ⚡ Kích hoạt thủ công ngay lập tức<br>
            ⏸️ Tạm dừng / Tiếp tục hệ thống
        </div>
    </div>
    <div style="font-size:0.73rem;color:#475569;padding:6px 2px;line-height:1.7">
        📊 Dữ liệu giao thông được cào<br>
        từ TomTom & Goong API
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

.status-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 20px 24px;
    backdrop-filter: blur(12px);
}
.job-row {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    padding: 12px 16px;
    margin-bottom: 8px;
    font-size: 0.84rem;
}
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
}
@keyframes pulse-dot {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}
.pulse { animation: pulse-dot 1.5s ease-in-out infinite; }
</style>
""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────────
st.markdown("""
<div class="admin-page">
<h1 style="margin:0 0 4px;font-size:1.6rem;font-weight:800;
           display:flex;align-items:center;gap:10px">
    <span>&#x1F504;</span>
    <span style="background:linear-gradient(135deg,#f1f5f9 30%,#34d399 100%);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                 background-clip:text">Quản lý Cào dữ liệu</span>
</h1>
<p style="color:#64748b;font-size:0.88rem;margin:0 0 24px">
    Giám sát và điều khiển scheduler thu thập dữ liệu giao thông tự động
</p>
</div>
""", unsafe_allow_html=True)

token = st.session_state.get("token", "")

# ── Fetch data ─────────────────────────────────────────────────────
sched_state  = admin_get_schedule_state(token)
sched_jobs   = admin_get_schedule_jobs(token)
crawl_status = admin_get_crawl_status(token)

# ── Scheduler state banner ─────────────────────────────────────────
state_val = sched_state.get("state", "unknown")
if state_val == "running":
    state_color = "#4ade80"
    state_icon  = "🟢"
    state_text  = "ĐANG CHẠY"
elif state_val == "paused":
    state_color = "#fbbf24"
    state_icon  = "⏸️"
    state_text  = "TẠM DỪNG"
else:
    state_color = "#f87171"
    state_icon  = "🔴"
    state_text  = "DỪNG / KHÔNG RÕ"

col_state, col_ctrl = st.columns([3, 1])
with col_state:
    st.markdown(f"""
    <div class="status-card">
        <div style="display:flex;align-items:center;gap:16px">
            <div style="font-size:2.5rem">{state_icon}</div>
            <div>
                <div style="font-size:1.2rem;font-weight:800;color:{state_color};
                            letter-spacing:0.04em">{state_text}</div>
                <div style="font-size:0.78rem;color:#64748b;margin-top:4px">
                    APScheduler · {len(sched_jobs)} jobs đang lên lịch
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_ctrl:
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if state_val == "running":
        if st.button("⏸️ Tạm dừng", use_container_width=True, type="secondary"):
            with st.spinner("Đang tạm dừng..."):
                res = admin_pause_schedule(token)
            if res.get("ok"):
                st.success("Đã tạm dừng scheduler.")
                st.rerun()
            else:
                st.error(f"Lỗi: {res.get('error')}")
    elif state_val == "paused":
        if st.button("▶️ Tiếp tục", use_container_width=True, type="primary"):
            with st.spinner("Đang khởi động lại..."):
                res = admin_resume_schedule(token)
            if res.get("ok"):
                st.success("Scheduler đang chạy trở lại.")
                st.rerun()
            else:
                st.error(f"Lỗi: {res.get('error')}")

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

# ── Crawl thủ công ────────────────────────────────────────────────
col_crawl, col_status = st.columns([1, 2])

with col_crawl:
    st.markdown("**⚡ Cào dữ liệu ngay**")
    st.markdown(
        '<p style="font-size:0.8rem;color:#64748b;margin-bottom:12px">'
        'Kích hoạt 1 chu kỳ cào dữ liệu cho toàn bộ đường trong DB</p>',
        unsafe_allow_html=True
    )
    if st.button("🚀 Cào ngay", use_container_width=True, type="primary",
                 key="btn_crawl_now"):
        with st.spinner("Đang cào dữ liệu... (có thể mất 30–60 giây)"):
            res = admin_crawl_now(token)
        if res.get("ok"):
            data = res.get("data", {})
            success = data.get("streets_success", "?")
            total   = data.get("streets_total", "?")
            st.success(f"✅ Cào hoàn tất: **{success}/{total}** đường thành công!")
            st.rerun()
        else:
            st.error(f"❌ Lỗi: {res.get('error', 'Không rõ')}")

with col_status:
    st.markdown("**📊 Trạng thái lần cào gần nhất**")
    if crawl_status:
        s_total   = crawl_status.get("streets_total", "—")
        s_success = crawl_status.get("streets_success", "—")
        s_fail    = crawl_status.get("streets_failed", "—")
        s_time    = (crawl_status.get("crawled_at") or "—")[:16]
        s_dur     = crawl_status.get("duration_sec")
        dur_txt   = f"{s_dur:.1f}s" if s_dur else "—"

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("✅ Thành công", s_success)
        with c2:
            st.metric("❌ Thất bại", s_fail)
        with c3:
            st.metric("⏱️ Thời gian", dur_txt)
        st.markdown(
            f'<div style="font-size:0.78rem;color:#475569;margin-top:8px">'
            f'🕐 Thời điểm: {s_time}</div>',
            unsafe_allow_html=True
        )
    else:
        st.info("Chưa có thông tin cào gần nhất.")

st.divider()

# ── Danh sách jobs ─────────────────────────────────────────────────
st.markdown("**📋 Danh sách Jobs đang lên lịch**")

if not sched_jobs:
    st.info("Không có job nào đang chạy.")
else:
    for job in sched_jobs:
        # API có thể trả về string (job ID) hoặc dict (job object)
        if isinstance(job, dict):
            job_id   = job.get("id", "")
            job_name = job.get("name", job_id)
            next_run = (job.get("next_run_time") or "Chưa xác định")[:19].replace("T", " ")
            trigger  = job.get("trigger", "—")
        else:
            # Fallback: job là string (job ID)
            job_id   = str(job)
            job_name = str(job)
            next_run = "—"
            trigger  = "—"

        st.markdown(f"""
        <div class="job-row">
            <div style="display:flex;align-items:center;justify-content:space-between">
                <div>
                    <div style="font-weight:600;color:#e2e8f0;margin-bottom:4px">{job_name}</div>
                    <div style="font-size:0.75rem;color:#475569">
                        ID: {job_id} &nbsp;·&nbsp; Trigger: {trigger}
                    </div>
                </div>
                <div style="text-align:right">
                    <div style="font-size:0.78rem;color:#64748b">Lần chạy tiếp theo</div>
                    <div style="font-size:0.85rem;font-weight:600;color:#93c5fd">{next_run}</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown(f"""
<div style="font-size:0.74rem;color:#334155;margin-top:16px;text-align:center">
    🔄 Trang tự động tải lại mỗi 60 giây &nbsp;·&nbsp; v{APP_VERSION}
</div>
""", unsafe_allow_html=True)
