"""
routers/traffic.py — API giao thông thời gian thực

Endpoints:
    GET  /api/traffic/current              Tình trạng giao thông mới nhất toàn TP
    GET  /api/traffic/current/{id}         Tình trạng mới nhất của 1 đường

    ─── Chế độ cào ───────────────────────────────────────────
    POST /api/traffic/crawl                [CHẾ ĐỘ 1] Cào toàn bộ đường — 1 lần (nền)
    GET  /api/traffic/crawl/status         Xem trạng thái lần cào 1-lần gần nhất

    POST /api/traffic/crawl/loop/start     [CHẾ ĐỘ 2] Bắt đầu cào vòng lặp liên tục
    POST /api/traffic/crawl/loop/stop      [CHẾ ĐỘ 2] Dừng vòng lặp cào
    GET  /api/traffic/crawl/loop/status    [CHẾ ĐỘ 2] Trạng thái vòng lặp

    POST /api/traffic/crawl/{street_id}    [CHẾ ĐỘ 3] Cào 1 đường duy nhất — 1 lần

    ─── Đồng bộ max_speed từ HERE freeflow ───────────────────
    POST /api/traffic/sync-max-speed       Cập nhật max_speed toàn bộ đường (nền)
    GET  /api/traffic/sync-max-speed/status Trạng thái lần đồng bộ gần nhất
"""

from typing import Optional
from datetime import datetime, timezone, timedelta
import io
import json
import threading

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Street, TrafficData
from schemas.traffic import TrafficCurrentOut, TrafficSummaryOut, TZ_DANANG
from utils.geometry import split_path_into_zones
from services import cache as cache_svc   # Redis cache layer
from redis_client import redis_client     # Dùng trực tiếp cho geometry/state cache

