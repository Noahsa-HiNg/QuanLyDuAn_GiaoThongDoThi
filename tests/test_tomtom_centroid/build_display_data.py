"""
tests/test_tomtom_centroid/build_display_data.py
==================================================
Tạo file hiển thị cho bản đồ đường thẳng:
  - Load speed data từ all_streets_results.json (1 speed/tên đường)
  - Parse SQL dump → tất cả segment riêng lẻ (mỗi segment = 1 path độc lập)
  - Gán speed cho từng segment theo tên
  - Lưu vào results/display_data.json

Kết quả: KHÔNG nối điểm giữa các segment — mỗi đường nhỏ hiển thị đúng vị trí.

Chạy: python tests/test_tomtom_centroid/build_display_data.py
"""

import sys, os, json, struct, binascii
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pathlib import Path
from datetime import datetime

BASE_DIR     = Path(__file__).parent.parent.parent
SQL_DUMP     = BASE_DIR / "street_district_dump.sql"
RESULTS_DIR  = Path(__file__).parent / "results"
SPEED_FILE   = RESULTS_DIR / "all_streets_results.json"   # speed per name
OUTPUT_FILE  = RESULTS_DIR / "display_data.json"

DISTRICT_NAMES = {
    1: "Cẩm Lệ", 2: "Hải Châu", 3: "Hòa Vang",
    4: "Liên Chiểu", 5: "Ngũ Hành Sơn", 6: "Sơn Trà",
    7: "Thanh Khê", 8: "Hoàng Sa",
}


def ewkb_to_path(ewkb_hex: str) -> list | None:
    """EWKB hex → [[lon, lat], ...] — trả về None nếu lỗi."""
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

        pts = []
        if base_type == 2:   # LineString
            n = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
            for _ in range(n):
                lo = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                la = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                pts.append([round(lo, 6), round(la, 6)])
        else:                # MultiLineString — chỉ lấy linestring đầu tiên
            n_lines = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
            for li in range(n_lines):
                idx += 1
                st = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
                if st & 0x20000000: idx += 4
                n = struct.unpack_from(endian + "I", raw, idx)[0]; idx += 4
                for _ in range(n):
                    lo = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                    la = struct.unpack_from(endian + "d", raw, idx)[0]; idx += 8
                    pts.append([round(lo, 6), round(la, 6)])
                if li == 0:
                    break   # Chỉ lấy linestring đầu để tránh nối lung tung

        if len(pts) < 2:
            return None
        # Giữ tối đa 20 điểm / segment
        if len(pts) > 20:
            step = len(pts) // 20
            pts  = pts[::step]
        return pts
    except Exception:
        return None


def load_speed_index(speed_file: Path) -> dict:
    """
    Đọc speed data từ JSON crawl result.
    Trả về: {street_name: {speed, freeflow, congestion_level, congestion_label}}
    """
    if not speed_file.exists():
        print(f"⚠️  Không tìm thấy {speed_file.name} — bản đồ sẽ không có màu tốc độ")
        return {}
    with open(speed_file, encoding="utf-8") as f:
        data = json.load(f)
    idx = {}
    for r in data.get("results", []):
        name = r.get("street_name")
        if name:
            idx[name] = {
                "speed"     : r.get("speed_kmh", 0),
                "freeflow"  : r.get("freeflow_kmh", 60),
                "congestion": r.get("congestion_level", -1),
                "label"     : r.get("congestion_label", "N/A"),
            }
    print(f"   Speed index: {len(idx):,} tên đường có dữ liệu tốc độ")
    return idx


