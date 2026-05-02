"""
ml/feature_engineering.py — Tạo đặc trưng ML từ dữ liệu đã cào

TRIẾT LÝ:
    Dữ liệu cào (traffic_data) chỉ có: avg_speed, congestion_level, timestamp.
    Tất cả đặc trưng còn lại đều được TÍNH TOÁN tại thời điểm train/inference.
    → Không cần cào lại để thêm đặc trưng mới.

Nhóm đặc trưng (được tính từ dữ liệu có sẵn):
    [A] Time features      — từ timestamp (không cần crawl thêm)
    [B] Lag features       — từ lịch sử traffic_data trong DB
    [C] Static features    — từ bảng streets (max_speed, length_km, ...)
    [D] Weather features   — từ OpenWeatherMap API (đã có key trong .env)
    [E] Derived features   — tính toán từ A+B+C (speed_ratio, trend, ...)
"""

import math
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import numpy as np
import pandas as pd

log = logging.getLogger("feature_engineering")

TZ_VN = timezone(timedelta(hours=7))

# ── Ngày lễ Việt Nam (không đổi hàng năm) ────────────────────────────────────
VN_HOLIDAYS_MMDD = {
    "01-01",  # Tết Dương lịch
    "04-30",  # Ngày Giải phóng
    "05-01",  # Ngày Quốc tế Lao động
    "09-02",  # Quốc khánh
}

# ── Giờ cao điểm giao thông Đà Nẵng ─────────────────────────────────────────
RUSH_HOURS_MORNING   = set(range(7, 10))    # 7:00 – 9:59
RUSH_HOURS_EVENING   = set(range(17, 20))   # 17:00 – 19:59
SCHOOL_HOURS         = set(range(11, 13))   # 11:00 – 12:59 (tan trường)


# ═════════════════════════════════════════════════════════════════════════════
# [A] TIME FEATURES — từ 1 cột timestamp
# ═════════════════════════════════════════════════════════════════════════════

