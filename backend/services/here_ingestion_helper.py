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

    records_to_insert = []
    success_cnt = 0
    now = datetime.now(TZ_DANANG)

    for i, row in enumerate(osm_query):
        dist = distances[i]
        if dist < 0.005:  # ~500m
            hs = here_segments[indices[i]]
            speed = hs["speed_kmh"]
            freeflow = hs.get("freeflow_kmh")
            # Dùng freeflow làm tốc độ giới hạn mặc định nếu max_speed rỗng
            max_spd = row.max_speed or freeflow or 50
            ratio = speed / max_spd if max_spd > 0 else 0
            if ratio >= 0.70: cong = 0
            elif ratio >= 0.40: cong = 1
            else: cong = 2

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

    if records_to_insert:
        db.bulk_save_objects(records_to_insert)
        db.commit()

    return {
        "streets_total": len(osm_query),
        "streets_success": success_cnt,
        "records_saved": success_cnt,
        "quota_remaining": "N/A",
        "duration_seconds": (datetime.now(TZ_DANANG) - started_at).total_seconds(),
        "timestamp": started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
        "errors": []
    }
