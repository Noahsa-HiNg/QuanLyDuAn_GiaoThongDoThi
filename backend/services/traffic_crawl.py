"""
services/traffic_crawl.py — Cào dữ liệu traffic 1 lần duy nhất

Dùng chung cho:
  - API endpoint  : POST /api/traffic/crawl
  - Scheduler     : traffic_scheduler.py (gọi hàm này mỗi 30 phút)

Hàm crawl_all_streets(db) trả về dict tóm tắt kết quả.
"""

import json
import time
import logging
import requests as _req

from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

from config import settings
from services.ingestion import (
    fetch_tomtom, fetch_goong, calc_congestion_level,
    tomtom_quota, goong_quota,
)
from services import cache as cache_svc   # ← Fix #1: invalidate cache sau crawl
from utils.geometry import split_path_into_zones, calc_road_length_m

# ─── TIMEZONE VIỆT NAM ────────────────────────────────────────────────────────
TZ_VN = timezone(timedelta(hours=7))


def _now_vn() -> datetime:
    return datetime.now(TZ_VN)


# ─── Fix #2: _call_tomtom() ĐÃ XÓA ──────────────────────────────────────────
# Dùng fetch_tomtom() từ services/ingestion.py — source of truth duy nhất.
# fetch_tomtom() đã xử lý đầy đủ: 403, 429, key rotation, retry all keys.


# ─── HÀM CHÍNH: Cào tất cả đường đúng 1 lần ─────────────────────────────────
def crawl_all_streets(db: Session) -> dict:
    """
    Cào dữ liệu traffic của TẤT CẢ đường — đúng 1 lần.

    Quy trình:
        1. Xóa bản ghi cũ hơn 2 giờ
        2. Với mỗi đường → split_path_into_zones → gọi TomTom tại midpoint
        3. Fallback Goong nếu TomTom thất bại
        4. Lưu TrafficData với timestamp giờ VN

    Trả về:
        {
          "streets_total"   : int,   # Tổng số đường trong DB
          "streets_success" : int,   # Số đường cào thành công
          "records_saved"   : int,   # Tổng bản ghi đã lưu
          "quota_remaining" : int,   # Quota TomTom còn lại
          "duration_seconds": float, # Thời gian chạy
          "timestamp"       : str,   # Giờ bắt đầu (VN)
          "errors"          : list,  # Danh sách đường bị lỗi
        }
    """
    from models import Street, TrafficData

    log = logging.getLogger("traffic_crawl")
    started_at = _now_vn()
    t0 = time.time()
    errors: list[str] = []

    # ── Kiểm tra key TomTom ──────────────────────────────────────────────────
    keys = settings.tomtom_keys_list
    if not keys:
        return {
            "streets_total"   : 0,
            "streets_success" : 0,
            "records_saved"   : 0,
            "quota_remaining" : 0,
            "duration_seconds": 0.0,
            "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
            "errors"          : ["Không có TOMTOM_API_KEY trong .env"],
        }

    if tomtom_quota.is_exhausted and goong_quota.is_exhausted:
        return {
            "streets_total"   : 0,
            "streets_success" : 0,
            "records_saved"   : 0,
            "quota_remaining" : 0,
            "duration_seconds": 0.0,
            "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
            "errors"          : ["Cả TomTom và Goong đều hết quota hôm nay"],
        }

    log.info(f"🚀 Bắt đầu crawl lúc {started_at.strftime('%H:%M:%S %d/%m/%Y +07')}")
    log.info(f"   TomTom: {len(keys)} key(s) | Quota: {tomtom_quota.summary}")

    # ── Xóa traffic cũ hơn 2 giờ ────────────────────────────────────────────
    cutoff = _now_vn() - timedelta(hours=2)
    deleted = db.execute(
        text("DELETE FROM traffic_data WHERE timestamp < :cutoff"),
        {"cutoff": cutoff}
    ).rowcount
    db.commit()
    if deleted:
        log.info(f"🗑  Đã xóa {deleted:,} bản ghi cũ hơn 2 giờ")

    # ── Lấy danh sách đường có geometry ─────────────────────────────────────
    streets = db.query(Street).all()
    if not streets:
        return {
            "streets_total"   : 0,
            "streets_success" : 0,
            "records_saved"   : 0,
            "quota_remaining" : tomtom_quota.remaining,
            "duration_seconds": round(time.time() - t0, 2),
            "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
            "errors"          : ["Không có đường nào trong DB — chạy sync_streets.py trước"],
        }

    ts_now       = _now_vn()
    LABEL        = {0: "🟢", 1: "🟡", 2: "🔴"}
    success_cnt  = 0
    total_saved  = 0

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
            errors.append(f"{street.name}: chưa có geometry")
            continue

        coords = json.loads(row.coords) if isinstance(row.coords, str) else row.coords
        if not coords or len(coords) < 2:
            errors.append(f"{street.name}: geometry không hợp lệ")
            continue

        zones    = split_path_into_zones(coords)
        length_m = calc_road_length_m(coords)
        n_zones  = len(zones)
        saved_n  = 0
        zone_results = []

        for zone in zones:
            seg_idx = zone["segment_idx"]
            lat     = zone["mid_lat"]
            lon     = zone["mid_lon"]

            # TomTom (tự rotate key khi 403/429) → fallback Goong
            # Fix #2: Dùng fetch_tomtom() từ ingestion.py (không copy lại)
            result = fetch_tomtom(lat, lon)
            src    = "tomtom"
            if result is None:
                result = fetch_goong(lat, lon, max_speed)
                src    = "goong"
            if result is None:
                log.debug(f"  ✗ {street.name} zone {seg_idx}: cả 2 API thất bại")
                continue

            avg_speed  = result["avg_speed"]
            ref_speed  = result.get("free_flow_speed") or max_speed
            congestion = calc_congestion_level(avg_speed, ref_speed)

            db.add(TrafficData(
                street_id        = street.id,
                segment_idx      = seg_idx,
                timestamp        = ts_now,
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
            errors.append(f"{street.name}: không cào được dữ liệu")

        time.sleep(0.8)   # Delay nhẹ giữa 2 đường

    db.commit()

    # ── Fix #1: Xóa cache Redis sau crawl để lần gọi tiếp theo đọc data mới ──
    cache_svc.invalidate_traffic()
    log.info("🗑  Cache Redis đã được xóa — lần gọi tiếp theo sẽ đọc từ DB")

    duration = round(time.time() - t0, 2)
    log.info(
        f"✅ Hoàn tất — {success_cnt}/{len(streets)} đường | "
        f"{total_saved} bản ghi | {duration}s | Quota còn: {tomtom_quota.remaining}"
    )

    return {
        "streets_total"   : len(streets),
        "streets_success" : success_cnt,
        "records_saved"   : total_saved,
        "quota_remaining" : tomtom_quota.remaining,
        "duration_seconds": duration,
        "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
        "errors"          : errors,
    }
