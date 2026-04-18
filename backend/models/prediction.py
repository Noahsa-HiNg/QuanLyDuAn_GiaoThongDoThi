"""
models/prediction.py — ORM Model cho bảng `predictions`

Lưu kết quả dự báo của AI model (Random Forest).
Scheduler chạy mỗi 5 phút → inference → INSERT vào đây.

Phân biệt 2 timestamp quan trọng:
    predicted_at = 17:00  → thời điểm model CHẠY DỰ BÁO
    target_time  = 17:30  → thời điểm ĐƯỢC DỰ BÁO (predicted_at + 30p)
"""

from sqlalchemy import (
    Column, BigInteger, Integer, Float,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Prediction(Base):
    __tablename__ = "predictions"

    # ─── COLUMNS ─────────────────────────────────────────────

    # BIGSERIAL — dùng BigInteger vì 50 đường × 288 lần/ngày (5p) = 14.400 bản ghi/ngày
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # FK → đường được dự báo
    street_id = Column(Integer, ForeignKey("streets.id"), nullable=False)

    # Thời điểm model chạy và tạo ra dự báo này
    # server_default=func.now(): tự điền NOW() khi INSERT không truyền
    predicted_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Thời điểm mà dự báo này hướng đến
    # target_time = predicted_at + horizon_minutes
    # Frontend hiển thị: "Giao thông lúc 17:30 sẽ thế nào?"
    target_time = Column(TIMESTAMP(timezone=True), nullable=False)

    # Khoảng thời gian dự báo trước (phút) — hiện tại cố định = 30
    # Để đây để tương lai có thể mở rộng: dự báo 15p, 60p...
    horizon_minutes = Column(Integer, nullable=False, default=30)

    # Kết quả từ RandomForestRegressor: tốc độ dự báo (km/h)
    pred_speed = Column(Float, nullable=True)

    # Kết quả từ RandomForestClassifier: mức kẹt dự báo (0/1/2)
    pred_level = Column(Integer, nullable=True)

    # Độ tin cậy của dự báo [0.0 → 1.0]
    # Lấy từ predict_proba() của classifier: max(xác suất từng class)
    # Hiển thị cho CSGT: "Model tin 85% sẽ kẹt"
    confidence = Column(Float, nullable=True)

    # ─── TABLE CONSTRAINTS ───────────────────────────────────
    __table_args__ = (
        # confidence phải nằm trong khoảng [0, 1]
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="check_confidence_range"
        ),
        CheckConstraint(
            "pred_level IN (0, 1, 2)",
            name="check_pred_level_valid"
        ),
        # Query nhanh: dự báo mới nhất của đường X
        # SELECT * FROM predictions WHERE street_id=X ORDER BY predicted_at DESC LIMIT 1
        Index("idx_predictions_street_time", "street_id", "predicted_at"),
    )

    # ─── RELATIONSHIPS ────────────────────────────────────────
    street = relationship("Street", back_populates="predictions")

    def __repr__(self):
        return (
            f"Prediction(street_id={self.street_id}, "
            f"target={self.target_time}, level={self.pred_level}, "
            f"confidence={self.confidence})"
        )
