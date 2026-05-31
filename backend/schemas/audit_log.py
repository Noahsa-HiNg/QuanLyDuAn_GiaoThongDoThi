# backend/schemas/audit_log.py
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from schemas.user import OfficerOut


class AuditLogOut(BaseModel):
    """Schema trả về thông tin nhật ký hệ thống"""
    id: int
    user_id: Optional[int] = None
    action: str
    target_table: Optional[str] = None
    target_id: Optional[int] = None
    detail: Optional[Any] = None
    ip_address: Optional[str] = None
    created_at: datetime
    
    user: Optional[OfficerOut] = None

    class Config:
        from_attributes = True
