# 📋 CHI TIẾT TASK TỪNG SPRINT — TRÁNH XUNG ĐỘT

> **Nguyên tắc chống xung đột:**
> - Mỗi người **sở hữu** một nhóm file/module cố định (xem bảng FILE OWNERSHIP bên dưới)
> - Không ai chỉnh sửa file của người khác khi chưa hỏi
> - Mọi **interface/contract** (API endpoint, schema DB, function signature) được thỏa thuận trước khi code
> - Dùng nhánh `feature/S<sprint>-<id>-<tên-ngắn>` — 1 nhánh / 1 task

---

## 🗂️ FILE OWNERSHIP — AI SỞ HỮU FILE NÀO

| Thư mục / File | Người A (BE) | Người B (FE) | Người C (DATA) |
|---|:---:|:---:|:---:|
| `backend/routers/*.py` | ✅ chính | ❌ | ❌ |
| `backend/services/*.py` | ✅ chính | ❌ | 🤝 AI service |
| `backend/models/*.py` (SQLAlchemy) | ✅ chính | ❌ | ❌ |
| `backend/auth/*.py` | ✅ chính | ❌ | ❌ |
| `backend/ingestion/*.py` | ✅ chính | ❌ | 🤝 validate |
| `ml/` | ❌ | ❌ | ✅ chính |
| `frontend/pages/*.py` | ❌ | ✅ chính | ❌ |
| `frontend/components/*.py` | ❌ | ✅ chính | ❌ |
| `docker-compose.yml` | 🤝 review | ❌ | ✅ chính |
| `docker/Dockerfile.*` | 🤝 review | ❌ | ✅ chính |
| `tests/` | 🤝 viết test BE | ❌ | ✅ chính |
| `docs/` | ❌ | 🤝 | ✅ chính |
| `.env.example` | 🤝 | ❌ | ✅ chính |

> 🤝 = cộng tác, cần báo trước khi chỉnh sửa

---

## 📌 CONTRACT GIỮA CÁC NGƯỜI — THỎA THUẬN TRƯỚC KHI CODE

Các interface này **phải thống nhất vào đầu mỗi sprint** để A, B, C làm song song không chờ nhau:

### Tuần 0 (Sprint 0 — trước khi bắt đầu)

```yaml
# Mỗi API endpoint mà B cần gọi → A phải đồng ý trước
GET  /api/traffic/current        → trả về List[TrafficRecord]
POST /api/auth/login             → nhận {email, password}, trả {access_token}
GET  /api/predict/30min          → trả về List[PredictedRecord]
POST /api/incidents              → nhận {location, type}, trả {id}
GET  /api/routes?from=X&to=Y     → trả về {primary_route, alt_route}
POST /api/community/report       → nhận {lat, lng, severity}
```

```python
# Schema chung (dùng Pydantic, đặt trong backend/schemas.py — NGƯỜI A tạo trước)
class TrafficRecord(BaseModel):
    road_id: int
    road_name: str
    lat: float
    lng: float
    speed: float          # km/h
    congestion_level: int # 1=xanh, 2=vàng, 3=đỏ
    updated_at: datetime
```

---

# ═══════════════════════════════════════
# SPRINT 1 — Nền tảng & Bản đồ (Tuần 1–2)
# ═══════════════════════════════════════

## TASK #1 — Docker Compose Setup
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S1-01-docker-setup`  
**File chính:** `docker-compose.yml`, `docker/Dockerfile.backend`, `docker/Dockerfile.frontend`

### Description
Tạo môi trường Docker chạy toàn bộ stack: PostgreSQL + FastAPI + Redis + Streamlit. Đây là nền tảng cho mọi người. Khi task này xong, A và B mới có thể chạy code của mình.

### Chú ý không xung đột
- C là **người duy nhất** chỉnh `docker-compose.yml` trong Sprint 1
- A và B **không được** tự thêm service vào docker-compose — báo C để C thêm

### Subtasks
- [ ] **S1-01a**: Tạo file `docker-compose.yml` với 4 service: `db`, `redis`, `backend`, `frontend`
  ```yaml
  services:
    db:
      image: postgis/postgis:15-3.3
      environment:
        POSTGRES_DB: traffic_db
        POSTGRES_USER: ${DB_USER}
        POSTGRES_PASSWORD: ${DB_PASS}
      ports: ["5432:5432"]
      volumes: ["pgdata:/var/lib/postgresql/data"]
    redis:
      image: redis:7-alpine
      ports: ["6379:6379"]
    backend:
      build: ./docker/Dockerfile.backend
      ports: ["8000:8000"]
      depends_on: [db, redis]
      env_file: .env
    frontend:
      build: ./docker/Dockerfile.frontend
      ports: ["8501:8501"]
      depends_on: [backend]
  volumes:
    pgdata:
  ```
- [ ] **S1-01b**: Viết `docker/Dockerfile.backend` cho FastAPI
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY backend/requirements.txt .
  RUN pip install -r requirements.txt
  COPY backend/ .
  CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
  ```
- [ ] **S1-01c**: Viết `docker/Dockerfile.frontend` cho Streamlit
  ```dockerfile
  FROM python:3.11-slim
  WORKDIR /app
  COPY frontend/requirements.txt .
  RUN pip install -r requirements.txt
  COPY frontend/ .
  CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
  ```
- [ ] **S1-01d**: Test `docker-compose up --build` thành công, tất cả 4 container `healthy`
- [ ] **S1-01e**: Viết script `scripts/reset_db.sh` để reset DB khi dev

### Definition of Done
```
✅ docker-compose up --build → 4 container xanh
✅ localhost:5432 kết nối được (pgAdmin)
✅ localhost:6379 ping OK (redis-cli)
✅ localhost:8000 trả về JSON
✅ localhost:8501 load Streamlit
```

---

## TASK #2 — .env Config
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S1-02-env-config` (merge cùng PR với #1)  
**File chính:** `.env.example`, `.gitignore`

### Description
Tạo template file `.env.example` chứa TẤT CẢ biến môi trường mà cả 3 người cần. `.env` thật không được push lên Git.

### Subtasks
- [ ] **S1-02a**: Tạo `.env.example`
  ```env
  # Database
  DB_USER=traffic_user
  DB_PASS=your_password_here
  DB_HOST=db
  DB_PORT=5432
  DB_NAME=traffic_db

  # Redis
  REDIS_HOST=redis
  REDIS_PORT=6379

  # API Keys
  TOMTOM_API_KEY=your_tomtom_key
  GOONG_API_KEY=your_goong_key
  OPENWEATHER_API_KEY=your_openweather_key

  # JWT
  JWT_SECRET_KEY=change_this_to_random_string
  JWT_ALGORITHM=HS256
  JWT_EXPIRE_HOURS=8

  # Backend
  BACKEND_URL=http://backend:8000
  ```
- [ ] **S1-02b**: Đảm bảo `.gitignore` có `.env` (không phải `.env.example`)
- [ ] **S1-02c**: Gửi file `.env` thật (có key thật) qua Zalo cho 2 người còn lại

### Definition of Done
```
✅ .env.example commit lên Git
✅ .env KHÔNG xuất hiện trong git status
✅ Cả 3 người chạy được docker-compose với .env thật
```

---

## TASK #3 — Health Check Endpoint
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S1-03-health-check`  
**File chính:** `backend/main.py`, `backend/routers/health.py`

### Description
Endpoint `/health` đơn giản xác nhận FastAPI + DB + Redis đang hoạt động. Đây là endpoint B sẽ dùng để kiểm tra backend có sẵn không.

### Chú ý không xung đột
- A tạo `backend/main.py` như template, B **không** động vào file này
- B chỉ gọi API qua `httpx`, không sửa backend code

### Subtasks
- [ ] **S1-03a**: Tạo cấu trúc thư mục backend
  ```
  backend/
  ├── main.py            ← A sở hữu
  ├── config.py          ← A sở hữu (đọc .env)
  ├── database.py        ← A sở hữu (SQLAlchemy engine)
  ├── routers/
  │   └── health.py      ← A sở hữu
  ├── models/            ← A sở hữu
  ├── schemas.py         ← A sở hữu (Pydantic, CHIA SẺ với B)
  ├── auth/              ← A sở hữu
  └── services/          ← A + C sở hữu theo module
  ```
- [ ] **S1-03b**: Viết `backend/config.py` đọc biến từ `.env` dùng `pydantic-settings`
  ```python
  from pydantic_settings import BaseSettings
  class Settings(BaseSettings):
      db_user: str; db_pass: str; db_host: str = "db"
      db_port: int = 5432; db_name: str = "traffic_db"
      redis_host: str = "redis"; redis_port: int = 6379
      jwt_secret_key: str; jwt_algorithm: str = "HS256"
      class Config:
          env_file = ".env"
  settings = Settings()
  ```
- [ ] **S1-03c**: Viết `backend/database.py` kết nối PostgreSQL
- [ ] **S1-03d**: Viết `backend/routers/health.py`
  ```python
  @router.get("/health")
  async def health_check(db: Session = Depends(get_db)):
      db.execute(text("SELECT 1"))  # test DB
      redis_client.ping()            # test Redis
      return {"status": "ok", "db": "ok", "redis": "ok"}
  ```
- [ ] **S1-03e**: Mount router vào `main.py` + bật CORS (để Streamlit gọi được)
- [ ] **S1-03f**: Viết `backend/schemas.py` với `TrafficRecord` schema — **thông báo cho B** khi xong

