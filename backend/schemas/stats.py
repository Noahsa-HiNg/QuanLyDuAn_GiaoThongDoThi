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
