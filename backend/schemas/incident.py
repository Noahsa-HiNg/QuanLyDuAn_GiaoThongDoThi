# backend/schemas/incident.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class IncidentBase(BaseModel):
    street_id: int = Field(..., description="ID tuyến đường xảy ra sự cố")
    type: str = Field(..., description="Loại sự cố: roadblock (lô cốt), accident (tai nạn), event (sự kiện), community (cộng đồng)")
    start_time: datetime = Field(..., description="Thời gian bắt đầu sự cố")
    end_time: Optional[datetime] = Field(None, description="Thời gian kết thúc (nếu có)")
    severity: int = Field(1, ge=1, le=3, description="Mức độ nghiêm trọng: 1 (Thấp), 2 (Trung bình), 3 (Cao)")
    description: Optional[str] = Field(None, description="Mô tả chi tiết sự cố")
    status: str = Field("active", description="Trạng thái: active (đang xảy ra), dispatched (đã cử người xử lý), resolved (đã giải quyết)")
    is_active: bool = Field(True, description="Cờ đánh dấu sự cố đang còn hiệu lực")
    latitude: Optional[float] = Field(None, description="Vĩ độ xảy ra sự cố")
    longitude: Optional[float] = Field(None, description="Kinh độ xảy ra sự cố")
    officer_id: Optional[int] = Field(None, description="ID CSGT được phân công tuần tra")

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = ("roadblock", "event", "accident", "community")
        if v not in allowed:
            raise ValueError(f"Loại sự cố phải thuộc: {allowed}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = ("active", "dispatched", "resolved")
        if v not in allowed:
            raise ValueError(f"Trạng thái phải thuộc: {allowed}")
        return v


class IncidentCreate(IncidentBase):
    """Schema nhận vào khi tạo mới sự cố (CSGT nhập tay)"""
    pass


class IncidentUpdate(BaseModel):
    """Schema nhận vào khi cập nhật sự cố (tất cả các trường đều là tùy chọn)"""
    street_id: Optional[int] = None
    type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    severity: Optional[int] = None
    description: Optional[str] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    officer_id: Optional[int] = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = ("roadblock", "event", "accident", "community")
        if v not in allowed:
            raise ValueError(f"Loại sự cố phải thuộc: {allowed}")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = ("active", "dispatched", "resolved")
        if v not in allowed:
            raise ValueError(f"Trạng thái phải thuộc: {allowed}")
        return v


class IncidentOut(IncidentBase):
    """Schema trả về cho client"""
    id: int
    created_by: Optional[int] = None
    created_at: datetime

    # Thông tin nguồn gốc — giúp frontend phân biệt manual vs tự động
    here_incident_id: Optional[str] = Field(
        None,
        description="ID gốc từ HERE API (NULL nếu CSGT nhập tay)"
    )
    source: str = Field(
        "manual",
        description="Nguồn tạo: 'manual' (CSGT nhập tay) hoặc 'here_api' (tự động cào)"
    )

    class Config:
        from_attributes = True

