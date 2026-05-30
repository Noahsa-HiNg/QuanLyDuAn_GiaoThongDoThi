-- add_routing_indexes.sql
-- Thêm 2 index để tăng tốc query build graph A*

-- Index 1: (street_id, timestamp DESC) trên traffic_data
-- Giúp query DISTINCT ON dùng Index Scan thay vì full table sort
CREATE INDEX IF NOT EXISTS idx_traffic_street_time_desc
    ON traffic_data (street_id, timestamp DESC);

-- Index 2: (name) trên streets
-- Giúp tăng tốc JOIN + ORDER BY s.name trong query routing
CREATE INDEX IF NOT EXISTS idx_streets_name
    ON streets (name);
