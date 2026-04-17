<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-1.31-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-15-4169E1?style=for-the-badge&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/scikit--learn-1.4-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white" />
</p>

<h1 align="center">🚦 Hệ thống AI Dự báo Giao thông Đô thị Đà Nẵng</h1>

<p align="center">
  <strong>Đề tài 11</strong> — Đồ án Quản lý Dự án Phần mềm<br/>
  Nhóm 3 sinh viên | 10 tuần | 5 Sprint
</p>

<p align="center">
  <a href="#-tổng-quan">Tổng quan</a> •
  <a href="#-tính-năng">Tính năng</a> •
  <a href="#%EF%B8%8F-kiến-trúc">Kiến trúc</a> •
  <a href="#-cài-đặt--chạy-dự-án">Cài đặt</a> •
  <a href="#-cấu-trúc-thư-mục">Cấu trúc</a> •
  <a href="#-api-endpoints">API</a> •
  <a href="#-quy-trình-phát-triển">Quy trình</a>
</p>

---

## 📋 Tổng quan

Người dân thành phố Đà Nẵng thường **không biết trước tình trạng giao thông** trên lộ trình di chuyển, dẫn đến mất thời gian và chi phí do kẹt xe.

**Giải pháp:** Hệ thống Web App cung cấp:
- 🗺️ **Bản đồ giao thông thời gian thực** — cập nhật mỗi 60 giây từ TomTom API
- 🤖 **Dự báo AI 30 phút** — sử dụng mô hình Random Forest
- 🧭 **Tìm đường tối ưu tránh kẹt** — thuật toán A* tích hợp trọng số tắc nghẽn
- 📊 **Dashboard giám sát** — dành cho CSGT điều hành và xử lý sự kiện

---

## ✨ Tính năng

### 👥 Dành cho Người dân (Không cần đăng nhập)

| Tính năng | Mô tả |
|---|---|
| **Bản đồ thời gian thực** | Xem tình trạng giao thông 50 tuyến đường Đà Nẵng, tô màu Đỏ/Vàng/Xanh theo mức kẹt |
| **Dự báo 30 phút** | Toggle xem dự báo tình trạng giao thông 30 phút tới từ AI |
| **Tìm đường tối ưu** | Chọn điểm A → B, nhận gợi ý tuyến chính + tuyến thay thế |
| **Báo cáo kẹt xe** | Gửi thông tin kẹt xe theo vị trí GPS, đóng góp vào dữ liệu cộng đồng |
| **Bộ lọc thông minh** | Lọc theo quận/huyện, mức độ kẹt, tìm kiếm tên đường |

### 🚔 Dành cho Cán bộ CSGT (Role: `csgt`)

| Tính năng | Mô tả |
|---|---|
| **Dashboard KPI** | 4 chỉ số tổng quan + Gauge chart + Biểu đồ kẹt theo giờ + Top 10 điểm kẹt |
| **Quản lý sự kiện** | CRUD lô cốt, tai nạn, sự kiện giao thông |
| **Điều động trên bản đồ** | Click điểm kẹt → đánh dấu "Đã điều động" |
| **Sổ trực ban điện tử** | Ghi chú, bàn giao ca trực |
| **Xuất CSV** | Trích xuất dữ liệu giao thông theo khoảng ngày |

### 🔑 Dành cho Quản trị viên (Role: `admin`)

| Tính năng | Mô tả |
|---|---|
| **Quản lý tài khoản** | Tạo, khóa/mở, đặt lại mật khẩu |
| **Cảnh báo khẩn cấp** | Phát/thu hồi banner khẩn toàn hệ thống |
| **Nhật ký kiểm toán** | Audit log mọi hành động nhạy cảm (append-only) |
| **Giám sát AI** | Xem RMSE, F1 score, kích hoạt tái huấn luyện thủ công |

### 🤖 Tác vụ Tự động (APScheduler)

| Job | Tần suất | Mô tả |
|---|---|---|
| Thu thập dữ liệu | Mỗi 60 giây | Gọi TomTom/Goong API, validate, lưu DB + Redis |
| Dự báo AI | Mỗi 5 phút | Chạy inference Random Forest cho 50 tuyến đường |
| Auto-incident | Mỗi 5 phút | ≥3 báo cáo cộng đồng/đường/15 phút → tạo sự kiện tự động |
| Tái huấn luyện | Chủ nhật 2:00 AM | Retrain model trên 4 tuần dữ liệu mới nhất |

