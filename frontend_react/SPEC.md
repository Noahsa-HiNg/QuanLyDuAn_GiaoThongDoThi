# SPEC: React Frontend — Giao thông Đà Nẵng
> Dùng file này để code toàn bộ frontend React thay thế Streamlit.
> Backend FastAPI KHÔNG thay đổi. Chỉ viết frontend.

---

## ⛔ RÀNG BUỘC CỨNG — ĐỌC TRƯỚC KHI CODE

> Những điều dưới đây là TUYỆT ĐỐI, không được vi phạm dù bất kỳ lý do gì.

1. **KHÔNG thêm thư viện** nào ngoài danh sách trong Section 0 (Package versions). Nếu cần gì, dùng thư viện đã có hoặc tự code tay.
2. **KHÔNG tạo file** ngoài cấu trúc trong Section 3. Không tạo thêm subfolder, không tạo utility files tự ý.
3. **KHÔNG mock data.** Mọi dữ liệu đều fetch từ API thật trong Section 4. Nếu API lỗi, hiện error state — không trả về hardcoded data.
4. **KHÔNG thêm animation phức tạp** (không dùng `framer-motion`, `@react-spring/*`, `gsap`). CSS transition đơn giản là đủ.
5. **KHÔNG dùng `any` trong TypeScript.** Tất cả type phải được định nghĩa rõ trong `types/`.
6. **KHÔNG import trực tiếp `axios`** trong component/page. Mọi HTTP call phải đi qua `api/` layer.
7. **KHÔNG đặt hardcode URL** (`http://localhost:8000`). Chỉ dùng `import.meta.env.VITE_API_BASE`.
8. **KHÔNG sửa Backend.** Không tạo file trong `backend/`, không sửa `docker-compose.yml` backend service.
9. **KHÔNG tự thêm trang mới** ngoài 8 trang trong Section 9.
10. **KHÔNG dùng CSS-in-JS** (`styled-components`, `emotion`). KHÔNG dùng CSS Modules. KHÔNG tạo file `.module.css`.
11. **Tailwind là DUY NHẤT cho style.** Ngoại lệ: inline style khi value đến từ JS runtime (color từ data, position từ tính toán). File `mapbox-overrides.css` cho Mapbox GL JS popup/marker.
12. **Dừng ngay** sau khi hoàn thành task được giao. Không tự làm thêm bước tiếp theo.

---

## 0. Package versions (package.json — chính xác, không thay đổi version)

```json
{
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.24.0",
    "mapbox-gl": "^3.4.0",
    "@tanstack/react-query": "^5.40.0",
    "zustand": "^4.5.4",
    "axios": "^1.7.2",
    "recharts": "^2.12.7",
    "lucide-react": "^0.400.0"
  },
  "devDependencies": {
    "@types/mapbox-gl": "^3.4.0",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.4.5",
    "vite": "^5.3.1",
    "tailwindcss": "^3.4.4",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.39"
  }
}
```

> **Lệnh cài đặt:**
> ```
> npm create vite@5.3.1 . -- --template react-ts
> npm install mapbox-gl@3.4.0 @tanstack/react-query@5.40.0 zustand@4.5.4 axios@1.7.2 recharts@2.12.7 lucide-react@0.400.0 react-router-dom@6.24.0
> npm install -D @types/mapbox-gl tailwindcss@3.4.4 autoprefixer postcss
> npx tailwindcss init -p
> ```

---

## 1. Tech Stack

| Layer | Công nghệ |
|---|---|
| Framework | **Vite + React 18 + TypeScript** |
| Map | **Mapbox GL JS v3** (style: `mapbox://styles/mapbox/light-v11`) |
| Routing (page) | **React Router v6** |
| Data fetching | **TanStack Query (React Query v5)** |
| Global state | **Zustand** |
| HTTP | **Axios** |
| Charts | **Recharts** |
| Styling | **Tailwind CSS v3** (primary) + inline style cho dynamic values |
| Icons | **Lucide React** |

---

## 2. Environment variables (.env)

```
VITE_API_BASE=http://localhost:8000
VITE_MAPBOX_TOKEN=pk.eyJ1IjoibWFwYm94IiwiYSI6...
```

---

## 3. Cấu trúc thư mục

