"""
shared/api/mock.py — Mock Data (Fallback khi backend down)

Dùng khi backend chưa xong hoặc chạy offline.
Format đã sync với Sprint 2: mỗi street có segments[] thay vì path[] trực tiếp.

FIX 6: Cập nhật format segments[] để build_map_dataframe() render đúng PathLayer.
"""

# ── Màu theo mức ùn tắc [R, G, B, A] ─────────────────────────────────────────
_COLORS = {
    0: [34,  197,  94, 220],   # Xanh — thông thoáng
    1: [234, 179,   8, 220],   # Vàng  — chậm
    2: [239,  68,  68, 220],   # Đỏ    — kẹt xe
}


def _seg(path: list, speed: float, level: int) -> dict:
    """Tạo 1 segment object đúng format Sprint 2."""
    return {
        "path"            : path,
        "avg_speed"       : speed,
        "congestion_level": level,
        "color"           : _COLORS.get(level, [156, 163, 175, 150]),
    }


def get_mock_traffic(district_id: int | None = None) -> dict:
    """Mock data giao thông 8 đường Đà Nẵng — format Sprint 2 segments[]."""
    streets = [
        {
            "street_id": 1, "street_name": "Hùng Vương",
            "district_name": "Hải Châu", "district_id": 1,
            "avg_speed": 25, "max_speed": 50, "congestion_level": 1,
            "congestion_label": "🟡 Chậm", "timestamp_vn": "19:00 20/04",
            "lat": 16.0670, "lon": 108.2135,
            "segments": [_seg([[108.2120, 16.0680], [108.2135, 16.0665], [108.2150, 16.0650]], 25, 1)],
        },
        {
            "street_id": 2, "street_name": "Lê Duẩn",
            "district_name": "Hải Châu", "district_id": 1,
            "avg_speed": 12, "max_speed": 50, "congestion_level": 2,
            "congestion_label": "🔴 Kẹt xe", "timestamp_vn": "19:00 20/04",
            "lat": 16.0705, "lon": 108.2215,
            "segments": [_seg([[108.2200, 16.0720], [108.2215, 16.0705], [108.2230, 16.0690]], 12, 2)],
        },
        {
            "street_id": 3, "street_name": "Nguyễn Văn Linh",
            "district_name": "Hải Châu", "district_id": 1,
            "avg_speed": 48, "max_speed": 60, "congestion_level": 0,
            "congestion_label": "🟢 Thông thoáng", "timestamp_vn": "19:00 20/04",
            "lat": 16.0585, "lon": 108.2070,
            "segments": [_seg([[108.2050, 16.0600], [108.2070, 16.0585], [108.2090, 16.0570]], 48, 0)],
        },
        {
            "street_id": 4, "street_name": "Trần Hưng Đạo",
            "district_name": "Sơn Trà", "district_id": 3,
            "avg_speed": 35, "max_speed": 50, "congestion_level": 1,
            "congestion_label": "🟡 Chậm", "timestamp_vn": "19:00 20/04",
            "lat": 16.0785, "lon": 108.2320,
            "segments": [_seg([[108.2300, 16.0800], [108.2320, 16.0785]], 35, 1)],
        },
        {
            "street_id": 5, "street_name": "Hoàng Sa",
            "district_name": "Sơn Trà", "district_id": 3,
            "avg_speed": 55, "max_speed": 80, "congestion_level": 0,
            "congestion_label": "🟢 Thông thoáng", "timestamp_vn": "19:00 20/04",
            "lat": 16.0860, "lon": 108.2450,
            "segments": [_seg([[108.2400, 16.0850], [108.2450, 16.0860], [108.2500, 16.0870]], 55, 0)],
        },
        {
            "street_id": 6, "street_name": "Nguyễn Tất Thành",
            "district_name": "Thanh Khê", "district_id": 2,
            "avg_speed": 8, "max_speed": 50, "congestion_level": 2,
            "congestion_label": "🔴 Kẹt xe", "timestamp_vn": "19:00 20/04",
            "lat": 16.0730, "lon": 108.1920,
            "segments": [_seg([[108.1900, 16.0750], [108.1920, 16.0730], [108.1940, 16.0710]], 8, 2)],
        },
        {
            "street_id": 7, "street_name": "2 tháng 9",
            "district_name": "Hải Châu", "district_id": 1,
            "avg_speed": 40, "max_speed": 60, "congestion_level": 0,
            "congestion_label": "🟢 Thông thoáng", "timestamp_vn": "19:00 20/04",
            "lat": 16.0595, "lon": 108.2185,
            "segments": [_seg([[108.2170, 16.0610], [108.2185, 16.0595], [108.2200, 16.0580]], 40, 0)],
        },
        {
            "street_id": 8, "street_name": "Phạm Văn Đồng",
            "district_name": "Sơn Trà", "district_id": 3,
            "avg_speed": 30, "max_speed": 60, "congestion_level": 1,
            "congestion_label": "🟡 Chậm", "timestamp_vn": "19:00 20/04",
            "lat": 16.0680, "lon": 108.2370,
            "segments": [_seg([[108.2350, 16.0700], [108.2370, 16.0680], [108.2390, 16.0660]], 30, 1)],
        },
    ]

    # Lọc theo quận nếu có
    if district_id:
        streets = [s for s in streets if s.get("district_id") == district_id]

    green  = sum(1 for s in streets if s["congestion_level"] == 0)
    yellow = sum(1 for s in streets if s["congestion_level"] == 1)
    red    = sum(1 for s in streets if s["congestion_level"] == 2)
    speeds = [s["avg_speed"] for s in streets if s["avg_speed"]]

    return {
        "total_streets" : len(streets),
        "green_count"   : green,
        "yellow_count"  : yellow,
        "red_count"     : red,
        "avg_speed_city": round(sum(speeds) / len(speeds), 1) if speeds else 0,
        "data_as_of"    : "2026-04-20T19:00:00Z",
        "streets"       : streets,
    }


