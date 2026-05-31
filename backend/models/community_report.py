"""
models/community_report.py — ORM Model cho bảng `community_reports`
Lưu các lượt báo cáo kẹt xe từ cộng đồng người dân.
"""

from sqlalchemy import Column, Integer, Float, Boolean, Text, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class CommunityReport(Base):
    __tablename__ = "community_reports"

    id = Column(Integer, primary_key=True, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    severity = Column(Integer, default=1, nullable=False)  # 1-3: Nhẹ, Trung bình, Nặng
    description = Column(Text, nullable=True)
    
    # Cờ đánh dấu báo cáo đã được gom cụm hoặc xử lý thành Incident tự động
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Đường gần nhất được định vị từ tọa độ báo cáo
    street_id = Column(Integer, ForeignKey("streets.id"), nullable=True)

    reported_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    street = relationship("Street")

    def __repr__(self):
        return (
            f"CommunityReport(id={self.id}, lat={self.latitude}, lng={self.longitude}, "
            f"severity={self.severity}, verified={self.is_verified})"
        )
