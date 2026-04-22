# 📚 HƯỚNG DẪN TOÀN BỘ BACKEND — AI Traffic Đà Nẵng

> Tài liệu này giải thích **từng dòng code quan trọng**, **luồng dữ liệu**, và **cách mở rộng** cho mọi thành viên trong nhóm.

---

## 📁 Cấu Trúc Thư Mục

```
backend/
│
├── main.py                   ← Điểm khởi động FastAPI, mount router
├── config.py                 ← Đọc .env, biến cấu hình toàn cục
├── database.py               ← Kết nối PostgreSQL, cung cấp session
├── redis_client.py           ← Kết nối Redis, helper functions
│
├── models/                   ← ORM: ánh xạ class Python ↔ bảng DB
│   ├── __init__.py           ← Export tất cả model (thứ tự quan trọng!)
│   ├── district.py           ← Bảng districts (8 quận Đà Nẵng)
│   ├── street.py             ← Bảng streets (50 tuyến đường) ← TRUNG TÂM
│   ├── traffic_data.py       ← Bảng traffic_data (dữ liệu real-time) ← QUAN TRỌNG NHẤT
│   ├── user.py               ← Bảng users (đăng nhập)
│   ├── prediction.py         ← Bảng predictions (kết quả dự báo AI)
│   ├── incident.py           ← Bảng incidents (lô cốt, tai nạn)
│   ├── feedback.py           ← Bảng feedback (báo cáo cộng đồng)
│   ├── audit_log.py          ← Bảng audit_log (lịch sử thao tác admin)
│   └── system_config.py      ← Bảng system_config (cấu hình hệ thống)
│
├── schemas/                  ← Pydantic: định hình JSON request/response
│   ├── street.py             ← Schema cho /api/streets
│   └── traffic.py            ← Schema cho /api/traffic
│
├── routers/                  ← HTTP Endpoints (API Controller)
│   ├── healthy.py            ← GET /api/health
│   ├── streets.py            ← GET /api/streets, GET /api/streets/{id}
│   └── traffic.py            ← GET /api/traffic/current, POST /api/traffic/crawl
│
├── services/                 ← Business Logic (không biết HTTP)
│   ├── cache.py              ← Wrapper Redis cho traffic data
│   ├── ingestion.py          ← Gọi TomTom/Goong API + quota management
│   ├── traffic_crawl.py      ← Cào tất cả đường 1 lần (dùng cho API + scheduler)
│   └── traffic_scheduler.py  ← Vòng lặp tự độnng mỗi 30 phút (container riêng)
│
└── utils/
    └── geometry.py           ← Tính toán địa lý: chia đường thành zone ~500m
```

---

## 🔵 PHẦN 1: NỀN TẢNG (Foundation)

### `config.py` — Trái Tim Cấu Hình

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # --- PostgreSQL ---
    postgres_user: str          # Bắt buộc phải có trong .env
    postgres_password: str      # Bắt buộc
    postgres_host: str = "postgres"  # Mặc định = tên service Docker
    postgres_port: int = 5432
    postgres_db: str

    # --- Redis ---
    redis_host: str = "redis"  # Mặc định = tên service Docker
    redis_port: int = 6379

    # --- JWT ---
    jwt_secret_key: str = "change-this-in-production"

    # --- TomTom (hỗ trợ nhiều key) ---
    tomtom_api_key: str = ""    # Backward-compat: 1 key
    tomtom_api_keys: str = ""   # Multi-key: "key1,key2,key3"

    @property
    def tomtom_keys_list(self) -> list[str]:
        """Parse chuỗi thành list, ưu tiên multi-key."""
        if self.tomtom_api_keys:
            keys = [k.strip() for k in self.tomtom_api_keys.split(",") if k.strip()]
            if keys: return keys
        if self.tomtom_api_key:
            return [self.tomtom_api_key]
        return []

    model_config = ConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()  # ← Singleton: import ở đâu cũng dùng chung 1 instance
```

**Cách dùng ở bất kỳ file nào:**
```python
from config import settings
print(settings.redis_host)     # "redis" (trong Docker) hoặc "localhost" (local)
print(settings.tomtom_keys_list)  # ["key1", "key2", "key3"]
```

**Khi chạy trong Docker:** `.env` được đọc tự động qua `env_file: .env` trong docker-compose.

---

### `database.py` — Quản Lý Kết Nối PostgreSQL

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Xây URL kết nối từ settings
DATABASE_URL = (
    f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)

# 2. Engine — đối tượng kết nối chính
# pool_pre_ping=True: trước mỗi query, kiểm tra kết nối còn sống không
# → tránh lỗi "connection timed out" khi PostgreSQL restart
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# 3. SessionLocal — factory tạo session cho mỗi request HTTP
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# autocommit=False: phải gọi db.commit() thủ công (tránh commit ngoài ý muốn)
# autoflush=False: không tự sync trước mỗi query

# 4. Base — class cha cho tất cả ORM model
Base = declarative_base()

# 5. Generator function — PATTERN QUAN TRỌNG
def get_db():
    db = SessionLocal()   # Tạo session mới cho request này
    try:
        yield db           # Trao session cho router (router làm việc ở đây)
        # Sau khi yield → FastAPI chờ router xử lý xong
    finally:
        db.close()         # Luôn đóng session dù thành công hay exception
```

