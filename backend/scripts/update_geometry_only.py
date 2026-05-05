"""
scripts/update_geometry_only.py — Cập nhật geometry của các đường đã có
                                   MÀ KHÔNG XÓA dữ liệu traffic

Dùng khi: bạn muốn chỉnh lại tọa độ vài đường mà không muốn mất traffic data.

Chạy:
    docker compose exec backend python scripts/update_geometry_only.py
    # hoặc nếu chạy local:
    cd backend && python scripts/update_geometry_only.py

Cách dùng:
  1. Sửa tọa độ trong data/manual_coords.py
  2. Chạy file này → chỉ cập nhật geometry, KHÔNG đụng traffic_data
"""

import sys, os, math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://myadmin:123456@postgres:5432/qlda_dothithongminh"
)
engine  = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def coords_to_wkt(coords: list) -> str:
    pts_str = ", ".join(f"{lon} {lat}" for lon, lat in coords)
    return f"LINESTRING({pts_str})"


def calc_length_km(coords: list) -> float:
    total = sum(
        haversine_km(
            float(coords[i][1]), float(coords[i][0]),
            float(coords[i+1][1]), float(coords[i+1][0])
        )
        for i in range(len(coords) - 1)
    )
    return round(total, 2)


def main():
    # ── Chỉ cập nhật các đường có tên trong danh sách này ────────────────────
    # Để trống [] → cập nhật TẤT CẢ đường có trong manual_coords.py
    ONLY_UPDATE_THESE = [
        "Bạch Đằng",
        "Hùng Vương",
        # Thêm tên đường khác nếu muốn
    ]

    from data.manual_coords import MANUAL_COORDS
    from models.street import Street

    db = Session()
    updated = 0
    skipped = 0
    not_found = 0

    print("🔄 Cập nhật geometry (KHÔNG xóa traffic data)...\n")

    for name, coords in MANUAL_COORDS.items():
        # Nếu có filter thì chỉ xử lý đường trong danh sách
        if ONLY_UPDATE_THESE and name not in ONLY_UPDATE_THESE:
            continue

        if not coords or len(coords) < 2:
            print(f"  ⚠️  {name} — không đủ tọa độ (cần ≥ 2 điểm), bỏ qua")
            skipped += 1
            continue

        street = db.query(Street).filter(Street.name == name).first()
        if not street:
            print(f"  ❌  '{name}' — không tìm thấy trong DB")
            not_found += 1
            continue

        wkt       = coords_to_wkt(coords)
        length_km = calc_length_km(coords)

        # Chỉ cập nhật geometry và length_km — KHÔNG đụng traffic_data
        db.execute(
            text("UPDATE streets SET geometry = ST_GeomFromText(:wkt, 4326), length_km = :len WHERE id = :id"),
            {"wkt": wkt, "len": length_km, "id": street.id}
        )
        print(f"  ✅  [{street.id:02d}] {name:<30} {length_km:.2f}km  ({len(coords)} điểm)")
        updated += 1

    db.commit()
    db.close()

    print(f"\n🎉 Hoàn tất!")
    print(f"   Đã cập nhật : {updated} đường")
    print(f"   Bỏ qua      : {skipped} đường (thiếu tọa độ)")
    print(f"   Không tìm thấy: {not_found} đường")
    print(f"\n⚠️  Traffic data GIỮ NGUYÊN — cào lại sau khi kiểm tra bản đồ.")


if __name__ == "__main__":
    main()