### Definition of Done
```
✅ GET localhost:8000/health → {"status": "ok", "db": "ok", "redis": "ok"}
✅ GET localhost:8000/docs → Swagger UI mở được
✅ schemas.py đã commit và B đã xem
```

---

## TASK #4 — Seed Data 50 Đường Đà Nẵng
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S1-04-seed-data`  
**File chính:** `backend/models/road.py`, `backend/scripts/seed_data.py`

### Description
Tạo bảng `roads` trong DB với 50 tuyến đường Đà Nẵng thật (tên đường, tọa độ GPS). Đây là dữ liệu nền mà C cần để generate mock traffic, và B cần để hiển thị bản đồ.

### Chú ý không xung đột
- A viết model `Road` → C và B dùng nhưng **không sửa**
- C generate mock traffic dựa trên `road_id` từ bảng này → phải chờ task này xong
- Chạy `seed_data.py` một lần khi init DB, không chạy lại

### Subtasks
- [ ] **S1-04a**: Viết `backend/models/road.py`
  ```python
  class Road(Base):
      __tablename__ = "roads"
      id = Column(Integer, primary_key=True)
      name = Column(String(200), nullable=False)
      district = Column(String(100))
      lat = Column(Float, nullable=False)   # tọa độ trung tâm đường
      lng = Column(Float, nullable=False)
      length_km = Column(Float)
      is_one_way = Column(Boolean, default=False)
      # PostGIS geometry (cho A* graph)
      geom = Column(Geometry("LINESTRING", srid=4326), nullable=True)
  ```
- [ ] **S1-04b**: Viết `backend/scripts/seed_data.py` với 50 tuyến đường thật
  - Bao gồm các quận: Hải Châu, Thanh Khê, Sơn Trà, Ngũ Hành Sơn, Liên Chiểu, Cẩm Lệ
  - Mỗi đường có lat/lng GPS thực tế (có thể copy từ Google Maps + Goong)
  - Ví dụ: Đường Nguyễn Văn Linh, Lê Duẩn, Hùng Vương, Điện Biên Phủ...
- [ ] **S1-04c**: Viết Alembic migration tạo bảng `roads`
- [ ] **S1-04d**: Test seed: `python scripts/seed_data.py` → `SELECT COUNT(*) FROM roads` = 50
- [ ] **S1-04e**: Tạo `GET /api/roads` endpoint trả danh sách roads → **thông báo B** để dùng cho dropdown tìm kiếm

### Definition of Done
```
✅ Bảng roads có 50 bản ghi
✅ GET /api/roads → JSON 50 đường, mỗi đường có id, name, lat, lng, district
✅ Đủ đường từ ít nhất 4 quận khác nhau
```

---

## TASK #5 — Mock Traffic Data
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S1-05-mock-traffic`  
**File chính:** `backend/services/mock_traffic.py`, `backend/models/traffic_record.py`

### Description
Tạo service sinh dữ liệu giao thông giả lập cho 50 đường. Cần task #4 xong trước (cần `road_id`). Dữ liệu mock này là fallback khi TomTom chết và là nguồn dữ liệu dev cho B.

### Chú ý không xung đột
- C viết `mock_traffic.py` — **chỉ trong thư mục `services/`**, không đụng `routers/`
- A viết endpoint `GET /api/traffic/current` gọi service này → C và A phải thống nhất function signature

### Subtasks
- [ ] **S1-05a**: Tạo model `TrafficRecord` (bảng DB lưu traffic snapshot)
  ```python
  class TrafficRecord(Base):
      __tablename__ = "traffic_records"
      id = Column(Integer, primary_key=True)
      road_id = Column(Integer, ForeignKey("roads.id"))
      speed = Column(Float)            # km/h hiện tại
      congestion_level = Column(Integer)  # 1, 2, 3
      recorded_at = Column(DateTime, default=datetime.utcnow)
      source = Column(String(20), default="mock")  # "tomtom", "goong", "mock"
  ```
- [ ] **S1-05b**: Viết `generate_mock_traffic(road_ids: List[int]) -> List[dict]`
  - Giờ cao điểm (7-9h, 17-19h) → tỷ lệ đỏ cao hơn
  - Giờ bình thường → tỷ lệ xanh cao hơn
  - Random seed có thể set để test deterministic
- [ ] **S1-05c**: Viết `save_traffic_batch(records: List[dict]) -> None` — lưu vào DB
- [ ] **S1-05d**: Thông báo A: "C đã xong mock_traffic.py, function signature là..."
- [ ] **S1-05e**: A viết `GET /api/traffic/current` gọi mock khi TomTom chưa có
  ```python
  # A viết trong backend/routers/traffic.py
  @router.get("/traffic/current", response_model=List[schemas.TrafficRecord])
  async def get_current_traffic(db: Session = Depends(get_db)):
      records = traffic_service.get_latest_traffic(db)
      if not records:
          records = mock_traffic.generate_mock_traffic(road_ids)
      return records
  ```

### Definition of Done
```
✅ GET /api/traffic/current → trả List[TrafficRecord] với 50 bản ghi
✅ Mỗi record có road_name, lat, lng, congestion_level (1/2/3)
✅ Chạy lại nhiều lần → dữ liệu thay đổi (không phải static)
```

---

## TASK #6 — Bản đồ Nền Pydeck
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S1-06-base-map`  
**File chính:** `frontend/pages/home.py`, `frontend/components/map_view.py`

### Description
Hiển thị bản đồ Đà Nẵng bằng Pydeck trên Streamlit. **Không cần** gọi backend thật — dùng mock data hardcode từ file JSON để làm độc lập. Sau khi A xong `GET /api/traffic/current` thì thay thế.

### Chú ý không xung đột
- B tạo `frontend/components/map_view.py` — **chỉ** làm việc trong `frontend/`
- B **không** thay đổi bất kỳ file backend nào
- Dùng `BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")` để gọi API — dễ thay đổi sau

### Subtasks
- [ ] **S1-06a**: Tạo cấu trúc thư mục frontend
  ```
  frontend/
  ├── app.py              ← B sở hữu (main entrypoint)
  ├── pages/
  │   ├── home.py         ← B sở hữu (bản đồ real-time)
  │   ├── predict.py      ← B sở hữu (dự báo)
  │   └── admin/          ← B sở hữu (giao diện admin)
  ├── components/
  │   ├── map_view.py     ← B sở hữu
  │   ├── kpi_cards.py    ← B sở hữu
  │   └── sidebar.py      ← B sở hữu
  ├── utils/
  │   └── api_client.py   ← B sở hữu (tập trung gọi backend)
  └── assets/
      └── style.css       ← B sở hữu
  ```
- [ ] **S1-06b**: Tạo `frontend/utils/api_client.py` — tập trung mọi lời gọi API
  ```python
  import httpx, os
  BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
  
  def get_traffic_current():
      """Gọi GET /api/traffic/current. Trả [] nếu lỗi."""
      try:
          r = httpx.get(f"{BACKEND_URL}/api/traffic/current", timeout=5)
          r.raise_for_status()
          return r.json()
      except Exception:
          return []  # Fallback: trả list rỗng, FE tự xử lý
  ```
- [ ] **S1-06c**: Viết `frontend/components/map_view.py`
  - Dùng `pydeck.ScatterplotLayer` cho các chấm màu
  - Map style: Goong dark mode `https://tiles.goong.io/...`
  - Center: Đà Nẵng (lat=16.054, lng=108.202, zoom=12)
  - Mock data trong khi chờ backend: đọc từ `assets/mock_traffic.json`