```
frontend_react/
├── public/
├── src/
│   ├── main.tsx
│   ├── App.tsx                    ← Router setup
│   ├── styles/
│   │   ├── globals.css              ← Tailwind directives + base reset
│   │   ├── variables.css            ← CSS custom properties (colors)
│   │   └── mapbox-overrides.css     ← Mapbox GL JS popup/marker overrides
│   ├── types/
│   │   ├── api.types.ts
│   │   ├── map.types.ts
│   │   └── auth.types.ts
│   ├── constants/
│   │   ├── map.constants.ts
│   │   └── api.constants.ts
│   ├── lib/
│   │   └── axios.ts               ← axios instance + JWT interceptor
│   ├── utils/
│   │   ├── buildGeoJSON.ts
│   │   ├── formatters.ts          ← fmtTimestampVN, normalizeVN
│   │   └── congestionColor.ts     ← level → Tailwind class + hex color
│   ├── api/
│   │   ├── traffic.api.ts
│   │   ├── routing.api.ts
│   │   ├── incidents.api.ts
│   │   ├── stats.api.ts
│   │   ├── auth.api.ts
│   │   ├── users.api.ts
│   │   └── scheduler.api.ts
│   ├── store/
│   │   ├── authStore.ts
│   │   ├── mapStore.ts
│   │   └── incidentStore.ts
│   ├── hooks/
│   │   ├── useTrafficData.ts
│   │   ├── useGeometry.ts
│   │   └── useAuth.ts
│   ├── components/
│   │   ├── common/
│   │   │   ├── KpiCard.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   ├── layout/
│   │   │   ├── Navbar.tsx
│   │   │   └── AppLayout.tsx
│   │   └── map/
│   │       ├── TrafficMap.tsx
│   │       ├── TrafficLayer.tsx
│   │       ├── IncidentMarkers.tsx
│   │       ├── RouteLayer.tsx
│   │       └── MapControls.tsx
│   └── pages/
│       ├── Home/
│       │   └── Home.tsx
│       ├── RouteFinder/
│       │   └── RouteFinder.tsx
│       ├── Dashboard/
│       │   └── Dashboard.tsx
│       ├── CsgtDashboard/
│       │   └── CsgtDashboard.tsx
│       ├── Incidents/
│       │   └── Incidents.tsx
│       ├── AdminUsers/
│       │   └── AdminUsers.tsx
│       ├── AdminScheduler/
│       │   └── AdminScheduler.tsx
│       └── Login/
│           └── Login.tsx
├── tailwind.config.ts
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## 4. API Endpoints (Backend: http://localhost:8000)

### Traffic
```
GET  /api/traffic/streets-geometry          → { streets: [{id, name, district, coordinates: [[lng,lat],...]}] }
GET  /api/traffic/state                     → { streets: [{street_id, congestion_level, avg_speed, timestamp}], data_as_of }
GET  /api/traffic/current?district_id=N     → { streets:[...], green_count, yellow_count, red_count, avg_speed, data_as_of }
GET  /api/predict/30min                     → [{street_id, predicted_level, confidence}]
```

### Stats
```
GET  /api/stats/report                      → { avg_speed, red_count, yellow_count, green_count, top_congested:[{street_name, district_name, avg_speed}] }
GET  /api/stats/hourly-trend?days=7         → [{hour, avg_congestion_pct, avg_speed}]
GET  /api/stats/heatmap                     → [{hour, weekday, congestion_pct}]
```

### Weather
```
GET  /api/weather/current                   → { temperature, humidity, wind_speed, rain_1h_mm, is_raining, weather_group }
```

### Routing
```
GET  /api/streets/midpoints                 → { streets: [{id, name, lat, lng}] }
GET  /api/routes?from_lat=&from_lng=&to_lat=&to_lng=&mode=shortest|fastest
     → { path: [[lat,lng],...], total_distance_m, estimated_time_min, streets:[{name, congestion_level, avg_speed}] }
```

### Auth
```
POST /api/auth/login                        body: { email, password }
     → { access_token, token_type, user: { id, email, full_name, role } }
