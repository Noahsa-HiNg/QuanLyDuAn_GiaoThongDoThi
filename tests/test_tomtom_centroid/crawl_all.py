"""
tests/test_tomtom_centroid/crawl_all.py
=========================================
Cào TOÀN BỘ đường Đà Nẵng — TomTom Point (OSM Centroid)

Chiến lược:
  1. Parse SQL dump → lấy centroid từng đường (không cần DB)
  2. Gom nhóm theo tên → 1 tên = 1 điểm đại diện (giảm ~72,742 → ~3,588)
  3. Async với 7 TomTom key song song → ~2-3 phút cho toàn bộ
  4. Lưu results/all_streets_results.json

Chạy:
  python tests/test_tomtom_centroid/crawl_all.py
  python tests/test_tomtom_centroid/crawl_all.py --limit 500
  python tests/test_tomtom_centroid/crawl_all.py --no-dedup   (cào từng segment)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import time
import struct
import binascii
import asyncio
import aiohttp
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ─── PATHS ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent.parent   # Project root
SQL_DUMP    = BASE_DIR / "street_district_dump.sql"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = RESULTS_DIR / "all_streets_results.json"
CACHE_FILE  = RESULTS_DIR / "streets_cache.json"    # Cache tọa độ đã parse

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TOMTOM_KEYS = os.getenv(
    "TOMTOM_API_KEYS",
    "ixWGJspbZGL07g4DUYYpznMJUn9nXPvC"
).split(",")

DAILY_LIMIT   = 2400          # req/key/ngày
MAX_CONCURRENT = len(TOMTOM_KEYS)  # Số yêu cầu song song = số key
DELAY_PER_KEY  = 0.5          # Delay giữa các call trên cùng 1 key (giây)


# ─── DISTRICT MAP ────────────────────────────────────────────────────────────
DISTRICT_NAMES = {
    1: "Cẩm Lệ",
    2: "Hải Châu",
    3: "Hòa Vang",
    4: "Liên Chiểu",
    5: "Ngũ Hành Sơn",
    6: "Sơn Trà",
    7: "Thanh Khê",
    8: "Hoàng Sa",
}


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 1: PARSE SQL DUMP → CENTROID (không cần psycopg2 / shapely)
# ════════════════════════════════════════════════════════════════════════════

def ewkb_hex_to_geometry(ewkb_hex: str) -> dict | None:
    """
    Chuyển EWKB hex string → dict với centroid và full path coordinates.
    Trả về: {"lat": float, "lon": float, "path": [[lon, lat], ...]}
    """
    try:
        raw = binascii.unhexlify(ewkb_hex)
        idx = 0

        byte_order = raw[idx]; idx += 1
        endian = "<" if byte_order == 1 else ">"

        geom_type = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
        has_srid  = (geom_type & 0x20000000) != 0
        base_type = geom_type & 0x0fffffff

        if base_type not in (2, 5):
            return None

        if has_srid:
            idx += 4

        all_points = []   # [[lon, lat], ...]

        if base_type == 2:  # LineString
            num_pts = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
            for _ in range(num_pts):
                lon = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                lat = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                all_points.append([round(lon, 7), round(lat, 7)])

        else:  # MultiLineString
            num_lines = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
            for _ in range(num_lines):
                idx += 1  # sub byte-order
                sub_type = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
                if sub_type & 0x20000000:
                    idx += 4
                num_pts = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
                for _ in range(num_pts):
                    lon = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                    lat = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                    all_points.append([round(lon, 7), round(lat, 7)])

        if not all_points:
            return None

        # Centroid = trung bình tất cả điểm
        avg_lon = sum(p[0] for p in all_points) / len(all_points)
        avg_lat = sum(p[1] for p in all_points) / len(all_points)

        # Giảm độ chi tiết nếu quá nhiều điểm (giữ tối đa 30 điểm/đường)
        path = all_points
        if len(path) > 30:
            step = len(path) // 30
            path = path[::step]
            if path[-1] != all_points[-1]:
                path.append(all_points[-1])  # Đảm bảo giữ điểm cuối

        return {
            "lat" : round(avg_lat, 7),
            "lon" : round(avg_lon, 7),
            "path": path,
        }

    except Exception:
        return None


def parse_sql_dump(sql_file: Path, dedup_by_name: bool = True) -> list[dict]:
    """
    Parse street_district_dump.sql → list of {id, name, district_id, lat, lon, ...}

    Tìm section:  COPY public.streets (id, name, district_id, geometry, ...) FROM stdin;
    Đọc từng dòng tab-separated cho đến dấu \\.
    """
    print(f"📂 Đang parse SQL dump: {sql_file}")
    print(f"   Kích thước: {sql_file.stat().st_size / 1_000_000:.1f} MB")

    streets_raw = []   # Tất cả segments
    in_streets  = False
    col_order   = []   # Thứ tự cột trong COPY statement

    with open(sql_file, "r", encoding="utf-8", errors="ignore") as f:
        for line_no, line in enumerate(f, 1):
            line = line.rstrip("\n")

            # Tìm COPY statement cho bảng streets
            if not in_streets:
                if "COPY public.streets" in line and "FROM stdin" in line:
                    # Parse tên cột: COPY public.streets (id, name, ...) FROM stdin;
                    start = line.find("(") + 1
                    end   = line.find(")")
                    if start > 0 and end > start:
                        col_order = [c.strip() for c in line[start:end].split(",")]
                    in_streets = True
                    print(f"   Tìm thấy COPY streets tại dòng {line_no}")
                    print(f"   Thứ tự cột: {col_order}")
                continue

            # Kết thúc COPY block
            if line.strip() == "\\.":
                in_streets = False
                print(f"   Đã đọc {len(streets_raw)} segments")
                break

            # Parse dòng dữ liệu tab-separated
            parts = line.split("\t")
            if len(parts) < len(col_order):
                continue

            row = dict(zip(col_order, parts))
            geom_hex = row.get("geometry", "")

            if not geom_hex or geom_hex == "\\N":
                continue

            # Parse WKB → geometry (centroid + full path)
            geom = ewkb_hex_to_geometry(geom_hex)
            if geom is None:
                continue

            lat, lon = geom["lat"], geom["lon"]
            path     = geom["path"]

            # Kiểm tra tọa độ hợp lệ (trong bbox Đà Nẵng)
            if not (15.5 <= lat <= 16.5 and 107.5 <= lon <= 109.0):
                continue

            streets_raw.append({
                "id"         : int(row.get("id", 0)),
                "name"       : row.get("name") if row.get("name") != "\\N" else None,
                "district_id": int(row.get("district_id", 0)) if row.get("district_id", "\\N") != "\\N" else 0,
                "district"   : DISTRICT_NAMES.get(int(row.get("district_id", 0)) if row.get("district_id", "\\N") != "\\N" else 0, "N/A"),
                "lat"        : lat,
                "lon"        : lon,
                "path"       : path,      # ← Full LineString coordinates
                "length_km"  : float(row["length_km"]) if row.get("length_km", "\\N") != "\\N" else 0,
                "max_speed"  : int(row["max_speed"]) if row.get("max_speed", "\\N") != "\\N" else 50,
                "is_one_way" : row.get("is_one_way", "f") == "t",
            })

    if not streets_raw:
        raise ValueError("Không tìm thấy dữ liệu streets trong SQL dump!")

    print(f"\n✅ Parse xong: {len(streets_raw):,} segments tổng")

    if dedup_by_name:
        # Gom nhóm theo tên — 1 tên = centroid trung bình tất cả segments
        named   = defaultdict(list)
        unnamed = []

        for s in streets_raw:
            if s["name"]:
                named[s["name"]].append(s)
            else:
                unnamed.append(s)

        deduped = []
        for name, segs in named.items():
            avg_lat  = sum(s["lat"] for s in segs) / len(segs)
            avg_lon  = sum(s["lon"] for s in segs) / len(segs)
            # Gom tất cả path points của cùng tên đường
            all_pts  = []
            for s in segs:
                all_pts.extend(s.get("path", [[s["lon"], s["lat"]]]))
            rep = segs[0]
            deduped.append({
                "id"              : rep["id"],
                "name"            : name,
                "district_id"     : rep["district_id"],
                "district"        : rep["district"],
                "lat"             : round(avg_lat, 7),
                "lon"             : round(avg_lon, 7),
                "path"            : all_pts,   # ← Full merged path
                "max_speed"       : rep["max_speed"],
                "segment_count"   : len(segs),
                "total_length_km" : round(sum(s["length_km"] for s in segs), 2),
            })

        print(f"   ├─ Đường có tên : {len(deduped):,} tên duy nhất (từ {len(streets_raw)-len(unnamed):,} segments)")
        print(f"   └─ Đường vô danh: {len(unnamed):,} segments (bỏ qua)")
        return sorted(deduped, key=lambda x: x.get("total_length_km", 0), reverse=True)
    else:
        print(f"   Trả về toàn bộ {len(streets_raw):,} segments")
        return streets_raw


def load_or_parse_streets(dedup: bool = True) -> list[dict]:
    """Dùng cache nếu đã parse rồi, không parse lại."""
    cache_key = "deduped" if dedup else "full"
    cache = {}

    if CACHE_FILE.exists():
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)
        if cache_key in cache:
            streets = cache[cache_key]
            print(f"📦 Dùng cache: {len(streets):,} {'tên' if dedup else 'segments'} (từ {CACHE_FILE.name})")
            return streets

    # Parse SQL dump
    streets = parse_sql_dump(SQL_DUMP, dedup_by_name=dedup)

    # Lưu cache
    cache[cache_key] = streets
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    print(f"💾 Đã cache vào {CACHE_FILE.name}")

    return streets


# ════════════════════════════════════════════════════════════════════════════
# BƯỚC 2: ASYNC TOMTOM CRAWL VỚI 7 KEY SONG SONG
# ════════════════════════════════════════════════════════════════════════════

class KeyPool:
    """Round-robin key rotation với giới hạn quota."""

    def __init__(self, keys: list[str], daily_limit: int):
        self.keys  = keys
        self.limit = daily_limit
        self.usage = {k: 0 for k in keys}
        self.locks = {k: asyncio.Semaphore(1) for k in keys}  # 1 req/key/time
        self._idx  = 0
        self._lock = asyncio.Lock()

    async def get_key(self) -> str | None:
        """Lấy key tiếp theo có quota còn."""
        async with self._lock:
            for _ in range(len(self.keys)):
                key = self.keys[self._idx % len(self.keys)]
                self._idx += 1
                if self.usage[key] < self.limit:
                    self.usage[key] += 1
                    return key
            return None  # Tất cả key hết quota

    def remaining(self) -> int:
        return sum(max(0, self.limit - u) for u in self.usage.values())

    def report(self) -> str:
        return " | ".join(f"k{i+1}:{u}" for i, (_, u) in enumerate(self.usage.items()))


async def fetch_one(
    session : aiohttp.ClientSession,
    key_pool: KeyPool,
    street  : dict,
    semaphore: asyncio.Semaphore,
    stats   : dict,
) -> dict | None:
    """Fetch TomTom speed cho 1 đường (async)."""
    async with semaphore:   # Giới hạn concurrent requests
        api_key = await key_pool.get_key()
        if not api_key:
            stats["quota_exhausted"] += 1
            return None

        url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData"
            f"/absolute/10/json"
        )
        params = {
            "point": f"{street['lat']},{street['lon']}",
            "key"  : api_key,
            "unit" : "KMPH",
        }

        t0 = time.time()
        try:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                elapsed = (time.time() - t0) * 1000  # ms

                if resp.status == 429:
                    key_pool.usage[api_key] = key_pool.limit
                    stats["rate_limited"] += 1
                    return None

                if resp.status != 200:
                    stats["api_errors"] += 1
                    return None

                data = (await resp.json()).get("flowSegmentData", {})
                speed    = data.get("currentSpeed")
                freeflow = data.get("freeFlowSpeed")

                if speed is None:
                    stats["no_data"] += 1
                    return None

                ref = freeflow or street.get("max_speed") or 50
                ratio = speed / ref
                congestion = 0 if ratio >= 0.70 else (1 if ratio >= 0.40 else 2)

                stats["success"] += 1
                return {
                    "street_id"         : street["id"],
                    "street_name"       : street.get("name"),
                    "district"          : street.get("district"),
                    "district_id"       : street.get("district_id"),
                    "lat"               : street["lat"],
                    "lon"               : street["lon"],
                    "path"              : street.get("path", [[street["lon"], street["lat"]]]),
                    "max_speed"         : street.get("max_speed"),
                    "segment_count"     : street.get("segment_count", 1),
                    "total_length_km"   : street.get("total_length_km", street.get("length_km", 0)),
                    "speed_kmh"         : speed,
                    "freeflow_kmh"      : freeflow,
                    "congestion_level"  : congestion,
                    "congestion_label"  : {0: "🟢 Thông", 1: "🟡 Chậm", 2: "🔴 Tắc"}[congestion],
                    "api_elapsed_ms"    : round(elapsed, 1),
                    "timestamp"         : datetime.now().isoformat(),
                }

        except asyncio.TimeoutError:
            stats["timeouts"] += 1
            return None
        except Exception:
            stats["api_errors"] += 1
            return None


async def crawl_async(streets: list[dict], key_pool: KeyPool) -> list[dict]:
    """Crawl toàn bộ streets song song với tất cả keys."""
    semaphore = asyncio.Semaphore(len(TOMTOM_KEYS) * 2)  # Tối đa N×2 concurrent
    stats = defaultdict(int)
    results = [None] * len(streets)

    # Progress tracking
    completed  = 0
    t_start    = time.time()
    print_lock = asyncio.Lock()

    async def track(i: int, street: dict, session: aiohttp.ClientSession):
        nonlocal completed
        result = await fetch_one(session, key_pool, street, semaphore, stats)
        results[i] = result
        completed += 1

        # In progress mỗi 50 streets
        if completed % 50 == 0 or completed == len(streets):
            elapsed   = time.time() - t_start
            rate      = completed / elapsed
            eta       = (len(streets) - completed) / rate if rate > 0 else 0
            pct       = completed / len(streets) * 100
            async with print_lock:
                print(f"  [{completed:5d}/{len(streets)}] {pct:5.1f}% "
                      f"| ✅{stats['success']} ❌{stats['api_errors']+stats['no_data']} "
                      f"| {rate:.1f} req/s | ETA {eta:.0f}s "
                      f"| Keys: {key_pool.report()}")

    connector = aiohttp.TCPConnector(limit=50, ttl_dns_cache=300)
    timeout   = aiohttp.ClientTimeout(total=30, connect=5)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [track(i, s, session) for i, s in enumerate(streets)]
        # Chạy tất cả song song (asyncio tự quản lý qua semaphore)
        await asyncio.gather(*tasks)

    return [r for r in results if r is not None]


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Cào traffic data cho toàn bộ đường Đà Nẵng")
    parser.add_argument("--limit",    type=int,  default=None,  help="Giới hạn số đường (mặc định: tất cả)")
    parser.add_argument("--no-dedup", action="store_true",      help="Cào từng segment thay vì gom theo tên")
    parser.add_argument("--no-cache", action="store_true",      help="Bỏ qua cache, parse lại SQL dump")
    args = parser.parse_args()

    print("=" * 65)
    print("  CRAWL TOÀN BỘ ĐƯỜNG ĐÀ NẴNG — TomTom Point (OSM Centroid)")
    print("=" * 65)
    print(f"  Keys: {len(TOMTOM_KEYS)} key | Quota: {len(TOMTOM_KEYS)*DAILY_LIMIT:,} req/ngày")
    print(f"  Concurrent: {len(TOMTOM_KEYS)*2} requests song song")
    print()

    # BƯỚC 1: Lấy danh sách đường
    if args.no_cache and CACHE_FILE.exists():
        CACHE_FILE.unlink()
        print("🗑️  Đã xóa cache\n")

    dedup = not args.no_dedup
    streets = load_or_parse_streets(dedup=dedup)

    if args.limit:
        streets = streets[:args.limit]
        print(f"⚡ Giới hạn còn {len(streets):,} đường (--limit {args.limit})\n")

    total = len(streets)

    # Kiểm tra quota
    total_quota = len(TOMTOM_KEYS) * DAILY_LIMIT
    if total > total_quota:
        print(f"⚠️  Cần {total:,} calls nhưng chỉ có {total_quota:,} quota/ngày")
        print(f"   Sẽ cào {total_quota:,} đường đầu tiên (ưu tiên đường dài nhất)")
        streets = streets[:total_quota]
        total   = len(streets)

    print(f"📍 Bắt đầu cào {total:,} đường")
    quota_est = total / total_quota * 100
    time_est  = total / (len(TOMTOM_KEYS) * 2) * 0.8   # ước tính giây
    print(f"   Dùng {quota_est:.1f}% quota hôm nay")
    print(f"   Ước tính: ~{time_est:.0f}s ({time_est/60:.1f} phút)")
    print()

    # BƯỚC 2: Async crawl
    key_pool  = KeyPool(TOMTOM_KEYS, DAILY_LIMIT)
    t_start   = time.time()
    results   = asyncio.run(crawl_async(streets, key_pool))
    total_time = time.time() - t_start

    # BƯỚC 3: Thống kê & lưu
    success = len(results)
    if success == 0:
        print("\n❌ Không có kết quả nào!")
        return

    avg_speed = sum(r["speed_kmh"] for r in results) / success
    cong_dist = {0: 0, 1: 0, 2: 0}
    for r in results:
        cong_dist[r["congestion_level"]] += 1

    # Phân tích theo quận
    district_stats = defaultdict(lambda: {"count": 0, "speeds": []})
    for r in results:
        d = r.get("district") or "N/A"
        district_stats[d]["count"]  += 1
        district_stats[d]["speeds"].append(r["speed_kmh"])

    district_summary = {
        d: {
            "count"    : v["count"],
            "avg_speed": round(sum(v["speeds"]) / len(v["speeds"]), 1),
        }
        for d, v in sorted(district_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    }

    summary = {
        "method"              : "tomtom_point_osm_centroid",
        "dedup_by_name"       : dedup,
        "crawl_time"          : datetime.now().isoformat(),
        "total_streets"       : total,
        "success"             : success,
        "success_rate_pct"    : round(success / total * 100, 1),
        "total_time_s"        : round(total_time, 2),
        "actual_rate_req_s"   : round(success / total_time, 2),
        "api_calls_made"      : success,
        "quota_used_pct"      : round(success / total_quota * 100, 2),
        "avg_speed_kmh"       : round(avg_speed, 1),
        "congestion_dist"     : {
            "smooth (🟢)"    : cong_dist[0],
            "slow (🟡)"      : cong_dist[1],
            "congested (🔴)" : cong_dist[2],
        },
        "district_summary"    : district_summary,
        "keys_usage"          : {f"key_{i+1}": u for i, (_, u) in enumerate(key_pool.usage.items())},
        "results"             : results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 65)
    print("  ✅ CRAWL HOÀN TẤT")
    print(f"     Đường cào được  : {success:,}/{total:,} ({summary['success_rate_pct']}%)")
    print(f"     Tổng thời gian  : {total_time:.1f}s ({total_time/60:.1f} phút)")
    print(f"     Tốc độ thực     : {summary['actual_rate_req_s']:.1f} req/s")
    print(f"     Quota đã dùng   : {summary['quota_used_pct']}% ({success:,}/{total_quota:,})")
    print(f"     Avg tốc độ xe   : {avg_speed:.1f} km/h")
    print(f"     Phân bố         : 🟢{cong_dist[0]:,}  🟡{cong_dist[1]:,}  🔴{cong_dist[2]:,}")
    print()
    print("  Theo quận:")
    for d, stat in district_summary.items():
        print(f"     {d:<20} {stat['count']:>5} đường  avg {stat['avg_speed']:>5.1f} km/h")
    print()
    print(f"     Đã lưu → {OUTPUT_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()
