# Sprint 4 Report — Frontend
**Version:** v1.1
**Date:** 27/05/2026
**Author:** Frontend Team (B)
**Sprint:** Sprint 4 — Route Finder UX & Map Performance Patch

---

## ✅ Hoàn thành — SCRUM-44, SCRUM-46 (cập nhật) + Performance Patch

### SCRUM-44: Form Điểm Đi-Đến — Nâng cấp toàn bộ input flow

**Vấn đề trước:**
- Ô nhập tên đường hiển thị dropdown các đường có sẵn (không phải để nhập tự do)
- Không hỗ trợ gõ không dấu (`bach dang` → không khớp `Bạch Đằng`)
- Chữ `đ/Đ` không được normalize đúng qua NFKD Unicode

**Đã fix:**
- Chuyển sang gõ tự do + fuzzy match: user gõ tên đường → Enter hoặc blur → tự động pin marker lên map
- Sửa hàm `_norm()` thêm `.replace("đ", "d")` trước NFKD — xử lý đúng ký tự Latin duy nhất không decompose được trong tiếng Việt
- Pipeline normalize đầy đủ: `lower()` → `replace("đ","d")` → `NFKD` → strip combining chars → khớp mọi kiểu gõ (có dấu, không dấu, sai dấu, HOA/thường)
- Xóa div thừa `search-panel` gây ô bo tròn rỗng giữa màn hình

**Ví dụ matching:**

| Gõ vào | Kết quả |
|---|---|
| `bach dang` | ✅ Bạch Đằng |
| `BACH DANG` | ✅ Bạch Đằng |
| `bạch đẳng` | ✅ Bạch Đằng (sai dấu vẫn khớp) |
| `dien bien phu` | ✅ Điện Biên Phủ |
| `ton duc thang` | ✅ Tôn Đức Thắng |

### SCRUM-46: Thông Tin Tuyến Đường — Xác nhận hoàn chỉnh

- So sánh 2 tuyến (Ngắn nhất / Nhanh nhất): hiển thị km, phút, số đoạn đường
- Badge `⭐ Khuyến nghị` tự động theo tuyến nhanh hơn
- Radio switch xem tuyến trên bản đồ (tím = ngắn nhất, xanh = nhanh nhất)
- Danh sách đường đi qua + trạng thái traffic thực tế (màu + tốc độ km/h)

---

## 🔧 Fix Backend — Router Conflict `/api/streets/midpoints`

**Vấn đề:** FastAPI route `GET /api/streets/{street_id}` (nhận int) bắt mất request
`GET /api/streets/midpoints` trước khi endpoint đúng được gọi → 422 Unprocessable Entity
→ `STREET_LOOKUP` rỗng → mọi tên đường đều không pin được.

**Fix:** Reorder trong `backend/routers/streets.py` — đặt `/streets/midpoints` **trước** `/{street_id}`:

```python
# TRƯỚC khi fix — /midpoints bị /{street_id} bắt mất
@router.get("/streets/{street_id}")   # ← đặt trước
@router.get("/streets/midpoints")     # ← không bao giờ được gọi

# SAU khi fix — đúng thứ tự FastAPI
@router.get("/streets/midpoints")     # ← static path trước
@router.get("/streets/{street_id}")   # ← dynamic path sau
```

---

## ⚡ Performance — Map 2-Step Loading (`1_home.py`)

**Vấn đề:** Mỗi 60s auto-refresh, backend phải query lại toàn bộ geometry (~17MB) từ PostgreSQL
→ render map mất 3–5 giây mỗi lần.

**Kiến trúc mới (2 API song song từ team):**

| API | Dữ liệu | Chu kỳ |
|---|---|---|
| `GET /api/traffic/streets-geometry` | Geometry tọa độ vẽ đường (tĩnh) | Cache Redis 1h |
| `GET /api/traffic/state` | Congestion level + màu + tốc độ (động) | Cache Redis 270s |

**Luồng mới:**
```
Lần đầu load:
  get_streets_geometry() → st.session_state.map_geometry  (1 lần duy nhất)

Mỗi 60s auto-refresh:
  get_traffic_state()  → ~1MB  (không có geometry)
  build_map_dataframe_split(geometry, state) → merge + tính KPI stats

Fallback: district_id != None → dùng API cũ /traffic/current?district_id=X
```

**Kết quả:** Lần đầu ~3s (load geometry), các lần sau < 1s (chỉ load state).

---

## 🗂️ Files thay đổi

| File | Thay đổi |
|---|---|
| `backend/routers/streets.py` | Reorder: `/streets/midpoints` đặt TRƯỚC `/{street_id}` |
| `frontend/pages/3_route_finder.py` | Fix `_norm()` ×2 (thêm `replace("đ","d")`); xóa div thừa `search-panel` |
| `frontend/shared/api/client.py` | Thêm `get_streets_geometry()`, `get_traffic_state()` |
| `frontend/features/map/service.py` | Thêm `build_map_dataframe_split()` — merge geometry + state → DataFrame + meta KPI |
| `frontend/pages/1_home.py` | Refactor `main()`: geometry cache session_state + state poll 60s |

---

## 📊 Hệ thống hiện tại

| Thành phần | Trạng thái |
|---|---|
| API `/api/streets/midpoints` | ✅ 200 OK (router fix) |
| API `/api/traffic/streets-geometry` | ✅ 200 OK (cache Redis 1h) |
| API `/api/traffic/state` | ✅ 200 OK (cache Redis 270s) |
| Route Finder fuzzy match | ✅ Hỗ trợ đầy đủ không dấu / sai dấu / HOA thường |
| Map reload performance | ✅ 3-5s → <1s (lần 2 trở đi) |

---

## 📝 Ghi chú kỹ thuật

- **`đ` và Unicode NFKD:** Ký tự `đ` (U+0111, Latin Small Letter D with Stroke) KHÔNG được NFKD decompose thành `d` + combining mark như các ký tự tiếng Việt khác. Đây là ký tự Latin duy nhất trong bảng chữ cái tiếng Việt cần replace thủ công trước khi normalize. Tất cả ký tự còn lại (`ă`, `â`, `ê`, `ô`, `ơ`, `ư` + các thanh điệu) đều được NFKD xử lý đúng.
- **FastAPI route ordering:** FastAPI khớp route theo thứ tự khai báo trong file. Path tĩnh (như `/midpoints`) phải đặt trước path động (như `/{id}`) nếu cùng prefix.
- **2-step map loading:** `st.session_state` persistent trong suốt session Streamlit của 1 user, nên geometry chỉ cần fetch 1 lần. Nút "Thử lại" cần xóa cả `session_state["map_geometry"]` lẫn `st.cache_data` để force re-fetch.
- **`build_map_dataframe_split` vs `build_map_dataframe`:** Hàm mới không nhận `district_id` vì geometry endpoint không hỗ trợ filter — filter quận vẫn dùng API cũ `/traffic/current?district_id=X` để tương thích.