**Tại sao dùng `yield` chứ không `return`?**

```
request đến
    │
    ▼
get_db() chạy đến yield → trao db cho router
    │
    ▼ (router xử lý, có thể lâu)
router xử lý xong / exception
    │
    ▼
get_db() tiếp tục sau yield → chạy finally → db.close()
```

Nếu dùng `return`: session không bao giờ được đóng → **memory leak** + **DB connection pool cạn kiệt**.

**Cách dùng trong router:**
```python
from fastapi import Depends
from database import get_db
from sqlalchemy.orm import Session

@router.get("/example")
def my_endpoint(db: Session = Depends(get_db)):
    # db đã được inject tự động bởi FastAPI
    results = db.query(MyModel).all()
    return results
    # Sau khi return → FastAPI tự gọi db.close()
```

---

### `redis_client.py` — Kết Nối và Helper Redis

```python
import redis, json
from config import settings

# Tạo client một lần, dùng chung toàn bộ app (singleton)
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    db=0,                    # Redis có 16 DB (0-15), dùng DB 0
    decode_responses=True,   # Tự decode bytes → str (tránh phải .decode() thủ công)
    socket_connect_timeout=5,  # Timeout kết nối 5s
    socket_timeout=5,          # Timeout mỗi command 5s
    retry_on_timeout=True,     # Tự retry nếu timeout (mạng chập chờn)
)
```

**5 nhóm helper function:**

```python
# ─── Nhóm 1: Kiểm tra kết nối ───────────────────────────────────────────────
def check_redis_connection() -> bool:
    try:
        redis_client.ping()   # Gửi PING → Redis phản hồi PONG
        return True
    except redis.ConnectionError:
        return False

# ─── Nhóm 2: Lưu/lấy JSON ──────────────────────────────────────────────────
# Redis chỉ lưu được chuỗi (string) → phải serialize dict/list thành JSON
def set_json(key: str, value: dict | list, ttl: int | None = None):
    serialized = json.dumps(value, ensure_ascii=False)
    if ttl:
        redis_client.setex(key, ttl, serialized)  # setex = SET + EXpire
    else:
        redis_client.set(key, serialized)

def get_json(key: str) -> dict | list | None:
    raw = redis_client.get(key)
    return json.loads(raw) if raw else None  # None = cache miss

# ─── Nhóm 3: JWT Blacklist (khi user logout) ────────────────────────────────
def blacklist_token(token: str, expire_seconds: int):
    redis_client.setex(f"jwt:blacklist:{token}", expire_seconds, "1")

def is_token_blacklisted(token: str) -> bool:
    return redis_client.exists(f"jwt:blacklist:{token}") > 0

# ─── Nhóm 4: Đếm API calls trong ngày ──────────────────────────────────────
def increment_api_counter(date_str: str) -> int:
    key = f"api:calls:{date_str}"
    count = redis_client.incr(key)  # Tăng 1, tự tạo nếu chưa có
    if count == 1:
        redis_client.expire(key, 90_000)  # Set TTL 25h lần đầu tiên
    return count
```

**Redis key naming convention trong dự án:**
```
traffic:current          → Cache giao thông toàn thành phố
traffic:street:{id}      → Cache giao thông 1 đường
jwt:blacklist:{token}    → Token đã bị thu hồi (logout)
api:calls:{YYYY-MM-DD}   → Số lần gọi TomTom hôm nay
```

---

## 🔴 PHẦN 2: MODELS (Database Schema)

### Thứ Tự Import Quan Trọng (`models/__init__.py`)

```python
# BẮT BUỘC import đúng thứ tự: bảng cha → bảng con
# Vì SQLAlchemy cần biết bảng cha tồn tại trước khi setup FK

from .district import District    # Không có FK → import trước
from .user import User            # Không có FK → import trước

from .street import Street        # FK → districts.id

from .traffic_data import TrafficData  # FK → streets.id
from .prediction import Prediction    # FK → streets.id
from .incident import Incident        # FK → streets.id, users.id
from .feedback import Feedback        # FK → streets.id

from .audit_log import AuditLog       # FK → users.id
from .system_config import SystemConfig  # FK → users.id
```

