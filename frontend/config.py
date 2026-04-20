"""
config.py — Cấu hình toàn bộ Frontend App

Đây là nơi DUY NHẤT chứa:
  - BACKEND_URL: URL backend FastAPI
  - Hằng số màu sắc, timeout, ...
  - Thông tin app (tên, version)

Thay đổi môi trường (dev → docker → production):
  Chỉ cần đổi biến môi trường BACKEND_URL, không cần sửa code.
"""

import os

# ── Backend ───────────────────────────────────────────────────────────
# Docker network: service name = "backend"
# Local dev:      localhost:8000
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://backend:8000")

# ── App Info ──────────────────────────────────────────────────────────
APP_TITLE    = "Giao thông Đà Nẵng"
APP_ICON     = "🚦"
APP_VERSION  = "1.0.0"

# ── Map defaults ──────────────────────────────────────────────────────
MAP_CENTER_LAT = 16.0544   # Trung tâm Đà Nẵng
MAP_CENTER_LON = 108.2022
MAP_ZOOM       = 12

# ── Auto-refresh ──────────────────────────────────────────────────────
REFRESH_INTERVAL_MS = 60_000   # 60 giây

# ── Cache TTL ─────────────────────────────────────────────────────────
TRAFFIC_CACHE_TTL = 55    # giây — dưới refresh interval
STREETS_CACHE_TTL = 300   # 5 phút — geometry ít thay đổi

# ── HTTP ──────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 10.0    # giây