from auth.dependencies import require_csgt, require_admin
from models.user import User

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
    response_class=JSONResponse,
)
def get_traffic_current(
    district_id: Optional[int] = Query(None, description="Lọc theo ID quận"),
    db: Session = Depends(get_db),
):
    # ── Kiểm tra Redis cache ───────────────────────────────────────────────────
    use_cache = (district_id is None)
    if use_cache:
        raw = cache_svc.get_traffic_raw()   # Lấy raw JSON string (không parse)
        if raw is not None:
            return Response(                 # ✅ Cache HIT — trả thẳng bytes, không parse
                content=raw,
                media_type="application/json"
            )

    # ── Cache MISS → query DB dùng Materialized View ──────────────────────────
    # 1 query JOIN: streets + districts + latest_traffic + geometry (~185ms)
    district_filter = ""
    params: dict = {}
    if district_id is not None:
        district_filter = "AND s.district_id = :district_id"
        params["district_id"] = district_id

    rows = db.execute(text(f"""
        SELECT
            s.id                                        AS street_id,
            s.name                                      AS street_name,
            d.name                                      AS district_name,
            s.max_speed,
            ST_Y(ST_Centroid(s.geometry))               AS lat,
            ST_X(ST_Centroid(s.geometry))               AS lon,
            (ST_AsGeoJSON(s.geometry)::json -> 'coordinates') AS coords,
            lt.segment_idx,
            lt.avg_speed,
            lt.free_flow_speed,
            lt.congestion_level,
            lt.source,
            lt.timestamp
        FROM streets s
        LEFT JOIN districts d   ON s.district_id = d.id
        JOIN  latest_traffic lt ON lt.street_id  = s.id
        WHERE s.geometry IS NOT NULL
        {district_filter}
        ORDER BY s.name
    """), params).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="Không có đường nào phù hợp")

    # ── Nhóm rows theo street_id ──────────────────────────────────────────────
    from collections import defaultdict
    # {street_id: {meta, segments: [...]}}
    street_map: dict = {}
    for row in rows:
        sid = row.street_id
        if sid not in street_map:
            coords = None
            if row.coords:
                c = json.loads(row.coords) if isinstance(row.coords, str) else row.coords
                if c and len(c) >= 2:
                    coords = c
            street_map[sid] = {
                "street_id"   : sid,
                "street_name" : row.street_name,
                "district_name": row.district_name,
                "max_speed"   : row.max_speed,
                "lat"         : row.lat,
                "lon"         : row.lon,
                "_path"       : coords,   # tạm, xóa sau
                "segments"    : [],
                "_seg_data"   : [],       # tạm, xóa sau
            }
        street_map[sid]["_seg_data"].append({
            "segment_idx"    : row.segment_idx,
            "avg_speed"      : row.avg_speed,
            "congestion_level": row.congestion_level,
            "source"         : row.source,
            "timestamp"      : row.timestamp,
        })

    # ── Build raw dict cho từng đường ─────────────────────────────────────────
    streets_out = []
    green = yellow = red = no_data = 0
    timestamps_all = []
    speeds_all     = []

    for s in sorted(street_map.values(), key=lambda x: x["street_name"] or ""):
        seg_data  = s.pop("_seg_data")
        full_path = s.pop("_path")

        # Tính avg congestion + speed toàn đường
        levels = [sd["congestion_level"] for sd in seg_data if sd["congestion_level"] is not None]
        speeds = [sd["avg_speed"]        for sd in seg_data if sd["avg_speed"]        is not None]
        avg_cong = round(sum(levels) / len(levels)) if levels else None
        avg_spd  = round(sum(speeds)  / len(speeds), 1) if speeds else None

        # Timestamp + source từ segment đầu tiên
        primary    = seg_data[0] if seg_data else {}
        ts         = primary.get("timestamp")
        ts_vn      = None
        if ts:
            ts_local = ts.astimezone(TZ_DANANG)
            ts_vn    = ts_local.strftime("%Y-%m-%d %H:%M:%S +07:00")
            timestamps_all.append(ts)
        if avg_spd is not None:
            speeds_all.append(avg_spd)

        # Build segments (per-segment path + color) — inline logic cũ
        segments_out = []
        seg_map = {sd["segment_idx"]: sd for sd in seg_data}
        if full_path and len(full_path) >= 2:
            if len(seg_map) <= 1:
                sd   = seg_data[0] if seg_data else {}
                cong = sd.get("congestion_level")
                segments_out.append({
                    "segment_idx"    : 0,
                    "path"           : full_path,
                    "avg_speed"      : sd.get("avg_speed"),
                    "congestion_level": cong,
                    "color"          : CONGESTION_COLORS.get(cong, CONGESTION_COLORS[None]),
                })
            else:
                n_zones = max(seg_map.keys()) + 1
                zones   = split_path_into_zones(full_path, n_zones=n_zones)
                for zone in zones:
                    idx  = zone["segment_idx"]
                    sd   = seg_map.get(idx, {})
                    cong = sd.get("congestion_level")
                    segments_out.append({
                        "segment_idx"    : idx,
                        "path"           : zone["coords"],
                        "avg_speed"      : sd.get("avg_speed"),
                        "congestion_level": cong,
                        "color"          : CONGESTION_COLORS.get(cong, CONGESTION_COLORS[None]),
                    })

        # Đếm thống kê
        if avg_cong == 0:    green   += 1
        elif avg_cong == 1:  yellow  += 1
        elif avg_cong == 2:  red     += 1
        else:                no_data += 1

        streets_out.append({
            "street_id"      : s["street_id"],
            "street_name"    : s["street_name"],
            "district_name"  : s["district_name"],
            "avg_speed"      : avg_spd,
            "max_speed"      : s["max_speed"],
            "congestion_level": avg_cong,
            "congestion_label": CONGESTION_LABEL.get(avg_cong),
            "source"         : primary.get("source"),
            "timestamp"      : ts.isoformat() if ts else None,
            "timestamp_vn"   : ts_vn,
            "lat"            : s["lat"],
            "lon"            : s["lon"],
            "path"           : full_path if not segments_out else None,
            "segments"       : segments_out,
            "color"          : CONGESTION_COLORS.get(avg_cong, CONGESTION_COLORS[None]),
        })

    data_as_of     = max(timestamps_all).isoformat() if timestamps_all else None
    avg_speed_city = round(sum(speeds_all) / len(speeds_all), 1) if speeds_all else None

    response = {
        "total_streets" : len(streets_out),
        "green_count"   : green,
        "yellow_count"  : yellow,
        "red_count"     : red,
        "no_data_count" : no_data,
        "avg_speed_city": avg_speed_city,
        "data_as_of"    : data_as_of,
        "streets"       : streets_out,
    }

    # ── Lưu vào Redis cache (chỉ khi không filter district) ──────────────────
    if use_cache:
        cache_svc.set_traffic(response)

    return JSONResponse(content=response)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/streets/geometry — Geometry tĩnh (load 1 lần, cache dài)
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/traffic/streets-geometry",
    summary="Geometry tất cả tuyến đường (load 1 lần)",
    description="""
Trả về **geometry (tọa độ vẽ đường)** của tất cả tuyến đường có traffic data.

**Mục đích:** Tách geometry (tĩnh, ~17MB) ra khỏi traffic state (động, ~1MB).
Frontend chỉ cần gọi endpoint này **1 lần duy nhất** rồi lưu vào `st.session_state`.

**Kết hợp với:** `GET /api/traffic/state` để lấy trạng thái giao thông.

**Cache:** 1 giờ (geometry đường không thay đổi thường xuyên).
""",
    response_class=Response,
    tags=["Streets"],
)
def get_streets_geometry(db: Session = Depends(get_db)):
    """
    Trả raw JSON geometry của tất cả đường có traffic data.
    Cache Redis 1 giờ — geometry gần như không thay đổi.
    """
    import services.cache as _cache

    CACHE_KEY_GEOMETRY = "streets:geometry"
    TTL_GEOMETRY = 3600  # 1 giờ

    # ── Kiểm tra cache ─────────────────────────────────────────────────────
    raw = redis_client.get(CACHE_KEY_GEOMETRY)
    if raw is not None:
        return Response(content=raw, media_type="application/json")

    # ── Cache MISS → query DB ──────────────────────────────────────────────
    rows = db.execute(text("""
        SELECT
            s.id                                            AS street_id,
            s.name                                          AS street_name,
            d.name                                          AS district_name,
            s.max_speed,
            ST_Y(ST_Centroid(s.geometry))                   AS lat,
            ST_X(ST_Centroid(s.geometry))                   AS lon,
            (ST_AsGeoJSON(s.geometry)::json -> 'coordinates') AS coords,
            COUNT(lt.segment_idx)                           AS segment_count
        FROM streets s
        LEFT JOIN districts d   ON s.district_id = d.id
        JOIN  latest_traffic lt ON lt.street_id  = s.id
        WHERE s.geometry IS NOT NULL
        GROUP BY s.id, s.name, d.name, s.max_speed, s.geometry
        ORDER BY s.name
    """)).fetchall()

    streets = []
    for row in rows:
        coords = None
        if row.coords:
            c = json.loads(row.coords) if isinstance(row.coords, str) else row.coords
            if c and len(c) >= 2:
                coords = c

        streets.append({
            "street_id"    : row.street_id,
            "street_name"  : row.street_name,
            "district_name": row.district_name,
            "max_speed"    : row.max_speed,
            "lat"          : row.lat,
            "lon"          : row.lon,
            "path"         : coords,
            "segment_count": row.segment_count,
        })

    result = {"total": len(streets), "streets": streets}
    raw_json = json.dumps(result, ensure_ascii=False, default=str)

    # ── Lưu cache 1 giờ ───────────────────────────────────────────────────
    redis_client.setex(name=CACHE_KEY_GEOMETRY, time=TTL_GEOMETRY, value=raw_json)

    return Response(content=raw_json, media_type="application/json")


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/traffic/state — Trạng thái giao thông nhẹ (refresh thường xuyên)
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/traffic/state",
    summary="Trạng thái giao thông (nhẹ, chỉ màu + tốc độ)",
    description="""
Trả về **trạng thái giao thông** của tất cả tuyến đường — **không có geometry**.

**Mục đích:** Endpoint nhẹ (~1MB) để refresh thường xuyên mà không phải tải lại geometry.

**Kết hợp với:** `GET /api/streets/geometry` (load 1 lần, lưu session_state).

**Cache:** 270 giây (cùng chu kỳ cào dữ liệu).

**Cấu trúc mỗi phần tử:**
```json
{
  "street_id": 1,
  "congestion_level": 0,
  "congestion_label": "Thông thoáng",
  "avg_speed": 55.2,
  "color": [34, 197, 94, 220],
  "segments": [{"segment_idx": 0, "congestion_level": 0, "color": [...]}]
}
```

**Congestion levels:** 0=Xanh, 1=Vàng, 2=Đỏ, null=Không có data.
""",
    response_class=Response,
)
def get_traffic_state(db: Session = Depends(get_db)):
    """
    Trả trạng thái giao thông nhẹ (không geometry).
    Cache Redis 270s — cùng chu kỳ cào.
    """
    CACHE_KEY_STATE = "traffic:state"
    TTL_STATE = 270

    # ── Kiểm tra cache ─────────────────────────────────────────────────────
    raw = redis_client.get(CACHE_KEY_STATE)
    if raw is not None:
        return Response(content=raw, media_type="application/json")

    # ── Cache MISS → query latest_traffic ─────────────────────────────────
    rows = db.execute(text("""
        SELECT
            lt.street_id,
            lt.segment_idx,
            lt.avg_speed,
            lt.congestion_level,
            lt.source,
            lt.timestamp
        FROM latest_traffic lt
        ORDER BY lt.street_id, lt.segment_idx
    """)).fetchall()

    if not rows:
        return Response(
            content=json.dumps({"total": 0, "streets": [], "data_as_of": None}),
            media_type="application/json"
        )

    # ── Nhóm theo street_id ────────────────────────────────────────────────
    from collections import defaultdict
    street_segs: dict = defaultdict(list)
    for row in rows:
        street_segs[row.street_id].append(row)

    streets_out = []
    timestamps_all = []

    for street_id, segs in sorted(street_segs.items()):
        levels = [s.congestion_level for s in segs if s.congestion_level is not None]
        speeds = [s.avg_speed        for s in segs if s.avg_speed        is not None]
        avg_cong = round(sum(levels) / len(levels)) if levels else None
        avg_spd  = round(sum(speeds)  / len(speeds), 1) if speeds else None

        ts = segs[0].timestamp
        if ts:
            timestamps_all.append(ts)

        segments_out = [
            {
                "segment_idx"    : s.segment_idx,
                "congestion_level": s.congestion_level,
                "avg_speed"      : s.avg_speed,
                "color"          : CONGESTION_COLORS.get(s.congestion_level,
                                                         CONGESTION_COLORS[None]),
            }
            for s in segs
        ]

        streets_out.append({
            "street_id"      : street_id,
            "congestion_level": avg_cong,
            "congestion_label": CONGESTION_LABEL.get(avg_cong),
            "avg_speed"      : avg_spd,
            "color"          : CONGESTION_COLORS.get(avg_cong, CONGESTION_COLORS[None]),
            "source"         : segs[0].source,
            "timestamp"      : ts.isoformat() if ts else None,
            "segments"       : segments_out,
        })

    data_as_of = max(timestamps_all).isoformat() if timestamps_all else None

    result = {
        "total"     : len(streets_out),
        "data_as_of": data_as_of,
        "streets"   : streets_out,
    }
    raw_json = json.dumps(result, ensure_ascii=False, default=str)

    # ── Lưu cache 270s ─────────────────────────────────────────────────────
    redis_client.setex(name=CACHE_KEY_STATE, time=TTL_STATE, value=raw_json)

    return Response(content=raw_json, media_type="application/json")


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


