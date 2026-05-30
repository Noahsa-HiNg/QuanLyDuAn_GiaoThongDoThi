"""
pages/8_incidents.py — Quản lý Sự cố & Lô Cốt
Sprint 4 | SCRUM-53 v1.2

Cải tiến v1.2:
  - st.dialog cho form Thêm mới (nằm ở đầu, không trôi xuống cuối)
  - Batch selection: chọn nhiều sự cố, xử lý 1 lần
  - CSS fix: button alignment + badge min-width đồng đều
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from datetime import datetime, timezone, timedelta

from shared.utils.css_loader import setup_ui
from shared.utils.auth_guard import require_login
from shared.components.sidebar import render_sidebar
from shared.api.client import (
    get_incidents, create_incident,
    update_incident_status, delete_incident,
)
from config import APP_VERSION

setup_ui()
require_login()
render_sidebar(show_map_controls=False, brand_icon="🚧", brand_title="Quản lý Sự cố",
               brand_subtitle="Lô Cốt & Tai nạn")

TZ7 = timezone(timedelta(hours=7))

# ── Hằng số ──────────────────────────────────────────────────────────────────
_TYPE_OPTS = {
    "":          "Tất cả loại",
    "roadblock": "🚧 Lô cốt",
    "accident":  "💥 Tai nạn",
    "event":     "📢 Sự kiện",
    "community": "👥 Cộng đồng",
}
_STATUS_OPTS = {
    "":           "Tất cả trạng thái",
    "active":     "🔴 Đang xảy ra",
    "dispatched": "🟡 Đã điều động",
    "resolved":   "🟢 Đã xử lý",
}
_STATUS_BG = {
    "active":     ("rgba(239,68,68,0.12)",  "#f87171",  "rgba(239,68,68,0.3)"),
    "dispatched": ("rgba(234,179,8,0.12)",   "#fbbf24",  "rgba(234,179,8,0.3)"),
    "resolved":   ("rgba(34,197,94,0.12)",   "#4ade80",  "rgba(34,197,94,0.3)"),
}
_SEV_LABEL = {1: "🟢 Thấp", 2: "🟡 Trung bình", 3: "🔴 Cao"}
_SEV_COLOR = {1: "#4ade80", 2: "#fbbf24", 3: "#f87171"}


def _status_badge(status: str) -> str:
    bg, clr, bdr = _STATUS_BG.get(status, _STATUS_BG["active"])
    labels = {"active": "Đang xảy ra", "dispatched": "Đã điều động", "resolved": "Đã xử lý"}
    return (
        f'<span style="background:{bg};color:{clr};border:1px solid {bdr};'
        f'border-radius:20px;padding:2px 10px;font-size:0.76rem;font-weight:600;'
        f'white-space:nowrap">{labels.get(status, status)}</span>'
    )


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ7)
        return dt.strftime("%H:%M %d/%m")
    except Exception:
        return iso[:16] if iso else "—"


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }
.inc-fade { animation: fadeIn 0.35s ease-out; }
.inc-card {
  background: rgba(255,255,255,0.025);
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 14px;
  padding: 14px 16px;
  margin-bottom: 8px;
  transition: border-color 0.2s, background 0.2s;
}
.inc-card:hover {
  background: rgba(255,255,255,0.04);
  border-color: rgba(255,255,255,0.12);
}
.block-container { padding-right:1rem !important; padding-left:1.5rem !important; }

/* Fix 1: badge min-width đồng đều */
.stat-badge {
  border-radius: 10px;
  padding: 8px 16px;
  font-size: 0.82rem;
  min-width: 140px;
  text-align: center;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

/* Fix 2: vertically center action buttons with incident cards */
[data-testid="stVerticalBlock"]:has(>[data-testid="element-container"]>[data-testid="stButton"]) {
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    min-height: 80px;
}
[data-testid="stVerticalBlock"]:has(>[data-testid="element-container"]>[data-testid="stButton"])
  [data-testid="element-container"] {
    margin-top: 0 !important;
    margin-bottom: 4px !important;
}

/* Fix 3: batch action bar */
.batch-bar {
  background: rgba(99,102,241,0.12);
  border: 1px solid rgba(99,102,241,0.3);
  border-radius: 12px;
  padding: 10px 16px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
""", unsafe_allow_html=True)

