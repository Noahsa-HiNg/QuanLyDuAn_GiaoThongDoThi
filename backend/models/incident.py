"""
models/incident.py — ORM Model cho bảng `incidents`

Lưu các sự kiện ảnh hưởng giao thông do CSGT nhập vào:
    - Lô cốt thi công (roadblock)
    - Sự kiện lớn: marathon, lễ hội (event)
    - Tai nạn (accident)
    - Báo cáo cộng đồng đã xác nhận (community)

Dùng làm feature đầu vào cho AI model:
    has_incident      = 1 nếu có incident active trên đường đó
    incident_severity = mức độ nghiêm trọng cao nhất (0-3)
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Text,
    ForeignKey, Index, CheckConstraint, TIMESTAMP
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Incident(Base):
    __tablename__ = "incidents"

    # ─── COLUMNS ─────────────────────────────────────────────

    id = Column(Integer, primary_key=True, index=True)

    # FK → đường xảy ra sự kiện
    street_id = Column(Integer, ForeignKey("streets.id"), nullable=False)

    # Loại sự kiện:
    #   'roadblock'  — lô cốt, rào chắn thi công
    #   'event'      — sự kiện lớn (marathon, pháo hoa, lễ hội)
    #   'accident'   — tai nạn giao thông
    #   'community'  — tự động tạo từ ≥3 báo cáo cộng đồng trong 15p
    type = Column(String(50), nullable=True)

    # Thời gian bắt đầu sự kiện — bắt buộc phải có
    start_time = Column(TIMESTAMP(timezone=True), nullable=False)

    # Thời gian kết thúc — NULL nếu chưa biết hoặc đang diễn ra
    end_time = Column(TIMESTAMP(timezone=True), nullable=True)

    # Mức độ nghiêm trọng:
    #   1 = Thấp   (ít ảnh hưởng, xe vẫn qua được)
    #   2 = Trung bình (xe chậm lại đáng kể)
    #   3 = Cao    (tắc đường, cần điều phối)
    severity = Column(Integer, default=1, nullable=False)

    # Mô tả chi tiết — CSGT nhập tự do
    # Text (không giới hạn độ dài) thay vì String(N)
    description = Column(Text, nullable=True)

    # Trạng thái xử lý:
    #   'active'     — đang xảy ra, chưa xử lý
    #   'dispatched' — đã cử nhân viên/xe đến xử lý
    #   'resolved'   — đã giải quyết xong
    status = Column(String(20), default="active", nullable=False)

    # Cờ nhanh để filter: WHERE is_active = TRUE
    # Được set FALSE khi status = 'resolved'
    # Dùng Partial Index để chỉ index bản ghi active → tiết kiệm bộ nhớ
    is_active = Column(Boolean, default=True, nullable=False)

    # FK → user tạo incident (CSGT hoặc NULL nếu tự động từ community)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Thời điểm tạo record
    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # ─── TABLE CONSTRAINTS ───────────────────────────────────
    __table_args__ = (
        CheckConstraint("severity IN (1, 2, 3)", name="check_severity_valid"),
        CheckConstraint(
            "status IN ('active', 'dispatched', 'resolved')",
            name="check_status_valid"
        ),

        # Partial Index: chỉ index bản ghi đang active
        # Nhỏ hơn full index nhưng nhanh hơn cho query thường dùng nhất:
        # SELECT * FROM incidents WHERE is_active = TRUE AND street_id = X
        Index("idx_incidents_active_street", "street_id",
              postgresql_where="is_active = TRUE"),
    )

    # ─── RELATIONSHIPS ────────────────────────────────────────
    street = relationship("Street", back_populates="incidents")

    # foreign_keys chỉ định rõ khi có nhiều FK cùng trỏ về 1 bảng
    created_by_user = relationship("User", back_populates="incidents",
                                    foreign_keys=[created_by])

    def __repr__(self):
        return (
            f"Incident(id={self.id}, street_id={self.street_id}, "
            f"type='{self.type}', severity={self.severity}, status='{self.status}')"
        )
