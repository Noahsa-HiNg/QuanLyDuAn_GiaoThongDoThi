"""
schemas/traffic.py — Pydantic schemas cho Traffic API
"""

from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, ConfigDict, computed_field

# Múi giờ Đà Nẵng UTC+7
TZ_DANANG = timezone(timedelta(hours=7))


class TrafficCurrentOut(BaseModel):
    """
    Dữ liệu giao thông MỚI NHẤT của 1 tuyến đường.
    Trả về cho endpoint GET /api/traffic/current
    """
    street_id: int
    street_name: str
    district_name: Optional[str] = None

    # Dữ liệu giao thông
    avg_speed: Optional[float] = None
    max_speed: Optional[int] = None
    congestion_level: Optional[int] = None
    congestion_label: Optional[str] = None

    source: Optional[str] = None
    timestamp: Optional[datetime] = None         # Lưu trong DB (UTC)
    timestamp_vn: Optional[str] = None           # Hiển thị giờ Đà Nẵng (+07:00)

    model_config = ConfigDict(from_attributes=True)


class TrafficSummaryOut(BaseModel):
    """
    Tổng hợp tình trạng giao thông toàn thành phố.
    Trả về kèm danh sách chi tiết từng đường.
    """
    total_streets: int
    green_count: int    # Số đường xanh (thông thoáng)
    yellow_count: int   # Số đường vàng (chậm)
    red_count: int      # Số đường đỏ (kẹt xe)
    no_data_count: int  # Số đường chưa có dữ liệu
    data_as_of: Optional[datetime] = None   # Thời điểm dữ liệu mới nhất
    streets: list[TrafficCurrentOut]