```

### Incidents (Bearer token required)
```
GET  /api/incidents?is_active=&type=&status=&page=1&page_size=50
POST /api/incidents                         body: { street_id, type, start_time, severity, description, status, is_active }
PUT  /api/incidents/{id}                    body: { status }
DELETE /api/incidents/{id}
```

### Users (Admin only)
```
GET    /api/users
POST   /api/users                           body: { email, password, full_name, role }
POST   /api/users/{id}/lock
POST   /api/users/{id}/unlock
DELETE /api/users/{id}
```

### Scheduler (Admin only)
```
GET  /api/traffic/schedule/state
GET  /api/traffic/schedule/jobs
POST /api/traffic/schedule/pause
POST /api/traffic/schedule/resume
POST /api/traffic/crawl
GET  /api/traffic/crawl/status
```

---

## 5. Types (types/api.types.ts)

```typescript
export interface StreetGeometry {
  id: number;
  name: string;
  district: string;
  district_id: number;
  coordinates: [number, number][];  // [lng, lat][]
}

export interface TrafficState {
  street_id: number;
  congestion_level: 0 | 1 | 2 | null; // 0=clear, 1=slow, 2=congested
  avg_speed: number;
  max_speed: number;
  timestamp: string; // ISO UTC
}

export interface Incident {
  id: number;
  street_id: number;
  type: 'roadblock' | 'accident' | 'event' | 'community';
  status: 'active' | 'dispatched' | 'resolved';
  severity: 1 | 2 | 3;
  description: string | null;
  start_time: string;
  end_time: string | null;
  is_active: boolean;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: 'admin' | 'csgt' | 'user';
  is_active: boolean;
  is_locked: boolean;
}

export interface RouteResult {
  path: [number, number][];
  total_distance_m: number;
  estimated_time_min: number;
  streets: { name: string; congestion_level: number; avg_speed: number }[];
}
```

---

## 6. Design System

### globals.css
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Import variables */
@import './variables.css';

* { box-sizing: border-box; margin: 0; padding: 0; }
html, body, #root { height: 100%; }
body { font-family: 'Inter', sans-serif; }
```

### variables.css (chỉ chứa Mapbox + dynamic color values)
```css
:root {
  /* Dùng cho Mapbox GL JS expression và inline style dynamic */
  --color-traffic-clear: #22c55e;
  --color-traffic-slow: #f59e0b;
  --color-traffic-congested: #ef4444;
  --color-traffic-unknown: #94a3b8;
}
```

### mapbox-overrides.css (Mapbox GL JS popup/marker — không đọc được Tailwind)
```css
.mapboxgl-popup-content {
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.15);
  font-size: 0.875rem;
}
.mapboxgl-popup-tip { display: none; }
.mapboxgl-ctrl-group { border-radius: 8px !important; }
```

### tailwind.config.ts
```typescript
import type { Config } from 'tailwindcss';
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'traffic-clear':     '#22c55e',
        'traffic-slow':      '#f59e0b',
        'traffic-congested': '#ef4444',
        'traffic-unknown':   '#94a3b8',
      },
      zIndex: {
        'map':     '0',
        'overlay': '90',
        'navbar':  '100',
        'modal':   '200',
      },
    },
  },
  plugins: [],
} satisfies Config;
```

### Quy tắc sử dụng Tailwind

| Trường hợp | Cách viết |
|---|---|
| Layout, spacing, typography | **Tailwind classes trong `className`** |
| Màu từ data (congestion_level) | `style={{ color: CONGESTION_COLORS[level] }}` |
| Position từ JS (popup, tooltip) | `style={{ top: y, left: x }}` |
| Mapbox popup/marker | File `mapbox-overrides.css` |
| Animation | Tailwind `transition-*`, `duration-*` — không dùng framer-motion |

**Map style:** `mapbox://styles/mapbox/light-v11` — nền trắng sáng giống Google Maps.

**Traffic line colors (Mapbox expression — dùng hex, không dùng Tailwind class):**
- `congestion_level = 0` → `#22c55e`
- `congestion_level = 1` → `#f59e0b`
- `congestion_level = 2` → `#ef4444`
- `null` → `#94a3b8`

---

## 7. Map constants (constants/map.constants.ts)

