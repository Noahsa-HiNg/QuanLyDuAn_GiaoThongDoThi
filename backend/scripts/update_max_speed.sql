-- =============================================================================
-- update_max_speed.sql
-- Cập nhật max_speed cho bảng streets dựa trên free_flow_speed từ HERE API
--
-- CHIẾN LƯỢC (3 bước):
--   Bước 1: Gán max_speed từ free_flow_speed HERE (làm sạch outlier)
--   Bước 2: Fill NULL còn lại theo tên đường (bảng tham chiếu thủ công)
--   Bước 3: Fill NULL còn lại theo loại đường (highway type fallback)
--
-- CHẠY:
--   docker compose exec postgres psql -U myadmin -d qlda_dothithongminh -f /scripts/update_max_speed.sql
-- =============================================================================

BEGIN;

-- ─── BƯỚC 1: CẬP NHẬT TỪ FREE_FLOW_SPEED CỦA HERE API ──────────────────────
-- Lấy giá trị freeflow trung bình mỗi đường (chỉ từ nguồn here_bbox)
-- Làm sạch outlier: chỉ nhận giá trị trong khoảng [15, 120] km/h
-- Chuẩn hóa về mức hợp lý: làm tròn lên bội số của 10
-- (ví dụ: 43 km/h → 50, 61 km/h → 70, 113 km/h → 120)

WITH freeflow_per_street AS (
    SELECT
        td.street_id,
        ROUND(AVG(td.free_flow_speed)) AS raw_freeflow
    FROM traffic_data td
    WHERE
        td.free_flow_speed IS NOT NULL
        AND td.source = 'here_bbox'
        AND td.free_flow_speed BETWEEN 15 AND 120  -- loại bỏ outlier
    GROUP BY td.street_id
),
normalized AS (
    SELECT
        street_id,
        raw_freeflow,
        -- Chuẩn hóa về bội số gần nhất của 10, giới hạn trong [20, 120]
        LEAST(120, GREATEST(20,
            CASE
                WHEN raw_freeflow <= 25 THEN 20
                WHEN raw_freeflow <= 35 THEN 30
                WHEN raw_freeflow <= 45 THEN 40
                WHEN raw_freeflow <= 55 THEN 50
                WHEN raw_freeflow <= 65 THEN 60
                WHEN raw_freeflow <= 75 THEN 70
                WHEN raw_freeflow <= 85 THEN 80
                WHEN raw_freeflow <= 100 THEN 90
                WHEN raw_freeflow <= 110 THEN 100
                ELSE 120
            END
        )) AS normalized_speed
    FROM freeflow_per_street
)
UPDATE streets s
SET max_speed = n.normalized_speed
FROM normalized n
WHERE s.id = n.street_id
  AND (s.max_speed IS NULL OR s.max_speed != n.normalized_speed);

-- Kiểm tra kết quả bước 1
SELECT 'Bước 1 (HERE freeflow):' as step,
       COUNT(*) as updated_rows,
       MIN(max_speed) as min_speed,
       MAX(max_speed) as max_speed,
       ROUND(AVG(max_speed)) as avg_speed
FROM streets WHERE max_speed IS NOT NULL;


-- ─── BƯỚC 2: OVERRIDE THEO TÊN ĐƯỜNG CỤ THỂ ────────────────────────────────
-- Cập nhật theo tên đường đã biết chính xác (từ quy định ATGT Việt Nam)
-- Áp dụng cho TẤT CẢ rows có cùng tên (kể cả đã có max_speed từ bước 1)

UPDATE streets SET max_speed = 80
WHERE name IN ('Võ Nguyên Giáp', 'Võ Chí Công', 'Quốc lộ 1A',
               'Quốc lộ 14B', 'ĐT605', 'Đường Võ Nguyên Giáp',
               'Đường Võ Chí Công');

