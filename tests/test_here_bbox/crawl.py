"""
tests/test_here_bbox/crawl.py
==============================
Phương pháp 2: HERE Traffic Flow JSON Bbox
- Gọi HERE /v7/flow với bbox của từng quận (7 calls)
- Nhận về tất cả segment + speed + geometry trong vùng
- Spatial join với OSM streets (nếu connect được mapdb)
- Lưu kết quả vào results/here_results.json

Chạy: python tests/test_here_bbox/crawl.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

import json
import time
import asyncio
import aiohttp
import requests
from datetime import datetime
from pathlib import Path

# ─── ĐỌC KEY TỪ .ENV ────────────────────────────────────────────────────────
def _load_env_key(name: str) -> str:
    """Đọc một key từ .env file (không cần python-dotenv)."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{name}="):
                    return line.split("=", 1)[1].strip()
    return os.getenv(name, "")

HERE_API_KEY = _load_env_key("HERE_API_KEY")

# File output
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = RESULTS_DIR / "here_results.json"

# ─── BBOX TỪNG QUẬN ĐÀ NẴNG ─────────────────────────────────────────────────
DISTRICT_BBOXES = {
    "Hải Châu"    : {"bbox": "108.19,16.04,108.24,16.08", "center": (16.06, 108.215)},
    "Thanh Khê"   : {"bbox": "108.18,16.05,108.22,16.09", "center": (16.07, 108.20)},
    "Sơn Trà"     : {"bbox": "108.21,16.05,108.27,16.12", "center": (16.08, 108.24)},
    "Ngũ Hành Sơn": {"bbox": "108.22,15.98,108.30,16.05", "center": (16.01, 108.26)},
    "Cẩm Lệ"     : {"bbox": "108.18,15.97,108.24,16.04", "center": (16.00, 108.21)},
    "Liên Chiểu"  : {"bbox": "108.12,16.05,108.20,16.12", "center": (16.08, 108.16)},
    "Hòa Vang"    : {"bbox": "107.90,15.85,108.20,16.08", "center": (15.96, 108.05)},
}


# ─── HELPER: Tính độ lệch (offset) giữa HERE và OSM ─────────────────────────
def haversine_m(lat1, lon1, lat2, lon2) -> float:
    """Khoảng cách Haversine giữa 2 điểm (mét)."""
    R = 6_371_000
    import math
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ─── SPATIAL JOIN VỚI MAPDB ─────────────────────────────────────────────────
def try_spatial_join(segments: list) -> list:
    """
    Nếu kết nối được mapdb, thực hiện spatial join:
    HERE segment point → OSM street gần nhất (trong 50m).
    """
    try:
        from sqlalchemy import create_engine, text
        mapdb_url = os.getenv(
            "MAPDB_URL",
            "postgresql://myadmin:123456@localhost:5433/mapdb"
        )
        engine = create_engine(mapdb_url, connect_args={"connect_timeout": 5})

        with engine.connect() as conn:
            print("  ✅ Connect mapdb OK — bắt đầu spatial join...")
            matched = 0
            for seg in segments:
                lat = seg.get("center_lat")
                lon = seg.get("center_lon")
                if lat is None or lon is None:
                    continue

                row = conn.execute(text("""
                    SELECT
                        id,
                        name,
                        ST_Distance(
                            geometry::geography,
                            ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography
                        ) AS dist_m
                    FROM streets
                    WHERE ST_DWithin(
                        geometry::geography,
                        ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography,
                        50
                    )
                    ORDER BY dist_m
                    LIMIT 1
                """), {"lat": lat, "lon": lon}).fetchone()

                if row:
                    seg["matched_street_id"]   = row.id
                    seg["matched_street_name"] = row.name
                    seg["match_dist_m"]        = round(row.dist_m, 1)
                    seg["match_status"]        = "matched"
                    matched += 1
                else:
                    seg["matched_street_id"]   = None
                    seg["matched_street_name"] = None
                    seg["match_dist_m"]        = None
                    seg["match_status"]        = "no_match"

            print(f"  📍 Spatial join: {matched}/{len(segments)} matched")
            return segments, matched

    except Exception as e:
        print(f"  ⚠️  Không connect mapdb: {e} → Bỏ qua spatial join")
        for seg in segments:
            seg["match_status"] = "skipped_no_db"
        return segments, 0


