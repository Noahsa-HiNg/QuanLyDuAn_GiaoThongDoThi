# Sprint 4 Report — Frontend
**Version:** v1.2
**Date:** 28/05/2026
**Author:** Frontend Team (B)
**Sprint:** Sprint 4 — Hotfix: Timestamp + Auto-refresh

---

## 🐛 Hotfix — 2 lỗi phát sinh sau Sprint 4 v1.1

### Fix 1: Timestamp hiển thị sai định dạng trong tooltip

**Vấn đề:**
Tooltip bản đồ tại field "Cập nhật" hiển thị raw UTC ISO string:
```
🕐 Cập nhật: 2026-05-28T05:15:17.853963+00:00
```

**Nguyên nhân:**
Hàm `build_map_dataframe_split()` (thêm ở v1.1) lấy `s.get("timestamp")` trực tiếp
từ `/api/traffic/state` — endpoint này chỉ trả `timestamp` dạng UTC ISO, không có field
`timestamp_vn` (đã format sẵn) như `/api/traffic/current`.

**Fix (frontend-only, không đụng backend):**
Thêm hàm `_fmt_ts_vn()` trong `features/map/service.py`:
- Parse chuỗi ISO UTC bằng `datetime.fromisoformat()`
- Convert sang múi giờ `+07:00` (Hà Nội/TP.HCM)
- Format thành `"YYYY-MM-DD HH:MM:SS +07:00"`

**Kết quả:**
```
🕐 Cập nhật: 2026-05-28 12:15:17 +07:00   ✅
```

---

### Fix 2: Auto-refresh 60s → 240s

**Vấn đề:**
Map đang tự refresh mỗi 60 giây trong khi `/api/traffic/state` cache Redis 270 giây.
→ 3 lần refresh trong 270s là vô nghĩa (data không đổi) + làm map giật, UX kém.

**Fix (frontend-only, không đụng backend):**
Trong `frontend/config.py`:
```python
# Trước
REFRESH_INTERVAL_MS = 60_000   # 60 giây

# Sau
REFRESH_INTERVAL_MS = 240_000  # 240 giây (4 phút)
```

**Lý do chọn 240s:**
- Cache state TTL = 270s → refresh mỗi 240s đảm bảo luôn lấy data mới sau mỗi chu kỳ
- Phù hợp chu kỳ cào thực tế (mỗi ~5 phút)

---

## 🔧 Files thay đổi

| File | Thay đổi |
|---|---|
| `frontend/features/map/service.py` | Thêm `_fmt_ts_vn()` + dùng cho `timestamp_vn` trong `build_map_dataframe_split` |
| `frontend/config.py` | `REFRESH_INTERVAL_MS`: `60_000` → `240_000` |

---

## 📝 Ghi chú kỹ thuật

- **Tại sao `/api/traffic/state` không có `timestamp_vn`:** Endpoint state được thiết kế tối giản (~1MB) — chỉ chứa dữ liệu cần thiết (congestion, speed, color). Format timestamp được delegate về phía frontend.
- **`_fmt_ts_vn` an toàn:** Có try/except fallback — nếu timestamp lỗi format hoặc None thì trả `"-"`, không crash.
- **`REFRESH_INTERVAL_MS` ảnh hưởng toàn bộ:** Constant này dùng duy nhất ở `1_home.py` → chỉ cần sửa 1 chỗ trong config.
