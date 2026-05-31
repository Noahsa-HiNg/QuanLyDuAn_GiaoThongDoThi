# backend/routers/community.py
from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy.orm import Session

from database import get_db
from models.community_report import CommunityReport
from models.incident import Incident
from auth.dependencies import get_current_user
from services.audit import audit_action
from schemas.community_report import CommunityReportCreate, CommunityReportOut
from services.incident_detector import find_nearest_street

router = APIRouter(prefix="/community", tags=["Community"])


@router.post(
    "/report",
    response_model=CommunityReportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Người dân gửi báo cáo kẹt xe",
    description="Cho phép bất kỳ người dùng nào gửi báo cáo sự cố/kẹt xe theo tọa độ GPS hiện tại."
)
def create_report(payload: CommunityReportCreate, db: Session = Depends(get_db)):
    # Tìm tuyến đường gần nhất dựa trên GPS gửi lên
    street = find_nearest_street(db, payload.latitude, payload.longitude)
    street_id = street.id if street else None
    
    report = CommunityReport(
        latitude=payload.latitude,
        longitude=payload.longitude,
        severity=payload.severity,
        description=payload.description,
        street_id=street_id
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get(
    "/reports",
    response_model=List[CommunityReportOut],
    summary="Lấy danh sách các báo cáo kẹt xe gần đây",
    description="Trả về các báo cáo kẹt xe từ cộng đồng trong vòng 30 phút qua để hiển thị lên bản đồ."
)
def get_reports(db: Session = Depends(get_db)):
    half_hour_ago = datetime.now(timezone.utc) - timedelta(minutes=30)
    reports = db.query(CommunityReport).filter(
        CommunityReport.reported_at >= half_hour_ago
    ).all()
    return reports


@router.post(
    "/report/{report_id}/verify",
    summary="CSGT duyệt/xác minh báo cáo kẹt xe",
    description="Xác minh một báo cáo từ người dân, cập nhật trạng thái đã duyệt và tự động tạo Incident."
)
@audit_action(action="VERIFY_COMMUNITY_REPORT", target_table="community_reports")
def verify_report(report_id: int, request: Request, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    # Check if user is CSGT or Admin
    if current_user.role not in ["csgt", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có lực lượng CSGT hoặc Admin mới được phép xác minh báo cáo."
        )

    # Find report
    report = db.query(CommunityReport).filter(CommunityReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo cáo kẹt xe."
        )

    if report.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Báo cáo này đã được xác minh trước đó."
        )

    # Mark as verified
    report.is_verified = True

    # Find nearest street
    street = find_nearest_street(db, report.latitude, report.longitude)
    if street:
        report.street_id = street.id

    # Create Incident
    new_incident = Incident(
        street_id=report.street_id,
        type="community",
        start_time=datetime.now(timezone.utc),
        severity=report.severity,
        description=f"Sự cố được CSGT xác minh từ báo cáo của người dân: {report.description or 'Kẹt xe'}",
        status="active",
        is_active=True,
        latitude=report.latitude,
        longitude=report.longitude
    )
    db.add(new_incident)
    db.commit()
    db.refresh(report)
    return {"message": "Duyệt kẹt xe thành công", "report_id": report.id}


@router.post(
    "/reports/verify-batch",
    summary="CSGT duyệt hàng loạt báo cáo kẹt xe (theo cụm)",
    description="Duyệt đồng thời nhiều báo cáo kẹt xe từ cộng đồng và tự động tạo một Incident chung."
)
@audit_action(action="VERIFY_COMMUNITY_REPORTS_BATCH", target_table="community_reports")
def verify_reports_batch(
    report_ids: List[int],
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # Check if user is CSGT or Admin
    if current_user.role not in ["csgt", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ có lực lượng CSGT hoặc Admin mới được phép xác minh báo cáo."
        )

    # Fetch reports
    reports = db.query(CommunityReport).filter(
        CommunityReport.id.in_(report_ids),
        CommunityReport.is_verified == False
    ).all()

    if not reports:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy báo cáo kẹt xe chưa xác minh nào trong danh sách gửi lên."
        )

    # Compute average coordinates
    avg_lat = sum(r.latitude for r in reports) / len(reports)
    avg_lng = sum(r.longitude for r in reports) / len(reports)

    # Find nearest street
    street = find_nearest_street(db, avg_lat, avg_lng)
    street_id = street.id if street else None

    # Mark as verified
    for r in reports:
        r.is_verified = True
        r.street_id = street_id

    # Create Incident
    new_incident = Incident(
        street_id=street_id,
        type="community",
        start_time=datetime.now(timezone.utc),
        severity=2,  # Mức độ Trung bình cho cụm báo cáo
        description=f"Sự cố được CSGT xác minh từ cụm {len(reports)} báo cáo của người dân.",
        status="active",
        is_active=True,
        latitude=avg_lat,
        longitude=avg_lng
    )
    db.add(new_incident)
    db.commit()

    return {"message": "Duyệt cụm kẹt xe thành công", "verified_count": len(reports)}

