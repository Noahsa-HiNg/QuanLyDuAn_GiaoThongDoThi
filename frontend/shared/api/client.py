"""
shared/api/client.py — HTTP Client tập trung
v1.1 — Fix: dùng json.loads(resp.content) để tránh lỗi encoding tiếng Việt

Tất cả giao tiếp với Backend FastAPI đều đi qua đây.
KHÔNG import trực tiếp httpx ở bất kỳ file khác.

Khi backend xong: bỏ comment mock, dùng httpx thật.
Khi chưa có backend: tự động fallback sang mock_data.
"""

import json
import httpx
import streamlit as st
from config import BACKEND_URL, TRAFFIC_CACHE_TTL, STREETS_CACHE_TTL, REQUEST_TIMEOUT
from shared.api.mock import get_mock_traffic, get_mock_streets


def _json_utf8(resp: httpx.Response):
    """Parse JSON response với encoding UTF-8 tường minh — tránh lỗi tiếng Việt."""
    return json.loads(resp.content.decode("utf-8"))


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
        # Fallback mock khi backend chưa sẵn
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
    # TODO Sprint 3
    pass


def get_predictions(street_id: int) -> dict:
    """GET /api/predictions/{street_id} — dự báo AI."""
    # TODO Sprint 3
    pass


def get_route(origin_id: int, dest_id: int) -> dict:
    """GET /api/route?origin=&dest= — tìm đường A*."""
    # TODO Sprint 4
    pass
