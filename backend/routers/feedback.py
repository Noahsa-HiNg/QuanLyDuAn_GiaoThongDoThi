# backend/routers/feedback.py
"""
routers/feedback.py — API tiếp nhận phản ánh kẹt xe/sự cố từ người dân (Public - Không cần đăng nhập)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.feedback import Feedback
from schemas.feedback import FeedbackCreate, FeedbackOut

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post(
    "",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
    summary="Gửi phản ánh kẹt xe/sự cố mới (Public)",
    description="Người dân gửi phản ánh kẹt xe, tai nạn hoặc báo thông thoáng tại vị trí cụ thể trên bản đồ.",
)
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    new_feedback = Feedback(
        street_id=payload.street_id,
        lat=payload.lat,
        lon=payload.lon,
        report_type=payload.report_type,
        description=payload.description,
    )
    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)
    return new_feedback
