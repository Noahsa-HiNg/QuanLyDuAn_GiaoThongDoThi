from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TrafficRecord(BaseModel):
    road_id: int
    road_name: str
    lat: float
    lng: float
    speed: float          # km/h
    congestion_level: int # 1=xanh, 2=vàng, 3=đỏ
    updated_at: datetime
# Thêm vào backend/schemas.py  ← A sở hữu
class PredictedRecord(BaseModel):
    road_id:         int
    road_name:       str
    lat:             Optional[float]
    lng:             Optional[float]
    predicted_level: int      # 1=xanh, 2=vàng, 3=đỏ
    confidence:      float    # 0.0 - 1.0
    predicted_at:    str