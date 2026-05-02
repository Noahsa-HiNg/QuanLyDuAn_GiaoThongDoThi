from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt


from config import settings

def create_access_token(data:dict) -> str:
    """
    Tạo JWT access token.
    Args:
        data: dict chứa các claim (sub, email, role, ...)
    Returns:
        JWT token dạng string (3 phần, phân cách bởi dấu chấm)
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc)+timedelta(hours=settings.jwt_expire_hours)
    to_encode["exp"] = expire
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

def decode_access_token(token:str) -> dict:
    """
    Giải mã JWT access token và trả về payload.
    Args:
        token: JWT token dạng string
    Returns:
        dict chứa các claim (sub, email, role, ...)
    Raises:
        JWTError: nếu token hết hạn, sai chữ ký, hoặc bị giả mạo
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        raise JWTError(str(e))