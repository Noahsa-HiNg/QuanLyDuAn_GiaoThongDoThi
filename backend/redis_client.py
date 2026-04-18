"""
redis_client.py — Khởi tạo và quản lý kết nối đến Redis

Redis là gì?
    Redis (Remote Dictionary Server) là một cơ sở dữ liệu lưu trữ
    dạng key-value IN-MEMORY — tức là dữ liệu nằm trong RAM, không phải ổ cứng.
    → Truy xuất cực nhanh (~1ms) so với PostgreSQL (~10-50ms).

Trong dự án này Redis dùng để:
    1. Cache dữ liệu giao thông (traffic:current) — tránh query DB mỗi request
    2. Cache kết quả dự báo AI (predictions:30m:{street_id})
    3. Lưu JWT blacklist khi user logout
    4. Đếm số lần gọi API bên ngoài theo ngày
    5. Lưu cảnh báo toàn bản đồ (alert:global)

Cách dùng trong router:
    from redis_client import redis_client

    # Lưu giá trị
    redis_client.set("my_key", "my_value")

    # Lấy giá trị
    value = redis_client.get("my_key")

    # Lưu có thời gian tự xóa (TTL)
    redis_client.setex("my_key", 65, "my_value")  # xóa sau 65 giây
"""

import json
import logging

import redis

from config import settings

# Logger riêng cho module này — log sẽ có prefix "[redis_client]" để dễ phân biệt
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# 1. TẠO REDIS CLIENT
# ─────────────────────────────────────────────────────────────

# redis.Redis() là constructor tạo đối tượng kết nối đến Redis server.
# Nó KHÔNG kết nối ngay lập tức — kết nối thực sự chỉ xảy ra khi
# bạn gọi lệnh đầu tiên (lazy connection).
redis_client = redis.Redis(
    host=settings.redis_host,       # Hostname của Redis server.
                                    # Trong Docker Compose → tên service: "redis"
                                    # Chạy local → "localhost"

    port=settings.redis_port,       # Cổng Redis, mặc định là 6379

    db=0,                           # Redis có 16 database logic (0-15), mặc định dùng db=0.
                                    # Các db này독lập với nhau như các schema trong PostgreSQL.
                                    # Dự án này chỉ cần db=0 là đủ.

    decode_responses=True,          # ★ QUAN TRỌNG:
                                    # Mặc định Redis trả về bytes: b"hello"
                                    # Với decode_responses=True → tự động decode thành str: "hello"
                                    # → Tiện hơn khi làm việc với JSON string

    socket_connect_timeout=5,       # Timeout kết nối (giây).
                                    # Nếu sau 5s không kết nối được → raise ConnectionError
                                    # (tránh bị treo vô hạn khi Redis down)

    socket_timeout=5,               # Timeout cho mỗi lệnh Redis (read/write).
                                    # Nếu lệnh không có kết quả sau 5s → raise TimeoutError

    retry_on_timeout=True,          # Tự động thử lại nếu timeout xảy ra.
                                    # Hữu ích khi mạng bị gián đoạn thoáng qua.
)


# ─────────────────────────────────────────────────────────────
# 2. KIỂM TRA KẾT NỐI (dùng cho health check)
# ─────────────────────────────────────────────────────────────

