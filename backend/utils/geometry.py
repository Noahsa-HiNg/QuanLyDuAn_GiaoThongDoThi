"""
utils/geometry.py — Tiện ích xử lý geometry đường thẳng

Module này cung cấp hàm chia path thành các zone để:
  1. Ingestion: gọi TomTom tại midpoint mỗi zone
  2. API: kết hợp path zone + traffic data để trả về frontend
  3. Frontend: render từng zone với màu riêng

ZONE là một đoạn liên tiếp của đường, gồm nhiều điểm tọa độ.
Mỗi zone → 1 lần gọi TomTom → 1 màu (xanh/vàng/đỏ).
"""

from __future__ import annotations
import math


# ─── THÔNG SỐ CHIA ZONE ──────────────────────────────────────────────────────
ZONE_LENGTH_M = 500   # Mỗi zone tương ứng với khoảng 500 mét
MIN_ZONES     = 1     # Luôn có ít nhất 1 zone
MAX_ZONES     = 8     # Tối đa 8 zone (kiểm soát quota TomTom)


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Tính khoảng cách giữa 2 điểm lat/lon theo công thức Haversine.
    Trả về khoảng cách tính bằng MÉT.

    Haversine cho kết quả chính xác với khoảng cách ngắn (< 10km),
    phù hợp để tính độ dài đoạn đường trong thành phố.
    """
    R = 6_371_000  # Bán kính Trái Đất theo mét

    # Chuyển độ → radian
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    # Công thức Haversine
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def calc_road_length_m(coords: list) -> float:
    """
    Tính tổng chiều dài đường (mét) từ danh sách tọa độ [[lon, lat], ...].

    Cộng dồn khoảng cách Haversine giữa các điểm liên tiếp:
      P0──P1──P2──P3──P4
      d01 + d12 + d23 + d34 = tổng chiều dài

    Ví dụ:
      Bạch Đằng (21 điểm) ≈ 2.4 km
      Võ Nguyên Giáp       ≈ 7 km
    """
    if len(coords) < 2:
        return 0.0

    total = 0.0
    for i in range(len(coords) - 1):
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[i + 1]
        total += haversine_m(lon1, lat1, lon2, lat2)
    return total


def calc_n_zones(coords: list) -> int:
    """
    Tự động tính số zone phù hợp với độ dài đường.

    Công thức: n_zones = max(MIN, min(MAX, round(length / ZONE_LENGTH_M)))

    Ví dụ với ZONE_LENGTH_M = 500m:
      Đường  400m  → round(0.8)  = 1 zone
      Đường  800m  → round(1.6)  = 2 zone
      Đường 1500m  → round(3.0)  = 3 zone
      Đường 2400m  → round(4.8)  = 5 zone  ← Bạch Đằng
      Đường 5000m  → round(10.0) → cap = 8 zone  ← Võ Nguyên Giáp
    """
    length_m = calc_road_length_m(coords)
    n = round(length_m / ZONE_LENGTH_M)
    return max(MIN_ZONES, min(MAX_ZONES, n))


def split_path_into_zones(
    coords: list,                   # [[lon, lat], [lon, lat], ...]
    n_zones: int | None = None,     # None = tự tính theo độ dài đường
) -> list[dict]:
    """
    Chia danh sách tọa độ thành N zone để gọi TomTom riêng lẻ.

    Nếu n_zones=None (mặc định):
        → Tự động tính dựa trên độ dài đường (1 zone / 500m)
        → Đường dài → nhiều zone → chi tiết hơn
        → Đường ngắn → ít zone → tiết kiệm quota

    Ví dụ với 21 điểm và n_zones tự tính = 5:
      Zone 0: coords[0..4]   → midpoint → TomTom → segment_idx=0
      Zone 1: coords[4..8]   → midpoint → TomTom → segment_idx=1
      Zone 2: coords[8..12]  → midpoint → TomTom → segment_idx=2
      Zone 3: coords[12..16] → midpoint → TomTom → segment_idx=3
      Zone 4: coords[16..20] → midpoint → TomTom → segment_idx=4

    Các zone liền nhau DÙNG CHUNG điểm biên (overlap 1 điểm)
    để đường vẽ không bị đứt đoạn.

    Trả về list[dict]:
        segment_idx : int         — Chỉ số zone (0, 1, 2, ...)
        coords      : list        — [[lon, lat], ...] của zone này
        mid_lat     : float       — Vĩ độ điểm giữa  (latitude)
        mid_lon     : float       — Kinh độ điểm giữa (longitude)
    """
    n = len(coords)
    if n < 2:
        return []

    # Tự tính n_zones theo độ dài nếu không truyền vào
    if n_zones is None:
        n_zones = calc_n_zones(coords)

    # Điều chỉnh n_zones nếu đường quá ít điểm
    # Mỗi zone cần tối thiểu 2 điểm
    n_zones = min(n_zones, n - 1)
    n_zones = max(1, n_zones)

    # Kích thước mỗi zone (tính theo số điểm)
    zone_size = math.ceil((n - 1) / n_zones)

    zones = []
    for z in range(n_zones):
        start = z * zone_size
        end   = min(start + zone_size + 1, n)   # +1 để overlap 1 điểm

        zone_coords = coords[start:end]

        if len(zone_coords) < 2:
            continue

        # Midpoint: điểm GIỮA danh sách tọa độ zone này
        mid_idx = len(zone_coords) // 2
        mid_lon, mid_lat = zone_coords[mid_idx]   # GeoJSON: [lon, lat]

        zones.append({
            "segment_idx": z,
            "coords"     : zone_coords,   # [[lon, lat], ...]
            "mid_lat"    : mid_lat,
            "mid_lon"    : mid_lon,
        })

    return zones


def midpoint_of_linestring(coords: list) -> tuple[float, float] | tuple[None, None]:
    """
    Lấy điểm GIỮA của một danh sách tọa độ.
    Trả về (lat, lon) hoặc (None, None) nếu coords rỗng.
    """
    if not coords:
        return None, None
    mid = coords[len(coords) // 2]
    lon, lat = mid
    return lat, lon
