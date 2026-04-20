"""
shared/api/mock.py — Mock Data cho Sprint 1

Dùng khi backend chưa xong hoặc chạy offline.
Sau khi backend ổn định → file này không còn được gọi nữa
(client.py tự dùng API thật, không fallback mock).

XÓA FILE NÀY khi không cần nữa — không ảnh hưởng gì.
"""


def get_mock_traffic(district_id: int | None = None) -> dict:
    """Mock data giao thông cho 43 đường Đà Nẵng."""
    streets = [
        {
            "street_id": 1, "street_name": "Hùng Vương", "district_name": "Hải Châu",
            "avg_speed": 25, "max_speed": 50, "congestion_level": 1,
            "congestion_label": "🟡 Chậm", "timestamp_vn": "19:00 20/04",
            "path": [[108.2120, 16.0680], [108.2135, 16.0665], [108.2150, 16.0650]],
        },
        {
            "street_id": 2, "street_name": "Lê Duẩn", "district_name": "Hải Châu",
            "avg_speed": 12, "max_speed": 50, "congestion_level": 2,
            "congestion_label": "🔴 Kẹt xe", "timestamp_vn": "19:00 20/04",
            "path": [[108.2200, 16.0720], [108.2215, 16.0705], [108.2230, 16.0690]],
        },
        {
            "street_id": 3, "street_name": "Nguyễn Văn Linh", "district_name": "Hải Châu",
            "avg_speed": 48, "max_speed": 60, "congestion_level": 0,
            "congestion_label": "🟢 Thông thoáng", "timestamp_vn": "19:00 20/04",
            "path": [[108.2050, 16.0600], [108.2070, 16.0585], [108.2090, 16.0570]],
        },
        {
            "street_id": 4, "street_name": "Trần Hưng Đạo", "district_name": "Sơn Trà",
            "avg_speed": 35, "max_speed": 50, "congestion_level": 1,
            "congestion_label": "🟡 Chậm", "timestamp_vn": "19:00 20/04",
            "path": [[108.2300, 16.0800], [108.2320, 16.0785]],
        },
        {
            "street_id": 5, "street_name": "Hoàng Sa", "district_name": "Sơn Trà",
            "avg_speed": 55, "max_speed": 80, "congestion_level": 0,
            "congestion_label": "🟢 Thông thoáng", "timestamp_vn": "19:00 20/04",
            "path": [[108.2400, 16.0850], [108.2450, 16.0860], [108.2500, 16.0870]],
        },
        {
            "street_id": 6, "street_name": "Nguyễn Tất Thành", "district_name": "Thanh Khê",
            "avg_speed": 8, "max_speed": 50, "congestion_level": 2,
            "congestion_label": "🔴 Kẹt xe", "timestamp_vn": "19:00 20/04",
            "path": [[108.1900, 16.0750], [108.1920, 16.0730], [108.1940, 16.0710]],
        },
        {
            "street_id": 7, "street_name": "2 tháng 9", "district_name": "Hải Châu",
            "avg_speed": 40, "max_speed": 60, "congestion_level": 0,
            "congestion_label": "🟢 Thông thoáng", "timestamp_vn": "19:00 20/04",
            "path": [[108.2170, 16.0610], [108.2185, 16.0595], [108.2200, 16.0580]],
        },
        {
            "street_id": 8, "street_name": "Phạm Văn Đồng", "district_name": "Sơn Trà",
            "avg_speed": 30, "max_speed": 60, "congestion_level": 1,
            "congestion_label": "🟡 Chậm", "timestamp_vn": "19:00 20/04",
            "path": [[108.2350, 16.0700], [108.2370, 16.0680], [108.2390, 16.0660]],
        },
    ]

    # Lọc theo quận nếu có
    if district_id:
        district_map = {
            1: "Hải Châu", 2: "Thanh Khê", 3: "Sơn Trà",
            4: "Ngũ Hành Sơn", 5: "Liên Chiểu", 6: "Cẩm Lệ",
        }
        district_name = district_map.get(district_id, "")
        streets = [s for s in streets if s["district_name"] == district_name]

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
        "data_as_of"    : "19:00 20/04/2026 (mock)",
        "streets"       : streets,
    }


def get_mock_streets() -> list:
    """Mock danh sách đường (geometry only)."""
    return get_mock_traffic()["streets"]
