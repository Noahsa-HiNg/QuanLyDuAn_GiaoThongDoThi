# backend/schemas/emergency_banner.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EmergencyBannerBase(BaseModel):
    title: str = Field(..., max_length=200, description="Tiêu đề thông báo khẩn cấp")
    content: str = Field(..., description="Nội dung thông báo khẩn cấp")
    is_active: bool = Field(True, description="Trạng thái hoạt động của banner")
    expires_at: Optional[datetime] = Field(None, description="Thời gian hết hiệu lực (tùy chọn)")


class EmergencyBannerCreate(EmergencyBannerBase):
    """Schema nhận vào khi admin tạo banner mới"""
    pass


class EmergencyBannerOut(EmergencyBannerBase):
    """Schema trả về thông tin banner"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