token     = st.session_state.get("token", "")
user_role = st.session_state.get("user_role", "")

# ── Dialog: Thêm sự cố mới ───────────────────────────────────────────────────
@st.dialog("➕ Thêm Sự cố / Lô cốt mới", width="large")
def _show_create_dialog():
    st.markdown("""
    <div style="background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.15);
                border-radius:10px;padding:10px 14px;margin-bottom:16px;font-size:0.83rem;
                color:#a5b4fc">
      ℹ️ Điền thông tin sự cố. Điền ID tuyến đường từ hệ thống.
    </div>""", unsafe_allow_html=True)

    with st.form("create_incident_form", clear_on_submit=True):
        f1, f2 = st.columns(2)
        with f1:
            f_street_id = st.number_input("Street ID *", min_value=1, value=1)
            f_type = st.selectbox("Loại sự cố *",
                                  ["roadblock", "accident", "event", "community"],
                                  format_func=lambda k: _TYPE_OPTS.get(k, k))
            f_sev = st.select_slider("Mức độ nghiêm trọng",
                                     options=[1, 2, 3],
                                     format_func=lambda x: _SEV_LABEL[x])
        with f2:
            f_start = st.date_input("Ngày bắt đầu *", value=datetime.now(TZ7).date())
            f_start_time = st.time_input("Giờ bắt đầu *", value=datetime.now(TZ7).time())
            f_status = st.selectbox("Trạng thái ban đầu",
                                    ["active", "dispatched"],
                                    format_func=lambda k: _STATUS_OPTS.get(k, k))

        f_desc = st.text_area("Mô tả chi tiết", placeholder="Mô tả tình trạng cụ thể...")
        submitted = st.form_submit_button("🚨 Tạo sự cố", type="primary",
                                          use_container_width=True)

    if submitted:
        start_dt = datetime.combine(f_start, f_start_time, tzinfo=TZ7).isoformat()
        payload = {
            "street_id":   int(f_street_id),
            "type":        f_type,
            "start_time":  start_dt,
            "severity":    int(f_sev),
            "description": f_desc.strip() if f_desc else None,
            "status":      f_status,
            "is_active":   True,
        }
        with st.spinner("Đang tạo sự cố..."):
            res = create_incident(token, payload)
        if res.get("ok"):
            inc_data = res.get("data", {})
            st.success(f"✅ Tạo thành công! Sự cố #{inc_data.get('id', '?')} đã được ghi nhận.")
            st.rerun()
        else:
            st.error(f"❌ Lỗi: {res.get('error', 'Không rõ lỗi')}")



# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="inc-fade" style="padding:16px 0 6px">
  <h1 style="margin:0;font-size:1.9rem;font-weight:800;letter-spacing:-0.03em">
    <span style="color:#f8fafc">🚧</span>
    <span style="background:linear-gradient(135deg,#f1f5f9 30%,#f87171 100%);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                 background-clip:text">Quản lý Sự cố & Lô Cốt</span>
  </h1>
  <p style="color:#64748b;font-size:0.85rem;margin:4px 0 0">
    Theo dõi, điều phối và xử lý sự cố giao thông
  </p>
