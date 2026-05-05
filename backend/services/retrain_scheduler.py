# backend/services/retrain_scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


async def _run_retrain():
    """Job được gọi tự động lúc 2h sáng mỗi ngày."""
    logger.info("⏰ [Scheduler] 2h sáng — bắt đầu auto-retrain...")
    try:
        # Import ở đây để tránh circular import
        from ml.train import retrain_and_reload
        from database import SessionLocal

        db = SessionLocal()
        try:
            result = retrain_and_reload(db_session=db)
            if result["status"] == "success":
                m = result["metrics"]
                logger.info(
                    f"✅ [Scheduler] Retrain thành công — "
                    f"F1={m['f1_weighted']:.3f}, "
                    f"Accuracy={m['accuracy']:.3f}, "
                    f"RMSE={m['rmse']:.3f}"
                )
            else:
                logger.error(f"❌ [Scheduler] Retrain thất bại: {result['error']}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"❌ [Scheduler] Lỗi không mong đợi: {e}", exc_info=True)


def create_retrain_scheduler() -> AsyncIOScheduler:
    """Tạo và return scheduler — A gọi hàm này trong main.py."""
    scheduler = AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")
    scheduler.add_job(
        _run_retrain,
        trigger=CronTrigger(hour=2, minute=0),   # 2:00 AM Việt Nam
        id="auto_retrain",
        name="Auto Retrain Model",
        replace_existing=True,
        misfire_grace_time=600,   # nếu miss, chạy bù trong vòng 10 phút
    )
    logger.info("📅 [Scheduler] Auto-retrain job đã đăng ký — chạy lúc 02:00 VN mỗi ngày")
    return scheduler