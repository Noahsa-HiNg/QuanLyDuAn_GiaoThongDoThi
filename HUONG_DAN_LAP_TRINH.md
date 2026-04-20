# 📖 HƯỚNG DẪN LẬP TRÌNH — AI Traffic Prediction Đà Nẵng

> Tài liệu này mô tả **cách viết code đúng chuẩn** cho dự án, từ cấu trúc thư mục, cách viết từng loại file, đến quy ước đặt tên và luồng dữ liệu end-to-end.  
> **Đọc kỹ trước khi viết bất kỳ dòng code nào.**

---

## MỤC LỤC

- [1. Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
- [2. Cấu trúc thư mục chuẩn](#2-cấu-trúc-thư-mục-chuẩn)
- [3. Backend — FastAPI](#3-backend--fastapi)
  - [3.1 config.py — Cấu hình](#31-configpy--cấu-hình)
  - [3.2 database.py — Kết nối DB](#32-databasepy--kết-nối-db)
  - [3.3 models/ — Bảng dữ liệu](#33-models--bảng-dữ-liệu)
  - [3.4 schemas/ — Validate dữ liệu API](#34-schemas--validate-dữ-liệu-api)
  - [3.5 services/ — Business logic](#35-services--business-logic)
  - [3.6 routers/ — API Endpoints](#36-routers--api-endpoints)
  - [3.7 main.py — Entry point](#37-mainpy--entry-point)
- [4. Frontend — Streamlit](#4-frontend--streamlit)
  - [4.1 app.py — Entry point](#41-apppy--entry-point)
  - [4.2 pages/ — Các trang](#42-pages--các-trang)
  - [4.3 Gọi API từ Frontend](#43-gọi-api-từ-frontend)
- [5. ML Module](#5-ml-module)
- [6. Quy ước đặt tên](#6-quy-ước-đặt-tên)
- [7. Luồng dữ liệu end-to-end](#7-luồng-dữ-liệu-end-to-end)
- [8. Quản lý thư viện](#8-quản-lý-thư-viện)
- [9. Những lỗi thường gặp & cách tránh](#9-những-lỗi-thường-gặp--cách-tránh)

---

## 1. Tổng quan kiến trúc

```
Người dùng (Browser)
       │  HTTP
       ▼
  ┌─────────┐
  │  Nginx  │  ← Reverse proxy, port 80
  └────┬────┘
       │                    
  ┌────┴─────────────────────────┐
  │                              │
  ▼  /api/*                      ▼  /*
┌──────────┐              ┌──────────────┐
│ Backend  │              │   Frontend   │
│ FastAPI  │ ◄──────────► │  Streamlit   │
│ :8000    │   HTTP/JSON  │  :8501       │
└────┬─────┘              └──────────────┘
     │
  ┌──┴──────────┐
  │             │
  ▼             ▼
┌──────┐   ┌───────┐
│  DB  │   │ Redis │
│ :5432│   │ :6379 │
└──────┘   └───────┘
```

**Nguyên tắc cơ bản:**
- **Frontend** chỉ hiển thị dữ liệu và gọi HTTP API — không kết nối thẳng vào DB
- **Backend** xử lý toàn bộ logic, quyết định trả về gì
- **Nginx** là cổng vào duy nhất — người dùng không truy cập thẳng backend hay frontend

---

## 2. Cấu trúc thư mục chuẩn

```
QuanLyDuAn_GiaoThongDoThi/
│
├── .env                         ← Biến môi trường (KHÔNG commit Git)
├── .gitignore
├── docker-compose.yml
│
├── backend/                     ← FastAPI application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                  ← Entry point: tạo app, mount routers
│   ├── config.py                ← Đọc biến từ .env (dùng pydantic-settings)
│   ├── database.py              ← Tạo engine, SessionLocal, Base
│   │
│   ├── models/                  ← SQLAlchemy ORM models (= bảng DB)
│   │   ├── __init__.py          ← Export tất cả models
│   │   ├── road.py
│   │   ├── traffic_record.py
│   │   └── user.py
│   │
│   ├── schemas/                 ← Pydantic models (validate request/response)
│   │   ├── __init__.py
│   │   ├── traffic.py
│   │   └── user.py
│   │
│   ├── services/                ← Business logic (không biết HTTP tồn tại)
│   │   ├── __init__.py
│   │   ├── traffic_service.py
│   │   ├── mock_traffic.py
│   │   └── cache_service.py
│   │
│   ├── routers/                 ← API endpoints (gọi services, không chứa logic)
│   │   ├── __init__.py
│   │   ├── health.py
│   │   ├── traffic.py
│   │   └── auth.py
│   │
│   ├── ml/                      ← Machine Learning module
│   │   ├── __init__.py
│   │   └── models/              ← File .pkl (model đã train)
│   │
│   └── tests/                   ← Unit tests
│       ├── __init__.py
│       └── test_traffic.py
│
├── frontend/                    ← Streamlit application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                   ← Entry point: cấu hình trang, routing
│   │
│   └── pages/                   ← Mỗi file = 1 trang trong Streamlit
│       ├── home.py              ← Trang chính: bản đồ real-time
│       ├── predict.py           ← Trang dự báo AI
│       └── admin/
│           └── dashboard.py     ← Trang quản trị CSGT
│
└── nginx/
    └── nginx.conf               ← Cấu hình reverse proxy
```

> **Quy tắc vàng:** Mỗi thư mục có **1 mục đích duy nhất**. Không viết logic DB trong router, không viết HTTP call trong service.

---

## 3. Backend — FastAPI

### 3.1 `config.py` — Cấu hình

**Mục đích:** Đọc tất cả biến từ file `.env` vào một object Python duy nhất.  
**Tại sao?** Thay vì gọi `os.environ["POSTGRES_USER"]` rải rác khắp nơi, ta import `settings.db_user` — type-safe, dễ kiểm tra.

```python
# backend/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"   # tên service trong docker-compose
    postgres_port: int = 5432

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    class Config:
        env_file = ".env"          # đọc từ file .env ở thư mục gốc
        case_sensitive = False     # POSTGRES_USER = postgres_user

# Tạo 1 instance duy nhất — import object này ở nơi khác
settings = Settings()
```

**Cách dùng ở nơi khác:**
```python
# Đúng ✅
from config import settings
print(settings.postgres_user)

# Sai ❌ — không dùng os.environ trực tiếp
import os
os.environ["POSTGRES_USER"]
```

---

### 3.2 `database.py` — Kết nối DB

**Mục đích:** Tạo kết nối SQLAlchemy đến PostgreSQL, cung cấp `SessionLocal` cho các router dùng.

```python
# backend/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Chuỗi kết nối PostgreSQL
DATABASE_URL = (
    f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)

# Engine: đối tượng quản lý kết nối DB
engine = create_engine(DATABASE_URL)

# SessionLocal: class để tạo session làm việc với DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base: class cha mà tất cả ORM model phải kế thừa
Base = declarative_base()


def get_db():
    """
    Dependency dùng trong FastAPI router.
    Tự động đóng session sau mỗi request, kể cả khi có lỗi.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

### 3.3 `models/` — Bảng dữ liệu

**Mục đích:** Mỗi class = 1 bảng trong PostgreSQL.  
**Quy tắc:** Chỉ khai báo cấu trúc bảng — không chứa business logic.

```python
# backend/models/road.py
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.sql import func
from database import Base

class Road(Base):
    __tablename__ = "roads"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    district = Column(String(100))
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    length_km = Column(Float, default=0.0)
    is_one_way = Column(Boolean, default=False)

    # Tự động ghi thời gian tạo/cập nhật
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

```python
# backend/models/traffic_record.py
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class TrafficRecord(Base):
    __tablename__ = "traffic_records"

    id = Column(Integer, primary_key=True, index=True)
    road_id = Column(Integer, ForeignKey("roads.id"), nullable=False)
    speed = Column(Float, nullable=False)
    congestion_level = Column(Integer, nullable=False)   # 1, 2, hoặc 3
    source = Column(String(20), default="mock")          # "tomtom", "goong", "mock"
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationship — có thể dùng record.road.name
    road = relationship("Road", back_populates="traffic_records")
```

**`models/__init__.py`** — phải export tất cả models để Alembic phát hiện:
```python
# backend/models/__init__.py
from .road import Road
from .traffic_record import TrafficRecord
from .user import User

# Export để Alembic autogenerate tìm thấy tất cả bảng
__all__ = ["Road", "TrafficRecord", "User"]
```

---

### 3.4 `schemas/` — Validate dữ liệu API

**Mục đích:** Định nghĩa cấu trúc request/response của API.  
**Tại sao tách khỏi models?** ORM model = hình dạng bảng DB. Schema = hình dạng dữ liệu API. Hai cái này thường khác nhau (ví dụ: không bao giờ trả `hashed_password` ra API).

```python
# backend/schemas/traffic.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

# Schema để TẠO bản ghi (nhận từ client)
class TrafficRecordCreate(BaseModel):
    road_id: int
    speed: float = Field(ge=0, le=200, description="Tốc độ km/h, phải từ 0 đến 200")
    congestion_level: int = Field(ge=1, le=3, description="Mức kẹt: 1=xanh, 2=vàng, 3=đỏ")
    source: str = "mock"

# Schema để TRẢ VỀ cho client (response)
class TrafficRecordResponse(BaseModel):
    id: int
    road_id: int
    road_name: str           # join từ bảng Road — không có trong DB trực tiếp
    lat: float
    lng: float
    district: str
    speed: float
    congestion_level: int
    source: str
    recorded_at: datetime

    class Config:
        from_attributes = True   # cho phép đọc từ ORM object

# Schema cho response list với metadata
class TrafficListResponse(BaseModel):
    records: List[TrafficRecordResponse]
    total: int
    freshness: str           # "fresh", "stale", "mock"
    updated_at: datetime
```

**Phân biệt 3 loại schema:**

| Tên hậu tố | Dùng khi | Ví dụ |
|---|---|---|
| `Create` | Nhận dữ liệu từ POST request | `TrafficRecordCreate` |
| `Update` | Nhận dữ liệu từ PATCH request (tất cả optional) | `UserUpdate` |
| `Response` | Trả về cho client | `TrafficRecordResponse` |

---

### 3.5 `services/` — Business Logic

**Mục đích:** Chứa toàn bộ logic nghiệp vụ.  
**Quy tắc quan trọng:**
- Service **không biết** HTTP, request, response tồn tại
- Service **nhận** `db: Session` như tham số — không tự tạo session
- Service **trả về** Python object hoặc raise Exception — không trả `JSONResponse`

```python
# backend/services/traffic_service.py
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from models.traffic_record import TrafficRecord
from models.road import Road
from schemas.traffic import TrafficRecordCreate

class TrafficService:
    
    def get_latest_traffic(self, db: Session) -> List[dict]:
        """
        Lấy bản ghi traffic mới nhất cho mỗi tuyến đường.
        Return list dict với đầy đủ thông tin road + traffic.
        """
        # Subquery: lấy max recorded_at cho mỗi road_id
        from sqlalchemy import func
        subquery = (
            db.query(
                TrafficRecord.road_id,
                func.max(TrafficRecord.recorded_at).label("max_time")
            )
            .group_by(TrafficRecord.road_id)
            .subquery()
        )

        # Join để lấy bản ghi có thời gian khớp với max
        records = (
            db.query(TrafficRecord, Road)
            .join(Road, TrafficRecord.road_id == Road.id)
            .join(subquery, 
                  (TrafficRecord.road_id == subquery.c.road_id) &
                  (TrafficRecord.recorded_at == subquery.c.max_time))
            .all()
        )
        
        return [
            {
                "id": r.TrafficRecord.id,
                "road_id": r.Road.id,
                "road_name": r.Road.name,
                "lat": r.Road.lat,
                "lng": r.Road.lng,
                "district": r.Road.district,
                "speed": r.TrafficRecord.speed,
                "congestion_level": r.TrafficRecord.congestion_level,
                "source": r.TrafficRecord.source,
                "recorded_at": r.TrafficRecord.recorded_at,
            }
            for r in records
        ]

    def save_traffic_batch(self, db: Session, records: List[TrafficRecordCreate]) -> int:
        """
        Lưu nhiều bản ghi traffic cùng lúc.
        Return số bản ghi đã lưu thành công.
        """
        db_records = [TrafficRecord(**r.model_dump()) for r in records]
        db.add_all(db_records)
        db.commit()
        return len(db_records)


# Tạo 1 instance duy nhất để import
traffic_service = TrafficService()
```

**Pattern viết service:**
```python
# ✅ ĐÚNG — nhận db như tham số
def get_roads(self, db: Session) -> List[Road]:
    return db.query(Road).all()

# ❌ SAI — tự tạo session trong service
def get_roads(self) -> List[Road]:
    db = SessionLocal()    # SAI! Ai sẽ đóng session này?
    return db.query(Road).all()
```

---

### 3.6 `routers/` — API Endpoints

**Mục đích:** Định nghĩa URL, method HTTP, nhận request, gọi service, trả response.  
**Quy tắc:** Router chỉ làm 3 việc: (1) nhận input, (2) gọi service, (3) trả output. **Không** chứa logic DB hay business logic.

```python
# backend/routers/traffic.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from schemas.traffic import TrafficListResponse
from services.traffic_service import traffic_service
from services.cache_service import cache_service

# Tạo router với prefix và tags
router = APIRouter(prefix="/api/traffic", tags=["Traffic"])


@router.get("/current", response_model=TrafficListResponse)
async def get_current_traffic(db: Session = Depends(get_db)):
    """
    Lấy dữ liệu giao thông hiện tại cho tất cả tuyến đường.
    Ưu tiên Redis cache, fallback sang DB, cuối cùng dùng mock data.
    """
    # 1. Thử lấy từ cache
    cached = cache_service.get_traffic()
    if cached:
        return {"records": cached, "freshness": "fresh", ...}

    # 2. Gọi service — không viết logic ở đây
    records = traffic_service.get_latest_traffic(db)

    if not records:
        raise HTTPException(status_code=503, detail="Không có dữ liệu giao thông")

    # 3. Lưu vào cache
    cache_service.set_traffic(records)

    return {
        "records": records,
        "total": len(records),
        "freshness": "fresh",
        "updated_at": ...,
    }


@router.get("/road/{road_id}", response_model=TrafficListResponse)
async def get_traffic_by_road(
    road_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Lấy lịch sử traffic của 1 tuyến đường cụ thể."""
    records = traffic_service.get_by_road(db, road_id=road_id, limit=limit)
    if not records:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy đường ID {road_id}")
    return {"records": records, "total": len(records), "freshness": "db", ...}
```

**Cách đặt tên endpoint:**

| Hành động | Method | URL | Ví dụ |
|---|---|---|---|
| Lấy danh sách | `GET` | `/api/roads` | Lấy 50 đường |
| Lấy 1 item | `GET` | `/api/roads/{id}` | Chi tiết đường #5 |
| Tạo mới | `POST` | `/api/incidents` | Tạo lô cốt mới |
| Cập nhật toàn bộ | `PUT` | `/api/incidents/{id}` | Cập nhật lô cốt |
| Cập nhật 1 phần | `PATCH` | `/api/incidents/{id}` | Chỉ đổi trạng thái |
| Xóa | `DELETE` | `/api/incidents/{id}` | Xóa lô cốt |

---

### 3.7 `main.py` — Entry Point

**Mục đích:** Tạo FastAPI app, mount tất cả routers, cấu hình CORS, startup/shutdown events.

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import health, traffic, auth

# Tạo tất cả bảng DB khi khởi động (chỉ dùng khi dev, production dùng Alembic)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI Traffic Prediction API",
    description="API dự báo giao thông đô thị Đà Nẵng",
    version="1.0.0",
)

# CORS — cho phép Streamlit frontend gọi API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://frontend:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers — thứ tự quan trọng nếu có prefix trùng nhau
app.include_router(health.router)
app.include_router(traffic.router)
app.include_router(auth.router)


@app.on_event("startup")
async def startup_event():
    """Chạy khi server khởi động — init scheduler, seed data, etc."""
    print("🚀 Backend đang khởi động...")
    # Khởi động APScheduler nếu cần


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup khi server tắt."""
    print("🛑 Backend đang tắt...")
```

---

## 4. Frontend — Streamlit

### 4.1 `app.py` — Entry Point

**Mục đích:** Cấu hình toàn cục cho Streamlit (tên trang, icon, layout), xử lý routing (hiển thị trang nào).

```python
# frontend/app.py
import streamlit as st
import os

# ════════════════════════════════════════
# CẤU HÌNH TRANG — phải là lệnh đầu tiên
# ════════════════════════════════════════
st.set_page_config(
    page_title="AI Traffic Đà Nẵng",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════
# LOAD CSS GLOBAL
# ════════════════════════════════════════
def load_css():
    css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# ════════════════════════════════════════
# SIDEBAR NAVIGATION
# ════════════════════════════════════════
with st.sidebar:
    st.image("assets/logo.png", width=120)   # logo dự án nếu có
    st.markdown("## 🚦 Giao thông Đà Nẵng")
    st.markdown("---")
    
    page = st.radio(
        "Điều hướng",
        options=["🗺️ Bản đồ Real-time", "🔮 Dự báo AI", "📊 Dashboard CSGT"],
        key="nav_page",
        label_visibility="collapsed",
    )

# ════════════════════════════════════════
# HIỂN THỊ TRANG TƯƠNG ỨNG
# ════════════════════════════════════════
if page == "🗺️ Bản đồ Real-time":
    from pages.home import render_home
    render_home()

elif page == "🔮 Dự báo AI":
    from pages.predict import render_predict
    render_predict()

elif page == "📊 Dashboard CSGT":
    # Kiểm tra login trước
    if not st.session_state.get("logged_in"):
        st.warning("⛔ Bạn cần đăng nhập để xem trang này.")
        from pages.login import render_login
        render_login()
    else:
        from pages.admin.dashboard import render_dashboard
        render_dashboard()
```

---

### 4.2 `pages/` — Các trang

**Mỗi file trong `pages/` là 1 trang.** Mỗi file phải export hàm `render_<tên>()`.

```python
# frontend/pages/home.py
import streamlit as st
import pandas as pd
import pydeck as pdk
from utils.api_client import get_traffic_current

# Màu sắc theo mức kẹt — định nghĩa 1 lần, dùng nhiều nơi
CONGESTION_COLORS = {
    1: [0, 200, 83, 200],    # Xanh — thông thoáng
    2: [255, 193, 7, 200],   # Vàng — chậm
    3: [244, 67, 54, 220],   # Đỏ — kẹt nặng
}
CONGESTION_LABELS = {1: "🟢 Thông thoáng", 2: "🟡 Chậm", 3: "🔴 Kẹt nặng"}


def render_home():
    """Hàm chính của trang Home — được gọi từ app.py."""
    st.title("🗺️ Bản đồ Giao thông Real-time")
    
    # 1. Lấy dữ liệu
    with st.spinner("⏳ Đang tải dữ liệu..."):
        result = get_traffic_current()
    
    records = result.get("records", [])
    freshness = result.get("freshness", "unknown")
    
    # 2. Hiện cảnh báo freshness
    _render_freshness_banner(freshness)
    
    # 3. KPI cards
    _render_kpi_cards(records)
    
    # 4. Sidebar filters
    filtered_records = _render_sidebar_filters(records)
    
    # 5. Bản đồ
    _render_map(filtered_records)


def _render_freshness_banner(freshness: str):
    if freshness == "stale":
        st.warning("⚠️ Đang hiển thị dữ liệu cũ — TomTom API có thể gặp sự cố.")
    elif freshness == "mock":
        st.info("ℹ️ Đang dùng dữ liệu mô phỏng — chưa kết nối API thật.")


def _render_kpi_cards(records: list):
    if not records:
        return
    
    total = len(records)
    jammed = sum(1 for r in records if r["congestion_level"] == 3)
    free = sum(1 for r in records if r["congestion_level"] == 1)
    avg_speed = sum(r["speed"] for r in records) / total

    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 Đường kẹt nặng", jammed)
    col2.metric("🟢 Tỷ lệ thông thoáng", f"{free / total * 100:.0f}%")
    col3.metric("⚡ Tốc độ TB", f"{avg_speed:.0f} km/h")


def _render_sidebar_filters(records: list) -> list:
    with st.sidebar:
        st.markdown("### 🎚️ Bộ lọc")
        
        levels = st.multiselect(
            "Mức kẹt",
            options=[1, 2, 3],
            default=[1, 2, 3],
            format_func=lambda x: CONGESTION_LABELS[x],
        )
        
        districts = sorted(set(r["district"] for r in records if r.get("district")))
        district = st.selectbox("Quận/Huyện", ["Tất cả"] + districts)
    
    filtered = [r for r in records if r["congestion_level"] in levels]
    if district != "Tất cả":
        filtered = [r for r in filtered if r.get("district") == district]
    
    return filtered


def _render_map(records: list):
    if not records:
        st.warning("Không có dữ liệu để hiển thị.")
        return
    
    df = pd.DataFrame(records)
    df["color"] = df["congestion_level"].map(CONGESTION_COLORS)
    df["congestion_label"] = df["congestion_level"].map(CONGESTION_LABELS)

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lng", "lat"],
        get_fill_color="color",
        get_radius=150,
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=16.054,
        longitude=108.202,
        zoom=12,
        pitch=0,
    )

    tooltip = {
        "html": "<b>{road_name}</b><br/>{congestion_label}<br/>Tốc độ: {speed} km/h",
        "style": {"background": "rgba(0,0,0,0.8)", "color": "white", "border-radius": "8px"},
    }

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip=tooltip))
```

**Quy tắc Streamlit:**
- Hàm `render_` bắt đầu bằng chữ thường — gọi từ `app.py`
- Hàm `_render_` có `_` ở đầu — hàm private, chỉ dùng trong file đó
- **Không** dùng global variable — dùng `st.session_state`
- **Không** để code chạy trực tiếp ở module level (ngoài import) — bọc vào hàm

---

### 4.3 Gọi API từ Frontend

**Tất cả HTTP call phải tập trung trong 1 file:** `frontend/utils/api_client.py`

```python
# frontend/utils/api_client.py
import httpx
import streamlit as st
import os

# URL backend — đọc từ env, fallback localhost khi dev local
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
TIMEOUT = 10  # giây


def _get_headers() -> dict:
    """Lấy Authorization header nếu đã đăng nhập."""
    token = st.session_state.get("token")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


@st.cache_data(ttl=60)   # cache 60 giây — không gọi API liên tục
def get_traffic_current() -> dict:
    """
    Lấy dữ liệu traffic hiện tại.
    Return dict với keys: records, freshness, total.
    Return {"records": [], "freshness": "error"} nếu lỗi — KHÔNG raise exception.
    """
    try:
        r = httpx.get(f"{BACKEND_URL}/api/traffic/current", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.TimeoutException:
        st.error("⏱️ Backend phản hồi quá chậm. Thử lại sau.")
        return {"records": [], "freshness": "error", "total": 0}
    except httpx.HTTPStatusError as e:
        st.error(f"❌ Lỗi API: {e.response.status_code}")
        return {"records": [], "freshness": "error", "total": 0}
    except Exception as e:
        st.error(f"❌ Không kết nối được backend: {e}")
        return {"records": [], "freshness": "error", "total": 0}


@st.cache_data(ttl=3600)  # cache 1 tiếng — roads ít thay đổi
def get_roads() -> list:
    try:
        r = httpx.get(f"{BACKEND_URL}/api/roads", timeout=TIMEOUT)
        return r.json() if r.status_code == 200 else []
    except Exception:
        return []


def login(email: str, password: str) -> dict:
    """
    Không dùng @st.cache_data vì đây là action, không phải query.
    Return {"access_token": "..."} hoặc {"error": "..."}
    """
    try:
        r = httpx.post(
            f"{BACKEND_URL}/api/auth/login",
            json={"email": email, "password": password},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            return r.json()
        return {"error": r.json().get("detail", "Đăng nhập thất bại")}
    except Exception as e:
        return {"error": str(e)}
```

**Quy tắc `api_client.py`:**
- Dùng `@st.cache_data(ttl=N)` cho GET requests
- **Không** dùng cache cho POST/PATCH/DELETE — đây là action thay đổi dữ liệu
- **Không** raise exception — bắt lỗi và trả dict với `error` key
- Luôn có `timeout` để tránh treo UI

---

## 5. ML Module

```python
# backend/ml/__init__.py — để Python nhận diện là package

# backend/services/prediction_service.py
import joblib
import os
from pathlib import Path

MODEL_PATH = Path(__file__).parent.parent / "ml" / "models" / "rf_model.pkl"

class PredictionService:
    def __init__(self):
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load model khi khởi động. Không crash nếu chưa có model."""
        if MODEL_PATH.exists():
            self.model = joblib.load(MODEL_PATH)
            print(f"✅ Model loaded from {MODEL_PATH}")
        else:
            print(f"⚠️ Model not found at {MODEL_PATH}. Predict endpoint sẽ trả 503.")

    def is_ready(self) -> bool:
        return self.model is not None

    def predict(self, features: dict) -> dict:
        if not self.is_ready():
            raise RuntimeError("Model chưa được train. Chạy ml/train.py trước.")
        
        import pandas as pd
        X = pd.DataFrame([features])
        prediction = self.model.predict(X)[0]
        confidence = max(self.model.predict_proba(X)[0])
        
        return {
            "predicted_level": int(prediction),
            "confidence": round(float(confidence), 3),
        }

prediction_service = PredictionService()
```

---

## 6. Quy ước đặt tên

### File và thư mục

```
snake_case cho file Python:     traffic_service.py, road_model.py
snake_case cho thư mục:         ai_traffic/, traffic_records/
```

### Python

```python
# Class: PascalCase
class TrafficService:
class Road(Base):

# Hàm, biến: snake_case
def get_latest_traffic():
traffic_level = 3

# Hằng số: UPPER_SNAKE_CASE
MAX_FAILED_ATTEMPTS = 5
CONGESTION_COLORS = {...}

# Biến private (chỉ dùng trong file): _gạch_dưới_đầu
def _render_map():
_cached_roads = None
```

### API Endpoints

```
Danh từ số nhiều, không có động từ:
GET  /api/roads             ← "roads", không phải "get-roads"
POST /api/incidents         ← "incidents", không phải "create-incident"
GET  /api/traffic/current   ← hợp lý vì "current" là tính từ của "traffic"
```

### Git Branch

```
feature/S<sprint>-<id>-<tên-ngắn-gọn>

Ví dụ:
feature/S1-06-base-map
feature/S2-13-tomtom-scheduler
feature/S3-30-jwt-login
```

### Commit message

```
<loại>(<scope>): <mô tả ngắn>

Loại:
  feat     — thêm tính năng mới
  fix      — sửa bug
  docs     — cập nhật tài liệu
  test     — thêm/sửa test
  chore    — config, dependencies
  style    — CSS, format code (không thay đổi logic)
  refactor — cải thiện code không thêm tính năng/sửa bug

Ví dụ thực tế:
feat(backend): add TomTom ingestion service
fix(frontend): fix map not rendering on first load
feat(ml): train RandomForest with 12 features, F1=0.82
test(auth): add brute force lock unit tests
chore(docker): remove deprecated version attribute from compose
```

---

## 7. Luồng dữ liệu end-to-end

### Luồng 1: Người dùng xem bản đồ traffic

```
1. Browser mở http://localhost/
   ↓ Nginx proxy
2. Streamlit render home.py
   ↓ gọi api_client.get_traffic_current()
3. httpx GET http://backend:8000/api/traffic/current
   ↓ FastAPI router/traffic.py
4. Kiểm tra Redis cache → có → trả về ngay
   Không có →
5. traffic_service.get_latest_traffic(db)
   ↓ SQLAlchemy query PostgreSQL
6. DB trả kết quả → service format → router trả JSON
   ↓ cache_service.set_traffic(records)
7. Redis lưu với TTL 60s
8. Frontend nhận JSON → tạo DataFrame → render Pydeck chart
```

### Luồng 2: Thêm file Python mới (ví dụ: thêm router mới)

```
1. Tạo file:     backend/routers/community.py
2. Viết router:  router = APIRouter(prefix="/api/community", tags=["Community"])
3. Mount vào:    main.py → app.include_router(community.router)
4. Tạo service:  backend/services/community_service.py
5. Tạo model:    backend/models/community_report.py
6. Export model: backend/models/__init__.py → thêm import
7. Tạo schema:   backend/schemas/community.py
8. Test API:     http://localhost:8000/docs → tìm tag "Community"
```

### Luồng 3: Thêm trang Streamlit mới

```
1. Tạo file:  frontend/pages/new_page.py
2. Viết hàm: def render_new_page(): ...
3. Import:   app.py → from pages.new_page import render_new_page
4. Thêm nav: st.radio → thêm option "Tên trang mới"
5. Xử lý:   if page == "Tên trang mới": render_new_page()
```

---

## 8. Quản lý thư viện

### Thêm thư viện mới (Backend)

```bash
# 1. Thêm vào backend/requirements.txt (dùng >= để linh hoạt version)
echo "redis>=5.0.0" >> backend/requirements.txt

# 2. Rebuild image Docker (bắt buộc!)
docker compose build backend

# 3. Restart
docker compose up -d backend
```

### Thêm thư viện mới (Frontend)

```bash
echo "plotly>=5.17.0" >> frontend/requirements.txt
docker compose build frontend
docker compose up -d frontend
```

### Quy tắc viết `requirements.txt`

```
# ✅ ĐÚNG — dùng >= để không bị khóa cứng version cũ
fastapi>=0.104.1
pandas>=2.2.0

# ❌ SAI — dùng == chỉ khi cực kỳ cần thiết, thường gây conflict  
fastapi==0.104.1

# ✅ Thêm comment giải thích nếu thư viện không rõ ràng
Faker==22.5.1     # Sinh dữ liệu mock — version cố định vì API thay đổi nhiều
```

---

## 9. Những lỗi thường gặp & cách tránh

### ❌ Lỗi 1: Import circular (vòng tròn)

```python
# TÌNH HUỐNG: models/__init__.py import Road, Road lại import từ models/__init__.py
# → Python báo ImportError: cannot import name 'Road'

# ✅ GIẢI PHÁP: Import trực tiếp từ file, không qua __init__
from models.road import Road          # ✅ đúng
from models import Road               # ❌ có thể gây circular
```

### ❌ Lỗi 2: Session DB không đóng

```python
# SAI — session có thể không bao giờ đóng nếu có exception
db = SessionLocal()
result = db.query(Road).all()
db.close()    # Nếu dòng trên raise exception, dòng này không chạy

# ✅ ĐÚNG — dùng try/finally hoặc context manager
db = SessionLocal()
try:
    result = db.query(Road).all()
finally:
    db.close()

# ✅ HOẶC dùng dependency injection của FastAPI (tốt hơn)
def my_endpoint(db: Session = Depends(get_db)):
    # get_db() tự đóng session
```

### ❌ Lỗi 3: Hardcode URL trong frontend

```python
# SAI — không chạy được trong Docker
r = httpx.get("http://localhost:8000/api/traffic/current")

# ✅ ĐÚNG — đọc từ biến môi trường
import os
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
r = httpx.get(f"{BACKEND_URL}/api/traffic/current")
```

### ❌ Lỗi 4: Streamlit gọi API không có cache

```python
# SAI — mỗi lần render lại trang là 1 lần gọi API
def render_home():
    data = get_traffic()   # gọi mỗi giây nếu có widget thay đổi

# ✅ ĐÚNG — cache với TTL phù hợp
@st.cache_data(ttl=60)
def get_traffic():
    ...
```

### ❌ Lỗi 5: Commit file `.env` lên Git

```bash
# Kiểm tra xem .env có bị track không
git status

# Nếu .env xuất hiện → thêm vào .gitignore ngay
echo ".env" >> .gitignore
git rm --cached .env    # bỏ khỏi Git tracking (giữ file local)
git commit -m "chore: remove .env from tracking"
```

### ❌ Lỗi 6: Bỏ qua `version` cũ trong docker-compose.yml

```yaml
# SAI — version là deprecated, Docker báo warning
version: '3.8'
services:
  ...

# ✅ ĐÚNG — xóa dòng version đi
services:
  ...
```

### ❌ Lỗi 7: Không validate input API

```python
# SAI — speed có thể là -999 hoặc null
@router.post("/traffic")
def create(road_id: int, speed: float, congestion_level: int):
    ...

# ✅ ĐÚNG — dùng Pydantic schema để tự động validate
class TrafficCreate(BaseModel):
    road_id: int = Field(gt=0)
    speed: float = Field(ge=0, le=200)
    congestion_level: int = Field(ge=1, le=3)

@router.post("/traffic")
def create(data: TrafficCreate):   # Pydantic tự throw 422 nếu sai
    ...
```

---

## 📌 Checklist trước khi tạo Pull Request

```
Code quality:
[ ] Không có print() debug còn sót — dùng logging thay thế
[ ] Không có hardcode URL, password, API key trong code
[ ] Không có file .env, *.pkl, __pycache__ trong commit

Backend:
[ ] Endpoint mới có response_model (schema cụ thể)
[ ] Service không tự tạo DB session
[ ] Input được validate bằng Pydantic
[ ] Lỗi trả HTTPException với status code và detail rõ ràng

Frontend:
[ ] API call trong api_client.py, không rải rác trong pages/
[ ] GET request có @st.cache_data(ttl=...)
[ ] Luôn xử lý trường hợp API trả lỗi (hiện thông báo thân thiện)

Docker:
[ ] Thêm thư viện mới → đã cập nhật requirements.txt
[ ] Test docker compose up --build không lỗi
```

---

*Tài liệu tạo ngày 18/04/2026. Cập nhật khi có thay đổi kiến trúc hoặc quy ước.*
