"""
tests/test_tomtom_centroid/crawl_per_segment.py
=================================================
Cào TỐC ĐỘ TỪNG ĐOẠN RIÊNG BIỆT — không gom theo tên đường.

Mỗi OSM segment → 1 TomTom call tại centroid → TomTom trả về:
  - currentSpeed (tốc độ thực đoạn đó)
  - coordinates (geometry CHÍNH XÁC của đoạn TomTom — dùng để vẽ)

Kết quả: Cùng 1 tên đường có NHIỀU MÀU khác nhau theo từng đoạn.

Giải pháp tiết kiệm quota:
  - Dedup theo TomTom segment (nhiều OSM centroid → cùng TomTom segment → chỉ query 1 lần)
  - Lưu kết quả theo batch → không mất data nếu dừng giữa chừng

Chạy:
  python tests/test_tomtom_centroid/crawl_per_segment.py           # tất cả
  python tests/test_tomtom_centroid/crawl_per_segment.py --limit 500   # thử 500 segment
  python tests/test_tomtom_centroid/crawl_per_segment.py --resume      # tiếp tục từ lần trước
"""

import sys, os, json, struct, binascii, asyncio, aiohttp, argparse, time, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ─── PATHS ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent.parent
SQL_DUMP    = BASE_DIR / "street_district_dump.sql"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)
OUTPUT_FILE  = RESULTS_DIR / "per_segment_results.json"
PARTIAL_FILE = RESULTS_DIR / "per_segment_partial.jsonl"   # Lưu incremental

DISTRICT_NAMES = {
    1: "Cẩm Lệ", 2: "Hải Châu", 3: "Hòa Vang",
    4: "Liên Chiểu", 5: "Ngũ Hành Sơn", 6: "Sơn Trà",
    7: "Thanh Khê", 8: "Hoàng Sa",
}

# ─── ĐỌC .ENV ĐỂ LẤY TẤT CẢ TOMTOM KEYS ────────────────────────────────────
def load_tomtom_keys() -> list[str]:
    """Đọc TOMTOM_API_KEYS từ .env file. Ưu tiên KEYS (multi) hơn KEY (single)."""
    env_path = BASE_DIR / ".env"
    single_key = None
    multi_keys = None

    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Multi-key line (ưu tiên cao hơn)
                if line.startswith("TOMTOM_API_KEYS="):
                    raw = line.split("=", 1)[1].strip()
                    keys = [k.strip() for k in raw.split(",") if k.strip()]
                    if keys:
                        multi_keys = keys
                # Single key (fallback)
                elif line.startswith("TOMTOM_API_KEY="):
                    k = line.split("=", 1)[1].strip()
                    if k:
                        single_key = k

    # Ưu tiên multi
    if multi_keys:
        return multi_keys
    if single_key:
        return [single_key]

    # Fallback từ environment variable
    multi = os.getenv("TOMTOM_API_KEYS", "")
    if multi:
        return [k.strip() for k in multi.split(",") if k.strip()]
    single = os.getenv("TOMTOM_API_KEY", "")
    return [single] if single else []

TOMTOM_KEYS = load_tomtom_keys()
DAILY_LIMIT = 2400   # per key

# ─── PARSE GEOMETRY ──────────────────────────────────────────────────────────
def ewkb_to_centroid(ewkb_hex: str) -> tuple[float, float] | None:
    """EWKB hex → (lat, lon) centroid."""
    try:
        raw = binascii.unhexlify(ewkb_hex)
        idx = 0
        bo = raw[idx]; idx += 1
        en = "<" if bo == 1 else ">"
        gt = struct.unpack_from(en + "I", raw, idx)[0]; idx += 4
        if gt & 0x20000000: idx += 4
        bt = gt & 0x0fffffff
        if bt not in (2, 5): return None
        pts = []
        if bt == 2:
            n = struct.unpack_from(en + "I", raw, idx)[0]; idx += 4
            for _ in range(n):
                lo = struct.unpack_from(en + "d", raw, idx)[0]; idx += 8
                la = struct.unpack_from(en + "d", raw, idx)[0]; idx += 8
                pts.append((lo, la))
        else:
            nl = struct.unpack_from(en + "I", raw, idx)[0]; idx += 4
            for _ in range(nl):
                idx += 1
                st = struct.unpack_from(en + "I", raw, idx)[0]; idx += 4
                if st & 0x20000000: idx += 4
                n = struct.unpack_from(en + "I", raw, idx)[0]; idx += 4
                for _ in range(n):
                    lo = struct.unpack_from(en + "d", raw, idx)[0]; idx += 8
                    la = struct.unpack_from(en + "d", raw, idx)[0]; idx += 8
                    pts.append((lo, la))
        if not pts: return None
        return sum(p[1] for p in pts)/len(pts), sum(p[0] for p in pts)/len(pts)
    except Exception:
        return None