```typescript
export const DA_NANG_CENTER: [number, number] = [108.2022, 16.0544]; // [lng, lat]
export const DEFAULT_ZOOM = 13;
export const REFRESH_INTERVAL_MS = 240_000; // 4 phút

export const CONGESTION_COLORS: Record<number | string, string> = {
  0: '#22c55e',
  1: '#f59e0b',
  2: '#ef4444',
  null: '#94a3b8',
};

export const DISTRICT_OPTIONS = [
  { id: null, label: '🗺️ Tất cả quận/huyện' },
  { id: 1, label: 'Hải Châu' },
  { id: 2, label: 'Thanh Khê' },
  { id: 3, label: 'Sơn Trà' },
  { id: 4, label: 'Ngũ Hành Sơn' },
  { id: 5, label: 'Liên Chiểu' },
  { id: 6, label: 'Cẩm Lệ' },
  { id: 7, label: 'Hòa Vang' },
  { id: 8, label: 'Hoàng Sa' },
];
```

---

## 8. Auth Store (store/authStore.ts)

```typescript
interface AuthState {
  token: string | null;
  user: { id: number; email: string; full_name: string; role: string } | null;
  isLoggedIn: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
}
// Persist to localStorage
```

---

## 9. Pages — Chi tiết tính năng

### 9.1 Home (`/`) — Bản đồ giao thông

**Layout:** Map chiếm toàn màn hình. Tất cả UI là overlay.

```
┌─────────────────────────────────────────────────────────────────┐
│  Navbar (overlay, top)                                          │
│  [≡] [🚦 Giao thông Đà Nẵng]      [🔍 Tìm đường]  [User ▼]   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    MAP FULL SCREEN (Mapbox light-v11)     │
│  │ Filter Panel    │                                           │
│  │ (slide từ trái) │    KPI Cards (top-right overlay):         │
│  │                 │    [🔴 2 Kẹt] [🚗 32km/h] [🚨 0 Sự cố]  │
│  │ Quận: [select]  │                                           │
│  │ Mức kẹt: [sel]  │    Weather (top-right dưới KPI):          │
│  │ Tìm đường: [🔍] │    [☀️ 32°C  💧65%  💨2m/s]              │
│  │                 │                                           │
│  │ Legend:         │                              [+]          │
│  │ ● Thông thoáng  │                              [-]          │
│  │ ● Chậm          │                              [📍]         │
│  │ ● Kẹt xe        │                                           │
│  └─────────────────┘                                           │
│                                                                 │
│  Bottom: [Data: 14:30 28/05/2026]  [Cập nhật lại sau 180s]    │
└─────────────────────────────────────────────────────────────────┘
```

**Tính năng:**
1. **2-step loading:** Fetch geometry 1 lần → cache trong memory/localStorage. Poll traffic state mỗi 240s.
2. **Traffic layer:** Vẽ LineString từ geometry, color = congestion_level.
3. **Click vào đường:** Popup tooltip hiện: tên đường, quận, tốc độ, tình trạng, timestamp.
4. **Filter Panel** (slide từ trái, toggle bằng nút ≡):
   - Selectbox quận → filter Mapbox layer expression: `['==', ['get', 'district_id'], selectedId]`
   - Selectbox mức kẹt → filter expression: `['==', ['get', 'congestion_level'], level]`
   - Input tìm tên đường → filter expression: `['in', searchText, ['downcase', ['get', 'name']]]`
   - Nút Reset
5. **AI Prediction Toggle:** Bật → fetch `/api/predict/30min` → thay màu layer theo predicted_level.
6. **Auto-refresh:** React Query polling interval 240_000ms → gọi lại `/api/traffic/state` → update layer data.
7. **KPI Cards overlay:** total_streets, red_count, avg_speed từ traffic state.
8. **Weather widget overlay.**

---

### 9.2 Route Finder (`/route`) — Tìm đường

**Layout:** Split panel — trái là form/kết quả, phải là map.

```
┌─────────────────┬────────────────────────────────────────┐
│ Route Finder    │                                        │
│─────────────────│         MAP (Mapbox light-v11)         │
│ Từ: [input 🔍]  │                                        │
│ Đến: [input 🔍] │   Route highlight (xanh/đỏ gradient)  │
│                 │   Start marker (🟢)                    │
│ [Ngắn nhất]     │   End marker (🔴)                      │
│ [Nhanh nhất]    │                                        │
│─────────────────│                                        │
│ So sánh:        │                                        │
│ ⚡ Ngắn: 5.2km  │                                        │
│ 🚀 Nhanh: 6.1km │                                        │
│─────────────────│                                        │
│ Tuyến đường:    │                                        │
│ ✅ Bạch Đằng   │                                        │
│ 🟡 Lê Duẩn     │                                        │
│ 🔴 Hùng Vương  │                                        │
└─────────────────┴────────────────────────────────────────┘
```

