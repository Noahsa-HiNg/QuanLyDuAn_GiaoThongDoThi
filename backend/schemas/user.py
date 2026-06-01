"""
schemas/user.py — Pydantic schemas cho User Management API

UserOut       : trả về thông tin user (không có password)
UserCreateRequest : body tạo user mới
UserLockRequest   : body khóa/mở khóa tài khoản
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserOut(BaseModel):
    """Response schema — thông tin user hiển thị cho Admin."""
    id:              int
    email:           EmailStr
    full_name:       Optional[str]
    role:            str            # 'admin' | 'csgt'
    is_active:       bool
    is_locked:       bool
    locked_until:    Optional[datetime]
    failed_attempts: int
    last_login:      Optional[datetime]
    created_at:      datetime
    is_busy:         bool = False

    model_config = {"from_attributes": True}


class OfficerOut(BaseModel):
    """
    Response schema — danh sách cảnh sát giao thông (CSGT).

    Chỉ trả về các trường an toàn, KHÔNG bao gồm thông tin bảo mật
    (failed_attempts, locked_until) để có thể chia sẻ rộng hơn.
    Cả admin lẫn csgt đều có thể gọi endpoint này.
    """
    id:         int
    email:      EmailStr
    full_name:  Optional[str]
    role:       str           # luôn là 'csgt' trong endpoint officers
    is_active:  bool
    last_login: Optional[datetime]
    created_at: datetime
    is_busy:    bool = False

    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    """Body cho POST /api/users — Admin tạo tài khoản mới."""
    email:     EmailStr
    password:  str = Field(
        ...,
        min_length=8,
        description="Mật khẩu tối thiểu 8 ký tự"
    )
    full_name: Optional[str] = Field(None, max_length=200)
    role:      str = Field("csgt", description="Chỉ chấp nhận: 'csgt' hoặc 'admin'")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("csgt", "admin"):
            raise ValueError("role phải là 'csgt' hoặc 'admin'")
        return v


class UserLockRequest(BaseModel):
    """
    Body cho POST /api/users/{id}/lock và /unlock.
    
    lock:
        POST /api/users/{id}/lock   → { "reason": "Vi phạm nội quy" }
    unlock:
        POST /api/users/{id}/unlock → không cần body
    """
    reason: Optional[str] = None    # Lý do khóa (ghi vào audit log)
