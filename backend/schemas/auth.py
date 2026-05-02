"""
schemas/auth.py — Pydantic models cho Auth endpoints
LoginRequest  : body của POST /api/auth/login
TokenResponse : response trả về sau khi login thành công
UserInfo      : thông tin user nhúng trong response (không có password)
"""

from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserInfo(BaseModel):
    id: int
    email: EmailStr
    role: str  # 'csgt', 'admin'

    model_config = {"from_attributes": True}  # Cho phép đọc từ SQLAlchemy ORM object

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    user: UserInfo