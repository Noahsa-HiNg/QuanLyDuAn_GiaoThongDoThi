"""
routers/traffic.py — API giao thống thời gian thực

Endpoints:
    GET  /api/traffic/current          Tình trạng giao thông mới nhất toàn TP
    GET  /api/traffic/current/{id}     Tình trạng mới nhất của 1 đường
    POST /api/traffic/crawl            Kích hoạt cào dữ liệu ngay (1 lần, chạy nền)
    GET  /api/traffic/crawl/status     Xem trạng thái lần cào gần nhất
"""

from typing import Optional
from datetime import datetime, timezone, timedelta
import json
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Street, TrafficData
from schemas.traffic import TrafficCurrentOut, TrafficSummaryOut, TZ_DANANG
from utils.geometry import split_path_into_zones
from services import cache as cache_svc   # Redis cache layer

router = APIRouter()

# Map congestion_level → nhãn tiếng Việt
CONGESTION_LABEL = {
    0: "Thông thoáng",
    1: "Chậm",
    2: "Kẹt xe",
}


def _get_centroids(street_ids: list[int], db: Session) -> dict[int, tuple]:
    """
    Lấy tọa độ centroid (lat, lon) của nhiều đường bằng SQL.
    Dùng để fallback khi PathLayer không có path data.
    """
    if not street_ids:
        return {}
    rows = db.execute(
        text("""
            SELECT id,
                   ST_Y(ST_Centroid(geometry)) AS lat,
                   ST_X(ST_Centroid(geometry)) AS lon
            FROM streets
            WHERE id = ANY(:ids) AND geometry IS NOT NULL
        """),
        {"ids": street_ids}
    ).fetchall()
    return {row.id: (row.lat, row.lon) for row in rows}




CONGESTION_COLORS = {
    0: [34,  197,  94, 220],   # Xanh lá — thông thoáng
    1: [234, 179,   8, 220],   # Vàng — chậm
    2: [239,  68,  68, 220],   # Đỏ — kẹt xe
    None: [148, 163, 184, 180], # Xám — chưa có data
}


def _get_paths(street_ids: list[int], db: Session) -> dict[int, list]:
    """Lấy [[lon, lat], ...] của từng đường từ geometry PostGIS."""
    if not street_ids:
        return {}
    rows = db.execute(
        text("""
            SELECT id, (ST_AsGeoJSON(geometry)::json -> 'coordinates') AS coords
            FROM streets WHERE id = ANY(:ids) AND geometry IS NOT NULL
        """),
        {"ids": street_ids}
    ).fetchall()
    result = {}
    for row in rows:
        if row.coords:
            coords = json.loads(row.coords) if isinstance(row.coords, str) else row.coords
            if coords and len(coords) >= 2:
                result[row.id] = coords
    return result