**Nếu sai thứ tự:** `NoReferencedTableError: 'streets' is not defined` hoặc tương tự.

---

### `models/street.py` — Bảng Trung Tâm

```python
from geoalchemy2 import Geometry  # PostGIS extension cho SQLAlchemy

class Street(Base):
    __tablename__ = "streets"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(200), nullable=False)   # "Bạch Đằng", "Lê Duẩn"
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=True)

    # LINESTRING: hình dạng đường trên bản đồ (danh sách điểm GPS theo thứ tự)
    # srid=4326: hệ tọa độ WGS84 (lat/lng GPS tiêu chuẩn)
    # Dùng để: render PathLayer Pydeck + tính khoảng cách A* routing
    geometry    = Column(Geometry("LINESTRING", srid=4326), nullable=True)

    length_km   = Column(Float)    # Chiều dài (km) — trọng số cạnh A*
    max_speed   = Column(Integer)  # Tốc độ giới hạn (km/h) — tính congestion
    is_one_way  = Column(Boolean, default=False)  # Đường 1 chiều?

    # Relationships — truy cập như thuộc tính Python
    district    = relationship("District", back_populates="streets")
    traffic_data = relationship("TrafficData", back_populates="street",
                                cascade="all, delete-orphan")
    # cascade="all, delete-orphan": xóa Street → tự xóa luôn traffic_data
```

**Cách dùng relationship:**
```python
street = db.query(Street).filter(Street.id == 1).first()
print(street.name)             # "Bạch Đằng"
print(street.district.name)    # "Hải Châu" (không cần JOIN thủ công!)
print(len(street.traffic_data))  # Số bản ghi traffic của đường này
```

---

### `models/traffic_data.py` — Bảng Quan Trọng Nhất

```python
class TrafficData(Base):
    __tablename__ = "traffic_data"

    id           = Column(BigInteger, primary_key=True, autoincrement=True)
    # BigInteger (max ~9.2 × 10^18) thay vì Integer (max ~2.1 tỷ)
    # Lý do: 50 đường × 4 zone × 30 min/lần × 24h = ~95,000 bản ghi/ngày
    # 1 năm = ~35 triệu bản ghi → Integer sẽ bị overflow sau ~16 năm

    street_id    = Column(Integer, ForeignKey("streets.id"), nullable=False)
    segment_idx  = Column(Integer, nullable=False, default=0)
    # segment_idx = 0, 1, 2, ... — đoạn nào của đường
    # Đường 2km chia 4 zone → 4 bản ghi với segment_idx 0,1,2,3
    # → Frontend tô 4 màu khác nhau trên cùng 1 đường

    timestamp    = Column(TIMESTAMP(timezone=True), nullable=False)
    # timezone=True = TIMESTAMPTZ trong PostgreSQL
    # QUAN TRỌNG: lưu kèm timezone info → tránh bug khi server đổi múi giờ
    # PostgreSQL tự đổi sang UTC khi lưu, tự đổi lại khi đọc

    avg_speed    = Column(Float)     # km/h thực tế từ API
    congestion_level = Column(Integer)  # 0=xanh 1=vàng 2=đỏ
    source       = Column(String(20))   # "tomtom" | "goong" | "simulated"

    __table_args__ = (
        # DB-level constraints — không cần validate trong Python
        CheckConstraint("avg_speed >= 0", name="check_avg_speed_positive"),
        CheckConstraint("congestion_level IN (0, 1, 2)", name="check_congestion_valid"),

        # Composite index → query "traffic mới nhất của từng đoạn đường" siêu nhanh
        # Không có index: O(n) scan toàn bảng
        # Có index: O(log n) B-tree search
        Index("idx_traffic_street_seg_time", "street_id", "segment_idx", "timestamp"),
    )
```

---

## 🟢 PHẦN 3: SCHEMAS (Pydantic)

### Tại Sao Cần Schema Riêng?

```
ORM Model (models/)     ≠    Pydantic Schema (schemas/)
      │                              │
      ▼                              ▼
Ánh xạ bảng DB               Định hình JSON API
Có geometry (binary)         Không expose geometry
Có relationship              Flatten thành dict
Dùng nội bộ                 Expose ra ngoài
```

### `schemas/traffic.py`