def get_mock_streets() -> list:
    """Mock danh sách đường (geometry only)."""
    return get_mock_traffic()["streets"]


# ═══════════════════════════════════════════════════════════════════════
# SPRINT 3 MOCK DATA — SCRUM 36–39
# Dùng khi backend chưa xong SCRUM-32 (API Dự báo) và SCRUM-35 (API Báo cáo)
# ═══════════════════════════════════════════════════════════════════════

import random, math
random.seed(42)   # seed cố định → data nhất quán mỗi lần chạy


def get_mock_predictions() -> list:
    """
    Mock: Dự báo AI congestion 30 phút tới cho 43 tuyến đường — SCRUM-36.
    Contract: GET /api/predict/30min
    Response: List[{street_id, street_name, district_name,
                    current_level, predicted_level, confidence,
                    current_speed, predicted_speed}]
    """
    streets_raw = get_mock_traffic()["streets"]
    # Mở rộng thêm các đường giống thực tế
    extra = [
        ("Bạch Đằng",       "Hải Châu",     1, 0, 0.88),
        ("Trần Phú",        "Hải Châu",     1, 2, 0.74),
        ("Nguyễn Chí Thanh","Hải Châu",     0, 1, 0.82),
        ("Lê Lợi",          "Hải Châu",     0, 0, 0.91),
        ("Điện Biên Phủ",   "Thanh Khê",    1, 1, 0.79),
        ("Phan Châu Trinh",  "Hải Châu",     2, 2, 0.95),
        ("Nguyễn Văn Thoại","Sơn Trà",      0, 0, 0.85),
        ("Võ Nguyên Giáp",  "Sơn Trà",      0, 1, 0.67),
        ("Trường Sa",       "Ngũ Hành Sơn", 0, 0, 0.93),
        ("Hà Huy Tập",      "Thanh Khê",    1, 2, 0.71),
        ("Cách Mạng Tháng 8","Liên Chiểu",  0, 0, 0.87),
        ("Nguyễn Lương Bằng","Liên Chiểu",  0, 0, 0.90),
    ]

    results = []
    for i, s in enumerate(streets_raw):
        cur = s["congestion_level"]
        # predicted thay đổi ngẫu nhiên ±1 mức
        pred = max(0, min(2, cur + random.choice([-1, 0, 0, 1])))
        conf = round(random.uniform(0.65, 0.95), 2)
        results.append({
            "street_id"     : s["street_id"],
            "street_name"   : s["street_name"],
            "district_name" : s["district_name"],
            "current_level" : cur,
            "predicted_level": pred,
            "confidence"    : conf,
            "current_speed" : s["avg_speed"],
            "predicted_speed": max(5, round(s["avg_speed"] * random.uniform(0.7, 1.2))),
        })

    for i, (name, district, cur, pred, conf) in enumerate(extra):
        results.append({
            "street_id"     : 100 + i,
            "street_name"   : name,
            "district_name" : district,
            "current_level" : cur,
            "predicted_level": pred,
            "confidence"    : conf,
            "current_speed" : random.randint(15, 55),
            "predicted_speed": random.randint(10, 50),
        })
    return results