def extract_time_features(ts: datetime) -> dict:
    """
    Trích xuất toàn bộ đặc trưng thời gian từ 1 timestamp.

    Tại sao dùng sin/cos encoding?
        - Giờ 23 và giờ 0 thực ra rất gần nhau (chỉ cách 1 giờ)
        - Nếu dùng raw: |23 - 0| = 23 (xa nhau giả tạo)
        - Sin/cos: sin(23×2π/24) ≈ sin(0×2π/24) → gần nhau ✓
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=TZ_VN)
    else:
        ts = ts.astimezone(TZ_VN)

    h   = ts.hour
    dow = ts.weekday()   # 0=Thứ 2, 6=CN
    mm  = ts.month
    dom = ts.day

    is_holiday = ts.strftime("%m-%d") in VN_HOLIDAYS_MMDD

    return {
        # Raw time values
        "hour"          : h,
        "day_of_week"   : dow,
        "month"         : mm,
        "day_of_month"  : dom,
        "quarter"       : (mm - 1) // 3 + 1,

        # Cyclic encoding (tránh boundary artifact)
        "sin_hour"      : math.sin(2 * math.pi * h / 24),
        "cos_hour"      : math.cos(2 * math.pi * h / 24),
        "sin_dow"       : math.sin(2 * math.pi * dow / 7),
        "cos_dow"       : math.cos(2 * math.pi * dow / 7),
        "sin_month"     : math.sin(2 * math.pi * mm / 12),
        "cos_month"     : math.cos(2 * math.pi * mm / 12),

        # Binary flags — ML model dễ học
        "is_weekend"    : int(dow >= 5),
        "is_rush_am"    : int(h in RUSH_HOURS_MORNING),
        "is_rush_pm"    : int(h in RUSH_HOURS_EVENING),
        "is_school_out" : int(h in SCHOOL_HOURS),
        "is_rush_hour"  : int(h in RUSH_HOURS_MORNING | RUSH_HOURS_EVENING),
        "is_holiday"    : int(is_holiday),
        "is_night"      : int(h < 6 or h >= 23),
        "is_morning"    : int(6 <= h < 12),
        "is_afternoon"  : int(12 <= h < 18),
        "is_evening"    : int(18 <= h < 23),
    }


# ═════════════════════════════════════════════════════════════════════════════
# [B] LAG FEATURES — từ lịch sử traffic_data (không cần crawl thêm)
# ═════════════════════════════════════════════════════════════════════════════

def extract_lag_features(history: list[dict]) -> dict:
    """
    Tính lag + rolling features từ lịch sử tốc độ.

    Args:
        history: list[dict] {"avg_speed": float, "timestamp": datetime}
                 Phải được SẮP XẾP TĂNG DẦN theo timestamp.
                 Thường lấy 48 bản ghi gần nhất (= 8 giờ nếu 10p/lần).

    Tại sao lag features quan trọng?
        - Giao thông có pattern rõ: nếu 10 phút trước kẹt → 10 phút sau vẫn kẹt
        - Lag 1 ngày (cùng giờ hôm qua) capture weekly pattern
        - Lag 1 tuần lần nữa = seasonal pattern
    """
    speeds = [h["avg_speed"] for h in history if h.get("avg_speed") is not None]

    def safe_get(lst: list, idx: int) -> Optional[float]:
        """Lấy phần tử từ cuối list, trả None nếu không đủ."""
        try:
            return lst[-(idx + 1)]
        except IndexError:
            return None

    n = len(speeds)

    # Rolling averages
    roll_2  = float(np.mean(speeds[-2:]))  if n >= 2  else None  # 20 phút
    roll_6  = float(np.mean(speeds[-6:]))  if n >= 6  else None  # 1 giờ
    roll_18 = float(np.mean(speeds[-18:])) if n >= 18 else None  # 3 giờ

    # Rolling std (variability)
    std_6   = float(np.std(speeds[-6:]))  if n >= 6  else None
    std_18  = float(np.std(speeds[-18:])) if n >= 18 else None

    # Speed trend (đang tăng hay giảm?)
    trend_1h = None
    if n >= 6:
        old = np.mean(speeds[-6:-3])
        new = np.mean(speeds[-3:])
        trend_1h = float(new - old)  # Dương = đang tăng tốc, Âm = đang chậm lại

    return {
        # Lag trực tiếp (n × interval phút trước)
        "speed_lag_1"   : safe_get(speeds, 0),   # 10 phút trước
        "speed_lag_2"   : safe_get(speeds, 1),   # 20 phút trước
        "speed_lag_3"   : safe_get(speeds, 2),   # 30 phút trước
        "speed_lag_6"   : safe_get(speeds, 5),   # 1 giờ trước
        "speed_lag_12"  : safe_get(speeds, 11),  # 2 giờ trước
        "speed_lag_18"  : safe_get(speeds, 17),  # 3 giờ trước

        # Rolling mean
        "speed_roll_20m": roll_2,
        "speed_roll_1h" : roll_6,
        "speed_roll_3h" : roll_18,

        # Rolling std (đo mức biến động)
        "speed_std_1h"  : std_6,
        "speed_std_3h"  : std_18,

        # Trend
        "speed_trend_1h": trend_1h,

        # Số quan sát có trong lịch sử (để model biết độ tin cậy)
        "history_count" : n,
    }


# ═════════════════════════════════════════════════════════════════════════════
# [C] STATIC FEATURES — từ bảng streets (đã có sẵn, không cần crawl)
# ═════════════════════════════════════════════════════════════════════════════

def extract_static_features(street: dict, segment_idx: int) -> dict:
    """
    Đặc trưng tĩnh của tuyến đường — không thay đổi theo thời gian.

    Args:
        street: dict với keys: id, district_id, max_speed, length_km, is_one_way
        segment_idx: 0, 1, 2, 3 — đoạn thứ mấy của đường
    """
    max_speed  = street.get("max_speed") or 50
    length_km  = street.get("length_km") or 1.0

    # Phân loại đường theo tốc độ giới hạn
    # 0 = phố nhỏ (<40), 1 = đường nội bộ (40-60), 2 = đường lớn (>60)
    speed_class = 0 if max_speed < 40 else (1 if max_speed <= 60 else 2)

    # Phân loại theo độ dài
    length_class = 0 if length_km < 1 else (1 if length_km <= 3 else 2)

    return {
        "street_id"     : street["id"],
        "district_id"   : street.get("district_id") or 0,
        "max_speed"     : max_speed,
        "length_km"     : length_km,
        "is_one_way"    : int(street.get("is_one_way") or False),
        "segment_idx"   : segment_idx,
        "speed_class"   : speed_class,
        "length_class"  : length_class,

        # Segment ratio: đoạn này chiếm bao nhiêu % đường
        # (tính gần đúng, sẽ update khi biết tổng số segment)
        "segment_ratio" : segment_idx / max(segment_idx + 1, 1),
    }


# ═════════════════════════════════════════════════════════════════════════════
# [D] WEATHER FEATURES — OpenWeatherMap (đã có key, cào nhẹ ~6 req/giờ)
# ═════════════════════════════════════════════════════════════════════════════

def fetch_weather_danang() -> dict:
    """
    Lấy thời tiết Đà Nẵng từ OpenWeatherMap.
    Gọi 1 lần / chu kỳ scheduler (dùng chung cho tất cả đường).
    Quota: 1 call/10 phút = 144 calls/ngày << 1000 limit free tier.

    Tọa độ Đà Nẵng: lat=16.0544, lon=108.2022
    """
    import os
    import requests

    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    if not api_key:
        return _weather_fallback()

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat=16.0544&lon=108.2022"
            f"&appid={api_key}"
            f"&units=metric"  # Celsius
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        weather_id  = data["weather"][0]["id"]   # 800=clear, 5xx=rain...
        temp        = data["main"]["temp"]
        humidity    = data["main"]["humidity"]
        wind_speed  = data.get("wind", {}).get("speed", 0)
        rain_1h     = data.get("rain", {}).get("1h", 0.0)
        visibility  = data.get("visibility", 10000) / 1000  # → km

        return {
            "temperature"    : temp,
            "humidity"       : humidity,
            "wind_speed"     : wind_speed,
            "rain_1h_mm"     : rain_1h,
            "visibility_km"  : visibility,
            "is_raining"     : int(rain_1h > 0.1),
            "is_heavy_rain"  : int(rain_1h > 5.0),
            "is_foggy"       : int(visibility < 1.0),
            "weather_id"     : weather_id,
            # Nhóm thời tiết: 0=rõ, 1=mây, 2=mưa nhẹ, 3=mưa nặng, 4=khác
            "weather_group"  : _classify_weather(weather_id, rain_1h),
        }
    except Exception as e:
        log.warning(f"⚠ OpenWeather API lỗi: {e} — dùng fallback")
        return _weather_fallback()


def _classify_weather(weather_id: int, rain_mm: float) -> int:
    """Phân loại thời tiết thành nhóm 0-4."""
    if weather_id == 800:          return 0  # Trời quang
    if 801 <= weather_id <= 804:   return 1  # Có mây
    if rain_mm > 5.0:              return 3  # Mưa nặng
    if rain_mm > 0.1:              return 2  # Mưa nhẹ
    return 4                                  # Khác (sương mù, etc.)


def _weather_fallback() -> dict:
    """Trả về giá trị trung bình khi API lỗi."""
    return {
        "temperature": 28.0, "humidity": 75, "wind_speed": 10,
        "rain_1h_mm": 0.0, "visibility_km": 10.0,
        "is_raining": 0, "is_heavy_rain": 0, "is_foggy": 0,
        "weather_id": 800, "weather_group": 0,
    }


# ═════════════════════════════════════════════════════════════════════════════
# [E] DERIVED FEATURES — tính từ A+B+C (không cần crawl)
# ═════════════════════════════════════════════════════════════════════════════

def extract_derived_features(
    current_speed: Optional[float],
    max_speed    : int,
    lag_features : dict,
    time_features: dict,
) -> dict:
    """Các đặc trưng phái sinh quan trọng."""
    speed = current_speed or lag_features.get("speed_lag_1") or max_speed * 0.6

    speed_ratio    = speed / max_speed if max_speed > 0 else 0
    roll_1h        = lag_features.get("speed_roll_1h") or speed
    deviation_1h   = speed - roll_1h                    # Lệch so với TB 1 giờ

    return {
        # Tỷ lệ so với tốc độ giới hạn (đặc trưng quan trọng nhất)
        "speed_ratio"        : speed_ratio,

        # Lệch so với trung bình lịch sử
        "speed_deviation_1h" : deviation_1h,

        # Mức kẹt hiện tại (để model học pattern transition)
        "current_level"      : _speed_to_level(speed_ratio),

        # Kết hợp giờ cao điểm + thời tiết
        "rush_x_rain"        : time_features.get("is_rush_hour", 0) * 1
                               + (1.5 if time_features.get("is_weekend") else 1.0),
    }


def _speed_to_level(ratio: float) -> int:
    if ratio >= 0.7: return 0
    if ratio >= 0.4: return 1
    return 2


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API: tạo feature vector hoàn chỉnh
# ═════════════════════════════════════════════════════════════════════════════

def build_feature_vector(
    street      : dict,
    segment_idx : int,
    history     : list[dict],  # [{avg_speed, timestamp}, ...]
    current_ts  : Optional[datetime] = None,
    weather     : Optional[dict] = None,
) -> dict:
    """
    Tạo feature vector đầy đủ cho 1 (street, segment) tại thời điểm current_ts.
    Dùng cho cả training và inference — API thống nhất.

    Args:
        street      : dict thông tin đường (id, max_speed, length_km, ...)
        segment_idx : zone number
        history     : list bản ghi traffic cũ (sắp xếp tăng dần theo timestamp)
        current_ts  : thời điểm inference (default = now())
        weather     : dict từ fetch_weather_danang() — gọi 1 lần share tất cả đường

    Returns:
        dict: tất cả đặc trưng sẵn sàng để đưa vào model.

    Example:
        weather = fetch_weather_danang()
        for street in streets:
            history = get_street_history(street.id, segment_idx, last_n=50)
            fv = build_feature_vector(street.__dict__, segment_idx, history, weather=weather)
            X.append(fv)
    """
    ts = current_ts or datetime.now(TZ_VN)

    time_f    = extract_time_features(ts)
    lag_f     = extract_lag_features(history)
    static_f  = extract_static_features(street, segment_idx)
    weather_f = weather or _weather_fallback()

    current_speed = history[-1].get("avg_speed") if history else None
    derived_f = extract_derived_features(
        current_speed,
        street.get("max_speed") or 50,
        lag_f,
        time_f,
    )

    # Merge tất cả nhóm
    return {**time_f, **lag_f, **static_f, **weather_f, **derived_f}


def get_feature_names() -> list[str]:
    """Trả về danh sách tên đặc trưng (để tạo DataFrame)."""
    dummy_street  = {"id": 0, "district_id": 1, "max_speed": 50,
                     "length_km": 2.0, "is_one_way": False}
    dummy_history = [{"avg_speed": 40.0, "timestamp": datetime.now(TZ_VN)}]
    fv = build_feature_vector(dummy_street, 0, dummy_history)
    return list(fv.keys())
