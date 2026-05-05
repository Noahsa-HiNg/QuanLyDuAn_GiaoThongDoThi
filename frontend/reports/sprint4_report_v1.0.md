# Sprint 4 Report — Frontend
**Version:** v1.0
**Date:** 06/05/2026
**Author:** Frontend Team (B)
**Sprint:** 29 Apr – 06 May 2026

---

## ✅ Completed — S3-35, S4-37, S4-40, S4-43 + Admin

### S3-35: Trang Đăng nhập (hoàn thiện Sprint 4)
- Form email + password, gọi `POST /api/auth/login`, lưu JWT vào `session_state`
- Hiển thị lỗi rõ ràng khi sai credentials; spinner loading khi đang xác thực
- Nút đăng xuất (↩) trong sidebar xóa token + rerun về trang Guest

### Navigation RBAC — `app.py`
- Dùng `st.navigation()` với danh sách pages động theo role
- **Guest**: Bản đồ giao thông · Tìm đường · Đăng nhập
- **CSGT**: Bản đồ giao thông · Tìm đường · Dashboard
- **Admin**: Bản đồ giao thông · Tìm đường · Dashboard · Quản lý tài khoản · Quản lý cào dữ liệu
- `auth_guard.py`: hàm `require_admin()` / `require_login()` redirect nếu chưa đủ quyền

### S4-37 + S4-40: Trang Tìm đường thông minh
- 2 selectbox chọn điểm xuất phát/đến từ 14 địa điểm tiêu biểu Đà Nẵng
- Chế độ: 📏 **Ngắn nhất** / ⚡ **Nhanh nhất** (dựa trên tốc độ giao thông thực tế)
- Gọi `GET /api/routes` — backend A* (`networkx` + `KDTree` snap GPS)
- Leaflet.js dark mode: vẽ polyline tuyến đường + marker xuất phát (xanh) / đích (đỏ)
- 3 thẻ tóm tắt: km · phút · số đoạn đường; danh sách tên đường đi qua

### Quản lý tài khoản — `5_admin_users.py`
- Bảng 5 cột căn thẳng hàng: Tài khoản · Vai trò · Trạng thái · Thời gian · Hành động
- Metric cards: Tổng / Đang hoạt động / Đang bị khóa / Quản trị viên
- Form tạo tài khoản mới (email, mật khẩu, họ tên, vai trò)
- Nút khóa 🔒 / mở khóa 🔓 / vô hiệu hóa ⛔ gọi trực tiếp API Admin

### Quản lý cào dữ liệu — `6_admin_scheduler.py`
- Banner trạng thái APScheduler (ĐANG CHẠY / TẠM DỪNG) với màu realtime
- Nút Tạm dừng / Tiếp tục scheduler; nút Cào ngay (trigger thủ công)
- Bảng danh sách jobs đang lên lịch + lần chạy tiếp theo
- Trạng thái lần cào gần nhất: Thành công / Thất bại / Thời điểm

---

## 🎨 UI/UX Refinements

| Hạng mục | Thay đổi |
|---|---|
| Sidebar navigation | Bỏ emoji icon khỏi label; tăng font-size lên 0.97rem |
| Sidebar layout | Đảo thứ tự: User widget trên → Nav → Branding dưới |
| Branding per-page | `render_sidebar(brand_icon, brand_title, brand_subtitle)` — mỗi trang có branding riêng |
| Emoji trong gradient h1 | Tách emoji ra `<span>` độc lập, gradient chỉ áp lên text → fix ô trắng |
| Admin Users table | Đổi 3 cols (có spacer rỗng) → 2 cols; bỏ icon khỏi badge, đồng nhất `height:54px` |
| Route Finder sidebar | Box info thuật toán A* + tip hướng dẫn sử dụng |
| Tạo tài khoản | Bỏ icon ✅ khỏi nút submit |

---

## 🔧 Issues từ Sprint 3 — Còn lại

| # | Vấn đề | Trạng thái |
|---|---|---|
| 1 | Migration file thiếu `segment_idx` | ⚠️ Còn — chưa fix |
| 2 | `st.components.v1.html` deprecated 01/06/2026 | ⚠️ Còn — chờ Streamlit stable API |
| 3 | Dashboard API endpoints (`/stats/hourly`, `/stats/heatmap`) | ⚠️ Dùng mock data |

---

## ⚠️ Known Issues — Sprint 4

| # | Vấn đề | Mức độ |
|---|---|---|
| 1 | Route graph chỉ dùng `MANUAL_COORDS` (14 node) — chưa kết nối toàn bộ 43 đường | Trung bình |
| 2 | Đường thay thế (S4-39) chưa implement — chỉ trả 1 tuyến | Thấp |
| 3 | Bản đồ Route Finder không tự zoom vào tuyến đường sau khi tìm | Thấp |

---

## 🔧 Files thay đổi Sprint 4

| File | Thay đổi |
|---|---|
| `app.py` | Đổi `st.navigation()` RBAC động theo role; bỏ `url_path` |
| `pages/4_login.py` | **Hoàn thiện** — form login JWT, session state, redirect |
| `pages/3_route_finder.py` | **Mới hoàn toàn** — A* UI, Leaflet map, summary cards |
| `pages/5_admin_users.py` | **Mới hoàn toàn** — quản lý tài khoản, 5-col table |
| `pages/6_admin_scheduler.py` | **Mới hoàn toàn** — APScheduler monitor & control |
| `shared/components/sidebar.py` | `brand_icon/title/subtitle` params; reorder layout; CSS nav font |
| `shared/api/client.py` | Thêm `get_route_api()`, `admin_*` functions |
| `shared/utils/auth_guard.py` | `require_admin()`, `require_login()` helpers |

---

## 📊 Hệ thống hiện tại

| Thành phần | Trạng thái |
|---|---|
| 7 Docker containers | ✅ All running |
| API `/api/auth/login` | ✅ 200 OK |
| API `/api/routes` | ✅ 200 OK (A* + KDTree) |
| API Admin endpoints | ✅ Hoạt động với JWT Bearer |
| Tài khoản test | 👑 `admin@danang-traffic.vn` · 🚔 `csgt@danang.gov.vn` |
| Frontend | ✅ http://localhost:8501 |

---

## 📝 Ghi chú kỹ thuật

- **RBAC:** `st.navigation()` nhận list hoặc dict pages → dùng dict để tạo section "⚙️ Quản trị" cho Admin
- **Auth guard:** dùng `st.stop()` sau `st.switch_page()` để đảm bảo không render tiếp trang bị chặn
- **Route API:** backend dùng `KDTree` để snap tọa độ GPS người dùng vào node gần nhất trong graph
- **Leaflet in Streamlit:** nhúng qua `st.components.v1.html()`, dữ liệu truyền vào qua f-string JSON inject
- **Gradient + emoji bug:** `-webkit-text-fill-color: transparent` làm emoji trong suốt → tách emoji ra `<span>` riêng ngoài gradient