UPDATE streets SET max_speed = 60
WHERE name IN ('Trần Phú', 'Lê Duẩn', 'Nguyễn Văn Linh',
               'Điện Biên Phủ', 'Nguyễn Tất Thành', 'Trường Chinh',
               'Phạm Văn Đồng', 'Hoàng Sa', 'Trường Sa',
               'Lê Văn Hiến', 'Nguyễn Lương Bằng', 'Nguyễn Sinh Sắc',
               'Cách Mạng Tháng 8', 'Trần Thị Lý', 'Nguyễn Hữu Thọ',
               '2 tháng 9', 'Cầu Rồng',
               'Đường Trường Sa', 'Đường Hoàng Sa', 'Đường Phạm Văn Đồng',
               'Đường Nguyễn Tất Thành', 'Đường Lê Văn Hiến',
               'Đường Nguyễn Sinh Sắc', 'Đường 2 tháng 9');

UPDATE streets SET max_speed = 50
WHERE name IN ('Bạch Đằng', 'Hùng Vương', 'Phan Châu Trinh',
               'Lý Tự Trọng', 'Hoàng Diệu', 'Nguyễn Chí Thanh',
               'Ông Ích Khiêm', 'Tôn Đức Thắng', 'Núi Thành',
               'Ngô Quyền', 'Lê Văn Duyệt', 'Trần Hưng Đạo',
               'Huyền Trân Công Chúa', 'Phan Đình Phùng',
               'Hoàng Văn Thái', 'Tôn Thất Thuyết', 'Trần Đại Nghĩa',
               'Nguyễn Đức Cảnh', 'Ngô Thì Nhậm', 'Lý Thái Tổ',
               'Lê Trọng Tấn', 'Hòa Phước', 'Nguyễn Tri Phương',
               '30 tháng 4',
               'Đường Bạch Đằng', 'Đường Hùng Vương',
               'Đường Nguyễn Chí Thanh', 'Đường Ngô Quyền',
               'Đường Trần Hưng Đạo', 'Đường Lê Trọng Tấn');

UPDATE streets SET max_speed = 40
WHERE name IN ('Châu Thị Vĩnh Tế', 'Vũ Hữu Lợi', 'Cầu Sông Hàn',
               'Yên Bái', 'Nguyễn Thái Học', 'Trần Quốc Toản',
               'Thái Phiên', 'Lê Hồng Phong', 'Hoàng Văn Thụ',
               'Phạm Hồng Thái', 'Phạm Phú Thứ');

-- Kiểm tra kết quả bước 2
SELECT 'Bước 2 (tên đường):' as step,
       COUNT(*) as total,
       COUNT(max_speed) as has_speed,
       COUNT(*) FILTER (WHERE max_speed IS NULL) as still_null
FROM streets;


-- ─── BƯỚC 3: FILL NULL CÒN LẠI THEO HIGHWAY TYPE ───────────────────────────
-- Các đường vẫn còn NULL max_speed → gán theo tên loại đường OSM
-- Quy tắc ATGT Việt Nam (Thông tư 31/2019/TT-BGTVT)

UPDATE streets SET max_speed = 100
WHERE max_speed IS NULL
  AND name IN ('motorway', 'motorway_link', 'trunk', 'trunk_link');

UPDATE streets SET max_speed = 80
WHERE max_speed IS NULL
  AND name IN ('primary', 'primary_link');

UPDATE streets SET max_speed = 60
WHERE max_speed IS NULL
  AND name IN ('secondary', 'secondary_link');

UPDATE streets SET max_speed = 50
WHERE max_speed IS NULL
  AND name IN ('tertiary', 'tertiary_link', 'unclassified');

UPDATE streets SET max_speed = 40
WHERE max_speed IS NULL
  AND name IN ('residential', 'living_street', 'service');

-- Đường không rõ loại → mặc định 50 km/h
UPDATE streets SET max_speed = 50
WHERE max_speed IS NULL;

-- ─── BÁO CÁO KẾT QUẢ CUỐI ──────────────────────────────────────────────────
SELECT 'KẾT QUẢ CUỐI:' as label, max_speed, COUNT(*) as so_duong
FROM streets
GROUP BY max_speed
ORDER BY max_speed;

SELECT 'Tổng kết:' as label,
       COUNT(*) as tong_duong,
       COUNT(max_speed) as co_max_speed,
       COUNT(*) FILTER (WHERE max_speed IS NULL) as con_null
FROM streets;

COMMIT;
