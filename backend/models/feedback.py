"""
models/feedback.py — ORM Model cho bảng `feedback`

Báo cáo kẹt xe từ người dân — KHÔNG cần đăng nhập.
Tích lũy để tự động tạo incident (≥3 báo cáo cùng đường trong 15 phút).
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text,
    ForeignKey, Index, TIMESTAMP
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    # ─── COLUMNS ─────────────────────────────────────────────

    id = Column(Integer, primary_key=True, index=True)

    # FK → đường liên quan — NULLABLE vì người dùng có thể
    # chỉ nhấn điểm trên bản đồ mà không biết tên đường
    street_id = Column(Integer, ForeignKey("streets.id"), nullable=True)

    # Tọa độ GPS nơi người dùng bấm báo cáo
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    # Loại báo cáo:
    #   'congested' — đang kẹt xe
    #   'clear'     — đường thông thoáng (phản bác báo cáo kẹt)
    #   'accident'  — có tai nạn
    report_type = Column(String(30), nullable=True)

    # Ghi chú thêm từ người dùng (tùy chọn)
    description = Column(Text, nullable=True)

    # Thời gian gửi báo cáo
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # ─── TABLE ARGS ──────────────────────────────────────────
    __table_args__ = (
        # Index để query nhanh: báo cáo của đường X trong 15 phút gần nhất
        # Dùng trong scheduler check_auto_incidents()
        Index("idx_feedback_street_time", "street_id", "created_at"),
    )

    # ─── RELATIONSHIPS ────────────────────────────────────────
    street = relationship("Street", back_populates="feedbacks")

    def __repr__(self):
        return (
            f"Feedback(id={self.id}, street_id={self.street_id}, "
            f"type='{self.report_type}', lat={self.lat}, lon={self.lon})"
        )
