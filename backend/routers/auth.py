"""
routers/auth.py — Endpoint đăng nhập / đăng xuất
POST /api/auth/login   → nhận {email, password}, trả JWT token
GET  /api/auth/me      → trả thông tin user đang đăng nhập (cần token)
POST /api/auth/logout  → (stateless: client xóa token phía FE)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from schemas.auth import LoginRequest, TokenResponse, UserInfo
from services.auth_service import auth_service
from auth.dependencies import get_current_user
from models.user import User


router = APIRouter(prefix="/auth")
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Đăng nhập và nhận JWT token",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Đăng nhập với email + password.
    - **email**: địa chỉ email đã đăng ký
    - **password**: mật khẩu (plaintext, HTTPS bảo vệ khi truyền)
    Trả về `access_token` (JWT). Lưu token này và gửi kèm mọi request
    cần xác thực dưới dạng header: `Authorization: Bearer <token>`
    """
    user = auth_service.authenticate_user(db, payload.email, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng, hoặc tài khoản đang bị khóa",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_service.create_token_for_user(user)
    return TokenResponse(
        access_token=token,
        user=UserInfo.model_validate(user)
    )
@router.get(
    "/me",
    response_model=UserInfo,
    summary="Lấy thông tin user đang đăng nhập",
)
def get_me(current_user: User = Depends(get_current_user)):
    """Trả về thông tin profile của user đang đăng nhập (cần JWT token)."""
    return UserInfo.model_validate(current_user)
@router.post(
    "/logout",
    summary="Đăng xuất (stateless)",
)
def logout():
    """
    JWT là stateless — server không lưu token.
    Client cần tự xóa token khỏi session_state / localStorage.
    """
    return {"message": "Đăng xuất thành công. Vui lòng xóa token phía client."}