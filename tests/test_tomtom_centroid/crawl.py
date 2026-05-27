"""
tests/test_tomtom_centroid/crawl.py
====================================
Phương pháp 1: TomTom Point-based (OSM Centroid)
- Lấy centroid của từng đường từ street_district_dump.sql
- Gọi TomTom flowSegmentData tại centroid đó
- Lưu kết quả vào results/tomtom_results.json

Chạy: python tests/test_tomtom_centroid/crawl.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import json
import time
import math
import requests
from datetime import datetime
from pathlib import Path

# ─── CẤU HÌNH ────────────────────────────────────────────────────────────────
# Lấy từ .env hoặc điền thẳng vào
TOMTOM_KEYS = os.getenv(
    "TOMTOM_API_KEYS",
    "ixWGJspbZGL07g4DUYYpznMJUn9nXPvC"
).split(",")

# Giới hạn số đường cào (None = tất cả)
MAX_STREETS = 200   # Tăng lên để cào nhiều hơn, đặt None để cào hết

# File output
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = RESULTS_DIR / "tomtom_results.json"

# ─── STREETS TỪ MAPDB (hardcode bbox + centroid từ SQL dump) ─────────────────
# Vì không connect trực tiếp mapdb trong test, ta dùng centroid tính sẵn
# Trong production: query từ mapdb qua SQLAlchemy

# Tọa độ các quận Đà Nẵng để generate grid sampling
DANANG_DISTRICTS = {
    "Hải Châu"    : {"bbox": [108.19, 16.04, 108.24, 16.08], "max_speed": 50},
    "Thanh Khê"   : {"bbox": [108.18, 16.05, 108.22, 16.09], "max_speed": 50},
    "Sơn Trà"     : {"bbox": [108.21, 16.05, 108.27, 16.12], "max_speed": 60},
    "Ngũ Hành Sơn": {"bbox": [108.22, 15.98, 108.30, 16.05], "max_speed": 60},
    "Cẩm Lệ"     : {"bbox": [108.18, 15.97, 108.24, 16.04], "max_speed": 60},
    "Liên Chiểu"  : {"bbox": [108.12, 16.05, 108.20, 16.12], "max_speed": 60},
    "Hòa Vang"    : {"bbox": [107.90, 15.85, 108.20, 16.08], "max_speed": 80},
}

# Thử kết nối mapdb nếu có
def try_get_streets_from_db():
    """Lấy danh sách đường từ mapdb nếu có thể connect."""
    try:
        from sqlalchemy import create_engine, text
        mapdb_url = os.getenv(
            "MAPDB_URL",
            "postgresql://myadmin:123456@localhost:5433/mapdb"
        )
        engine = create_engine(mapdb_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    id,
                    COALESCE(name, 'unnamed_' || id::text) AS name,
                    COALESCE(max_speed, 50) AS max_speed,
                    district_id,
                    ST_Y(ST_Centroid(geometry)) AS lat,
                    ST_X(ST_Centroid(geometry)) AS lon
                FROM streets
                WHERE geometry IS NOT NULL
                ORDER BY
                    CASE WHEN name IS NOT NULL THEN 0 ELSE 1 END,
                    id
                LIMIT :lim
            """), {"lim": MAX_STREETS or 99999}).fetchall()
            streets = [dict(r._mapping) for r in rows]
            print(f"✅ Connect mapdb OK — {len(streets)} đường")
            return streets
    except Exception as e:
        print(f"⚠️  Không connect được mapdb: {e}")
        print("   → Dùng grid sampling thay thế")
        return None


def generate_grid_streets(points_per_district: int = 30) -> list:
    """
    Fallback: tạo lưới điểm đều nhau trong bbox mỗi quận.
    Dùng khi không connect được mapdb.
    """
    streets = []
    sid = 1
    for district, cfg in DANANG_DISTRICTS.items():
        min_lon, min_lat, max_lon, max_lat = cfg["bbox"]
        step = int(math.sqrt(points_per_district))

        for i in range(step):
            for j in range(step):
                lat = min_lat + (max_lat - min_lat) * i / (step - 1)
                lon = min_lon + (max_lon - min_lon) * j / (step - 1)
                streets.append({
                    "id"       : sid,
                    "name"     : f"{district}_grid_{i}_{j}",
                    "district" : district,
                    "lat"      : round(lat, 6),
                    "lon"      : round(lon, 6),
                    "max_speed": cfg["max_speed"],
                })
                sid += 1

    if MAX_STREETS:
        streets = streets[:MAX_STREETS]
    return streets


# ─── QUOTA KEY ROTATION ───────────────────────────────────────────────────────
_key_idx = 0
_key_usage = {k: 0 for k in TOMTOM_KEYS}
DAILY_LIMIT = 2400

def get_next_key() -> str | None:
    global _key_idx
    for _ in range(len(TOMTOM_KEYS)):
        key = TOMTOM_KEYS[_key_idx % len(TOMTOM_KEYS)]
        if _key_usage[key] < DAILY_LIMIT:
            _key_usage[key] += 1
            return key
        _key_idx += 1
    return None  # Tất cả key hết quota


