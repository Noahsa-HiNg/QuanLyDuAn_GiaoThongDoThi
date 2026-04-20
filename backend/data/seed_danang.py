"""
data/seed_danang.py — Seed dữ liệu 50 tuyến đường Đà Nẵng

CÁCH CHẠY (chỉ cần chạy 1 LẦN DUY NHẤT khi setup dự án):
    docker compose exec backend python data/seed_danang.py

LOGIC:
    Lần 1: Gọi Overpass API → lưu geometry vào osm_cache.json → INSERT vào DB
    Lần 2+: Đọc osm_cache.json → không gọi API → INSERT vào DB
    Nếu DB đã có dữ liệu → bỏ qua hoàn toàn, không làm gì
"""

import sys, os, re, json, math, requests
from pathlib import Path
from data.manual_coords import MANUAL_COORDS
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "/app")
from models import District, Street

# ─── CẤU HÌNH ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://myadmin:123456@postgres:5432/qlda_dothithongminh"
)

# File cache — lưu kết quả Overpass để không gọi lại lần sau
# Đường dẫn: /app/data/osm_cache.json (trong container)
CACHE_FILE = Path(__file__).parent / "osm_cache.json"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


# ─── DỮ LIỆU 8 QUẬN ───────────────────────────────────────────────────────────
DISTRICTS = [
    "Hải Châu", "Thanh Khê", "Sơn Trà", "Ngũ Hành Sơn",
    "Liên Chiểu", "Cẩm Lệ", "Hòa Vang", "Hoàng Sa",
]

