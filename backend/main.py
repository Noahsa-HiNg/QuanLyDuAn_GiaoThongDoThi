"""
main.py — FastAPI Application Entry Point

Cách tổ chức:
  - Tạo instance FastAPI với metadata (title, version, docs)
  - Mount từng router theo domain (healthy, traffic, predict, ...)
  - Tất cả route đều có prefix /api
  - APScheduler khởi động khi server start, tắt khi server stop

Chạy local (bên ngoài Docker):
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Chạy qua Docker Compose:
    docker compose up backend
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

from routers import healthy
from routers import streets
from routers import traffic
from routers import auth
from routers import users
from routers import predict
from routers import route
from routers import stats
from routers import incidents
log = logging.getLogger("main")


# ─────────────────────────────────────────────────────────────
# 1. LIFESPAN — khởi động / tắt APScheduler cùng với FastAPI
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle hook của FastAPI (thay thế @app.on_event deprecated).

    Startup : Khởi động APScheduler nếu ENABLE_CRAWL=true (mặc định).
              Tự động tạo các DB index cần thiết.
    Shutdown: Dừng APScheduler sạch sẽ, không chờ job đang chạy.

    Để TẪT cào (đồng đội không muốn cào):
        Thêm vào .env:  ENABLE_CRAWL=false
    """
    import os
    from services.scheduler import start_scheduler, stop_scheduler
    from database import engine
    from sqlalchemy import text as _text

    # ── Tạo DB index hiệu năng (chỉ chạy 1 lần, idempotent) ─────────────
    try:
        with engine.connect() as conn:
            conn.execute(_text("""
                CREATE INDEX IF NOT EXISTS ix_traffic_data_street_ts
                ON traffic_data (street_id, timestamp DESC)
            """))
            conn.execute(_text("""
                CREATE INDEX IF NOT EXISTS ix_incidents_street_active
                ON incidents (street_id, is_active)
                WHERE is_active = TRUE
            """))
            conn.commit()
        log.info("✅ DB indexes verified/created")
    except Exception as e:
        log.warning(f"⚠️ Không tạo được DB index (có thể chưa có bảng): {e}")

    enable_crawl = os.getenv("ENABLE_CRAWL", "true").strip().lower()

    if enable_crawl == "true":
        log.info("🚀 Server khởi động — bật APScheduler (ENABLE_CRAWL=true)...")
        start_scheduler()
    else:
        log.warning("⚠️  Cào dữ liệu đã TẪT (ENABLE_CRAWL=false) — server chạy bình thường nhưng không tự động cào")

    yield  # ← Server đang chạy

    if enable_crawl == "true":
        log.info("🛑 Server tắt — dừng APScheduler...")
        stop_scheduler()



# ─────────────────────────────────────────────────────────────
# 2. KHỞI TẠO ỨNG DỤNG FASTAPI
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "AI Dự báo Giao thông Đà Nẵng",
    description = "Backend API cho hệ thống dự báo giao thông đô thị Đà Nẵng bằng AI.",
    version     = "0.1.0",
    docs_url    = "/docs",      # Swagger UI tại http://localhost:8000/docs
    redoc_url   = "/redoc",     # ReDoc tại http://localhost:8000/redoc
    lifespan    = lifespan,     # ← APScheduler lifecycle
)

# ─────────────────────────────────────────────────────────────
# 3. CORS — Cho phép frontend và test tool gọi API
# ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Dev: cho phép mọi origin (file://, localhost, v.v.)
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# 3. MOUNT ROUTERS
# ─────────────────────────────────────────────────────────────
app.include_router(healthy.router,  prefix="/api", tags=["Health"])
app.include_router(streets.router,  prefix="/api", tags=["Streets"])
app.include_router(traffic.router,  prefix="/api", tags=["Traffic"])
app.include_router(auth.router,     prefix="/api", tags=["Auth"])
app.include_router(users.router,    prefix="/api", tags=["Users"])
app.include_router(predict.router,  prefix="/api", tags=["Predict"])
app.include_router(route.router,     prefix="/api", tags=["Route"])
app.include_router(stats.router,     prefix="/api", tags=["Stats"])
app.include_router(incidents.router, prefix="/api", tags=["Incidents"])
# TODO: Thêm router theo từng sprint
# app.include_router(feedback.router, prefix="/api", tags=["Feedback"])
# app.include_router(admin.router,    prefix="/api", tags=["Admin"])


# ─────────────────────────────────────────────────────────────
# 4. ROOT ENDPOINT — chuyển hướng về Swagger docs
# ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    """Redirect về trang Swagger UI khi truy cập root."""
    return RedirectResponse(url="/docs")
