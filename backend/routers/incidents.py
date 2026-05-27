# backend/routers/incidents.py
"""
incidents.py — CRUD API cho sự kiện lô cốt / sự cố giao thông

Endpoints:
    GET    /api/incidents          — Danh sách sự cố (filter + phân trang)
    GET    /api/incidents/{id}     — Chi tiết 1 sự cố
    POST   /api/incidents          — Tạo sự cố mới (CSGT/Admin)
    PUT    /api/incidents/{id}     — Cập nhật sự cố (CSGT/Admin)
    DELETE /api/incidents/{id}     — Xóa vĩnh viễn sự cố (Admin)

Quyền truy cập: Chỉ CSGT hoặc Admin (yêu cầu JWT token hợp lệ + role phù hợp)
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from models.incident import Incident
from models.user import User
from auth.dependencies import require_csgt
from schemas.incident import IncidentCreate, IncidentUpdate, IncidentOut

router = APIRouter(prefix="/incidents", tags=["Incidents"])


# ─────────────────────────────────────────────────────────────
# 1. GET /api/incidents — Danh sách sự cố (Có filter + Phân trang)
# ─────────────────────────────────────────────────────────────
@router.get(
    "",
    response_model=List[IncidentOut],
    summary="Lấy danh sách sự cố",
    description=(
        "Trả về danh sách sự cố/lô cốt với các bộ lọc tùy chọn. "
        "Kết quả được sắp xếp theo thời gian tạo mới nhất trước."
    ),
)
def list_incidents(
    is_active: Optional[bool] = Query(None, description="Lọc theo trạng thái hoạt động"),
    type: Optional[str] = Query(None, description="Lọc theo loại: roadblock | accident | event | community"),
    street_id: Optional[int] = Query(None, description="Lọc theo ID tuyến đường"),
    status_filter: Optional[str] = Query(None, alias="status", description="Lọc theo trạng thái: active | dispatched | resolved"),
    page: int = Query(1, ge=1, description="Trang hiện tại (bắt đầu từ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Số bản ghi mỗi trang (tối đa 100)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    query = db.query(Incident)

    # Áp dụng các bộ lọc
    if is_active is not None:
        query = query.filter(Incident.is_active == is_active)
    if type is not None:
        query = query.filter(Incident.type == type)
    if street_id is not None:
        query = query.filter(Incident.street_id == street_id)
    if status_filter is not None:
        query = query.filter(Incident.status == status_filter)

    offset = (page - 1) * page_size
    incidents = (
        query.order_by(Incident.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return incidents


# ─────────────────────────────────────────────────────────────
# 2. GET /api/incidents/{id} — Chi tiết 1 sự cố
# ─────────────────────────────────────────────────────────────
@router.get(
    "/{incident_id}",
    response_model=IncidentOut,
    summary="Xem chi tiết 1 sự cố",
)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sự cố với id={incident_id}",
        )
    return incident


# ─────────────────────────────────────────────────────────────
# 3. POST /api/incidents — Tạo sự cố/lô cốt mới
# ─────────────────────────────────────────────────────────────
@router.post(
    "",
    response_model=IncidentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo sự cố mới (Chỉ CSGT/Admin)",
    description=(
        "Tạo một bản ghi sự cố/lô cốt mới. "
        "Trường `created_by` được tự động gán từ tài khoản đang đăng nhập."
    ),
)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    new_incident = Incident(
        street_id=payload.street_id,
        type=payload.type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        severity=payload.severity,
        description=payload.description,
        status=payload.status,
        is_active=payload.is_active,
        created_by=current_user.id,  # Tự động gán ID của CSGT đang đăng nhập
    )
    db.add(new_incident)
    db.commit()
    db.refresh(new_incident)
    return new_incident


# ─────────────────────────────────────────────────────────────
# 4. PUT /api/incidents/{id} — Cập nhật thông tin sự cố
# ─────────────────────────────────────────────────────────────
@router.put(
    "/{incident_id}",
    response_model=IncidentOut,
    summary="Cập nhật sự cố",
    description=(
        "Cập nhật một hoặc nhiều trường của sự cố. "
        "Khi `status` được chuyển sang `resolved`, hệ thống tự động "
        "đặt `is_active = False` và điền `end_time` nếu chưa có."
    ),
)
def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sự cố với id={incident_id}",
        )

    # Chỉ cập nhật các trường được gửi lên trong payload (exclude_unset=True)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(incident, key, value)

    # Logic đặc biệt: Chuyển sang 'resolved' → tắt cờ active + điền end_time
    if update_data.get("status") == "resolved":
        incident.is_active = False
        if not incident.end_time:
            incident.end_time = datetime.now(timezone.utc)

    db.commit()
    db.refresh(incident)
    return incident


# ─────────────────────────────────────────────────────────────
# 5. DELETE /api/incidents/{id} — Xóa sự cố vật lý
# ─────────────────────────────────────────────────────────────
@router.delete(
    "/{incident_id}",
    status_code=status.HTTP_200_OK,
    summary="Xóa vĩnh viễn sự cố (Admin)",
    description=(
        "Xóa hoàn toàn bản ghi sự cố khỏi cơ sở dữ liệu. "
        "Hành động này không thể hoàn tác. "
        "Thường dùng để xóa dữ liệu nhập sai."
    ),
)
def delete_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy sự cố với id={incident_id}",
        )

    db.delete(incident)
    db.commit()
    return {"message": f"Đã xóa thành công sự cố id={incident_id} ra khỏi hệ thống"}
