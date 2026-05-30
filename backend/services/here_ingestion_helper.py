import os
import requests
import time
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
try:
    from scipy.spatial import cKDTree
except ImportError:
    pass

from models import Street, TrafficData
from config import settings

TZ_DANANG = timezone(timedelta(hours=7))

DISTRICT_BBOXES = {
    "Hải Châu"    : {"bbox": "108.19,16.04,108.24,16.08"},
    "Thanh Khê"   : {"bbox": "108.18,16.05,108.22,16.09"},
    "Sơn Trà"     : {"bbox": "108.21,16.05,108.27,16.12"},
    "Ngũ Hành Sơn": {"bbox": "108.22,15.98,108.30,16.05"},
    "Cẩm Lệ"     : {"bbox": "108.18,15.97,108.24,16.04"},
    "Liên Chiểu"  : {"bbox": "108.12,16.05,108.20,16.12"},
    "Hòa Vang"    : {"bbox": "107.90,15.85,108.20,16.08"},
}

def _normalize_speed(freeflow_kmh: float) -> int:
    """
    Chuẩn hóa tốc độ freeflow (km/h) về mức giới hạn gần nhất theo
    quy định ATGT Việt Nam: 20, 30, 40, 50, 60, 70, 80, 90, 100, 120.

    Ví dụ:  43 km/h → 40,  58 km/h → 60,  82 km/h → 80
    """
    thresholds = [20, 30, 40, 50, 60, 70, 80, 90, 100, 120]
    for t in thresholds:
        if freeflow_kmh <= t + 8:   # ngưỡng ±8 km/h
            return t
    return 120


def fetch_here_district(district: str, bbox: str, api_key: str) -> list:
    try:
        resp = requests.get(
            "https://data.traffic.hereapi.com/v7/flow",
            params={"in": f"bbox:{bbox}", "locationReferencing": "shape", "apiKey": api_key},
            timeout=30,
        )
        if resp.status_code != 200:
            return []
        results = resp.json().get("results", [])
        segments = []
        for item in results:
            flow = item.get("currentFlow", {})
            speed = flow.get("speed")
            if speed is None: continue
            
            shape = item.get("location", {}).get("shape", {})
            links = shape.get("links", [])
            if not links: continue
            points = links[0].get("points", [])
            if not points: continue
            
            mid_idx = len(points) // 2
            center_lat, center_lon = points[mid_idx].get("lat"), points[mid_idx].get("lng")
            
            if center_lat and center_lon:
                segments.append({
                    "lat": center_lat, "lon": center_lon,
                    "speed_kmh": round(speed * 3.6, 1),
                    "freeflow_kmh": round((flow.get("freeFlow") or 16.7) * 3.6, 1),
                    "jam_factor": flow.get("jamFactor", 0),
                    "confidence": flow.get("confidence", 0),
                })
        return segments
    except Exception as e:
        print("HERE fetch error:", str(e))
        return []

