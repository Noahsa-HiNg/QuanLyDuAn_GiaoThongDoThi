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

    # Nếu loại phản ánh là kẹt xe (congested) hoặc tai nạn (accident), nhân bản sang community_reports
    if payload.report_type in ["congested", "accident"]:
        from models.community_report import CommunityReport
        from services.incident_detector import find_nearest_street

        street_id = payload.street_id
        if not street_id:
            street = find_nearest_street(db, payload.lat, payload.lon)
            if street:
                street_id = street.id

        severity = 2 # Mức độ mặc định: Vừa
        desc = payload.description or f"Báo cáo {payload.report_type} từ phản ánh trên bản đồ"

        comm_report = CommunityReport(
            latitude=payload.lat,
            longitude=payload.lon,
            severity=severity,
            description=desc,
            street_id=street_id
        )
        db.add(comm_report)
        db.commit()

    return new_feedback
