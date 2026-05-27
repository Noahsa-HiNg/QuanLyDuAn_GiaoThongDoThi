"""
tests/test_tomtom_centroid/enrich_geometry.py
=============================================
Thêm trường 'path' (geometry LineString) vào file JSON đã crawl.
Dùng khi file JSON cũ chưa có 'path', cần bổ sung mà không cào lại API.

Chạy: python tests/test_tomtom_centroid/enrich_geometry.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import json
import struct
import binascii
from pathlib import Path

BASE_DIR    = Path(__file__).parent.parent.parent
SQL_DUMP    = BASE_DIR / "street_district_dump.sql"
RESULTS_DIR = Path(__file__).parent / "results"
INPUT_FILE  = RESULTS_DIR / "all_streets_results.json"
CACHE_FILE  = RESULTS_DIR / "streets_cache.json"


def ewkb_hex_to_geometry(ewkb_hex: str) -> dict | None:
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
        all_points = []
        if base_type == 2:
            num_pts = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
            for _ in range(num_pts):
                lon = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                lat = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                all_points.append([round(lon, 7), round(lat, 7)])
        else:
            num_lines = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
            for _ in range(num_lines):
                idx += 1
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
        avg_lon = sum(p[0] for p in all_points) / len(all_points)
        avg_lat = sum(p[1] for p in all_points) / len(all_points)
        path = all_points
        if len(path) > 30:
            step = len(path) // 30
            path = path[::step]
            if path[-1] != all_points[-1]:
                path.append(all_points[-1])
        return {"lat": round(avg_lat, 7), "lon": round(avg_lon, 7), "path": path}
    except Exception:
        return None


def parse_geometry_index(sql_file: Path) -> dict[str, list]:
    """
    Parse SQL dump → dict {street_name: [[lon,lat],...]}
    Gom theo tên: cùng tên → nối path lại.
    """
    print(f"📂 Đang parse SQL dump ({sql_file.stat().st_size/1e6:.1f} MB)...")
    name_to_paths = {}   # name → list of points
    name_to_lat   = {}
    name_to_lon   = {}
    in_streets    = False
    col_order     = []
    count         = 0

    with open(sql_file, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            if not in_streets:
                if "COPY public.streets" in line and "FROM stdin" in line:
                    s = line.find("(") + 1; e = line.find(")")
                    if s > 0 and e > s:
                        col_order = [c.strip() for c in line[s:e].split(",")]
                    in_streets = True
                continue
            if line.strip() == "\\.":
                break
            parts = line.split("\t")
            if len(parts) < len(col_order):
                continue
            row = dict(zip(col_order, parts))
            name     = row.get("name")
            geom_hex = row.get("geometry", "")
            if not name or name == "\\N" or not geom_hex or geom_hex == "\\N":
                continue
            geom = ewkb_hex_to_geometry(geom_hex)
            if not geom:
                continue
            if name not in name_to_paths:
                name_to_paths[name] = []
            name_to_paths[name].extend(geom["path"])
            name_to_lat.setdefault(name, geom["lat"])
            name_to_lon.setdefault(name, geom["lon"])
            count += 1

    print(f"   ✅ Parse xong: {count:,} named segments → {len(name_to_paths):,} tên duy nhất")
    return name_to_paths


def enrich():
    if not INPUT_FILE.exists():
        print(f"❌ Không tìm thấy: {INPUT_FILE}")
        return

    print(f"📂 Đọc kết quả cũ: {INPUT_FILE.name}")
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", [])
    print(f"   {len(results):,} đường cần bổ sung geometry")

    # Kiểm tra xem đã có path chưa
    has_path = sum(1 for r in results if r.get("path") and len(r.get("path", [])) >= 2)
    if has_path == len(results):
        print(f"   ✅ Tất cả đường đã có path — không cần enrich")
        return

    print(f"   ⚠️  {len(results)-has_path:,} đường thiếu path → parse SQL dump...")

    # Parse SQL dump
    name_to_paths = parse_geometry_index(SQL_DUMP)

    # Enrich kết quả
    enriched = 0
    for r in results:
        if r.get("path") and len(r.get("path", [])) >= 2:
            continue
        name = r.get("street_name")
        if name and name in name_to_paths:
            pts = name_to_paths[name]
            # Giảm xuống tối đa 40 điểm
            if len(pts) > 40:
                step = len(pts) // 40
                pts = pts[::step]
            r["path"] = pts
            enriched += 1
        else:
            # Fallback: đoạn ngắn tại centroid
            lon, lat = r.get("lon", 108.2), r.get("lat", 16.05)
            r["path"] = [[lon - 0.0002, lat], [lon + 0.0002, lat]]

    print(f"   ✅ Đã bổ sung path cho {enriched:,} đường")

    # Lưu lại
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"💾 Đã lưu vào {INPUT_FILE.name}")


if __name__ == "__main__":
    enrich()
