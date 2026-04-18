"""
schemas/street.py — Pydantic schemas cho Street API

Tách biệt schema khỏi ORM model:
  - ORM model (models/street.py) = ánh xạ bảng DB
  - Schema (schemas/street.py)   = định nghĩa hình dạng JSON request/response
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DistrictOut(BaseModel):
    """Thông tin quận — embed trong StreetOut."""
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class StreetOut(BaseModel):
    """
    Schema trả về cho 1 tuyến đường.
    Dùng from_attributes=True để convert trực tiếp từ SQLAlchemy ORM object.
    """
    id: int
    name: str
    district_id: Optional[int] = None
    district: Optional[DistrictOut] = None   # Embed thông tin quận nếu cần
    length_km: Optional[float] = None
    max_speed: Optional[int] = None
    is_one_way: bool

    model_config = ConfigDict(from_attributes=True)


class StreetListOut(BaseModel):
    """Wrapper cho danh sách đường — kèm meta tổng số."""
    total: int
    page: int
    page_size: int
    data: list[StreetOut]
