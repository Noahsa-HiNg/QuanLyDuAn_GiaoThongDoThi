"""
models/system_config.py — Key-Value Store cấu hình runtime

Admin thay đổi cấu hình này qua UI mà không cần restart server.
"""

# Lỗi 1: Thiếu toàn bộ import — file không thể chạy
from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base   # ← Bắt buộc phải có


class SystemConfig(Base):
    __tablename__ = "system_config"

    # key là Primary Key — tên cấu hình, phải unique
    # Examples: 'global_alert', 'speed_threshold_red', 'auto_incident_threshold'
    key = Column(String(100), primary_key=True)

    # Giá trị — lưu dạng string, parse ở tầng service nếu cần số
    # Có thể là JSON string nếu cần lưu nhiều field
    # Example: '{"message": "Lễ hội pháo hoa", "is_active": true}'
    value = Column(String(500), nullable=False)

    # Ai cập nhật gần nhất
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Khi nào cập nhật
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),   # Tự cập nhật khi UPDATE record
        nullable=False
    )

    # ─── RELATIONSHIPS ────────────────────────────────────────
    updated_by_user = relationship("User", back_populates="system_configs")

    def __repr__(self):
        return f"SystemConfig(key='{self.key}', value='{self.value}')"