- [ ] **S1-06d**: Tạo `assets/mock_traffic.json` với 10 điểm mẫu đủ 3 màu Đỏ/Vàng/Xanh
- [ ] **S1-06e**: Dùng Streamlit `st.pydeck_chart()` render bản đồ trong `home.py`
- [ ] **S1-06f**: Sau khi A xong endpoint (task #3/#5): thay mock JSON bằng `api_client.get_traffic_current()`

### Definition of Done
```
✅ localhost:8501 → bản đồ đà nẵng hiện ra
✅ Có ít nhất 10 chấm: đỏ, vàng, xanh
✅ Bản đồ có thể zoom/pan
✅ Chỉ dùng Streamlit + Pydeck, KHÔNG dùng React/JS thêm
```

---

## TASK #7 — Màu Đỏ/Vàng/Xanh (Congestion Colors)
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S1-07-congestion-colors` (PR chung với #6)  
**File chính:** `frontend/components/map_view.py`

### Description
Mỗi chấm trên bản đồ có màu theo mức kẹt xe: Đỏ (kẹt nặng), Vàng (chậm), Xanh (thông thoáng). Logic màu dựa trên `congestion_level` từ API.

### Subtasks
- [ ] **S1-07a**: Định nghĩa hằng số màu trong `frontend/components/map_view.py`
  ```python
  CONGESTION_COLORS = {
      1: [0, 200, 83, 200],    # Xanh lá - thông thoáng
      2: [255, 193, 7, 200],   # Vàng - chậm
      3: [244, 67, 54, 220],   # Đỏ - kẹt nặng
  }
  ```
- [ ] **S1-07b**: Map `congestion_level` → màu trong `DataFrame` trước khi truyền vào Pydeck
  ```python
  df["color"] = df["congestion_level"].map(CONGESTION_COLORS)
  ```
- [ ] **S1-07c**: `ScatterplotLayer` dùng `get_fill_color="color"`, radius dựa trên mức kẹt
- [ ] **S1-07d**: Thêm legend màu vào sidebar: `🔴 Kẹt nặng | 🟡 Chậm | 🟢 Thông thoáng`

### Definition of Done
```
✅ Chấm đỏ = congestion_level 3, vàng = 2, xanh = 1
✅ Legend màu hiển thị ở sidebar
✅ Radius chấm đỏ > vàng > xanh (visualize severity)
```

---

## TASK #8 — Tooltip Tên Đường
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S1-08-map-tooltip` (PR chung với #6, #7)  
**File chính:** `frontend/components/map_view.py`

### Description
Hover chuột vào chấm → hiện tên đường, tốc độ hiện tại, mức kẹt.

### Subtasks
- [ ] **S1-08a**: Config Pydeck tooltip
  ```python
  tooltip={
      "html": "<b>{road_name}</b><br/>Mức kẹt: {congestion_label}<br/>Tốc độ: {speed} km/h",
      "style": {"background": "rgba(0,0,0,0.8)", "color": "white", "border-radius": "8px"}
  }
  ```
- [ ] **S1-08b**: Thêm cột `congestion_label` vào DataFrame
  ```python
  CONGESTION_LABELS = {1: "🟢 Thông thoáng", 2: "🟡 Chậm", 3: "🔴 Kẹt nặng"}
  df["congestion_label"] = df["congestion_level"].map(CONGESTION_LABELS)
  ```

### Definition of Done
```
✅ Hover vào chấm → hiện tooltip có tên đường + tốc độ + mức kẹt
✅ Tooltip có styling, không phải default browser
```

---

## TASK #9 — 3 KPI Metric Cards
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S1-09-kpi-cards`  
**File chính:** `frontend/components/kpi_cards.py`, `frontend/pages/home.py`

### Description
3 thẻ KPI ở đầu trang: tổng số đường đang kẹt, % tuyến thông thoáng, tốc độ trung bình toàn thành phố.

### Subtasks
- [ ] **S1-09a**: Viết `frontend/components/kpi_cards.py`
  ```python
  def render_kpi_cards(traffic_data: list):
      total = len(traffic_data)
      jammed = sum(1 for r in traffic_data if r["congestion_level"] == 3)
      free = sum(1 for r in traffic_data if r["congestion_level"] == 1)
      avg_speed = sum(r["speed"] for r in traffic_data) / max(total, 1)
      
      col1, col2, col3 = st.columns(3)
      col1.metric("🔴 Đường kẹt nặng", jammed, help="Số tuyến congestion_level=3")
      col2.metric("🟢 Đường thông thoáng", f"{free/total*100:.0f}%")
      col3.metric("⚡ Tốc độ TB", f"{avg_speed:.0f} km/h")
  ```
- [ ] **S1-09b**: Gọi `render_kpi_cards()` ở đầu `home.py` trước `st.pydeck_chart()`
- [ ] **S1-09c**: Styling card: background glassmorphism, text white, số liệu nổi bật

### Definition of Done
```
✅ 3 metric hiển thị trên 1 hàng ở đầu trang
✅ Số liệu tính đúng từ traffic_data
✅ Ẩn delta khi chưa có dữ liệu lịch sử
```

---

## TASK #10 — Nút Làm Mới
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S1-10-refresh-button` (PR chung với #9)  
**File chính:** `frontend/pages/home.py`

### Description
Nút "🔄 Làm mới" để user tự trigger fetch lại dữ liệu traffic từ backend.

### Subtasks
- [ ] **S1-10a**: Thêm nút vào `home.py`
  ```python
  col_btn, col_time = st.columns([1, 3])
  if col_btn.button("🔄 Làm mới", key="btn_refresh"):
      st.cache_data.clear()  # xóa cache cũ
      st.rerun()
  col_time.caption(f"Cập nhật lúc: {datetime.now().strftime('%H:%M:%S')}")
  ```
- [ ] **S1-10b**: Dùng `@st.cache_data(ttl=60)` cho hàm gọi API để tránh gọi liên tục

### Definition of Done
```
✅ Bấm nút → dữ liệu reload và timestamp cập nhật
✅ Không bấm nút → cache 60s, không gọi API liên tục
```

---

## TASK #11 — Dark Mode + Footer
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S1-11-dark-mode`  
**File chính:** `frontend/assets/style.css`, `frontend/app.py`

### Description
Dark mode CSS injection cho Streamlit và footer thông tin nhóm ở cuối trang.

### Subtasks
- [ ] **S1-11a**: Viết `frontend/assets/style.css`
  ```css
  /* Dark mode override Streamlit */
  .stApp { background-color: #0D1117 !important; color: #E6EDF3; }
  .stMetric { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 16px; }
  div[data-testid="metric-container"] { border: 1px solid rgba(255,255,255,0.1); }
  ```
- [ ] **S1-11b**: Load CSS trong `app.py` bằng `st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)`
- [ ] **S1-11c**: Thêm footer component
  ```python
  st.markdown("---")
  st.caption("🚦 AI Traffic Prediction Đà Nẵng | Nhóm 3 | PTIT 2026")
  ```

### Definition of Done
```
✅ Nền trang tối (không phải trắng Streamlit mặc định)
✅ Card metric có background semi-transparent
✅ Footer hiển thị ở cuối trang
```

---

## TASK #12 — Loading Spinner
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S1-12-loading-spinner` (PR chung với #11)  
**File chính:** `frontend/pages/home.py`

### Description
Hiển thị spinner khi đang tải dữ liệu backend để UX tốt hơn.

### Subtasks
- [ ] **S1-12a**: Wrap lời gọi API bằng `st.spinner`
  ```python
  with st.spinner("⏳ Đang tải dữ liệu giao thông..."):
      traffic_data = api_client.get_traffic_current()
  ```
- [ ] **S1-12b**: Nếu `traffic_data` rỗng → hiện `st.warning("⚠️ Không lấy được dữ liệu. Đang dùng cache.")`

### Definition of Done
```
✅ Spinner hiện khi tải, tắt khi xong
✅ Có thông báo lỗi thân thiện nếu backend chưa sẵn
```

---

# ═══════════════════════════════════════
# SPRINT 2 — Dữ liệu Thực & Tìm kiếm (Tuần 3–4)
# ═══════════════════════════════════════

## TASK #13 — Scheduler TomTom API
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S2-13-tomtom-scheduler`  
**File chính:** `backend/services/ingestion.py`, `backend/main.py`

### Description
Gọi TomTom Flow API mỗi 60 giây để lấy dữ liệu traffic thật và lưu vào DB. Thay thế mock data bằng dữ liệu thật.

### Chú ý không xung đột
- A viết `ingestion.py` trong `services/` — C không đụng vào file này
- C đã viết `validate_record()` trong task #17 → A **gọi** hàm đó, không tự viết validation

### Subtasks
- [ ] **S2-13a**: Nghiên cứu TomTom Flow API endpoint
  ```
  GET https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json
      ?key={TOMTOM_API_KEY}
      &point={lat},{lng}
      &unit=KMPH
  ```
- [ ] **S2-13b**: Viết `backend/services/ingestion.py`
  ```python
  class TomTomIngestionService:
      async def fetch_road_traffic(self, road: Road) -> dict | None:
          """Gọi TomTom API cho 1 tuyến đường. Return None nếu lỗi."""
      
      async def ingest_all_roads(self, db: Session) -> dict:
          """Gọi fetch cho tất cả 50 đường. Return {"success": N, "failed": M}"""
  ```
- [ ] **S2-13c**: Tích hợp `APScheduler` vào FastAPI startup
  ```python
  # backend/main.py
  from apscheduler.schedulers.asyncio import AsyncIOScheduler
  scheduler = AsyncIOScheduler()
  
  @app.on_event("startup")
  async def startup():
      scheduler.add_job(ingestion_service.ingest_all_roads, "interval", seconds=60, args=[db])
      scheduler.start()
  ```
- [ ] **S2-13d**: Lưu kết quả vào bảng `traffic_records` (dùng hàm C đã viết)
- [ ] **S2-13e**: Test: chạy 2 phút → bảng `traffic_records` có dữ liệu `source="tomtom"`

### Definition of Done
```
✅ Mỗi 60s → có bản ghi mới trong traffic_records với source="tomtom"
✅ Log in/out tổng số thành công/thất bại
✅ Không crash khi 1 đường bị lỗi (try/except từng road)
```

---

## TASK #14 — Redis Cache
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S2-14-redis-cache`  
**File chính:** `backend/services/cache.py`

### Description
Cache kết quả traffic vào Redis với TTL 90s. Endpoint `/api/traffic/current` ưu tiên đọc từ Redis trước khi query DB.

### Chú ý không xung đột
- A viết `cache.py` trong `services/` — không ảnh hưởng file nào của B hay C
- B gọi `/api/traffic/current` như cũ — không cần biết có cache hay không

### Subtasks
- [ ] **S2-14a**: Viết `backend/services/cache.py`
  ```python
  import redis, json
  
  class CacheService:
      def __init__(self): self.r = redis.Redis(host=settings.redis_host)
      
      def get_traffic(self) -> list | None:
          data = self.r.get("traffic:current")
          return json.loads(data) if data else None
      
      def set_traffic(self, records: list, ttl: int = 90):
          self.r.setex("traffic:current", ttl, json.dumps(records))
      
      def get_api_call_count(self) -> int:
          return int(self.r.get("api:tomtom:count") or 0)
      
      def increment_api_count(self):
          self.r.incr("api:tomtom:count")
          self.r.expire("api:tomtom:count", 86400)  # reset mỗi ngày
  ```
- [ ] **S2-14b**: Cập nhật `GET /api/traffic/current` dùng cache
  ```python
  cached = cache_service.get_traffic()
  if cached: return cached
  # else: query DB và cache lại
  ```
- [ ] **S2-14c**: Test: dùng `redis-cli MONITOR` xem key được set/get đúng

### Definition of Done
```
✅ Lần gọi đầu → query DB, set Redis
✅ Lần gọi tiếp theo (trong 90s) → từ Redis, không query DB
✅ Kiểm tra bằng: gọi 10 lần liên tục, DB log chỉ 1 query
```

---

## TASK #15 — Fallback Khi API Lỗi
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S2-15-api-fallback` (PR chung với #14)  
**File chính:** `backend/services/ingestion.py`

### Description
Khi TomTom API trả lỗi hoặc hết quota → trả về dữ liệu từ Redis cache cũ. Frontend hiện badge "Dữ liệu có thể cũ".

### Subtasks
- [ ] **S2-15a**: Thêm field `data_freshness` vào response
  ```python
  # backend/routers/traffic.py
  cached = cache_service.get_traffic()
  if cached:
      return {"records": cached, "freshness": "fresh", "source": "cache"}
  db_records = get_latest_from_db(db)
  if db_records:
      return {"records": db_records, "freshness": "stale", "source": "db"}
  return {"records": generate_mock(), "freshness": "mock", "source": "mock"}
  ```
- [ ] **S2-15b**: Cập nhật `schemas.py` với `TrafficResponse` model mới — **thông báo B**
- [ ] **S2-15c**: B xử lý `freshness` field để hiện badge (task #24 liên quan)

### Definition of Done
```
✅ Tắt TomTom (đổi API key sai) → response vẫn trả dữ liệu
✅ Response có "freshness": "stale" khi dùng cache cũ
✅ Response có "freshness": "mock" khi dùng mock data
```

---

## TASK #16 — Auto Chuyển Goong
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S2-16-goong-failover` (PR chung với #13, #15)  
**File chính:** `backend/services/ingestion.py`

### Description
Khi TomTom lỗi 3 lần liên tiếp → tự động chuyển sang Goong Maps API để lấy dữ liệu.

### Subtasks
- [ ] **S2-16a**: Thêm biến đếm lỗi vào Redis
  ```python
  def record_api_failure(self, api_name: str):
      key = f"api:{api_name}:failures"
      count = self.r.incr(key)
      self.r.expire(key, 300)  # reset sau 5 phút
      return count
  ```
- [ ] **S2-16b**: Logic chuyển đổi trong `ingestion.py`
  ```python
  async def get_traffic_data(self, road: Road) -> dict | None:
      tomtom_failures = cache.get_failure_count("tomtom")
      if tomtom_failures >= 3:
          return await self.fetch_from_goong(road)
      try:
          return await self.fetch_from_tomtom(road)
      except Exception:
          cache.record_api_failure("tomtom")
          return await self.fetch_from_goong(road)
  ```
- [ ] **S2-16c**: Viết `fetch_from_goong()` với Goong Directions API
- [ ] **S2-16d**: Log rõ nguồn dữ liệu: `source = "tomtom" | "goong" | "mock"`

### Definition of Done
```
✅ Đổi TOMTOM_API_KEY sai → sau 3 lần thất bại → tự động dùng Goong
✅ log hiển thị "Switching to Goong API"
✅ traffic_records có source="goong"
```

---

## TASK #17 — Validate Dữ Liệu
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S2-17-data-validation`  
**File chính:** `backend/services/validate.py`

### Description
Hàm kiểm tra dữ liệu từ API trước khi lưu vào DB. Lọc bỏ record ngoài phạm vi Đà Nẵng, speed âm, thiếu field bắt buộc.

### Chú ý không xung đột
- C viết `validate.py` trong `services/` — **độc lập hoàn toàn** với file của A
- A **gọi** `validate_record()` trong `ingestion.py` nhưng không sửa validate.py

### Subtasks
- [ ] **S2-17a**: Viết `backend/services/validate.py`
  ```python
  DANANG_BBOX = {"lat_min": 15.9, "lat_max": 16.2, "lng_min": 107.9, "lng_max": 108.4}
  
  def validate_record(record: dict) -> tuple[bool, str]:
      """Return (is_valid, reason). Reason rỗng nếu valid."""
      if record.get("speed", -1) < 0:
          return False, "speed_negative"
      if record.get("congestion_level") not in [1, 2, 3]:
          return False, "invalid_congestion_level"
      lat, lng = record.get("lat"), record.get("lng")
      if not (DANANG_BBOX["lat_min"] <= lat <= DANANG_BBOX["lat_max"] and
              DANANG_BBOX["lng_min"] <= lng <= DANANG_BBOX["lng_max"]):
          return False, "out_of_danang_bounds"
      return True, ""
  
  def validate_batch(records: list) -> tuple[list, list]:
      """Return (valid_records, invalid_records)"""
  ```
- [ ] **S2-17b**: Viết unit test cho `validate_record`
  ```python
  # tests/test_validate.py
  def test_negative_speed(): assert validate_record({"speed": -5, ...})[0] == False
  def test_out_of_bounds(): ...
  def test_valid_record(): assert validate_record({...})[0] == True
  ```
- [ ] **S2-17c**: Thông báo A: "validate.py đã xong, function signature là `validate_record(dict) -> (bool, str)`"

### Definition of Done
```
✅ validate_record() trả (True, "") cho record hợp lệ
✅ 100% test cases pass
✅ A đã tích hợp vào ingestion.py
```

---

## TASK #18 — Tìm kiếm Tên Đường
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S2-18-road-search`  
**File chính:** `frontend/components/sidebar.py`, `frontend/utils/api_client.py`

### Description
Selectbox tìm kiếm tên đường + bản đồ fly-to tới vị trí đường đó. Cần A xong `GET /api/roads` (task #4).

### Chú ý không xung đột
- B chỉ gọi `GET /api/roads` — không sửa backend
- B thêm function vào `api_client.py`, không tạo file mới

### Subtasks
- [ ] **S2-18a**: Thêm `get_roads()` vào `api_client.py`
  ```python
  @st.cache_data(ttl=3600)  # cache 1 tiếng vì roads ít thay đổi
  def get_roads():
      r = httpx.get(f"{BACKEND_URL}/api/roads")
      return r.json() if r.status_code == 200 else []
  ```
- [ ] **S2-18b**: Thêm selectbox tìm kiếm vào sidebar
  ```python
  roads = api_client.get_roads()
  road_names = ["-- Chọn đường --"] + [r["name"] for r in roads]
  selected = st.selectbox("🔍 Tìm đường", road_names, key="road_search")
  ```
- [ ] **S2-18c**: Khi chọn đường → update `st.session_state.map_center` để bản đồ fly-to
  ```python
  if selected != "-- Chọn đường --":
      road = next(r for r in roads if r["name"] == selected)
      st.session_state["map_center"] = {"lat": road["lat"], "lng": road["lng"], "zoom": 15}
  ```
- [ ] **S2-18d**: `map_view.py` đọc `st.session_state.map_center` để cập nhật view state Pydeck

### Definition of Done
```
✅ Selectbox tìm kiếm có tất cả 50 đường
✅ Chọn đường → bản đồ zoom đến đường đó
✅ Xóa chọn → bản đồ trở về view Đà Nẵng tổng thể
```

---

## TASK #19 — Lọc Theo Mức Kẹt
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S2-19-congestion-filter` (PR chung với #18)  
**File chính:** `frontend/components/sidebar.py`, `frontend/pages/home.py`

### Description
Checkbox/multiselect cho user chọn hiển thị đường nào theo mức kẹt (Xanh/Vàng/Đỏ).

### Subtasks
- [ ] **S2-19a**: Thêm multiselect vào sidebar
  ```python
  st.markdown("### 🎚️ Lọc mức kẹt")
  show_levels = st.multiselect(
      "Hiển thị mức kẹt",
      options=[1, 2, 3],
      default=[1, 2, 3],
      format_func=lambda x: {1: "🟢 Thông thoáng", 2: "🟡 Chậm", 3: "🔴 Kẹt nặng"}[x],
      key="filter_congestion"
  )
  ```
- [ ] **S2-19b**: Filter DataFrame trước khi truyền vào `map_view`
  ```python
  df_filtered = df[df["congestion_level"].isin(show_levels)]
  map_view.render_map(df_filtered)
  ```
- [ ] **S2-19c**: KPI cards cũng cập nhật theo filter

### Definition of Done
```
✅ Bỏ chọn "Xanh" → các chấm xanh biến mất khỏi bản đồ
✅ KPI cards cập nhật theo filter
✅ Không bị lag khi filter (dùng st.session_state tốt)
```

---

## TASK #20 — Lọc Theo Quận
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S2-20-district-filter` (PR chung với #18, #19)

### Description
Selectbox lọc bản đồ theo quận Đà Nẵng.

### Subtasks
- [ ] **S2-20a**: Thêm `district` selectbox vào sidebar
  ```python
  districts = ["Tất cả"] + sorted(set(r["district"] for r in roads))
  selected_district = st.selectbox("📍 Quận/Huyện", districts, key="filter_district")
  ```
- [ ] **S2-20b**: Filter DataFrame theo district
  ```python
  if selected_district != "Tất cả":
      df_filtered = df_filtered[df_filtered["district"] == selected_district]
  ```
- [ ] **S2-20c**: Khi chọn quận → bản đồ tự zoom vào quận đó (cập nhật viewState)

### Definition of Done
```
✅ Chọn quận Hải Châu → chỉ hiện đường ở Hải Châu
✅ Bản đồ zoom tự động vào quận
```

---

## TASK #21 — Nút Reset Bộ Lọc
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S2-21-reset-filter` (PR chung với #18-20)

### Subtasks
- [ ] **S2-21a**: Thêm nút Reset
  ```python
  if st.button("⟳ Reset bộ lọc", key="btn_reset_filter"):
      st.session_state["filter_congestion"] = [1, 2, 3]
      st.session_state["filter_district"] = "Tất cả"
      st.session_state["road_search"] = "-- Chọn đường --"
      st.rerun()
  ```

### Definition of Done
```
✅ Bấm Reset → tất cả bộ lọc về mặc định, bản đồ hiện toàn Đà Nẵng
```

---

## TASK #22 — Auto-Refresh 60 Giây
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S2-22-auto-refresh`  
**File chính:** `frontend/pages/home.py`

### Description
Trang tự động reload dữ liệu mỗi 60s mà không cần user bấm nút.

### Subtasks
- [ ] **S2-22a**: Cài `streamlit-autorefresh`
  ```bash
  pip install streamlit-autorefresh
  ```
- [ ] **S2-22b**: Thêm vào `home.py`
  ```python
  from streamlit_autorefresh import st_autorefresh
  count = st_autorefresh(interval=60_000, limit=None, key="auto_refresh")
  ```
- [ ] **S2-22c**: Hiện đồng hồ đếm ngược: "Cập nhật tiếp theo trong Xs"
  ```python
  seconds_to_next = 60 - (time.time() % 60)
  st.caption(f"⏰ Tự động cập nhật sau {int(seconds_to_next)}s")
  ```

### Definition of Done
```
✅ Sau 60s → trang refresh, dữ liệu mới tải
✅ Không phá vỡ trạng thái filter (session_state giữ nguyên)
```

---

## TASK #23 — Cảnh Báo Ngân Sách API
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S2-23-api-budget-alert`  
**File chính:** `backend/services/monitor.py`

### Description
Theo dõi số lần gọi TomTom API/ngày. Khi đạt 80% quota → log warning. Khi đạt 100% → tự switch sang mock.

### Chú ý không xung đột
- C viết `monitor.py` — A **không** viết file này
- C dùng Redis client (cùng instance với A) — dùng key prefix `monitor:` để tránh xung đột

### Subtasks
- [ ] **S2-23a**: Viết `backend/services/monitor.py`
  ```python
  TOMTOM_DAILY_LIMIT = 2500
  
  class APIMonitor:
      def check_budget(self) -> dict:
          count = cache.get_api_call_count()
          pct = count / TOMTOM_DAILY_LIMIT * 100
          return {"count": count, "limit": TOMTOM_DAILY_LIMIT, "pct": pct,
                  "status": "critical" if pct >= 100 else "warning" if pct >= 80 else "ok"}
      
      def log_budget_status(self):
          status = self.check_budget()
          if status["status"] == "warning":
              logger.warning(f"TomTom API {status['pct']:.0f}% quota used")
          elif status["status"] == "critical":
              logger.error("TomTom API quota EXHAUSTED - switching to mock")
  ```
- [ ] **S2-23b**: Thêm `GET /api/monitor/budget` endpoint (A viết router, C viết logic)
- [ ] **S2-23c**: Gọi `log_budget_status()` sau mỗi lần ingest thành công

### Definition of Done
```
✅ GET /api/monitor/budget → {"count": N, "pct": X, "status": "ok/warning/critical"}
✅ Log warning khi >80% quota
✅ Budget tự reset mỗi ngày lúc 0h (Redis TTL = 86400s)
```

---

## TASK #24 — Gợi Ý Khi Không Có Data (Empty State)
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S2-24-empty-state` (PR chung với #22)

### Description
Khi không có dữ liệu (backend lỗi, mock trống) → hiện UI friendly thay vì trang trắng.

### Subtasks
- [ ] **S2-24a**: Kiểm tra `freshness` field từ API response
  ```python
  response = api_client.get_traffic()
  if response["freshness"] == "stale":
      st.warning("⚠️ Đang dùng dữ liệu cũ. TomTom API có thể gặp sự cố.")
  elif response["freshness"] == "mock":
      st.info("ℹ️ Đang hiển thị dữ liệu mô phỏng. Kết nối API chưa sẵn sàng.")
  ```
- [ ] **S2-24b**: Khi `records` hoàn toàn rỗng → hiện empty state
  ```python
  if not records:
      st.markdown("### 😶 Không có dữ liệu")
      st.markdown("Hệ thống đang khởi động hoặc không kết nối được backend.")
      st.button("🔄 Thử lại", on_click=lambda: st.cache_data.clear())
  ```

---

# ═══════════════════════════════════════
# SPRINT 3 — AI Dự báo & Xác thực (Tuần 5–6)
# ═══════════════════════════════════════

> ⚡ **2 luồng hoàn toàn độc lập** — A và C không đụng file nhau trong Sprint này.

## TASK #25 — Train Random Forest Model
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S3-25-train-model`  
**File chính:** `ml/train.py`, `ml/features.py`, `ml/models/rf_model.pkl`

### Description
Huấn luyện mô hình Random Forest dự báo mức kẹt xe 30 phút tới cho từng tuyến đường.

### Chú ý không xung đột
- Toàn bộ thư mục `ml/` là của C — A và B không đụng vào
- C export model ra `ml/models/rf_model.pkl` → A load file này trong API (task #26)
- A và C thỏa thuận **input/output format** của model TRƯỚC KHI code

### Input/Output Contract (thỏa thuận từ đầu sprint)
```python
# Input features cho model (C và A cùng thống nhất)
FEATURES = [
    "hour",          # giờ trong ngày (0-23)
    "day_of_week",   # thứ (0=Thứ 2, 6=CN)
    "is_weekend",    # boolean
    "is_rush_hour",  # boolean (7-9h, 17-19h)
    "current_congestion",  # mức kẹt hiện tại (1,2,3)
    "current_speed",       # tốc độ hiện tại
    "road_length",         # km
    "district_encoded",    # label encoded
    # LƯU Ý: Đã bỏ weather_temp, weather_rain vì chưa có nguồn thu thập dữ liệu thời tiết
    "avg_speed_1h_ago",    # tốc độ trung bình 1h trước
    "avg_speed_yesterday"  # tốc độ cùng giờ ngày hôm qua
]

# Output: congestion_level 30 phút tới (1, 2, hoặc 3)
```

### Subtasks
- [ ] **S3-25a**: Tạo dataset từ `traffic_records` DB (ít nhất 1 tuần dữ liệu mock)
  ```python
  # ml/prepare_dataset.py
  def build_training_data(db_session) -> pd.DataFrame:
      """Query traffic_records, tính features, tạo label (target = congestion sau 30p)"""
  ```
- [ ] **S3-25b**: Viết `ml/features.py` — tính toán tất cả features
- [ ] **S3-25c**: Train & tune Random Forest
  ```python
  from sklearn.ensemble import RandomForestClassifier
  from sklearn.model_selection import GridSearchCV
  
  param_grid = {"n_estimators": [100, 200], "max_depth": [5, 10, None]}
  model = GridSearchCV(RandomForestClassifier(), param_grid, cv=5, scoring="f1_weighted")
  model.fit(X_train, y_train)
  ```
- [ ] **S3-25d**: Lưu model và scaler
  ```python
  import joblib
  joblib.dump(model.best_estimator_, "ml/models/rf_model.pkl")
  joblib.dump(scaler, "ml/models/scaler.pkl")
  ```
- [ ] **S3-25e**: Ghi kết quả metrics vào `ml/models/metrics.json`
  ```json
  {"accuracy": 0.82, "f1_weighted": 0.81, "rmse": 6.4, "trained_at": "2026-05-15T10:00:00"}
  ```

### Definition of Done
```
✅ ml/models/rf_model.pkl tồn tại và load được
✅ F1 score > 0.70 trên test set
✅ metrics.json có đủ thông tin
✅ Notebook Jupyter giải thích feature importance
```

---

## TASK #26 — API Dự Báo 30 Phút
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S3-26-predict-api`  
**File chính:** `backend/services/prediction_service.py`, (A viết router)

### Description
Service load model và tạo dự báo. A viết endpoint, C viết business logic.

### Chú ý không xung đột
- C viết `prediction_service.py` trong `backend/services/`
- A viết `backend/routers/predict.py` — gọi service của C
- Không overlap: C viết service, A viết router

### Subtasks
- [ ] **S3-26a (C)**: Viết `backend/services/prediction_service.py`
  ```python
  class PredictionService:
      def __init__(self):
          self.reload_model() # Hỗ trợ hot reload cho Task 29
          
      def reload_model(self):
          self.model = joblib.load("ml/models/rf_model.pkl")
          self.scaler = joblib.load("ml/models/scaler.pkl")
      
      def predict(self, road_id: int, db: Session) -> dict:
          """Tạo dự báo cho 1 tuyến đường. Return {"road_id", "predicted_level", "confidence"}"""
      
      def predict_all(self, db: Session) -> List[dict]:
          """Dự báo cho tất cả 50 đường"""
  ```
- [ ] **S3-26b (A)**: Viết `backend/routers/predict.py`
  ```python
  @router.get("/predict/30min", response_model=List[schemas.PredictedRecord])
  async def predict_30min(db: Session = Depends(get_db)):
      return prediction_service.predict_all(db)
  ```
- [ ] **S3-26c**: Thêm `PredictedRecord` schema vào `schemas.py` (A viết, thông báo B)

### Definition of Done
```
✅ GET /api/predict/30min → List với predicted_level, confidence mỗi đường
✅ Response time < 2s
✅ Không crash khi model file chưa có (return lỗi 503 với message thân thiện)
```

---

## TASK #27 — Toggle Bản Đồ Dự Báo
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S3-27-predict-toggle`  
**File chính:** `frontend/pages/home.py`, `frontend/components/map_view.py`

### Description
Toggle switch chuyển đổi giữa "Xem thực tế" và "Dự báo 30p". Cần task #26 xong.

### Subtasks
- [ ] **S3-27a**: Thêm toggle vào sidebar
  ```python
  show_prediction = st.toggle("🔮 Xem dự báo 30 phút", key="show_prediction")
  ```
- [ ] **S3-27b**: Thêm `get_predictions()` vào `api_client.py`
- [ ] **S3-27c**: Dựa vào toggle, truyền data khác vào `map_view`
  ```python
  if show_prediction:
      data = api_client.get_predictions()
      st.info("📡 Đang xem dự báo giao thông 30 phút tới")
  else:
      data = api_client.get_traffic_current()
  map_view.render_map(data)
  ```
- [ ] **S3-27d**: Thêm thanh chú thích "DỰ BÁO" màu tím để phân biệt với thực tế
  ```python
  # Màu dự báo: tím thay vì đỏ
  PREDICT_COLORS = {1: [0, 200, 83, 180], 2: [156, 39, 176, 180], 3: [74, 0, 224, 200]}
  ```

### Definition of Done
```
✅ Toggle → màu bản đồ chuyển từ {xanh/vàng/đỏ} sang {xanh/tím nhạt/tím đậm}
✅ Banner "Đang xem DỰ BÁO" hiện rõ
✅ Toggle về "Thực tế" → màu bản đồ bình thường
```

---

## TASK #28 — Chỉ Số AI (RMSE, F1)
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S3-28-ai-metrics` (PR chung với #25)  
**File chính:** `backend/routers/admin.py` (A viết router), `backend/services/prediction_service.py`

### Description
Hiển thị metrics của model trên trang Admin.

### Subtasks
- [ ] **S3-28a (C)**: Thêm method `get_model_metrics()` vào `prediction_service.py`
  ```python
  def get_model_metrics(self) -> dict:
      with open("ml/models/metrics.json") as f:
          return json.load(f)
  ```
- [ ] **S3-28b (A)**: Thêm `GET /api/admin/ai-metrics` vào admin router
- [ ] **S3-28c (B)**: Hiển thị metrics trên trang Admin (task #35 liên quan)

---

## TASK #29 — Retrain Tự Động
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S3-29-auto-retrain`  
**File chính:** `ml/train.py`, `backend/main.py`

### Description
Mỗi 24h → tự động retrain model với dữ liệu mới nhất thu thập được.

### Subtasks
- [ ] **S3-29a**: Wrap logic train vào hàm `retrain_model(db_session)` (Lưu ý: Quá trình này tốn CPU)
- [ ] **S3-29b**: Thêm scheduled job trong `backend/main.py` (chỉ báo A để A thêm vào startup)
  ```python
  # A thêm vào startup event. QUAN TRỌNG: Phải dùng executor để không block luồng chính của FastAPI!
  scheduler.add_job(prediction_service.retrain, "cron", hour=2, minute=0, executor='processpool')  # 2h sáng
  ```
- [ ] **S3-29c**: Sau retrain → gọi `self.reload_model()` để cập nhật model mới (hot reload không cần restart)
- [ ] **S3-29d**: Ghi log: "Model retrained at 02:01, new F1=0.83"

---

## TASK #30 — Đăng Nhập JWT
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S3-30-jwt-login`  
**File chính:** `backend/auth/jwt.py`, `backend/routers/auth.py`

### Description
Login endpoint, tạo JWT token cho user. Luồng độc lập với luồng AI của C.

### Chú ý không xung đột
- A viết toàn bộ `backend/auth/` — C không đụng vào
- B viết UI login (`frontend/pages/login.py`) — không đụng vào backend auth

### Subtasks
- [ ] **S3-30a**: Tạo model `User` trong DB
  ```python
  class User(Base):
      __tablename__ = "users"
      id = Column(Integer, primary_key=True)
      email = Column(String, unique=True, nullable=False)
      hashed_password = Column(String, nullable=False)
      role = Column(String(20), default="viewer")  # "admin", "csgt", "viewer"
      is_active = Column(Boolean, default=True)
      failed_attempts = Column(Integer, default=0)
      locked_until = Column(DateTime, nullable=True)
  ```
- [ ] **S3-30b**: Viết `backend/auth/jwt.py`
  ```python
  def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
      ...
  def verify_token(token: str) -> dict | None:
      ...
  ```
- [ ] **S3-30c**: Viết `POST /api/auth/login`
  ```python
  @router.post("/auth/login")
  def login(credentials: LoginRequest, db: Session = Depends(get_db)):
      user = authenticate_user(db, credentials.email, credentials.password)
      if not user: raise HTTPException(401, "Invalid credentials")
      token = create_access_token({"sub": user.email, "role": user.role})
      return {"access_token": token, "token_type": "bearer"}
  ```
- [ ] **S3-30d**: Seed 2 user test: `admin@test.com/Admin123` và `csgt@test.com/Csgt123`
- [ ] **S3-30e**: Thông báo B: "Login API done. Request: {email, password}. Response: {access_token}"

### Definition of Done
```
✅ POST /api/auth/login với đúng credentials → {access_token}
✅ POST /api/auth/login với sai credentials → 401
✅ Token decode ra được {sub, role, exp}
```

---

## TASK #31 — Phân Quyền 2 Role
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S3-31-rbac` (PR chung với #30)

### Subtasks
- [ ] **S3-31a**: Viết dependency `require_role(roles: List[str])`
  ```python
  def require_role(*roles):
      def checker(current_user = Depends(get_current_user)):
          if current_user.role not in roles:
              raise HTTPException(403, "Insufficient permissions")
          return current_user
      return checker
  ```
- [ ] **S3-31b**: Bảo vệ admin endpoints
  ```python
  @router.get("/admin/users", dependencies=[Depends(require_role("admin"))])
  ```
- [ ] **S3-31c**: Test: csgt token → truy cập admin endpoint → 403

---

## TASK #32 — Mã Hóa Bcrypt
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S3-32-bcrypt` (PR chung với #30)

### Subtasks
- [ ] **S3-32a**: Dùng `passlib[bcrypt]` — không tự implement hash
  ```python
  from passlib.context import CryptContext
  pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
  def verify_password(plain, hashed): return pwd_context.verify(plain, hashed)
  def hash_password(plain): return pwd_context.hash(plain)
  ```

---

## TASK #33 — Khóa Tài Khoản Brute Force
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S3-33-brute-force` (PR chung với #30-#32)

### Subtasks
- [ ] **S3-33a**: Logic kiểm tra và ghi nhận đăng nhập sai
  ```python
  MAX_FAILED = 5
  LOCK_MINUTES = 15
  
  def handle_failed_login(user: User, db: Session):
      user.failed_attempts += 1
      if user.failed_attempts >= MAX_FAILED:
          user.locked_until = datetime.utcnow() + timedelta(minutes=LOCK_MINUTES)
      db.commit()
  ```
- [ ] **S3-33b**: Kiểm tra lock trước khi xử lý login
  ```python
  if user.locked_until and user.locked_until > datetime.utcnow():
      remaining = (user.locked_until - datetime.utcnow()).seconds // 60
      raise HTTPException(429, f"Account locked. Try again in {remaining} minutes")
  ```

---

## TASK #34 — Đăng Xuất Session
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S3-34-logout` (PR chung với #30-#33)

### Subtasks
- [ ] **S3-34a**: JWT blacklist bằng Redis
  ```python
  def blacklist_token(jti: str, exp: int):
      ttl = exp - int(datetime.utcnow().timestamp())
      redis_client.setex(f"blacklist:{jti}", ttl, "1")
  
  def is_blacklisted(jti: str) -> bool:
      return redis_client.exists(f"blacklist:{jti}") > 0
  ```
- [ ] **S3-34b**: Thêm `jti` (JWT ID) vào payload token
- [ ] **S3-34c**: Endpoint `POST /api/auth/logout` → thêm token vào blacklist

---

## TASK #35 — Trang Login UI
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S3-35-login-page`  
**File chính:** `frontend/pages/login.py`

### Subtasks
- [ ] **S3-35a**: Tạo `frontend/pages/login.py` với form đăng nhập
  ```python
  def render_login():
      st.title("🔐 Đăng nhập Hệ thống")
      email = st.text_input("Email", key="login_email")
      password = st.text_input("Mật khẩu", type="password", key="login_pass")
      if st.button("Đăng nhập", key="btn_login"):
          result = api_client.login(email, password)
          if result.get("access_token"):
              st.session_state["token"] = result["access_token"]
              st.session_state["logged_in"] = True
              st.rerun()
          else:
              st.error("❌ Email hoặc mật khẩu không đúng")
  ```
- [ ] **S3-35b**: Kiểm tra `st.session_state["logged_in"]` ở `app.py` để redirect
- [ ] **S3-35c**: Thêm `api_client.login(email, password)` gọi `POST /api/auth/login`
- [ ] **S3-35d**: Nút "Đăng xuất" trên sidebar gọi `POST /api/auth/logout`

### Definition of Done
```
✅ Truy cập trang Admin khi chưa login → redirect về trang Login
✅ Đăng nhập đúng → vào Dashboard
✅ Đăng nhập sai → "Email hoặc mật khẩu không đúng"
✅ Đăng xuất → session_state xóa, về trang Login
```

---

## TASK #36 — Validate Input (SQL Injection Prevention)
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S3-36-input-validation` (PR chung với #30)

### Subtasks
- [ ] **S3-36a**: Đảm bảo 100% query DB dùng ORM hoặc parameterized query — KHÔNG raw SQL với string format
- [ ] **S3-36b**: Thêm Pydantic validation cho tất cả request body (email format, password min length 8)
- [ ] **S3-36c**: Test: gửi `email: "' OR 1=1--"` → 422 Unprocessable Entity, không lỗi DB

---

# ═══════════════════════════════════════
# SPRINT 4 — Tìm đường & Dashboard (Tuần 7–8)
# ═══════════════════════════════════════

## TASK #38 — A* Pathfinding (PAIR: A + C)
**Phân cho:** 🔧 A + 🧪 C (pair programming)  
**Nhánh:** `feature/S4-38-astar-pathfinding`  
**File chính:** `backend/services/routing.py`, `backend/scripts/build_graph.py`

### Description
Thuật toán A* tìm đường ngắn nhất tránh kẹt. Đây là tính năng phức tạp nhất của dự án — **bắt buộc pair**.

### Phân chia trong pair
- **C**: Xây dựng graph từ dữ liệu đường (PostGIS/NetworkX), tính trọng số cạnh
- **A**: Cài đặt A* algorithm, tích hợp vào API endpoint

### Subtasks
- [ ] **S4-38a (C)**: Xây dựng NetworkX graph từ 50 đường
  ```python
  # backend/scripts/build_graph.py
  def build_road_graph(roads: List[Road], traffic: List[TrafficRecord]) -> nx.DiGraph:
      G = nx.DiGraph()
      for road in roads:
          # Weight = length × (1 + congestion_factor)
          congestion_factor = {1: 0, 2: 0.5, 3: 2.0}[road.congestion]
          weight = road.length_km * (1 + congestion_factor)
          G.add_edge(road.start_node, road.end_node, 
                     weight=weight, road_id=road.id, road_name=road.name)
          if not road.is_one_way:
              G.add_edge(road.end_node, road.start_node, weight=weight)
      return G
  ```
- [ ] **S4-38b (A)**: Cài đặt A* dùng NetworkX
  ```python
  def heuristic(node1, node2):
      """Haversine distance giữa 2 node"""
  
  def find_route(graph, from_id: int, to_id: int) -> dict:
      path = nx.astar_path(graph, from_id, to_id, heuristic=heuristic, weight="weight")
      return {"path": path, "total_km": ..., "estimated_minutes": ...}
  ```
- [ ] **S4-38c (A)**: Viết `GET /api/routes?from_road_id=X&to_road_id=Y`
- [ ] **S4-38d (C)**: Cache graph vào Redis (rebuild mỗi 5 phút với traffic mới)
- [ ] **S4-38e**: Integration test: from_id=1, to_id=25 → path không đi qua đường đỏ

---

## TASK #37 — Form Điểm Đi–Đến
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S4-37-route-finder-ui`

### Subtasks
- [ ] **S4-37a**: Tạo trang `frontend/pages/route_finder.py`
- [ ] **S4-37b**: 2 selectbox chọn điểm đi/đến từ danh sách 50 đường
- [ ] **S4-37c**: Nút "🔍 Tìm đường" → gọi `GET /api/routes`
- [ ] **S4-37d**: Hiển thị loading spinner khi đang tính toán

---

## TASK #39 — Đường Thay Thế
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S4-39-alt-route` (PR chung với #38)

### Subtasks
- [ ] **S4-39a**: Loại bỏ K đường đỏ nhất khỏi graph → chạy A* lại → đường thay thế
- [ ] **S4-39b**: Response trả cả `primary_route` lẫn `alt_route`

---

## TASK #40 — Thông Tin Tuyến Đường
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S4-40-route-info` (PR chung với #37)

### Subtasks
- [ ] **S4-40a**: Sidebar panel hiện km + phút + số đường kẹt trên tuyến
- [ ] **S4-40b**: Vẽ PathLayer Pydeck cho tuyến đường chính + tuyến thay thế
  ```python
  path_layer = pdk.Layer("PathLayer",
      data=[{"path": route_coords, "width": 5, "color": [0, 128, 255]}])
  ```

---

## TASK #41 — Ưu Tiên Đường 1 Chiều
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S4-41-oneway` (PR chung với #38)

### Subtasks
- [ ] **S4-41a**: Dùng `DiGraph` (directed) thay vì `Graph` (undirected)
- [ ] **S4-41b**: Field `is_one_way` trong Road model đã có → chỉ thêm cạnh 1 chiều

---

## TASK #43 — Dashboard 4 KPI (CSGT)
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S4-43-csgt-dashboard`

### Subtasks
- [ ] **S4-43a**: Tạo `frontend/pages/admin/dashboard.py`
- [ ] **S4-43b**: 4 KPI: Đường kẹt / API calls hôm nay / Báo cáo cộng đồng / Thời gian uptime
- [ ] **S4-43c**: Chỉ hiện khi user có role "admin" hoặc "csgt"

---

## TASK #44 — Gauge Chart
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S4-44-gauge-chart` (PR chung với #43)

### Subtasks
- [ ] **S4-44a**: Plotly gauge chart hiện % đường kẹt toàn thành phố
  ```python
  fig = go.Figure(go.Indicator(
      mode="gauge+number", value=pct_jammed,
      gauge={"axis": {"range": [0, 100]},
             "bar": {"color": "red" if pct_jammed > 50 else "orange" if pct_jammed > 20 else "green"}}
  ))
  ```

---

## TASK #45 — Biểu Đồ Kẹt Theo Giờ
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S4-45-hourly-chart` (PR chung với #43)

### Subtasks
- [ ] **S4-45a**: `GET /api/stats/hourly` (A viết) → trả avg congestion theo giờ trong ngày
- [ ] **S4-45b**: Plotly histogram/bar chart hiện số đường kẹt theo từng giờ
- [ ] **S4-45c**: Filter theo ngày (hôm nay / hôm qua / tuần này)

---

## TASK #46 — Bảng Top 10 Đường Kẹt Nhất
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S4-46-top10-table` (PR chung với #43)

### Subtasks
- [ ] **S4-46a**: `GET /api/stats/top-congested?limit=10` (A viết)
- [ ] **S4-46b**: Styled DataFrame với màu theo mức kẹt
  ```python
  styled_df = df.style.applymap(color_by_congestion, subset=["Mức kẹt"])
  st.dataframe(styled_df)
  ```

---

## TASK #47 — Điều Động Trên Bản Đồ (PAIR: B + A)
**Phân cho:** 🎨 B + 🔧 A  
**Nhánh:** `feature/S4-47-officer-dispatch`

### Phân chia
- **B**: UI click trên bản đồ → modal xác nhận điều động
- **A**: `PATCH /api/traffic/{road_id}/dispatch` → đổi trạng thái

### Subtasks
- [ ] **S4-47a (B)**: Dùng `st.pydeck_chart(selection_mode="single-object")` để bắt click event
- [ ] **S4-47b (B)**: Khi click đường đỏ → hiện dialog "Điều cảnh sát tới đây?"
- [ ] **S4-47c (A)**: Endpoint `PATCH /api/traffic/{road_id}/dispatch` → lưu `is_dispatched=True`
- [ ] **S4-47d (B)**: Sau dispatch → icon chấm đổi sang dấu ✓

---

## TASK #48 — Thêm Lô Cốt/Sự Kiện (CRUD)
**Phân cho:** 🔧 A (API) + 🎨 B (Form UI)  
**Nhánh:** `feature/S4-48-incident-crud`

### Subtasks
- [ ] **S4-48a (A)**: Model `Incident` trong DB
  ```python
  class Incident(Base):
      __tablename__ = "incidents"
      id = Column(Integer, primary_key=True)
      type = Column(String(50))  # "barricade", "event", "accident"
      road_id = Column(Integer, ForeignKey("roads.id"))
      description = Column(Text)
      start_time = Column(DateTime)
      end_time = Column(DateTime, nullable=True)
      created_by = Column(Integer, ForeignKey("users.id"))
      is_active = Column(Boolean, default=True)
  ```
- [ ] **S4-48b (A)**: CRUD endpoints: `POST/GET/PUT/DELETE /api/incidents`
- [ ] **S4-48c (B)**: Form thêm lô cốt trong trang Admin
- [ ] **S4-48d (B)**: Hiển thị lô cốt trên bản đồ bằng `IconLayer` (icon khác màu)

---

## TASK #51 — Quản Lý Tài Khoản
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S4-51-user-management`

### Subtasks
- [ ] **S4-51a**: `GET /api/admin/users` — danh sách users (admin only)
- [ ] **S4-51b**: `POST /api/admin/users` — tạo user mới
- [ ] **S4-51c**: `PATCH /api/admin/users/{id}/lock` — khóa tài khoản
- [ ] **S4-51d**: `PATCH /api/admin/users/{id}/reset-password` — reset password
- [ ] **S4-51e (B)**: Tạo trang `frontend/pages/admin/user_management.py`

---

## TASK #52 — Xuất CSV
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S4-52-export-csv`

### Subtasks
- [ ] **S4-52a**: `GET /api/export/traffic?date=YYYY-MM-DD` → trả CSV attachment
  ```python
  from fastapi.responses import StreamingResponse
  import io
  
  @router.get("/export/traffic")
  def export_traffic(date: str, db: Session = Depends(get_db)):
      df = get_traffic_by_date(db, date)
      stream = io.StringIO()
      df.to_csv(stream, index=False, encoding="utf-8-sig")
      return StreamingResponse(iter([stream.getvalue()]),
          media_type="text/csv",
          headers={"Content-Disposition": f"attachment; filename=traffic_{date}.csv"})
  ```
- [ ] **S4-52b (B)**: Nút "⬇️ Xuất CSV" trong trang Dashboard với date picker

---

# ═══════════════════════════════════════
# SPRINT 5 — Cộng đồng & Hoàn thiện (Tuần 9–10)
# ═══════════════════════════════════════

## TASK #53 — Báo Cáo Kẹt Người Dân
**Phân cho:** 🔧 A (API) + 🎨 B (UI)  
**Nhánh:** `feature/S5-53-community-report`

### Subtasks
- [ ] **S5-53a (A)**: Model `CommunityReport` + `POST /api/community/report`
  ```python
  class CommunityReport(Base):
      __tablename__ = "community_reports"
      id = Column(Integer, ...); lat = Column(Float); lng = Column(Float)
      severity = Column(Integer)  # 1-3
      description = Column(Text); reported_at = Column(DateTime)
      is_verified = Column(Boolean, default=False)
  ```
- [ ] **S5-53b (B)**: Nút "📍 Báo kẹt tại đây" trong trang người dùng
- [ ] **S5-53c (B)**: Lấy GPS từ browser (HTML5 Geolocation API qua st.components)
  ```python
  # HTML component để lấy GPS
  html_code = """<script>
  navigator.geolocation.getCurrentPosition(function(pos) {
      window.parent.postMessage({lat: pos.coords.latitude, lng: pos.coords.longitude}, "*");
  });
  </script>"""
  st.components.v1.html(html_code, height=0)
  ```

---

## TASK #54 — Auto-Incident Detection
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S5-54-auto-incident`

### Description
Background job phân tích community reports — nếu cùng 1 khu vực có ≥3 báo cáo trong 10 phút → tự động tạo incident.

### Subtasks
- [ ] **S5-54a**: Viết `backend/services/incident_detector.py`
  ```python
  def detect_incidents(db: Session):
      """Chạy mỗi 10 phút. Cluster reports theo Haversine distance < 500m."""
      recent = get_reports_last_10min(db)
      clusters = cluster_reports(recent, max_distance_m=500)
      for cluster in clusters:
          if len(cluster) >= 3:
              create_auto_incident(db, cluster)
  ```
- [ ] **S5-54b**: Thêm scheduled job (báo A để A thêm vào startup)

---

## TASK #55 — Hiển Thị Báo Cáo Cộng Đồng
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S5-55-community-icons`

### Subtasks
- [ ] **S5-55a**: Thêm `IconLayer` Pydeck cho community reports
  ```python
  icon_data = {"url": "https://img.icons8.com/...", "width": 128, "height": 128, "anchorY": 128}
  icon_layer = pdk.Layer("IconLayer", data=reports_df, get_icon="icon_data", get_size=4)
  ```
- [ ] **S5-55b**: Toggle hiện/ẩn community reports layer trong sidebar

---

## TASK #56 — Proximity Alert
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S5-56-proximity-alert`

### Subtasks
- [ ] **S5-56a**: Lấy GPS của user, tính Haversine distance tới các điểm đỏ
- [ ] **S5-56b**: Nếu có đường kẹt trong bán kính 2km → hiện `st.toast("⚠️ Cảnh báo kẹt gần bạn!")`

---

## TASK #57 — Banner Cấm Đường Khẩn Cấp
**Phân cho:** 🔧 A (API) + 🎨 B (Frontend poll)  
**Nhánh:** `feature/S5-57-emergency-banner`

### Subtasks
- [ ] **S5-57a (A)**: `POST /api/admin/emergency-banner` — tạo banner
- [ ] **S5-57b (A)**: `GET /api/emergency-banner` — lấy banner active (public endpoint)
- [ ] **S5-57c (B)**: Poll endpoint mỗi 30s → hiện `st.error()` toàn trang nếu có banner

---

## TASK #58 — Audit Log
**Phân cho:** 🔧 A  
**Nhánh:** `feature/S5-58-audit-log`

### Subtasks
- [ ] **S5-58a**: Tạo bảng `audit_logs`
  ```python
  class AuditLog(Base):
      __tablename__ = "audit_logs"
      id = Column(Integer, primary_key=True)
      user_id = Column(Integer, ForeignKey("users.id"))
      action = Column(String(100))  # "create_incident", "dispatch_officer"...
      resource = Column(String(100)); resource_id = Column(Integer)
      detail = Column(JSON); created_at = Column(DateTime)
  ```
- [ ] **S5-58b**: Viết decorator `@audit_action(action="...")`
  ```python
  def audit_action(action: str):
      def decorator(func):
          async def wrapper(*args, current_user=..., db=..., **kwargs):
              result = await func(*args, **kwargs)
              log = AuditLog(user_id=current_user.id, action=action, ...)
              db.add(log); db.commit()
              return result
          return wrapper
      return decorator
  ```
- [ ] **S5-58c**: Áp dụng decorator cho các endpoint quan trọng: login, dispatch, create_incident, emergency_banner
- [ ] **S5-58d**: `GET /api/admin/audit-logs` — xem log (admin only)

---

## TASK #59 — Unit Tests
**Phân cho:** 🧪 C  
**Nhánh:** `feature/S5-59-unit-tests`

### Subtasks
- [ ] **S5-59a**: Setup pytest
  ```
  tests/
  ├── conftest.py          ← fixtures: test DB, test client
  ├── test_health.py
  ├── test_auth.py
  ├── test_traffic.py
  ├── test_validate.py     ← đã có từ S2-17
  ├── test_predict.py
  └── test_routing.py
  ```
- [ ] **S5-59b**: `conftest.py` dùng SQLite in-memory cho test DB
- [ ] **S5-59c**: Test auth: login đúng/sai, brute force lock, logout
- [ ] **S5-59d**: Test traffic: ingest mock, validate, cache
- [ ] **S5-59e**: Chạy coverage: `pytest --cov=backend --cov-report=html`
  - Target: `> 70%` overall coverage

### Definition of Done
```
✅ pytest → all pass, 0 failed
✅ Coverage report: > 70%
✅ CI có thể chạy pytest tự động (GitHub Actions optional)
```

---

## TASK #60 — Responsive Mobile
**Phân cho:** 🎨 B  
**Nhánh:** `feature/S5-60-responsive`

### Subtasks
- [ ] **S5-60a**: Thêm CSS media queries vào `style.css`
  ```css
  @media (max-width: 768px) {
      .stColumns { flex-direction: column; }
      .stSidebar { display: none; }  /* Hide sidebar on mobile */
  }
  ```
- [ ] **S5-60b**: Test trên Chrome DevTools Mobile view (iPhone 12 Pro, iPad)
- [ ] **S5-60c**: KPI cards stack dọc khi màn hình nhỏ

---

# ═══════════════════════════════════════
# 🛡️ HƯỚNG DẪN TRÁNH XUNG ĐỘT — TÓM TẮT
# ═══════════════════════════════════════

## Rule 1: 1 Task = 1 Nhánh = 1 PR
```bash
# Bắt đầu task mới
git checkout develop
git pull origin develop
git checkout -b feature/S<sprint>-<id>-<tên>

# Kết thúc
git push origin feature/S<sprint>-<id>-<tên>
# → Tạo PR → Request review → Merge
```

## Rule 2: File Ownership (KHÔNG vi phạm)
| Tình huống | Làm gì |
|---|---|
| B cần thêm field vào `schemas.py` (file A sở hữu) | B tạo Issue → A thêm trong sprint đó |
| C cần thêm scheduled job vào `main.py` (file A sở hữu) | C viết hàm trong `services/`, nhắn A thêm 1 dòng vào startup |
| A cần dùng validate của C | A import `from services.validate import validate_record` — không copy code |

## Rule 3: Interface Contract Trước Khi Code
Đầu mỗi sprint, họp 30 phút thống nhất:
- Endpoint URL + method + request/response format
- DB schema thay đổi (migration)
- Function signature cho service gọi cross-module

## Rule 4: Mock Trước, Thật Sau
```
B cần API chưa xong của A → B dùng mock data trong assets/
Khi A xong → B thay 1 dòng trong api_client.py
```

## Rule 5: Key DB Conventions
```python
# Tất cả table đều có:
id = Column(Integer, primary_key=True)
created_at = Column(DateTime, default=datetime.utcnow)
updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

## Rule 6: Redis Key Naming Convention
```
traffic:current          ← cache dữ liệu traffic (A sở hữu)
api:tomtom:count         ← đếm API call (A sở hữu)
api:tomtom:failures      ← đếm lỗi (A sở hữu)
blacklist:{jti}          ← JWT blacklist (A sở hữu)
monitor:*                ← monitoring (C sở hữu)
ml:retrain:last          ← thời gian retrain cuối (C sở hữu)
```

---

*Tài liệu này là phần mở rộng của HUONG_DAN_TRIEN_KHAI.md — cập nhật theo từng Sprint Review.*