</div>
<hr style="border-color:rgba(255,255,255,0.07);margin:8px 0 18px">
""", unsafe_allow_html=True)

# ── Filter Row (với nút Thêm mới ở đầu) ──────────────────────────────────────
fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 2, 1, 1.2])

with fc1:
    type_filter = st.selectbox(
        "Loại sự cố", list(_TYPE_OPTS.keys()),
        format_func=lambda k: _TYPE_OPTS[k],
        key="inc_type_filter", label_visibility="collapsed",
    )
with fc2:
    status_filter = st.selectbox(
        "Trạng thái", list(_STATUS_OPTS.keys()),
        format_func=lambda k: _STATUS_OPTS[k],
        key="inc_status_filter", label_visibility="collapsed",
    )
with fc3:
    active_filter = st.selectbox(
        "Hiệu lực", ["all", "active_only", "inactive_only"],
        format_func=lambda x: {
            "all": "Tất cả", "active_only": "✅ Còn hiệu lực", "inactive_only": "❌ Hết hiệu lực"
        }[x],
        key="inc_active_filter", label_visibility="collapsed",
    )
with fc4:
    if st.button("🔄 Làm mới", use_container_width=True, key="inc_refresh"):
        st.rerun()
with fc5:
    if st.button("➕ Thêm mới", use_container_width=True, key="btn_add_inc", type="primary"):
        _show_create_dialog()

# ── Fetch incidents ───────────────────────────────────────────────────────────
is_active_param = None
if active_filter == "active_only":
    is_active_param = True
elif active_filter == "inactive_only":
    is_active_param = False

with st.spinner("Đang tải sự cố..."):
    incidents = get_incidents(
        token,
        is_active=is_active_param,
        incident_type=type_filter if type_filter else None,
        status=status_filter if status_filter else None,
        page_size=50,
    )

# ── Stats Row (badge đồng kích cỡ) ───────────────────────────────────────────
n_active     = sum(1 for i in incidents if i.get("status") == "active")
n_dispatched = sum(1 for i in incidents if i.get("status") == "dispatched")
n_resolved   = sum(1 for i in incidents if i.get("status") == "resolved")

st.markdown(f"""
<div class="inc-fade" style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap">
  <div class="stat-badge" style="background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2)">
    🔴 <b style="color:#f87171">{n_active}</b> <span style="color:#94a3b8">Đang xảy ra</span>
  </div>
  <div class="stat-badge" style="background:rgba(234,179,8,0.08);border:1px solid rgba(234,179,8,0.2)">
    🟡 <b style="color:#fbbf24">{n_dispatched}</b> <span style="color:#94a3b8">Đã điều động</span>
  </div>
  <div class="stat-badge" style="background:rgba(34,197,94,0.08);border:1px solid rgba(34,197,94,0.2)">
    🟢 <b style="color:#4ade80">{n_resolved}</b> <span style="color:#94a3b8">Đã xử lý</span>
  </div>
  <div class="stat-badge" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08)">
    📋 <b style="color:#e2e8f0">{len(incidents)}</b> <span style="color:#94a3b8">Tổng (trang này)</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Batch selection action bar ────────────────────────────────────────────────
if incidents:
    # Thu thập IDs đang được chọn (từ session_state của các checkbox)
    selected_ids = [
        inc["id"] for inc in incidents
        if inc.get("status") != "resolved"
        and st.session_state.get(f"sel_{inc.get('id', 0)}", False)
    ]

    if selected_ids:
        bc1, bc2, bc3 = st.columns([3, 1.5, 1.5])
        with bc1:
            st.markdown(
                f'<div style="padding:10px 4px;color:#a5b4fc;font-weight:600">'
                f'☑️ Đã chọn <b>{len(selected_ids)}</b> sự cố</div>',
                unsafe_allow_html=True
            )
        with bc2:
            if st.button(f"✅ Xử lý tất cả ({len(selected_ids)})",
                         type="primary", use_container_width=True, key="batch_resolve"):
                for sid in selected_ids:
                    update_incident_status(token, sid, "resolved")
                for sid in selected_ids:
                    st.session_state.pop(f"sel_{sid}", None)
                st.success(f"✅ Đã xử lý {len(selected_ids)} sự cố!")
                st.rerun()
        with bc3:
            if st.button("✖ Bỏ chọn tất cả", use_container_width=True, key="batch_clear"):
                for inc in incidents:
                    st.session_state.pop(f"sel_{inc.get('id', 0)}", None)
                st.rerun()

# ── Danh sách sự cố ──────────────────────────────────────────────────────────
if not incidents:
    st.info("📭 Không có sự cố nào phù hợp với bộ lọc.")
