# backend/routers/audit.py
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.audit_log import AuditLog
from models.user import User
from auth.dependencies import require_admin
from schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/admin/audit-logs", tags=["Audit Logs"])


@router.get(
    "",
    response_model=List[AuditLogOut],
    summary="Xem nhật ký hoạt động hệ thống",
    description="Chỉ Admin mới có quyền truy cập để xem lịch sử thao tác của các thành viên."
)
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200, description="Số lượng log tối đa trả về"),
    offset: int = Query(0, ge=0, description="Vị trí bắt đầu lấy log"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return logs
