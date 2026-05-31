# backend/routers/emergency.py
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, status, Request, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.emergency_banner import EmergencyBanner
from models.user import User
from auth.dependencies import require_csgt
from schemas.emergency_banner import EmergencyBannerCreate, EmergencyBannerOut
from services.audit import audit_action

router = APIRouter(prefix="/system", tags=["System Announcement"])


@router.post(
    "/announcement",
    response_model=EmergencyBannerOut,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo bảng tin khẩn cấp toàn thành phố",
    description="Chỉ CSGT/Admin mới có quyền tạo bảng tin. Khi tạo mới, các banner cũ sẽ được chuyển về không hoạt động."
)
@audit_action(action="CREATE_EMERGENCY_BANNER", target_table="emergency_banners")
def create_emergency_alert(
    payload: EmergencyBannerCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt)
):
    # Đặt tất cả banner đang hoạt động khác về trạng thái tắt
    db.query(EmergencyBanner).filter(EmergencyBanner.is_active == True).update({"is_active": False})
    
    banner = EmergencyBanner(
        title=payload.title,
        content=payload.content,
        is_active=payload.is_active,
        expires_at=payload.expires_at
    )
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return banner


@router.get(
    "/announcement",
    response_model=Optional[EmergencyBannerOut],
    summary="Lấy bảng tin khẩn cấp đang hiệu lực",
    description="API Public trả về thông báo khẩn cấp hiện tại nếu có và chưa hết hạn."
)
def get_active_alert(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    banner = db.query(EmergencyBanner).filter(
        EmergencyBanner.is_active == True
    ).first()
    
    # Kiểm tra hạn dùng
    if banner and banner.expires_at and banner.expires_at < now:
        banner.is_active = False
        db.commit()
        return None
        
    return banner


@router.get(
    "/announcement/list",
    response_model=list[EmergencyBannerOut],
    summary="Danh sách tất cả thông báo khẩn cấp (CSGT/Admin)",
    description="Lấy danh sách tất cả thông báo khẩn cấp đã phát trong hệ thống."
)
def list_emergency_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt)
):
    return db.query(EmergencyBanner).order_by(EmergencyBanner.created_at.desc()).all()


@router.post(
    "/announcement/{alert_id}/deactivate",
    response_model=EmergencyBannerOut,
    summary="Hủy phát thông báo khẩn cấp (CSGT/Admin)",
    description="CSGT/Admin hủy kích hoạt một thông báo khẩn cấp trước khi nó tự động hết hạn."
)
@audit_action(action="DEACTIVATE_EMERGENCY_BANNER", target_table="emergency_banners")
def deactivate_emergency_alert(
    alert_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt)
):
    banner = db.query(EmergencyBanner).filter(EmergencyBanner.id == alert_id).first()
    if not banner:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông báo")
    banner.is_active = False
    db.commit()
    db.refresh(banner)
    return banner