# ─── 50 TUYẾN ĐƯỜNG ───────────────────────────────────────────────────────────
STREETS_DATA = [
    # Hải Châu
    {"name": "Bạch Đằng",            "district": "Hải Châu",     "max_speed": 50, "one_way": False, "lat": 16.0676, "lng": 108.2218, "km": 2.8},
    {"name": "Trần Phú",             "district": "Hải Châu",     "max_speed": 60, "one_way": False, "lat": 16.0660, "lng": 108.2125, "km": 3.1},
    {"name": "Lê Duẩn",              "district": "Hải Châu",     "max_speed": 60, "one_way": False, "lat": 16.0636, "lng": 108.2126, "km": 4.2},
    {"name": "Hùng Vương",           "district": "Hải Châu",     "max_speed": 50, "one_way": False, "lat": 16.0668, "lng": 108.2096, "km": 2.5},
    {"name": "Nguyễn Văn Linh",      "district": "Hải Châu",     "max_speed": 60, "one_way": False, "lat": 16.0562, "lng": 108.2001, "km": 5.6},
    {"name": "Điện Biên Phủ",        "district": "Hải Châu",     "max_speed": 60, "one_way": False, "lat": 16.0598, "lng": 108.2058, "km": 6.3},
    {"name": "Phan Châu Trinh",      "district": "Hải Châu",     "max_speed": 50, "one_way": False, "lat": 16.0657, "lng": 108.2167, "km": 1.8},
    {"name": "Lý Tự Trọng",          "district": "Hải Châu",     "max_speed": 50, "one_way": False, "lat": 16.0639, "lng": 108.2099, "km": 1.2},
    {"name": "Hoàng Diệu",           "district": "Hải Châu",     "max_speed": 50, "one_way": False, "lat": 16.0700, "lng": 108.2167, "km": 2.1},
    {"name": "Nguyễn Chí Thanh",     "district": "Hải Châu",     "max_speed": 50, "one_way": False, "lat": 16.0598, "lng": 108.2119, "km": 2.9},
    # Thanh Khê
    {"name": "Ông Ích Khiêm",        "district": "Thanh Khê",    "max_speed": 50, "one_way": False, "lat": 16.0717, "lng": 108.1914, "km": 3.5},
    {"name": "Nguyễn Tất Thành",     "district": "Thanh Khê",    "max_speed": 60, "one_way": False, "lat": 16.0756, "lng": 108.1892, "km": 8.2},
    {"name": "Trường Chinh",         "district": "Thanh Khê",    "max_speed": 60, "one_way": False, "lat": 16.0700, "lng": 108.1957, "km": 4.1},
    {"name": "Tôn Đức Thắng",       "district": "Thanh Khê",    "max_speed": 50, "one_way": False, "lat": 16.0756, "lng": 108.1960, "km": 2.7},
    {"name": "Núi Thành",            "district": "Thanh Khê",    "max_speed": 50, "one_way": False, "lat": 16.0630, "lng": 108.2032, "km": 2.3},
    {"name": "Châu Thị Vĩnh Tế",    "district": "Thanh Khê",    "max_speed": 40, "one_way": False, "lat": 16.0756, "lng": 108.1853, "km": 1.5},
    # Sơn Trà
    {"name": "Võ Nguyên Giáp",       "district": "Sơn Trà",      "max_speed": 80, "one_way": False, "lat": 16.0540, "lng": 108.2417, "km": 7.8},
    {"name": "Phạm Văn Đồng",        "district": "Sơn Trà",      "max_speed": 60, "one_way": False, "lat": 16.0638, "lng": 108.2296, "km": 3.6},
    {"name": "Ngô Quyền",            "district": "Sơn Trà",      "max_speed": 50, "one_way": False, "lat": 16.0748, "lng": 108.2282, "km": 2.9},
    {"name": "Hoàng Sa",             "district": "Sơn Trà",      "max_speed": 60, "one_way": False, "lat": 16.0819, "lng": 108.2328, "km": 5.1},
    {"name": "Lê Văn Duyệt",         "district": "Sơn Trà",      "max_speed": 50, "one_way": False, "lat": 16.0735, "lng": 108.2229, "km": 1.8},
    {"name": "Trần Hưng Đạo",        "district": "Sơn Trà",      "max_speed": 50, "one_way": False, "lat": 16.0740, "lng": 108.2201, "km": 2.4},
    # Ngũ Hành Sơn
    {"name": "Trường Sa",            "district": "Ngũ Hành Sơn", "max_speed": 60, "one_way": False, "lat": 16.0220, "lng": 108.2529, "km": 9.5},
    {"name": "Võ Chí Công",          "district": "Ngũ Hành Sơn", "max_speed": 80, "one_way": False, "lat": 15.9980, "lng": 108.2627, "km": 12.3},
    {"name": "Lê Văn Hiến",          "district": "Ngũ Hành Sơn", "max_speed": 60, "one_way": False, "lat": 16.0128, "lng": 108.2419, "km": 4.2},
    {"name": "Huyền Trân Công Chúa", "district": "Ngũ Hành Sơn", "max_speed": 50, "one_way": False, "lat": 16.0028, "lng": 108.2648, "km": 3.1},
    {"name": "Phan Đình Phùng",      "district": "Ngũ Hành Sơn", "max_speed": 50, "one_way": False, "lat": 16.0250, "lng": 108.2430, "km": 2.8},
    # Liên Chiểu
    {"name": "Nguyễn Lương Bằng",    "district": "Liên Chiểu",   "max_speed": 60, "one_way": False, "lat": 16.0920, "lng": 108.1690, "km": 3.4},
    {"name": "Hoàng Văn Thái",       "district": "Liên Chiểu",   "max_speed": 50, "one_way": False, "lat": 16.0937, "lng": 108.1710, "km": 2.6},
    {"name": "Tôn Thất Thuyết",      "district": "Liên Chiểu",   "max_speed": 50, "one_way": False, "lat": 16.1030, "lng": 108.1631, "km": 2.1},
    {"name": "Nguyễn Sinh Sắc",      "district": "Liên Chiểu",   "max_speed": 60, "one_way": False, "lat": 16.1058, "lng": 108.1594, "km": 4.8},
    {"name": "Trần Đại Nghĩa",       "district": "Liên Chiểu",   "max_speed": 50, "one_way": False, "lat": 16.1096, "lng": 108.1527, "km": 3.2},
    {"name": "Nguyễn Đức Cảnh",      "district": "Liên Chiểu",   "max_speed": 50, "one_way": False, "lat": 16.0960, "lng": 108.1738, "km": 1.9},
    # Cẩm Lệ
    {"name": "Cách Mạng Tháng 8",    "district": "Cẩm Lệ",       "max_speed": 60, "one_way": False, "lat": 16.0165, "lng": 108.1876, "km": 5.7},
    {"name": "Quốc lộ 1A",           "district": "Cẩm Lệ",       "max_speed": 80, "one_way": False, "lat": 16.0120, "lng": 108.1948, "km": 18.5},
    {"name": "Ngô Thì Nhậm",         "district": "Cẩm Lệ",       "max_speed": 50, "one_way": False, "lat": 16.0200, "lng": 108.1979, "km": 1.6},
    {"name": "Vũ Hữu Lợi",           "district": "Cẩm Lệ",       "max_speed": 40, "one_way": False, "lat": 16.0260, "lng": 108.1940, "km": 1.2},
    {"name": "Lý Thái Tổ",           "district": "Cẩm Lệ",       "max_speed": 50, "one_way": False, "lat": 16.0300, "lng": 108.1913, "km": 2.0},
    {"name": "Trần Thị Lý",          "district": "Cẩm Lệ",       "max_speed": 60, "one_way": False, "lat": 16.0375, "lng": 108.1937, "km": 2.8},
    # Hòa Vang
    {"name": "Quốc lộ 14B",          "district": "Hòa Vang",     "max_speed": 80, "one_way": False, "lat": 15.9750, "lng": 108.1620, "km": 22.0},
    {"name": "ĐT605",                "district": "Hòa Vang",     "max_speed": 60, "one_way": False, "lat": 15.9450, "lng": 108.0880, "km": 15.3},
    {"name": "Lê Trọng Tấn",         "district": "Hòa Vang",     "max_speed": 50, "one_way": False, "lat": 16.0008, "lng": 108.1713, "km": 3.1},
    {"name": "Hòa Phước",            "district": "Hòa Vang",     "max_speed": 50, "one_way": False, "lat": 15.9654, "lng": 108.2105, "km": 4.5},
    # Liên quận / cầu
    {"name": "Cầu Rồng",             "district": "Hải Châu",     "max_speed": 50, "one_way": False, "lat": 16.0609, "lng": 108.2273, "km": 0.7},
    {"name": "Cầu Sông Hàn",         "district": "Hải Châu",     "max_speed": 40, "one_way": True,  "lat": 16.0734, "lng": 108.2234, "km": 0.5},
    {"name": "Nguyễn Tri Phương",    "district": "Hải Châu",     "max_speed": 50, "one_way": False, "lat": 16.0623, "lng": 108.2049, "km": 3.3},
    {"name": "30 tháng 4",           "district": "Hải Châu",     "max_speed": 50, "one_way": False, "lat": 16.0561, "lng": 108.2166, "km": 2.1},
    {"name": "2 tháng 9",            "district": "Hải Châu",     "max_speed": 60, "one_way": False, "lat": 16.0420, "lng": 108.2122, "km": 7.4},
    {"name": "Nguyễn Hữu Thọ",      "district": "Cẩm Lệ",       "max_speed": 60, "one_way": False, "lat": 16.0328, "lng": 108.2067, "km": 4.6},
]