---

## 🏗️ Kiến trúc

```
BROWSER (Người dân / CSGT / Admin)
    │
    │  HTTPS
    ▼
NGINX (reverse proxy, SSL termination)
    │
    ├──► STREAMLIT (port 8501) — Frontend Python
    │         │
    │         │  REST API calls
    │         ▼
    └──► FASTAPI (port 8000) — Backend Python
              │
              ├── Routers    (auth, traffic, predict, route, incidents, feedback, admin)
              ├── Services   (ingestion, ai_engine, routing, auth_service, cache)
              ├── Scheduler  (APScheduler — 5 background jobs)
              │
              ├──► PostgreSQL 15 + PostGIS (port 5432)
              ├──► Redis 7 (port 6379)
              │
              └──► External APIs:
                   ├── TomTom Traffic Flow API
                   ├── Goong Maps API (fallback)
                   └── OpenWeather API
```

### Công nghệ sử dụng

| Layer | Công nghệ | Phiên bản |
|---|---|---|
| **Backend** | FastAPI + SQLAlchemy + Pydantic | Python 3.11 |
| **Frontend** | Streamlit + Pydeck + Plotly | Python 3.11 |
| **AI/ML** | scikit-learn (Random Forest) | ≥ 1.4.0 |
| **Database** | PostgreSQL + PostGIS | 15 |
| **Cache** | Redis | 7 |
| **Deploy** | Docker Compose + Nginx | latest |
| **Bản đồ** | Pydeck + Goong Maps API | — |
| **Data** | TomTom Traffic Flow API | v4 |

---

## 🚀 Cài đặt & Chạy dự án

### Yêu cầu hệ thống

