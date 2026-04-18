"""
models/street.py — ORM Model cho bảng `streets`

Bảng TRUNG TÂM của hệ thống — 50 tuyến đường Đà Nẵng.
Hầu hết các bảng khác đều có foreign key trỏ về đây.

Quan hệ:
    districts (1) ──── (N) streets         ← thuộc quận nào
    streets   (1) ──── (N) traffic_data    ← dữ liệu giao thông theo thời gian
    streets   (1) ──── (N) predictions     ← dự báo AI
    streets   (1) ──── (N) incidents       ← sự kiện/lô cốt
    streets   (1) ──── (N) feedback        ← báo cáo cộng đồng
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from database import Base


class Street(Base):
    __tablename__ = "streets"

    # ─── COLUMNS ─────────────────────────────────────────────

    # Khóa chính — dùng làm FK ở tất cả bảng khác
    id = Column(Integer, primary_key=True, index=True)

    # Tên tuyến đường — ví dụ: "Nguyễn Văn Linh", "Bạch Đằng"
    name = Column(String(200), nullable=False)

    # FK → bảng districts: đường này thuộc quận nào
    # ForeignKey("districts.id") = REFERENCES districts(id)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True)

    # Hình dạng tuyến đường trên bản đồ (danh sách tọa độ theo thứ tự)
    # LINESTRING: đường thẳng nối các điểm tọa độ
    # srid=4326: hệ tọa độ GPS (lat/lng)
    # Dùng để render PathLayer trên Pydeck và tính khoảng cách trong A*
    geometry = Column(Geometry("LINESTRING", srid=4326), nullable=True)

    # Chiều dài đường (km) — dùng làm trọng số cạnh trong đồ thị A*
    # weight = length_km × (1 + congestion_factor)
    length_km = Column(Float, nullable=True)

    # Tốc độ giới hạn (km/h) — dùng để tính congestion_level
    # Nếu avg_speed < 40% max_speed → congestion_level = 2 (đỏ)
    max_speed = Column(Integer, nullable=True)

    # Đường một chiều? → Ảnh hưởng đến cách thêm cạnh vào đồ thị routing
    # True  → chỉ thêm cạnh 1 chiều (A → B)
    # False → thêm cạnh 2 chiều   (A → B và B → A)
    is_one_way = Column(Boolean, default=False, nullable=False)

    # ─── RELATIONSHIPS ────────────────────────────────────────

    # Quan hệ ngược: truy cập street.district để lấy thông tin quận
    district = relationship("District", back_populates="streets")

    # Quan hệ 1-N với các bảng phụ thuộc
    # lazy="dynamic" = không load toàn bộ ngay, query khi cần
    traffic_data = relationship("TrafficData", back_populates="street",
                                 cascade="all, delete-orphan")
    predictions  = relationship("Prediction",  back_populates="street",
                                 cascade="all, delete-orphan")
    incidents    = relationship("Incident",    back_populates="street")
    feedbacks    = relationship("Feedback",    back_populates="street")

    def __repr__(self):
        return f"Street(id={self.id}, name='{self.name}', district_id={self.district_id})"