```python
class TrafficCurrentOut(BaseModel):
    """Dữ liệu traffic của 1 tuyến đường — trả về trong API response."""

    street_id: int
    street_name: str
    district_name: Optional[str] = None

    avg_speed: Optional[float] = None    # None = chưa có data
    max_speed: Optional[int] = None
    congestion_level: Optional[int] = None  # 0/1/2 hoặc None
    congestion_label: Optional[str] = None  # "Thông thoáng" / "Chậm" / "Kẹt xe"

    source: Optional[str] = None        # "tomtom" | "goong"
    timestamp: Optional[datetime] = None
    timestamp_vn: Optional[str] = None  # "2026-04-21 23:00:00 +07:00" (đã format)

    lat: Optional[float] = None   # Tọa độ điểm giữa (fallback ScatterplotLayer)
    lon: Optional[float] = None

    path: Optional[list] = None   # [[lon,lat], ...] — cho đường chỉ có 1 zone
    segments: list[dict] = []     # [{segment_idx, path, color, speed}, ...]

    model_config = ConfigDict(from_attributes=True)  # Cho phép tạo từ ORM object


class TrafficSummaryOut(BaseModel):
    """Tổng hợp toàn thành phố — bao gồm stats và danh sách đường."""

    total_streets: int
    green_count: int     # Số đường xanh (congestion=0)
    yellow_count: int    # Số đường vàng (congestion=1)
    red_count: int       # Số đường đỏ (congestion=2)
    no_data_count: int   # Số đường chưa có data
    avg_speed_city: Optional[float] = None  # Tốc độ TB toàn TP
    data_as_of: Optional[datetime] = None   # Timestamp mới nhất trong data
    streets: list[TrafficCurrentOut]        # Danh sách chi tiết từng đường
```

---

## 🟡 PHẦN 4: ROUTERS (HTTP Endpoints)

### `routers/healthy.py` — Endpoint Kiểm Tra

```python
@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    # Kiểm tra PostgreSQL
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))  # Query đơn giản nhất
    except Exception as e:
        db_status = f"error: {e}"

    # Kiểm tra Redis
    redis_status = "ok"
    try:
        redis_client.ping()
    except Exception as e:
        redis_status = f"error: {e}"

    overall = "ok" if (db_status == "ok" and redis_status == "ok") else "degraded"
    return {"status": overall, "db": db_status, "redis": redis_status}
```

**Tại sao không dùng `raise HTTPException`?**
Vì health check endpoint **KHÔNG BAO GIỜ được trả về 500**. Monitor/alerting hệ thống cần đọc JSON để biết service nào lỗi. Nếu throw 500, monitor không phân biệt được DB lỗi hay Redis lỗi.

---

### `routers/streets.py` — CRUD Tuyến Đường

```python
@router.get("/streets", response_model=StreetListOut)
def get_streets(
    district_id: Optional[int] = Query(None),
    name: Optional[str]        = Query(None),
    page: int                  = Query(1, ge=1),        # ge=1: phải >= 1
    page_size: int             = Query(20, ge=1, le=100), # le=100: tối đa 100
    db: Session = Depends(get_db),
):
    # joinedload = load district trong cùng 1 SQL JOIN (tránh N+1 query)
    # Không có joinedload: 1 query lấy streets + N query lấy district của từng street
    # Có joinedload: 1 query duy nhất với LEFT JOIN
    query = db.query(Street).options(joinedload(Street.district))

    if district_id:
        query = query.filter(Street.district_id == district_id)

    if name:
        # ilike = ILIKE trong SQL = LIKE nhưng case-insensitive
        # f"%{name}%" = tìm bất kỳ chỗ nào trong chuỗi chứa `name`
        query = query.filter(Street.name.ilike(f"%{name}%"))

    total = query.count()  # Đếm trước khi phân trang (cho FE biết tổng)

    # Phân trang: page=2, page_size=10 → bỏ qua 10, lấy 10 tiếp theo
    offset = (page - 1) * page_size
    streets = query.order_by(Street.name).offset(offset).limit(page_size).all()

    return StreetListOut(total=total, page=page, page_size=page_size, data=streets)
```

---

### `routers/traffic.py` — Traffic Real-time (File Quan Trọng Nhất)

#### Luồng GET /api/traffic/current

```
Request: GET /api/traffic/current

        ┌─────────────────────────────────┐
        │ Kiểm tra Redis cache            │
        │ cache_svc.get_traffic()         │
        └──────────────┬──────────────────┘
                       │
              Cache có? (TTL còn?)
             ╱                    ╲
           YES                    NO
            │                     │
     Trả về ngay           Query PostgreSQL
     (~1ms, fast)                 │
                          Lấy latest record
                          cho từng (street, segment)
                                  │
                          Lấy geometry (path)
                          Tính centroid (lat/lon)
                                  │
                          Build TrafficCurrentOut
                          cho từng đường
                                  │
                          Tính stats tổng hợp
                          (green/yellow/red count)
                                  │
                          Lưu vào Redis (TTL=90s)
                                  │
                          Trả về TrafficSummaryOut
```

**Kỹ thuật subquery lấy bản ghi mới nhất:**