- [Git](https://git-scm.com/downloads)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (bao gồm Docker Compose)
- [Python 3.11](https://www.python.org/downloads/) (cho development local)

### Cách 1: Docker Compose (Khuyến nghị ✅)

```bash
# 1. Clone repository
git clone https://github.com/<username>/traffic-prediction-danang.git
cd traffic-prediction-danang

# 2. Tạo file .env từ template
cp .env.example .env

# 3. Điền API keys vào file .env
# (Xem phần Cấu hình môi trường bên dưới)

# 4. Khởi động toàn bộ hệ thống
docker-compose up --build

# 5. Truy cập ứng dụng
# 🌐 Frontend:  http://localhost:8501
# 🔌 Backend:   http://localhost:8000
# 📖 API Docs:  http://localhost:8000/docs
```

### Cách 2: Chạy thủ công (Development)

```bash
# 1. Clone và cài đặt
git clone https://github.com/<username>/traffic-prediction-danang.git
cd traffic-prediction-danang

# 2. Tạo môi trường ảo (chọn một trong hai cách)

# --- Cách A: pip venv ---
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# --- Cách B: Conda ---
conda create -n traffic_env python=3.11 -y
conda activate traffic_env

# 3. Cài đặt dependencies
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt

# 4. Khởi động PostgreSQL và Redis
# (Cài riêng hoặc dùng Docker cho DB)
docker-compose up postgres redis -d

# 5. Tạo file .env và điền cấu hình
cp .env.example .env

# 6. Chạy Backend
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 7. Chạy Frontend (terminal mới)
cd frontend
streamlit run app.py --server.port 8501
```

### Cấu hình môi trường (`.env`)

Tạo file `.env` ở thư mục gốc với nội dung sau:

```bash
# ── Database ─────────────────────────────────────────
DATABASE_URL=postgresql://traffic_user:your_password@postgres:5432/traffic_db
POSTGRES_USER=traffic_user
POSTGRES_PASSWORD=your_password
POSTGRES_DB=traffic_db

# ── Redis ────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ── API Keys (Đăng ký miễn phí) ─────────────────────
TOMTOM_API_KEY=your_tomtom_api_key
GOONG_API_KEY=your_goong_api_key
OPENWEATHER_API_KEY=your_openweather_api_key

# ── Authentication ───────────────────────────────────
JWT_SECRET_KEY=thay-bang-chuoi-bi-mat-toi-thieu-32-ky-tu
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=8

# ── Application ─────────────────────────────────────
APP_ENV=development
LOG_LEVEL=INFO
API_BASE_URL=http://backend:8000
API_DAILY_REQUEST_LIMIT=2000
```

> ⚠️ **Lưu ý:** File `.env` chứa thông tin nhạy cảm — **KHÔNG** commit lên Git!

### Tài khoản mặc định (sau khi seed data)

| Email | Mật khẩu | Vai trò |
|---|---|---|
| `admin@test.com` | `Admin123` | Quản trị viên (`admin`) |
| `csgt@test.com` | `Csgt123` | Cán bộ CSGT (`csgt`) |

### Đăng ký API Keys miễn phí

| Dịch vụ | Link đăng ký | Free tier |
|---|---|---|
| TomTom | [developer.tomtom.com](https://developer.tomtom.com/) | 2,500 req/ngày |
| Goong | [docs.goong.io](https://docs.goong.io/) | 1,000 req/ngày |
| OpenWeather | [openweathermap.org/api](https://openweathermap.org/api) | 1,000 req/ngày |

---

## 📁 Cấu trúc thư mục

```
QuanLyDuAn_GiaoThongDoThi/
│
├── docker-compose.yml           # Khai báo tất cả services
├── .env.example                 # Template biến môi trường (commit được)
├── .env                         # Giá trị thực (KHÔNG commit ❌)
├── .gitignore
├── README.md                    # 📖 File này
│
├── backend/                     # 🔌 FastAPI Backend
│   ├── main.py                  #   Entry point — khởi tạo FastAPI app
│   ├── config.py                #   Đọc .env, cấu hình chung
│   ├── database.py              #   SQLAlchemy engine + session
│   ├── requirements.txt         #   Dependencies backend
│   │
│   ├── models/                  #   SQLAlchemy ORM models
│   │   ├── street.py            #     Bảng streets (50 đường ĐN)
│   │   ├── traffic_data.py      #     Bảng traffic_data (time-series)
│   │   ├── user.py              #     Bảng users (CSGT + Admin)
│   │   ├── incident.py          #     Bảng incidents (lô cốt, tai nạn)
│   │   ├── feedback.py          #     Bảng feedback (báo cáo cộng đồng)
│   │   └── audit_log.py         #     Bảng audit_log (nhật ký kiểm toán)
│   │
│   ├── schemas/                 #   Pydantic schemas (request/response)
│   │   ├── traffic.py
│   │   ├── auth.py
│   │   ├── incident.py
│   │   └── feedback.py
│   │
│   ├── routers/                 #   FastAPI routers (1 file = 1 domain)
│   │   ├── auth.py              #     POST /api/auth/login, /logout
│   │   ├── traffic.py           #     GET /api/traffic/current, /history
│   │   ├── predict.py           #     GET /api/predict/{street_id}
│   │   ├── route.py             #     GET /api/route?from=&to=
│   │   ├── incidents.py         #     CRUD /api/incidents
│   │   ├── feedback.py          #     POST /api/feedback
│   │   └── admin.py             #     Admin-only routes
│   │
│   ├── services/                #   Business logic (tách khỏi router)
│   │   ├── ingestion.py         #     Fetch TomTom/Goong API
│   │   ├── ai_engine.py         #     Load model, chạy inference
│   │   ├── routing.py           #     A* pathfinding (NetworkX)
│   │   ├── auth_service.py      #     JWT create/verify, bcrypt
│   │   └── cache.py             #     Redis helpers
│   │
│   ├── ml_models/               #   🧠 AI/ML
│   │   ├── train.py             #     Script huấn luyện model
│   │   ├── features.py          #     build_features() — 12 features
│   │   ├── evaluate.py          #     Tính RMSE, F1
│   │   ├── rf_classifier.pkl    #     Model phân loại mức kẹt (gitignore)
│   │   └── rf_regressor.pkl     #     Model dự báo tốc độ (gitignore)
│   │
│   └── tests/                   #   🧪 pytest tests
│       ├── test_validate.py
│       ├── test_ai.py
│       ├── test_routing.py
│       └── test_auth.py
│
├── frontend/                    # 🎨 Streamlit Frontend
│   ├── app.py                   #   Trang chính — bản đồ giao thông
│   ├── requirements.txt         #   Dependencies frontend
│   │
│   └── pages/                   #   Streamlit multipage
│       ├── Login.py             #     Trang đăng nhập
│       ├── Route_Finder.py      #     Tìm đường tối ưu
│       ├── Admin_Dashboard.py   #     Dashboard CSGT/Admin
│       └── Admin_Settings.py    #     Quản lý users, cấu hình
│
├── data/                        # 📦 Dữ liệu tĩnh
│   ├── streets.geojson          #   50 đường Đà Nẵng với tọa độ
│   ├── districts.geojson        #   Ranh giới 8 quận/huyện
│   └── seed_data.py             #   Script tạo dữ liệu mẫu
│
└── nginx/                       # 🔒 Reverse proxy
    ├── nginx.conf
    └── certs/                   #   SSL certificates
```

---

## 🔌 API Endpoints

### Công khai (Không cần đăng nhập)

```
GET  /health                     → Kiểm tra trạng thái hệ thống
GET  /api/traffic/current        → Dữ liệu giao thông thời gian thực
GET  /api/traffic/history        → Lịch sử giao thông theo đường + khoảng thời gian
GET  /api/predict/{street_id}    → Dự báo 30 phút cho 1 tuyến đường
GET  /api/predict/all            → Dự báo 30 phút toàn bộ tuyến đường
GET  /api/route                  → Tìm đường tối ưu (A → B)
POST /api/feedback               → Gửi báo cáo kẹt xe cộng đồng
GET  /api/feedback/recent        → Báo cáo cộng đồng 30 phút gần nhất
GET  /api/config/alert           → Trạng thái cảnh báo khẩn cấp
```

### Yêu cầu đăng nhập — CSGT / Admin

```
POST /api/auth/login             → Đăng nhập, nhận JWT token
POST /api/auth/logout            → Đăng xuất, blacklist token
GET  /api/auth/me                → Thông tin user hiện tại

GET    /api/incidents            → Danh sách sự kiện giao thông
POST   /api/incidents            → Tạo sự kiện (CSGT)
PUT    /api/incidents/{id}       → Cập nhật trạng thái sự kiện
DELETE /api/incidents/{id}       → Xóa sự kiện
```

### Chỉ Admin

```
GET  /api/admin/users            → Danh sách tài khoản
POST /api/admin/users            → Tạo tài khoản mới
PUT  /api/admin/users/{id}       → Khóa/mở/đặt lại mật khẩu
GET  /api/admin/audit-log        → Nhật ký kiểm toán
GET  /api/admin/system-stats     → Thống kê hệ thống (CPU, RAM)
GET  /api/admin/ai-metrics       → Chỉ số AI (RMSE, F1)
PUT  /api/config/alert           → Phát/thu hồi cảnh báo khẩn cấp
```

> 📖 **Swagger UI:** Sau khi chạy backend, truy cập `http://localhost:8000/docs` để xem interactive API docs.

---

## 🧠 Mô hình AI

### Thuật toán

| Model | Thuật toán | Input | Output |
|---|---|---|---|
| **Classifier** | RandomForestClassifier | 12 features | Mức kẹt: `0` (Xanh), `1` (Vàng), `2` (Đỏ) |
| **Regressor** | RandomForestRegressor | 12 features | Tốc độ dự báo (km/h) |

### 12 Features đầu vào

```
hour              — Giờ trong ngày (0-23)
weekday           — Ngày trong tuần (0=Thứ 2, 6=CN)
is_rush_morning   — Giờ cao điểm sáng (7-8h)
is_rush_evening   — Giờ cao điểm chiều (17-18h)
is_weekend        — Cuối tuần
current_speed     — Tốc độ hiện tại (km/h)
speed_15m_ago     — Tốc độ 15 phút trước
speed_30m_ago     — Tốc độ 30 phút trước
speed_45m_ago     — Tốc độ 45 phút trước
has_incident      — Có sự kiện ảnh hưởng
incident_severity — Mức nghiêm trọng sự kiện (0-3)
is_rain           — Đang mưa (OpenWeather API)
```

### Quy trình huấn luyện

```
Dữ liệu 4 tuần → build_features() → TimeSeriesSplit(5 fold)
    → Train trên 4 fold → Evaluate trên fold cuối
    → Nếu F1_mới ≥ F1_cũ × 0.95 → Triển khai model mới
    → Ngược lại → Giữ model cũ, ghi cảnh báo
```

---

## 🔒 Bảo mật

| Lớp | Cơ chế |
|---|---|
| **Xác thực** | JWT Bearer Token (HS256, hết hạn 8 giờ) |
| **Mã hóa mật khẩu** | bcrypt (cost factor 12) |
| **Chống brute-force** | Khóa tài khoản 15 phút sau 5 lần sai |
| **Token logout** | JWT Blacklist lưu trong Redis |
| **Phân quyền** | RBAC 3 cấp: Public → CSGT → Admin |
| **Rate limiting** | 5 req/phút/IP cho endpoint feedback |
| **Audit log** | Ghi nhật ký mọi hành động nhạy cảm (append-only) |
| **Input validation** | Pydantic schemas, parameterized SQL queries |
| **API Keys** | Lưu trong `.env`, không commit lên Git |

---

## 🧪 Kiểm thử

```bash
# Chạy toàn bộ tests
cd backend
pytest tests/ -v

# Chạy với coverage report
pytest tests/ -v --cov=. --cov-report=term-missing

# Chạy test riêng lẻ
pytest tests/test_validate.py -v    # Test validation dữ liệu
pytest tests/test_ai.py -v          # Test AI features + inference
pytest tests/test_routing.py -v     # Test thuật toán A*
pytest tests/test_auth.py -v        # Test JWT + bcrypt + brute-force
```

**Mục tiêu coverage:** `> 70%` cho các module `services/` và `ml_models/`

---

## 🔄 Quy trình phát triển

### Git Workflow

```
main              ← Code ổn định, đã chạy được (chỉ merge từ develop)
  └── develop     ← Nhánh phát triển chung
        ├── feature/S1-06-db-migration
        ├── feature/S2-01-ingestion
        └── feature/S3-01-train-model
```

### Quy ước đặt tên nhánh

```
feature/<sprint>-<task_number>-<short-description>
```

Ví dụ: `feature/S1-06-db-migration`, `feature/S3-01-train-model`

### Quy ước commit message

```
feat(module): mô tả         ← Thêm tính năng mới
fix(module): mô tả          ← Sửa bug
docs: mô tả                 ← Cập nhật tài liệu
test(module): mô tả         ← Thêm test
chore: mô tả                ← Config, dependencies
```

### Quy trình merge

1. Tạo nhánh `feature/` từ `develop`
2. Code + commit thường xuyên
3. Push lên remote + tạo **Pull Request** vào `develop`
4. Ít nhất **1 người review** trước khi merge
5. **Squash and Merge** vào `develop`
6. Cuối Sprint: merge `develop` → `main` (nếu stable)

---

## 📅 Lộ trình phát triển

| Sprint | Tuần | Mục tiêu chính | Trạng thái |
|---|---|---|---|
| **Sprint 1** | 1–2 | Docker + FastAPI + Bản đồ Streamlit cơ bản | 🔨 Đang thực hiện |
| **Sprint 2** | 3–4 | TomTom API live + Redis cache + Bộ lọc + Fallback | ⬜ Chưa bắt đầu |
| **Sprint 3** | 5–6 | AI dự báo 30 phút + JWT Auth + Login UI | ⬜ Chưa bắt đầu |
| **Sprint 4** | 7–8 | A* tìm đường + Dashboard CSGT + CRUD sự kiện | ⬜ Chưa bắt đầu |
| **Sprint 5** | 9–10 | Feedback cộng đồng + Testing >70% + HTTPS + Demo | ⬜ Chưa bắt đầu |

---

## 🤝 Nhóm phát triển

**Đề tài 11** — Môn Quản lý Dự án Phần mềm

| STT | Họ và tên | Vai trò |
|---|---|---|
| 1 | Thành viên 1 | Scrum Master (xoay vòng) |
| 2 | Thành viên 2 | Developer |
| 3 | Thành viên 3 | Developer |

> 💡 Mô hình làm việc: **Pull-based Backlog** — Ai giỏi gì nhận việc đó, không phân công cứng nhắc.

---

## 📜 License

Dự án này được phát triển cho mục đích học tập trong khuôn khổ đồ án môn Quản lý Dự án Phần mềm.

---

<p align="center">
  Made with ❤️ by Nhóm Đề tài 11 — Đại học Đà Nẵng
</p>