from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, ConfigDict

# Múi giờ Đà Nẵng UTC+7
TZ_DANANG = timezone(timedelta(hours=7))


class TopCongestedStreetResponse(BaseModel):
    """
    Dữ liệu của một tuyến đường bị kẹt xe nhất.
    Trả về cho endpoint GET /api/stats/top-congested
    """
    street_id: int
    street_name: str
    district_name: Optional[str] = None
    avg_speed: Optional[float] = None
    max_speed: Optional[int] = None
    congestion_level: Optional[int] = None
    congestion_label: Optional[str] = None
    ratio: Optional[float] = None
    timestamp: Optional[datetime] = None
    timestamp_vn: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CongestedRankingResponse(BaseModel):
    """Phản hồi xếp hạng đường kẹt xe lịch sử (ngày/tuần/tháng)"""
    street_id: int
    street_name: str
    district_name: Optional[str] = None
    total_records: int
    congested_records: int
    congestion_rate: float        # Tỉ lệ mẫu kẹt Level 2
    avg_speed: Optional[float] = None
    max_speed: Optional[int] = None
    avg_ratio: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class DistrictCongestionStatsResponse(BaseModel):
    """Phản hồi thống kê tình trạng kẹt xe theo quận/huyện"""
    district_id: int
    district_name: str
    total_streets: int
    congested_occurrences: int    # Số lần ghi nhận kẹt đỏ (Level 2)
    avg_congestion_rate: float    # Tỉ lệ kẹt xe trung bình toàn quận

    model_config = ConfigDict(from_attributes=True)


class HourlyTrendPoint(BaseModel):
    """Điểm dữ liệu biểu đồ xu hướng kẹt xe theo giờ"""
    hour: int
    avg_speed: float
    avg_congested_count: float    # Số lượng đường kẹt đỏ trung bình trong giờ đó
    avg_congestion_pct: Optional[float] = 0.0

    model_config = ConfigDict(from_attributes=True)


class IncidentStatsResponse(BaseModel):
    """Phản hồi thống kê sự cố giao thông và lô cốt"""
    total_active: int
    by_type: dict[str, int]
    by_severity: dict[int, int]
    avg_resolve_time_minutes: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class TopReportedStreet(BaseModel):
    street_name: str
    report_count: int

    model_config = ConfigDict(from_attributes=True)


class FeedbackStatsResponse(BaseModel):
    """Phản hồi thống kê báo cáo/phản ánh từ cộng đồng"""
    total_reports: int
    by_type: dict[str, int]
    top_reported_streets: list[TopReportedStreet]

    model_config = ConfigDict(from_attributes=True)


class CongestedStreet(BaseModel):
    street_name: str
    district_name: Optional[str] = None
    avg_speed: float

    model_config = ConfigDict(from_attributes=True)


class StatsReport(BaseModel):
    avg_speed: float
    red_count: int
    yellow_count: int
    green_count: int
    top_congested: list[CongestedStreet]

    model_config = ConfigDict(from_attributes=True)


class HeatmapItem(BaseModel):
    hour: int
    weekday: int
    congestion_pct: float

    model_config = ConfigDict(from_attributes=True)

