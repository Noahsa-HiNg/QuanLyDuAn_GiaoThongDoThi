"""
data/seed_all.py — Chạy toàn bộ seed theo đúng thứ tự

CÁCH DÙNG (chỉ cần chạy 1 lệnh duy nhất):
    docker compose exec backend python data/seed_all.py

THỨ TỰ CHẠY:
    1. alembic upgrade head   → Tạo schema bảng
    2. seed_danang.py         → INSERT 8 quận + 49 đường
    3. seed_traffic.py        → INSERT 9.000+ bản ghi traffic (7 ngày)

LƯU Ý:
    - Script idempotent: chạy nhiều lần không bị lỗi (tự bỏ qua nếu đã có dữ liệu)
    - Traffic data dùng random.seed(42) → kết quả giống nhau mỗi lần
"""

import subprocess
import sys
import os

sys.path.insert(0, "/app")


def run_step(title: str, fn):
    """Chạy 1 bước, in kết quả rõ ràng."""
    print(f"\n{'─'*52}")
    print(f"  ▶  {title}")
    print(f"{'─'*52}")
    try:
        fn()
        print(f"  ✅ {title} — XONG")
    except SystemExit:
        pass   # seed scripts dùng sys.exit(0) đôi khi — bỏ qua
    except Exception as e:
        print(f"  ❌ Lỗi: {e}")
        raise


def step1_migrate():
    """Chạy alembic upgrade head để tạo/cập nhật schema."""
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True, text=True
    )
    print(result.stdout)

    if result.returncode != 0:
        # Nếu lỗi vì bảng đã tồn tại (DuplicateTable) → stamp version thôi
        if "DuplicateTable" in result.stderr or "already exists" in result.stderr:
            print("  ⚠ Bảng đã tồn tại → stamp version (không chạy lại migration)")
            subprocess.run(["alembic", "stamp", "head"], check=True)
        else:
            print(result.stderr)
            raise RuntimeError("Migration thất bại!")
    else:
        print("  Schema đã cập nhật.")


def step2_seed_streets():
    """Seed 8 quận + 49 đường Đà Nẵng."""
    # Import trực tiếp để chạy trong cùng process
    from data.seed_danang import seed
    seed()


def step3_seed_traffic():
    """Seed 9.000+ bản ghi traffic giả lập 7 ngày."""
    import random
    random.seed(42)   # Đảm bảo cùng kết quả cho mọi người
    from data.seed_traffic import seed_traffic
    seed_traffic()


if __name__ == "__main__":
    print("=" * 52)
    print("  SETUP DỮ LIỆU DỰ ÁN GIAO THÔNG ĐÀ NẴNG")
    print("=" * 52)

    steps = [
        ("Bước 1: Tạo schema DB (alembic upgrade head)", step1_migrate),
        ("Bước 2: Seed 8 quận + 49 đường",              step2_seed_streets),
        ("Bước 3: Sinh mock traffic data 7 ngày",        step3_seed_traffic),
    ]

    for title, fn in steps:
        run_step(title, fn)

    print(f"\n{'='*52}")
    print("  🎉 SETUP HOÀN TẤT — Dự án sẵn sàng chạy!")
    print(f"{'='*52}")
    print("\n  API đang chạy tại: http://localhost:8000")
    print("  Swagger UI       : http://localhost:8000/docs")
    print("  pgAdmin          : http://localhost:5050")
