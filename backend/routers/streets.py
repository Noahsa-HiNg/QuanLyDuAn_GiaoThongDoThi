"""
routers/streets.py — API endpoints cho danh sách tuyến đường

Endpoints:
    GET  /api/streets              Danh sách đường (có filter + phân trang)
    GET  /api/streets/{id}         Chi tiết 1 đường
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Street
from schemas.street import StreetOut, StreetListOut

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/streets — Danh sách tuyến đường
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/streets",
    response_model=StreetListOut,
    summary="Lấy danh sách tuyến đường",
    description="""
Trả về danh sách tất cả tuyến đường ở Đà Nẵng.

**Filter:**
- `district_id` — Lọc theo quận
- `name` — Tìm kiếm theo tên đường (không phân biệt hoa thường)

**Phân trang:**
- `page` — Trang hiện tại (bắt đầu từ 1)
- `page_size` — Số lượng mỗi trang (tối đa 100)

**Ví dụ:**
- `/api/streets` → tất cả đường
- `/api/streets?district_id=1` → đường thuộc Hải Châu
- `/api/streets?name=bạch` → tìm đường có \"bạch\" trong tên
- `/api/streets?page=2&page_size=10` → trang 2, mỗi trang 10 đường
""",
)
def get_streets(
    district_id: Optional[int] = Query(None,  description="Lọc theo ID quận"),
    name: Optional[str]        = Query(None,  description="Tìm kiếm tên đường"),
    page: int                  = Query(1,     ge=1,       description="Trang hiện tại"),
    page_size: int             = Query(20,    ge=1, le=100, description="Số lượng / trang"),
    db: Session                = Depends(get_db),
):
    # joinedload(Street.district) = load district cùng 1 query SQL (tránh N+1)
    query = db.query(Street).options(joinedload(Street.district))

    # ── Filter ────────────────────────────────────────────────
    if district_id is not None:
        query = query.filter(Street.district_id == district_id)

    if name:
        query = query.filter(Street.name.ilike(f"%{name}%"))  # không phân biệt hoa thường

    # ── Đếm tổng (trước khi phân trang) ──────────────────────
    total = query.count()

    # ── Phân trang ────────────────────────────────────────────
    offset = (page - 1) * page_size
    streets = (
        query
        .order_by(Street.name)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return StreetListOut(
        total=total,
        page=page,
        page_size=page_size,
        data=streets,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/streets/{street_id} — Chi tiết 1 tuyến đường
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/streets/{street_id}",
    response_model=StreetOut,
    summary="Lấy chi tiết 1 tuyến đường",
)
def get_street_by_id(
    street_id: int,
    db: Session = Depends(get_db),
):
    street = (
        db.query(Street)
        .options(joinedload(Street.district))
        .filter(Street.id == street_id)
        .first()
    )

    if not street:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy đường id={street_id}"
        )

    return street
