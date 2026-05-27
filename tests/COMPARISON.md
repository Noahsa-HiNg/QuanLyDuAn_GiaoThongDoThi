# So Sánh Phương Pháp Cào Dữ Liệu Traffic — Đà Nẵng

## Tổng Quan

| | TomTom Point (OSM Centroid) | HERE Bbox Flow |
|--|--|--|
| **Ý tưởng** | Dùng tọa độ centroid của từng đường trong OSM DB, gọi TomTom tại điểm đó | Gọi HERE với bbox của từng quận, nhận toàn bộ segment trong vùng |
| **API calls (toàn TP)** | ~3,588 (1/đường có tên) | **7** (1/quận) |
| **Thời gian ước tính** | ~24 phút (1 key), ~12 phút (2 keys) | **~30 giây** |
| **Geometry mismatch** | ❌ Không có | ⚠️ ~20-40% tại VN |
| **Quota miễn phí/ngày** | 2,400 × N keys | 250,000/tháng ≈ 8,333/ngày |
| **Cần key riêng** | TomTom (đã có) | HERE (đăng ký thêm) |

---

## Chi Tiết Phương Pháp 1: TomTom Point (OSM Centroid)

### Nguyên lý

```
DB (mapdb):
  id=1  Bạch Đằng  LINESTRING(108.220 16.067, 108.225 16.068, ...)
                              ↓ ST_Centroid()
                         (16.0675, 108.2225) ← 1 điểm đại diện

TomTom API:
  GET /flowSegmentData?point=16.0675,108.2225&key=...
       → { currentSpeed: 42, freeFlowSpeed: 60 }

Mapping:
  street_id=1 → speed=42 km/h → congestion=1 (slow)
```

### Ưu điểm

- **Không bị mismatch:** Tọa độ là của chính OSM DB → map thẳng vào `street_id` không cần spatial join
- **Chính xác:** TomTom probe data thực tế, không phải ước tính
- **Đơn giản:** 1 đường = 1 call = 1 bản ghi

### Nhược điểm

- **Nhiều calls:** 3,588 đường = 3,588 calls/cycle
- **Chậm:** ~12–24 phút/cycle (phụ thuộc số keys)
- **Tốn quota:** Cần ≥ 2 keys cho đường chính, ≥ 5 keys cho tất cả đường có tên
- **Không coverage đường không tên:** ~69,000 segments vô danh bị bỏ qua

### Phù hợp khi

- Cần độ chính xác cao (monitoring đường chính)
- Đã có nhiều TomTom API keys
- Cycle dài (1-2 lần/ngày là đủ)

---

## Chi Tiết Phương Pháp 2: HERE Bbox Flow

### Nguyên lý

```
districts.geometry:
  Hải Châu → bbox: 108.19, 16.04, 108.24, 16.08

HERE API:
  GET /v7/flow?in=bbox:108.19,16.04,108.24,16.08&apiKey=...
       → 150+ segments với { speed, freeFlow, jamFactor, geometry }

Spatial Join (PostGIS):
  Mỗi HERE segment (point) → tìm OSM street gần nhất (ST_DWithin 50m)
  → match: street_id=45 (khoảng cách 12m, confidence cao)
  → miss:  không tìm thấy trong 50m (khoảng cách > 50m, bỏ qua)
```

### Ưu điểm

- **Cực ít calls:** 7 calls toàn Đà Nẵng
- **Nhanh:** ~5s API + ~25s spatial join = 30 giây tổng
- **Coverage rộng:** Phủ cả đường không có tên
- **Thêm thông tin:** `jamFactor` (0–10), `confidence`, traffic flow theo giờ
- **Quota lớn:** HERE miễn phí 250k/tháng → chạy mỗi 3 phút thoải mái

### Nhược điểm

- **Geometry mismatch:** HERE và OSM là 2 nguồn khác nhau
  - Urban (Hải Châu, Thanh Khê): offset ~5–15m → ST_DWithin(50m) bắt được ~90%
  - Suburban: offset ~15–30m → ~75% match
  - Rural (Hòa Vang): HERE có thể không có probe data → ~30% match
- **Cần spatial join:** Phức tạp hơn, cần PostGIS + GIST index
- **Cần HERE key riêng:** Đăng ký tại developer.here.com

### Phù hợp khi

- Cần cập nhật nhanh, thường xuyên (mỗi 5–15 phút)
- Muốn coverage toàn thành phố kể cả đường nhỏ
- Chấp nhận 20–40% miss rate (đủ cho heatmap/tổng quan)

---

## Kết Quả Test Thực Tế

> Cập nhật tự động sau khi chạy `crawl.py`

| Chỉ số | TomTom | HERE |
|--------|--------|------|
| Số đường/segments | _(sau test)_ | _(sau test)_ |
| Thời gian thực | _(sau test)_ | _(sau test)_ |
| Avg speed (km/h) | _(sau test)_ | _(sau test)_ |
| Success rate | _(sau test)_ | _(sau test)_ |
| Mismatch rate | 0% | _(sau test)_ |

---

## Khuyến Nghị Kết Hợp (Hybrid)

```
Giờ cao điểm (06–09h, 17–20h):
  ├── TomTom Point → 300–500 đường chính (primary/secondary/trunk)
  │   Độ chính xác cao, cập nhật mỗi 10 phút
  └── HERE Bbox → 7 quận (coverage rộng)
      Cập nhật mỗi 5 phút, bổ sung đường phụ

Giờ bình thường (09–17h):
  └── HERE Bbox only → tiết kiệm quota TomTom

Ban đêm (20–06h):
  └── HERE Bbox mỗi 30 phút → đủ cho lịch sử/training model
```

### Bảng Quota Tổng Hợp

| Kịch bản | TomTom calls/ngày | HERE calls/ngày | Keys cần |
|---------|------------------|----------------|---------|
| Chỉ TomTom (58 đường) | 2,784 | 0 | 2 keys |
| Chỉ TomTom (500 đường) | 24,000 | 0 | 10 keys |
| Chỉ HERE | 0 | 672 | 1 HERE key |
| **Hybrid (khuyến nghị)** | **4,800** | **672** | **2 TT + 1 HERE** |

---

## Cách Chạy Test

```bash
# Từ thư mục gốc QuanLyDuAn_GiaoThongDoThi/

# Phương pháp 1: TomTom (cần TomTom key trong .env)
python tests/test_tomtom_centroid/crawl.py

# Phương pháp 2: HERE (cần HERE_API_KEY trong .env)
HERE_API_KEY=your_key python tests/test_here_bbox/crawl.py

# Dashboard so sánh
streamlit run tests/compare_view.py
```

---

## Kết Luận

**Không có phương pháp nào "tốt hơn tuyệt đối"** — mỗi cái phục vụ một mục đích:

| Mục đích | Chọn |
|----------|------|
| Độ chính xác tối đa cho đường chính | **TomTom Point** |
| Coverage nhanh toàn thành phố | **HERE Bbox** |
| Hệ thống production đầy đủ | **Hybrid cả hai** |
| Đồ án (demo/báo cáo) | **TomTom Point (58 đường)** — đã hoạt động |