```python
# Vấn đề: mỗi đường có nhiều bản ghi traffic (lịch sử)
# → Cần lấy bản ghi MỚI NHẤT của từng (street_id, segment_idx)

# Bước 1: Subquery lấy timestamp mới nhất của mỗi (street, segment)
latest_subq = (
    db.query(
        TrafficData.street_id,
        TrafficData.segment_idx,
        func.max(TrafficData.timestamp).label("max_ts"),  # MAX() = mới nhất
    )
    .filter(TrafficData.street_id.in_(street_ids))
    .group_by(TrafficData.street_id, TrafficData.segment_idx)  # Nhóm theo cặp
    .subquery()
)

# Bước 2: JOIN để lấy bản ghi đầy đủ tương ứng với timestamp max đó
latest_records = (
    db.query(TrafficData)
    .join(
        latest_subq,
        (TrafficData.street_id  == latest_subq.c.street_id)
        & (TrafficData.segment_idx == latest_subq.c.segment_idx)
        & (TrafficData.timestamp   == latest_subq.c.max_ts),  # 3 điều kiện JOIN
    )
    .all()
)
```

**SQL tương đương:**
```sql
SELECT td.*
FROM traffic_data td
JOIN (
    SELECT street_id, segment_idx, MAX(timestamp) AS max_ts
    FROM traffic_data
    WHERE street_id IN (1, 2, 3, ...)
    GROUP BY street_id, segment_idx
) latest ON td.street_id = latest.street_id
         AND td.segment_idx = latest.segment_idx
         AND td.timestamp = latest.max_ts;
```

---

## 🔵 PHẦN 5: SERVICES (Business Logic)

### `services/cache.py` — Wrapper Redis

```python
# TTL = Time-To-Live (thời gian tồn tại)
TTL_TRAFFIC_CURRENT = 90    # 90 giây — đủ để không query DB liên tục
                             # trong khi scheduler chạy mỗi 30 phút

def get_traffic() -> list | None:
    """Cache HIT: trả list. Cache MISS: trả None → caller phải query DB."""
    return get_json("traffic:current")

def set_traffic(records: list, ttl: int = 90):
    """Lưu snapshot traffic vào Redis, tự xóa sau `ttl` giây."""
    set_json("traffic:current", records, ttl=ttl)

def invalidate_traffic():
    """Xóa cache ngay — gọi sau khi crawl xong data mới."""
    redis_client.delete("traffic:current")
    # Lần gọi tiếp theo sẽ: cache MISS → query DB → trả data mới → set cache lại
```

**Tại sao cần invalidate sau crawl?**
```
Giả sử TTL = 90s, crawl lúc t=0:
  t=0: Crawl xong → data mới trong DB
  t=1: Request → Cache còn sống → trả data CŨ (hơn 30 phút trước)
  t=90: Cache hết hạn → Request → query DB → trả data mới

→ Không invalidate: user chờ đến 90s mới thấy data mới
→ Có invalidate: user thấy data mới ngay lập tức sau crawl
```

---

### `services/ingestion.py` — Thu Thập Dữ Liệu (Phức Tạp Nhất)

#### Hệ Thống Quota Management

```python
class QuotaTracker:
    """Đếm số API request đã dùng trong ngày, tự reset lúc 00:00."""

    def use(self) -> bool:
        """
        Trả về True nếu còn quota (và tăng count).
        Trả về False nếu đã hết quota.

        Gọi hàm này TRƯỚC MỖI API call:
            if not goong_quota.use():
                return None  # Không gọi API, tránh bị charge/ban
        """
        self._maybe_reset()    # Reset nếu sang ngày mới
        if self.count >= self.limit:
            return False       # Hết quota
        self.count += 1
        return True            # Còn quota, đã tăng count


class MultiKeyQuotaTracker:
    """
    Quản lý NHIỀU TomTom key với cơ chế tự động chuyển key.

    Vấn đề:
        TomTom free tier: 2500 req/ngày/key
        49 đường × 4 zone × 48 lần/ngày = 9408 req/ngày
        → 1 key không đủ!

    Giải pháp:
        3 key × 2500 = 7500 req/ngày
        Khi key A hết → tự chuyển sang key B → rồi C

    TOMTOM_API_KEYS=key1,key2,key3 trong .env
    """

    @property
    def active_key(self) -> str | None:
        """
        Trả về key đang dùng, tự chuyển nếu key hiện tại hết quota.

        Logic:
        1. Lấy key tại vị trí hiện tại
        2. Nếu key này hết quota → _current_idx += 1 → thử key tiếp
        3. Nếu tất cả key đều hết → trả None
        """
```

#### Hàm `fetch_tomtom()` — Source of Truth

