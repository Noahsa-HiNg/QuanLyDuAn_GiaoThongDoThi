"""
models/traffic_data.py — ORM Model cho bảng `traffic_data`

Bảng QUAN TRỌNG NHẤT — lưu dữ liệu giao thông theo thời gian thực.
Scheduler chạy mỗi 60 giây → gọi TomTom API → INSERT vào bảng này.

Quy mô dữ liệu ước tính:
    50 đường × 1440 phút/ngày = 72.000 bản ghi/ngày
    1 tháng ≈ 2.16 triệu bản ghi

→ Dùng BIGSERIAL thay SERIAL để tránh overflow (SERIAL max ≈ 2.1 tỷ)
→ Index (street_id, timestamp DESC) để query nhanh bản ghi mới nhất
"""

from sqlalchemy import (
    Column, BigInteger, Integer, Float, String,
    ForeignKey, Index, CheckConstraint
)
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func       # func.now() = NOW() trong SQL
from database import Base


class TrafficData(Base):
    __tablename__ = "traffic_data"

    # ─── COLUMNS ─────────────────────────────────────────────

    # BIGSERIAL: số nguyên lớn tự tăng (max ≈ 9.2 × 10^18)
    # Dùng BigInteger vì bảng time-series sẽ có hàng triệu bản ghi
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # FK → streets.id — bản ghi này đo tuyến đường nào
    # nullable=False: bắt buộc phải có — không cho phép NULL
    street_id = Column(Integer, ForeignKey("streets.id"), nullable=False)

    # TIMESTAMPTZ (timestamp with time zone):
    #   - Lưu kèm thông tin timezone → tránh bug khi server đổi múi giờ
    #   - nullable=False: bắt buộc phải có timestamp
    #   - server_default=func.now(): DB tự điền NOW() nếu không truyền
    timestamp = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    # Tốc độ trung bình xe trên đường (km/h)
    # CheckConstraint: tự động kiểm tra avg_speed >= 0 ở tầng DB
    avg_speed = Column(Float, nullable=True)

    # Mức độ ùn tắc:
    #   0 = Xanh  (thông thoáng): avg_speed >= 70% max_speed
    #   1 = Vàng  (chậm)        : avg_speed 40-70% max_speed
    #   2 = Đỏ    (kẹt xe)      : avg_speed < 40% max_speed
    # SMALLINT: chỉ lưu số nhỏ (-32768 đến 32767), tiết kiệm bộ nhớ hơn Integer
    congestion_level = Column(Integer, nullable=True)

    # Nguồn dữ liệu — để tracking xem dữ liệu đến từ đâu
    #   'tomtom'   : TomTom Traffic Flow API (nguồn chính)
    #   'goong'    : Goong Maps API (fallback khi TomTom lỗi)
    #   'simulated': Dữ liệu mô phỏng (khi cả 2 API lỗi)
    source = Column(String(20), nullable=True, default="simulated")

    # ─── TABLE CONSTRAINTS ───────────────────────────────────
    # Khai báo constraints và index ở đây thay vì inline trong Column
    __table_args__ = (
        # Kiểm tra avg_speed hợp lệ — tầng DB đảm bảo không có giá trị âm
        CheckConstraint("avg_speed >= 0", name="check_avg_speed_positive"),

        # Kiểm tra congestion_level hợp lệ (0, 1, hoặc 2)
        CheckConstraint(
            "congestion_level IN (0, 1, 2)",
            name="check_congestion_level_valid"
        ),

        # ★ INDEX quan trọng nhất hệ thống:
        #   Khi query "dữ liệu mới nhất của đường X":
        #   SELECT * FROM traffic_data WHERE street_id=X ORDER BY timestamp DESC LIMIT 1
        #   Index này giúp truy vấn chạy ~100x nhanh hơn so với không có index
        Index("idx_traffic_street_time", "street_id", "timestamp"),
    )

    # ─── RELATIONSHIPS ────────────────────────────────────────
    # Truy cập record.street.name thay vì phải JOIN thủ công
    street = relationship("Street", back_populates="traffic_data")

    def __repr__(self):
        return (
            f"TrafficData(id={self.id}, street_id={self.street_id}, "
            f"speed={self.avg_speed}, level={self.congestion_level}, "
            f"source='{self.source}')"
        )
