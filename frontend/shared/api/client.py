"""
shared/api/client.py — HTTP Client tập trung
v1.2 — Sprint 3: thêm get_predictions(), get_hourly_trend(), get_heatmap(), get_report()

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
    except Exception:
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