```python
def fetch_tomtom(lat: float, lon: float) -> Optional[dict]:
    """
    Gọi TomTom Flow Segment API tại tọa độ (lat, lon).

    Cách TomTom hoạt động:
        → Bạn gửi 1 điểm GPS
        → TomTom tìm đoạn đường gần nhất với điểm đó
        → Trả về tốc độ thực tế + tốc độ free flow của đoạn đó

    Response:
        {
          "avg_speed": 35.0,        # km/h hiện tại
          "free_flow_speed": 60.0,  # km/h khi không kẹt
          "source": "tomtom"
        }
    """
    for attempt in range(n_keys + 1):   # Thử từng key
        api_key = tomtom_quota.active_key  # Lấy key đang active
        if not api_key:
            return None   # Tất cả key đã hết

        resp = requests.get(url, timeout=10)

        if resp.status_code == 429:   # Too Many Requests
            tomtom_quota.mark_exhausted(api_key)
            continue   # Thử key tiếp

        if resp.status_code == 403:   # Forbidden (key sai/bị khóa)
            tomtom_quota.mark_exhausted(api_key)
            continue   # Thử key tiếp

        # Thành công!
        data = resp.json()["flowSegmentData"]
        return {"avg_speed": data["currentSpeed"], "free_flow_speed": data["freeFlowSpeed"]}
```

#### Hàm `calc_congestion_level()` — Logic Tính Màu

```python
def calc_congestion_level(avg_speed: float, max_speed: int) -> int:
    """
    Tính mức độ tắc nghẽn dựa trên tỷ lệ tốc độ thực / tốc độ tối đa.

    Ví dụ đường Lê Duẩn (max_speed=50):
        avg_speed=40: ratio=0.80 → 0 (Xanh, thông thoáng)
        avg_speed=25: ratio=0.50 → 1 (Vàng, chậm)
        avg_speed=15: ratio=0.30 → 2 (Đỏ, kẹt xe)
    """
    ratio = avg_speed / max_speed if max_speed > 0 else 0
    if ratio >= 0.70: return 0   # Xanh: đang chạy >= 70% tốc độ tối đa
    if ratio >= 0.40: return 1   # Vàng: chạy 40-70% tốc độ tối đa
    return 2                      # Đỏ: chạy < 40% tốc độ tối đa
```

#### Hàm `ingest_street()` — Thu Thập 1 Đường

```python
def ingest_street(street: Street, db: Session) -> bool:
    """
    Thu thập và lưu traffic cho 1 đường.

    Quy trình:
    ┌─────────────────────────────────────────────────────┐
    │ 1. Lấy geometry (LINESTRING) từ PostGIS             │
    │    → [[lon,lat], [lon,lat], ..., [lon,lat]]         │
    └────────────────────────┬────────────────────────────┘
                             │
    ┌────────────────────────▼────────────────────────────┐
    │ 2. Chia thành zone ~500m                            │
    │    split_path_into_zones() → [{zone0}, {zone1}, ...]│
    └────────────────────────┬────────────────────────────┘
                             │
    ┌────────────────────────▼────────────────────────────┐
    │ 3. Với mỗi zone:                                    │
    │    a. Lấy midpoint (điểm giữa zone)                 │
    │    b. Gọi TomTom tại midpoint đó                    │
    │    c. Nếu fail → Fallback Goong                     │
    │    d. Tính congestion_level                          │
    │    e. Tạo TrafficData record                        │
    │    f. db.add(record)                                │
    └─────────────────────────────────────────────────────┘
    """
```

---

### `utils/geometry.py` — Chia Đường Thành Zone

```python
ZONE_LENGTH_M = 500   # Mỗi zone = ~500 mét
MAX_ZONES     = 8     # Tối đa 8 zone (kiểm soát quota TomTom)

def split_path_into_zones(coords: list, n_zones=None) -> list[dict]:
    """
    Input:  [[lon,lat], [lon,lat], ..., [lon,lat]]  (N điểm)
    Output: [
        {
          "segment_idx": 0,
          "coords": [[lon,lat], ...],  # Các điểm của zone này
          "mid_lat": 16.054,           # Điểm giữa zone (gửi lên TomTom)
          "mid_lon": 108.202,
        },
        ...
    ]

    Ví dụ đường Bạch Đằng (2.4km, 21 điểm → 5 zone):
    ●─────●─────●─────●─────●
    ▲      ▲     ▲     ▲     ▲
    zone0  1     2     3     4
    Mỗi zone gọi 1 API → 5 màu khác nhau trên bản đồ
    """
```

**Tại sao dùng overlap 1 điểm giữa các zone?**
```
Zone 0: coords[0..4]    ← điểm 4 dùng chung
Zone 1: coords[4..8]    ← điểm 4 và 8 dùng chung
Zone 2: coords[8..12]

→ Không overlap: đường vẽ bị ĐỨT ĐOẠN giữa các zone
→ Có overlap: đường vẽ LIỀN MẠCH (PathLayer Pydeck render đúng)
```