def get_mock_hourly_trend(days: int = 7) -> list:
    """
    Mock: Xu hướng congestion theo giờ trong N ngày gần nhất — SCRUM-37.
    Contract: GET /api/stats/hourly-trend?days=7
    Response: List[{hour, avg_green, avg_yellow, avg_red}]  (trung bình theo giờ)
    """
    rush_hours = {7, 8, 9, 17, 18, 19}
    result = []
    for h in range(24):
        is_rush = h in rush_hours
        is_night = h < 6 or h >= 22
        base_green  = 30 if is_rush else (38 if is_night else 35)
        base_yellow = 9  if is_rush else (3  if is_night else 6)
        base_red    = 4  if is_rush else (0  if is_night else 2)
        result.append({
            "hour"      : h,
            "avg_green" : base_green  + random.randint(-2, 2),
            "avg_yellow": base_yellow + random.randint(-1, 1),
            "avg_red"   : max(0, base_red + random.randint(-1, 1)),
        })
    return result


def get_mock_heatmap() -> list:
    """
    Mock: Heatmap mức ùn tắc theo giờ × ngày — SCRUM-38.
    Contract: GET /api/stats/heatmap
    Response: List[{day_of_week, hour, avg_congestion}]
    day_of_week: 0=Thứ 2 … 6=Chủ nhật
    avg_congestion: 0.0 – 2.0 (trung bình congestion_level)
    """
    rush = {7, 8, 9, 17, 18, 19}
    rows = []
    for day in range(7):
        is_weekend = day >= 5
        for h in range(24):
            is_rush = h in rush
            is_night = h < 6 or h >= 22
            base = 1.2 if (is_rush and not is_weekend) else (
                   0.8 if (is_rush and is_weekend) else (
                   0.1 if is_night else 0.5))
            rows.append({
                "day_of_week"    : day,
                "hour"           : h,
                "avg_congestion" : round(max(0, min(2, base + random.uniform(-0.2, 0.3))), 2),
            })
    return rows


def get_mock_report() -> dict:
    """
    Mock: Báo cáo tổng hợp giao thông — SCRUM-39.
    Contract: GET /api/stats/report
    """
    streets = get_mock_traffic()["streets"]
    districts = {}
    for s in streets:
        d = s["district_name"]
        districts.setdefault(d, {"green": 0, "yellow": 0, "red": 0})
        lv = s["congestion_level"]
        if lv == 0:   districts[d]["green"]  += 1
        elif lv == 1: districts[d]["yellow"] += 1
        else:         districts[d]["red"]    += 1

    # Top 5 đường kẹt nhất (theo avg_speed thấp nhất)
    top_congested = sorted(streets, key=lambda x: x["avg_speed"])[:5]

    return {
        "total_streets"   : len(streets),
        "total_records_db": 576,
        "green_count"     : sum(1 for s in streets if s["congestion_level"] == 0),
        "yellow_count"    : sum(1 for s in streets if s["congestion_level"] == 1),
        "red_count"       : sum(1 for s in streets if s["congestion_level"] == 2),
        "avg_speed"       : round(sum(s["avg_speed"] for s in streets) / len(streets), 1),
        "district_stats"  : [
            {"district": d, **v} for d, v in districts.items()
        ],
        "top_congested"   : [
            {
                "street_name"   : s["street_name"],
                "district_name" : s["district_name"],
                "avg_speed"     : s["avg_speed"],
                "congestion_label": s["congestion_label"],
            }
            for s in top_congested
        ],
    }
