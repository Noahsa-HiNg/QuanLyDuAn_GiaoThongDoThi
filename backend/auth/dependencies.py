"""
auth/dependencies.py — FastAPI Dependencies cho Auth
get_current_user : inject User object vào các endpoint cần login
require_admin    : chỉ cho phép role='admin'
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from auth.jwt_handler import decode_access_token
                                                                                                                                                                                                            
bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency: decode JWT token → trả về User object.
    Dùng trong route cần đăng nhập:
        @router.get("/protected")
        async def my_route(user: User = Depends(get_current_user)):
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị vô hiệu hóa",
        )
    return user
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency: chỉ cho phép user có role='admin'.
    Dùng trong route admin:
        @router.delete("/users/{id}")
        async def delete_user(user: User = Depends(require_admin)):
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện thao tác này (cần quyền admin)",
        )
    return current_user


def require_csgt(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency: cho phép cả 'csgt' lẫn 'admin'.
    Dùng cho route cần đăng nhập nhưng không yêu cầu quyền admin:
        @router.post("/traffic/crawl")
        def crawl(user: User = Depends(require_csgt)):
    """
    if current_user.role not in ("csgt", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không có quyền thực hiện thao tác này",
        )
    return current_user