# ─── BƯỚC 1: LẤY GEOMETRY (từ cache hoặc Overpass) ────────────────────────────
def coords_to_wkt(coords: list) -> str:
    """
    Chuyển danh sách [[lon, lat], ...] từ manual_coords.py sang WKT LINESTRING.
    Ví dụ: [[108.22, 16.06], [108.23, 16.07]] → "LINESTRING(108.22 16.06, 108.23 16.07)"
    """
    pts_str = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    return f"LINESTRING({pts_str})"

def get_geometries() -> dict:
    """
    Trả về dict {tên_đường: "LINESTRING(...)"}

    Logic ưu tiên:
    1. Nếu osm_cache.json đã có → đọc file, KHÔNG gọi API
    2. Nếu chưa có → gọi Overpass 1 lần → lưu vào file → trả về
    """

    # ── Kiểm tra cache ──────────────────────────────────────────
    if CACHE_FILE.exists():
        print(f"📂 Tìm thấy cache: {CACHE_FILE}")
        print("   → Đọc từ file, KHÔNG gọi API")
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    # ── Chưa có cache → gọi Overpass 1 lần ─────────────────────
    print("🌐 Chưa có cache → Gọi Overpass API (1 lần duy nhất)...")

    street_names = [s["name"] for s in STREETS_DATA]
    name_regex   = "|".join(street_names)
    DANANG_BBOX  = "15.85,107.90,16.25,108.40"

    query = f"""
    [out:json][timeout:60];
    way["name"~"{name_regex}"]["highway"]({DANANG_BBOX});
    out geom qt;
    """

    try:
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=90,
            headers={"User-Agent": "QLDA-DaNang-Traffic/1.0"}
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        print(f"   → Nhận {len(elements)} way từ Overpass")

        # Gom tọa độ theo tên đường
        raw: dict[str, list] = {}
        for way in elements:
            way_name = way.get("tags", {}).get("name", "")
            coords   = way.get("geometry", [])
            if not way_name or len(coords) < 2:
                continue
            # Khớp với tên trong danh sách
            for s_name in street_names:
                if s_name in way_name or way_name in s_name:
                    raw.setdefault(s_name, [])
                    raw[s_name].extend((c["lon"], c["lat"]) for c in coords)
                    break

        # Chuyển sang WKT
        result = {}
        for name, pts in raw.items():
            if len(pts) >= 2:
                # pts = [(lng1, lat1), (lng2, lat2), ...]
                # WKT đúng: "LINESTRING(lng1 lat1, lng2 lat2, ...)"
                pts_str = ", ".join(f"{lng} {lat}" for lng, lat in pts)
                result[name] = f"LINESTRING({pts_str})"

        print(f"   → Match: {len(result)}/{len(street_names)} đường")

    except Exception as e:
        print(f"   ⚠ Lỗi: {e} → geometry sẽ dùng fallback hết")
        result = {}

    # ── Lưu vào cache để lần sau không gọi API nữa ─────────────
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"💾 Đã lưu cache → {CACHE_FILE}")
    print("   (Lần sau chạy script sẽ đọc từ file này, không gọi API)")
    return result


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    """
    Tính khoảng cách thực tế (km) giữa 2 tọa độ GPS.
    Công thức Haversine — chính xác cho khoảng cách phẳng ngắn.
    """
    R = 6371  # Bán kính Trái Đất (km)
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat/2)**2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


