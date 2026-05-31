# backend/schemas/community_report.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CommunityReportBase(BaseModel):
    latitude: float = Field(..., description="Vĩ độ xảy ra sự cố báo cáo")
    longitude: float = Field(..., description="Kinh độ xảy ra sự cố báo cáo")
    severity: int = Field(1, ge=1, le=3, description="Mức độ kẹt xe: 1 (Thấp), 2 (Trung bình), 3 (Cao)")
    description: Optional[str] = Field(None, description="Mô tả chi tiết từ người dân")


class CommunityReportCreate(CommunityReportBase):
    """Schema nhận vào khi người dân gửi báo cáo"""
    pass


class CommunityReportOut(CommunityReportBase):
    """Schema trả về thông tin báo cáo"""
    id: int
    is_verified: bool
    street_id: Optional[int] = None
    reported_at: datetime

    class Config:
        from_attributes = True
