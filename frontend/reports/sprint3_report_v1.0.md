# Sprint 3 Report — Frontend
**Version:** v1.0
**Date:** 26/04/2026
**Author:** Frontend Team (B)
**Sprint:** 22 Apr – 29 Apr 2026

---

## ✅ Completed — SCRUM 36–39

### SCRUM-36: Trang Dự báo AI
- HTML table thuần (không dùng `st.dataframe`) — render nhanh, style hoàn toàn tự kiểm soát
- Badge trạng thái dùng **CSS dot** (`border-radius: 50%`) thay emoji Unicode → căn hàng tuyệt đối trên mọi OS
- Cột **Xu hướng** riêng biệt: `▲ Xấu hơn / ▼ Cải thiện / — Giữ nguyên` (tách khỏi badge tình trạng)
- Confidence bar dạng mini progress bar màu sắc theo ngưỡng (≥80% xanh / ≥65% vàng / đỏ)
- Filter tìm kiếm + lọc theo xu hướng — client-side trên DataFrame

### SCRUM-37: Biểu đồ Xu hướng 7 ngày
- Plotly `go.Scatter` — 3 trace (Thông thoáng / Chậm / Kẹt xe) + fill `tozeroy`
- Annotation vùng cao điểm sáng (7–9h) và chiều (17–19h)
- Bộ lọc số ngày (7/14/30) chuyển vào **sidebar** — giải phóng main content area
- `config={"displayModeBar": False}` — ẩn toolbar Plotly, tránh che legend khi hover

### SCRUM-38: Heatmap thời gian
- Plotly `go.Heatmap` — trục X: 24 giờ, trục Y: 7 ngày trong tuần
- Palette `RdYlGn_r` — đỏ = kẹt, xanh = thông thoáng
- Legend đọc heatmap bên dưới chart

### SCRUM-39: Báo cáo & Thống kê
- KPI 5 cột: Tổng tuyến / Records DB / Thông thoáng / Chậm / Kẹt
- Bar chart stacked: phân bổ ùn tắc theo quận
- Top 5 đường kẹt nhất dạng card (flex layout, rank #1–5)
- Gauge chart tốc độ TB toàn thành phố + delta so với 40 km/h
- Progress bars trạng thái hệ thống (% theo từng mức)

---

## 🎨 UI/UX Refinements

| Hạng mục | Thay đổi |
|---|---|
| Sidebar Dashboard | Thêm bộ lọc (ngày, quận), header `📊 Dashboard` flex-row icon + text căn trái |
| Sidebar Home | Đồng bộ format header với Dashboard (`🚦` inline bên trái chữ) |
| Plotly toolbar | `displayModeBar: False` cho tất cả 4 charts |
| `use_container_width` | Deprecated → đổi sang `width="stretch"` (4 charts trong dashboard) |
| `top_html` | Đổi triple-quoted indented f-string → single-line string concat (tránh Markdown code block bug) |
| Filter labels | `⬆️ Xấu hơn / ⬇️ Tốt hơn / ➡️ Không đổi` → `▲ / ▼ / —` khớp cột Xu hướng |

---

## 🔧 Issues từ Sprint 2 — Còn lại

| # | Vấn đề | Trạng thái |
|---|---|---|
| 1 | Migration file thiếu `segment_idx` | ⚠️ Còn — chưa fix |
| 2 | `st.components.v1.html` deprecated 01/06/2026 | ⚠️ Còn — chờ Streamlit stable API |

---

## ⚠️ Known Issues — Backend chưa implement

| Endpoint | HTTP | SCRUM | Mức độ |
|---|---|---|---|
| `/api/predict/30min` | 404 | SCRUM-32 | Cao — dashboard dùng mock data |
| `/api/stats/hourly-trend` | 404 | SCRUM-35 | Cao — dashboard dùng mock data |
| `/api/stats/heatmap` | 404 | SCRUM-35 | Cao — dashboard dùng mock data |
| `/api/stats/report` | 404 | SCRUM-35 | Cao — dashboard dùng mock data |

> Frontend đã có `try-except` fallback sang mock data — không crash, nhưng data chưa thực.

---

## 🔧 Files thay đổi Sprint 3

| File | Thay đổi |
|---|---|
| `pages/2_dashboard.py` | **Mới hoàn toàn** — 4 tabs SCRUM 36–39, sidebar, 4 Plotly charts |
| `shared/components/sidebar.py` | Header style: `text-align:center` → `display:flex` icon inline |
| `assets/style/main.css` | Không thay đổi |

---

## 📊 Hệ thống hiện tại

| Thành phần | Trạng thái |
|---|---|
| 7 Docker containers | ✅ All running |
| Traffic records trong DB | 192 bản ghi/chu kỳ (tăng liên tục) |
| Scheduler | ✅ 43/43 đường, mỗi 30 phút |
| API `/api/traffic/current` | ✅ 200 OK |
| API Dashboard endpoints | ⚠️ 404 — chờ backend Sprint 3 |
| Frontend | ✅ http://localhost:8501 |

---

## 📝 Ghi chú kỹ thuật

- **Mock data:** các hàm `get_mock_*` trong `client.py` sẵn sàng thay bằng API thật — chỉ cần đổi URL trong `config.py`
- **Sidebar state:** `days_sel` và `district_filter` định nghĩa trong `with st.sidebar:` trước tabs → dùng được toàn page
- **CSS specificity:** dashboard inject CSS sau `main.css` → override padding `.block-container` bằng cùng selector + `!important`
- **Plotly categorical axis:** cần `type="category"` khi set `range` bằng index integer, không dùng string label
