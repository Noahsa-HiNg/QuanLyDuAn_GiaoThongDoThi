from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from redis_client import redis_client

router = APIRouter()


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))  # test DB
    redis_client.ping()            # test Redis
    return {"status": "ok", "db": "ok", "redis": "ok"}