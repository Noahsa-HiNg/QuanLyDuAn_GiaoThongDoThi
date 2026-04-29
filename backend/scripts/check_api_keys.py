"""
scripts/check_api_keys.py — Kiểm tra tất cả API key có hoạt động không

Chạy TRONG container backend:
    docker compose exec backend python scripts/check_api_keys.py

Chạy NGOÀI Docker (cần pip install python-dotenv requests):
    cd backend
    python scripts/check_api_keys.py

Output ví dụ:
    ══════════════════════════════════════
    🔑 KIỂM TRA API KEYS — 17:14 29/04/2026
    ══════════════════════════════════════
    [TomTom] ixWGJspb...
      ✅ OK — speed=42.3 km/h  (quota còn: ~2499 req)
    [TomTom] 0MwoazqB...
      ✅ OK — speed=42.3 km/h  (quota còn: ~2499 req)
    [Goong]
      ✅ OK — speed=38.1 km/h
    [OpenWeather]
      ✅ OK — 32°C, mưa: 0.0mm, tầm nhìn: 10.0km
    ══════════════════════════════════════
    Kết quả: 3/3 TomTom ✅ | Goong ✅ | Weather ✅
"""

import os
import sys
import requests
from datetime import datetime, timezone, timedelta

# ── Đọc .env nếu chạy ngoài Docker ──────────────────────────────────────────
try:
    from dotenv import load_dotenv
    # Tìm .env ở thư mục cha của backend/
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    load_dotenv(dotenv_path=os.path.abspath(env_path))
except ImportError:
    pass  # Trong Docker thì env đã có sẵn

TZ_VN = timezone(timedelta(hours=7))

# ── Tọa độ test: giữa TP Đà Nẵng (đường Lê Duẩn) ───────────────────────────
TEST_LAT = 16.0544
TEST_LON = 108.2022

TIMEOUT = 8  # giây

# ─────────────────────────────────────────────────────────────────────────────

