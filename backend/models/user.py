"""
models/user.py — ORM Model cho bảng `users`

Quản lý tài khoản CSGT và Admin.
KHÔNG phải người dân — bản đồ công dân không cần đăng nhập.

Bảo mật:
    - password_hash: bcrypt hash, KHÔNG LƯU plaintext
    - failed_attempts + locked_until: chống Brute Force (khóa sau 5 lần sai)
    - is_active: deactivate tài khoản mà không xóa hẳn (giữ audit log)
"""

from sqlalchemy import (
    Column, Integer, String, Boolean,
    TIMESTAMP
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    # ─── COLUMNS ─────────────────────────────────────────────

    id = Column(Integer, primary_key=True, index=True)

    # unique=True → PostgreSQL tự tạo UNIQUE INDEX trên cột này
    # Đảm bảo không có 2 user cùng email
    email = Column(String(255), unique=True, nullable=False, index=True)

    # Lưu kết quả bcrypt.hash(password) — dạng: "$2b$12$abc...xyz"
    # KHÔNG LƯU password thật — nếu DB bị leak cũng không bị mất password
    password_hash = Column(String(255), nullable=False)

    # Phân quyền:
    #   'admin' — toàn quyền: quản lý users, xem audit log, cấu hình hệ thống
    #   'csgt'  — tạo/xử lý incidents, điều hành bản đồ
    role = Column(String(20), nullable=False, default="csgt")

    # Tên hiển thị trên Dashboard
    full_name = Column(String(200), nullable=True)

    # Admin có thể deactivate mà không xóa tài khoản
    # is_active=False → đăng nhập bị từ chối, nhưng audit log vẫn còn
    is_active = Column(Boolean, default=True, nullable=False)

    # ─── BRUTE FORCE PROTECTION ──────────────────────────────

    # Đếm số lần nhập sai password liên tiếp
    # Reset về 0 khi đăng nhập thành công
    failed_attempts = Column(Integer, default=0, nullable=False)

    # Tài khoản có đang bị khóa không?
    is_locked = Column(Boolean, default=False, nullable=False)

    # Bị khóa đến khi nào — NULL = không bị khóa hoặc đã hết thời gian khóa
    # Logic: IF locked_until > NOW() → từ chối đăng nhập
    locked_until = Column(TIMESTAMP(timezone=True), nullable=True)

    # ─── TRACKING ────────────────────────────────────────────

    # Thời điểm đăng nhập gần nhất — hiển thị trên trang quản lý users
    last_login = Column(TIMESTAMP(timezone=True), nullable=True)

    # Thời điểm tạo tài khoản
    # server_default=func.now(): PostgreSQL tự điền, Python không cần truyền
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # ─── RELATIONSHIPS ────────────────────────────────────────

    # Các incident do user này tạo
    incidents = relationship("Incident", back_populates="created_by_user",
                              foreign_keys="Incident.created_by")

    # Các hành động trong audit log
    audit_logs = relationship("AuditLog", back_populates="user")

    # Các cấu hình mà user này đã cập nhật
    system_configs = relationship("SystemConfig", back_populates="updated_by_user")

    def __repr__(self):
        return f"User(id={self.id}, email='{self.email}', role='{self.role}')"