def build():
    print("=" * 60)
    print("  BUILD DISPLAY DATA — Từng segment độc lập")
    print("=" * 60)

    # 1. Load speed index
    print("\n📊 Đang load dữ liệu tốc độ...")
    speed_idx = load_speed_index(SPEED_FILE)

    # 2. Parse SQL dump — GIỮ TỪNG SEGMENT RIÊNG LẺ
    print(f"\n📂 Đang parse SQL dump ({SQL_DUMP.stat().st_size/1e6:.1f} MB)...")
    segments    = []
    no_data     = 0
    bad_geom    = 0
    in_streets  = False
    col_order   = []

    with open(SQL_DUMP, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            if not in_streets:
                if "COPY public.streets" in line and "FROM stdin" in line:
                    s = line.find("(") + 1
                    e = line.find(")")
                    if s > 0 and e > s:
                        col_order = [c.strip() for c in line[s:e].split(",")]
                    in_streets = True
                continue
            if line.strip() == "\\.":
                break

            parts = line.split("\t")
            if len(parts) < len(col_order):
                continue

            row      = dict(zip(col_order, parts))
            name     = row.get("name")
            geom_hex = row.get("geometry", "")

            # Bỏ qua đường không tên
            if not name or name == "\\N":
                continue
            if not geom_hex or geom_hex == "\\N":
                bad_geom += 1
                continue

            path = ewkb_to_path(geom_hex)
            if path is None:
                bad_geom += 1
                continue

            # Tính centroid từ path
            avg_lon = sum(p[0] for p in path) / len(path)
            avg_lat = sum(p[1] for p in path) / len(path)

            # Kiểm tra trong bbox Đà Nẵng
            if not (15.5 <= avg_lat <= 16.5 and 107.5 <= avg_lon <= 109.0):
                continue

            did    = int(row.get("district_id", 0)) if row.get("district_id", "\\N") != "\\N" else 0
            lkm    = float(row["length_km"]) if row.get("length_km", "\\N") != "\\N" else 0
            mspd   = int(row["max_speed"])   if row.get("max_speed", "\\N")  != "\\N" else 50

            # Tra cứu tốc độ theo tên
            spd_info = speed_idx.get(name)
            if spd_info:
                speed      = spd_info["speed"]
                freeflow   = spd_info["freeflow"]
                congestion = spd_info["congestion"]
                label      = spd_info["label"]
            else:
                speed      = None
                freeflow   = mspd
                congestion = -1   # Không có data → màu xám
                label      = "⬜ Không có dữ liệu"
                no_data   += 1

            segments.append({
                "id"        : int(row.get("id", 0)),
                "name"      : name,
                "district"  : DISTRICT_NAMES.get(did, "N/A"),
                "path"      : path,          # ← Path của CHÍNH segment này, không merge
                "lat"       : round(avg_lat, 6),
                "lon"       : round(avg_lon, 6),
                "length_km" : round(lkm, 3),
                "max_speed" : mspd,
                "speed_kmh" : speed,
                "freeflow_kmh" : freeflow,
                "congestion_level": congestion,
                "congestion_label": label,
            })

    total = len(segments)
    has_data = total - no_data

    print(f"   ✅ {total:,} segments hợp lệ")
    print(f"   ├─ Có dữ liệu tốc độ : {has_data:,} ({has_data/total*100:.1f}%)")
    print(f"   ├─ Không có dữ liệu  : {no_data:,} ({no_data/total*100:.1f}%) → màu xám")
    print(f"   └─ Geometry lỗi      : {bad_geom:,} (bỏ qua)")

    # 3. Thống kê
    cong = {-1: 0, 0: 0, 1: 0, 2: 0}
    for s in segments:
        cong[s["congestion_level"]] += 1

    summary = {
        "built_at"      : datetime.now().isoformat(),
        "total_segments": total,
        "has_speed_data": has_data,
        "no_speed_data" : no_data,
        "congestion_dist": {
            "no_data (⬜)": cong[-1],
            "smooth (🟢)" : cong[0],
            "slow (🟡)"   : cong[1],
            "congested (🔴)": cong[2],
        },
        "segments": segments,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False)

    sz = OUTPUT_FILE.stat().st_size / 1e6
    print(f"\n💾 Đã lưu → {OUTPUT_FILE.name} ({sz:.1f} MB)")
    print("=" * 60)
    print(f"  Mở bản đồ: streamlit run tests/map_view.py")
    print("=" * 60)


if __name__ == "__main__":
    build()
