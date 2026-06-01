from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from database import get_db
from schemas.stats import (
    TopCongestedStreetResponse,
    CongestedRankingResponse,
    DistrictCongestionStatsResponse,
    HourlyTrendPoint,
    IncidentStatsResponse,
    FeedbackStatsResponse,
    TopReportedStreet,
    TZ_DANANG,
    CongestedStreet,
    StatsReport,
    HeatmapItem
)
from auth.dependencies import require_csgt
from models.user import User
from models.incident import Incident
from models.feedback import Feedback

router = APIRouter(prefix="/stats", tags=["Stats"])

CONGESTION_LABEL = {
    0: "Thông thoáng",
    1: "Chậm",
    2: "Kẹt xe",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. GET /api/stats/top-congested — Tuyến đường kẹt xe nhất thời gian thực
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/top-congested",
    response_model=List[TopCongestedStreetResponse],
    summary="Top các tuyến đường kẹt xe nhất",
    description="Trả về danh sách các tuyến đường đang kẹt xe nhất dựa trên dữ liệu giao thông mới nhất.",
)
def get_top_congested_streets(
    limit: int = Query(10, ge=1, le=100, description="Số lượng tuyến đường giới hạn"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    # Bước 1: Lấy timestamp mới nhất bằng cách quét ngược từ index PK (cực nhanh <1ms)
    latest_ts_row = db.execute(
        text("SELECT timestamp FROM traffic_data ORDER BY id DESC LIMIT 1")
    ).fetchone()

    if not latest_ts_row or not latest_ts_row[0]:
        return []

    latest_timestamp = latest_ts_row[0]

    # Bước 2: Truy vấn top các đường kẹt nhất tại timestamp mới nhất
    # Sắp xếp theo:
    # 1. Mức kẹt giảm dần (Đỏ = 2 -> Vàng = 1)
    # 2. Tỷ lệ tốc độ thực tế/tốc độ thiết kế tăng dần (càng nhỏ = kẹt càng nặng)
    query = text("""
        SELECT td.street_id,
               s.name AS street_name,
               d.name AS district_name,
               td.avg_speed,
               s.max_speed,
               td.congestion_level,
               (td.avg_speed / COALESCE(NULLIF(s.max_speed, 0), 50)) AS ratio,
               td.timestamp
        FROM traffic_data td
        JOIN streets s ON td.street_id = s.id
        LEFT JOIN districts d ON s.district_id = d.id
        WHERE td.timestamp = :latest_timestamp
          AND td.congestion_level IS NOT NULL
        ORDER BY td.congestion_level DESC, ratio ASC
        LIMIT :limit
    """)

    rows = db.execute(
        query,
        {"latest_timestamp": latest_timestamp, "limit": limit}
    ).fetchall()

    results = []
    for row in rows:
        ts_vn = None
        if row.timestamp:
            ts_local = row.timestamp.astimezone(TZ_DANANG)
            ts_vn = ts_local.strftime("%Y-%m-%d %H:%M:%S +07:00")

        results.append(TopCongestedStreetResponse(
            street_id=row.street_id,
            street_name=row.street_name,
            district_name=row.district_name,
            avg_speed=row.avg_speed,
            max_speed=row.max_speed,
            congestion_level=row.congestion_level,
            congestion_label=CONGESTION_LABEL.get(row.congestion_level, "Chưa rõ"),
            ratio=round(row.ratio, 3) if row.ratio is not None else None,
            timestamp=row.timestamp,
            timestamp_vn=ts_vn,
        ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 2. GET /api/stats/congested-ranking — Xếp hạng đường kẹt xe lịch sử
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/congested-ranking",
    response_model=List[CongestedRankingResponse],
    summary="Xếp hạng tuyến đường kẹt xe lịch sử (ngày/tuần/tháng)",
    description="Trả về danh sách các tuyến đường bị kẹt xe nhiều nhất trong khoảng thời gian (1 ngày, 1 tuần, hoặc 1 tháng).",
)
def get_congested_ranking(
    period: str = Query("1d", regex="^(1d|1w|1m)$", description="Khoảng thời gian: 1d (24h), 1w (7 ngày), 1m (30 ngày)"),
    limit: int = Query(10, ge=1, le=100, description="Giới hạn số lượng tuyến đường trả về"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    now = datetime.now(timezone.utc)
    if period == "1d":
        start_time = now - timedelta(days=1)
    elif period == "1w":
        start_time = now - timedelta(days=7)
    else:  # "1m"
        start_time = now - timedelta(days=30)

    # Phân tích độ tắc nghẽn dựa trên:
    # 1. Congestion Rate (Tỷ lệ số lần kẹt đỏ / tổng số lần đo) giảm dần
    # 2. Speed Ratio trung bình (tốc độ thực tế / tốc độ thiết kế) tăng dần
    query = text("""
        SELECT td.street_id,
               s.name AS street_name,
               d.name AS district_name,
               COUNT(td.id) AS total_records,
               SUM(CASE WHEN td.congestion_level = 2 THEN 1 ELSE 0 END) AS congested_records,
               (SUM(CASE WHEN td.congestion_level = 2 THEN 1.0 ELSE 0.0 END) / COUNT(td.id)) AS congestion_rate,
               AVG(td.avg_speed) AS avg_speed,
               s.max_speed,
               AVG(td.avg_speed / COALESCE(NULLIF(s.max_speed, 0), 50)) AS avg_ratio
        FROM traffic_data td
        JOIN streets s ON td.street_id = s.id
        LEFT JOIN districts d ON s.district_id = d.id
        WHERE td.timestamp >= :start_time
          AND td.congestion_level IS NOT NULL
        GROUP BY td.street_id, s.name, d.name, s.max_speed
        ORDER BY congestion_rate DESC, avg_ratio ASC
        LIMIT :limit
    """)

    rows = db.execute(query, {"start_time": start_time, "limit": limit}).fetchall()

    results = []
    for row in rows:
        results.append(CongestedRankingResponse(
            street_id=row.street_id,
            street_name=row.street_name,
            district_name=row.district_name,
            total_records=row.total_records,
            congested_records=row.congested_records,
            congestion_rate=round(row.congestion_rate, 4),
            avg_speed=round(row.avg_speed, 2) if row.avg_speed is not None else None,
            max_speed=row.max_speed,
            avg_ratio=round(row.avg_ratio, 3) if row.avg_ratio is not None else None,
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 3. GET /api/stats/congested-by-district — Thống kê kẹt xe theo quận
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/congested-by-district",
    response_model=List[DistrictCongestionStatsResponse],
    summary="Thống kê số lượng đường kẹt theo quận",
    description="Thống kê số lượng các đoạn đường bị kẹt xe và tỷ lệ kẹt trung bình theo từng quận/huyện.",
)
def get_congested_by_district(
    period: str = Query("realtime", regex="^(realtime|1d|1w|1m)$", description="Khoảng thời gian: realtime (hiện tại), 1d, 1w, 1m"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    if period == "realtime":
        latest_ts_row = db.execute(
            text("SELECT timestamp FROM traffic_data ORDER BY id DESC LIMIT 1")
        ).fetchone()

        if not latest_ts_row or not latest_ts_row[0]:
            return []
        latest_timestamp = latest_ts_row[0]

        query = text("""
            SELECT d.id AS district_id,
                   d.name AS district_name,
                   COUNT(DISTINCT s.id) AS total_streets,
                   SUM(CASE WHEN td.congestion_level = 2 THEN 1 ELSE 0 END) AS congested_occurrences,
                   (SUM(CASE WHEN td.congestion_level = 2 THEN 1.0 ELSE 0.0 END) / COALESCE(NULLIF(COUNT(td.id), 0), 1)) AS avg_congestion_rate
            FROM districts d
            LEFT JOIN streets s ON s.district_id = d.id
            LEFT JOIN traffic_data td ON td.street_id = s.id AND td.timestamp = :latest_timestamp
            GROUP BY d.id, d.name
            ORDER BY congested_occurrences DESC
        """)
        rows = db.execute(query, {"latest_timestamp": latest_timestamp}).fetchall()
    else:
        now = datetime.now(timezone.utc)
        if period == "1d":
            start_time = now - timedelta(days=1)
        elif period == "1w":
            start_time = now - timedelta(days=7)
        else:  # "1m"
            start_time = now - timedelta(days=30)

        query = text("""
            SELECT d.id AS district_id,
                   d.name AS district_name,
                   COUNT(DISTINCT s.id) AS total_streets,
                   SUM(CASE WHEN td.congestion_level = 2 THEN 1 ELSE 0 END) AS congested_occurrences,
                   (SUM(CASE WHEN td.congestion_level = 2 THEN 1.0 ELSE 0.0 END) / COALESCE(NULLIF(COUNT(td.id), 0), 1)) AS avg_congestion_rate
            FROM districts d
            LEFT JOIN streets s ON s.district_id = d.id
            LEFT JOIN traffic_data td ON td.street_id = s.id AND td.timestamp >= :start_time
            GROUP BY d.id, d.name
            ORDER BY avg_congestion_rate DESC
        """)
        rows = db.execute(query, {"start_time": start_time}).fetchall()

    results = []
    for row in rows:
        results.append(DistrictCongestionStatsResponse(
            district_id=row.district_id,
            district_name=row.district_name,
            total_streets=row.total_streets,
            congested_occurrences=row.congested_occurrences or 0,
            avg_congestion_rate=round(row.avg_congestion_rate or 0.0, 4),
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 4. GET /api/stats/hourly-trend — Diễn biến kẹt xe theo giờ
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/hourly-trend",
    response_model=List[HourlyTrendPoint],
    summary="Diễn biến kẹt xe theo giờ trong ngày",
    description="Trả về tốc độ trung bình, số điểm kẹt trung bình, và tỷ lệ kẹt xe trung bình theo từng giờ.",
)
def get_hourly_trend(
    days: int = Query(7, description="Số ngày gần nhất cần thống kê"),
    date_str: str = Query(None, description="Ngày cụ thể cần thống kê (định dạng YYYY-MM-DD), nếu dùng sẽ ghi đè tham số days"),
    district_id: Optional[int] = Query(None, description="Lọc theo quận (tùy chọn)"),
    db: Session = Depends(get_db),
):
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            start_time = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=TZ_DANANG)
            end_time = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=TZ_DANANG)
        except ValueError:
            raise HTTPException(status_code=400, detail="Định dạng ngày không hợp lệ, yêu cầu YYYY-MM-DD")
    elif days == 0:
        # "Hiện tại" -> từ 0h hôm nay đến giờ hiện tại
        now_local = datetime.now(TZ_DANANG)
        start_time = datetime.combine(now_local.date(), datetime.min.time()).replace(tzinfo=TZ_DANANG)
        end_time = now_local
    else:
        # past 'days' days
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=days)
        end_time = now

    query_str = """
        SELECT EXTRACT(HOUR FROM td.timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh')::int AS hr,
               AVG(td.avg_speed) AS avg_speed,
               (COUNT(CASE WHEN td.congestion_level = 2 THEN 1 END) / 12.0) AS avg_congested_count,
               (COUNT(CASE WHEN td.congestion_level = 2 THEN 1 WHEN td.congestion_level = 1 THEN 0.5 END)::float / NULLIF(COUNT(td.id), 0)) * 100.0 AS avg_congestion_pct
        FROM traffic_data td
        JOIN streets s ON td.street_id = s.id
        WHERE td.timestamp >= :start_time AND td.timestamp <= :end_time
          AND td.congestion_level IS NOT NULL
    """
    
    params = {"start_time": start_time, "end_time": end_time}
    if district_id is not None:
        query_str += " AND s.district_id = :district_id"
        params["district_id"] = district_id
        
    query_str += """
        GROUP BY hr
        ORDER BY hr
    """
    
    rows = db.execute(text(query_str), params).fetchall()

    trend_dict = {h: {"avg_speed": 0.0, "avg_congested_count": 0.0, "avg_congestion_pct": 0.0} for h in range(24)}
    
    for row in rows:
        h = row.hr
        if h in trend_dict:
            trend_dict[h] = {
                "avg_speed": round(row.avg_speed, 2) if row.avg_speed is not None else 0.0,
                "avg_congested_count": round(row.avg_congested_count, 1) if row.avg_congested_count is not None else 0.0,
                "avg_congestion_pct": round(row.avg_congestion_pct, 2) if row.avg_congestion_pct is not None else 0.0
            }
            
    results = []
    max_hour = 23
    if date_str is None and days == 0:
        max_hour = datetime.now(TZ_DANANG).hour

    for h in range(max_hour + 1):
        results.append(HourlyTrendPoint(
            hour=h,
            avg_speed=trend_dict[h]["avg_speed"],
            avg_congested_count=trend_dict[h]["avg_congested_count"],
            avg_congestion_pct=trend_dict[h]["avg_congestion_pct"]
        ))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 4b. GET /api/stats/report — Báo cáo tình trạng giao thông tổng quan
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/report",
    response_model=StatsReport,
    summary="Báo cáo tình trạng giao thông tổng quan",
    description="Trả về các chỉ số KPI giao thông hiện tại và danh sách top 5 tuyến đường kẹt nhất.",
)
def get_stats_report(db: Session = Depends(get_db)):
    latest_ts_row = db.execute(
        text("SELECT timestamp FROM traffic_data ORDER BY id DESC LIMIT 1")
    ).fetchone()

    if not latest_ts_row or not latest_ts_row[0]:
        return StatsReport(
            avg_speed=0.0,
            red_count=0,
            yellow_count=0,
            green_count=0,
            top_congested=[]
        )

    latest_timestamp = latest_ts_row[0]

    stats_row = db.execute(text("""
        SELECT 
            COALESCE(SUM(CASE WHEN congestion_level = 0 THEN 1 ELSE 0 END), 0) AS green_count,
            COALESCE(SUM(CASE WHEN congestion_level = 1 THEN 1 ELSE 0 END), 0) AS yellow_count,
            COALESCE(SUM(CASE WHEN congestion_level = 2 THEN 1 ELSE 0 END), 0) AS red_count,
            COALESCE(AVG(avg_speed), 0.0) AS avg_speed
        FROM traffic_data
        WHERE timestamp = :latest_timestamp
          AND congestion_level IS NOT NULL
    """), {"latest_timestamp": latest_timestamp}).fetchone()

    top_query = text("""
        SELECT 
            s.name AS street_name,
            d.name AS district_name,
            td.avg_speed,
            s.max_speed,
            (td.avg_speed / COALESCE(NULLIF(s.max_speed, 0), 50)) AS ratio
        FROM traffic_data td
        JOIN streets s ON td.street_id = s.id
        LEFT JOIN districts d ON s.district_id = d.id
        WHERE td.timestamp = :latest_timestamp
          AND td.congestion_level IS NOT NULL
        ORDER BY td.congestion_level DESC, ratio ASC
        LIMIT 5
    """)
    top_rows = db.execute(top_query, {"latest_timestamp": latest_timestamp}).fetchall()

    top_congested = []
    for row in top_rows:
        top_congested.append(CongestedStreet(
            street_name=row.street_name,
            district_name=row.district_name,
            avg_speed=round(row.avg_speed, 2)
        ))

    return StatsReport(
        avg_speed=round(stats_row.avg_speed, 2) if stats_row else 0.0,
        red_count=stats_row.red_count if stats_row else 0,
        yellow_count=stats_row.yellow_count if stats_row else 0,
        green_count=stats_row.green_count if stats_row else 0,
        top_congested=top_congested
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4c. GET /api/stats/heatmap — Bản đồ nhiệt kẹt xe theo thứ và giờ
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/heatmap",
    response_model=List[HeatmapItem],
    summary="Bản đồ nhiệt kẹt xe theo thứ và giờ",
    description="Trả về tỷ lệ kẹt xe trung bình phân loại theo Thứ trong tuần (0=Thứ 2, 6=Chủ nhật) và Giờ trong ngày (0-23).",
)
def get_stats_heatmap(
    days: int = Query(30, description="Số ngày gần nhất cần thống kê"),
    db: Session = Depends(get_db)
):
    if days == 0:
        # "Hiện tại" -> từ 0h hôm nay
        now_local = datetime.now(TZ_DANANG)
        start_time = datetime.combine(now_local.date(), datetime.min.time()).replace(tzinfo=TZ_DANANG)
    else:
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=days)

    query_str = """
        SELECT 
            (EXTRACT(ISODOW FROM td.timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh')::int - 1) AS wday,
            EXTRACT(HOUR FROM td.timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh')::int AS hr,
            (COUNT(CASE WHEN td.congestion_level = 2 THEN 1 WHEN td.congestion_level = 1 THEN 0.5 END)::float / NULLIF(COUNT(td.id), 0)) * 100.0 AS avg_congestion_pct
        FROM traffic_data td
        WHERE td.timestamp >= :start_time
          AND td.congestion_level IS NOT NULL
        GROUP BY wday, hr
        ORDER BY wday, hr
    """

    rows = db.execute(text(query_str), {"start_time": start_time}).fetchall()

    heatmap_dict = {}
    for w in range(7):
        for h in range(24):
            heatmap_dict[(w, h)] = 0.0

    for row in rows:
        w = row.wday
        h = row.hr
        if (w, h) in heatmap_dict:
            heatmap_dict[(w, h)] = round(row.avg_congestion_pct, 2) if row.avg_congestion_pct is not None else 0.0

    results = []
    for w in range(7):
        for h in range(24):
            results.append(HeatmapItem(
                weekday=w,
                hour=h,
                congestion_pct=heatmap_dict[(w, h)]
            ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 5. GET /api/stats/incidents — Thống kê sự cố giao thông & lô cốt
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/incidents",
    response_model=IncidentStatsResponse,
    summary="Thống kê sự cố giao thông & lô cốt",
    description="Trả về tổng số sự cố đang hoạt động phân loại theo loại hình, mức độ nghiêm trọng và thời gian xử lý trung bình.",
)
def get_incident_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    total_active = db.query(Incident).filter(Incident.is_active == True).count()

    type_counts_rows = db.query(Incident.type, func.count(Incident.id)).filter(Incident.is_active == True).group_by(Incident.type).all()
    type_counts = {t or "unknown": count for t, count in type_counts_rows}
    for std_type in ["roadblock", "event", "accident", "community"]:
        if std_type not in type_counts:
            type_counts[std_type] = 0

    severity_counts_rows = db.query(Incident.severity, func.count(Incident.id)).filter(Incident.is_active == True).group_by(Incident.severity).all()
    severity_counts = {sev: count for sev, count in severity_counts_rows}
    for std_sev in [1, 2, 3]:
        if std_sev not in severity_counts:
            severity_counts[std_sev] = 0

    avg_resolve_row = db.execute(text("""
        SELECT AVG(EXTRACT(EPOCH FROM (end_time - start_time)) / 60.0) 
        FROM incidents 
        WHERE status = 'resolved' AND end_time IS NOT NULL
    """)).fetchone()
    
    avg_resolve_time = round(avg_resolve_row[0], 1) if avg_resolve_row and avg_resolve_row[0] is not None else 0.0

    return IncidentStatsResponse(
        total_active=total_active,
        by_type=type_counts,
        by_severity=severity_counts,
        avg_resolve_time_minutes=avg_resolve_time
    )


# ─────────────────────────────────────────────────────────────────────────────
# 6. GET /api/stats/feedback-summary — Thống kê phản hồi từ cộng đồng
# ─────────────────────────────────────────────────────────────────────────────
@router.get(
    "/feedback-summary",
    response_model=FeedbackStatsResponse,
    summary="Thống kê báo cáo phản ánh từ cộng đồng",
    description="Thống kê tổng số báo cáo của người dân trong 24 giờ qua, biểu đồ loại hình báo cáo và top các tuyến đường nhận phản ánh.",
)
def get_feedback_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_csgt),
):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)

    total_reports = db.query(Feedback).filter(Feedback.created_at >= cutoff).count()

    type_counts_rows = db.query(Feedback.report_type, func.count(Feedback.id)).filter(Feedback.created_at >= cutoff).group_by(Feedback.report_type).all()
    type_counts = {t or "unknown": count for t, count in type_counts_rows}
    for std_type in ["congested", "clear", "accident"]:
        if std_type not in type_counts:
            type_counts[std_type] = 0

    top_reported_query = text("""
        SELECT s.name AS street_name, COUNT(f.id) AS report_count
        FROM feedback f
        JOIN streets s ON f.street_id = s.id
        WHERE f.created_at >= :cutoff
        GROUP BY s.name
        ORDER BY report_count DESC
        LIMIT 5
    """)
    top_streets_rows = db.execute(top_reported_query, {"cutoff": cutoff}).fetchall()
    
    top_reported_streets = []
    for row in top_streets_rows:
        top_reported_streets.append(TopReportedStreet(
            street_name=row.street_name,
            report_count=row.report_count
        ))

    return FeedbackStatsResponse(
        total_reports=total_reports,
        by_type=type_counts,
        top_reported_streets=top_reported_streets
    )
