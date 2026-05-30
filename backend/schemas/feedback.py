# backend/schemas/feedback.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class FeedbackBase(BaseModel):
    street_id: Optional[int] = Field(None, description="ID tuyến đường liên quan (nếu có)")
    lat: float = Field(..., description="Vĩ độ nơi gửi phản ánh")
    lon: float = Field(..., description="Kinh độ nơi gửi phản ánh")
    report_type: str = Field(..., description="Loại phản ánh: congested (kẹt xe), clear (thông thoáng), accident (tai nạn)")
    description: Optional[str] = Field(None, description="Ghi chú chi tiết từ người dân")

    @field_validator("report_type")
    @classmethod
    def validate_report_type(cls, v: str) -> str:
        allowed = ("congested", "clear", "accident")
        if v not in allowed:
            raise ValueError(f"Loại phản ánh phải thuộc: {allowed}")
        return v


class FeedbackCreate(FeedbackBase):
    """Schema nhận vào khi tạo phản ánh mới"""
    pass


class FeedbackOut(FeedbackBase):
    """Schema trả về cho client"""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