def check_tomtom(api_key: str) -> dict:
    """Gọi TomTom Traffic Flow API và kiểm tra phản hồi."""
    url = (
        f"https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
        f"?point={TEST_LAT},{TEST_LON}&key={api_key}"
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            speed = data.get("flowSegmentData", {}).get("currentSpeed", "?")
            free  = data.get("flowSegmentData", {}).get("freeFlowSpeed", "?")
            return {"ok": True, "speed": speed, "free_flow": free, "status": 200}
        elif resp.status_code == 403:
            return {"ok": False, "error": "403 Forbidden — Key không hợp lệ hoặc hết hạn"}
        elif resp.status_code == 429:
            return {"ok": False, "error": "429 Too Many Requests — Key đã hết quota hôm nay"}
        else:
            return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:100]}"}
    except requests.Timeout:
        return {"ok": False, "error": "Timeout — TomTom không phản hồi trong 8 giây"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_goong(api_key: str) -> dict:
    """Gọi Goong Directions API và kiểm tra phản hồi."""
    # Dùng geocoding để test — nhẹ nhất, không tốn nhiều quota
    url = (
        f"https://rsapi.goong.io/Geocode"
        f"?latlng={TEST_LAT},{TEST_LON}&api_key={api_key}"
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "?")
            if status == "OK":
                address = data.get("results", [{}])[0].get("formatted_address", "?")
                return {"ok": True, "address": address[:60]}
            else:
                return {"ok": False, "error": f"API status: {status}"}
        elif resp.status_code == 401:
            return {"ok": False, "error": "401 Unauthorized — Key không hợp lệ"}
        elif resp.status_code == 429:
            return {"ok": False, "error": "429 — Key đã hết quota hôm nay"}
        else:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
    except requests.Timeout:
        return {"ok": False, "error": "Timeout — Goong không phản hồi trong 8 giây"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_openweather(api_key: str) -> dict:
    """Gọi OpenWeatherMap Current Weather API."""
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?lat={TEST_LAT}&lon={TEST_LON}&appid={api_key}&units=metric"
    )
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            temp     = data["main"]["temp"]
            humidity = data["main"]["humidity"]
            rain     = data.get("rain", {}).get("1h", 0.0)
            vis      = data.get("visibility", 10000) / 1000
            desc     = data["weather"][0]["description"]
            return {"ok": True, "temp": temp, "humidity": humidity,
                    "rain": rain, "visibility": vis, "desc": desc}
        elif resp.status_code == 401:
            return {"ok": False, "error": "401 — Key không hợp lệ hoặc chưa kích hoạt (chờ ~2h sau khi đăng ký)"}
        elif resp.status_code == 429:
            return {"ok": False, "error": "429 — Vượt giới hạn request"}
        else:
            return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:100]}"}
    except requests.Timeout:
        return {"ok": False, "error": "Timeout — OpenWeather không phản hồi trong 8 giây"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now(TZ_VN).strftime("%H:%M %d/%m/%Y")
    print(f"\n{'═'*50}")
    print(f"🔑 KIỂM TRA API KEYS — {now}")
    print(f"{'═'*50}\n")

    # ── TomTom keys ──────────────────────────────────────────────────────────
    tomtom_keys_raw = os.getenv("TOMTOM_API_KEYS", "")
    tomtom_single   = os.getenv("TOMTOM_API_KEY", "")

    # Lấy danh sách key (ưu tiên TOMTOM_API_KEYS)
    if tomtom_keys_raw:
        tomtom_keys = [k.strip() for k in tomtom_keys_raw.split(",") if k.strip()]
    elif tomtom_single:
        tomtom_keys = [tomtom_single]
    else:
        tomtom_keys = []

    print(f"📍 TomTom ({len(tomtom_keys)} key):")
    tomtom_ok = 0
    if not tomtom_keys:
        print("  ⚠️  Không tìm thấy TOMTOM_API_KEY hoặc TOMTOM_API_KEYS trong .env")
    else:
        for key in tomtom_keys:
            display = f"{key[:8]}...{key[-4:]}"
            result = check_tomtom(key)
            if result["ok"]:
                print(f"  ✅ [{display}] speed={result['speed']} km/h | free_flow={result['free_flow']} km/h")
                tomtom_ok += 1
            else:
                print(f"  ❌ [{display}] {result['error']}")

    # ── Goong key ─────────────────────────────────────────────────────────────
    goong_key = os.getenv("GOONG_API_KEY", "")
    print(f"\n📍 Goong:")
    goong_ok = False
    if not goong_key:
        print("  ⚠️  Không tìm thấy GOONG_API_KEY trong .env")
    else:
        display = f"{goong_key[:8]}...{goong_key[-4:]}"
        result = check_goong(goong_key)
        if result["ok"]:
            print(f"  ✅ [{display}] Địa chỉ test: {result['address']}")
            goong_ok = True
        else:
            print(f"  ❌ [{display}] {result['error']}")

    # ── OpenWeather key ───────────────────────────────────────────────────────
    weather_key = os.getenv("OPENWEATHER_API_KEY", "")
    print(f"\n📍 OpenWeather:")
    weather_ok = False
    if not weather_key:
        print("  ⚠️  Không tìm thấy OPENWEATHER_API_KEY trong .env")
    else:
        display = f"{weather_key[:8]}...{weather_key[-4:]}"
        result = check_openweather(weather_key)
        if result["ok"]:
            print(
                f"  ✅ [{display}] "
                f"{result['temp']:.0f}°C | "
                f"Độ ẩm: {result['humidity']}% | "
                f"Mưa: {result['rain']:.1f}mm | "
                f"Tầm nhìn: {result['visibility']:.1f}km | "
                f"{result['desc']}"
            )
            weather_ok = True
        else:
            print(f"  ❌ [{display}] {result['error']}")

    # ── Tổng kết ──────────────────────────────────────────────────────────────
    print(f"\n{'═'*50}")
    tomtom_summary = f"{tomtom_ok}/{len(tomtom_keys)} TomTom {'✅' if tomtom_ok == len(tomtom_keys) and tomtom_keys else ('⚠️' if tomtom_ok > 0 else '❌')}"
    goong_summary  = f"Goong {'✅' if goong_ok else '❌'}"
    weather_summary= f"Weather {'✅' if weather_ok else '❌'}"
    print(f"📊 Kết quả: {tomtom_summary} | {goong_summary} | {weather_summary}")

    # Ước tính quota còn lại
    if tomtom_ok > 0:
        print(f"📈 Tổng quota TomTom/ngày: ~{tomtom_ok * 2500:,} req ({tomtom_ok} key × 2,500)")

    all_ok = tomtom_ok == len(tomtom_keys) and tomtom_keys and goong_ok and weather_ok
    print(f"{'✅ Tất cả key hoạt động tốt!' if all_ok else '⚠️  Một số key cần kiểm tra lại.'}")
    print(f"{'═'*50}\n")

    # Exit code 1 nếu có lỗi (dùng trong CI/CD)
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