---

### `services/traffic_crawl.py` — Cào Tất Cả Đường 1 Lần

```python
def crawl_all_streets(db: Session) -> dict:
    """
    Dùng chung cho 2 nơi:
    1. POST /api/traffic/crawl     → kích hoạt thủ công
    2. traffic_scheduler.py        → gọi tự động mỗi 30 phút

    Quy trình:
    1. Kiểm tra key TomTom còn không
    2. Xóa bản ghi cũ hơn 2 giờ (tránh DB phình to)
    3. Với MỖI ĐƯỜNG:
       a. Lấy geometry từ PostGIS
       b. split_path_into_zones()
       c. Gọi fetch_tomtom() tại midpoint từng zone
       d. db.add(TrafficData(...))
    4. db.commit() — lưu tất cả cùng lúc
    5. cache_svc.invalidate_traffic() — xóa cache cũ
    6. Trả về dict tổng kết
    """
```

**Tại sao xóa bản ghi cũ hơn 2 giờ?**
```
Scheduler chạy mỗi 30 phút → 48 lần/ngày
Mỗi lần: 49 đường × 4 zone = 196 bản ghi mới

Không xóa → 196 × 48 = 9408 bản ghi/ngày
1 tháng → ~282,000 bản ghi
1 năm   → ~3.4 triệu bản ghi → DB chậm dần

Xóa > 2 giờ → chỉ giữ 4 chu kỳ gần nhất (2h / 30min = 4)
→ DB luôn nhỏ gọn, query nhanh
```

---

### `services/traffic_scheduler.py` — Vòng Lặp Tự Động

```python
def main():
    """
    Entry point chạy như container riêng trong docker-compose.

    Container `scheduler` trong docker-compose.yml:
        command: python services/traffic_scheduler.py
        depends_on: [postgres, redis, backend]
    """
    while True:
        cycle += 1

        db = Session()
        try:
            run_crawl_cycle(db)   # Thu thập + lưu DB + xóa cache
        except Exception as e:
            log.error(f"❌ Lỗi chu kỳ #{cycle}: {e}")
            db.rollback()
        finally:
            db.close()  # Luôn đóng session

        # Ngủ 30 phút
        time.sleep(30 * 60)

# Vì sao không dùng APScheduler hay Celery?
# → Đơn giản hơn, không cần thêm dependency
# → Docker restart container nếu crash → tự recover
# → Đủ cho bài toán 30 phút/lần
```

---

## 🗺️ PHẦN 6: LUỒNG DỮ LIỆU TOÀN HỆ THỐNG

### Luồng Thu Thập (Every 30 min)

```
traffic_scheduler.py
    │
    ├── run_crawl_cycle(db)
    │       │
    │       ├── DELETE traffic_data WHERE timestamp < now - 2h
    │       │
    │       ├── FOR EACH street:
    │       │       │
    │       │       ├── GET geometry FROM PostGIS
    │       │       ├── split_path_into_zones() → [(zone0), (zone1), ...]
    │       │       │
    │       │       └── FOR EACH zone:
    │       │               ├── fetch_tomtom(mid_lat, mid_lon)
    │       │               │       └── [fail] → fetch_goong()
    │       │               ├── calc_congestion_level()
    │       │               └── db.add(TrafficData(...))
    │       │
    │       ├── db.commit()  ← Lưu tất cả 1 lần (atomic)
    │       └── cache_svc.invalidate_traffic()  ← Xóa cache cũ
    │
    └── time.sleep(30 * 60)
```

### Luồng Phục Vụ (Every Request)

```
GET /api/traffic/current
    │
    ├── [Cache HIT] → Redis → return ngay (~1ms)
    │
    └── [Cache MISS] → PostgreSQL
            │
            ├── Query: latest TrafficData cho mỗi (street, segment)
            ├── Query: geometry path của mỗi street
            ├── Query: centroid (lat/lon) của mỗi street
            │
            ├── Build TrafficCurrentOut cho mỗi street:
            │       └── Gán color, path, segments, speed, congestion
            │
            ├── Tính stats: green/yellow/red count, avg_speed_city
            │
            ├── Lưu vào Redis (TTL=90s)
            │
            └── Return TrafficSummaryOut (~50-200ms)
```

---

## 🔧 PHẦN 7: CÁCH MỞ RỘNG

### Thêm Endpoint Mới
```python
# 1. Tạo file routers/predict.py
router = APIRouter()

@router.get("/predict/30min")
def get_prediction(street_id: int, db: Session = Depends(get_db)):
    # Logic dự báo
    ...

# 2. Mount trong main.py
from routers import predict
app.include_router(predict.router, prefix="/api", tags=["Predict"])
```