# ─── PARSE SQL DUMP → CÁC SEGMENT RIÊNG LẺ ──────────────────────────────────
def parse_all_segments(sql_file: Path) -> list[dict]:
    """Parse ALL named segments — mỗi dòng SQL = 1 segment."""
    print(f"📂 Parse SQL dump ({sql_file.stat().st_size/1e6:.1f} MB)...")
    segments = []; col_order = []; in_streets = False

    with open(sql_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            if not in_streets:
                if "COPY public.streets" in line and "FROM stdin" in line:
                    s = line.find("(")+1; e = line.find(")")
                    if s > 0 and e > s:
                        col_order = [c.strip() for c in line[s:e].split(",")]
                    in_streets = True
                continue
            if line.strip() == "\\.": break

            parts = line.split("\t")
            if len(parts) < len(col_order): continue
            row = dict(zip(col_order, parts))

            name     = row.get("name")
            geom_hex = row.get("geometry", "")
            if not name or name == "\\N": continue
            if not geom_hex or geom_hex == "\\N": continue

            centroid = ewkb_to_centroid(geom_hex)
            if centroid is None: continue
            lat, lon = centroid
            if not (15.5 <= lat <= 16.5 and 107.5 <= lon <= 109.0): continue

            did = int(row.get("district_id","0")) if row.get("district_id","\\N") != "\\N" else 0
            segments.append({
                "osm_id"    : int(row.get("id", 0)),
                "name"      : name,
                "district"  : DISTRICT_NAMES.get(did, "N/A"),
                "lat"       : round(lat, 7),
                "lon"       : round(lon, 7),
                "max_speed" : int(row["max_speed"]) if row.get("max_speed","\\N")!="\\N" else 50,
                "length_km" : float(row["length_km"]) if row.get("length_km","\\N")!="\\N" else 0,
            })

    print(f"   ✅ {len(segments):,} named segments")
    return segments


# ─── KEY POOL ────────────────────────────────────────────────────────────────
class KeyPool:
    def __init__(self, keys: list[str], limit: int):
        self.keys  = keys
        self.limit = limit
        self.usage = {k: 0 for k in keys}
        self._idx  = 0
        self._lock = asyncio.Lock()

    async def get(self) -> str | None:
        async with self._lock:
            for _ in range(len(self.keys)):
                k = self.keys[self._idx % len(self.keys)]
                self._idx += 1
                if self.usage[k] < self.limit:
                    self.usage[k] += 1
                    return k
            return None

    def total_remaining(self) -> int:
        return sum(max(0, self.limit - u) for u in self.usage.values())

    def report(self) -> str:
        return " ".join(f"k{i+1}:{u}" for i,(_, u) in enumerate(self.usage.items()))


# ─── ASYNC TOMTOM FETCH ──────────────────────────────────────────────────────
async def fetch_segment(
    session  : aiohttp.ClientSession,
    pool     : KeyPool,
    seg      : dict,
    sem      : asyncio.Semaphore,
    stats    : dict,
    seen_segs: set,              # Dedup theo TomTom segment hash
    out_file,                    # File ghi kết quả
    lock     : asyncio.Lock,
) -> None:
    async with sem:
        key = await pool.get()
        if key is None:
            stats["quota_exhausted"] += 1
            return

        t0 = time.time()
        try:
            async with session.get(
                # Zoom 18 = granularity 10–50m/segment (giống frontend)
                # Zoom 10 = 500m–2km/segment (quá thô, nhiều segment gom chung)
                "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/18/json",
                params={"point": f"{seg['lat']},{seg['lon']}", "key": key, "unit": "KMPH"},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as resp:
                elapsed_ms = (time.time() - t0) * 1000

                if resp.status == 429:
                    pool.usage[key] = pool.limit
                    stats["rate_limited"] += 1
                    return
                if resp.status != 200:
                    stats["errors"] += 1
                    return

                body  = await resp.json()
                fsd   = body.get("flowSegmentData", {})
                speed = fsd.get("currentSpeed")
                if speed is None:
                    stats["no_data"] += 1
                    return

                # ── Lấy geometry TomTom trả về ──────────────────────────────
                coords_raw = fsd.get("coordinates", {}).get("coordinate", [])
                # Format: [{"latitude": ..., "longitude": ...}, ...]
                tomtom_path = [
                    [round(c["longitude"], 6), round(c["latitude"], 6)]
                    for c in coords_raw
                    if "latitude" in c and "longitude" in c
                ]
                if len(tomtom_path) < 2:
                    # Fallback: dùng điểm query
                    tomtom_path = [
                        [seg["lon"] - 0.0002, seg["lat"]],
                        [seg["lon"] + 0.0002, seg["lat"]],
                    ]

                # ── Dedup: cùng TomTom segment (hash đầu+cuối điểm) ────────
                seg_hash = hashlib.md5(
                    json.dumps(tomtom_path[0] + tomtom_path[-1]).encode()
                ).hexdigest()[:12]

                async with lock:
                    if seg_hash in seen_segs:
                        stats["deduped"] += 1
                        return
                    seen_segs.add(seg_hash)

                # ── Tính congestion ─────────────────────────────────────────
                freeflow   = fsd.get("freeFlowSpeed") or seg["max_speed"] or 50
                ratio      = speed / freeflow
                congestion = 0 if ratio >= 0.70 else (1 if ratio >= 0.40 else 2)

                result = {
                    "osm_id"          : seg["osm_id"],
                    "name"            : seg["name"],
                    "district"        : seg["district"],
                    "lat"             : seg["lat"],
                    "lon"             : seg["lon"],
                    "tomtom_path"     : tomtom_path,   # ← Geometry TomTom, chính xác
                    "speed_kmh"       : speed,
                    "freeflow_kmh"    : freeflow,
                    "congestion_level": congestion,
                    "congestion_label": {0:"🟢 Thông", 1:"🟡 Chậm", 2:"🔴 Tắc"}[congestion],
                    "elapsed_ms"      : round(elapsed_ms, 1),
                    "timestamp"       : datetime.now().isoformat(),
                }

                # Ghi ngay vào file (incremental, an toàn nếu crash)
                async with lock:
                    out_file.write(json.dumps(result, ensure_ascii=False) + "\n")
                    out_file.flush()
                    stats["success"] += 1

        except asyncio.TimeoutError:
            stats["timeouts"] += 1
        except Exception:
            stats["errors"] += 1


# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Cào per-segment traffic data")
    parser.add_argument("--limit",  type=int, default=None, help="Giới hạn số segment")
    parser.add_argument("--resume", action="store_true",    help="Tiếp tục từ partial file")
    args = parser.parse_args()

    print("=" * 65)
    print("  PER-SEGMENT CRAWL — Mỗi đoạn 1 tốc độ riêng")
    print("=" * 65)

    if not TOMTOM_KEYS:
        print("❌ Không tìm thấy TomTom API keys trong .env!")
        return

    print(f"  Keys: {len(TOMTOM_KEYS)} key")
    for i, k in enumerate(TOMTOM_KEYS, 1):
        print(f"    k{i}: {k[:12]}...")
    print(f"  Quota tổng: {len(TOMTOM_KEYS) * DAILY_LIMIT:,} req/ngày")
    print()

    # ── Lấy các segment đã cào (nếu resume) ──────────────────────────────────
    seen_segs_init = set()
    existing = []
    if args.resume and PARTIAL_FILE.exists():
        print(f"📂 Đọc kết quả cũ từ {PARTIAL_FILE.name}...")
        with open(PARTIAL_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line.strip())
                    path = r.get("tomtom_path", [])
                    if len(path) >= 2:
                        h = hashlib.md5(
                            json.dumps(path[0] + path[-1]).encode()
                        ).hexdigest()[:12]
                        seen_segs_init.add(h)
                    existing.append(r)
                except json.JSONDecodeError:
                    pass
        print(f"   ✅ {len(existing):,} kết quả cũ, {len(seen_segs_init):,} TomTom segments đã dedup")
    elif not args.resume and PARTIAL_FILE.exists():
        PARTIAL_FILE.unlink()
        print("🗑️  Xóa partial file cũ (dùng --resume để tiếp tục)")

    # ── Parse SQL dump ────────────────────────────────────────────────────────
    segments = parse_all_segments(SQL_DUMP)

    if args.limit:
        segments = segments[:args.limit]
        print(f"⚡ Giới hạn {len(segments):,} segments (--limit)")

    total = len(segments)
    total_quota = len(TOMTOM_KEYS) * DAILY_LIMIT

    print(f"\n📍 Cần crawl: {total:,} segments")
    print(f"   Quota hôm nay: {total_quota:,}")
    if total > total_quota:
        print(f"   ⚠️  Sẽ dừng sau {total_quota:,} segments (hết quota)")
    time_est = min(total, total_quota) / (len(TOMTOM_KEYS) * 2) * 0.1
    print(f"   Ước tính: ~{time_est:.0f}s ({time_est/60:.1f} phút) với {len(TOMTOM_KEYS)*2} concurrent")
    print()

    # ── Async crawl ───────────────────────────────────────────────────────────
    pool      = KeyPool(TOMTOM_KEYS, DAILY_LIMIT)
    sem       = asyncio.Semaphore(len(TOMTOM_KEYS) * 3)
    stats     = defaultdict(int)
    seen_segs = seen_segs_init
    lock      = asyncio.Lock()

    # Progress tracking
    completed = 0
    t_start   = time.time()

    async def run():
        nonlocal completed
        print_lk = asyncio.Lock()

        async def track(seg):
            nonlocal completed
            await fetch_segment(session, pool, seg, sem, stats, seen_segs, out_file, lock)
            completed += 1
            if completed % 200 == 0 or completed == total:
                elapsed = time.time() - t_start
                rate    = completed / max(elapsed, 0.1)
                eta     = (total - completed) / rate if rate > 0 else 0
                async with print_lk:
                    print(f"  [{completed:6d}/{total}] {completed/total*100:5.1f}%"
                          f" | ✅{stats['success']} 🔁{stats['deduped']} ❌{stats['errors']}"
                          f" | {rate:.1f} req/s | ETA {eta:.0f}s"
                          f" | {pool.report()}")

        conn = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
        async with aiohttp.ClientSession(connector=conn) as session:
            tasks = [track(s) for s in segments]
            await asyncio.gather(*tasks)

    with open(PARTIAL_FILE, "a" if args.resume else "w", encoding="utf-8") as out_file:
        asyncio.run(run())

    total_time = time.time() - t_start

    # ── Đọc lại tất cả kết quả (existing + mới) và lưu JSON ─────────────────
    all_results = list(existing)
    if PARTIAL_FILE.exists():
        new_count = 0
        with open(PARTIAL_FILE, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i < len(existing): continue   # Skip existing nếu resume
                try:
                    all_results.append(json.loads(line.strip()))
                    new_count += 1
                except:
                    pass

    # Thống kê
    success  = stats["success"]
    deduped  = stats["deduped"]
    cong_d   = {0:0, 1:0, 2:0}
    for r in all_results:
        cong_d[r.get("congestion_level", 0)] += 1

    by_district = defaultdict(lambda: {"count":0,"speeds":[]})
    for r in all_results:
        d = r.get("district","N/A")
        by_district[d]["count"] += 1
        s = r.get("speed_kmh")
        if s: by_district[d]["speeds"].append(s)

    summary = {
        "method"           : "per_segment_tomtom",
        "crawl_time"       : datetime.now().isoformat(),
        "total_osm_segments": total,
        "unique_tomtom_segs": len(all_results),
        "deduped"          : deduped,
        "success_this_run" : success,
        "total_time_s"     : round(total_time, 2),
        "rate_req_s"       : round(success / max(total_time, 1), 2),
        "congestion_dist"  : {
            "smooth (🟢)"   : cong_d[0],
            "slow (🟡)"     : cong_d[1],
            "congested (🔴)": cong_d[2],
        },
        "district_summary" : {
            d: {
                "count": v["count"],
                "avg_speed": round(sum(v["speeds"])/len(v["speeds"]),1) if v["speeds"] else 0,
            }
            for d, v in sorted(by_district.items(), key=lambda x:-x[1]["count"])
        },
        "results": all_results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False)

    print()
    print("=" * 65)
    print("  ✅ HOÀN TẤT")
    print(f"     OSM segments     : {total:,}")
    print(f"     TomTom segments  : {len(all_results):,} (sau dedup {deduped:,})")
    print(f"     Thời gian        : {total_time:.1f}s ({total_time/60:.1f} phút)")
    print(f"     Tốc độ           : {summary['rate_req_s']:.1f} req/s")
    print(f"     Phân bố          : 🟢{cong_d[0]:,} 🟡{cong_d[1]:,} 🔴{cong_d[2]:,}")
    print()
    for d, st in summary["district_summary"].items():
        print(f"     {d:<20} {st['count']:>5} segs  avg {st['avg_speed']:>5.1f} km/h")
    print()
    print(f"     Đã lưu → {OUTPUT_FILE.name}")
    print(f"     Mở bản đồ: streamlit run tests/map_view.py")
    print("=" * 65)


if __name__ == "__main__":
    main()
