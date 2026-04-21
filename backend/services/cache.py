"""
services/cache.py — Cache layer dùng Redis

Nhiệm vụ:
    Bọc các thao tác Redis hay dùng nhất trong dự án.
    Router chỉ cần gọi cache.get_traffic() / cache.set_traffic()
    mà không cần biết chi tiết Redis hoạt động thế nào.

Key naming convention:
    traffic:current        → Snapshot traffic toàn thành phố
    traffic:street:{id}    → Snapshot 1 tuyến đường
    api:calls:{date}       → Đếm request TomTom trong ngày
"""

import logging
from redis_client import redis_client, get_json, set_json

log = logging.getLogger("cache")

# ─── TTL (Time-To-Live) mặc định ─────────────────────────────────────────────
TTL_TRAFFIC_CURRENT  = 90    # giây — cache traffic toàn TP (30 phút cào 1 lần, 90s là đủ)
TTL_TRAFFIC_STREET   = 90    # giây — cache traffic 1 đường
TTL_API_COUNTER      = 90_000  # giây (25 giờ) — reset counter TomTom mỗi ngày


# ─── 1. CACHE TRAFFIC TOÀN THÀNH PHỐ ────────────────────────────────────────

CACHE_KEY_TRAFFIC = "traffic:current"


def get_traffic() -> list | None:
    """
    Lấy snapshot traffic toàn thành phố từ Redis.

    Returns:
        list  — nếu cache còn hiệu lực (chưa hết TTL 90s)
        None  — nếu cache miss (chưa set hoặc đã hết TTL) → router phải query DB
    """
    data = get_json(CACHE_KEY_TRAFFIC)
    if data is not None:
        log.debug(f"✅ Cache HIT: {CACHE_KEY_TRAFFIC}")
    else:
        log.debug(f"❌ Cache MISS: {CACHE_KEY_TRAFFIC} → sẽ query DB")
    return data


def set_traffic(records: list, ttl: int = TTL_TRAFFIC_CURRENT) -> None:
    """
    Lưu snapshot traffic toàn thành phố vào Redis.

    Args:
        records : list dict — kết quả từ query DB
        ttl     : Số giây trước khi Redis tự xóa key (default 90s)
    """
    set_json(CACHE_KEY_TRAFFIC, records, ttl=ttl)
    log.info(f"💾 Cache SET: {CACHE_KEY_TRAFFIC} (TTL={ttl}s, {len(records)} bản ghi)")


def invalidate_traffic() -> None:
    """
    Xóa cache traffic ngay lập tức.
    Gọi sau khi cào xong dữ liệu mới → buộc lần gọi tiếp theo đọc lại từ DB.
    """
    redis_client.delete(CACHE_KEY_TRAFFIC)
    log.info(f"🗑  Cache INVALIDATED: {CACHE_KEY_TRAFFIC}")


# ─── 2. CACHE TRAFFIC 1 TUYẾN ĐƯỜNG ─────────────────────────────────────────

def get_traffic_street(street_id: int) -> dict | None:
    """
    Lấy traffic của 1 tuyến đường từ Redis.
    Returns dict hoặc None nếu cache miss.
    """
    return get_json(f"traffic:street:{street_id}")


def set_traffic_street(street_id: int, data: dict, ttl: int = TTL_TRAFFIC_STREET) -> None:
    """Lưu traffic 1 tuyến đường vào Redis."""
    set_json(f"traffic:street:{street_id}", data, ttl=ttl)


# ─── 3. COUNTER SỐ LẦN GỌI TOMTOM ───────────────────────────────────────────

def get_api_call_count(date_str: str) -> int:
    """
    Lấy số lần đã gọi TomTom API trong ngày.

    Args:
        date_str: "YYYY-MM-DD", ví dụ "2026-04-21"
    Returns:
        int — số lần đã gọi (0 nếu chưa gọi lần nào hôm nay)
    """
    return int(redis_client.get(f"api:calls:{date_str}") or 0)


def increment_api_call(date_str: str) -> int:
    """
    Tăng counter TomTom lên 1.
    Tự đặt TTL 25h cho lần đầu tiên trong ngày.

    Returns:
        int — giá trị mới sau khi tăng
    """
    key = f"api:calls:{date_str}"
    count = redis_client.incr(key)       # Tăng 1, nếu key chưa có thì khởi tạo = 0 rồi tăng
    if count == 1:
        redis_client.expire(key, TTL_API_COUNTER)   # Chỉ set TTL lần đầu
    return count


# ─── 4. KIỂM TRA TRẠNG THÁI CACHE (dùng cho health check / debug) ────────────

def get_cache_info() -> dict:
    """
    Trả về thông tin trạng thái cache hiện tại.
    Dùng cho admin panel hoặc debug.
    """
    traffic_ttl   = redis_client.ttl(CACHE_KEY_TRAFFIC)   # -2 = key không tồn tại, -1 = không có TTL
    traffic_exist = redis_client.exists(CACHE_KEY_TRAFFIC) > 0

    return {
        "traffic_cached" : traffic_exist,
        "traffic_ttl_sec": traffic_ttl if traffic_ttl >= 0 else None,
        "traffic_key"    : CACHE_KEY_TRAFFIC,
    }
