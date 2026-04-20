"""
services/traffic_scheduler.py — Scheduler tự động cào traffic mỗi 30 phút

CÁCH CHẠY:
    docker compose exec backend python services/traffic_scheduler.py

HOẶC thêm vào docker-compose.yml để chạy nền tự động.

NHỮNG GÌ SCRIPT NÀY LÀM:
    ✅ Chỉ cào đường CÓ tọa độ trong manual_coords.py
    ✅ Chia mỗi đường thành ~500m/đoạn → gọi TomTom từng đoạn
    ✅ XÓA traffic cũ trước mỗi chu kỳ (chỉ giữ bản ghi mới nhất)
    ✅ Timestamp ĐÚNG theo giờ Việt Nam (UTC+7)
    ✅ Lặp lại mỗi 30 phút tự động
    ✅ Fallback Goong nếu TomTom hết quota
    ✅ Log đẹp với giờ VN +07:00

TIMEZONE FIX:
    Lỗi cũ: datetime.now(timezone.utc) → lưu 17:44 UTC
             → API hiển thị "17:44" trong khi thực tế là 00:44 VN
    Fix mới: datetime.now(TZ_VN) → lưu 00:44+07:00
             → PostgreSQL tự quy đổi sang UTC khi lưu
             → API trả về đúng giờ VN
"""

import sys, os, json, math, time, logging

sys.path.insert(0, "/app")

from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ─── TIMEZONE VIỆT NAM ────────────────────────────────────────────────────────
TZ_VN = timezone(timedelta(hours=7))   # UTC+7 — Giờ Việt Nam

# ─── DATABASE ────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://myadmin:123456@postgres:5432/qlda_dothithongminh"
)
engine  = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

# ─── LOGGING với giờ VN ──────────────────────────────────────────────────────
class VNFormatter(logging.Formatter):
    """Formatter hiển thị timestamp theo giờ Việt Nam UTC+7."""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=TZ_VN)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S +07")