**Tính năng:**
1. Autocomplete tên đường: fetch `/api/streets/midpoints` → fuzzy search (normalize tiếng Việt: đ→d, etc.)
2. Chọn điểm đầu/điểm cuối → call cả 2 API `mode=shortest` và `mode=fastest` song song (Promise.all).
3. Vẽ route trên map: GeoJSON LineString từ `path: [[lat,lng]]`.
4. Hiện bảng so sánh: khoảng cách, thời gian, số đường kẹt.
5. Danh sách các đường đi qua: màu theo congestion_level.
6. Nút "Swap" hoán đổi điểm đầu/cuối.

---

### 9.3 Dashboard (`/dashboard`) — Analytics (Public)

**Layout:** Grid cards + Charts.

**Tính năng:**
1. **KPI row:** avg_speed, red_count, yellow_count, green_count (từ `/api/stats/report`).
2. **Biểu đồ xu hướng theo giờ (Recharts LineChart):** `/api/stats/hourly-trend?days=7` — x=giờ, y=avg_congestion_pct và avg_speed (2 trục).
3. **Heatmap ùn tắc (Recharts hoặc custom grid):** `/api/stats/heatmap` — x=giờ (0-23), y=ngày tuần (T2-CN), color=congestion_pct.
4. **Top 10 đường kẹt nhất:** từ `report.top_congested` — bảng: rank, tên đường, quận, tốc độ trung bình.
5. **Weather card:** `/api/weather/current`.

---

### 9.4 CSGT Dashboard (`/csgt`) — Role: csgt, admin

**Layout:** Full page, không map.

**Tính năng:**
1. **4 KPI Cards:**
   - 🚨 Sự cố đang xảy ra (active_count) + sub: "N đã điều động"
   - 🔴 Đường kẹt xe (red_count) + sub: "N đường đang chậm"
   - 🚗 Tốc độ TB (avg_speed) — chỉ số, đơn vị ở label: "km/h · Tốc độ TB"
   - 📋 Tổng sự cố (total_incidents) + sub: "N đã xử lý"
2. **Gauge tốc độ:** SVG arc gauge, min=0, max=80, giá trị=avg_speed. Màu: xanh≥40, vàng≥20, đỏ<20.
3. **Biểu đồ xu hướng theo giờ (Recharts AreaChart):** 7 ngày gần nhất.
4. **Top 10 đường kẹt nhất (2 cột):**
   - Trái: danh sách rank + nút "🚔 Điều động" căn giữa với từng dòng.
   - Phải: mini map (Mapbox) hiện scatter markers tại vị trí top 10.
5. **Form điều động (Modal):** Khi bấm "Điều động" → modal hiện: ghi chú, mức độ → submit → `POST /api/incidents` với status="dispatched".

---

### 9.5 Incidents (`/incidents`) — Role: csgt, admin

**Layout:** Full page, danh sách.

**Tính năng:**
1. **Filter row (top):** Loại sự cố | Trạng thái | Còn hiệu lực | [🔄 Làm mới] [➕ Thêm mới]
2. **"➕ Thêm mới"** → mở Modal form: street_id, loại, ngày giờ bắt đầu, mức độ, mô tả, trạng thái ban đầu → `POST /api/incidents`.
3. **Stats badges (đồng kích cỡ, min-width: 140px):** 🔴 N Đang xảy ra | 🟡 N Đã điều động | 🟢 N Đã xử lý | 📋 N Tổng.
4. **Batch selection:**
   - Checkbox trái mỗi card (chỉ với incidents chưa resolved).
   - Khi chọn ≥1: hiện thanh "☑️ Đã chọn N" + [✅ Xử lý tất cả] + [✖ Bỏ chọn].
   - Submit → loop `PUT /api/incidents/{id}` với status="resolved" → rerun.