def _build_traffic_out(
    street: Street,
    segments_data: list[TrafficData],   # Bản ghi mới nhất của từng (street, segment_idx)
    full_path: Optional[list],          # [[lon, lat], ...] geometry đường
    centroid: Optional[tuple],          # (lat, lon) fallback
) -> TrafficCurrentOut:
    """
    Xây dựng TrafficCurrentOut với per-segment data.

    Nếu đường có nhiều segment (có geometry):  
      → chia full_path thành N zone (giống ingestion)
      → gán data thị trường của segment tương ứng vào từng zone
      → trả về `segments` = list[đoạn với path + color + speed]

    Nếu đường chỉ có 1 segment (fallback):  
      → `path` = full_path, `segments` = []
    """
    # ─ Tóm tắt chung cho street (dùng segment 0 hoặc segment đầu tiên)
    primary_td = segments_data[0] if segments_data else None

    ts_vn = None
    if primary_td and primary_td.timestamp:
        ts_local = primary_td.timestamp.astimezone(TZ_DANANG)
        ts_vn = ts_local.strftime("%Y-%m-%d %H:%M:%S +07:00")

    # ─ Tính average congestion toàn đường (hiển thị trong bảng)
    avg_cong = None
    avg_spd  = None
    if segments_data:
        levels = [td.congestion_level for td in segments_data if td.congestion_level is not None]
        speeds = [td.avg_speed for td in segments_data if td.avg_speed is not None]
        if levels:  avg_cong = round(sum(levels) / len(levels))
        if speeds:  avg_spd  = round(sum(speeds)  / len(speeds), 1)

    # ─ Xây dựng per-segment path + color (cho PathLayer)
    segments_out = []
    seg_map = {td.segment_idx: td for td in segments_data}

    # 🔥 LUÔN đảm bảo có ít nhất 1 segment
    if full_path and len(full_path) >= 2:

        if len(seg_map) <= 1:
            # 👉 fallback cho đường ngắn / chỉ có 1 segment
            td = segments_data[0] if segments_data else None
            cong = td.congestion_level if td else None

            segments_out.append({
                "segment_idx": 0,
                "path": full_path,
                "avg_speed": td.avg_speed if td else None,
                "congestion_level": cong,
                "color": CONGESTION_COLORS.get(cong, CONGESTION_COLORS[None]),
            })

        else:
            # 👉 đường dài (chia nhiều segment)
            n_zones = max(seg_map.keys()) + 1
            zones = split_path_into_zones(full_path, n_zones=n_zones)

            for zone in zones:
                idx = zone["segment_idx"]
                td  = seg_map.get(idx)
                cong = td.congestion_level if td else None

                segments_out.append({
                    "segment_idx": idx,
                    "path": zone["coords"],
                    "avg_speed": td.avg_speed if td else None,
                    "congestion_level": cong,
                    "color": CONGESTION_COLORS.get(cong, CONGESTION_COLORS[None]),
                })

    lat = centroid[0] if centroid else None
    lon = centroid[1] if centroid else None

    return TrafficCurrentOut(
        street_id        = street.id,
        street_name      = street.name,
        district_name    = street.district.name if street.district else None,
        avg_speed        = avg_spd,
        max_speed        = street.max_speed,
        congestion_level = avg_cong,
        congestion_label = CONGESTION_LABEL.get(avg_cong),
        source           = primary_td.source if primary_td else None,
        timestamp        = primary_td.timestamp if primary_td else None,
        timestamp_vn     = ts_vn,
        lat              = lat,
        lon              = lon,
        path             = full_path if not segments_out else None,
        segments         = segments_out,
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
    # ── Kiểm tra Redis cache (chỉ cache khi không filter district) ────────────
    # Lý do không cache khi filter: mỗi district cho kết quả khác nhau
    # → cần nhiều key cache → phức tạp không cần thiết
    use_cache = (district_id is None)
    if use_cache:
        cached = cache_svc.get_traffic()
        if cached is not None:
            return cached   # ✅ Cache HIT — trả về ngay, không query DB

    # ── Cache MISS → query DB bình thường ────────────────────────────────────
    street_query = db.query(Street).options(joinedload(Street.district))
    if district_id is not None:
        street_query = street_query.filter(Street.district_id == district_id)
    streets = street_query.order_by(Street.name).all()

    if not streets:
        raise HTTPException(status_code=404, detail="Không có đường nào phù hợp")

    street_ids = [s.id for s in streets]

    # ── Subquery: timestamp mới nhất của mỗi (street, SEGMENT) ───────────
    latest_subq = (
        db.query(
            TrafficData.street_id,
            TrafficData.segment_idx,
            func.max(TrafficData.timestamp).label("max_ts"),
        )
        .filter(TrafficData.street_id.in_(street_ids))
        .group_by(TrafficData.street_id, TrafficData.segment_idx)
        .subquery()
    )

    # ── JOIN lấy bản ghi đầy đủ mới nhất của từng (street, segment) ─────
    latest_records = (
        db.query(TrafficData)
        .join(
            latest_subq,
            (TrafficData.street_id  == latest_subq.c.street_id)
            & (TrafficData.segment_idx == latest_subq.c.segment_idx)
            & (TrafficData.timestamp   == latest_subq.c.max_ts),
        )
        .all()
    )

    # Dict {street_id: [TrafficData, ...]} — giữ tất cả segment của mỗi đường
    from collections import defaultdict
    traffic_map: dict[int, list] = defaultdict(list)
    for td in latest_records:
        traffic_map[td.street_id].append(td)

    # ── Lấy centroid (fallback) & full path của tất cả đường ─────────
    centroid_map = _get_centroids(street_ids, db)
    path_map     = _get_paths(street_ids, db)

    # ── Ghép kết quả ─────────────────────────────────────────
    result_list = [
        _build_traffic_out(
            s,
            segments_data = traffic_map.get(s.id, []),
            full_path     = path_map.get(s.id),
            centroid      = centroid_map.get(s.id),
        )
        for s in streets
    ]

    # ── Thống kê tổng hợp ─────────────────────────────────────
    green    = sum(1 for r in result_list if r.congestion_level == 0)
    yellow   = sum(1 for r in result_list if r.congestion_level == 1)
    red      = sum(1 for r in result_list if r.congestion_level == 2)
    no_data  = sum(1 for r in result_list if r.congestion_level is None)

    # Thời điểm dữ liệu mới nhất trong toàn bộ kết quả
    timestamps = [r.timestamp for r in result_list if r.timestamp]
    data_as_of = max(timestamps) if timestamps else None

    valid_speeds = [r.avg_speed for r in result_list if r.avg_speed is not None]
    avg_speed_city = round(sum(valid_speeds) / len(valid_speeds), 1) if valid_speeds else None

    response = TrafficSummaryOut(
        total_streets = len(result_list),
        green_count   = green,
        yellow_count  = yellow,
        red_count     = red,
        no_data_count = no_data,
        avg_speed_city  = avg_speed_city,
        data_as_of    = data_as_of,
        streets       = result_list,
    )

    # ── Lưu vào Redis cache (chỉ khi không filter district) ──────────────────
    if use_cache:
        # Pydantic → dict → JSON để lưu Redis
        cache_svc.set_traffic(response.model_dump(mode="json"))

    return response

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

    from collections import defaultdict

    # Lấy tất cả segment mới nhất của đường này
    latest_subq = (
        db.query(
            TrafficData.segment_idx,
            func.max(TrafficData.timestamp).label("max_ts"),
        )
        .filter(TrafficData.street_id == street_id)
        .group_by(TrafficData.segment_idx)
        .subquery()
    )
    segments_data = (
        db.query(TrafficData)
        .join(
            latest_subq,
            (TrafficData.segment_idx == latest_subq.c.segment_idx)
            & (TrafficData.timestamp == latest_subq.c.max_ts),
        )
        .filter(TrafficData.street_id == street_id)
        .all()
    )

    centroid = _get_centroids([street_id], db)
    path_data = _get_paths([street_id], db).get(street_id)

    return _build_traffic_out(
        street,
        segments_data = segments_data,
        full_path     = path_data,
        centroid      = centroid.get(street_id),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Trạng thái lần cào gần nhất (lưu in-memory, reset khi restart container)
# ─────────────────────────────────────────────────────────────────────────────
_crawl_status: dict = {
    "running"         : False,
    "last_started_at" : None,
    "last_result"     : None,   # dict kết quả từ crawl_all_streets()
}
_crawl_lock = threading.Lock()


def _run_crawl_in_background(db: Session):
    """Hàm chạy trong background thread — cập nhật _crawl_status."""
    global _crawl_status
    try:
        result = None
        from services.traffic_crawl import crawl_all_streets
        result = crawl_all_streets(db)
    except Exception as e:
        result = {"error": str(e)}
    finally:
        db.close()
        with _crawl_lock:
            _crawl_status["running"]     = False
            _crawl_status["last_result"] = result


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/traffic/crawl — Kích hoạt cào ngay (chạy nền)
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/traffic/crawl",
    summary="Kích hoạt cào dữ liệu traffic ngay lập tức (1 lần, chạy nền)",
    description="""
Cào dữ liệu TomTom cho **tất cả tuyến đường** đúng 1 lần.

- Chạy **bất đồng bộ** (nền) — trả về response ngay, không cần chờ.
- Gọi `GET /api/traffic/crawl/status` để xem kết quả sau khi hoàn tất.
- Nếu đang có lần cào chạy dở → trả về **409 Conflict**.

⏱ Thời gian ước tính: ~1–3 phút tùy số đường và quota.
""",
    status_code=202,
)
def trigger_crawl(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    global _crawl_status

    with _crawl_lock:
        if _crawl_status["running"]:
            raise HTTPException(
                status_code=409,
                detail="Đang có lần cào đang chạy. Vui lòng đợi hoàn tất.",
            )
        _crawl_status["running"]         = True
        _crawl_status["last_started_at"] = datetime.now(
            timezone(timedelta(hours=7))
        ).strftime("%H:%M:%S %d/%m/%Y +07")

    # Chạy nền để không block API
    background_tasks.add_task(_run_crawl_in_background, db)

    return {
        "message"   : "✅ Đã khởi động cào dữ liệu traffic (đang chạy nền)",
        "started_at": _crawl_status["last_started_at"],
        "status_url": "/api/traffic/crawl/status",
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/traffic/crawl/status — Xem trạng thái lần cào gần nhất
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/traffic/crawl/status",
    summary="Trạng thái lần cào dữ liệu gần nhất",
    description="Trả về trạng thái (đang chạy / hoàn tất) và kết quả tóm tắt của lần cào gần nhất.",
)
def get_crawl_status():
    with _crawl_lock:
        return {
            "running"         : _crawl_status["running"],
            "last_started_at" : _crawl_status["last_started_at"],
            "last_result"     : _crawl_status["last_result"],
        }