else:
    st.markdown(f"<p style='font-size:0.75rem;color:#475569;margin-bottom:8px'>"
                f"Hiển thị {len(incidents)} sự cố</p>", unsafe_allow_html=True)

    for inc in incidents:
        inc_id   = inc.get("id", 0)
        status   = inc.get("status", "active")
        inc_type = inc.get("type", "event")
        sev      = inc.get("severity", 1)
        desc     = inc.get("description", "")
        start    = _fmt_dt(inc.get("start_time"))
        end      = _fmt_dt(inc.get("end_time"))
        is_act   = inc.get("is_active", True)

        _, clr, bdr = _STATUS_BG.get(status, _STATUS_BG["active"])
        sev_clr = _SEV_COLOR.get(sev, "#94a3b8")

        # Layout: checkbox | card info | actions
        col_cb, col_info, col_actions = st.columns([0.25, 3, 1])

        with col_cb:
            # Checkbox chỉ cho sự cố chưa xử lý
            if status != "resolved":
                st.checkbox("", key=f"sel_{inc_id}",
                            label_visibility="collapsed")

        with col_info:
            street_display = f"Street ID {inc.get('street_id', '?')}"
            st.markdown(f"""
            <div class="inc-card inc-fade">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
                <span style="font-size:1.1rem">{_TYPE_OPTS.get(inc_type, '📌')}</span>
                <div>
                  <span style="font-weight:600;color:#e2e8f0;font-size:0.9rem">{street_display}</span><br>
                  <span style="font-size:0.72rem;color:#64748b">#{inc_id} · {start}</span>
                </div>
                <div style="margin-left:auto">{_status_badge(status)}</div>
              </div>
              <div style="font-size:0.82rem;color:#cbd5e1;line-height:1.5">
                {f'&ldquo;{desc}&rdquo;' if desc else '<span style="color:#475569">Không có mô tả</span>'}
              </div>
              <div style="margin-top:6px;display:flex;gap:10px;font-size:0.73rem;color:#64748b">
                <span>⏱ Bắt đầu: <b style="color:#94a3b8">{start}</b></span>
                <span>⏹ Kết thúc: <b style="color:#94a3b8">{end}</b></span>
                <span style="color:{sev_clr};font-weight:600">{_SEV_LABEL.get(sev,'?')}</span>
                {'<span style="color:#4ade80">✅ Còn hiệu lực</span>' if is_act else '<span style="color:#475569">⬜ Hết hiệu lực</span>'}
              </div>
            </div>""", unsafe_allow_html=True)


        with col_actions:
            # Nút Điều động (chỉ khi active)
            if status == "active":
                if st.button("🚔 Điều động", key=f"dispatch_{inc_id}",
                             use_container_width=True, type="primary"):
                    res = update_incident_status(token, inc_id, "dispatched")
                    if res.get("ok"):
                        st.success(f"✅ Đã điều động #{inc_id}")
                        st.rerun()
                    else:
                        st.error(f"❌ {res.get('error')}")

            # Nút Đã xử lý
            if status in ("active", "dispatched"):
                if st.button("✅ Đã xử lý", key=f"resolve_{inc_id}",
                             use_container_width=True):
                    res = update_incident_status(token, inc_id, "resolved")
                    if res.get("ok"):
                        st.success(f"✅ Giải quyết #{inc_id}")
                        st.rerun()
                    else:
                        st.error(f"❌ {res.get('error')}")

            # Nút Xóa (Admin only)
            if user_role == "admin":
                if st.button("🗑️ Xóa", key=f"del_{inc_id}",
                             use_container_width=True):
                    st.session_state[f"confirm_del_{inc_id}"] = True

                if st.session_state.get(f"confirm_del_{inc_id}"):
                    st.markdown(
                        f'<p style="font-size:0.73rem;color:#f87171">Xác nhận xóa #{inc_id}?</p>',
                        unsafe_allow_html=True)
                    cc1, cc2 = st.columns(2)
                    with cc1:
                        if st.button("Có", key=f"del_yes_{inc_id}", type="primary"):
                            res = delete_incident(token, inc_id)
                            if res.get("ok"):
                                st.success(f"Đã xóa #{inc_id}")
                                st.session_state.pop(f"confirm_del_{inc_id}", None)
                                st.rerun()
                            else:
                                st.error(f"❌ {res.get('error')}")
                    with cc2:
                        if st.button("Không", key=f"del_no_{inc_id}"):
                            st.session_state.pop(f"confirm_del_{inc_id}", None)
                            st.rerun()

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;color:#1e293b;font-size:0.73rem;
            padding:20px 0 6px;border-top:1px solid rgba(255,255,255,0.05);margin-top:16px">
  🚧 Quản lý Sự cố · PBL5 Giao thông Đà Nẵng · v{APP_VERSION}
</div>
""", unsafe_allow_html=True)