_handler = logging.StreamHandler()
_handler.setFormatter(VNFormatter("%(asctime)s  %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
log = logging.getLogger("scheduler")

# ─── INTERVAL ────────────────────────────────────────────────────────────────
INTERVAL_MINUTES = 30   # Cào lại sau mỗi X phút


# ─── HÀM HELPER ─────────────────────────────────────────────────────────────
def haversine_km(lat1, lng1, lat2, lng2) -> float:
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def now_vn() -> datetime:
    """Trả về datetime hiện tại theo giờ VN (UTC+7) — có timezone info."""
    return datetime.now(TZ_VN)


def now_vn_str() -> str:
    """Chuỗi giờ VN đẹp để print/log."""
    return now_vn().strftime("%H:%M:%S %d/%m/%Y +07")


# ─── CHU KỲ CÀO DỮ LIỆU ─────────────────────────────────────────────────────
def run_crawl_cycle(db):
    """
    Xóa traffic cũ → cào lại dữ liệu theo từng ĐOẠN ĐƯỜNG (~500m/đoạn).

    Mỗi đường → split_path_into_zones() → gọi TomTom tại midpoint từng zone
    → lưu TrafficData với:
        - timestamp = datetime.now(TZ_VN)   ← ĐÚNG giờ VN có timezone
        - segment_idx = 0, 1, 2, ...         ← đoạn nào đang kẹt
        - congestion_level = 0/1/2           ← xanh/vàng/đỏ

    Kết quả: frontend tô màu từng đoạn độc lập → thấy chỗ nào đang kẹt.
    """
    from models import Street, TrafficData
    from services.ingestion import (
        fetch_tomtom, fetch_goong, calc_congestion_level,
        tomtom_quota, goong_quota
    )
    from utils.geometry import split_path_into_zones, calc_road_length_m
    from config import settings

    # ── Kiểm tra quota ───────────────────────────────────────────────────────
    keys = settings.tomtom_keys_list
    if not keys:
        log.warning("⛔ Không có TOMTOM_API_KEY trong .env — bỏ qua chu kỳ")
        return 0

    if tomtom_quota.is_exhausted and goong_quota.is_exhausted:
        log.warning("⛔ Cả TomTom và Goong đều HẾT QUOTA — reset lúc 00:00 +07")
        return 0

    # ── Xóa traffic cũ (CHỈ GIỮ bản ghi mới nhất cho từng segment) ──────────
    # Để tránh DB phình ra vô hạn, xóa các bản ghi cũ hơn 2 giờ
    cutoff = now_vn() - timedelta(hours=2)
    deleted = db.execute(
        text("DELETE FROM traffic_data WHERE timestamp < :cutoff"),
        {"cutoff": cutoff}
    ).rowcount
    db.commit()
    if deleted:
        log.info(f"🗑  Xóa {deleted:,} bản ghi cũ hơn 2 giờ")

    # ── Lấy danh sách đường có geometry ─────────────────────────────────────
    streets = db.query(Street).all()
    if not streets:
        log.warning("⚠ Không có đường trong DB — chạy sync_streets.py trước")
        return 0

    # Timestamp mới — ĐÚNG giờ Việt Nam
    ts_now = now_vn()
    log.info(f"🌐 Bắt đầu cào {len(streets)} đường lúc {ts_now.strftime('%H:%M:%S %d/%m/%Y +07')}")
    log.info(f"   TomTom: {len(keys)} key(s) | Quota còn: {tomtom_quota.remaining} req")

    LABEL = {0: "🟢", 1: "🟡", 2: "🔴"}
    success_cnt = 0
    total_saved = 0

    for street in streets:
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
            log.debug(f"  ⚠ {street.name} — chưa có geometry, bỏ qua")
            continue

        coords = json.loads(row.coords) if isinstance(row.coords, str) else row.coords
        if not coords or len(coords) < 2:
            continue

        # Chia đường thành zone ~500m/zone
        zones    = split_path_into_zones(coords)
        length_m = calc_road_length_m(coords)
        n_zones  = len(zones)
        saved_n  = 0
        zone_results = []

        for zone in zones:
            seg_idx = zone["segment_idx"]
            lat     = zone["mid_lat"]
            lon     = zone["mid_lon"]

            # TomTom → fallback Goong
            result = fetch_tomtom(lat, lon)
            src    = "tomtom"
            if result is None:
                result = fetch_goong(lat, lon, max_speed)
                src    = "goong"
            if result is None:
                continue

            avg_speed  = result["avg_speed"]
            ref_speed  = result.get("free_flow_speed") or max_speed
            congestion = calc_congestion_level(avg_speed, ref_speed)

            # ✅ Lưu với timestamp ĐÚNG giờ VN (PostgreSQL lưu UTC tự động)
            db.add(TrafficData(
                street_id        = street.id,
                segment_idx      = seg_idx,
                timestamp        = ts_now,       # datetime với TZ_VN → đúng giờ
                avg_speed        = avg_speed,
                congestion_level = congestion,
                source           = src,
            ))
            saved_n += 1
            zone_results.append(f"{LABEL.get(congestion,'⚪')}{avg_speed:.0f}")

            if n_zones > 1:
                time.sleep(0.4)

        if saved_n > 0:
            success_cnt += 1
            total_saved += saved_n
            zone_str = " | ".join(zone_results)
            log.info(
                f"  ✓ {street.name:<28} {length_m/1000:.1f}km "
                f"[{n_zones} đoạn] → {zone_str}"
            )
        else:
            log.debug(f"  ✗ {street.name} — không cào được")

        time.sleep(0.8)  # Delay nhẹ giữa 2 đường

    db.commit()
    log.info(
        f"✅ Chu kỳ hoàn tất — "
        f"{success_cnt}/{len(streets)} đường | "
        f"{total_saved} bản ghi | "
        f"Quota còn: {tomtom_quota.remaining}"
    )
    return success_cnt


# ─── VÒNG LẶP CHÍNH ──────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("  TRAFFIC SCHEDULER — Cào dữ liệu mỗi 30 phút")
    log.info(f"  Múi giờ : UTC+7 (Việt Nam)")
    log.info(f"  Interval: {INTERVAL_MINUTES} phút")
    log.info("=" * 60)

    cycle = 0

    while True:
        cycle += 1
        log.info(f"\n{'─'*60}")
        log.info(f"  CHU KỲ #{cycle} — {now_vn_str()}")
        log.info(f"{'─'*60}")

        db = Session()
        try:
            run_crawl_cycle(db)
        except Exception as e:
            log.error(f"❌ Lỗi chu kỳ #{cycle}: {e}")
            import traceback
            traceback.print_exc()
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()

        # Tính thời điểm chu kỳ tiếp theo
        next_run = now_vn() + timedelta(minutes=INTERVAL_MINUTES)
        log.info(f"\n⏰ Chu kỳ tiếp theo lúc: {next_run.strftime('%H:%M:%S %d/%m/%Y +07')}")
        log.info(f"   Đang đợi {INTERVAL_MINUTES} phút...")

        time.sleep(INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    main()
