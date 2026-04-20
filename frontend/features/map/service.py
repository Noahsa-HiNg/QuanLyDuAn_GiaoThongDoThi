"""
features/map/service.py — Business Logic: Bản đồ Giao thông
v1.2 — Fix dot: khi segments rỗng, dùng street.path trước khi fallback lat/lon
"""

import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.api.client import get_traffic_current
from shared.utils.colors import get_color
from shared.utils.formatters import congestion_label


def get_traffic_data(district_id: int | None = None) -> dict:
    """
    Lấy traffic data từ backend (hoặc mock nếu backend chưa sẵn).
    Trả về dict chuẩn: total_streets, green/yellow/red count, streets[].
    """
    return get_traffic_current(district_id)


def build_map_dataframe(traffic_data: dict) -> pd.DataFrame:
    """
    Chuyển traffic JSON → pandas DataFrame cho Pydeck layers.

    Cấu trúc API thực tế:
      street.path     = null (luôn luôn)
      street.segments = [{ path: [[lon,lat],...], congestion_level, color }, ...]

    Mỗi SEGMENT = 1 row trong DataFrame → PathLayer vẽ từng đoạn màu riêng.
    Nếu không có segments → 1 row fallback dùng lat/lon → ScatterLayer.

    v1.1: Fix đọc segments thay vì street.path.
    """
    rows = []

    for street in traffic_data.get("streets", []):
        segments = street.get("segments") or []

        # Tooltip info chung cho cả đường
        base = {
            "street_id"       : street.get("street_id"),
            "name"            : street.get("street_name", ""),
            "district"        : street.get("district_name", ""),
            "avg_speed"       : street.get("avg_speed") or 0,
            "max_speed"       : street.get("max_speed") or 50,
            "congestion_level": street.get("congestion_level"),
            "congestion_label": street.get("congestion_label") or congestion_label(street.get("congestion_level")),
            "timestamp_vn"    : street.get("timestamp_vn", "—"),
        }

        if segments:
            # ── Mỗi segment = 1 row với path + màu riêng ─────────────
            for seg in segments:
                level = seg.get("congestion_level")
                color = seg.get("color") or get_color(level)
                rows.append({
                    **base,
                    # Ghi đè speed/label của segment (chính xác hơn street)
                    "avg_speed"       : seg.get("avg_speed") or base["avg_speed"],
                    "congestion_level": level,
                    "congestion_label": congestion_label(level) or base["congestion_label"],
                    "color"           : color,
                    "path"            : seg.get("path"),   # [[lon, lat], ...]
                    "lat"             : None,
                    "lon"             : None,
                })
        else:
            # ── Không có segments → ưu tiên street.path, fallback dot ──
            # Trường hợp: đường ngắn (Ngô Thì Nhậm...) TomTom không chia đoạn
            # street.path có tọa độ đường → dùng PathLayer
            # street.path = null → hiện dot tại tọa độ trung tâm
            level       = street.get("congestion_level")
            street_path = street.get("path")   # Có thể là list hoặc None
            rows.append({
                **base,
                "color": get_color(level),
                "path" : street_path,                           # PathLayer nếu có
                "lat"  : None if street_path else (street.get("lat") or 16.0544),
                "lon"  : None if street_path else (street.get("lon") or 108.2022),
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame()
