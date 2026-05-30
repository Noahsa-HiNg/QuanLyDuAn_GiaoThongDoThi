"""
services/tomtom_incidents.py — Cào sự cố giao thông từ TomTom Traffic Incidents API v5

Hỗ trợ các loại sự cố:
    Cat 1  → ACCIDENT    → Incident.type = 'accident'
    Cat 6  → LANE_CLOSED → Incident.type = 'roadblock'
    Cat 7  → ROAD_WORKS  → Incident.type = 'roadblock'  ← đường đang sửa chữa
    Cat 8  → WIND/CLOSED → Incident.type = 'roadblock'
    Cat 9  → FLOODING    → Incident.type = 'roadblock'

Cơ chế dedup:
    Lưu TomTom incident ID vào cột here_incident_id với prefix "TT_"
    → Không bao giờ insert trùng cùng 1 sự cố

API docs: https://developer.tomtom.com/traffic-api/documentation/traffic-incidents/incident-details
"""

import os
import time
import requests
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text as _text

try:
    from scipy.spatial import cKDTree
except ImportError:
    pass

TZ_DANANG = timezone(timedelta(hours=7))

# ── Toàn bộ Đà Nẵng (1 request duy nhất thay vì 7 quận) ──────────────────────
DANANG_BBOX = "108.05,15.80,108.35,16.20"   # minLon,minLat,maxLon,maxLat

# ── TomTom category → (Incident.type, severity, label) ───────────────────────
_TOMTOM_CAT_MAP = {
    1:  ("accident",   2, "Tai nạn giao thông"),
    6:  ("roadblock",  1, "Làn đường bị đóng"),
    7:  ("roadblock",  2, "Thi công / Sửa chữa đường"),
    8:  ("roadblock",  1, "Đường bị đóng do thời tiết"),
    9:  ("roadblock",  3, "Ngập lụt"),
    10: ("roadblock",  1, "Đường vòng / Phân lưu"),
    14: ("accident",   1, "Xe hỏng / Cản trở"),
}

_DEFAULT_CAT = ("roadblock", 1, "Sự cố giao thông")

# ── magnitudeOfDelay → severity bổ sung ──────────────────────────────────────
_DELAY_SEVERITY = {0: 1, 1: 1, 2: 2, 3: 3, 4: 1}


def _get_tomtom_key() -> str | None:
    """Lấy TomTom API key từ env (ưu tiên TOMTOM_API_KEYS, fallback TOMTOM_API_KEY)."""
    multi = os.getenv("TOMTOM_API_KEYS", "")
    if multi:
        keys = [k.strip() for k in multi.split(",") if k.strip()]
        if keys:
            return keys[0]   # Dùng key đầu tiên cho incident API (riêng với flow API)
    return os.getenv("TOMTOM_API_KEY", "")


