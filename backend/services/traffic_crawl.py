"""
services/traffic_crawl.py — Cào dữ liệu traffic theo 3 chế độ

─────────────────────────────────────────────────────────────
  CHẾ ĐỘ 1: crawl_all_once(db)
    Cào toàn bộ tất cả đường → 1 lần duy nhất → trả về kết quả.
    Được gọi từ: POST /api/traffic/crawl

  CHẾ ĐỘ 2: crawl_all_loop(db_factory, interval_seconds, stop_event)
    Cào toàn bộ đường → lặp lại định kỳ → cho đến khi stop_event.set().
    Được gọi từ: POST /api/traffic/crawl/loop/start
    Dừng lại từ : POST /api/traffic/crawl/loop/stop

  CHẾ ĐỘ 3: crawl_one_street(db, street_id)
    Cào đúng 1 đường duy nhất → 1 lần → trả về kết quả.
    Được gọi từ: POST /api/traffic/crawl/{street_id}
─────────────────────────────────────────────────────────────

Lưu ý:
  - Không xóa lịch sử (retention_days=0) để bảo toàn dataset ML.
  - Không fetch weather (with_weather=False) để tiết kiệm API call.
  - Toàn bộ logic thực tế nằm ở: services/ingestion.
"""

import logging
import threading
import time as _time
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional

from sqlalchemy.orm import Session

from services.ingestion import (
    TZ_DANANG,
    tomtom_quota,
    goong_quota,
    ingest_street,
    _make_error_result,
)
from services import cache as cache_svc
from models import Street

log = logging.getLogger("traffic_crawl")

# ─── CHẾ ĐỘ 1: CÀO TOÀN BỘ 1 LẦN ───────────────────────────────────────────

def crawl_all_once(db: Session) -> dict:
    """
    Cào toàn bộ tất cả đường đúng 1 lần.

    Không xóa dữ liệu lịch sử (bảo toàn dataset ML).
    Trả về dict tóm tắt: streets_total, streets_success, records_saved, ...
    """
    log.info("🔔 [CHẾ ĐỘ 1] Cào toàn bộ đường — 1 lần")
    return _run_single_cycle(db, label="[1-lần]")


# ─── CHẾ ĐỘ 2: CÀO TOÀN BỘ LẶP LẠI ─────────────────────────────────────────

def crawl_all_loop(
    db_factory: Callable[[], Session],
    interval_seconds: int = 600,
    stop_event: Optional[threading.Event] = None,
    on_cycle_done: Optional[Callable[[dict], None]] = None,
) -> None:
    """
    Cào toàn bộ đường — lặp đi lặp lại mỗi `interval_seconds` giây.

    Chạy trên một thread riêng, thoát khi stop_event.set() được gọi.

    Args:
        db_factory       : Hàm trả về SQLAlchemy Session mới (để tạo session mỗi chu kỳ).
        interval_seconds : Khoảng cách giữa 2 chu kỳ (mặc định 10 phút).
        stop_event       : threading.Event — set() để dừng vòng lặp.
        on_cycle_done    : Callback tùy chọn — nhận dict kết quả mỗi chu kỳ.
    """
    if stop_event is None:
        stop_event = threading.Event()

    cycle = 0
    log.info(
        f"🔁 [CHẾ ĐỘ 2] Bắt đầu cào vòng lặp — interval={interval_seconds}s"
    )

    while not stop_event.is_set():
        cycle += 1
        log.info(f"🔁 [Vòng {cycle}] Bắt đầu chu kỳ cào...")
        db = db_factory()
        try:
            result = _run_single_cycle(db, label=f"[loop #{cycle}]")
            if on_cycle_done:
                on_cycle_done(result)
        finally:
            db.close()

        # Chờ interval, nhưng kiểm tra stop_event mỗi giây
        log.info(f"⏳ [Vòng {cycle}] Chờ {interval_seconds}s trước chu kỳ tiếp theo...")
        for _ in range(interval_seconds):
            if stop_event.is_set():
                break
            _time.sleep(1)

    log.info("🛑 [CHẾ ĐỘ 2] Vòng lặp cào đã dừng.")


# ─── CHẾ ĐỘ 3: CÀO 1 ĐƯỜNG 1 LẦN ────────────────────────────────────────────

