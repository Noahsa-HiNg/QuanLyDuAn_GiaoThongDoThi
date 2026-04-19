"""
data/seed_traffic.py — Sinh mock traffic data cho 50 đường Đà Nẵng

CÁCH CHẠY:
    docker compose exec backend python data/seed_traffic.py

MỤC ĐÍCH:
    Tạo dữ liệu giao thông giả lập (mock) để:
    1. Test API /api/traffic mà không cần TomTom key
    2. Train AI model với 7 ngày dữ liệu lịch sử
    3. Demo ứng dụng trong báo cáo

CHIẾN LƯỢC SINH DỮ LIỆU THỰC TẾ:
    - Mô phỏng 2 đợt kẹt xe cao điểm thực tế Đà Nẵng:
        + Sáng: 7:00 – 9:00 (đi làm)
        + Chiều: 16:30 – 18:30 (tan làm)
    - Ban đêm (22:00–5:00): thông thoáng, speed cao
    - Cuối tuần: giảm 30% lưu lượng so với ngày thường
    - Mỗi đường có max_speed riêng → tốc độ thực tế dao động theo

LƯỢNG DỮ LIỆU:
    50 đường × 24 bản ghi/ngày × 7 ngày = 8.400 bản ghi
    (1 bản ghi/giờ thay vì 1 bản ghi/phút để tránh quá nhiều)
"""

import sys, os, random
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "/app")
from models import Street, TrafficData

# ─── CONFIG ───────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://myadmin:123456@postgres:5432/qlda_dothithongminh"
)
DAYS_BACK    = 7     # Sinh dữ liệu 7 ngày trước đến hiện tại
INTERVAL_MIN = 60    # Cách nhau 60 phút mỗi bản ghi (= 24 bản ghi/ngày/đường)

# Múi giờ Đà Nẵng: UTC+7
TZ_DANANG = timezone(timedelta(hours=7))

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)


# ─── MÔ HÌNH GIỜ CAO ĐIỂM ─────────────────────────────────────────────────────
def get_congestion_factor(hour: int, is_weekend: bool) -> float:
    """
    Trả về hệ số ùn tắc (0.0 → 1.0) theo giờ ĐÀ NẴNG (UTC+7) và ngày trong tuần.

    `hour` được truyền vào là giờ địa phương Đà Nẵng, không phải UTC.
    Càng cao → đường càng kẹt → avg_speed càng thấp.

    Mô hình giao thông Đà Nẵng (giờ địa phương):
        Cao điểm sáng  (7-9h)    : factor = 0.85–0.95
        Cao điểm chiều (16:30-18:30): factor = 0.80–0.92
        Giờ bình thường (9-16:30): factor = 0.30–0.55
        Ban đêm (22-5h)          : factor = 0.05–0.15
        Cuối tuần: giảm 30%
    """
    # Định nghĩa profile ùn tắc theo từng giờ (0-23)
    hourly_base = {
         0: 0.05,  1: 0.05,  2: 0.05,  3: 0.05,  4: 0.08,
         5: 0.15,  6: 0.45,  7: 0.85,  8: 0.92,  9: 0.60,
        10: 0.40, 11: 0.35, 12: 0.50, 13: 0.40, 14: 0.35,
        15: 0.45, 16: 0.75, 17: 0.90, 18: 0.88, 19: 0.60,
        20: 0.40, 21: 0.25, 22: 0.12, 23: 0.08,
    }

    factor = hourly_base.get(hour, 0.3)

    # Cuối tuần: giảm 30% ùn tắc (ít xe hơn ngày thường)
    if is_weekend:
        factor *= 0.7

    # Thêm nhiễu ngẫu nhiên ±10% để dữ liệu trông tự nhiên hơn
    noise = random.uniform(-0.10, 0.10)
    return max(0.02, min(0.98, factor + noise))


def calc_congestion_level(avg_speed: float, max_speed: int) -> int:
    """
    Tính mức độ ùn tắc từ tốc độ thực tế và tốc độ giới hạn.

    Theo chuẩn đã định nghĩa trong models/traffic_data.py:
      0 = Xanh  (thông thoáng): avg_speed >= 70% max_speed
      1 = Vàng  (chậm)        : avg_speed 40–70% max_speed
      2 = Đỏ    (kẹt xe)      : avg_speed < 40% max_speed
    """
    ratio = avg_speed / max_speed if max_speed > 0 else 0
    if ratio >= 0.70:
        return 0   # Xanh
    elif ratio >= 0.40:
        return 1   # Vàng
    else:
        return 2   # Đỏ