### Thêm Bảng DB Mới
```python
# 1. Tạo models/my_model.py
class MyModel(Base):
    __tablename__ = "my_table"
    id = Column(Integer, primary_key=True)
    ...

# 2. Import trong models/__init__.py (đúng thứ tự FK)
from .my_model import MyModel

# 3. Tạo migration Alembic
# alembic revision --autogenerate -m "Add my_table"
# alembic upgrade head
```

### Thêm Cache Cho Endpoint Mới
```python
# Trong services/cache.py
def get_predictions(street_id: int) -> list | None:
    return get_json(f"predictions:{street_id}")

def set_predictions(street_id: int, data: list, ttl: int = 300):
    set_json(f"predictions:{street_id}", data, ttl=ttl)

# Trong router
@router.get("/predict/{street_id}")
def predict(street_id: int, db=Depends(get_db)):
    cached = cache_svc.get_predictions(street_id)
    if cached:
        return cached
    # ... tính dự báo
    cache_svc.set_predictions(street_id, result, ttl=300)
    return result
```

### Thêm API Key Mới
```env
# .env — thêm key mới vào danh sách (phân cách dấu phẩy)
TOMTOM_API_KEYS=key1,key2,key3,key4_mới
```
→ Hệ thống tự nhận sau khi restart. Không cần sửa code.

---

## ⚠️ PHẦN 8: NHỮNG LỖI HAY GẶP

### 1. Không commit DB
```python
# ❌ SAI — thêm nhưng không lưu
db.add(record)
# Restart container → mất hết data

# ✅ ĐÚNG
db.add(record)
db.commit()
```

### 2. Quên invalidate cache sau update
```python
# ❌ SAI — crawl xong nhưng user vẫn thấy data cũ
db.commit()
return result

# ✅ ĐÚNG
db.commit()
cache_svc.invalidate_traffic()
return result
```

### 3. Dùng datetime.now() không có timezone
```python
# ❌ SAI — naive datetime (không có timezone info)
timestamp = datetime.now()
# → PostgreSQL lưu sai giờ khi server ở UTC nhưng app ở +07

# ✅ ĐÚNG — aware datetime (có timezone info)
from datetime import timezone, timedelta
TZ_VN = timezone(timedelta(hours=7))
timestamp = datetime.now(TZ_VN)
```

### 4. N+1 Query Problem
```python
# ❌ SAI — 1 query lấy streets + N query lấy district của từng street
streets = db.query(Street).all()
for s in streets:
    print(s.district.name)  # Mỗi dòng này = 1 SQL query riêng!

# ✅ ĐÚNG — 1 query duy nhất với JOIN
streets = db.query(Street).options(joinedload(Street.district)).all()
for s in streets:
    print(s.district.name)  # Không query thêm, đã có sẵn trong memory
```

### 5. Return trước khi set cache (bug cũ đã fix)
```python
# ❌ SAI — set cache là dead code (không bao giờ chạy)
def get_traffic():
    result = build_result()
    return result              # ← hàm kết thúc ở đây
    cache_svc.set_traffic(result)  # ← không bao giờ chạy!

# ✅ ĐÚNG — set cache TRƯỚC khi return
def get_traffic():
    result = build_result()
    cache_svc.set_traffic(result)  # ← chạy trước
    return result                  # ← rồi mới return
```

---

## 📌 QUICK REFERENCE

### Các Lệnh Docker Hay Dùng
```bash
# Xem log backend
docker compose logs -f backend

# Xem log scheduler (traffic crawl)
docker compose logs -f scheduler

# Vào Redis CLI
docker compose exec redis redis-cli

# Restart 1 service
docker compose restart backend

# Rebuild khi đổi requirements.txt
docker compose up --build backend
```

### Các Lệnh Redis Hay Dùng
```bash
127.0.0.1:6379> KEYS *              # Liệt kê tất cả key
127.0.0.1:6379> TTL traffic:current # Kiểm tra còn bao nhiêu giây
127.0.0.1:6379> DEL traffic:current # Xóa cache thủ công
127.0.0.1:6379> DBSIZE              # Tổng số key
127.0.0.1:6379> FLUSHDB             # XÓA TOÀN BỘ (cẩn thận!)
```

### Test API Nhanh (PowerShell)
```powershell
# Health check
Invoke-RestMethod http://localhost:8000/api/health

# Traffic toàn TP
Invoke-RestMethod http://localhost:8000/api/traffic/current

# Kích crawl ngay
Invoke-RestMethod -Method Post http://localhost:8000/api/traffic/crawl

# Xem trạng thái crawl
Invoke-RestMethod http://localhost:8000/api/traffic/crawl/status
```
