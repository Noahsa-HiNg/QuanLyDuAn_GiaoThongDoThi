-- merge_streets_full.sql
-- Merge backup vào streets (UPDATE existing + INSERT new)
-- Chạy: psql -U myadmin -d qlda_dothithongminh -f /tmp/merge_streets_full.sql

BEGIN;

-- B1: Bảng tạm raw (text)
CREATE TEMP TABLE _bk_raw (
    id          INTEGER,
    name        TEXT,
    district_id INTEGER,
    geom_hex    TEXT,
    length_km   TEXT,
    max_speed   TEXT,
    is_one_way  TEXT
);

-- B2: Load TSV
COPY _bk_raw FROM '/tmp/streets_data_only.tsv'
    WITH (FORMAT text, DELIMITER E'\t', NULL '\N');

-- B3: Chuyển sang bảng typed với geometry thực (EWKB có SRID nhúng sẵn)
CREATE TEMP TABLE _bk AS
SELECT
    id,
    name,
    district_id,
    ST_GeomFromEWKB(decode(geom_hex, 'hex'))::geometry(LINESTRING,4326) AS geometry,
    NULLIF(length_km,  '')::FLOAT   AS length_km,
    NULLIF(max_speed,  '')::INTEGER AS max_speed,
    (is_one_way = 't')              AS is_one_way
FROM _bk_raw;

-- Kiểm tra
SELECT COUNT(*) AS backup_rows FROM _bk;

-- B4: UPDATE đường đã có
UPDATE streets s
SET
    name        = b.name,
    district_id = b.district_id,
    geometry    = b.geometry,
    length_km   = b.length_km,
    max_speed   = COALESCE(b.max_speed, s.max_speed),
    is_one_way  = b.is_one_way
FROM _bk b
WHERE s.id = b.id;

-- B5: INSERT đường mới chưa có
INSERT INTO streets (id, name, district_id, geometry, length_km, max_speed, is_one_way)
SELECT b.id, b.name, b.district_id, b.geometry, b.length_km, b.max_speed, b.is_one_way
FROM _bk b
LEFT JOIN streets s ON s.id = b.id
WHERE s.id IS NULL;

-- B6: Sync sequence auto-increment
SELECT setval('streets_id_seq', (SELECT MAX(id) FROM streets));

-- B7: Kết quả
SELECT
    (SELECT COUNT(*) FROM streets) AS total_streets_after,
    (SELECT COUNT(*) FROM _bk)     AS backup_count,
    (SELECT MAX(id) FROM streets)  AS max_id;

COMMIT;
