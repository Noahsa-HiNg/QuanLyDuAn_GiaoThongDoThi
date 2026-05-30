# backend/scripts/benchmark_query.py
import sys
import os
import time
from sqlalchemy import text

sys.path.insert(0, "/app")
from database import SessionLocal

def benchmark():
    db = SessionLocal()
    print("=== STARTING BENCHMARK ===")
    
    # 1. Đo SQL traffic thô trong 3 giờ (không lọc)
    t0 = time.time()
    try:
        res1 = db.execute(text("""
            SELECT COUNT(*) FROM traffic_data t
            WHERE t.timestamp >= NOW() - INTERVAL '3 hours'
        """)).fetchone()
        print(f"1. Total traffic records (3 hours): Count = {res1[0]}, Time = {time.time()-t0:.3f}s")
    except Exception as e:
        print(f"1. Failed: {e}")
        
    # 2. Đo SQL traffic thô trong 3 giờ (chỉ lấy segment_idx = 0)
    t0 = time.time()
    try:
        res2 = db.execute(text("""
            SELECT COUNT(*) FROM traffic_data t
            WHERE t.timestamp >= NOW() - INTERVAL '3 hours' AND t.segment_idx = 0
        """)).fetchone()
        print(f"2. Traffic records with segment_idx=0 (3 hours): Count = {res2[0]}, Time = {time.time()-t0:.3f}s")
    except Exception as e:
        print(f"2. Failed: {e}")

    # 3. Đo SQL group by theo street_id và timestamp trong 3 giờ
    t0 = time.time()
    try:
        res3 = db.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT t.street_id, t.timestamp
                FROM traffic_data t
                WHERE t.timestamp >= NOW() - INTERVAL '3 hours'
                GROUP BY t.street_id, t.timestamp
            ) as g
        """)).fetchone()
        print(f"3. Grouped unique (street_id, timestamp) (3 hours): Count = {res3[0]}, Time = {time.time()-t0:.3f}s")
    except Exception as e:
        print(f"3. Failed: {e}")

    # 4. Chạy thử query GROUP BY đầy đủ (3 giờ) xem thời gian chạy thực tế
    t0 = time.time()
    try:
        res4 = db.execute(text("""
            SELECT t.street_id as road_id, 
                   AVG(t.avg_speed) as speed, 
                   ROUND(AVG(t.congestion_level)) as congestion_level, 
                   t.timestamp as updated_at,
                   COALESCE(s.length_km, 1.0) as road_length,
                   COALESCE(d.name, '') as district,
                   COALESCE(w.temperature, 28.0) as weather_temp,
                   COALESCE(w.rain_1h_mm, 0.0) as weather_rain
            FROM traffic_data t
            JOIN streets s ON t.street_id = s.id
            LEFT JOIN districts d ON s.district_id = d.id
            LEFT JOIN weather_snapshots w ON w.id = (
                SELECT ws.id FROM weather_snapshots ws
                WHERE ws.timestamp >= NOW() - INTERVAL '3 hours'
                ORDER BY ABS(EXTRACT(EPOCH FROM (ws.timestamp - t.timestamp)))
                LIMIT 1
            )
            WHERE t.timestamp >= NOW() - INTERVAL '3 hours'
            GROUP BY t.street_id, t.timestamp, s.length_km, d.name, w.temperature, w.rain_1h_mm
            ORDER BY t.street_id, t.timestamp DESC
        """)).fetchall()
        print(f"4. Full Grouped query with weather: Count = {len(res4)}, Time = {time.time()-t0:.3f}s")
    except Exception as e:
        print(f"4. Failed: {e}")
        
    db.close()

if __name__ == "__main__":
    benchmark()
