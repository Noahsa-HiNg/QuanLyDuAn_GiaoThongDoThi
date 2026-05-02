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

from routers import healthy
from routers import streets
from routers import traffic
from routers import auth
log = logging.getLogger("main")


# ─────────────────────────────────────────────────────────────
# 1. LIFESPAN — khởi động / tắt APScheduler cùng với FastAPI
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle hook của FastAPI (thay thế @app.on_event deprecated).

    Startup : khởi động APScheduler với lịch cào mặc định.
    Shutdown: dừng APScheduler sạch sẽ, không chờ job đang chạy.
    """
    from services.scheduler import start_scheduler, stop_scheduler
    log.info("🚀 Server khởi động — bật APScheduler...")
    start_scheduler()
    yield                       # ← Server đang chạy
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
# 3. MOUNT ROUTERS
# ─────────────────────────────────────────────────────────────
app.include_router(healthy.router,  prefix="/api", tags=["Health"])
app.include_router(streets.router,  prefix="/api", tags=["Streets"])
app.include_router(traffic.router,  prefix="/api", tags=["Traffic"])
app.include_router(auth.router, prefix="/api", tags=["Auth"]) 
# TODO: Thêm router theo từng sprint
# app.include_router(predict.router,   prefix="/api", tags=["Predict"])
# app.include_router(route.router,     prefix="/api", tags=["Route"])
# app.include_router(incidents.router, prefix="/api", tags=["Incidents"])
# app.include_router(feedback.router,  prefix="/api", tags=["Feedback"])
# app.include_router(auth.router,      prefix="/api", tags=["Auth"])
# app.include_router(admin.router,     prefix="/api", tags=["Admin"])


# ─────────────────────────────────────────────────────────────
# 4. ROOT ENDPOINT — chuyển hướng về Swagger docs
# ─────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    """Redirect về trang Swagger UI khi truy cập root."""
    return RedirectResponse(url="/docs")