def check_redis_connection() -> bool:
    """
    Kiểm tra xem ứng dụng có kết nối được đến Redis không.
    Trả về True nếu thành công, False nếu thất bại.

    Được gọi trong endpoint GET /api/health.
    """
    try:
        # redis_client.ping() gửi lệnh PING lên Redis server.
        # Nếu Redis đang chạy → trả về True (tương đương response "PONG").
        # Nếu không kết nối được → raise redis.ConnectionError
        redis_client.ping()
        return True
    except redis.ConnectionError as e:
        logger.error(f"[redis_client] ❌ Không kết nối được Redis: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# 3. HELPER FUNCTIONS — Thao tác JSON tiện lợi
# ─────────────────────────────────────────────────────────────
# Redis chỉ lưu được string, không lưu được dict/list trực tiếp.
# Hai hàm dưới đây tự động serialize/deserialize JSON để code ở
# tầng service trở nên đơn giản hơn.

def set_json(key: str, value: dict | list, ttl: int | None = None) -> None:
    """
    Lưu một dict hoặc list vào Redis dưới dạng JSON string.

    Args:
        key  : Tên key Redis, ví dụ "traffic:current"
        value: Dict hoặc list Python cần lưu
        ttl  : Thời gian sống (giây). None = không tự xóa.

    Ví dụ:
        set_json("traffic:current", [{"street_id": 1, "speed": 40}], ttl=65)
    """
    # json.dumps() chuyển dict/list Python → chuỗi JSON
    # Ví dụ: {"a": 1} → '{"a": 1}'
    serialized = json.dumps(value, ensure_ascii=False)

    if ttl is not None:
        # setex(key, time, value) = SET + EX (EXpire)
        # Lưu key và tự động xóa sau `ttl` giây
        redis_client.setex(name=key, time=ttl, value=serialized)
    else:
        # set(key, value) — lưu không có hạn
        redis_client.set(name=key, value=serialized)


def get_json(key: str) -> dict | list | None:
    """
    Lấy giá trị JSON từ Redis và parse thành dict hoặc list.

    Args:
        key: Tên key Redis cần đọc

    Returns:
        dict hoặc list nếu key tồn tại, None nếu key không có (cache miss).

    Ví dụ:
        data = get_json("traffic:current")
        if data is None:
            # Cache miss → query DB
    """
    # redis_client.get(key):
    #   - Nếu key tồn tại → trả về string
    #   - Nếu key không tồn tại (hết TTL hoặc chưa set) → trả về None
    raw = redis_client.get(key)

    if raw is None:
        return None  # Cache miss

    # json.loads() chuyển chuỗi JSON → dict/list Python
    # Ví dụ: '{"a": 1}' → {"a": 1}
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────
# 4. HELPER — Blacklist JWT Token khi logout
# ─────────────────────────────────────────────────────────────

def blacklist_token(token: str, expire_seconds: int) -> None:
    """
    Thêm JWT token vào blacklist Redis khi user logout.

    Cơ chế:
        - Lưu token như một key với TTL = thời gian còn lại của token
        - Khi user gửi request → middleware kiểm tra key này có tồn tại không
        - Nếu tồn tại → token đã bị thu hồi → trả về 401 Unauthorized

    Args:
        token          : JWT token string
        expire_seconds : Số giây TTL (thường = thời gian còn hiệu lực của JWT)
    """
    # Dùng prefix "jwt:blacklist:" để phân biệt với các key khác
    key = f"jwt:blacklist:{token}"
    # Lưu giá trị "1" (không quan trọng nội dung, chỉ cần key tồn tại)
    redis_client.setex(name=key, time=expire_seconds, value="1")


def is_token_blacklisted(token: str) -> bool:
    """
    Kiểm tra xem token có trong blacklist không.

    Returns:
        True nếu token đã bị thu hồi (logout), False nếu còn hợp lệ.
    """
    key = f"jwt:blacklist:{token}"
    # exists() trả về số lượng key tìm thấy (0 hoặc 1)
    # Chuyển về bool: 0 → False, 1 → True
    return redis_client.exists(key) > 0


# ─────────────────────────────────────────────────────────────
# 5. HELPER — Đếm API calls trong ngày
# ─────────────────────────────────────────────────────────────

def increment_api_counter(date_str: str) -> int:
    """
    Tăng counter số lần gọi external API trong ngày lên 1.

    Args:
        date_str: Chuỗi ngày dạng "YYYY-MM-DD", ví dụ "2025-10-15"

    Returns:
        Giá trị counter sau khi tăng.

    Ví dụ:
        count = increment_api_counter("2025-10-15")
        if count > 2000:
            raise Exception("Đã vượt giới hạn API hôm nay")
    """
    key = f"api:calls:{date_str}"

    # incr() tăng giá trị của key lên 1 và trả về giá trị mới.
    # Nếu key chưa tồn tại → Redis tự tạo với giá trị ban đầu = 0, rồi tăng lên 1.
    count = redis_client.incr(key)

    # Chỉ set TTL cho lần đầu tiên (count == 1) để tránh reset TTL liên tục
    if count == 1:
        # expire() đặt TTL cho key hiện có (khác setex là set + TTL cùng lúc)
        # 25 giờ = 90000 giây → đảm bảo key tồn tại qua nửa đêm
        redis_client.expire(key, 90_000)

    return count