@router.get(
    "/export/traffic",
    summary="Xuất CSV traffic theo ngày",
    response_class=StreamingResponse,
)
def export_traffic(
    date: str = Query(..., description="Ngày theo định dạng YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    """Trả file CSV các bản ghi traffic trong ngày được chỉ định."""
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Ngày không hợp lệ. Vui lòng dùng định dạng YYYY-MM-DD.",
        )

    rows = db.execute(text("""
        SELECT
            td.id,
            td.street_id,
            s.name AS street_name,
            d.name AS district_name,
            td.segment_idx,
            td.avg_speed,
            td.free_flow_speed,
            td.congestion_level,
            td.source,
            (td.timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh') AS timestamp
        FROM traffic_data td
        LEFT JOIN streets s ON td.street_id = s.id
        LEFT JOIN districts d ON s.district_id = d.id
        WHERE (td.timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh')::date = :query_date
        ORDER BY td.timestamp ASC, td.street_id, td.segment_idx
    """), {"query_date": query_date}).fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Không có dữ liệu traffic cho ngày được chọn.",
        )

    df = pd.DataFrame([dict(row) for row in rows])
    if not df.empty and "timestamp" in df.columns:
        df["timestamp"] = df["timestamp"].apply(
            lambda ts: ts.strftime("%Y-%m-%d %H:%M:%S") if ts is not None else ""
        )

    stream = io.StringIO()
    df.to_csv(stream, index=False, encoding="utf-8-sig")
    stream.seek(0)

    headers = {
        "Content-Disposition": f"attachment; filename=traffic_{date}.csv"
    }
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers=headers,
    )


# ═════════════════════════════════════════════════════════════════════════════
# CHẾ ĐỘ 1: Cào toàn bộ đường — 1 lần
# ═════════════════════════════════════════════════════════════════════════════

# Trạng thái lần cào 1-lần (in-memory, reset khi restart)
_crawl_once_status: dict = {
    "running"         : False,
    "last_started_at" : None,
    "last_result"     : None,
}
_crawl_once_lock = threading.Lock()


def _run_crawl_once_background(db: Session):
    """Background thread cho chế độ cào 1 lần."""
    try:
        from services.traffic_crawl import crawl_all_once
        result = crawl_all_once(db)
    except Exception as e:
        result = {"error": str(e)}
    finally:
        db.close()
        with _crawl_once_lock:
            _crawl_once_status["running"]     = False
            _crawl_once_status["last_result"] = result


@router.post(
    "/traffic/crawl",
    summary="[Chế độ 1] Cào toàn bộ đường — 1 lần (chạy nền)",
    description="""
Cào dữ liệu TomTom cho **tất cả tuyến đường** đúng **1 lần**.

- Chạy **bất đồng bộ** (nền) — trả về response ngay, không cần chờ.
- Gọi `GET /api/traffic/crawl/status` để xem kết quả sau khi hoàn tất.
- Nếu đang có lần cào chạy dở → **409 Conflict**.

⏱ Thời gian ước tính: ~1–3 phút tùy số đường và quota.
""",
    status_code=202,
)
def trigger_crawl_once(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db),user: User = Depends(require_csgt)
):
    with _crawl_once_lock:
        if _crawl_once_status["running"]:
            raise HTTPException(
                status_code=409,
                detail="Đang có lần cào đang chạy. Vui lòng đợi hoàn tất.",
            )
        _crawl_once_status["running"]         = True
        _crawl_once_status["last_started_at"] = datetime.now(
            timezone(timedelta(hours=7))
        ).strftime("%H:%M:%S %d/%m/%Y +07")

    background_tasks.add_task(_run_crawl_once_background, db)

    return {
        "message"   : "✅ [Chế độ 1] Đã khởi động cào toàn bộ đường — 1 lần",
        "started_at": _crawl_once_status["last_started_at"],
        "status_url": "/api/traffic/crawl/status",
    }


@router.get(
    "/traffic/crawl/status",
    summary="[Chế độ 1] Trạng thái lần cào toàn bộ gần nhất",
)
def get_crawl_once_status():
    with _crawl_once_lock:
        return {
            "mode"            : "crawl_all_once",
            "running"         : _crawl_once_status["running"],
            "last_started_at" : _crawl_once_status["last_started_at"],
            "last_result"     : _crawl_once_status["last_result"],
        }


# ═════════════════════════════════════════════════════════════════════════════
# CHẾ ĐỘ 2: Cào toàn bộ đường — vòng lặp liên tục
# ═════════════════════════════════════════════════════════════════════════════

_loop_stop_event: Optional[threading.Event] = None
_loop_thread: Optional[threading.Thread] = None
_loop_lock = threading.Lock()
_loop_status: dict = {
    "running"         : False,
    "started_at"      : None,
    "interval_seconds": None,
    "cycle_count"     : 0,
    "last_cycle_result": None,
}


def _on_loop_cycle_done(result: dict):
    """Callback cập nhật _loop_status sau mỗi chu kỳ."""
    with _loop_lock:
        _loop_status["cycle_count"]      = _loop_status.get("cycle_count", 0) + 1
        _loop_status["last_cycle_result"] = result


def _run_loop_thread(interval_seconds: int):
    """Hàm chạy trong background thread cho chế độ vòng lặp."""
    from database import SessionLocal
    from services.traffic_crawl import crawl_all_loop

    def db_factory():
        return SessionLocal()

    crawl_all_loop(
        db_factory        = db_factory,
        interval_seconds  = interval_seconds,
        stop_event        = _loop_stop_event,
        on_cycle_done     = _on_loop_cycle_done,
    )
    with _loop_lock:
        _loop_status["running"] = False


@router.post(
    "/traffic/crawl/loop/start",
    summary="[Chế độ 2] Bắt đầu cào toàn bộ đường — lặp liên tục",
    description="""
Bắt đầu vòng lặp cào tất cả đường, lặp lại sau mỗi `interval_seconds` giây.

- Chạy **nền** liên tục đến khi gọi `POST /api/traffic/crawl/loop/stop`.
- Nếu vòng lặp đang chạy → **409 Conflict**.

**Tham số:**
- `interval_seconds` — khoảng cách giữa 2 chu kỳ (mặc định 600 = 10 phút).
""",
    status_code=202,
)
def start_crawl_loop(
    interval_seconds: int = Query(600, ge=60, description="Khoảng cách giữa 2 chu kỳ (giây, tối thiểu 60s)"),
    current_user: User = Depends(require_admin), 
):
    global _loop_stop_event, _loop_thread

    with _loop_lock:
        if _loop_status["running"]:
            raise HTTPException(
                status_code=409,
                detail="Vòng lặp cào đang chạy. Gọi /loop/stop để dừng trước.",
            )
        _loop_stop_event = threading.Event()
        _loop_status["running"]          = True
        _loop_status["started_at"]       = datetime.now(
            timezone(timedelta(hours=7))
        ).strftime("%H:%M:%S %d/%m/%Y +07")
        _loop_status["interval_seconds"] = interval_seconds
        _loop_status["cycle_count"]      = 0
        _loop_status["last_cycle_result"] = None

    _loop_thread = threading.Thread(
        target=_run_loop_thread,
        args=(interval_seconds,),
        daemon=True,
        name="crawl-loop",
    )
    _loop_thread.start()

    return {
        "message"          : "✅ [Chế độ 2] Đã khởi động cào vòng lặp liên tục",
        "interval_seconds" : interval_seconds,
        "started_at"       : _loop_status["started_at"],
        "stop_url"         : "/api/traffic/crawl/loop/stop",
        "status_url"       : "/api/traffic/crawl/loop/status",
    }


@router.post(
    "/traffic/crawl/loop/stop",
    summary="[Chế độ 2] Dừng vòng lặp cào liên tục",
)
def stop_crawl_loop(
    current_user: User = Depends(require_admin),
):
    with _loop_lock:
        if not _loop_status["running"]:
            raise HTTPException(
                status_code=409,
                detail="Vòng lặp cào không đang chạy.",
            )
        if _loop_stop_event:
            _loop_stop_event.set()

    return {
        "message"    : "🛑 [Chế độ 2] Đã gửi tín hiệu dừng vòng lặp cào",
        "note"       : "Chu kỳ hiện tại sẽ hoàn thành trước khi dừng hẳn.",
        "status_url" : "/api/traffic/crawl/loop/status",
    }


@router.get(
    "/traffic/crawl/loop/status",
    summary="[Chế độ 2] Trạng thái vòng lặp cào",
)
def get_crawl_loop_status():
    with _loop_lock:
        return {
            "mode"             : "crawl_all_loop",
            "running"          : _loop_status["running"],
            "started_at"       : _loop_status["started_at"],
            "interval_seconds" : _loop_status["interval_seconds"],
            "cycle_count"      : _loop_status["cycle_count"],
            "last_cycle_result": _loop_status["last_cycle_result"],
        }


# ═════════════════════════════════════════════════════════════════════════════
# CHẾ ĐỘ 3: Cào 1 đường duy nhất — 1 lần
# ═════════════════════════════════════════════════════════════════════════════

@router.post(
    "/traffic/crawl/{street_id}",
    summary="[Chế độ 3] Cào 1 đường duy nhất — 1 lần",
    description="""
Cào dữ liệu TomTom cho **đúng 1 tuyến đường** theo `street_id`, đúng **1 lần**.

- Chạy **đồng bộ** — trả về kết quả ngay sau khi cào xong.
- Thích hợp để kiểm tra 1 đường cụ thể hoặc debug.
""",
)
def trigger_crawl_one(
    street_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    from services.traffic_crawl import crawl_one_street
    result = crawl_one_street(db, street_id)

    if not result["success"] and result.get("error"):
        # Trả về 200 nhưng có field error để frontend xử lý được
        pass

    return result


# ═════════════════════════════════════════════════════════════════════════════
# ĐỒNG BỘ MAX_SPEED TỪ FREEFLOW HERE API (chạy 1 lần, nền)
# ═════════════════════════════════════════════════════════════════════════════

_sync_speed_status: dict = {
    "running"    : False,
    "started_at" : None,
    "last_result": None,
}
_sync_speed_lock = threading.Lock()


def _run_sync_max_speed_background(db: Session):
    """Background task: gọi sync_max_speed_from_here() rồi cập nhật trạng thái."""
    try:
        from services.here_ingestion_helper import sync_max_speed_from_here
        result = sync_max_speed_from_here(db)
        # Sau khi cập nhật max_speed → xóa cache geometry để frontend thấy giá trị mới
        redis_client.delete("streets:geometry")
    except Exception as e:
        result = {"error": str(e)}
    finally:
        db.close()
        with _sync_speed_lock:
            _sync_speed_status["running"]     = False
            _sync_speed_status["last_result"] = result


@router.post(
    "/traffic/sync-max-speed",
    summary="Đồng bộ tốc độ tối đa từ freeflow HERE API",
    description="""
Gọi HERE Flow API và **cập nhật `max_speed`** của tất cả tuyến đường theo giá trị freeflow thực tế.

**Cơ chế:**
- Gọi HERE `/v7/flow` cho **7 quận Đà Nẵng** (7 request)
- Match từng đường trong DB với segment HERE gần nhất (ngưỡng ≤ 500m)
- Chuẩn hóa freeflow → mức giới hạn ATGT VN gần nhất (20/30/40/50/60/70/80/100/120 km/h)
- Ghi đè `max_speed` **không điều kiện** — kể cả khi chênh lệch nhỏ

**Chạy nền** — trả về ngay, gọi `GET /api/traffic/sync-max-speed/status` để xem kết quả.

⏱ Thời gian ước tính: ~15–30 giây (7 request × 0.5s delay + xử lý KDTree).
""",
    status_code=202,
)
def trigger_sync_max_speed(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    with _sync_speed_lock:
        if _sync_speed_status["running"]:
            raise HTTPException(
                status_code=409,
                detail="Đang có lần đồng bộ max_speed đang chạy. Vui lòng đợi hoàn tất.",
            )
        _sync_speed_status["running"]    = True
        _sync_speed_status["started_at"] = datetime.now(
            timezone(timedelta(hours=7))
        ).strftime("%H:%M:%S %d/%m/%Y +07")
        _sync_speed_status["last_result"] = None

    background_tasks.add_task(_run_sync_max_speed_background, db)

    return {
        "message"   : "✅ Đã khởi động đồng bộ max_speed từ HERE freeflow",
        "started_at": _sync_speed_status["started_at"],
        "status_url": "/api/traffic/sync-max-speed/status",
        "note"      : "Sau khi hoàn tất, gọi GET /api/traffic/sync-max-speed/status để xem chi tiết.",
    }


@router.get(
    "/traffic/sync-max-speed/status",
    summary="Trạng thái lần đồng bộ max_speed gần nhất",
)
def get_sync_max_speed_status():
    with _sync_speed_lock:
        return {
            "running"    : _sync_speed_status["running"],
            "started_at" : _sync_speed_status["started_at"],
            "last_result": _sync_speed_status["last_result"],
        }


# ═════════════════════════════════════════════════════════════════════════════
# APSCHEDULER — Quản lý lịch cào tự động
# ═════════════════════════════════════════════════════════════════════════════

@router.get(
    "/traffic/schedule/jobs",
    summary="Danh sách tất cả scheduled job",
    description="""
Trả về danh sách tất cả job cào đang được lên lịch trong APScheduler.

Mỗi job bao gồm: `id`, `name`, `trigger` (cron expression), `next_run_at`.
""",
)
def get_schedule_jobs(
    current_user: User = Depends(require_admin),
):
    from services.scheduler import list_jobs, scheduler_state
    return {
        "scheduler": scheduler_state(),
        "jobs"     : list_jobs(),
    }


@router.get(
    "/traffic/schedule/state",
    summary="Trạng thái tổng quan của APScheduler",
)
def get_scheduler_state(
    current_user: User = Depends(require_admin),
):
    from services.scheduler import scheduler_state, list_jobs
    state = scheduler_state()
    state["jobs"] = list_jobs()
    return state


@router.post(
    "/traffic/schedule/pause",
    summary="Tạm dừng toàn bộ APScheduler",
    description="Tạm dừng tất cả job — không mất cấu hình, gọi `/resume` để tiếp tục.",
)
def pause_schedule(
    current_user: User = Depends(require_admin),
):
    from services.scheduler import pause_scheduler, scheduler_state
    pause_scheduler()
    return {
        "message"  : "⏸ Scheduler đã tạm dừng",
        "scheduler": scheduler_state(),
    }


@router.post(
    "/traffic/schedule/resume",
    summary="Tiếp tục APScheduler sau khi tạm dừng",
)
def resume_schedule(
    current_user: User = Depends(require_admin),
):
    from services.scheduler import resume_scheduler, scheduler_state
    resume_scheduler()
    return {
        "message"  : "▶️ Scheduler đã tiếp tục",
        "scheduler": scheduler_state(),
    }


@router.post(
    "/traffic/schedule/run-now/{job_id}",
    summary="Chạy ngay 1 job theo ID (không ảnh hưởng lịch định kỳ)",
    description="""
Kích hoạt 1 job chạy ngay lập tức mà không phá vỡ lịch định kỳ của nó.

**Job ID mặc định:**
- `crawl_traffic_5m`     — 🔄 Cào định kỳ 5 phút
- `auto_retrain`         — 🤖 Huấn luyện lại model
""",
)
def run_job_now(
    job_id: str,
    current_user: User = Depends(require_admin),
):
    from services.scheduler import run_job_now as _run_now
    found = _run_now(job_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy job với id='{job_id}'",
        )
    return {
        "message": f"▶️ Đã kích hoạt chạy ngay job '{job_id}'",
        "job_id" : job_id,
    }


@router.post(
    "/traffic/schedule/add",
    summary="Thêm job cào interval tuỳ chỉnh",
    description="""
Thêm 1 job cào tất cả đường với interval tuỳ chỉnh.

**Tham số:**
- `job_id`     — ID duy nhất cho job (tên tự đặt, ví dụ: `my_custom_job`)
- `minutes`    — Cào mỗi bao nhiêu phút (tối thiểu 5)
- `hour_start` — Giờ bắt đầu (0–23, múi giờ Đà Nẵng)
- `hour_end`   — Giờ kết thúc (0–23, múi giờ Đà Nẵng)
""",
)
def add_schedule_job(
    job_id    : str = Query(..., description="ID duy nhất cho job"),
    minutes   : int = Query(..., ge=5,  description="Cào mỗi N phút (tối thiểu 5)"),
    hour_start: int = Query(0,  ge=0, le=23, description="Giờ bắt đầu (0–23)"),
    hour_end  : int = Query(23, ge=0, le=23, description="Giờ kết thúc (0–23)"),
    current_user: User = Depends(require_admin),
):
    if hour_start >= hour_end:
        raise HTTPException(
            status_code=422,
            detail="hour_start phải nhỏ hơn hour_end",
        )
    from services.scheduler import add_interval_job
    job_info = add_interval_job(job_id, minutes, hour_start, hour_end)
    return {
        "message" : f"➕ Đã thêm job '{job_id}'",
        "job"     : job_info,
    }


@router.delete(
    "/traffic/schedule/{job_id}",
    summary="Xóa 1 scheduled job",
)
def remove_schedule_job(
    job_id: str,
    current_user: User = Depends(require_admin),
):
    from services.scheduler import remove_job
    found = remove_job(job_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy job với id='{job_id}'",
        )
    return {"message": f"🗑 Đã xóa job '{job_id}'"}


# ════════════════════════════════════════════════════════════════════════════════
# THỜI TIẾT API
# GET /api/weather/current  — Thời tiết hiện tại (gọi thẳng OpenWeather)
# GET /api/weather/history  — Lịch sử snapshot từ DB, timestamp hiển thị UTC+7
# ════════════════════════════════════════════════════════════════════════════════

@router.get(
    "/weather/current",
    summary="Thời tiết Đà Nẵng hiện tại",
    description="Gọi trực tiếp OpenWeatherMap API — luôn lấy dữ liệu mới nhất, không qua cache.",
    tags=["Weather"],
)
def get_weather_current():
    """
    Trả về thời tiết Đà Nẵng ngay lúc này (gọi thẳng API, không qua DB).
    Timestamp hiển thị theo giờ Việt Nam (UTC+7).
    """
    from ml.feature_engineering import fetch_weather_danang
    weather = fetch_weather_danang()
    now_vn = datetime.now(TZ_DANANG)
    return {
        "timestamp"     : now_vn.strftime("%Y-%m-%d %H:%M:%S +07:00"),
        "source"        : "openweathermap",
        "temperature"   : weather.get("temperature"),
        "humidity"      : weather.get("humidity"),
        "wind_speed"    : weather.get("wind_speed"),
        "rain_1h_mm"    : weather.get("rain_1h_mm", 0.0),
        "visibility_km" : weather.get("visibility_km"),
        "is_raining"    : bool(weather.get("is_raining", 0)),
        "weather_id"    : weather.get("weather_id"),
        "weather_group" : weather.get("weather_group", 0),
        "description"   : _weather_group_label(weather.get("weather_group", 0)),
    }


@router.get(
    "/weather/history",
    summary="Lịch sử thời tiết từ DB",
    description="Trả về N snapshot thời tiết gần nhất đã lưu trong DB. Timestamp đều theo giờ Việt Nam (+07:00).",
    tags=["Weather"],
)
def get_weather_history(
    limit: int = 24,
    db: Session = Depends(get_db),
):
    """
    Trả về tối đa `limit` bản ghi WeatherSnapshot gần nhất.
    Timestamp được convert sang UTC+7 để khớp với traffic_data.
    """
    from models.weather_snapshot import WeatherSnapshot
    rows = (
        db.query(WeatherSnapshot)
        .order_by(WeatherSnapshot.timestamp.desc())
        .limit(min(limit, 200))  # tối đa 200
        .all()
    )

    result = []
    for r in rows:
        # Convert timestamp sang +07 để hiển thị nhất quán với traffic_data
        ts_vn = r.timestamp.astimezone(TZ_DANANG).strftime("%Y-%m-%d %H:%M:%S +07:00") \
                if r.timestamp else None
        result.append({
            "id"            : r.id,
            "timestamp"     : ts_vn,              # ← UTC+7, khớp với traffic
            "source"        : r.source,
            "temperature"   : r.temperature,
            "humidity"      : r.humidity,
            "wind_speed"    : r.wind_speed,
            "rain_1h_mm"    : r.rain_1h_mm,
            "visibility_km" : r.visibility_km,
            "is_raining"    : bool(r.is_raining),
            "weather_id"    : r.weather_id,
            "weather_group" : r.weather_group,
            "description"   : _weather_group_label(r.weather_group),
        })

    return {
        "count"    : len(result),
        "snapshots": result,
    }


def _weather_group_label(group: int) -> str:
    """Chuyển mã nhóm thời tiết thành mô tả tiếng Việt."""
    return {
        0: "☀️ Trời quang",
        1: "⛅ Có mây",
        2: "🌧️ Mưa nhẹ",
        3: "⚡ Mưa nặng",
        4: "🌫️ Sương mù/khác",
    }.get(group or 0, "Không xác định")


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/traffic/history — Lấy lịch sử traffic của tất cả đường tại mốc giờ trước
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/traffic/history",
    summary="Lấy lịch sử giao thông theo số giờ trước",
    description="Lấy dữ liệu kẹt xe tại mốc thời gian X giờ trước (tối đa 6 giờ).",
)
def get_traffic_history(
    hours_ago: int = Query(..., ge=1, le=6),
    db: Session = Depends(get_db),
):
    # Lấy timezone Đà Nẵng
    now_vn = datetime.now(TZ_DANANG)
    target_time = now_vn - timedelta(hours=hours_ago)
    
    # Tạo cửa sổ tìm kiếm dữ liệu xung quanh mốc target_time
    start_win = target_time - timedelta(minutes=15)
    end_win = target_time + timedelta(minutes=15)
    
    # Query các bản ghi traffic gần nhất cho từng street_id, segment_idx trong cửa sổ
    # Dùng CONGESTION_COLORS từ file constants/colors.py hoặc định nghĩa trực tiếp nếu chưa có.
    # Trong latest_traffic / state:
    # CONGESTION_COLORS = {0: [34, 197, 94, 220], 1: [234, 179, 8, 220], 2: [239, 68, 68, 220], None: [100, 116, 139, 150]}
    congestion_colors = {
        0: [34, 197, 94, 220],
        1: [234, 179, 8, 220],
        2: [239, 68, 68, 220],
        None: [100, 116, 139, 150]
    }
    
    rows = db.execute(text("""
        SELECT DISTINCT ON (td.street_id, td.segment_idx)
            td.street_id,
            td.segment_idx,
            td.avg_speed,
            td.congestion_level,
            td.timestamp
        FROM traffic_data td
        WHERE td.timestamp BETWEEN :start_win AND :end_win
        ORDER BY td.street_id, td.segment_idx, td.timestamp DESC
    """), {"start_win": start_win, "end_win": end_win}).fetchall()
    
    # Nếu không tìm thấy, mở rộng cửa sổ lên 45 phút
    if not rows:
        start_win = target_time - timedelta(minutes=45)
        end_win = target_time + timedelta(minutes=45)
        rows = db.execute(text("""
            SELECT DISTINCT ON (td.street_id, td.segment_idx)
                td.street_id,
                td.segment_idx,
                td.avg_speed,
                td.congestion_level,
                td.timestamp
            FROM traffic_data td
            WHERE td.timestamp BETWEEN :start_win AND :end_win
            ORDER BY td.street_id, td.segment_idx, td.timestamp DESC
        """), {"start_win": start_win, "end_win": end_win}).fetchall()

    # Phân nhóm theo street_id
    from collections import defaultdict
    street_segs = defaultdict(list)
    for row in rows:
        street_segs[row.street_id].append(row)
        
    streets_out = []
    for street_id, segs in sorted(street_segs.items()):
        levels = [s.congestion_level for s in segs if s.congestion_level is not None]
        speeds = [s.avg_speed        for s in segs if s.avg_speed        is not None]
        avg_cong = round(sum(levels) / len(levels)) if levels else None
        avg_spd  = round(sum(speeds)  / len(speeds), 1) if speeds else None
        
        segments_out = [
            {
                "segment_idx": s.segment_idx,
                "congestion_level": s.congestion_level,
                "avg_speed": s.avg_speed,
                "color": congestion_colors.get(s.congestion_level, congestion_colors[None]),
            }
            for s in segs
        ]
        
        streets_out.append({
            "street_id": street_id,
            "congestion_level": avg_cong,
            "congestion_label": CONGESTION_LABEL.get(avg_cong),
            "avg_speed": avg_spd,
            "color": congestion_colors.get(avg_cong, congestion_colors[None]),
            "timestamp": segs[0].timestamp.isoformat() if segs[0].timestamp else None,
            "segments": segments_out,
        })
        
    return {
        "hours_ago": hours_ago,
        "target_time": target_time.isoformat(),
        "total": len(streets_out),
        "streets": streets_out,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/traffic/crawl/logs — Lấy nhật ký cào dữ liệu (logs) mới nhất
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/traffic/crawl/logs",
    summary="Lấy nhật ký cào dữ liệu (logs) mới nhất",
    description="Đọc 150 dòng cuối cùng từ file logs/crawler.log.",
)
def get_crawler_logs(
    limit: int = Query(150, ge=10, le=500),
    current_user: User = Depends(require_admin),
):
    import os
    log_path = "logs/crawler.log"
    if not os.path.exists(log_path):
        return {"logs": [], "message": "Chưa có file log crawler.log"}
        
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        # Lấy limit dòng cuối cùng
        last_lines = lines[-limit:]
        return {
            "logs": [line.rstrip() for line in last_lines],
            "total_lines": len(lines),
            "returned_lines": len(last_lines)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi đọc file log: {str(e)}"
        )


@router.get(
    "/traffic/crawl/stats",
    summary="Phân tích logs cào dữ liệu để xuất thống kê đồ thị",
    description="Đọc toàn bộ logs/crawler.log để thống kê KPIs, tỷ lệ thành công, số lượng cào và số lượng bị lỡ.",
)
def get_crawl_stats(
    current_user: User = Depends(require_admin),
):
    import os
    import re
    from datetime import datetime, timedelta

    log_path = "logs/crawler.log"
    if not os.path.exists(log_path):
        return {
            "success": False,
            "message": "Chưa có file log crawler.log",
            "kpis": {
                "total_runs": 0,
                "success_runs": 0,
                "failed_runs": 0,
                "missed_runs": 0,
                "success_rate": 100.0,
                "avg_duration": 0.0,
            },
            "last_runs": [],
            "daily_stats": [],
        }

    success_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \+07 \[INFO\] ✅ Hoàn tất HERE Bbox Crawl: (\d+)/(\d+) segments map được — ([\d.]+)s"
    )
    error_pattern = re.compile(
        r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \+07 \[(?:ERROR|WARNING)\] (?:Lỗi cào dữ liệu HERE API: |Lỗi cào |Thất bại |⛔ \[TOMTOM\] HẾT QUOTA |⛔ \[GOONG\] HẾT QUOTA )(.*)"
    )

    runs = []

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                m_success = success_pattern.match(line)
                if m_success:
                    dt_str, succ_str, tot_str, dur_str = m_success.groups()
                    runs.append({
                        "dt": datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S"),
                        "status": "success",
                        "success_count": int(succ_str),
                        "total_count": int(tot_str),
                        "duration": float(dur_str),
                    })
                    continue

                m_error = error_pattern.match(line)
                if m_error:
                    dt_str, err_msg = m_error.groups()
                    runs.append({
                        "dt": datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S"),
                        "status": "failed",
                        "success_count": 0,
                        "total_count": 0,
                        "duration": 0.0,
                    })
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi đọc file log: {str(e)}"
        )

    if not runs:
        return {
            "success": True,
            "kpis": {
                "total_runs": 0,
                "success_runs": 0,
                "failed_runs": 0,
                "missed_runs": 0,
                "success_rate": 100.0,
                "avg_duration": 0.0,
            },
            "last_runs": [],
            "daily_stats": [],
        }

    # Sort runs chronologically
    runs.sort(key=lambda x: x["dt"])

    # Calculate missed runs and build detailed run list
    detailed_runs = []
    total_missed = 0

    # Track daily counts
    daily_data = {}  # date_str -> {success, failed, missed}

    for i, run in enumerate(runs):
        missed = 0
        if i > 0:
            prev_run = runs[i-1]
            diff = (run["dt"] - prev_run["dt"]).total_seconds()
            if diff > 330:
                missed = int(diff / 300) - 1
                total_missed += max(0, missed)

        day_str = run["dt"].strftime("%Y-%m-%d")
        if day_str not in daily_data:
            daily_data[day_str] = {"success": 0, "failed": 0, "missed": 0}

        if run["status"] == "success":
            daily_data[day_str]["success"] += 1
        else:
            daily_data[day_str]["failed"] += 1
        daily_data[day_str]["missed"] += max(0, missed)

        detailed_runs.append({
            "timestamp": run["dt"].strftime("%H:%M %d/%m"),
            "date": day_str,
            "status": run["status"],
            "success_count": run["success_count"],
            "total_count": run["total_count"],
            "duration": run["duration"],
            "missed_before": max(0, missed),
        })

    success_runs = sum(1 for r in runs if r["status"] == "success")
    failed_runs = sum(1 for r in runs if r["status"] == "failed")
    total_attempts = success_runs + failed_runs
    success_rate = (success_runs / total_attempts * 100) if total_attempts > 0 else 100.0

    durations = [r["duration"] for r in runs if r["status"] == "success" and r["duration"] > 0]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    # Format daily stats for charts
    daily_stats = []
    for day in sorted(daily_data.keys()):
        daily_stats.append({
            "date": datetime.strptime(day, "%Y-%m-%d").strftime("%d/%m"),
            "success": daily_data[day]["success"],
            "failed": daily_data[day]["failed"],
            "missed": daily_data[day]["missed"],
        })

    return {
        "success": True,
        "kpis": {
            "total_runs": total_attempts,
            "success_runs": success_runs,
            "failed_runs": failed_runs,
            "missed_runs": total_missed,
            "success_rate": round(success_rate, 1),
            "avg_duration": round(avg_duration, 2),
        },
        "last_runs": detailed_runs[-50:],  # last 50 runs for charts
        "daily_stats": daily_stats[-7:],   # last 7 days for bar charts
    }