def crawl_one_street(db: Session, street_id: int) -> dict:
    """
    Cào đúng 1 đường duy nhất, 1 lần.

    Args:
        db        : SQLAlchemy Session.
        street_id : ID của đường cần cào.

    Returns:
        dict tóm tắt gồm: street_id, street_name, success, records_saved,
                          quota_remaining, duration_seconds, timestamp, error.
    """
    started_at = datetime.now(TZ_DANANG)
    t0 = _time.time()

    log.info(f"🔔 [CHẾ ĐỘ 3] Cào 1 đường — street_id={street_id}")

    # Kiểm tra quota
    if not tomtom_quota._keys:
        msg = "Không có TOMTOM_API_KEY trong .env"
        log.error(f"❌ {msg}")
        return _single_error(started_at, street_id, None, msg)

    if tomtom_quota.is_exhausted and goong_quota.is_exhausted:
        msg = "Cả TomTom và Goong đều hết quota hôm nay"
        log.warning(f"⛔ {msg}")
        return _single_error(started_at, street_id, None, msg)

    # Lấy thông tin đường
    street = db.query(Street).filter(Street.id == street_id).first()
    if not street:
        msg = f"Không tìm thấy đường với id={street_id}"
        log.warning(f"❌ {msg}")
        return _single_error(started_at, street_id, None, msg)

    # Cào
    ok = ingest_street(street, db)

    # Commit + invalidate cache
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        log.error(f"❌ Lỗi commit DB: {e}")
        raise

    cache_svc.invalidate_traffic()

    duration = round(_time.time() - t0, 2)
    log.info(
        f"{'✅' if ok else '❌'} [Đường: {street.name}] "
        f"{'Thành công' if ok else 'Thất bại'} — {duration}s"
    )

    return {
        "street_id"       : street.id,
        "street_name"     : street.name,
        "success"         : ok,
        "records_saved"   : 1 if ok else 0,
        "quota_remaining" : tomtom_quota.remaining,
        "duration_seconds": duration,
        "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
        "error"           : None if ok else "Không lấy được dữ liệu từ API",
    }


# ─── HELPERS NỘI BỘ ──────────────────────────────────────────────────────────

def _run_single_cycle(db: Session, label: str = "") -> dict:
    """
    Chạy 1 chu kỳ cào toàn bộ đường — dùng chung cho cả chế độ 1 và 2.

    Không xóa lịch sử (retention_days=0), không fetch weather.
    """
    started_at = datetime.now(TZ_DANANG)
    t0 = _time.time()
    errors: list[str] = []

    # Kiểm tra key và quota
    if not tomtom_quota._keys:
        return _make_error_result(started_at, "Không có TOMTOM_API_KEY trong .env")

    if tomtom_quota.is_exhausted and goong_quota.is_exhausted:
        log.warning(f"⛔ {label} Cả TomTom và Goong đều hết quota — bỏ qua chu kỳ")
        return _make_error_result(started_at, "Cả TomTom và Goong đều hết quota hôm nay")

    # Lấy danh sách đường
    streets = db.query(Street).all()
    if not streets:
        return _make_error_result(
            started_at, "Không có đường nào trong DB — chạy sync_streets.py trước"
        )

    log.info(
        f"🌐 {label} Cào {len(streets)} đường lúc "
        f"{started_at.strftime('%H:%M:%S %d/%m/%Y +07')} | "
        f"Quota TomTom: {tomtom_quota.remaining} req"
    )

    success_cnt = 0
    for street in streets:
        ok = ingest_street(street, db)
        if ok:
            success_cnt += 1
        else:
            errors.append(street.name)
        _time.sleep(1.0)   # Delay nhẹ giữa 2 đường

    # Commit + invalidate cache
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        log.error(f"❌ {label} Lỗi commit DB: {e}")
        raise

    cache_svc.invalidate_traffic()
    log.info(f"🗑  {label} Cache Redis đã xóa — lần gọi tiếp theo đọc từ DB")

    duration = round(_time.time() - t0, 2)
    log.info(
        f"✅ {label} Hoàn tất — {success_cnt}/{len(streets)} đường | "
        f"{duration}s | Quota còn: {tomtom_quota.remaining}"
    )

    return {
        "streets_total"   : len(streets),
        "streets_success" : success_cnt,
        "records_saved"   : success_cnt,
        "quota_remaining" : tomtom_quota.remaining,
        "duration_seconds": duration,
        "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
        "errors"          : errors,
    }


def _single_error(
    started_at: datetime, street_id: int, street_name: Optional[str], msg: str
) -> dict:
    """Dict lỗi chuẩn cho crawl_one_street."""
    return {
        "street_id"       : street_id,
        "street_name"     : street_name,
        "success"         : False,
        "records_saved"   : 0,
        "quota_remaining" : tomtom_quota.remaining,
        "duration_seconds": 0.0,
        "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
        "error"           : msg,
    }


# ─── BACKWARD COMPAT (tên cũ vẫn hoạt động) ──────────────────────────────────
# Router cũ gọi crawl_all_streets() → forward sang crawl_all_once()
def crawl_all_streets(db: Session) -> dict:
    """Alias backward-compatible — sử dụng crawl_all_once() thay thế."""
    return crawl_all_once(db)
