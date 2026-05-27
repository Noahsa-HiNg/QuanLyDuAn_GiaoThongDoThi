"""
test_new_endpoints.py — Kiểm thử 2 endpoint mới
  GET /api/traffic/state          — Trạng thái giao thông nhẹ
  GET /api/traffic/streets-geometry — Geometry tĩnh

Chạy từ trong Docker:
    docker compose exec backend python3 tests/test_new_endpoints.py
"""

import time
import urllib.request
import json

BASE = "http://localhost:8000/api"

ENDPOINTS = [
    ("traffic/state",       "/traffic/state"),
    ("streets-geometry",    "/traffic/streets-geometry"),
]

SEP = "-" * 68


def fetch(url):
    s = time.time()
    res = urllib.request.urlopen(url)
    first_byte = time.time()
    data = res.read()
    end = time.time()
    return data, first_byte - s, end - first_byte, end - s


def test_structure_state(obj):
    """Kiểm tra cấu trúc /traffic/state"""
    errors = []
    assert "total"      in obj, "Thiếu field 'total'"
    assert "data_as_of" in obj, "Thiếu field 'data_as_of'"
    assert "streets"    in obj, "Thiếu field 'streets'"
    assert isinstance(obj["streets"], list), "'streets' phải là list"
    assert len(obj["streets"]) > 0, "'streets' rỗng!"

    sample = obj["streets"][0]
    required = ["street_id", "congestion_level", "avg_speed", "color", "segments"]
    for f in required:
        if f not in sample:
            errors.append(f"Thiếu field '{f}' trong street")

    # Kiểm tra color format [R, G, B, A]
    color = sample.get("color", [])
    assert isinstance(color, list) and len(color) == 4, \
        f"color phải là [R,G,B,A], got: {color}"

    # Kiểm tra segments
    segs = sample.get("segments", [])
    assert isinstance(segs, list), "segments phải là list"
    if segs:
        seg = segs[0]
        seg_required = ["segment_idx", "congestion_level", "avg_speed", "color"]
        for f in seg_required:
            if f not in seg:
                errors.append(f"Thiếu field '{f}' trong segment")

    # Không được có geometry trong state
    assert "path" not in sample, "state KHÔNG được có 'path' (geometry)!"
    assert "lat"  not in sample, "state KHÔNG được có 'lat'!"
    assert "lon"  not in sample, "state KHÔNG được có 'lon'!"

    if errors:
        return False, errors
    return True, []


def test_structure_geometry(obj):
    """Kiểm tra cấu trúc /traffic/streets-geometry"""
    errors = []
    assert "total"   in obj, "Thiếu field 'total'"
    assert "streets" in obj, "Thiếu field 'streets'"
    assert isinstance(obj["streets"], list), "'streets' phải là list"
    assert len(obj["streets"]) > 0, "'streets' rỗng!"

    sample = obj["streets"][0]
    required = ["street_id", "street_name", "lat", "lon", "path", "segment_count"]
    for f in required:
        if f not in sample:
            errors.append(f"Thiếu field '{f}' trong street")

    # path phải là list tọa độ
    path = sample.get("path", None)
    if path is not None:
        assert isinstance(path, list), "path phải là list"
        assert len(path) >= 2, "path phải có ít nhất 2 điểm"
        assert len(path[0]) == 2, "Mỗi điểm trong path phải là [lon, lat]"

    # Không được có traffic data trong geometry
    assert "congestion_level" not in sample, "geometry KHÔNG được có 'congestion_level'!"
    assert "color"            not in sample, "geometry KHÔNG được có 'color'!"
    assert "avg_speed"        not in sample, "geometry KHÔNG được có 'avg_speed'!"

    if errors:
        return False, errors
    return True, []


# ─── Chạy test ────────────────────────────────────────────────────────────────

print(SEP)
print("  KIỂM THỬ 2 ENDPOINT MỚI")
print(SEP)

all_pass = True

for name, path in ENDPOINTS:
    url = BASE + path
    print(f"\n>>> {name} ({url})")

    # --- Lần 1: Cache MISS ---
    try:
        data, server_t, xfer_t, total_t = fetch(url)
        obj = json.loads(data)
        size_kb = len(data) / 1024

        print(f"  [MISS] server={server_t:.3f}s | xfer={xfer_t:.3f}s | "
              f"total={total_t:.3f}s | size={size_kb:.0f}KB")
        print(f"         total={obj.get('total', '?')} items | "
              f"data_as_of={obj.get('data_as_of', 'N/A')}")

        # Kiểm tra cấu trúc
        if name == "traffic/state":
            ok, errs = test_structure_state(obj)
        else:
            ok, errs = test_structure_geometry(obj)

        if ok:
            print(f"  [STRUCTURE] ✅ Cấu trúc đúng")
        else:
            print(f"  [STRUCTURE] ❌ LỖI: {errs}")
            all_pass = False

        # In sample
        sample = obj["streets"][0]
        print(f"  [SAMPLE]    street_id={sample.get('street_id')} "
              f"name='{sample.get('street_name', 'N/A')}'")

    except Exception as e:
        print(f"  [MISS] ❌ LỖI: {e}")
        all_pass = False
        continue

    # --- Lần 2: Cache HIT ---
    try:
        data2, server_t2, xfer_t2, total_t2 = fetch(url)
        print(f"  [HIT ] server={server_t2:.3f}s | xfer={xfer_t2:.3f}s | "
              f"total={total_t2:.3f}s | size={len(data2)/1024:.0f}KB")

        speedup = total_t / total_t2 if total_t2 > 0 else 0
        print(f"  [CACHE] ✅ HIT nhanh hơn MISS {speedup:.1f}x")

        # Kiểm tra data giống nhau
        if data == data2:
            print(f"  [CACHE] ✅ Response giống hệt nhau (đúng — raw string cache)")
        else:
            print(f"  [CACHE] ⚠️  Response khác nhau giữa MISS và HIT")

    except Exception as e:
        print(f"  [HIT ] ❌ LỖI: {e}")
        all_pass = False

# ─── So sánh với /traffic/current (endpoint cũ) ───────────────────────────────
print(f"\n{SEP}")
print("  SO SÁNH VỚI ENDPOINT CŨ /traffic/current")
print(SEP)
try:
    data_old, s_old, x_old, t_old = fetch(BASE + "/traffic/current")
    print(f"  /traffic/current  : size={len(data_old)/1024:.0f}KB | total={t_old:.3f}s")
    data_new_state, s_ns, x_ns, t_ns = fetch(BASE + "/traffic/state")
    data_new_geo, s_ng, x_ng, t_ng = fetch(BASE + "/traffic/streets-geometry")
    print(f"  /traffic/state    : size={len(data_new_state)/1024:.0f}KB | total={t_ns:.3f}s")
    print(f"  /streets-geometry : size={len(data_new_geo)/1024:.0f}KB | total={t_ng:.3f}s")
    saved = len(data_old) - len(data_new_state)
    print(f"\n  Mỗi lần refresh sau lần đầu: tiết kiệm {saved/1024:.0f}KB "
          f"({saved*100//len(data_old)}%)")
except Exception as e:
    print(f"  ❌ {e}")

# ─── Kết luận ─────────────────────────────────────────────────────────────────
print(f"\n{SEP}")
if all_pass:
    print("  ✅ TẤT CẢ KIỂM THỬ ĐỀU PASS")
else:
    print("  ❌ CÓ KIỂM THỬ THẤT BẠI")
print(SEP)
