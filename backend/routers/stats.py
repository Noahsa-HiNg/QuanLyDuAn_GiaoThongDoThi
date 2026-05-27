from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from schemas.stats import TopCongestedStreetResponse, TZ_DANANG
from auth.dependencies import require_csgt
from models.user import User

router = APIRouter(prefix="/stats", tags=["Stats"])

CONGESTION_LABEL = {
    0: "Thông thoáng",
    1: "Chậm",
    2: "Kẹt xe",
}


@router.get(
    "/top-congested",
    response_model=List[TopCongestedStreetResponse],
    summary="Top các tuyến đường kẹt xe nhất",
    description="Trả về danh sách các tuyến đường đang kẹt xe nhất dựa trên dữ liệu giao thông mới nhất.",
)
def get_top_congested_streets(
    limit: int = Query(10, ge=1, le=100, description="Số lượng tuyến đường giới hạn"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    # Bước 1: Lấy timestamp mới nhất bằng cách quét ngược từ index PK (cực nhanh <1ms)
    latest_ts_row = db.execute(
        text("SELECT timestamp FROM traffic_data ORDER BY id DESC LIMIT 1")
    ).fetchone()

    if not latest_ts_row or not latest_ts_row[0]:
        return []

    latest_timestamp = latest_ts_row[0]

    # Bước 2: Truy vấn top các đường kẹt nhất tại timestamp mới nhất
    # Sắp xếp theo:
    # 1. Mức kẹt giảm dần (Đỏ = 2 -> Vàng = 1)
    # 2. Tỷ lệ tốc độ thực tế/tốc độ thiết kế tăng dần (càng nhỏ = kẹt càng nặng)
    query = text("""
        SELECT td.street_id,
               s.name AS street_name,
               d.name AS district_name,
               td.avg_speed,
               s.max_speed,
               td.congestion_level,
               (td.avg_speed / COALESCE(NULLIF(s.max_speed, 0), 50)) AS ratio,
               td.timestamp
        FROM traffic_data td
        JOIN streets s ON td.street_id = s.id
        LEFT JOIN districts d ON s.district_id = d.id
        WHERE td.timestamp = :latest_timestamp
          AND td.congestion_level IS NOT NULL
        ORDER BY td.congestion_level DESC, ratio ASC
        LIMIT :limit
    """)

    rows = db.execute(
        query,
        {"latest_timestamp": latest_timestamp, "limit": limit}
    ).fetchall()

    results = []
    for row in rows:
        ts_vn = None
        if row.timestamp:
            ts_local = row.timestamp.astimezone(TZ_DANANG)
            ts_vn = ts_local.strftime("%Y-%m-%d %H:%M:%S +07:00")

        results.append(TopCongestedStreetResponse(
            street_id=row.street_id,
            street_name=row.street_name,
            district_name=row.district_name,
            avg_speed=row.avg_speed,
            max_speed=row.max_speed,
            congestion_level=row.congestion_level,
            congestion_label=CONGESTION_LABEL.get(row.congestion_level, "Chưa rõ"),
            ratio=round(row.ratio, 3) if row.ratio is not None else None,
            timestamp=row.timestamp,
            timestamp_vn=ts_vn,
        ))

    return results