# ─── TOMTOM API CALL ──────────────────────────────────────────────────────────
def fetch_tomtom_speed(lat: float, lon: float) -> dict | None:
    """Gọi TomTom Flow Segment Data tại 1 điểm."""
    api_key = get_next_key()
    if not api_key:
        print("⛔ Tất cả TomTom key hết quota!")
        return None

    url = (
        f"https://api.tomtom.com/traffic/services/4/flowSegmentData"
        f"/absolute/10/json"
        f"?point={lat},{lon}&key={api_key}&unit=KMPH"
    )
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 429:
            print(f"  ⛔ 429 key={api_key[:8]}")
            _key_usage[api_key] = DAILY_LIMIT  # Đánh dấu hết
            return None
        if resp.status_code != 200:
            return None

        data = resp.json().get("flowSegmentData", {})
        speed    = data.get("currentSpeed")
        freeflow = data.get("freeFlowSpeed")
        if speed is None:
            return None

        return {
            "speed"    : speed,
            "freeflow" : freeflow,
            "source"   : "tomtom",
        }
    except Exception as e:
        print(f"  ⚠️  {e}")
        return None


def calc_congestion(speed: float, freeflow: float, max_speed: int) -> int:
    ref = freeflow or max_speed or 50
    ratio = speed / ref
    return 0 if ratio >= 0.70 else (1 if ratio >= 0.40 else 2)


# ─── MAIN CRAWL ───────────────────────────────────────────────────────────────
def crawl():
    print("=" * 60)
    print("  PHƯƠNG PHÁP 1: TomTom Point (OSM Centroid)")
    print("=" * 60)
    print(f"  Keys: {len(TOMTOM_KEYS)} | Quota/key: {DAILY_LIMIT} req/ngày")
    print(f"  Tổng quota: {len(TOMTOM_KEYS) * DAILY_LIMIT} req")
    print()

    # Lấy danh sách đường
    streets = try_get_streets_from_db()
    if streets is None:
        streets = generate_grid_streets(points_per_district=30)
        source_type = "grid_sampling"
    else:
        source_type = "mapdb_centroid"

    total = len(streets)
    print(f"📍 Chuẩn bị cào {total} đường ({source_type})")
    print(f"   Ước tính thời gian: ~{total * 0.4:.0f}s ({total * 0.4 / 60:.1f} phút)")
    print()

    results   = []
    errors    = []
    t_start   = time.time()
    t_api_sum = 0.0

    for i, street in enumerate(streets, 1):
        lat = street.get("lat") or street.get("lat")
        lon = street.get("lon") or street.get("lon")

        if lat is None or lon is None:
            errors.append({"street": street.get("name"), "reason": "no_coords"})
            continue

        t0 = time.time()
        data = fetch_tomtom_speed(lat, lon)
        elapsed = time.time() - t0
        t_api_sum += elapsed

        if data is None:
            errors.append({"street": street.get("name"), "reason": "api_fail"})
            if i % 10 == 0:
                print(f"  [{i:4d}/{total}] ❌ {street.get('name', 'N/A')}")
            continue

        speed      = data["speed"]
        freeflow   = data.get("freeflow") or street.get("max_speed", 50)
        congestion = calc_congestion(speed, freeflow, street.get("max_speed", 50))
        label      = {0: "🟢 Thông", 1: "🟡 Chậm", 2: "🔴 Tắc"}[congestion]

        results.append({
            "street_id"       : street.get("id"),
            "street_name"     : street.get("name"),
            "district"        : street.get("district", street.get("district_id")),
            "lat"             : lat,
            "lon"             : lon,
            "speed_kmh"       : speed,
            "freeflow_kmh"    : freeflow,
            "congestion_level": congestion,
            "congestion_label": label,
            "api_elapsed_ms"  : round(elapsed * 1000, 1),
            "source"          : "tomtom_point",
            "timestamp"       : datetime.now().isoformat(),
        })

        if i % 10 == 0 or i == total:
            pct = i / total * 100
            avg_ms = t_api_sum / i * 1000
            print(f"  [{i:4d}/{total}] {pct:5.1f}% | {label} {speed:5.1f} km/h"
                  f" | avg {avg_ms:.0f}ms/call | {street.get('name', 'N/A')[:30]}")

        time.sleep(0.35)  # ~2.8 req/s, an toàn

    # ─── Thống kê ────────────────────────────────────────────────────────────
    total_time = time.time() - t_start
    success    = len(results)
    avg_speed  = sum(r["speed_kmh"] for r in results) / success if success else 0
    cong_dist  = {0: 0, 1: 0, 2: 0}
    for r in results:
        cong_dist[r["congestion_level"]] += 1

    summary = {
        "method"         : "tomtom_point_osm_centroid",
        "source_type"    : source_type,
        "crawl_time"     : datetime.now().isoformat(),
        "total_streets"  : total,
        "success"        : success,
        "errors"         : len(errors),
        "success_rate_pct": round(success / total * 100, 1) if total else 0,
        "total_time_s"   : round(total_time, 2),
        "avg_time_per_call_ms": round(t_api_sum / max(success, 1) * 1000, 1),
        "api_calls_made" : success,
        "avg_speed_kmh"  : round(avg_speed, 1),
        "congestion_dist": {
            "smooth (🟢)": cong_dist[0],
            "slow (🟡)"  : cong_dist[1],
            "congested (🔴)": cong_dist[2],
        },
        "results": results,
        "errors_detail": errors[:20],   # Chỉ lưu 20 lỗi đầu
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print(f"  ✅ HOÀN TẤT")
    print(f"     Thành công : {success}/{total} ({summary['success_rate_pct']}%)")
    print(f"     Thời gian  : {total_time:.1f}s ({total_time/60:.1f} phút)")
    print(f"     TB tốc độ  : {avg_speed:.1f} km/h")
    print(f"     Phân bố    : 🟢{cong_dist[0]} 🟡{cong_dist[1]} 🔴{cong_dist[2]}")
    print(f"     Đã lưu     : {OUTPUT_FILE}")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    crawl()
