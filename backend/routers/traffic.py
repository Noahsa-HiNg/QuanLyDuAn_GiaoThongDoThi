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
"""

from typing import Optional
from datetime import datetime, timezone, timedelta
import json
import threading

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Street, TrafficData
from schemas.traffic import TrafficCurrentOut, TrafficSummaryOut, TZ_DANANG
from utils.geometry import split_path_into_zones
from services import cache as cache_svc   # Redis cache layer

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
