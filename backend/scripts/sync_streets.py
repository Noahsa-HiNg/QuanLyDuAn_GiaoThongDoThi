"""
scripts/sync_streets.py — Đồng bộ streets từ manual_coords.py (GIỮ NGUYÊN districts)

CÁCH CHẠY (không cần xác nhận):
    docker compose exec backend python scripts/sync_streets.py

NHỮNG GÌ SCRIPT NÀY LÀM:
    ✅ GIỮ NGUYÊN bảng districts
    🗑️  XÓA những đường KHÔNG CÓ tọa độ trong manual_coords.py
           (cùng toàn bộ traffic_data liên quan)
    🔄  CẬP NHẬT geometry chính xác cho đường ĐÃ CÓ trong DB
    ➕  THÊM MỚI đường có tọa độ nhưng chưa có trong DB
    🗑️  XÓA SẠCH toàn bộ traffic_data cũ
    🌐  CÀO TRAFFIC theo từng ĐOẠN ĐƯỜNG (~500m/đoạn) từ TomTom API
        → Mỗi đoạn có congestion_level riêng → frontend tô màu từng đoạn
"""

import sys, os, json, math, time

sys.path.insert(0, "/app")

from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://myadmin:123456@postgres:5432/qlda_dothithongminh"
)
engine  = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


# ─── HELPERS ─────────────────────────────────────────────────────────────────
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


