"""
services/auth_service.py — Business logic cho đăng nhập
Tách logic khỏi router để dễ test và tái sử dụng.
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from models.user import User
from auth.password import verify_password
from auth.jwt_handler import create_access_token
class AuthService:
    def authenticate_user(self, db: Session, email: str, password: str) -> User | None:
        """
        Xác thực user với email + password.
        Quy trình:
          1. Tìm user theo email (None → trả None ngay)
          2. Kiểm tra is_active
          3. Kiểm tra brute-force lock (locked_until > now)
          4. Verify bcrypt password
          5. Nếu sai: tăng failed_attempts, khóa nếu >= 5 lần
          6. Nếu đúng: reset failed_attempts, cập nhật last_login
        Returns:
            User object nếu hợp lệ, None nếu sai email/password/bị khóa
        """
        # 1. Tìm user
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None  # Email không tồn tại
        # 2. Tài khoản có active không?
        if not user.is_active:
            return None
        # 3. Kiểm tra khóa tài khoản:
        #    - Khóa thủ công bởi Admin: is_locked=True, locked_until=NULL → khóa vô thời hạn
        #    - Khóa brute-force:        is_locked=True, locked_until > NOW → hết 15 phút tự mở
        now = datetime.now(timezone.utc)
        if user.is_locked:
            if user.locked_until is None:
                return None  # Khóa thủ công vô thời hạn → từ chối
            if user.locked_until > now:
                return None  # Brute-force, chưa hết thời gian khóa → từ chối
            # locked_until <= now: hết hạn → tự động mở khóa brute-force
            user.is_locked = False
            user.locked_until = None
        # 4. Verify password
        if not verify_password(password, user.password_hash):
            # Sai mật khẩu → tăng failed_attempts
            user.failed_attempts = (user.failed_attempts or 0) + 1
            if user.failed_attempts >= 5:
                # Khóa tài khoản 15 phút
                from datetime import timedelta
                user.is_locked = True
                user.locked_until = now + timedelta(minutes=15)
            db.commit()
            return None
        # 5. Đăng nhập thành công → reset đếm lỗi
        user.failed_attempts = 0
        user.is_locked = False
        user.locked_until = None
        user.last_login = now
        db.commit()
        db.refresh(user)
        return user

    def create_token_for_user(self, user: User) -> str:
        """Tạo JWT token chứa thông tin user."""
        return create_access_token({
            "sub": str(user.id),   # "sub" là claim chuẩn JWT cho user ID
            "email": user.email,
            "role": user.role,
        })


# Singleton instance — router import object này
auth_service = AuthService()
