"""
services/traffic_scheduler.py — Standalone Scheduler Process
Chạy như một process riêng trong Docker Compose (service: scheduler).

Mục đích:
  - Cào dữ liệu traffic từ TomTom mỗi 30 phút (giờ thường)
  - Cào mỗi 10 phút trong giờ cao điểm (sáng + chiều)
  - Hoàn toàn độc lập với FastAPI backend process

Khởi động:
  docker compose up scheduler          ← tự chạy trong Docker
  python services/traffic_scheduler.py ← chạy thủ công

APScheduler bên trong FastAPI (main.py) cũng đang chạy, 
nhưng service này là backup standalone để đảm bảo data luôn được cào
ngay cả khi API server bị khởi động lại.
"""

import logging
import time
import sys
import os

# ── Đảm bảo import được backend modules ──────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHEDULER] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("traffic_scheduler")


def run_crawl():
    """Chạy 1 chu kỳ cào dữ liệu traffic."""
    try:
        from database import SessionLocal
        from services.ingestion import run_crawl_cycle

        db = SessionLocal()
        try:
            result = run_crawl_cycle(db, retention_days=30, with_weather=False)  # weather_snapshots chưa có trong DB
            success = result.get("streets_success", 0)
            total   = result.get("streets_total", 0)
            log.info(f"✅ Crawl hoàn tất: {success}/{total} đường")
        finally:
            db.close()

    except Exception as e:
        log.error(f"❌ Crawl lỗi: {e}")


def main():
    log.info("🚀 Traffic Scheduler standalone khởi động")

    # Crawl ngay lần đầu khi start
    log.info("▶️  Crawl lần đầu ngay lúc khởi động...")
    run_crawl()

    # Lịch crawl đơn giản theo interval — APScheduler phức tạp hơn ở backend
    INTERVAL_MINUTES = 30  # Mặc định 30 phút
    log.info(f"⏰ Sẽ cào lại mỗi {INTERVAL_MINUTES} phút")

    while True:
        try:
            time.sleep(INTERVAL_MINUTES * 60)
            log.info("🔄 Bắt đầu chu kỳ cào...")
            run_crawl()
        except KeyboardInterrupt:
            log.info("🛑 Scheduler dừng theo yêu cầu")
            break
        except Exception as e:
            log.error(f"❌ Lỗi vòng lặp scheduler: {e}")
            time.sleep(60)  # Chờ 1 phút rồi thử lại


if __name__ == "__main__":
    main()
