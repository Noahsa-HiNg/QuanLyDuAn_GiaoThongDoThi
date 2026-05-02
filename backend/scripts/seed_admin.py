"""
scripts/seed_admin.py — Tạo tài khoản admin mặc định

Chạy một lần khi khởi tạo hệ thống:
    python scripts/seed_admin.py

Nếu admin đã tồn tại → bỏ qua (idempotent).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.user import User
from auth.password import hash_password

ADMIN_EMAIL    = "admin@danang-traffic.vn"
ADMIN_PASSWORD = "Admin@2026!"     # ← ĐỔI MẬT KHẨU TRƯỚC KHI DEPLOY
ADMIN_FULLNAME = "Quản trị viên hệ thống"


def seed_admin():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == ADMIN_EMAIL).first()
        if existing:
            print(f"✅ Admin đã tồn tại: {ADMIN_EMAIL}")
            return

        admin = User(
            email         = ADMIN_EMAIL,
            password_hash = hash_password(ADMIN_PASSWORD),
            role          = "admin",
            full_name     = ADMIN_FULLNAME,
            is_active     = True,
        )
        db.add(admin)
        db.commit()
        print(f"✅ Tạo admin thành công: {ADMIN_EMAIL}")
        print(f"   Password: {ADMIN_PASSWORD}")
        print(f"   ⚠️  HÃY ĐỔI MẬT KHẨU SAU KHI ĐĂNG NHẬP LẦN ĐẦU!")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
