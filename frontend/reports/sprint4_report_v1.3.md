# Sprint 4 Report — Frontend Hotfix
**Version:** v1.3
**Date:** 28/05/2026
**Author:** Frontend Team (B)

---

## Tổng quan

Sau khi commit Sprint 4 v1.1, phát sinh 7 lỗi thực tế khi team deploy và test. Toàn bộ được fix trong ngày 28/05/2026 qua 3 phiên làm việc.

---

## Fix 1 — `StreamlitPageNotFoundError` (Critical)

**File:** `frontend/app.py`

**Lỗi:** Trang `7_csgt_dashboard.py` và `8_incidents.py` chưa được đăng ký vào `st.navigation()`, khiến `sidebar.py` crash khi gọi `st.page_link()` đến 2 trang này.

**Fix:** Thêm `pg_csgt` và `pg_incidents` vào navigation theo role:
- CSGT: section "🚔 Điều hành" → Dashboard CSGT + Quản lý Sự cố
- Admin: thêm section "🚔 Điều hành" bên cạnh "⚙️ Quản trị"

---

## Fix 2 — Timestamp UTC hiển thị sai (CSGT Dashboard tooltip)

**File:** `frontend/features/map/service.py`

**Lỗi:** Tooltip bản đồ hiển thị raw UTC ISO string (`2026-05-28T05:15:17.853963+00:00`) thay vì giờ VN.

**Fix:** Thêm hàm `_fmt_ts_vn()` — parse ISO UTC → convert sang `+07:00` → format `YYYY-MM-DD HH:MM:SS +07:00`. Frontend-only, không đụng backend.

---

## Fix 3 — Auto-refresh 60s → 240s

**File:** `frontend/config.py`

**Lý do:** `/api/traffic/state` cache Redis 270s. Refresh mỗi 60s là vô nghĩa (data không đổi) và làm map giật.

**Fix:** `REFRESH_INTERVAL_MS = 60_000` → `240_000`. Cập nhật các text hardcode "60 giây" ở `1_home.py` và `sidebar.py`.

---

## Fix 4 — KPI "Tốc độ TB" = 0 khi filter theo quận

**File:** `frontend/pages/1_home.py`

**Lỗi:** Fallback path (filter quận) dùng `meta = traffic` — API trả key `"avg_speed"`, nhưng `render_kpi_cards()` đọc `"avg_speed_city"` → KPI luôn hiện 0.

**Fix:** Normalize meta dict:
```python
meta = {**traffic, "avg_speed_city": traffic.get("avg_speed_city") or traffic.get("avg_speed", 0)}
```

---

## Fix 5 — KPI speed card không đồng đều (`7_csgt_dashboard.py`)

**Lỗi:** Value `"32 km/h"` dài hơn `"0"`, `"2"`, `"1"` → card tốc độ render khác kích cỡ.

**Fix:** Tách đơn vị ra label: value = `"32"`, label = `"km/h · Tốc độ TB toàn TP"`. Tất cả 4 cards giờ chỉ render số đơn thuần.

---

## Fix 6 — Nút "Điều động" lệch dọc trong Top 10 (`7_csgt_dashboard.py`)

**Lỗi:** Nút bị tuột xuống so với card đường bên trái do Streamlit button có default `margin-top`.

**Fix:** CSS `:has()` selector:
```css
[data-testid="stVerticalBlock"]:has(>[data-testid="element-container"]>[data-testid="stButton"]) {
    display: flex; flex-direction: column; justify-content: center; min-height: 52px;
}
```
Xóa `<div style='height:4px'>` spacer thủ công.

---

## Fix 7 — Cải tiến toàn bộ `8_incidents.py` (UX Overhaul)

**4 cải tiến cùng lúc:**

| # | Vấn đề | Fix |
|---|---|---|
| 7a | Badge status không đồng kích cỡ | CSS `.stat-badge` với `min-width:140px; text-align:center` |
| 7b | Nút Xử lý/Xóa lệch dọc với card | CSS `:has()` tương tự Fix 6 |
| 7c | "Thêm sự cố" trôi xuống cuối | Đổi sang `@st.dialog` + nút "➕ Thêm mới" cố định ở filter row |
| 7d | Không có batch action | Checkbox trái mỗi card + thanh "✅ Xử lý tất cả (N)" xuất hiện khi chọn ≥1 |

---

## Files thay đổi

| File | Sprint Fix |
|---|---|
| `frontend/app.py` | Fix 1 |
| `frontend/features/map/service.py` | Fix 2 |
| `frontend/config.py` | Fix 3 |
| `frontend/pages/1_home.py` | Fix 3, Fix 4 |
| `frontend/shared/components/sidebar.py` | Fix 3 (text) |
| `frontend/pages/7_csgt_dashboard.py` | Fix 5, Fix 6 |
| `frontend/pages/8_incidents.py` | Fix 7 (viết lại) |
