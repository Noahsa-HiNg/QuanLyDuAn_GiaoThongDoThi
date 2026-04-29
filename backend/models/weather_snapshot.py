"""
models/weather_snapshot.py — Lưu trạng thái thời tiết Đà Nẵng theo chu kỳ

Thiết kế:
    - 1 bản ghi / chu kỳ cào (10-30 phút/lần)
    - Đà Nẵng thời tiết đồng đều → 1 điểm đo toàn TP là đủ
    - Khi train ML: JOIN với traffic_data theo timestamp gần nhất

Ví dụ query lấy thời tiết gần nhất với 1 traffic record:
    SELECT w.*
    FROM weather_snapshots w
    ORDER BY ABS(EXTRACT(EPOCH FROM (w.timestamp - :traffic_ts)))
    LIMIT 1;
"""

from sqlalchemy import Column, BigInteger, Float, Integer, String, Index
from sqlalchemy import TIMESTAMP
from sqlalchemy.sql import func
from database import Base


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # Thời điểm đo thời tiết (đồng bộ với timestamp của chu kỳ cào traffic)
    timestamp = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Nguồn dữ liệu
    source = Column(String(30), nullable=True, default="openweathermap")

    # ── Nhiệt độ & độ ẩm ────────────────────────────────────────
    temperature   = Column(Float, nullable=True)   # °C
    humidity      = Column(Integer, nullable=True)  # % (0-100)

    # ── Gió ─────────────────────────────────────────────────────
    wind_speed    = Column(Float, nullable=True)    # m/s

    # ── Mưa ─────────────────────────────────────────────────────
    rain_1h_mm    = Column(Float, nullable=True, default=0.0)   # mm/giờ qua
    is_raining    = Column(Integer, nullable=True, default=0)    # 0/1

    # ── Tầm nhìn ────────────────────────────────────────────────
    visibility_km = Column(Float, nullable=True)   # km (0-10+)

    # ── Phân loại thời tiết ──────────────────────────────────────
    # 0=quang, 1=có mây, 2=mưa nhẹ, 3=mưa nặng, 4=sương mù/khác
    weather_group = Column(Integer, nullable=True, default=0)
    weather_id    = Column(Integer, nullable=True)  # OpenWeather condition code

    # Index theo timestamp để JOIN nhanh với traffic_data
    __table_args__ = (
        Index("idx_weather_timestamp", "timestamp"),
    )

    def __repr__(self):
        return (
            f"WeatherSnapshot(ts={self.timestamp}, "
            f"temp={self.temperature}°C, rain={self.rain_1h_mm}mm)"
        )
