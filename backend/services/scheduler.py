"""
services/scheduler.py — APScheduler tích hợp với FastAPI

Quản lý lịch cào dữ liệu traffic tự động bằng APScheduler 3.x.

─────────────────────────────────────────────────────────────
  JOBS MẶC ĐỊNH (tự động chạy khi server khởi động):

  1. crawl_traffic_5m     — Cào toàn bộ đường định kỳ mỗi 5 phút
  2. auto_retrain         — Tự động huấn luyện lại model lúc 02:00 hàng ngày

  API quản lý (xem routers/traffic.py):
    GET  /api/traffic/schedule/jobs        Danh sách tất cả job
    POST /api/traffic/schedule/pause       Tạm dừng toàn bộ scheduler
    POST /api/traffic/schedule/resume      Tiếp tục scheduler
    POST /api/traffic/schedule/run-now     Chạy 1 job ngay lập tức
─────────────────────────────────────────────────────────────
"""

import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

log = logging.getLogger("scheduler")

TZ_DANANG = timezone(timedelta(hours=7))

# ─── KHỞI TẠO SCHEDULER ──────────────────────────────────────────────────────

_scheduler = BackgroundScheduler(
    jobstores   = {"default": MemoryJobStore()},
    executors   = {"default": ThreadPoolExecutor(max_workers=2)},
    job_defaults= {
        "coalesce"        : True,   # Gộp nhiều lần missed vào 1 lần chạy
        "max_instances"   : 1,      # Không chạy song song 2 lần cùng 1 job
        "misfire_grace_time": 120,  # Bỏ qua nếu trễ quá 2 phút
    },
    timezone="Asia/Ho_Chi_Minh",
)


# ─── HÀMMÓC CHO TỪNG JOB ─────────────────────────────────────────────────────

def _job_crawl_all(job_id: str, with_weather: bool = True):
    """
    Hàm thực thi thực tế của mỗi scheduled job.
    Tạo session mới, cào toàn bộ đường + thời tiết, đóng session.
    """
    from database import SessionLocal
    from services.ingestion import run_crawl_cycle   # dùng trực tiếp hàm gốc

    log.info(f"⏰ [APScheduler] Job '{job_id}' bắt đầu lúc "
             f"{datetime.now(TZ_DANANG).strftime('%H:%M:%S %d/%m/%Y')}")
    db = SessionLocal()
    try:
        result = run_crawl_cycle(
            db,
            retention_days = 0,          # không tự động xóa dữ liệu (xóa thủ công)
            with_weather   = with_weather,  # True = lưu WeatherSnapshot
        )
        log.info(
            f"✅ [APScheduler] Job '{job_id}' hoàn tất — "
            f"{result.get('streets_success', 0)}/{result.get('streets_total', 0)} đường"
        )
    except Exception as e:
        log.error(f"❌ [APScheduler] Job '{job_id}' lỗi: {e}")
    finally:
        db.close()


def _make_job_func(job_id: str, with_weather: bool = True):
    """Tạo closure để truyền job_id và with_weather vào hàm job."""
    def _fn():
        _job_crawl_all(job_id, with_weather)
    _fn.__name__ = job_id
    return _fn


# ─── ĐĂNG KÝ JOBS MẶC ĐỊNH ───────────────────────────────────────────────────

def _register_default_jobs():
    """
    Đăng ký job mặc định cào dữ liệu định kỳ mỗi 5 phút (UTC+7).
    """
    _scheduler.add_job(
        func     = _make_job_func("crawl_traffic_5m", with_weather=True),
        trigger  = CronTrigger(
            minute = "*/5",       # mỗi 5 phút
            second = "0",
            timezone="Asia/Ho_Chi_Minh",
        ),
        id       = "crawl_traffic_5m",
        name     = "🔄 Cào dữ liệu traffic định kỳ (Mỗi 5 phút)",
        replace_existing=True,
    )

    log.info("📅 [APScheduler] Đã đăng ký job cào định kỳ mỗi 5 phút")

    # ─── JOB RETRAIN (Task #29) ──────────────────────────────────────────────

    def _job_retrain():
        """Auto retrain model mỗi ngày lúc 2h sáng."""
        from ml.train import retrain_and_reload
        from database import SessionLocal

        log.info("⏰ [APScheduler] Auto-retrain job bắt đầu...")
        db = SessionLocal()
        try:
            result = retrain_and_reload(db_session=db)
            if result.get("status") == "success":
                m = result.get("metrics", {})
                log.info(
                    f"✅ [APScheduler] Retrain thành công — "
                    f"F1={m.get('f1_weighted', 0):.3f}, "
                    f"Accuracy={m.get('accuracy', 0):.3f}"
                )
            else:
                log.error(f"❌ [APScheduler] Retrain thất bại: {result.get('error')}")
        except Exception as e:
            log.error(f"❌ [APScheduler] Retrain lỗi: {e}", exc_info=True)
        finally:
            db.close()

    _scheduler.add_job(
        func    = _job_retrain,
        trigger = CronTrigger(
            hour   = 2,
            minute = 0,
            second = 0,
            timezone="Asia/Ho_Chi_Minh",
        ),
        id      = "auto_retrain",
        name    = "🤖 Auto Retrain Model (02:00 mỗi ngày)",
        replace_existing=True,
    )
    log.info("📅 [APScheduler] Đã đăng ký job auto-retrain lúc 2h sáng")




# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def start_scheduler():
    """Khởi động APScheduler — gọi từ FastAPI lifespan startup."""
    _register_default_jobs()
    _scheduler.start()
    log.info("🚀 [APScheduler] Scheduler đã khởi động")


def stop_scheduler():
    """Dừng APScheduler — gọi từ FastAPI lifespan shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("🛑 [APScheduler] Scheduler đã dừng")


def get_scheduler() -> BackgroundScheduler:
    """Trả về instance scheduler (dùng trong router)."""
    return _scheduler


def list_jobs() -> list[dict]:
    """Trả về danh sách tất cả job đang đăng ký."""
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id"          : job.id,
            "name"        : job.name,
            "trigger"     : str(job.trigger),
            "next_run_at" : next_run.strftime("%H:%M:%S %d/%m/%Y +07")
                            if next_run else None,
            "pending"     : job.pending,
        })
    return jobs


def run_job_now(job_id: str) -> bool:
    """
    Kích hoạt chạy ngay 1 job theo ID (không ảnh hưởng lịch định kỳ).
    Trả về True nếu tìm thấy job, False nếu không có.
    """
    job = _scheduler.get_job(job_id)
    if not job:
        return False
    _scheduler.modify_job(job_id, next_run_time=datetime.now(TZ_DANANG))
    log.info(f"▶️ [APScheduler] Kích hoạt chạy ngay job '{job_id}'")
    return True


def add_interval_job(
    job_id: str,
    minutes: int,
    hour_start: int = 0,
    hour_end: int = 23,
) -> dict:
    """
    Thêm job cào interval tuỳ chỉnh.

    Args:
        job_id     : ID duy nhất cho job.
        minutes    : Cào mỗi bao nhiêu phút.
        hour_start : Giờ bắt đầu (0–23, múi giờ Đà Nẵng).
        hour_end   : Giờ kết thúc (0–23, múi giờ Đà Nẵng).

    Returns:
        dict thông tin job vừa thêm.
    """
    trigger = CronTrigger(
        hour     = f"{hour_start}-{hour_end}",
        minute   = f"*/{minutes}",
        second   = "0",
        timezone = "Asia/Ho_Chi_Minh",
    )
    _scheduler.add_job(
        func    = _make_job_func(job_id),
        trigger = trigger,
        id      = job_id,
        name    = f"⚙️ Custom: mỗi {minutes}p ({hour_start}h–{hour_end}h)",
        replace_existing=True,
    )
    log.info(f"➕ [APScheduler] Đã thêm job '{job_id}': mỗi {minutes}p, {hour_start}h–{hour_end}h")
    job = _scheduler.get_job(job_id)
    return {
        "id"         : job.id,
        "name"       : job.name,
        "next_run_at": job.next_run_time.strftime("%H:%M:%S %d/%m/%Y +07")
                       if job.next_run_time else None,
    }


def remove_job(job_id: str) -> bool:
    """Xóa 1 job khỏi scheduler. Trả về True nếu thành công."""
    job = _scheduler.get_job(job_id)
    if not job:
        return False
    _scheduler.remove_job(job_id)
    log.info(f"🗑  [APScheduler] Đã xóa job '{job_id}'")
    return True


def pause_scheduler():
    """Tạm dừng toàn bộ scheduler (giữ nguyên job list)."""
    _scheduler.pause()
    log.info("⏸  [APScheduler] Scheduler đã tạm dừng")


def resume_scheduler():
    """Tiếp tục scheduler sau khi tạm dừng."""
    _scheduler.resume()
    log.info("▶️ [APScheduler] Scheduler đã tiếp tục")


def scheduler_state() -> dict:
    """Trả về trạng thái tổng quan của scheduler."""
    from apscheduler.schedulers.base import STATE_RUNNING, STATE_PAUSED, STATE_STOPPED
    state_map = {
        STATE_RUNNING: "running",
        STATE_PAUSED : "paused",
        STATE_STOPPED: "stopped",
    }
    return {
        "state"    : state_map.get(_scheduler.state, "unknown"),
        "running"  : _scheduler.running,
        "job_count": len(_scheduler.get_jobs()),
    }
