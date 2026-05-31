"""
models/emergency_banner.py — ORM Model cho bảng `emergency_banners`
Lưu thông tin cấm đường hoặc thông báo khẩn cấp toàn thành phố do Admin ban hành.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class EmergencyBanner(Base):
    __tablename__ = "emergency_banners"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)

    def __repr__(self):
        return f"EmergencyBanner(id={self.id}, title='{self.title}', active={self.is_active})"
