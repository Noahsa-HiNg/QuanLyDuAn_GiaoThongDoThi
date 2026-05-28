"""
features/map/service.py — Business Logic: Bản đồ Giao thông
v1.4 — FIX 1: lat/lon centroid thêm vào base (dùng cho map zoom SCRUM-22/24)
v1.5 — OPT: 2-step loading (geometry tĩnh + state động) giảm reload 3-5s → <1s
"""

import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.api.client import get_traffic_current, get_streets_geometry, get_traffic_state
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

    Cấu trúc API Sprint 2:
      street.segments = [{ path, avg_speed, congestion_level, color }, ...]  ← luôn có nếu có geometry
      street.path     = null  (backend không dùng nữa)
      street.lat/lon  = centroid fallback khi không có geometry

    Mỗi SEGMENT = 1 row trong DataFrame → PathLayer vẽ từng đoạn màu riêng.
    Không có segments (không có geometry) → fallback dot tại centroid lat/lon.
    """
    rows = []

    for street in traffic_data.get("streets", []):
        segments = street.get("segments") or []

        # Tooltip info chung cho cả đường
        # lat/lon centroid của đường — dùng cho ScatterLayer fallback + map zoom
        base = {
            "street_id"       : street.get("street_id"),
            "name"            : street.get("street_name", ""),
            "district"        : street.get("district_name", ""),
            "avg_speed"       : street.get("avg_speed") or 0,
            "max_speed"       : street.get("max_speed") or 50,
            "congestion_level": street.get("congestion_level"),
            "congestion_label": street.get("congestion_label") or congestion_label(street.get("congestion_level")),
            "timestamp_vn"    : street.get("timestamp_vn", "—"),
            # FIX 1: centroid luôn có trong mọi row để tính zoom map
            "lat"             : street.get("lat") or 16.0544,
            "lon"             : street.get("lon") or 108.2022,
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
                    # lat/lon kế thừa từ base (centroid của đường)
                })
        else:
            # ── Không có segments = đường không có geometry trong DB ──
            # Fallback: hiển thị dot tại centroid (lat/lon từ base)
            level = street.get("congestion_level")
            rows.append({
                **base,
                "color": get_color(level),
                "path" : None,
            })

    return pd.DataFrame(rows) if rows else pd.DataFrame()


def filter_dataframe(
    df: pd.DataFrame,
    search: str = "",
    congestion: int | None = None,
) -> pd.DataFrame:
    """
    Lọc DataFrame theo tên đường và/hoặc mức ùn tắc — client-side.
    Gọi sau build_map_dataframe(). Không gọi thêm API.

    Args:
        df         — DataFrame từ build_map_dataframe()
        search     — Từ khoá tên đường (case-insensitive). "" = không lọc
        congestion — Mức ùn tắc (0/1/2). None = hiển thị tất cả

    Returns:
        DataFrame đã lọc, cùng cấu trúc cột với input.
    """
    if df.empty:
        return df

    # SCRUM-22: Tìm kiếm tên đường (so khớp một phần, không phân biệt hoa thường)
    if search:
        mask_search = df["name"].str.contains(search, case=False, na=False)
        df = df[mask_search]

    # SCRUM-23: Lọc theo mức ùn tắc
    if congestion is not None:
        mask_cong = df["congestion_level"] == congestion
        df = df[mask_cong]

    return df



def _fmt_ts_vn(iso_str) -> str:
    """Parse ISO UTC timestamp -> formatted VN +07 string. Frontend-only, no backend change."""
    if not iso_str:
        return "-"
    try:
        from datetime import datetime, timezone, timedelta
        s = str(iso_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s).astimezone(timezone(timedelta(hours=7)))
        return dt.strftime("%Y-%m-%d %H:%M:%S +07:00")
    except Exception:
        return str(iso_str)


def build_map_dataframe_split(geometry: dict, state: dict) -> tuple:
    """
    Merge geometry (tinh, cache 1h) + state (dong, poll 60s) -> DataFrame + meta KPI.
    geometry tu GET /api/traffic/streets-geometry
    state tu GET /api/traffic/state
    Tra ve (df, meta) - meta tuong thich voi render_kpi_cards().
    """
    state_map = {s["street_id"]: s for s in state.get("streets", [])}

    rows = []
    green = yellow = red = no_data = 0
    speeds = []

    for g in geometry.get("streets", []):
        sid   = g["street_id"]
        s     = state_map.get(sid, {})
        level = s.get("congestion_level")
        color = s.get("color") or [107, 114, 128, 150]
        spd   = s.get("avg_speed")

        if   level == 0: green   += 1
        elif level == 1: yellow  += 1
        elif level == 2: red     += 1
        else:            no_data += 1

        if spd is not None:
            speeds.append(spd)

        rows.append({
            "street_id"       : sid,
            "name"            : g.get("street_name", ""),
            "district"        : g.get("district_name", ""),
            "avg_speed"       : spd or 0,
            "max_speed"       : g.get("max_speed") or 50,
            "congestion_level": level,
            "congestion_label": s.get("congestion_label") or congestion_label(level),
            "timestamp_vn"    : _fmt_ts_vn(s.get("timestamp")),
            "lat"             : g.get("lat") or 16.0544,
            "lon"             : g.get("lon") or 108.2022,
            "color"           : color,
            "path"            : g.get("path"),
        })

    meta = {
        "total_streets" : len(rows),
        "green_count"   : green,
        "yellow_count"  : yellow,
        "red_count"     : red,
        "no_data_count" : no_data,
        "avg_speed_city": round(sum(speeds) / len(speeds), 1) if speeds else None,
        "data_as_of"    : state.get("data_as_of"),
    }

    import pandas as pd
    return (pd.DataFrame(rows) if rows else pd.DataFrame()), meta