# ─── BƯỚC 3: XÓA TRAFFIC CŨ + CÀO THEO TỪNG ĐOẠN ĐƯỜNG ─────────────────────
def ingest_all_streets_by_segment(db):
    """
    Xóa toàn bộ traffic_data cũ, sau đó cào lại dữ liệu mới
    theo từng ĐOẠN (segment) của mỗi đường.
    """
    from models import Street, TrafficData
    from services.ingestion import (
        fetch_tomtom, fetch_goong, calc_congestion_level,
        tomtom_quota, goong_quota
    )
    from utils.geometry import split_path_into_zones, calc_road_length_m
    from config import settings

    # Kiểm tra API key
    keys = settings.tomtom_keys_list
    if not keys:
        print("\n" + "─" * 60)
        print("  ⚠️  KHÔNG CÓ TOMTOM_API_KEY")
        print("─" * 60)
        print("  Thêm vào file .env:")
        print("    TOMTOM_API_KEY=your_key_here")
        print("  Hoặc dùng mock data (không cần key):")
        print("    docker compose exec backend python data/seed_traffic.py")
        return

    if tomtom_quota.is_exhausted and goong_quota.is_exhausted:
        print("\n⛔ Cả TomTom và Goong đều HẾT QUOTA hôm nay (reset 00:00 +07)")
        return

    # ── Xóa toàn bộ traffic_data cũ ─────────────────────────────────────────
    print("\n" + "─" * 60)
    print("  BƯỚC 3: XÓA TRAFFIC CŨ + CÀO DỮ LIỆU THEO ĐOẠN ĐƯỜNG")
    print("─" * 60)
    old_count = db.execute(text("SELECT COUNT(*) FROM traffic_data")).scalar()
    db.execute(text("DELETE FROM traffic_data"))
    db.commit()
    print(f"  🗑️  Đã xóa {old_count:,} bản ghi traffic cũ\n")

    # ── Lấy tất cả đường từ DB ───────────────────────────────────────────────
    streets    = db.query(Street).all()
    now        = datetime.now(timezone.utc)
    now_vn_str = datetime.fromtimestamp(now.timestamp() + 7*3600).strftime("%H:%M %d/%m/%Y +07")

    print(f"  Thời điểm cào: {now_vn_str}")
    print(f"  TomTom keys  : {len(keys)} key(s) | Quota còn: {tomtom_quota.remaining} req")
    print(f"  Tổng đường   : {len(streets)}\n")

    LABEL = {0: "🟢 Thông thoáng", 1: "🟡 Chậm      ", 2: "🔴 Kẹt xe    "}

    total_zones  = 0
    total_saved  = 0
    success_cnt  = 0
    fail_cnt     = 0

    for idx, street in enumerate(streets, 1):
        max_speed = street.max_speed or 50

        # Lấy geometry từ PostGIS
        row = db.execute(
            text("""
                SELECT (ST_AsGeoJSON(geometry)::json -> 'coordinates') AS coords
                FROM streets WHERE id = :sid AND geometry IS NOT NULL
            """),
            {"sid": street.id}
        ).fetchone()

        if not row or not row.coords:
            print(f"  [{idx:02d}] ⚠  {street.name:<28} — không có geometry, bỏ qua")
            fail_cnt += 1
            continue

        coords = json.loads(row.coords) if isinstance(row.coords, str) else row.coords
        if not coords or len(coords) < 2:
            fail_cnt += 1
            continue

        # Chia thành zone tự động (~500m/zone, tối đa 8 zone)
        zones    = split_path_into_zones(coords)
        length_m = calc_road_length_m(coords)
        n_zones  = len(zones)
        saved_n  = 0

        print(f"  [{idx:02d}] {street.name:<28}  {length_m/1000:.1f}km → {n_zones} đoạn")

        for zone in zones:
            seg_idx = zone["segment_idx"]
            lat     = zone["mid_lat"]
            lon     = zone["mid_lon"]

            # Thử TomTom → fallback Goong
            result = fetch_tomtom(lat, lon)
            src    = "tomtom"
            if result is None:
                result = fetch_goong(lat, lon, max_speed)
                src    = "goong"
            if result is None:
                print(f"       Đoạn {seg_idx}: ❌ thất bại (hết quota?)")
                continue

            avg_speed  = result["avg_speed"]
            ref_speed  = result.get("free_flow_speed") or max_speed
            congestion = calc_congestion_level(avg_speed, ref_speed)

            db.add(TrafficData(
                street_id        = street.id,
                segment_idx      = seg_idx,
                timestamp        = now,
                avg_speed        = avg_speed,
                congestion_level = congestion,
                source           = src,
            ))
            saved_n += 1

            print(f"       Đoạn {seg_idx}: {LABEL.get(congestion)}  "
                  f"{avg_speed:>5.1f} km/h  [{src}]")

            if n_zones > 1:
                time.sleep(0.5)   # Delay nhỏ giữa các zone

        if saved_n > 0:
            success_cnt += 1
            total_saved += saved_n
        else:
            fail_cnt += 1
        total_zones += n_zones

        time.sleep(1.0)   # Delay giữa các đường

    db.commit()

    # ── Tổng kết ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  ✅ CÀO TRAFFIC HOÀN TẤT")
    print(f"     Thành công     : {success_cnt}/{len(streets)} đường")
    print(f"     Thất bại       : {fail_cnt} đường (no geometry / API fail)")
    print(f"     Tổng đoạn cào  : {total_zones} zones")
    print(f"     Bản ghi đã lưu : {total_saved:,} traffic records")
    print(f"     Quota TomTom   : {tomtom_quota.remaining} req còn lại hôm nay")
    print(f"{'='*60}")

    if fail_cnt > 0:
        print(f"\n  ℹ️  Đường thất bại có thể do:")
        print(f"     - Hết quota API (reset 00:00 +07:00)")
        print(f"     - Chưa có geometry trong DB")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  SYNC STREETS — Đồng bộ từ manual_coords.py")
    print("  (Giữ nguyên districts)")
    print("=" * 60)

    from data.manual_coords import MANUAL_COORDS
    from data.seed_danang import STREETS_DATA
    from models import Street, District

    # Phân loại đường
    has_coords  = {s["name"]: s for s in STREETS_DATA
                   if len(MANUAL_COORDS.get(s["name"], [])) >= 2}
    no_coords   = [s["name"] for s in STREETS_DATA
                   if len(MANUAL_COORDS.get(s["name"], [])) < 2]

    print(f"\n📋 Phân tích:")
    print(f"   ✓ Có tọa độ   : {len(has_coords)} đường")
    print(f"   ✗ Không có    : {len(no_coords)} đường → sẽ xóa khỏi DB")

    db = Session()
    try:
        # ── Lấy district map từ DB (không tạo mới) ───────────────────────────
        districts = db.query(District).all()
        if not districts:
            print("\n❌ Chưa có districts trong DB. Chạy seed_danang.py trước!")
            return

        district_map = {d.name: d.id for d in districts}
        print(f"\n📍 Dùng {len(districts)} quận hiện có trong DB:")
        for name in district_map:
            print(f"   • {name}")

        # ── BƯỚC 1: Xóa đường không có tọa độ (+ traffic_data liên quan) ────
        print(f"\n{'─'*60}")
        print(f"  BƯỚC 1: XÓA ĐƯỜNG KHÔNG CÓ TỌA ĐỘ")
        print(f"{'─'*60}")
        deleted_streets = 0
        deleted_traffic = 0
        for name in no_coords:
            street = db.query(Street).filter(Street.name == name).first()
            if street:
                count = db.execute(
                    text("SELECT COUNT(*) FROM traffic_data WHERE street_id = :sid"),
                    {"sid": street.id}
                ).scalar()
                db.execute(
                    text("DELETE FROM traffic_data WHERE street_id = :sid"),
                    {"sid": street.id}
                )
                db.delete(street)
                deleted_streets += 1
                deleted_traffic += count
                print(f"  🗑  {name} (id={street.id}, {count} traffic records)")
            else:
                print(f"  ⚠  {name} — không có trong DB")

        db.commit()
        print(f"  → Xóa {deleted_streets} đường, {deleted_traffic:,} traffic records")

        # ── BƯỚC 2: UPDATE / INSERT đường có tọa độ ──────────────────────────
        print(f"\n{'─'*60}")
        print(f"  BƯỚC 2: CẬP NHẬT / THÊM MỚI {len(has_coords)} ĐƯỜNG")
        print(f"{'─'*60}")
        updated  = 0
        inserted = 0

        for name, s_info in has_coords.items():
            coords    = MANUAL_COORDS[name]
            wkt       = coords_to_wkt(coords)
            length_km = calc_length_km(coords)
            d_id      = district_map.get(s_info["district"])

            if d_id is None:
                print(f"  ⚠  Không tìm thấy quận '{s_info['district']}' → bỏ qua '{name}'")
                continue

            existing = db.query(Street).filter(Street.name == name).first()

            if existing:
                existing.length_km   = length_km
                existing.max_speed   = s_info["max_speed"]
                existing.is_one_way  = s_info["one_way"]
                existing.district_id = d_id
                db.flush()
                db.execute(
                    text("UPDATE streets SET geometry = ST_GeomFromText(:wkt, 4326) WHERE id = :id"),
                    {"wkt": wkt, "id": existing.id}
                )
                print(f"  🔄 [{existing.id:02d}] {name:<30} {length_km:>5.1f}km  ({len(coords)} pts)")
                updated += 1
            else:
                from models import Street as StreetModel
                new_street = StreetModel(
                    name        = name,
                    district_id = d_id,
                    length_km   = length_km,
                    max_speed   = s_info["max_speed"],
                    is_one_way  = s_info["one_way"],
                )
                db.add(new_street)
                db.flush()
                db.execute(
                    text("UPDATE streets SET geometry = ST_GeomFromText(:wkt, 4326) WHERE id = :id"),
                    {"wkt": wkt, "id": new_street.id}
                )
                print(f"  ➕ [{new_street.id:02d}] {name:<30} {length_km:>5.1f}km  ({len(coords)} pts) [MỚI]")
                inserted += 1

        db.commit()
        print(f"  ✅ ĐỒNG BỘ HOÀN TẤT")
        print(f"     Districts : Giữ nguyên {len(districts)} quận")
        print(f"     Đã xóa   : {deleted_streets} đường ({deleted_traffic:,} traffic records)")
        print(f"     Đã cập nhật: {updated} đường")
        print(f"     Thêm mới  : {inserted} đường")
        print(f"{'='*60}")

        # ── BƯỚC 3: Xóa traffic cũ + cào theo từng ĐOẠN ĐƯỜNG ───────────────
        ingest_all_streets_by_segment(db)

        print(f"\n🎉 Xong! Kiểm tra tại:")
        print(f"   Map : http://localhost:8501")
        print(f"   API : http://localhost:8000/docs")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Lỗi: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
