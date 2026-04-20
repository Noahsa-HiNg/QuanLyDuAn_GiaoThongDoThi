# Sprint 1 Report — Frontend
**Version:** v1.0
**Date:** 20/04/2026
**Author:** Frontend Team (B)

---

## ✅ Completed

### SCRUM 8–10: Bản đồ Pydeck
- Hiển thị **43 đường** Đà Nẵng dạng line màu trên dark map (CARTO dark-matter)
- Màu theo congestion: 🟢 Xanh / 🟡 Vàng / 🔴 Đỏ
- Tooltip hover: tên đường, tốc độ, tình trạng, thời gian cập nhật
- Xử lý 2 trường hợp geometry: `segments[].path` (đường dài) và `street.path` (đường ngắn)

### SCRUM 11: 3 KPI Cards
- Đường kẹt xe / % Thông thoáng / Tốc độ TB — glassmorphism style

### SCRUM 12: Nút Làm mới
- Clear Streamlit cache + rerun ngay lập tức

### SCRUM 13: Dark Mode + Footer
- Dark glassmorphism theme toàn app (inject CSS từ `assets/style.css`)
- Footer: tên nhóm, version, nguồn dữ liệu

### SCRUM 14: Loading Spinner
- `st.spinner()` khi đang fetch backend

### Khác
- Cấu trúc Feature-based architecture (app.py / pages / features / shared / assets)
- Auto-refresh 60 giây
- Mock data fallback tự động khi backend chưa sẵn

---

## ⚠️ Known Issues — Cần báo Backend

| # | Vấn đề | Bên xử lý | Mức độ |
|---|---|---|---|
| 1 | Tên đường/quận trong DB lỗi encoding — hiển thị `C?ch M?ng Th?ng 8` | **Hiếu (Backend)** | Cao |
| 2 | API `segments[]` rỗng cho đường ngắn — đã tạm fix frontend | **Hiếu (Backend)** | Trung bình |
| 3 | Migration Alembic thiếu cột `segment_idx` — ai clone repo mới sẽ lỗi | **Hiếu (Backend)** | Cao |
| 4 | Historical data (21,869 bản ghi trong dump) chưa import do lỗi `segment_idx` cũ | **Hiếu (Backend)** | Trung bình |
| 5 | **API thiếu field `avg_speed_city`** trong response của `GET /api/traffic/current` — KPI card "Tốc độ TB" đang hiển thị 0 | **Hiếu (Backend)** | Trung bình |

---

## 📊 Hệ thống hiện tại

| Thành phần | Trạng thái |
|---|---|
| 7 Docker containers | ✅ All running |
| Traffic records trong DB | 576 bản ghi (live từ TomTom) |
| Scheduler | ✅ Chạy mỗi 30 phút, 43/43 đường |
| API quota còn | ~2200 requests/ngày |
| Frontend | ✅ http://localhost:8501 |

---

## 📝 Ghi chú kỹ thuật

- **Data flow:** TomTom → Scheduler (30 phút/lần) → PostgreSQL → FastAPI → Streamlit
- **Geometry:** `segments[].path` ưu tiên → `street.path` fallback → ScatterLayer dot
- **Khi Hiếu fix encoding DB:** frontend tự hiển thị đúng, không cần sửa thêm
- **Khi Hiếu chuẩn hóa API (1 format duy nhất):** xóa `else` branch trong `service.py`
