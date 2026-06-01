import numpy as np
# ── HELPERS ────────────────────────────────────────────────────────────────────
def is_rush_hour(hour: int) -> int:
    return 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0
def engineer_features(traffic_df):
    # =====================================================
    # Historical Features
    # =====================================================

    traffic_df["avg_speed_1h_ago"] = (
        traffic_df.groupby("street_id")["avg_speed"]
        .shift(12)
    )

    traffic_df["avg_speed_yesterday"] = (
        traffic_df.groupby("street_id")["avg_speed"]
        .shift(288)
    )

    # =====================================================
    # Feature Engineering
    # =====================================================

    traffic_df["current_speed"] = traffic_df["avg_speed"]

    traffic_df["speed_ratio"] = (
        traffic_df["current_speed"]
        / traffic_df["free_flow_speed"]
    )

    traffic_df["speed_ratio"] = (
        traffic_df["speed_ratio"]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(1.0)
    )

    traffic_df["speed_delta"] = (
        traffic_df["current_speed"]
        - traffic_df["avg_speed_1h_ago"]
    )

    traffic_df["rolling_speed_3"] = (
        traffic_df.groupby("street_id")["current_speed"]
        .transform(
            lambda x: x.rolling(
                window=3,
                min_periods=1
            ).mean()
        )
    )
    # =====================================================
    # Time Features
    # =====================================================

    traffic_df["hour"] = (
        traffic_df["hour"]
        .astype(int)
    )

    traffic_df["day_of_week"] = (
        traffic_df["day_of_week"]
        .astype(int)
    )

    traffic_df["is_weekend"] = (
        traffic_df["day_of_week"] >= 5
    ).astype(int)

    traffic_df["is_rush_hour"] = (
        traffic_df["hour"]
        .apply(is_rush_hour)
    )
    return traffic_df

def fetch_weather_danang() -> dict:
    import os
    import requests
    import logging
    log = logging.getLogger(__name__)

    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    if not api_key:
        return _weather_fallback()

    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat=16.0544&lon=108.2022"
            f"&appid={api_key}"
            f"&units=metric"
        )
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()

        weather_id  = data["weather"][0]["id"]
        temp        = data["main"]["temp"]
        humidity    = data["main"]["humidity"]
        wind_speed  = data.get("wind", {}).get("speed", 0)
        rain_1h     = data.get("rain", {}).get("1h", 0.0)
        visibility  = data.get("visibility", 10000) / 1000

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
            "weather_group"  : _classify_weather(weather_id, rain_1h),
        }
    except Exception as e:
        log.warning(f"⚠ OpenWeather API lỗi: {e} — dùng fallback")
        return _weather_fallback()

def _classify_weather(weather_id: int, rain_mm: float) -> int:
    if weather_id == 800:          return 0
    if 801 <= weather_id <= 804:   return 1
    if rain_mm > 5.0:              return 3
    if rain_mm > 0.1:              return 2
    return 4

def _weather_fallback() -> dict:
    return {
        "temperature": 28.0, "humidity": 75, "wind_speed": 10,
        "rain_1h_mm": 0.0, "visibility_km": 10.0,
        "is_raining": 0, "is_heavy_rain": 0, "is_foggy": 0,
        "weather_id": 800, "weather_group": 0,
    }