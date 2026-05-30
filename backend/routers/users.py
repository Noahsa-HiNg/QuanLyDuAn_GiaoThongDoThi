"""
routers/users.py — API Quản lý tài khoản (Admin only)

Endpoints:
    GET    /api/users              Danh sách tất cả user
    GET    /api/users/{id}         Thông tin 1 user
    POST   /api/users              Tạo tài khoản mới
    POST   /api/users/{id}/lock    Khóa tài khoản thủ công (vô thời hạn)
    POST   /api/users/{id}/unlock  Mở khóa tài khoản
    DELETE /api/users/{id}         Vô hiệu hóa tài khoản (is_active=False)

Tất cả endpoint đều yêu cầu quyền Admin.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from schemas.user import UserOut, UserCreateRequest, UserLockRequest, OfficerOut
from auth.dependencies import require_admin, require_csgt
from auth.password import hash_password

router = APIRouter(prefix="/users", tags=["Users"])


# ─────────────────────────────────────────────────────────────
# GET /api/users — Danh sách tất cả user
# ─────────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=list[UserOut],
    summary="Danh sách tất cả tài khoản",
)
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Trả về danh sách tất cả tài khoản. Chỉ Admin được xem."""
    return db.query(User).order_by(User.created_at.desc()).all()


# ─────────────────────────────────────────────────────────────
# GET /api/users/officers — Danh sách cảnh sát giao thông
# ─────────────────────────────────────────────────────────────
@router.get(
    "/officers",
    response_model=list[OfficerOut],
    summary="Danh sách cảnh sát giao thông (CSGT)",
    description="""
Trả về danh sách tài khoản CSGT trong hệ thống.

- **Quyền truy cập**: cả `admin` lẫn `csgt` đều gọi được.
- **active_only** (mặc định `true`): chỉ trả về tài khoản đang hoạt động.
- **search**: lọc theo tên hoặc email (không phân biệt hoa thường).
- Không bao gồm thông tin bảo mật (failed_attempts, locked_until).
""",
)
def list_officers(
    active_only: bool = Query(True,  description="Chỉ trả về tài khoản còn hoạt động"),
    search:      str  = Query("",    description="Tìm kiếm theo tên hoặc email"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    """
    Danh sách CSGT — trả về OfficerOut (không có trường nhạy cảm).

    Query params:
        active_only : bool  (default True)  — lọc is_active=True
        search      : str   (default "")    — tìm theo email hoặc full_name
    """
    q = db.query(User).filter(User.role == "csgt")

    if active_only:
        q = q.filter(User.is_active == True)  # noqa: E712

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        q = q.filter(
            (User.full_name.ilike(term)) | (User.email.ilike(term))
        )

    return q.order_by(User.full_name.asc()).all()


# ─────────────────────────────────────────────────────────────
# GET /api/users/{user_id} — Chi tiết 1 user
# ─────────────────────────────────────────────────────────────
@router.get(
    "/{user_id}",
    response_model=UserOut,
    summary="Thông tin chi tiết 1 tài khoản",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy user id={user_id}")
    return user


# ─────────────────────────────────────────────────────────────
# POST /api/users — Tạo tài khoản mới
# ─────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=UserOut,
    status_code=201,
    summary="Tạo tài khoản mới (Admin only)",
)
def create_user(
    payload: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin tạo tài khoản mới cho nhân viên CSGT.
    - Email phải unique.
    - Role chỉ được là 'csgt' hoặc 'admin'.
    """
    # Kiểm tra email trùng
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Email '{payload.email}' đã được sử dụng",
        )

    # Kiểm tra role hợp lệ
    if payload.role not in ("csgt", "admin"):
        raise HTTPException(
            status_code=400,
            detail="Role không hợp lệ. Chỉ chấp nhận: 'csgt', 'admin'",
        )

    new_user = User(
        email         = payload.email,
        password_hash = hash_password(payload.password),
        full_name     = payload.full_name,
        role          = payload.role,
        is_active     = True,
        is_locked     = False,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ─────────────────────────────────────────────────────────────
# POST /api/users/{user_id}/lock — Khóa tài khoản thủ công
# ─────────────────────────────────────────────────────────────
@router.post(
    "/{user_id}/lock",
    response_model=UserOut,
    summary="Khóa tài khoản thủ công (Admin only)",
    description="""
Admin khóa tài khoản vô thời hạn.

- `is_locked = True`, `locked_until = NULL` (khóa mãi, không tự hết hạn).
- User bị khóa → đăng nhập bị từ chối với thông báo "tài khoản bị khóa".
- Chỉ Admin gọi `/unlock` mới mở được.
""",
)
def lock_user(
    user_id: int,
    payload: UserLockRequest = UserLockRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy user id={user_id}")

    # Không cho phép Admin tự khóa chính mình
    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Không thể khóa chính tài khoản của bạn",
        )

    user.is_locked    = True
    user.locked_until = None   # NULL = khóa vô thời hạn (khác brute-force 15 phút)
    db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────
# POST /api/users/{user_id}/unlock — Mở khóa tài khoản
# ─────────────────────────────────────────────────────────────
@router.post(
    "/{user_id}/unlock",
    response_model=UserOut,
    summary="Mở khóa tài khoản (Admin only)",
)
def unlock_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Mở khóa tài khoản — reset cả khóa thủ công lẫn khóa brute-force.
    - `is_locked = False`
    - `locked_until = NULL`
    - `failed_attempts = 0`
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy user id={user_id}")

    user.is_locked      = False
    user.locked_until   = None
    user.failed_attempts = 0
    db.commit()
    db.refresh(user)
    return user


# ─────────────────────────────────────────────────────────────
# DELETE /api/users/{user_id} — Vô hiệu hóa tài khoản
# ─────────────────────────────────────────────────────────────
@router.delete(
    "/{user_id}",
    status_code=200,
    summary="Vô hiệu hóa tài khoản (Admin only)",
    description="""
**Không xóa hẳn** — chỉ đặt `is_active = False`.

Lý do: giữ lại audit log, incident history liên kết với user này.
Nếu muốn xóa hoàn toàn khỏi DB cần thực hiện thủ công qua DB console.
""",
)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy user id={user_id}")

    if user.id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Không thể vô hiệu hóa chính tài khoản của bạn",
        )

    user.is_active = False
    db.commit()
    return {"message": f"Tài khoản '{user.email}' đã bị vô hiệu hóa (is_active=False)"}
