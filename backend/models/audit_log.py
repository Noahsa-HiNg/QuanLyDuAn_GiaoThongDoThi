"""
models/audit_log.py — ORM Model cho bảng `audit_log`

Ghi lại mọi hành động quan trọng của Admin/CSGT.
APPEND-ONLY — không bao giờ xóa hay cập nhật record.

Dùng để:
    - Kiểm tra trách nhiệm: "Ai đã xóa user này?"
    - Debug: "Cài gì đã thay đổi trước khi hệ thống lỗi?"
    - Audit: Xuất log cho ban quản lý
"""

from sqlalchemy import Column, BigInteger, Integer, String, JSON, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base   # ← THIẾU — class phải kế thừa Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    # BIGSERIAL — log nhiều, dùng BigInteger
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Ai thực hiện hành động — NULL nếu do scheduler tự động
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Tên action chuẩn hóa dạng UPPER_SNAKE_CASE:
    # Examples: 'CREATE_INCIDENT', 'DELETE_USER', 'RESET_PASSWORD',
    #           'UPDATE_CONFIG', 'DISPATCH_OFFICER', 'LOGIN_FAILED'
    action = Column(String(100), nullable=False)

    # Bảng bị tác động — để tìm kiếm nhanh
    target_table = Column(String(50), nullable=True)

    # ID của bản ghi bị tác động
    target_id = Column(Integer, nullable=True)

    # Chi tiết thay đổi dạng JSON — lưu cả before và after
    # Ví dụ: {"before": {"status": "active"}, "after": {"status": "resolved"}}
    # JSON (không phải JSONB) vì chỉ cần lưu, không cần query bên trong
    detail = Column(JSON, nullable=True)

    # IP address của người thực hiện — VARCHAR(45) đủ chứa IPv6
    ip_address = Column(String(45), nullable=True)

    # Thời điểm xảy ra
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # ─── RELATIONSHIPS ────────────────────────────────────────
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return (
            f"AuditLog(id={self.id}, user_id={self.user_id}, "
            f"action='{self.action}', target='{self.target_table}:{self.target_id}')"
        )
