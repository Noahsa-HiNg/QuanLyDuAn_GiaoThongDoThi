-- ============================================================
-- merge_streets.sql
-- Merge dữ liệu từ backup vào bảng streets hiện tại
-- Chiến lược: INSERT đường mới + UPDATE geometry/length/speed/oneway
--             cho đường đã có (giữ nguyên traffic_data, incidents,...)
-- ============================================================

BEGIN;

-- Bước 1: Tạo bảng tạm để load toàn bộ backup vào
DROP TABLE IF EXISTS _streets_backup;
CREATE TEMP TABLE _streets_backup (
    id          INTEGER,
    name        TEXT,
    district_id INTEGER,
    geometry    geometry(LINESTRING, 4326),
    length_km   FLOAT,
    max_speed   INTEGER,
    is_one_way  BOOLEAN
);

-- Bước 2: Load dữ liệu từ backup (chỉ phần streets, bỏ districts)
\copy _streets_backup (id, name, district_id, geometry, length_km, max_speed, is_one_way) FROM '/backup/load_streets_districts.sql' WITH (FORMAT text, DELIMITER E'\t', NULL '\N', HEADER false);

-- Bước 3: UPDATE các đường đã tồn tại (khớp theo id)
UPDATE streets s
SET
    name        = b.name,
    district_id = b.district_id,
    geometry    = b.geometry,
    length_km   = b.length_km,
    max_speed   = COALESCE(b.max_speed, s.max_speed),
    is_one_way  = b.is_one_way
FROM _streets_backup b
WHERE s.id = b.id;

-- Bước 4: INSERT các đường mới (có trong backup nhưng chưa có trong bảng)
INSERT INTO streets (id, name, district_id, geometry, length_km, max_speed, is_one_way)
SELECT b.id, b.name, b.district_id, b.geometry, b.length_km, b.max_speed, b.is_one_way
FROM _streets_backup b
WHERE NOT EXISTS (
    SELECT 1 FROM streets s WHERE s.id = b.id
);

-- Bước 5: Đồng bộ sequence ID để INSERT sau này không bị conflict
SELECT setval('streets_id_seq', (SELECT MAX(id) FROM streets));

-- Bước 6: Thống kê kết quả
SELECT
    (SELECT COUNT(*) FROM streets)            AS total_streets,
    (SELECT COUNT(*) FROM _streets_backup)    AS backup_streets,
    (SELECT MAX(id) FROM streets)             AS max_id;

DROP TABLE IF EXISTS _streets_backup;

COMMIT;