def sync_max_speed_from_here(db: Session) -> dict:
    """
    Cập nhật max_speed của TẤT CẢ đường trong DB từ freeflow HERE API.

    Khác với run_here_crawl (chỉ cập nhật khi chênh lệch > 15 km/h),
    hàm này LUÔN ghi đè max_speed = freeflow chuẩn hóa cho mọi đường match được.

    Quy trình:
      1. Gọi HERE Flow API cho 7 quận Đà Nẵng → lấy freeflow_kmh mỗi segment
      2. Dùng cKDTree match segment HERE → centroid đường trong DB (ngưỡng 500m)
      3. Chuẩn hóa freeflow về bội số quy định ATGT VN (20/30/40/50/60/70/80/100/120)
      4. UPDATE toàn bộ đường match được — KHÔNG kiểm tra chênh lệch

    Returns:
        dict với: streets_total, streets_updated, streets_skipped,
                  duration_seconds, timestamp, errors
    """
    started_at = datetime.now(TZ_DANANG)
    api_key = os.getenv("HERE_API_KEY", "zuF2Nv-k7xbJcG5lB1Row5R-N_kpi02_kovwuaqnm_Y")
    if not api_key:
        return {"error": "Missing HERE_API_KEY"}

    # ── 1. Gọi HERE API cho tất cả quận ───────────────────────────────────
    print("[sync_max_speed] Đang gọi HERE Flow API cho tất cả quận...")
    here_segments = []
    for district, data in DISTRICT_BBOXES.items():
        segs = fetch_here_district(district, data["bbox"], api_key)
        here_segments.extend(segs)
        print(f"  [{district}] → {len(segs)} segment(s)")
        time.sleep(0.5)

    if not here_segments:
        return {
            "error": "Không lấy được dữ liệu HERE",
            "streets_total": 0, "streets_updated": 0,
            "streets_skipped": 0, "duration_seconds": 0, "errors": []
        }

    print(f"[sync_max_speed] Tổng HERE segments: {len(here_segments)}")

    # ── 2. Xây dựng KDTree từ segments HERE ───────────────────────────────
    here_pts = [[s["lat"], s["lon"]] for s in here_segments]
    tree = cKDTree(here_pts)

    # ── 3. Lấy centroid tất cả đường từ DB ────────────────────────────────
    osm_rows = db.execute(text("""
        SELECT id, name, max_speed,
               ST_Y(ST_Centroid(geometry)) as lat,
               ST_X(ST_Centroid(geometry)) as lon
        FROM streets WHERE geometry IS NOT NULL
    """)).fetchall()

    if not osm_rows:
        return {
            "error": "Không có geometry trong DB",
            "streets_total": 0, "streets_updated": 0,
            "streets_skipped": 0, "duration_seconds": 0, "errors": []
        }

    osm_pts = [[r.lat, r.lon] for r in osm_rows]
    distances, indices = tree.query(osm_pts, k=1)

    # ── 4. UPDATE max_speed cho từng đường match được ──────────────────────
    updated = 0
    skipped = 0
    details = []   # log chi tiết từng đường

    for i, row in enumerate(osm_rows):
        dist = distances[i]
        if dist >= 0.005:  # > ~500m → không match
            skipped += 1
            continue

        hs = here_segments[indices[i]]
        freeflow = hs.get("freeflow_kmh")

        # Bỏ qua nếu freeflow ngoài khoảng hợp lệ
        if not freeflow or not (15 <= freeflow <= 130):
            skipped += 1
            continue

        normalized = _normalize_speed(freeflow)
        old_speed  = row.max_speed or 0

        db.execute(
            text("UPDATE streets SET max_speed = :spd WHERE id = :sid"),
            {"spd": normalized, "sid": row.id}
        )
        updated += 1
        details.append({
            "street_id"  : row.id,
            "street_name": row.name,
            "old_max_speed" : old_speed,
            "new_max_speed" : normalized,
            "freeflow_kmh"  : round(freeflow, 1),
            "dist_deg"      : round(dist, 5),
        })

    db.commit()

    duration = round((datetime.now(TZ_DANANG) - started_at).total_seconds(), 2)
    print(
        f"[sync_max_speed] Hoàn tất: {updated} đường cập nhật, "
        f"{skipped} bỏ qua — {duration}s"
    )

    return {
        "streets_total"   : len(osm_rows),
        "streets_updated" : updated,
        "streets_skipped" : skipped,
        "duration_seconds": duration,
        "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
        "details"         : details,
        "errors"          : [],
    }


