"""
services/ingestion.py — Thu thập dữ liệu giao thông từ TomTom & Goong

CHIẾN LƯỢC:
    TomTom (ưu tiên) → nếu thất bại → Goong → nếu thất bại → bỏ qua đường đó

QUOTA MIỄN PHÍ:
    TomTom : 2,500 req/ngày → 49 đường × ~51 lần/ngày = 2,499 req ✓
    Goong  : 1,000 req/ngày → fallback khi TomTom lỗi

LỊCH GỌI API:
    - Mỗi chu kỳ: lần lượt gọi cho từng đường, delay nhỏ giữa mỗi đường
    - Mỗi vòng lặp cách nhau INTERVAL_MINUTES phút
    - Tracker lưu số request đã dùng trong ngày, reset lúc 00:00 Đà Nẵng

TOMTOM API dùng:
    Flow Segment Data — lấy tốc độ thực tế từ 1 điểm tọa độ
    GET https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json
        ?point={lat},{lon}&key={API_KEY}

GOONG API dùng:
    Directions Matrix — lấy duration/distance giữa 2 điểm → tính speed
    GET https://rsapi.goong.io/DistanceMatrix
        ?origins={lat},{lon}&destinations={lat2},{lon2}&vehicle=car&api_key={KEY}
"""

import time
import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional

import requests
from sqlalchemy.orm import Session

from config import settings
from models import Street, TrafficData

# ─── LOGGING (hiển thị giờ Đà Nẵng +07:00) ───────────────────────────────────
class DaNangFormatter(logging.Formatter):
    """Formatter tùy chỉnh: in timestamp theo múi giờ Đà Nẵng (UTC+7)."""
    TZ = timezone(timedelta(hours=7))

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=self.TZ)
        return dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S +07")

handler = logging.StreamHandler()
handler.setFormatter(DaNangFormatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler])
log = logging.getLogger("ingestion")

# ─── TIMEZONE ─────────────────────────────────────────────────────────────────
TZ_DANANG = timezone(timedelta(hours=7))

# ─── GIỚI HẠN QUOTA PER NGÀY ──────────────────────────────────────────────────
TOMTOM_DAILY_LIMIT = 2400   # Để dưới 2500 một chút cho an toàn
GOONG_DAILY_LIMIT  = 900    # Để dưới 1000

# ─── TRACKER QUOTA ────────────────────────────────────────────────────────────
class QuotaTracker:
    """Đếm số request đã dùng trong ngày, tự reset lúc 00:00 Đà Nẵng."""
    def __init__(self, name: str, daily_limit: int):
        self.name  = name
        self.limit = daily_limit
        self.count = 0
        self._today = date.today()
        self._exhausted_today = False   # Đã hết quota hôm nay?

    def _maybe_reset(self):
        today = datetime.now(TZ_DANANG).date()
        if today != self._today:
            log.info(f"🔄 [{self.name}] Reset quota (ngày mới: {today})")
            self.count = 0
            self._today = today
            self._exhausted_today = False  # Ngày mới → cho phép gọi lại

    def use(self) -> bool:
        """Trả về True nếu còn quota, False nếu đã hết."""
        self._maybe_reset()
        if self.count >= self.limit:
            if not self._exhausted_today:
                # Chỉ cảnh báo 1 lần, không spam log
                next_reset = (datetime.now(TZ_DANANG) + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0
                )
                log.warning(
                    f"⛔ [{self.name}] HẾT QUOTA hôm nay ({self.count}/{self.limit} req). "
                    f"Tự động dừng gọi API. Reset lúc: {next_reset.strftime('%H:%M %d/%m')} +07:00"
                )
                self._exhausted_today = True
            return False
        self.count += 1
        return True

    @property
    def remaining(self) -> int:
        self._maybe_reset()
        return max(0, self.limit - self.count)

    @property
    def is_exhausted(self) -> bool:
        self._maybe_reset()
        return self._exhausted_today


tomtom_quota = QuotaTracker("TomTom", TOMTOM_DAILY_LIMIT)
goong_quota  = QuotaTracker("Goong",  GOONG_DAILY_LIMIT)


