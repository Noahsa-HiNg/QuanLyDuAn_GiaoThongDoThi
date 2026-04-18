"""
models/district.py — ORM Model cho bảng `districts`

Bảng này lưu ranh giới địa lý của 8 quận/huyện Đà Nẵng.
Dữ liệu được nạp từ file data/districts.geojson khi seed.

Quan hệ:
    districts (1) ──── (N) streets
    Một quận có nhiều tuyến đường.
"""

# Column, Integer, String: Kiểu dữ liệu cột SQL
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship    # Để khai báo quan hệ 1-N

# Thư viện PostGIS — lưu dữ liệu địa lý dạng Polygon
from geoalchemy2 import Geometry

# Base là class cha chung, được tạo trong database.py
from database import Base


class District(Base):
    # __tablename__ là tên bảng thực trong PostgreSQL
    __tablename__ = "districts"

    # ─── COLUMNS ─────────────────────────────────────────────
    # SERIAL PRIMARY KEY — số nguyên tự tăng (1, 2, 3, ...)
    id = Column(Integer, primary_key=True, index=True)

    # VARCHAR(100) NOT NULL — tên quận, tối đa 100 ký tự
    name = Column(String(100), nullable=False)

    # GEOMETRY(POLYGON, 4326):
    #   - POLYGON: hình đa giác (ranh giới quận)
    #   - 4326 = SRID WGS84 — hệ tọa độ GPS tiêu chuẩn (lat/lng)
    #   - nullable=True vì khi seed có thể chưa có geometry ngay
    geometry = Column(Geometry("POLYGON", srid=4326), nullable=True)

    # ─── RELATIONSHIPS ────────────────────────────────────────
    # Khai báo quan hệ 1-N: 1 quận → nhiều đường
    # back_populates="district" phải khớp với tên trong class Street
    streets = relationship("Street", back_populates="district")

    # ─── PYTHON REPR ─────────────────────────────────────────
    def __repr__(self):
        # Giúp debug dễ hơn: print(district) → District(id=1, name='Hải Châu')
        return f"District(id={self.id}, name='{self.name}')"
