"""
routers/healthy.py — Health Check Endpoint

GET /api/health
    Kiểm tra trạng thái từng service (DB, Redis).
    Luôn trả về JSON — không bao giờ crash 500.

Response khi tất cả OK:
    {"status": "ok", "db": "ok", "redis": "ok"}

Response khi Redis lỗi:
    {"status": "degraded", "db": "ok", "redis": "error: Connection refused"}
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from redis_client import redis_client

router = APIRouter()


@router.get("/health", summary="Kiểm tra trạng thái hệ thống")
async def health_check(db: Session = Depends(get_db)):
    """
    Kiểm tra kết nối đến PostgreSQL và Redis.

    - **status**: "ok" nếu tất cả hoạt động, "degraded" nếu có service lỗi
    - **db**: "ok" hoặc mô tả lỗi
    - **redis**: "ok" hoặc mô tả lỗi
    """
    # ── Kiểm tra PostgreSQL ─────────────────────────────────────────────
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    # ── Kiểm tra Redis ──────────────────────────────────────────────────
    redis_status = "ok"
    try:
        redis_client.ping()
    except Exception as e:
        redis_status = f"error: {e}"

    # ── Tổng hợp trạng thái ─────────────────────────────────────────────
    overall = "ok" if (db_status == "ok" and redis_status == "ok") else "degraded"

    return {
        "status": overall,
        "db"    : db_status,
        "redis" : redis_status,
    }