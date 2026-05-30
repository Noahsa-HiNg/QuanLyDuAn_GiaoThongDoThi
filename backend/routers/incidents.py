# backend/routers/incidents.py
"""
incidents.py — CRUD API cho sự kiện lô cốt / sự cố giao thông

Endpoints:
    GET    /api/incidents                     — Danh sách sự cố (filter + phân trang)
    GET    /api/incidents/{id}                — Chi tiết 1 sự cố
    POST   /api/incidents                     — Tạo sự cố mới (CSGT/Admin)
    PUT    /api/incidents/{id}                — Cập nhật sự cố (CSGT/Admin)
    DELETE /api/incidents/{id}                — Xóa vĩnh viễn sự cố (Admin)
    POST   /api/incidents/crawl-accidents     — Trigger cào HERE API ngay (Admin)
    GET    /api/incidents/crawl-accidents/status — Xem kết quả cào gần nhất (Admin)

Quyền truy cập: Chỉ CSGT hoặc Admin (yêu cầu JWT token hợp lệ + role phù hợp)
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
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
# 10. GET /api/incidents/map-data — Dữ liệu incidents + lat/lon cho Map
# Yêu cầu quyền CSGT/Admin → frontend bản đồ gọi kèm token
# ─────────────────────────────────────────────────────────────
@router.get(
    "/map-data",
    summary="Lấy danh sách incidents kèm tọa độ GPS để hiển thị trên bản đồ",
    description=(
        "Trả về tất cả incidents đang active, join với geometry của đường "
        "để lấy lat/lon centroid. Yêu cầu quyền CSGT/Admin."
    ),
    status_code=status.HTTP_200_OK,
)
def get_incidents_map_data(
    db: Session = Depends(get_db),
    type: Optional[str] = Query(None, description="Lọc theo loại: accident, roadblock, event, community"),
    source: Optional[str] = Query(None, description="Lọc theo nguồn: manual, here_api"),
    active_only: bool = Query(True, description="Chỉ lấy incidents đang active"),
    current_user: User = Depends(require_csgt),
):
    from sqlalchemy import text as _sql_text

    # Build WHERE clause
    filters = []
    params: dict = {}
    if active_only:
        filters.append("i.is_active = TRUE")
    if type:
        filters.append("i.type = :inc_type")
        params["inc_type"] = type
    if source:
        filters.append("i.source = :source")
        params["source"] = source

    and_clause = ("AND " + " AND ".join(filters)) if filters else ""

    sql = _sql_text(f"""
        SELECT
            i.id,
            i.type,
            i.severity,
            i.status,
            i.description,
            i.source,
            i.here_incident_id  AS external_id,
            i.start_time,
            i.end_time,
            i.is_active,
            s.name              AS street_name,
            d.name              AS district,
            ST_Y(ST_Centroid(s.geometry)) AS lat,
            ST_X(ST_Centroid(s.geometry)) AS lon
        FROM incidents i
        JOIN streets s ON s.id = i.street_id
        LEFT JOIN districts d ON d.id = s.district_id
        WHERE s.geometry IS NOT NULL
          { "AND " + " AND ".join(filters) if filters else "" }
        ORDER BY i.start_time DESC
        LIMIT 500
    """)

    rows = db.execute(sql, params).fetchall()

    features = []
    for r in rows:
        if r.lat is None or r.lon is None:
            continue
        features.append({
            "id"         : r.id,
            "lat"        : float(r.lat),
            "lon"        : float(r.lon),
            "type"       : r.type,
            "severity"   : r.severity,
            "status"     : r.status,
            "description": r.description or "",
            "source"     : r.source,
            "external_id": r.external_id,
            "street_name": r.street_name,
            "district"   : r.district,
            "start_time" : r.start_time.isoformat() if r.start_time else None,
            "end_time"   : r.end_time.isoformat()   if r.end_time   else None,
            "is_active"  : r.is_active,
        })

    return {
        "total"   : len(features),
        "incidents": features,
    }


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
    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )
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
    current_user: User = Depends(require_csgt),  # CSGT cũng được xóa
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





# Cache kết quả cào TomTom incidents gần nhất
_last_tomtom_crawl: dict = {}


# ─────────────────────────────────────────────────────────────
# 8. POST /api/incidents/crawl-incidents — Cào TomTom Incidents
# ─────────────────────────────────────────────────────────────
@router.post(
    "/crawl-incidents",
    summary="Cào sự cố giao thông từ TomTom (tai nạn, thi công, ngập lụt)",
    description=(
        "Gọi TomTom Traffic Incidents API v5 để lấy tất cả sự cố tại Đà Nẵng:\n"
        "- **Cat 7** (🚧 Road Works): Thi công / sửa chữa đường\n"
        "- **Cat 6** (⚠️ Lane Closed): Làn đường bị đóng\n"
        "- **Cat 1** (🚗 Accident): Tai nạn giao thông\n"
        "- **Cat 8/9** (🌊 Flood/Wind): Ngập lụt, đóng do thời tiết\n\n"
        "Kết quả được match tự động vào đường gần nhất (KDTree ≤500m) "
        "và dedup bằng TomTom ID (không bao giờ insert trùng)."
    ),
    status_code=status.HTTP_200_OK,
)
def trigger_crawl_tomtom_incidents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    global _last_tomtom_crawl
    from services.tomtom_incidents import fetch_tomtom_incidents

    result = fetch_tomtom_incidents(db)
    _last_tomtom_crawl = result

    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Lỗi cào TomTom Incidents: {result['error']}",
        )

    return {
        "success"         : True,
        "message"         : (
            f"✅ TomTom Incidents: {result.get('fetched', 0)} sự cố từ API, "
            f"lưu {result.get('saved', 0)} mới, "
            f"bỏ qua {result.get('skipped_dup', 0)} trùng, "
            f"{result.get('skipped_no_match', 0)} không match đường"
        ),
        "fetched"         : result.get("fetched", 0),
        "saved"           : result.get("saved", 0),
        "skipped_dup"     : result.get("skipped_dup", 0),
        "skipped_no_match": result.get("skipped_no_match", 0),
        "by_category"     : result.get("by_category", {}),
        "errors"          : result.get("errors", []),
        "duration_seconds": result.get("duration_seconds", 0),
        "timestamp"       : result.get("timestamp", ""),
        "triggered_by"    : current_user.email,
    }


# ─────────────────────────────────────────────────────────────
# 9. GET /api/incidents/crawl-incidents/status
# ─────────────────────────────────────────────────────────────
@router.get(
    "/crawl-incidents/status",
    summary="Xem kết quả cào TomTom Incidents lần gần nhất",
    status_code=status.HTTP_200_OK,
)
def get_tomtom_crawl_status(
    current_user: User = Depends(require_csgt),
):
    if not _last_tomtom_crawl:
        return {
            "status" : "never_run",
            "message": "Chưa cào lần nào. Gọi POST /api/incidents/crawl-incidents.",
        }
    return {
        "status": "ok" if not _last_tomtom_crawl.get("error") else "error",
        **_last_tomtom_crawl,
    }


# ─────────────────────────────────────────────────────────────
# 10. GET /api/incidents/map-data — Dữ liệu incidents + lat/lon cho Map
# Yêu cầu quyền CSGT/Admin → frontend bản đồ gọi kèm token
# ─────────────────────────────────────────────────────────────