# ─── 1. TOMTOM FLOW SEGMENT API ───────────────────────────────────────────────
def fetch_tomtom(lat: float, lon: float) -> Optional[dict]:
    """
    Gọi TomTom Flow Segment API để lấy:
        - currentSpeed    : Tốc độ trung bình hiện tại (km/h)
        - freeFlowSpeed   : Tốc độ khi không có tắc nghẽn (km/h)
        - currentTravelTime / freeFlowTravelTime

    Docs: https://developer.tomtom.com/traffic-api/api-explorer/traffic-flow/flow-segment-data

    Trả về None nếu lỗi hoặc hết quota.
    """
    if not settings.tomtom_api_key:
        return None
    if not tomtom_quota.use():
        log.warning("⛔ TomTom quota hết cho hôm nay")
        return None

    url = (
        f"https://api.tomtom.com/traffic/services/4/flowSegmentData"
        f"/absolute/10/json"
        f"?point={lat},{lon}"
        f"&key={settings.tomtom_api_key}"
        f"&unit=KMPH"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("flowSegmentData", {})
        return {
            "avg_speed"      : data.get("currentSpeed"),
            "free_flow_speed": data.get("freeFlowSpeed"),
            "source"         : "tomtom",
        }
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            # Server bảo vượt rate limit → đánh dấu hết quota, không gọi tiếp
            log.warning("⛔ TomTom 429: Vượt rate limit. Đánh dấu hết quota.")
            tomtom_quota._exhausted_today = True
        else:
            log.warning(f"TomTom HTTP error: {e}")
        return None
    except Exception as e:
        log.warning(f"TomTom error: {e}")
        return None


# ─── 2. GOONG DISTANCE MATRIX API ─────────────────────────────────────────────
def fetch_goong(lat: float, lon: float, max_speed: int) -> Optional[dict]:
    """
    Gọi Goong Distance Matrix API — tính speed từ duration/distance.

    Chiến lược: gọi từ điểm trung tâm đến điểm lệch nhỏ →
    duration & distance → speed = distance / duration × 3.6

    Docs: https://docs.goong.io/rest/distance_matrix/

    Trả về None nếu lỗi hoặc hết quota.
    """
    if not settings.goong_api_key:
        return None
    if not goong_quota.use():
        log.warning("⛔ Goong quota hết cho hôm nay")
        return None

    # Điểm đích lệch ~500m về phía Đông
    lat2 = lat
    lon2 = lon + 0.005

    url = (
        f"https://rsapi.goong.io/DistanceMatrix"
        f"?origins={lat},{lon}"
        f"&destinations={lat2},{lon2}"
        f"&vehicle=car"
        f"&api_key={settings.goong_api_key}"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        rows = resp.json().get("rows", [])
        if not rows:
            return None
        element = rows[0]["elements"][0]
        if element.get("status") != "OK":
            return None

        distance_m : float = element["distance"]["value"]   # mét
        duration_s : float = element["duration"]["value"]   # giây

        if duration_s <= 0:
            return None

        speed_kmh = round((distance_m / duration_s) * 3.6, 1)
        # Giới hạn speed trong khoảng hợp lý
        speed_kmh = max(2.0, min(speed_kmh, max_speed * 1.1))

        return {
            "avg_speed": speed_kmh,
            "source"   : "goong",
        }
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            log.warning("⛔ Goong 429: Vượt rate limit. Đánh dấu hết quota.")
            goong_quota._exhausted_today = True
        else:
            log.warning(f"Goong HTTP error: {e}")
        return None
    except Exception as e:
        log.warning(f"Goong error: {e}")
        return None


# ─── 3. TÍNH CONGESTION LEVEL ─────────────────────────────────────────────────
def calc_congestion_level(avg_speed: float, max_speed: int) -> int:
    """0=Xanh, 1=Vàng, 2=Đỏ."""
    ratio = avg_speed / max_speed if max_speed > 0 else 0
    if ratio >= 0.70:
        return 0
    elif ratio >= 0.40:
        return 1
    return 2


# ─── 4. THU THẬP 1 ĐƯỜNG ──────────────────────────────────────────────────────
def get_street_centroid(street: Street, db: Session):
    """
    Lấy tọa độ điểm GIỮA của tuyến đường từ geometry LINESTRING trong DB.

    Dùng ST_Centroid (PostGIS) để tính tâm hình học:
      LINESTRING: ●──────●──────●──────●──────●
                                ↑
                           centroid → lat, lon

    Tại sao dùng centroid thay vì điểm đầu?
      - TomTom trả về traffic của đoạn gần nhất với điểm bạn gửi
      - Centroid đại diện tốt cho cả tuyến đường hơn điểm đầu/cuối
    """
    from sqlalchemy import func, text

    # Dùng PostGIS ST_Centroid để lấy điểm giữa
    # ST_X = kinh độ (longitude), ST_Y = vĩ độ (latitude)
    result = db.execute(
        text("""
            SELECT
                ST_Y(ST_Centroid(geometry)) AS lat,
                ST_X(ST_Centroid(geometry)) AS lon
            FROM streets
            WHERE id = :street_id
              AND geometry IS NOT NULL
        """),
        {"street_id": street.id}
    ).fetchone()

    if result and result.lat and result.lon:
        return result.lat, result.lon

    return None, None


def ingest_street(street: Street, db: Session) -> bool:
    """
    Thu thập và lưu dữ liệu traffic cho 1 đường.
    Ưu tiên TomTom → fallback Goong → bỏ qua nếu cả 2 đều fail.
    Trả về True nếu lưu thành công.
    """
    # ── Lấy tọa độ điểm giữa từ geometry trong DB ────────────
    lat, lon = get_street_centroid(street, db)

    # Fallback: đọc từ STREETS_DATA nếu geometry chưa có
    if lat is None or lon is None:
        from data.seed_danang import STREETS_DATA
        seed_coords = next(
            (s for s in STREETS_DATA if s["name"] == street.name), None
        )
        if not seed_coords:
            log.debug(f"  Không tìm thấy tọa độ cho '{street.name}'")
            return False
        lat, lon = seed_coords["lat"], seed_coords["lng"]
        log.debug(f"  [{street.name}] Dùng seed coords (geometry chưa có trong DB)")

    max_speed = street.max_speed or 50

    # Thử TomTom trước
    result = fetch_tomtom(lat, lon)

    # Fallback Goong
    if result is None:
        result = fetch_goong(lat, lon, max_speed)

    if result is None:
        log.debug(f"  [{street.name}] Không lấy được dữ liệu (cả 2 API fail)")
        return False

    avg_speed = result["avg_speed"]
    source    = result["source"]

    # Dùng freeFlowSpeed của TomTom làm chuẩn so sánh (chính xác hơn max_speed DB)
    # freeFlowSpeed = tốc độ thực tế khi đường thông thoáng (không phải giới hạn pháp lý)
    # Nếu không có (Goong fallback) → dùng max_speed từ DB
    reference_speed = result.get("free_flow_speed") or max_speed
    congestion = calc_congestion_level(avg_speed, reference_speed)

    # Lưu vào DB
    record = TrafficData(
        street_id        = street.id,
        timestamp        = datetime.now(timezone.utc),
        avg_speed        = avg_speed,
        congestion_level = congestion,
        source           = source,
    )
    db.add(record)

    label = {0: "🟢", 1: "🟡", 2: "🔴"}[congestion]
    log.info(
        f"  {label} {street.name:<30} {avg_speed:>5.1f} km/h "
        f"[{source}] (TomTom còn {tomtom_quota.remaining} req)"
    )
    return True


# ─── 5. MỘT VÒNG THU THẬP ─────────────────────────────────────────────────────
def run_one_cycle(streets: list, db: Session, delay_seconds: float = 1.5) -> int:
    """
    Thu thập toàn bộ đường trong 1 chu kỳ.
    delay_seconds: nghỉ giữa mỗi đường để tránh spike request.
    Trả về số đường thu thập thành công.
    """
    # Nếu cả 2 API đều hết quota → bỏ qua chu kỳ này hoàn toàn
    if tomtom_quota.is_exhausted and goong_quota.is_exhausted:
        log.warning(
            "⛔ Cả TomTom và Goong đều hết quota hôm nay. "
            "Bỏ qua chu kỳ, đợi đến 00:00 +07:00 reset tự động."
        )
        return 0

    success = 0
    for street in streets:
        ok = ingest_street(street, db)
        if ok:
            success += 1
        time.sleep(delay_seconds)

    try:
        db.commit()
        log.info(f"✅ Đã lưu {success}/{len(streets)} đường vào DB")
    except Exception as e:
        db.rollback()
        log.error(f"❌ Lỗi commit DB: {e}")

    return success