def _extract_coords(geometry: dict) -> tuple[float | None, float | None]:
    """
    Lấy tọa độ (lat, lon) từ GeoJSON geometry của TomTom.
    Hỗ trợ: Point, LineString, MultiLineString.
    """
    if not geometry:
        return None, None

    gtype = geometry.get("type", "")
    coords = geometry.get("coordinates", [])

    if gtype == "Point":
        # [lon, lat]
        if len(coords) >= 2:
            return float(coords[1]), float(coords[0])

    elif gtype == "LineString":
        # [[lon, lat], ...]  → lấy điểm giữa
        if coords:
            mid = coords[len(coords) // 2]
            if len(mid) >= 2:
                return float(mid[1]), float(mid[0])

    elif gtype == "MultiLineString":
        # [[[lon, lat], ...], ...] → flatten, lấy giữa
        flat = [pt for line in coords for pt in line]
        if flat:
            mid = flat[len(flat) // 2]
            if len(mid) >= 2:
                return float(mid[1]), float(mid[0])

    return None, None


def _fetch_tomtom_incidents_raw(api_key: str, bbox: str) -> list[dict]:
    """
    Gọi TomTom Traffic Incidents v5 và parse kết quả thô.
    Trả về list các incident dict với tọa độ đã extract.
    """
    url = "https://api.tomtom.com/traffic/services/5/incidentDetails"
    params = {
        "key"               : api_key,
        "bbox"              : bbox,
        "timeValidityFilter": "present",
        "fields"            : "{incidents{type,geometry{type,coordinates},"
                              "properties{iconCategory,magnitudeOfDelay,"
                              "from,to,events{description,code,iconCategory}}}}",
    }

    try:
        resp = requests.get(url, params=params, timeout=20)
        if resp.status_code == 403:
            print("[TomTom Incidents] 403 Forbidden — API key không hợp lệ hoặc hết quota")
            return []
        if resp.status_code == 429:
            print("[TomTom Incidents] 429 Too Many Requests — rate limit, thử lại sau")
            return []
        if resp.status_code != 200:
            print(f"[TomTom Incidents] HTTP {resp.status_code}: {resp.text[:300]}")
            return []

        data = resp.json()
        raw_incidents = data.get("incidents", [])
        result = []

        for item in raw_incidents:
            props    = item.get("properties", {})
            geometry = item.get("geometry", {})

            # ── ID duy nhất của TomTom incident ─────────────────────────────
            # TomTom không trả về stable ID trong v5 → dùng from+to+cat làm key
            from_loc = props.get("from", "") or ""
            to_loc   = props.get("to",   "") or ""
            cat      = int(props.get("iconCategory", 0))
            tomtom_id = f"TT_{cat}_{from_loc[:30]}_{to_loc[:30]}".replace(" ", "_")

            # ── Tọa độ ──────────────────────────────────────────────────────
            lat, lon = _extract_coords(geometry)
            if lat is None or lon is None:
                continue

            # ── Loại sự cố và severity ──────────────────────────────────────
            inc_type, base_severity, base_desc = _TOMTOM_CAT_MAP.get(cat, _DEFAULT_CAT)
            delay_sev = _DELAY_SEVERITY.get(int(props.get("magnitudeOfDelay", 0) or 0), 1)
            severity  = max(base_severity, delay_sev)

            # ── Mô tả ────────────────────────────────────────────────────────
            events  = props.get("events", []) or []
            ev_desc = events[0].get("description", "") if events else ""
            description = f"{base_desc}"
            if from_loc and to_loc:
                description += f": {from_loc} → {to_loc}"
            if ev_desc and ev_desc.lower() not in description.lower():
                description += f" ({ev_desc})"

            result.append({
                "tomtom_id"  : tomtom_id,
                "lat"        : lat,
                "lon"        : lon,
                "type"       : inc_type,
                "severity"   : severity,
                "description": description,
                "from_loc"   : from_loc,
                "to_loc"     : to_loc,
                "category"   : cat,
            })

        return result

    except Exception as e:
        print(f"[TomTom Incidents] Lỗi gọi API: {e}")
        return []


def fetch_tomtom_incidents(db: Session) -> dict:
    """
    Cào tất cả sự cố giao thông từ TomTom Traffic Incidents API cho Đà Nẵng.
    Bao gồm: tai nạn (cat=1), làn đóng (cat=6), thi công (cat=7),
              đóng đường (cat=8), ngập lụt (cat=9).

    Quy trình:
      1. Gọi TomTom Incidents v5 cho toàn bộ Đà Nẵng (1 request)
      2. Xây KDTree từ tọa độ incident
      3. Match với đường DB bằng KDTree (ngưỡng ≤ 500m)
      4. Dedup bằng here_incident_id (prefix "TT_")
      5. INSERT vào bảng incidents (source='here_api', created_by=NULL)

    Returns:
        dict: fetched, saved, skipped_dup, skipped_no_match, by_category, errors
    """
    from models.incident import Incident

    started_at = datetime.now(TZ_DANANG)
    api_key    = _get_tomtom_key()

    if not api_key:
        return {"error": "Không có TomTom API key. Kiểm tra TOMTOM_API_KEYS trong .env"}

    # ── 1. Gọi TomTom API ────────────────────────────────────────────────────
    print("[TomTom Incidents] Đang gọi API...")
    raw = _fetch_tomtom_incidents_raw(api_key, DANANG_BBOX)
    fetched = len(raw)

    cat_counter = {}
    for inc in raw:
        cat_name = _TOMTOM_CAT_MAP.get(inc["category"], _DEFAULT_CAT)[2]
        cat_counter[cat_name] = cat_counter.get(cat_name, 0) + 1

    print(f"[TomTom Incidents] Fetched: {fetched} incidents")
    for cat, count in cat_counter.items():
        print(f"  [{cat}] → {count}")

    if fetched == 0:
        return {
            "fetched"         : 0,
            "saved"           : 0,
            "skipped_dup"     : 0,
            "skipped_no_match": 0,
            "by_category"     : {},
            "errors"          : ["TomTom không trả về sự cố nào"],
            "duration_seconds": round((datetime.now(TZ_DANANG) - started_at).total_seconds(), 2),
            "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
        }

    # ── 2. Lấy centroid đường từ DB ──────────────────────────────────────────
    osm_rows = db.execute(_text("""
        SELECT id,
               ST_Y(ST_Centroid(geometry)) AS lat,
               ST_X(ST_Centroid(geometry)) AS lon
        FROM streets
        WHERE geometry IS NOT NULL
    """)).fetchall()

    if not osm_rows:
        return {
            "fetched": fetched, "saved": 0, "skipped_dup": 0,
            "skipped_no_match": fetched, "by_category": cat_counter,
            "errors": ["Không có geometry trong DB để match đường"],
            "duration_seconds": round((datetime.now(TZ_DANANG) - started_at).total_seconds(), 2),
            "timestamp": started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
        }

    # ── 3. KDTree — match incident → đường gần nhất ──────────────────────────
    osm_pts    = [[r.lat, r.lon] for r in osm_rows]
    street_tree = cKDTree(osm_pts)

    inc_pts = [[inc["lat"], inc["lon"]] for inc in raw]
    s_dists, s_idxs = street_tree.query(inc_pts, k=1)

    # ── 4. Lấy TomTom IDs đã có trong DB (dedup) ─────────────────────────────
    existing_ids = set(
        row[0] for row in db.execute(_text(
            "SELECT here_incident_id FROM incidents WHERE here_incident_id LIKE 'TT_%'"
        )).fetchall()
    )

    # ── 5. INSERT sự cố mới ──────────────────────────────────────────────────
    saved             = 0
    skipped_dup       = 0
    skipped_no_match  = 0
    errors            = []
    by_category_saved : dict = {}
    now               = datetime.now(TZ_DANANG)

    for i, inc in enumerate(raw):
        tt_id = inc["tomtom_id"]

        if tt_id in existing_ids:
            skipped_dup += 1
            continue

        dist = s_dists[i]
        if dist >= 0.005:   # > ~500m
            skipped_no_match += 1
            continue

        street_id = osm_rows[s_idxs[i]].id

        try:
            db.add(Incident(
                street_id       = street_id,
                type            = inc["type"],
                start_time      = now,
                end_time        = None,
                severity        = inc["severity"],
                description     = inc["description"],
                status          = "active",
                is_active       = True,
                here_incident_id= tt_id,
                source          = "here_api",   # Dùng chung field (TT_ prefix phân biệt)
                created_by      = None,
            ))
            db.flush()
            existing_ids.add(tt_id)
            saved += 1

            cat_name = _TOMTOM_CAT_MAP.get(inc["category"], _DEFAULT_CAT)[2]
            by_category_saved[cat_name] = by_category_saved.get(cat_name, 0) + 1

        except Exception as e:
            db.rollback()
            errors.append(f"{tt_id}: {str(e)[:100]}")

    if saved > 0:
        db.commit()

    duration = round((datetime.now(TZ_DANANG) - started_at).total_seconds(), 2)
    print(
        f"[TomTom Incidents] Hoàn tất: "
        f"fetched={fetched}, saved={saved}, "
        f"dup={skipped_dup}, no_match={skipped_no_match} — {duration}s"
    )

    return {
        "fetched"         : fetched,
        "saved"           : saved,
        "skipped_dup"     : skipped_dup,
        "skipped_no_match": skipped_no_match,
        "by_category"     : by_category_saved,
        "errors"          : errors,
        "duration_seconds": duration,
        "timestamp"       : started_at.strftime("%H:%M:%S %d/%m/%Y +07"),
    }
