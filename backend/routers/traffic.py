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
    background_tasks: BackgroundTasks, db: Session = Depends(get_db)
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
    interval_seconds: int = Query(600, ge=60, description="Khoảng cách giữa 2 chu kỳ (giây, tối thiểu 60s)")
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
def stop_crawl_loop():
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
def get_schedule_jobs():
    from services.scheduler import list_jobs, scheduler_state
    return {
        "scheduler": scheduler_state(),
        "jobs"     : list_jobs(),
    }


@router.get(
    "/traffic/schedule/state",
    summary="Trạng thái tổng quan của APScheduler",
)
def get_scheduler_state():
    from services.scheduler import scheduler_state, list_jobs
    state = scheduler_state()
    state["jobs"] = list_jobs()
    return state


@router.post(
    "/traffic/schedule/pause",
    summary="Tạm dừng toàn bộ APScheduler",
    description="Tạm dừng tất cả job — không mất cấu hình, gọi `/resume` để tiếp tục.",
)
def pause_schedule():
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
def resume_schedule():
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
- `crawl_peak_morning`   — 🌅 Giờ cao điểm sáng
- `crawl_offpeak_day`    — ☀️ Ban ngày bình thường
- `crawl_peak_evening`   — 🌆 Giờ cao điểm chiều
- `crawl_offpeak_evening`— 🌙 Buổi tối
""",
)
def run_job_now(job_id: str):
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
def remove_schedule_job(job_id: str):
    from services.scheduler import remove_job
    found = remove_job(job_id)
    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy job với id='{job_id}'",
        )
    return {"message": f"🗑 Đã xóa job '{job_id}'"}