# ─── HERE API CALL ───────────────────────────────────────────────────────────
def fetch_here_district(district: str, bbox: str, api_key: str) -> dict:
    """Gọi HERE Traffic Flow cho 1 quận."""
    t0 = time.time()
    try:
        resp = requests.get(
            "https://data.traffic.hereapi.com/v7/flow",
            params={
                "in"                 : f"bbox:{bbox}",
                "locationReferencing": "shape",
                "apiKey"             : api_key,
            },
            timeout=30,
        )
        elapsed = time.time() - t0

        if resp.status_code == 401:
            return {"district": district, "error": "Invalid API key", "elapsed_s": elapsed, "segments": []}
        if resp.status_code != 200:
            return {"district": district, "error": f"HTTP {resp.status_code}", "elapsed_s": elapsed, "segments": []}

        results = resp.json().get("results", [])
        segments = []
        for item in results:
            flow = item.get("currentFlow", {})
            speed = flow.get("speed")
            if speed is None:
                continue

            # Lấy full path từ shape → dùng cho PathLayer
            center_lat, center_lon = None, None
            path = []
            shape = item.get("location", {}).get("shape", {})
            links = shape.get("links", [])
            for link in links:
                for pt in link.get("points", []):
                    la, lo = pt.get("lat"), pt.get("lng")
                    if la is not None and lo is not None:
                        path.append([round(lo, 6), round(la, 6)])

            if path:
                mid = path[len(path) // 2]
                center_lon, center_lat = mid[0], mid[1]
            elif not path:
                # fallback nếu không có shape
                path = None

            # HERE v7 trả về speed/freeFlow bằng m/s → nhân 3.6 để ra km/h
            freeflow_ms  = flow.get("freeFlow") or 16.7   # default ~60 km/h
            speed_ms     = speed
            speed_kmh    = round(speed_ms  * 3.6, 1)
            freeflow_kmh = round(freeflow_ms * 3.6, 1)
            ratio    = speed_ms / freeflow_ms
            congestion = 0 if ratio >= 0.70 else (1 if ratio >= 0.40 else 2)

            segments.append({
                "district"        : district,
                "center_lat"      : center_lat,
                "center_lon"      : center_lon,
                "path"            : path,          # ← full geometry
                "speed_kmh"       : speed_kmh,
                "freeflow_kmh"    : freeflow_kmh,
                "jam_factor"      : flow.get("jamFactor", 0),
                "confidence"      : flow.get("confidence", 0),
                "congestion_level": congestion,
                "congestion_label": {0: "Thong thoang", 1: "Cham", 2: "Tac nghen"}[congestion],
                "source"          : "here_bbox",
                "timestamp"       : datetime.now().isoformat(),
            })

        return {
            "district" : district,
            "bbox"     : bbox,
            "elapsed_s": round(elapsed, 3),
            "segments" : segments,
            "count"    : len(segments),
            "error"    : None,
        }

    except Exception as e:
        return {"district": district, "error": str(e), "elapsed_s": time.time()-t0, "segments": []}


# ─── MAIN CRAWL ───────────────────────────────────────────────────────────────
def crawl(api_key: str = None):
    key = api_key or HERE_API_KEY

    print("=" * 60)
    print("  PHƯƠNG PHÁP 2: HERE Traffic Flow JSON Bbox")
    print("=" * 60)

    if not key:
        print()
        print("  ⚠️  HERE_API_KEY chưa được cấu hình!")
        print("  📌 Cách lấy key MIỄN PHÍ:")
        print("     1. Truy cập: https://developer.here.com/")
        print("     2. Đăng ký tài khoản → Create project")
        print("     3. Generate API Key (loại: REST)")
        print("     4. Thêm vào .env: HERE_API_KEY=your_key_here")
        print()
        print("  ⏩ Chạy với demo data (không gọi API thật)...")
        print()
        key = "DEMO"  # Sẽ fail gracefully

    print(f"  Districts: {len(DISTRICT_BBOXES)} quận")
    print(f"  API calls: {len(DISTRICT_BBOXES)} (song song)")
    print()

    t_start = time.time()
    district_results = []
    all_segments = []

    # Gọi tuần tự (asyncio optional)
    for district, cfg in DISTRICT_BBOXES.items():
        print(f"  📡 Đang cào {district}...", end=" ", flush=True)
        result = fetch_here_district(district, cfg["bbox"], key)

        if result.get("error"):
            print(f"❌ {result['error']}")
        else:
            cnt = result["count"]
            avg = (sum(s["speed_kmh"] for s in result["segments"]) / cnt) if cnt else 0
            print(f"✅ {cnt} segments | avg {avg:.1f} km/h | {result['elapsed_s']:.2f}s")
            all_segments.extend(result["segments"])

        district_results.append(result)

    t_after_api = time.time()
    total_api_time = t_after_api - t_start

    # Spatial join
    print()
    print(f"  🔗 Thực hiện Spatial Join ({len(all_segments)} segments)...")
    all_segments, matched_count = try_spatial_join(all_segments)

    total_time = time.time() - t_start

    # ─── Thống kê ────────────────────────────────────────────────────────────
    success = len(all_segments)
    avg_speed = sum(s["speed_kmh"] for s in all_segments) / success if success else 0
    cong_dist = {0: 0, 1: 0, 2: 0}
    for s in all_segments:
        cong_dist[s["congestion_level"]] += 1

    # Tính mismatch rate
    match_possible = sum(1 for s in all_segments if s.get("match_status") != "skipped_no_db")
    matched = sum(1 for s in all_segments if s.get("match_status") == "matched")
    mismatch_rate = round((1 - matched / match_possible) * 100, 1) if match_possible else "N/A (no DB)"

    summary = {
        "method"            : "here_bbox_flow",
        "crawl_time"        : datetime.now().isoformat(),
        "total_districts"   : len(DISTRICT_BBOXES),
        "api_calls"         : len(DISTRICT_BBOXES),
        "total_segments"    : success,
        "spatial_matched"   : matched_count,
        "mismatch_rate_pct" : mismatch_rate,
        "total_time_s"      : round(total_time, 2),
        "api_time_s"        : round(total_api_time, 2),
        "join_time_s"       : round(total_time - total_api_time, 2),
        "avg_speed_kmh"     : round(avg_speed, 1),
        "congestion_dist"   : {
            "smooth (🟢)": cong_dist[0],
            "slow (🟡)"  : cong_dist[1],
            "congested (🔴)": cong_dist[2],
        },
        "district_results"  : [
            {k: v for k, v in d.items() if k != "segments"} for d in district_results
        ],
        "segments": all_segments,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 60)
    print(f"  ✅ HOÀN TẤT")
    print(f"     Segments tìm thấy: {success}")
    print(f"     Spatial matched   : {matched_count} ({mismatch_rate}% miss)")
    print(f"     Thời gian API     : {total_api_time:.1f}s")
    print(f"     Tổng thời gian    : {total_time:.1f}s")
    print(f"     TB tốc độ         : {avg_speed:.1f} km/h")
    print(f"     Phân bố           : 🟢{cong_dist[0]} 🟡{cong_dist[1]} 🔴{cong_dist[2]}")
    print(f"     Đã lưu            : {OUTPUT_FILE}")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    crawl()