def run_here_crawl(db: Session, started_at: datetime):
    api_key = os.getenv("HERE_API_KEY", "zuF2Nv-k7xbJcG5lB1Row5R-N_kpi02_kovwuaqnm_Y")
    if not api_key:
        return {"error": "Missing HERE_API_KEY"}
    
    here_segments = []
    for district, data in DISTRICT_BBOXES.items():
        segs = fetch_here_district(district, data["bbox"], api_key)
        here_segments.extend(segs)
        time.sleep(0.5)

    if not here_segments:
        return {"error": "Không lấy được dữ liệu HERE"}

    here_pts = [[s["lat"], s["lon"]] for s in here_segments]
    tree = cKDTree(here_pts)

    # Lấy tọa độ centroid các đường từ DB
    osm_query = db.execute(text("""
        SELECT id, ST_Y(ST_Centroid(geometry)) as lat, ST_X(ST_Centroid(geometry)) as lon, max_speed
        FROM streets WHERE geometry IS NOT NULL
    """)).fetchall()

    if not osm_query:
        return {"error": "Không có geometry trong DB"}

    osm_pts = [[r.lat, r.lon] for r in osm_query]
    distances, indices = tree.query(osm_pts, k=1)

    # ── Lấy danh sách sự cố đang hoạt động để ghi đè vận tốc ───────────────
    active_incidents = db.execute(text("""
        SELECT street_id, type 
        FROM incidents 
        WHERE is_active = TRUE
    """)).fetchall()
    
    # Chuyển thành set để check O(1)
    roadblocks = {r.street_id for r in active_incidents if r.type == "roadblock"}
    events     = {r.street_id for r in active_incidents if r.type in ("event", "accident")}

    records_to_insert = []
    streets_to_update_speed = []  # (street_id, new_max_speed)
    success_cnt = 0
    now = datetime.now(TZ_DANANG)

    for i, row in enumerate(osm_query):
        dist = distances[i]
        if dist < 0.005:  # ~500m
            hs = here_segments[indices[i]]
            speed = hs["speed_kmh"]
            freeflow = hs.get("freeflow_kmh")
            jam_factor = hs.get("jam_factor", 0.0)
            confidence = hs.get("confidence", 1.0)

            # ── Tự động cập nhật max_speed từ freeflow HERE ────────────────
            # Chỉ cập nhật nếu freeflow hợp lệ (15–120 km/h)
            # và chênh lệch đáng kể so với max_speed hiện tại (> 15 km/h)
            if freeflow and 15 <= freeflow <= 120:
                # Chuẩn hóa về bội số gần nhất của 10
                normalized = _normalize_speed(freeflow)
                current_max = row.max_speed or 0
                if current_max == 0 or abs(current_max - normalized) > 15:
                    streets_to_update_speed.append((row.id, normalized))

            # ── Ghi đè vận tốc đối với đường bị đóng (Roadblock) ─────────────────
            if row.id in roadblocks:
                speed = 0.0
                cong = 2
            # ── Ghi đè vận tốc đối với đường bị kẹt do sự kiện / tai nạn ──────────
            elif (row.id in events or jam_factor >= 8.0) and (speed >= 25.0 and confidence < 0.5):
                # Bị ùn tắc/chặn do sự kiện nhưng HERE trả về vận tốc cao ảo do fallback dữ liệu cũ
                # -> Cưỡng bức tốc độ về mức bò 5 km/h và gán mức đỏ (2)
                speed = 5.0
                cong = 2
            else:
                # Phân cấp tắc đường dùng jamFactor của HERE (0.0 -> 10.0)
                #   jam_factor < 4.0        -> 0 (Xanh - thông thoáng)
                #   4.0 <= jam_factor < 8.0 -> 1 (Vàng - ùn ứ)
                #   jam_factor >= 8.0       -> 2 (Đỏ - kẹt xe)
                if jam_factor >= 8.0:
                    cong = 2
                elif jam_factor >= 4.0:
                    cong = 1
                else:
                    cong = 0

            records_to_insert.append(TrafficData(
                street_id=row.id,
                segment_idx=0,
                timestamp=now,
                avg_speed=speed,
                free_flow_speed=freeflow,
                congestion_level=cong,
                source="here_bbox"
            ))
            success_cnt += 1

    # ── Cập nhật max_speed hàng loạt cho các đường cần điều chỉnh ─────────
    if streets_to_update_speed:
        for sid, new_speed in streets_to_update_speed:
            db.execute(
                text("UPDATE streets SET max_speed = :spd WHERE id = :sid"),
                {"spd": new_speed, "sid": sid}
            )
        print(f"[HERE] Đã cập nhật max_speed cho {len(streets_to_update_speed)} đường từ freeflow HERE")

    if records_to_insert:
        db.bulk_save_objects(records_to_insert)
        db.commit()

        # ── Refresh Materialized View sau khi commit ────────────────────────
        # CONCURRENTLY: không lock bảng → người dùng vẫn đọc được trong lúc refresh
        try:
            db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_traffic"))
            db.commit()
            print("[HERE] Đã refresh Materialized View latest_traffic")
        except Exception as e:
            print(f"[HERE] Cảnh báo: Không refresh được MV: {e}")

    return {
        "streets_total": len(osm_query),
        "streets_success": success_cnt,
        "records_saved": success_cnt,
        "quota_remaining": "N/A",
        "duration_seconds": (datetime.now(TZ_DANANG) - started_at).total_seconds(),
        "timestamp": started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
        "errors": []
    }



