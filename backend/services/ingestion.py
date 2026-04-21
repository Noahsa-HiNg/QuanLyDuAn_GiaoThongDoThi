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
        self._exhausted_today = False

    def _maybe_reset(self):
        today = datetime.now(TZ_DANANG).date()
        if today != self._today:
            log.info(f"🔄 [{self.name}] Reset quota (ngày mới: {today})")
            self.count = 0
            self._today = today
            self._exhausted_today = False

    def use(self) -> bool:
        """Trả về True nếu còn quota, False nếu đã hết."""
        self._maybe_reset()
        if self.count >= self.limit:
            if not self._exhausted_today:
                next_reset = (datetime.now(TZ_DANANG) + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0
                )
                log.warning(
                    f"⛔ [{self.name}] HẾT QUOTA hôm nay ({self.count}/{self.limit} req). "
                    f"Reset lúc: {next_reset.strftime('%H:%M %d/%m')} +07:00"
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


class MultiKeyQuotaTracker:
    """
    Quản lý nhiều TomTom API key với tự động luân phiên (key rotation).

    Cơ chế:
      - Mỗi key có QuotaTracker riêng (2400 req/ngày)
      - Khi key hiện tại hết quota → tự chuyển sang key tiếp theo
      - Khi tất cả key hết quota → trả về None (bỏ qua chu kỳ)

    Cấu hình trong .env:
      TOMTOM_API_KEYS=key1,key2,key3
      → Tổng quota: 3 × 2400 = 7200 req/ngày
    """
    def __init__(self, daily_limit: int = TOMTOM_DAILY_LIMIT):
        self.daily_limit   = daily_limit
        self._trackers: dict[str, QuotaTracker] = {}   # {api_key: QuotaTracker}
        self._current_idx  = 0
        self._keys: list[str] = []
        self._reload_keys()

    def _reload_keys(self):
        """Load danh sách key từ settings (hỗ trợ add key khi đang chạy)."""
        new_keys = settings.tomtom_keys_list
        if new_keys != self._keys:
            # Thêm tracker cho key mới, giữ tracker cũ
            for k in new_keys:
                if k not in self._trackers:
                    self._trackers[k] = QuotaTracker(f"TomTom[{k[:8]}...]", self.daily_limit)
            self._keys = new_keys
            log.info(f"🔑 TomTom keys loaded: {len(self._keys)} key(s), "
                     f"tổng quota: {len(self._keys) * self.daily_limit} req/ngày")

    @property
    def active_key(self) -> Optional[str]:
        """Trả về key đang dùng, tự chuyển sang key tiếp nếu key hiện tại hết."""
        self._reload_keys()
        if not self._keys:
            return None

        # Thử các key từ vị trí hiện tại
        for _ in range(len(self._keys)):
            idx = self._current_idx % len(self._keys)
            key = self._keys[idx]
            tracker = self._trackers[key]

            if not tracker.is_exhausted and tracker.use():
                return key

            # Key này hết quota → thử key tiếp
            log.info(f"🔄 Key [{key[:8]}...] hết quota, thử key tiếp theo...")
            self._current_idx += 1

        # Tất cả key hết quota
        return None

    def mark_exhausted(self, key: str):
        """Đánh dấu key bị 429 → chuyển sang key khác ngay."""
        if key in self._trackers:
            self._trackers[key]._exhausted_today = True
            log.warning(f"⛔ Key [{key[:8]}...] bị 429 → đánh dấu hết quota, chuyển key")
            self._current_idx += 1

    @property
    def is_exhausted(self) -> bool:
        """True khi TẤT CẢ key đều hết quota hôm nay."""
        if not self._keys:
            return True
        return all(self._trackers[k].is_exhausted for k in self._keys)

    @property
    def remaining(self) -> int:
        """Tổng số request còn lại trên TẤT CẢ key."""
        return sum(self._trackers[k].remaining for k in self._keys)

    @property
    def summary(self) -> str:
        parts = []
        for k in self._keys:
            t = self._trackers[k]
            parts.append(f"{k[:8]}...:{t.remaining}")
        return " | ".join(parts) if parts else "Không có key"


tomtom_quota = MultiKeyQuotaTracker()
goong_quota  = QuotaTracker("Goong", GOONG_DAILY_LIMIT)


# ─── 1. TOMTOM FLOW SEGMENT API ───────────────────────────────────────────────
def fetch_tomtom(lat: float, lon: float) -> Optional[dict]:
    """
    Gọi TomTom Flow Segment API — SOURCE OF TRUTH cho toàn bộ project.

    Tự động xử lý:
      - 429 → key hết quota  → chuyển sang key tiếp theo
      - 403 → key không hợp lệ / bị khóa → chuyển sang key tiếp theo
      Thử TẤT CẢ key trước khi trả về None.

    Trả về None nếu:
      - Tất cả key đều hết quota / không hợp lệ
      - Lỗi mạng nghiêm trọng
    """
    n_keys = len(tomtom_quota._keys) if tomtom_quota._keys else 1

    # Thử tối đa n_keys lần — mỗi lần một key khác nhau
    for attempt in range(n_keys + 1):
        api_key = tomtom_quota.active_key
        if not api_key:
            log.warning("⛔ Tất cả TomTom key đã hết quota / không hợp lệ")
            return None

        key_hint = f"{api_key[:8]}..."
        url = (
            f"https://api.tomtom.com/traffic/services/4/flowSegmentData"
            f"/absolute/10/json"
            f"?point={lat},{lon}"
            f"&key={api_key}"
            f"&unit=KMPH"
        )
        try:
            resp = requests.get(url, timeout=10)

            if resp.status_code == 429:
                # 429 = Too Many Requests → key bị rate-limit → chuyển key tiếp
                log.warning(f"⛔ TomTom 429: key [{key_hint}] hết quota → thử key tiếp")
                tomtom_quota.mark_exhausted(api_key)
                continue   # ← thử lại với key mới

            if resp.status_code == 403:
                # 403 = Forbidden → key không hợp lệ hoặc bị khóa → chuyển key tiếp
                log.warning(f"⛔ TomTom 403: key [{key_hint}] bị từ chối → thử key tiếp")
                tomtom_quota.mark_exhausted(api_key)
                continue   # ← thử lại với key mới

            resp.raise_for_status()
            data = resp.json().get("flowSegmentData", {})
            return {
                "avg_speed"      : data.get("currentSpeed"),
                "free_flow_speed": data.get("freeFlowSpeed"),
                "source"         : "tomtom",
            }

        except requests.exceptions.HTTPError as e:
            log.warning(f"TomTom HTTP error [{key_hint}]: {e}")
            return None
        except Exception as e:
            log.warning(f"TomTom error [{key_hint}]: {e}")
            return None

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


# Số ZONE TỐI ĐA mỗi đường (càng nhiều → càng chi tiết → càng nhiều quota)
# 4 zone × 49 đường = 196 calls/chu kỳ
MAX_ZONES_PER_STREET = 4


def get_street_path_coords(street: Street, db: Session) -> list:
    """
    Lấy danh sách tọa độ [[lon, lat], ...] của tuyến đường từ geometry PostGIS.
    Trả về list rỗng nếu chưa có geometry.
    """
    from sqlalchemy import text
    import json

    row = db.execute(
        text("""
            SELECT (ST_AsGeoJSON(geometry)::json -> 'coordinates') AS coords
            FROM streets
            WHERE id = :sid AND geometry IS NOT NULL
        """),
        {"sid": street.id}
    ).fetchone()

    if not row or not row.coords:
        return []

    coords = json.loads(row.coords) if isinstance(row.coords, str) else row.coords
    return coords if coords else []    # [[lon, lat], [lon, lat], ...]


def ingest_street(street: Street, db: Session) -> bool:
    """
    Thu thập và lưu dữ liệu traffic cho 1 đường.

    Nếu đường có geometry (nhiều điểm) → chia thành MAX_ZONES_PER_STREET zone
    → gọi TomTom tại midpoint mỗi zone → lưu N bản ghi với segment_idx khác nhau.

    Nếu đường không có geometry (fallback) → gọi 1 lần tại centroid seed coords.
    Trả về số bản ghi đã lưu (>0 = thành công).
    """
    from utils.geometry import split_path_into_zones

    max_speed = street.max_speed or 50
    now       = datetime.now(timezone.utc)
    saved     = 0

    # ── Lấy tọa độ geometry từ DB ─────────────────────────────────────
    coords = get_street_path_coords(street, db)

    if coords and len(coords) >= 2:
        # Đường có geometry → chia thành zone TỰ ĐỘNG theo độ dài
        # split_path_into_zones() không có n_zones → tự tính (1 zone/500m)
        from utils.geometry import calc_road_length_m
        length_m = calc_road_length_m(coords)
        zones = split_path_into_zones(coords)   # n_zones=None → auto
        log.debug(
            f"  [{street.name}] Dài {length_m/1000:.1f}km "
            f"→ {len(zones)} zone(s)"
        )
    else:
        # Không có geometry → dùng seed coords, chỉ 1 zone
        from data.seed_danang import STREETS_DATA
        seed = next((s for s in STREETS_DATA if s["name"] == street.name), None)
        if not seed:
            log.debug(f"  Không tìm thấy tọa độ cho '{street.name}'")
            return False
        zones = [{
            "segment_idx": 0,
            "mid_lat"    : seed["lat"],
            "mid_lon"    : seed["lng"],
        }]
        log.debug(f"  [{street.name}] Dùng seed coords (chưa có geometry)")

    # ── Gọi TomTom cho từng zone ──────────────────────────────────────
    for zone in zones:
        seg_idx = zone["segment_idx"]
        lat     = zone["mid_lat"]
        lon     = zone["mid_lon"]

        # Thử TomTom → fallback Goong
        result = fetch_tomtom(lat, lon)
        if result is None:
            result = fetch_goong(lat, lon, max_speed)
        if result is None:
            log.debug(f"  [{street.name}] Zone {seg_idx}: API fail, bỏ qua")
            continue

        avg_speed = result["avg_speed"]
        source    = result["source"]
        ref_speed = result.get("free_flow_speed") or max_speed
        congestion = calc_congestion_level(avg_speed, ref_speed)

        record = TrafficData(
            street_id        = street.id,
            segment_idx      = seg_idx,
            timestamp        = now,
            avg_speed        = avg_speed,
            congestion_level = congestion,
            source           = source,
        )
        db.add(record)
        saved += 1

        label = {0: "🟢", 1: "🟡", 2: "🔴"}[congestion]
        log.info(
            f"  {label} {street.name:<25} zone{seg_idx} "
            f"{avg_speed:>5.1f} km/h [{source}] "
            f"(quota: {tomtom_quota.summary})"
        )

        # Delay nhỏ giữa các zone của cùng 1 đường
        if len(zones) > 1:
            time.sleep(0.5)

    return saved > 0


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