def fallback_linestring(lat: float, lng: float, km: float = 1.0) -> str:
    """
    Tạo LINESTRING đơn giản với chiều dài gần đúng theo km.
    Tạo đường nằm ngang (hướng Tây-Đông) qua điểm trung tâm.
    1 độ kinh tuyến ≈ 111km × cos(lat) ≈ 106km tại Đà Nẵng (lat≈16°)
    """
    # Đổi km → độ kinh tuyến (mỗi bên là km/2)
    half_deg = (km / 2) / (111.0 * math.cos(math.radians(lat)))
    return f"LINESTRING({lng-half_deg} {lat}, {lng} {lat}, {lng+half_deg} {lat})"


# ─── BƯỚC 2: INSERT VÀO DATABASE ──────────────────────────────────────────────
def seed():
    db = Session()
    try:
        # Nếu đã có dữ liệu → thoát ngay
        count = db.query(Street).count()
        if count > 0:
            print(f"\n✅ DB đã có {count} đường. Không cần seed lại.")
            print("   Muốn reset: TRUNCATE streets, districts CASCADE;")
            return

        # Bước 1: Lấy geometry
        geometries = get_geometries()

        # Bước 2: INSERT quận
        print("\n📍 Thêm 8 quận...")
        district_map = {}
        for name in DISTRICTS:
            d = District(name=name)
            db.add(d)
            db.flush()
            district_map[name] = d.id
            print(f"  ✓ {name} (id={d.id})")
        db.commit()

        # Bước 3: INSERT đường
        print(f"\n🛣️  Thêm {len(STREETS_DATA)} tuyến đường...")
        osm_ok = 0
        fallback_ok = 0

        manual_ok = 0

        for i, s in enumerate(STREETS_DATA, 1):
            d_id = district_map[s["district"]]

            manual_pts = MANUAL_COORDS.get(s["name"], [])

            if manual_pts and len(manual_pts) >= 2:
                # ── Ưu tiên 1: Tọa độ thủ công từ manual_coords.py ──────
                wkt = coords_to_wkt(manual_pts)
                tag = f"✏ manual({len(manual_pts)} pts)"
                manual_ok += 1
                # Tính length_km thực từ geometry manual bằng Haversine
                pts = re.findall(r"(-?[\d.]+)\s+(-?[\d.]+)", wkt)
                length_km = sum(
                    haversine_km(float(pts[j][1]), float(pts[j][0]),
                                 float(pts[j+1][1]), float(pts[j+1][0]))
                    for j in range(len(pts)-1)
                )
                length_km = round(length_km, 2)

            elif s["name"] in geometries:
                # ── Ưu tiên 2: Geometry từ Overpass OSM cache ───────────
                wkt = geometries[s["name"]]
                tag = "✓ OSM"
                osm_ok += 1
                pts = re.findall(r"(-?[\d.]+)\s+(-?[\d.]+)", wkt)
                length_km = sum(
                    haversine_km(float(pts[j][1]), float(pts[j][0]),
                                 float(pts[j+1][1]), float(pts[j+1][0]))
                    for j in range(len(pts)-1)
                )
                length_km = round(length_km, 2)

            else:
                # ── Ưu tiên 3: Fallback đường thẳng ước tính ──────────
                length_km = s.get("km", 1.0)
                wkt = fallback_linestring(s["lat"], s["lng"], km=length_km)
                tag = f"〜 fallback({length_km}km)"
                fallback_ok += 1

            street = Street(
                name=s["name"], district_id=d_id,
                length_km=length_km,
                max_speed=s["max_speed"],
                is_one_way=s["one_way"],
            )
            db.add(street)
            db.flush()

            db.execute(
                text("UPDATE streets SET geometry = ST_GeomFromText(:wkt, 4326) WHERE id = :id"),
                {"wkt": wkt, "id": street.id}
            )
            print(f"  [{i:02d}] {s['name']:<30} {length_km:>5.1f} km  {tag}")

        db.commit()

        # Báo cáo
        print(f"\n{'='*52}")
        print(f"  ✅ SEED HOÀN TẤT")
        print(f"     Thủ công  : {manual_ok} đường  ← manual_coords.py")
        print(f"     Từ OSM    : {osm_ok} đường")
        print(f"     Fallback  : {fallback_ok} đường")
        print(f"{'='*52}")
        print(f"\n  Phân bổ theo quận:")
        for name, d_id in district_map.items():
            n = db.query(Street).filter(Street.district_id == d_id).count()
            print(f"  {'█' * n:<12} {n:>2}  {name}")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Lỗi: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 52)
    print("  SEED 50 TUYẾN ĐƯỜNG ĐÀ NẴNG  (chạy 1 lần)")
    print("=" * 52)
    seed()