5. **Incident card:** icon loại | #ID · Street ID · timestamp | badge trạng thái | mô tả | thời gian | mức độ | còn hiệu lực.
6. **Action buttons (căn giữa dọc với card):**
   - active: [🚔 Điều động] [✅ Đã xử lý]
   - dispatched: [✅ Đã xử lý]
   - resolved: (không có nút)
   - Admin only: [🗑️ Xóa] + confirm dialog.

---

### 9.6 Admin Users (`/admin/users`) — Role: admin

**Tính năng:**
1. **Bảng người dùng:** STT | Tên | Email | Role (badge) | Trạng thái (Active/Locked) | Hành động.
2. **Hành động:** Khóa/Mở khóa | Vô hiệu hóa (confirm trước khi xóa).
3. **Form tạo user mới (modal):** email, full_name, password, role (admin/csgt/user) → `POST /api/users`.
4. **Role badge:** admin=vàng, csgt=xanh dương, user=xám.

---

### 9.7 Admin Scheduler (`/admin/scheduler`) — Role: admin

**Tính năng:**
1. **Trạng thái scheduler:** Running / Paused (từ `/api/traffic/schedule/state`).
2. **Danh sách jobs:** tên job, interval, next_run.
3. **Nút:** [⏸ Tạm dừng] / [▶️ Tiếp tục] | [🔄 Cào ngay] → `POST /api/traffic/crawl`.
4. **Kết quả crawl:** hiện khi "Cào ngay" xong: N đường đã cập nhật, thời gian.

---

### 9.8 Login (`/login`)

**Layout:** Centered card, nền có map mờ phía sau (hoặc gradient).

**Tính năng:**
1. Form: Email + Password + [Đăng nhập].
2. Submit → `POST /api/auth/login` → lưu token vào authStore + localStorage → redirect theo role:
   - admin → `/admin/users`
   - csgt → `/csgt`
   - user → `/`
3. Hiện lỗi inline nếu sai thông tin.

---

## 10. Navigation & Route Guards

```typescript
// App.tsx routes
/ → Home (public)
/route → RouteFinder (public)
/dashboard → Dashboard (public)
/login → Login (public, redirect nếu đã login)
/csgt → CsgtDashboard (require: csgt | admin)
/incidents → Incidents (require: csgt | admin)
/admin/users → AdminUsers (require: admin)
/admin/scheduler → AdminScheduler (require: admin)
```

**ProtectedRoute component:** check `authStore.isLoggedIn` + role → redirect `/login` nếu chưa auth, redirect `/` nếu không đủ quyền.

**Navbar links theo role:**
- Guest: Bản đồ | Tìm đường | Dashboard | Đăng nhập
- CSGT: Bản đồ | Tìm đường | Dashboard | CSGT Dashboard | Sự cố | [Đăng xuất]
- Admin: Tất cả trên + Admin Users | Admin Scheduler

---

## 11. Axios setup (lib/axios.ts)

```typescript
const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE });

// Request interceptor: tự động thêm Bearer token
api.interceptors.request.use(config => {
  const token = useAuthStore.getState().token;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Response interceptor: 401 → logout
api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) useAuthStore.getState().logout();
    return Promise.reject(err);
  }
);
```

---

## 12. Data fetching patterns

### Geometry (fetch 1 lần, cache localStorage)
```typescript
// hooks/useGeometry.ts
const GEOMETRY_KEY = 'traffic_geometry';
const GEOMETRY_TTL = 3600_000; // 1h

export function useGeometry() {
  return useQuery({
    queryKey: ['geometry'],
    queryFn: async () => {
      const cached = localStorage.getItem(GEOMETRY_KEY);
      if (cached) {
        const { data, ts } = JSON.parse(cached);
        if (Date.now() - ts < GEOMETRY_TTL) return data;
      }
      const res = await trafficApi.getGeometry();
      localStorage.setItem(GEOMETRY_KEY, JSON.stringify({ data: res, ts: Date.now() }));
      return res;
    },
    staleTime: GEOMETRY_TTL,
  });
}
```

### Traffic state (poll 240s)
```typescript
// hooks/useTrafficData.ts
export function useTrafficData() {
  return useQuery({
    queryKey: ['traffic-state'],
    queryFn: () => trafficApi.getState(),
    refetchInterval: 240_000,
    staleTime: 230_000,
  });
}
```

---

