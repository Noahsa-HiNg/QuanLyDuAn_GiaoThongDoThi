# Sprint 2 Report — Frontend
**Version:** v1.0
**Date:** 21/04/2026
**Author:** Frontend Team (B)
**Sprint:** 22 Apr – 29 Apr 2026

---

## ✅ Completed — SCRUM 22–26, 28

### SCRUM 22: Tìm kiếm tên đường
- `st.text_input` trong sidebar — gõ từ khoá tìm tên đường
- Filter **client-side** trên DataFrame (không gọi thêm API)
- So khớp một phần, không phân biệt hoa thường (`str.contains(case=False)`)
- Ví dụ: gõ "Bạch" → map chỉ hiện đường **Bạch Đằng**

### SCRUM 23: Lọc theo mức ùn tắc
- `st.selectbox` 4 options: Tất cả / Thông thoáng / Chậm / Kẹt xe
- Filter client-side trên cột `congestion_level` trong DataFrame
- Có thể kết hợp với SCRUM-22 (filter đồng thời tên + mức kẹt)

### SCRUM 24: Lọc theo quận *(đã có từ Sprint 1, xác nhận đúng)*
- `st.selectbox` 8 quận Đà Nẵng → truyền `district_id` lên `GET /api/traffic/current`
- Backend filter server-side → KPI cards tự nhảy theo quận đang chọn ✅

### SCRUM 25: Nút Reset bộ lọc
- Nút "↩️ Reset bộ lọc" trong sidebar
- Sử dụng `session_state` keys riêng cho từng filter (`sb_district`, `sb_congestion`, `sb_search`)
- Nút tự **disable** khi không có filter nào đang active — UX clean
- Dùng `on_click=_reset_filters` callback (không dùng if-block) để tránh `StreamlitAPIException`
- **Chỉ reset filter**, không clear cache — data không bị reload lại

### SCRUM 26: Auto-Refresh 60 giây *(đã có từ Sprint 1, xác nhận đúng)*
- `st_autorefresh(interval=REFRESH_INTERVAL_MS)` trong `1_home.py` ✅

### SCRUM 28: Empty State *(đã có từ Sprint 1, nâng cấp)*
- Empty state cũ: backend không có data → `st.warning()`
- **Thêm mới Sprint 2:** filter không có kết quả → `st.info()` thông minh
  - Hiển thị đúng filter nào gây ra trống: `Không tìm thấy đường nào với bộ lọc: tên chứa "abc" + mức "Kẹt xe"`

---

## 🔧 Issues từ Sprint 1 — Đã giải quyết

| # | Vấn đề Sprint 1 | Trạng thái |
|---|---|---|
| 1 | Encoding tên đường `C?ch M?ng Th?ng 8` | ✅ **Fixed** — Import lại DB qua `traffic_dump.sql` UTF-8 |
| 2 | `segments[]` rỗng cho đường ngắn | ✅ **Fixed** — Backend Sprint 2 luôn trả segments có data |
| 3 | Migration thiếu `segment_idx` | ⚠️ **Partial** — Dump có column đúng; migration file vẫn thiếu (rủi ro fresh install) |
| 4 | Historical data chưa import | ✅ **Resolved** — Scheduler live collect 384+ bản ghi từ hôm nay |
| 5 | API thiếu `avg_speed_city` | ✅ **Fixed** — Backend Sprint 2 tính và trả về; frontend hiển thị đúng |

---

## 🔧 Fix kỹ thuật frontend trong Sprint 2

| File | Thay đổi |
|---|---|
| `kpi_cards.py` v1.1 | Fix `avg_speed_city`: dùng `or 0` thay `get(..., 0)` để xử lý cả `None` |
| `service.py` v1.3 | Sync comment với Sprint 2 backend; đơn giản hoá else-branch (chỉ còn centroid fallback) |
| `sidebar.py` v2.0 | Thêm SCRUM 22–25; session_state; on_click reset |
| `service.py` v1.4 | Thêm `filter_dataframe()` client-side |
| `1_home.py` v1.2 | Wire 3-tuple từ sidebar; apply filter; smart empty state |

---

## 📊 Hệ thống hiện tại

| Thành phần | Trạng thái |
|---|---|
| 7 Docker containers | ✅ All running (nginx cần tắt IIS port 80 trước) |
| Traffic records trong DB | 384+ bản ghi live (tăng theo chu kỳ scheduler) |
| Scheduler | ✅ Chạy mỗi 30 phút, 43/43 đường, ~192 bản ghi/chu kỳ |
| API quota còn | ~2000+ requests/ngày |
| Frontend | ✅ http://localhost:8501 |
| Tên đường tiếng Việt | ✅ Đúng hoàn toàn sau khi import dump |

---

## ⚠️ Known Issues — Còn lại

| # | Vấn đề | Bên xử lý | Mức độ |
|---|---|---|---|
| 1 | Migration file vẫn thiếu `segment_idx` — ai `alembic upgrade head` mà không dùng dump sẽ lỗi | **Hiếu (Backend)** | Trung bình |
| 2 | `mock.py` dùng format cũ (`path[]` thay vì `segments[]`) — nếu backend down, map chỉ hiện dots | Frontend | Thấp |
| 3 | `st.components.v1.html` sẽ bị deprecated 01/06/2026 — sidebar toggle JS cần đổi sang `st.iframe` | Frontend | Thấp |
| 4 | Dump data ngày 19/04 không import được do Alembic chạy trước → lỗi COPY silent | **Hiếu (Backend)** | Thấp (scheduler đang collect data thật) |

---

## 📝 Ghi chú kỹ thuật

- **Filter architecture:** district → server-side (API) | search + congestion → client-side (DataFrame)
- **KPI cards:** luôn tính trên data toàn quận (`df_full`), không bị ảnh hưởng bởi client-side filter
- **Session state keys:** prefix `sb_` để tránh xung đột với Streamlit widgets khác
- **Reset button:** phải dùng `on_click=callback` thay vì `if button: st.session_state[key]=val` để tránh `StreamlitAPIException`
- **Data flow:** TomTom/Goong → Scheduler (30 phút) → PostgreSQL → FastAPI → Streamlit cache (TTL) → Pydeck map
