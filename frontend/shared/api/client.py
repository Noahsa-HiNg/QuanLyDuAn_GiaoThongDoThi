"""
shared/api/client.py — HTTP Client tập trung
v1.3 — Sprint 3: thêm get_weather_current() cho widget thời tiết sidebar

Tất cả giao tiếp với Backend FastAPI đều đi qua đây.
KHÔNG import trực tiếp httpx ở bất kỳ file khác.

Khi backend xong: bỏ comment mock, dùng httpx thật.
Khi chưa có backend: tự động fallback sang mock_data.
"""

import json
import httpx
import streamlit as st
from config import BACKEND_URL, TRAFFIC_CACHE_TTL, STREETS_CACHE_TTL, REQUEST_TIMEOUT
from shared.api.mock import (
    get_mock_traffic, get_mock_streets,
    get_mock_predictions, get_mock_hourly_trend,
    get_mock_heatmap, get_mock_report,
)


def _json_utf8(resp: httpx.Response):
    """Parse JSON response với encoding UTF-8 tường minh — tránh lỗi tiếng Việt."""
    return json.loads(resp.content.decode("utf-8"))


# ── Sprint 1 & 2 ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=TRAFFIC_CACHE_TTL)
def get_traffic_current(district_id: int | None = None) -> dict:
    """GET /api/traffic/current — traffic theo mức ùn tắc hiện tại."""
    try:
        params = {}
        if district_id:
            params["district_id"] = district_id
        resp = httpx.get(
            f"{BACKEND_URL}/api/traffic/current",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception as e:
        print(f"ERROR calling get_traffic_current: {e}")
        return get_mock_traffic(district_id)


@st.cache_data(ttl=STREETS_CACHE_TTL)
def get_streets(district_id: int | None = None, page_size: int = 100) -> list:
    """GET /api/streets — danh sách đường + geometry."""
    try:
        params = {"page_size": page_size}
        if district_id:
            params["district_id"] = district_id
        resp = httpx.get(
            f"{BACKEND_URL}/api/streets",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp).get("data", [])
    except Exception:
        return get_mock_streets()


def post_login(email: str, password: str) -> dict:
    """POST /api/auth/login — trả về access_token."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return {}


def get_traffic_csv(date: str) -> bytes | None:
    """GET /api/export/traffic?date=YYYY-MM-DD — trả về nội dung file CSV."""
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/export/traffic",
            params={"date": date},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        print(f"ERROR calling get_traffic_csv: {e}")
        return None


# ── Sprint 3 — SCRUM 36–39 ────────────────────────────────────────────────────

@st.cache_data(ttl=300)   # 5 phút — predictions ít thay đổi trong ngắn hạn
def get_predictions() -> list:
    """
    GET /api/predict/30min — dự báo AI congestion 30 phút tới cho tất cả đường.
    SCRUM-36. Backend: SCRUM-32 (NT đang làm).
    Fallback: mock data với pattern giờ cao điểm thực tế.
    """
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/predict/30min",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return get_mock_predictions()


@st.cache_data(ttl=600)   # 10 phút — trend ít thay đổi
def get_hourly_trend(days: int = 7) -> list:
    """
    GET /api/stats/hourly-trend?days=N — xu hướng congestion theo giờ trong N ngày.
    SCRUM-37. Backend: SCRUM-35 (Hiếu đang làm).
    """
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/stats/hourly-trend",
            params={"days": days},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return get_mock_hourly_trend(days)


@st.cache_data(ttl=1800)  # 30 phút — heatmap từ dữ liệu lịch sử
def get_heatmap_data() -> list:
    """
    GET /api/stats/heatmap — heatmap congestion theo giờ × ngày trong tuần.
    SCRUM-38. Backend: SCRUM-35 (Hiếu đang làm).
    """
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/stats/heatmap",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return get_mock_heatmap()


@st.cache_data(ttl=300)
def get_report() -> dict:
    """
    GET /api/stats/report — báo cáo tổng hợp giao thông toàn thành phố.
    SCRUM-39. Backend: SCRUM-35 (Hiếu đang làm).
    """
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/stats/report",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return get_mock_report()


def get_route(origin_id: int, dest_id: int) -> dict:
    """GET /api/route?origin=&dest= — tìm đường A*."""
    # TODO Sprint 4
    pass


# ── Sprint 3: Weather ─────────────────────────────────────────────────────────

@st.cache_data(ttl=300)  # cache 5 phút — weather không đổi quá nhanh
def get_weather_current() -> dict:
    """
    GET /api/weather/current — thời tiết Đà Nẵng hiện tại.
    Trả về dict: temperature, humidity, wind_speed, rain_1h_mm,
                 is_raining, visibility_km, weather_group, weather_id.
    Fallback về {} nếu backend không khả dụng.
    """
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/weather/current",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return {}


# ── Sprint 4 — Admin API (yêu cầu Bearer token) ──────────────────────────────

def _auth_headers(token: str) -> dict:
    """Tạo Authorization header từ JWT token."""
    return {"Authorization": f"Bearer {token}"}


# ── User management ───────────────────────────────────────────────────────────

def admin_get_users(token: str) -> list:
    """GET /api/users — danh sách tất cả tài khoản (Admin only)."""
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/users",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return []


def admin_create_user(token: str, email: str, password: str,
                      full_name: str, role: str) -> dict:
    """POST /api/users — tạo tài khoản mới (Admin only)."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/api/users",
            headers=_auth_headers(token),
            json={"email": email, "password": password,
                  "full_name": full_name, "role": role},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return {"ok": True, "data": _json_utf8(resp)}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"ok": False, "error": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def admin_lock_user(token: str, user_id: int) -> dict:
    """POST /api/users/{id}/lock — khóa tài khoản (Admin only)."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/api/users/{user_id}/lock",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"ok": False, "error": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def admin_unlock_user(token: str, user_id: int) -> dict:
    """POST /api/users/{id}/unlock — mở khóa tài khoản (Admin only)."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/api/users/{user_id}/unlock",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"ok": False, "error": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def admin_deactivate_user(token: str, user_id: int) -> dict:
    """DELETE /api/users/{id} — vô hiệu hóa tài khoản (Admin only)."""
    try:
        resp = httpx.delete(
            f"{BACKEND_URL}/api/users/{user_id}",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"ok": False, "error": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ── Scheduler management ──────────────────────────────────────────────────────

def admin_get_schedule_state(token: str) -> dict:
    """GET /api/traffic/schedule/state — trạng thái APScheduler."""
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/traffic/schedule/state",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return {}


def admin_get_schedule_jobs(token: str) -> list:
    """GET /api/traffic/schedule/jobs — danh sách jobs đang chạy."""
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/traffic/schedule/jobs",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp).get("jobs", [])
    except Exception:
        return []


def admin_pause_schedule(token: str) -> dict:
    """POST /api/traffic/schedule/pause — tạm dừng scheduler."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/api/traffic/schedule/pause",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return {"ok": True, "data": _json_utf8(resp)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def admin_resume_schedule(token: str) -> dict:
    """POST /api/traffic/schedule/resume — tiếp tục scheduler."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/api/traffic/schedule/resume",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return {"ok": True, "data": _json_utf8(resp)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def admin_crawl_now(token: str) -> dict:
    """POST /api/traffic/crawl — kích hoạt cào thủ công ngay."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/api/traffic/crawl",
            headers=_auth_headers(token),
            timeout=60,   # crawl có thể mất thời gian
        )
        resp.raise_for_status()
        return {"ok": True, "data": _json_utf8(resp)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def admin_get_crawl_status(token: str) -> dict:
    """GET /api/traffic/crawl/status — trạng thái lần cào gần nhất."""
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/traffic/crawl/status",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return {}


# ── Sprint 5 ──────────────────────────────────────────────────────────────────

def get_route_api(
    from_lat: float,
    from_lng: float,
    to_lat: float,
    to_lng: float,
    mode: str = "shortest",
) -> dict:
    """GET /api/routes — Tìm đường A* (ngắn nhất hoặc nhanh nhất)."""
    try:
        resp = httpx.get(
            f"{BACKEND_URL}/api/routes",
            params={
                "from_lat": from_lat,
                "from_lng": from_lng,
                "to_lat":   to_lat,
                "to_lng":   to_lng,
                "mode":     mode,
            },
            timeout=30,   # A* có thể mất vài giây lần đầu build graph
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except httpx.HTTPStatusError as e:
        # Lấy message tiếng Việt từ FastAPI detail thay vì raw HTTP error
        try:
            detail = e.response.json().get("detail", "Không tìm được đường.")
        except Exception:
            detail = str(e)
        return {"error": detail}
    except Exception as e:
        return {"error": str(e)}


def get_street_midpoints() -> list[dict]:
    """GET /api/streets/midpoints — Lấy midpoint tọa độ từ MANUAL_COORDS."""
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/streets/midpoints", timeout=10)
        resp.raise_for_status()
        return _json_utf8(resp).get("streets", [])
    except Exception:
        return []


def get_streets_geometry() -> dict:
    """GET /api/traffic/streets-geometry — Geometry tĩnh (cache Redis 1h).
    Chỉ cần gọi 1 lần rồi lưu vào st.session_state.
    """
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/traffic/streets-geometry", timeout=30)
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return {"streets": [], "total": 0}


def get_traffic_state() -> dict:
    """GET /api/traffic/state — Trạng thái giao thông nhẹ (~1MB, không có geometry).
    Poll mỗi 60s — không cần tải lại geometry.
    """
    try:
        resp = httpx.get(f"{BACKEND_URL}/api/traffic/state", timeout=15)
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception:
        return {"streets": [], "total": 0, "data_as_of": None}


# ── Sprint 4 — Incidents CRUD (yêu cầu Bearer token CSGT/Admin) ──────────────

def get_incidents(
    token: str,
    is_active: bool | None = None,
    incident_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list:
    """GET /api/incidents — danh sách sự cố/lô cốt với filter."""
    try:
        params: dict = {"page": page, "page_size": page_size}
        if is_active is not None:
            params["is_active"] = str(is_active).lower()
        if incident_type:
            params["type"] = incident_type
        if status:
            params["status"] = status
        resp = httpx.get(
            f"{BACKEND_URL}/api/incidents",
            headers=_auth_headers(token),
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return _json_utf8(resp)
    except Exception as e:
        print(f"ERROR get_incidents: {e}")
        return []


def create_incident(token: str, data: dict) -> dict:
    """POST /api/incidents — tạo sự cố mới (CSGT/Admin)."""
    try:
        resp = httpx.post(
            f"{BACKEND_URL}/api/incidents",
            headers=_auth_headers(token),
            json=data,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return {"ok": True, "data": _json_utf8(resp)}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"ok": False, "error": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def update_incident_status(token: str, incident_id: int, new_status: str) -> dict:
    """PUT /api/incidents/{id} — cập nhật trạng thái sự cố."""
    try:
        resp = httpx.put(
            f"{BACKEND_URL}/api/incidents/{incident_id}",
            headers=_auth_headers(token),
            json={"status": new_status},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"ok": False, "error": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def delete_incident(token: str, incident_id: int) -> dict:
    """DELETE /api/incidents/{id} — xóa vĩnh viễn (Admin only)."""
    try:
        resp = httpx.delete(
            f"{BACKEND_URL}/api/incidents/{incident_id}",
            headers=_auth_headers(token),
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return {"ok": True}
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"ok": False, "error": detail}
    except Exception as e:
        return {"ok": False, "error": str(e)}
