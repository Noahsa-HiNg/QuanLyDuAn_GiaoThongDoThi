"""
schemas/user.py — Pydantic schemas cho User Management API

UserOut       : trả về thông tin user (không có password)
UserCreateRequest : body tạo user mới
UserLockRequest   : body khóa/mở khóa tài khoản
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


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

    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    """Body cho POST /api/users — Admin tạo tài khoản mới."""
    email:     EmailStr
    password:  str
    full_name: Optional[str] = None
    role:      str = "csgt"         # Mặc định là csgt


class UserLockRequest(BaseModel):
    """
    Body cho POST /api/users/{id}/lock và /unlock.
    
    lock:
        POST /api/users/{id}/lock   → { "reason": "Vi phạm nội quy" }
    unlock:
        POST /api/users/{id}/unlock → không cần body
    """
    reason: Optional[str] = None    # Lý do khóa (ghi vào audit log)