## 13. TrafficMap component (components/map/TrafficMap.tsx)

```typescript
// Khởi tạo Mapbox với style sáng
const map = new mapboxgl.Map({
  container: mapRef.current,
  style: 'mapbox://styles/mapbox/light-v11',
  center: DA_NANG_CENTER,
  zoom: DEFAULT_ZOOM,
});

// Khi geometry load xong → thêm source + layer
map.addSource('traffic', {
  type: 'geojson',
  data: buildGeoJSON(geometry, trafficState),
});

map.addLayer({
  id: 'traffic-lines',
  type: 'line',
  source: 'traffic',
  layout: { 'line-join': 'round', 'line-cap': 'round' },
  paint: {
    'line-color': [
      'case',
      ['==', ['get', 'congestion_level'], 0], '#22c55e',
      ['==', ['get', 'congestion_level'], 1], '#f59e0b',
      ['==', ['get', 'congestion_level'], 2], '#ef4444',
      '#94a3b8'
    ],
    'line-width': [
      'interpolate', ['linear'], ['zoom'],
      10, 2,
      14, 5,
      18, 8
    ],
    'line-opacity': 0.9,
  },
});

// Cập nhật traffic state (không reload map):
(map.getSource('traffic') as GeoJSONSource).setData(buildGeoJSON(geometry, newState));

// Click handler → popup
map.on('click', 'traffic-lines', (e) => {
  const { name, district, avg_speed, congestion_level, timestamp } = e.features[0].properties;
  new mapboxgl.Popup()
    .setLngLat(e.lngLat)
    .setHTML(`<b>${name}</b><br>${district}<br>🚗 ${avg_speed} km/h<br>${statusLabel(congestion_level)}`)
    .addTo(map);
});
```

---

## 13.1 buildGeoJSON helper — spec bắt buộc

Hàm này PHẢI được implement chính xác như sau. Không được thay đổi output format.

```typescript
// utils/buildGeoJSON.ts
import { StreetGeometry, TrafficState } from '../types/api.types';

interface GeometryResponse {
  streets: StreetGeometry[];
}
interface StateResponse {
  streets: TrafficState[];
  data_as_of: string | null;
}

export function buildGeoJSON(
  geometry: GeometryResponse,
  state: StateResponse
): GeoJSON.FeatureCollection {
  // Build lookup map: street_id → traffic state
  const stateMap = new Map<number, TrafficState>();
  for (const s of state.streets ?? []) {
    stateMap.set(s.street_id, s);
  }

  const features: GeoJSON.Feature[] = (geometry.streets ?? []).map(street => {
    const traffic = stateMap.get(street.id);
    return {
      type: 'Feature',
      geometry: {
        type: 'LineString',
        coordinates: street.coordinates, // already [lng, lat][]
      },
      properties: {
        street_id: street.id,
        name: street.name,
        district: street.district,
        district_id: street.district_id,
        congestion_level: traffic?.congestion_level ?? null,
        avg_speed: traffic?.avg_speed ?? null,
        max_speed: traffic?.max_speed ?? null,
        timestamp: traffic?.timestamp ?? null,
      },
    };
  });

  return { type: 'FeatureCollection', features };
}
```

> **Quan trọng:** File này đặt tại `src/utils/buildGeoJSON.ts` — thêm `utils/` vào Section 3.

---

```yaml
# docker-compose.yml — thêm service này
frontend_react:
  build:
    context: ./frontend_react
    dockerfile: Dockerfile
  ports:
    - "3000:80"
  environment:
    - VITE_API_BASE=http://backend:8000
    - VITE_MAPBOX_TOKEN=${MAPBOX_TOKEN}
```

```dockerfile
# frontend_react/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

---

## 15. Timezone

Tất cả timestamp từ API là UTC ISO. Hiển thị: convert sang UTC+7.
```typescript
export function fmtTimestampVN(iso: string): string {
  const d = new Date(iso);
  d.setHours(d.getHours() + 7);
  return d.toISOString().replace('T', ' ').substring(0, 19) + ' +07';
}
```

---

## 16. Lưu ý Vietnamese text

Route finder: normalize tên đường khi search.
```typescript
export function normalizeVN(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D');
}
// Filter: normalizeVN(street.name).includes(normalizeVN(searchInput))
```