# ─── SEED CHÍNH ───────────────────────────────────────────────────────────────
def seed_traffic():
    db = Session()
    try:
        # Kiểm tra đã có dữ liệu chưa
        existing = db.query(TrafficData).count()
        if existing > 0:
            print(f"✓ Đã có {existing:,} bản ghi traffic. Bỏ qua.")
            print("  Reset: DELETE FROM traffic_data;")
            return

        # Lấy tất cả đường từ DB
        streets = db.query(Street).all()
        if not streets:
            print("❌ Chưa có đường nào. Chạy seed_danang.py trước!")
            return

        print(f"🚗 Sinh mock traffic data cho {len(streets)} đường × {DAYS_BACK} ngày...")
        print(f"   Tổng ước tính: {len(streets) * 24 * DAYS_BACK:,} bản ghi\n")

        # Thời gian bắt đầu = DAYS_BACK ngày trước, theo giờ Đà Nẵng (UTC+7)
        now_danang = datetime.now(TZ_DANANG)
        start_danang = (now_danang - timedelta(days=DAYS_BACK)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        total_inserted = 0
        batch = []          # Gom bản ghi lại, insert 1 lần / đường để nhanh hơn
        BATCH_SIZE = 500    # Insert theo batch tránh tốn RAM

        for street in streets:
            max_speed = street.max_speed or 50   # Fallback 50km/h nếu NULL

            # Sinh từng time slot từ start_danang đến now (giờ Đà Nẵng)
            current_danang = start_danang
            while current_danang <= now_danang:
                # Lấy giờ và thứ theo múi giờ Đà Nẵng (đã có TZ_DANANG)
                hour       = current_danang.hour
                is_weekend = current_danang.weekday() >= 5

                factor    = get_congestion_factor(hour, is_weekend)
                raw_speed = max_speed * (1 - factor)
                avg_speed = round(max(2.0, raw_speed + random.uniform(-3, 3)), 1)
                congestion = calc_congestion_level(avg_speed, max_speed)

                batch.append(TrafficData(
                    street_id        = street.id,
                    # Lưu UTC vào DB (chuẩn quoc tế), DB tự quy đổi khi cần
                    timestamp        = current_danang.astimezone(timezone.utc),
                    avg_speed        = avg_speed,
                    congestion_level = congestion,
                    source           = "simulated",
                ))

                if len(batch) >= BATCH_SIZE:
                    db.bulk_save_objects(batch)
                    db.flush()
                    total_inserted += len(batch)
                    batch = []

                current_danang += timedelta(minutes=INTERVAL_MIN)

            print(f"  ✓ {street.name:<30} ({street.district.name if street.district else '?'})")

        # Insert phần còn lại
        if batch:
            db.bulk_save_objects(batch)
            total_inserted += len(batch)

        db.commit()

        # ── Thống kê kết quả ──────────────────────────────────
        print(f"\n{'='*52}")
        print(f"  ✅ MOCK TRAFFIC DATA HOÀN TẤT")
        print(f"     Tổng bản ghi : {total_inserted:,}")
        print(f"     Đường        : {len(streets)}")
        print(f"     Thời gian    : {DAYS_BACK} ngày gần nhất")
        print(f"     Interval     : {INTERVAL_MIN} phút/bản ghi")
        print(f"{'='*52}")

        # In phân bổ mức ùn tắc
        green  = db.query(TrafficData).filter(TrafficData.congestion_level == 0).count()
        yellow = db.query(TrafficData).filter(TrafficData.congestion_level == 1).count()
        red    = db.query(TrafficData).filter(TrafficData.congestion_level == 2).count()
        total  = green + yellow + red

        print(f"\n  Phân bổ mức ùn tắc:")
        print(f"  🟢 Xanh  (thông thoáng): {green:>6,}  ({green/total*100:4.1f}%)")
        print(f"  🟡 Vàng  (chậm)        : {yellow:>6,}  ({yellow/total*100:4.1f}%)")
        print(f"  🔴 Đỏ    (kẹt xe)      : {red:>6,}  ({red/total*100:4.1f}%)")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Lỗi: {e}")
        import traceback; traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 52)
    print("  SEED MOCK TRAFFIC DATA")
    print("=" * 52)
    random.seed(42)   # Fixed seed → kết quả reproducible (cùng data mỗi lần chạy)
    seed_traffic()
