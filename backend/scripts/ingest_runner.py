"""
scripts/ingest_runner.py — Script treo máy cào dữ liệu giao thông liên tục

CÁCH CHẠY:
    docker compose exec backend python scripts/ingest_runner.py

    # Tùy chỉnh interval (phút):
    docker compose exec backend python scripts/ingest_runner.py --interval 30

    # Chạy 1 lần rồi thoát (test):
    docker compose exec backend python scripts/ingest_runner.py --once

LỊCH GỌI API VỚI QUOTA FREE:
    TomTom: 2,500 req/ngày ÷ 49 đường = 51 lần/đường/ngày
    → Interval tối thiểu: 1440 phút ÷ 51 ≈ 28 phút
    → Khuyến nghị: 30 phút (an toàn, còn dư buffer)

    Goong: 1,000 req/ngày (chỉ dùng khi TomTom fail)

TIMELINE CỦA 1 CHU KỲ 30 PHÚT (49 đường):
    ├─ 00:00  Bắt đầu chu kỳ N
    ├─ Gọi TomTom/Goong cho từng đường (delay 1.5s giữa mỗi đường)
    │          49 đường × 1.5s = ~75 giây ≈ 1.25 phút thu thập
    ├─ 01:15  Xong, commit DB
    ├─ Ngủ 28 phút 45 giây
    └─ 30:00  Bắt đầu chu kỳ N+1

TỔNG REQUEST THEO INTERVAL:
    30 phút → 48 chu kỳ/ngày  × 49 đường = 2,352 req TomTom ✓ (< 2,400 limit)
    60 phút → 24 chu kỳ/ngày  × 49 đường = 1,176 req TomTom ✓ (rất an toàn)
"""

import sys, os, time, argparse, logging
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from models import Street
from services.ingestion import run_one_cycle, tomtom_quota, goong_quota

# ─── LOGGING ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ingest_runner")

# ─── DB ───────────────────────────────────────────────────────────────────────
DATABASE_URL = (
    f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

TZ_DANANG = timezone(timedelta(hours=7))


def print_banner(interval_minutes: int, n_streets: int):
    """In thông tin khởi động."""
    daily_cycles  = 1440 // interval_minutes
    tomtom_daily  = daily_cycles * n_streets
    cycle_seconds = n_streets * 1.5

    print("\n" + "="*60)
    print("  🚦 INGEST RUNNER — Cào dữ liệu giao thông Đà Nẵng")
    print("="*60)
    print(f"  Số đường        : {n_streets}")
    print(f"  Interval        : {interval_minutes} phút")
    print(f"  Chu kỳ/ngày     : {daily_cycles}")
    print(f"  TomTom/ngày     : ~{tomtom_daily} req (limit: 2,400)")
    print(f"  Thời gian/chu kỳ: ~{cycle_seconds:.0f}s ({n_streets}đường × 1.5s)")
    print(f"  Bắt đầu lúc     : {datetime.now(TZ_DANANG).strftime('%H:%M:%S %d/%m/%Y')} +07:00")
    print("="*60)

    if not settings.tomtom_api_key:
        print("\n  ⚠️  TOMTOM_API_KEY chưa cấu hình trong .env!")
        print("     Chỉ dùng Goong (hoặc bỏ qua nếu Goong cũng chưa cấu hình)\n")
    if not settings.goong_api_key:
        print("  ⚠️  GOONG_API_KEY chưa cấu hình trong .env!\n")


def run(interval_minutes: int = 30, run_once: bool = False):
    """Vòng lặp chính — chạy mãi cho đến khi Ctrl+C."""
    db = Session()
    try:
        streets = db.query(Street).order_by(Street.id).all()
        if not streets:
            log.error("Chưa có đường nào trong DB. Chạy seed_danang.py trước!")
            return

        print_banner(interval_minutes, len(streets))

        cycle = 0
        while True:
            cycle += 1
            now_vn = datetime.now(TZ_DANANG).strftime("%H:%M:%S %d/%m")
            log.info(f"\n{'─'*60}")
            log.info(f"  Chu kỳ #{cycle} — {now_vn} +07:00")
            log.info(f"  TomTom còn: {tomtom_quota.remaining} | Goong còn: {goong_quota.remaining}")
            log.info(f"{'─'*60}")

            t_start = time.time()
            run_one_cycle(streets, db, delay_seconds=1.5)
            elapsed = time.time() - t_start

            if run_once:
                log.info("✅ Chạy 1 lần xong (--once). Thoát.")
                break

            # Tính thời gian nghỉ: interval - thời gian đã dùng
            sleep_secs = max(0, interval_minutes * 60 - elapsed)
            next_run = datetime.now(TZ_DANANG) + timedelta(seconds=sleep_secs)

            log.info(
                f"\n  Xong trong {elapsed:.1f}s. "
                f"Chu kỳ tiếp: {next_run.strftime('%H:%M:%S')} +07:00 "
                f"(nghỉ {sleep_secs/60:.1f} phút)"
            )

            # Ngủ theo từng đoạn ngắn để Ctrl+C có thể dừng ngay
            slept = 0
            while slept < sleep_secs:
                time.sleep(min(5, sleep_secs - slept))
                slept += 5

    except KeyboardInterrupt:
        log.info("\n⛔ Dừng bởi Ctrl+C. Thoát sạch.")
    finally:
        db.close()


# ─── ENTRY POINT ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Cào dữ liệu giao thông từ TomTom & Goong liên tục"
    )
    parser.add_argument(
        "--interval", type=int, default=30,
        help="Interval giữa các chu kỳ (phút). Mặc định: 30"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Chỉ chạy 1 chu kỳ rồi thoát (để test)"
    )
    args = parser.parse_args()

    if args.interval < 10:
        print("❌ Interval tối thiểu 10 phút để không vượt quota TomTom!")
        sys.exit(1)

    run(interval_minutes=args.interval, run_once=args.once)
