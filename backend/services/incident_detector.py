"""
services/incident_detector.py — Tự động phát hiện sự cố từ báo cáo cộng đồng
Gom cụm các báo cáo kẹt xe của người dân và tự động tạo Incident nếu đủ số lượng.
"""

import math
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.community_report import CommunityReport
from models.incident import Incident
from models.street import Street


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách giữa 2 điểm tọa độ GPS theo mét sử dụng công thức Haversine"""
    R = 6371000  # Bán kính Trái Đất theo mét
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_phi / 2) ** 2 + 
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def find_nearest_street(db: Session, lat: float, lng: float) -> Street:
    """Tìm tuyến đường gần nhất với tọa độ GPS thông qua truy vấn khoảng cách PostGIS"""
    try:
        point = func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326)
        street = db.query(Street).order_by(
            func.ST_Distance(Street.geometry, point)
        ).first()
        return street
    except Exception as e:
        print(f"[incident_detector] Error finding nearest street: {e}")
        return None


def get_reports_last_10min(db: Session):
    """Lấy các báo cáo chưa xử lý trong vòng 10 phút qua"""
    ten_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
    return db.query(CommunityReport).filter(
        CommunityReport.is_verified == False,
        CommunityReport.reported_at >= ten_mins_ago
    ).all()


def cluster_reports(reports, max_distance_m=500):
    """Gom cụm các báo cáo có khoảng cách dưới max_distance_m"""
    clusters = []
    visited = set()
    
    for r1 in reports:
        if r1.id in visited:
            continue
        cluster = [r1]
        visited.add(r1.id)
        
        for r2 in reports:
            if r2.id in visited:
                continue
            dist = haversine_distance(r1.latitude, r1.longitude, r2.latitude, r2.longitude)
            if dist <= max_distance_m:
                cluster.append(r2)
                visited.add(r2.id)
        
        clusters.append(cluster)
    return clusters


def detect_incidents(db: Session):
    """
    Tác vụ chạy ngầm được vô hiệu hóa tự động tạo sự cố.
    Sự cố từ cộng đồng hiện được quản lý và duyệt thủ công bởi lực lượng CSGT trên Dashboard.
    """
    print("[incident_detector] Cơ chế tự động tạo sự cố kẹt xe đã được chuyển sang cơ chế duyệt thủ công của CSGT.")
    return

