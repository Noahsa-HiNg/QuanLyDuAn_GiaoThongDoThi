"""
routers/traffic.py — API giao thông thời gian thực

Endpoints:
    GET /api/traffic/current          Tình trạng giao thông mới nhất toàn TP
    GET /api/traffic/current/{id}     Tình trạng mới nhất của 1 đường
"""

from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Street, TrafficData
from schemas.traffic import TrafficCurrentOut, TrafficSummaryOut, TZ_DANANG

router = APIRouter()

# Map congestion_level → nhãn tiếng Việt
CONGESTION_LABEL = {
    0: "Thông thoáng",
    1: "Chậm",
    2: "Kẹt xe",
}


def _build_traffic_out(street: Street, td: Optional[TrafficData]) -> TrafficCurrentOut:
    """
    Ghép dữ liệu street + traffic_data thành TrafficCurrentOut.
    td=None nếu đường chưa có dữ liệu giao thông.
    """
    # Chuyển timestamp UTC → giờ Đà Nẵng (+07:00) để hiển thị
    ts_vn = None
    if td and td.timestamp:
        ts_local = td.timestamp.astimezone(TZ_DANANG)
        ts_vn = ts_local.strftime("%Y-%m-%d %H:%M:%S +07:00")

    return TrafficCurrentOut(
        street_id        = street.id,
        street_name      = street.name,
        district_name    = street.district.name if street.district else None,
        avg_speed        = td.avg_speed if td else None,
        max_speed        = street.max_speed,
        congestion_level = td.congestion_level if td else None,
        congestion_label = CONGESTION_LABEL.get(td.congestion_level) if td else None,
        source           = td.source if td else None,
        timestamp        = td.timestamp if td else None,
        timestamp_vn     = ts_vn,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/traffic/current — Toàn bộ tuyến đường
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/traffic/current",
    response_model=TrafficSummaryOut,
    summary="Tình trạng giao thông hiện tại toàn thành phố",
    description="""
Trả về tình trạng giao thông **mới nhất** của tất cả tuyến đường.

Mỗi đường chỉ lấy **1 bản ghi mới nhất** từ bảng `traffic_data`.

**Filter:**
- `district_id` — Lọc chỉ xem đường trong 1 quận

**Mức congestion_level:**
- `0` 🟢 Thông thoáng — avg_speed ≥ 70% max_speed
- `1` 🟡 Chậm          — avg_speed 40–70% max_speed
- `2` 🔴 Kẹt xe        — avg_speed < 40% max_speed
- `null` — Chưa có dữ liệu
""",
)
def get_traffic_current(
    district_id: Optional[int] = Query(None, description="Lọc theo ID quận"),
    db: Session = Depends(get_db),
):
    # ── Truy vấn tất cả đường (kèm district) ──────────────────
    street_query = db.query(Street).options(joinedload(Street.district))
    if district_id is not None:
        street_query = street_query.filter(Street.district_id == district_id)
    streets = street_query.order_by(Street.name).all()

    if not streets:
        raise HTTPException(status_code=404, detail="Không có đường nào phù hợp")

    street_ids = [s.id for s in streets]

    # ── Subquery: timestamp mới nhất của mỗi đường ────────────
    # SELECT street_id, MAX(timestamp) FROM traffic_data GROUP BY street_id
    latest_subq = (
        db.query(
            TrafficData.street_id,
            func.max(TrafficData.timestamp).label("max_ts"),
        )
        .filter(TrafficData.street_id.in_(street_ids))
        .group_by(TrafficData.street_id)
        .subquery()
    )

    # ── JOIN để lấy bản ghi đầy đủ tương ứng với max_ts ──────
    latest_records = (
        db.query(TrafficData)
        .join(
            latest_subq,
            (TrafficData.street_id == latest_subq.c.street_id)
            & (TrafficData.timestamp == latest_subq.c.max_ts),
        )
        .all()
    )

    # Tạo dict {street_id: TrafficData} để tra cứu nhanh
    traffic_map: dict[int, TrafficData] = {td.street_id: td for td in latest_records}

    # ── Ghép kết quả ──────────────────────────────────────────
    result_list = [_build_traffic_out(s, traffic_map.get(s.id)) for s in streets]

    # ── Thống kê tổng hợp ─────────────────────────────────────
    green    = sum(1 for r in result_list if r.congestion_level == 0)
    yellow   = sum(1 for r in result_list if r.congestion_level == 1)
    red      = sum(1 for r in result_list if r.congestion_level == 2)
    no_data  = sum(1 for r in result_list if r.congestion_level is None)

    # Thời điểm dữ liệu mới nhất trong toàn bộ kết quả
    timestamps = [r.timestamp for r in result_list if r.timestamp]
    data_as_of = max(timestamps) if timestamps else None

    return TrafficSummaryOut(
        total_streets = len(result_list),
        green_count   = green,
        yellow_count  = yellow,
        red_count     = red,
        no_data_count = no_data,
        data_as_of    = data_as_of,
        streets       = result_list,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/traffic/current/{street_id} — 1 tuyến đường cụ thể
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/traffic/current/{street_id}",
    response_model=TrafficCurrentOut,
    summary="Tình trạng giao thông hiện tại của 1 tuyến đường",
)
def get_traffic_current_by_street(
    street_id: int,
    db: Session = Depends(get_db),
):
    # Lấy thông tin đường
    street = (
        db.query(Street)
        .options(joinedload(Street.district))
        .filter(Street.id == street_id)
        .first()
    )
    if not street:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đường id={street_id}")

    # Lấy bản ghi traffic mới nhất
    latest = (
        db.query(TrafficData)
        .filter(TrafficData.street_id == street_id)
        .order_by(TrafficData.timestamp.desc())
        .first()
    )

    return _build_traffic_out(street, latest)
