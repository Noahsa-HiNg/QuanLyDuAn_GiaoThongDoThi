"""
app.py — Trang chính: Bản đồ Giao thông Đà Nẵng

CHẠY:
    docker compose up frontend
    Truy cập: http://localhost:8501

KIẾN TRÚC:
    Frontend (Streamlit + Pydeck)
        │  HTTP GET /api/traffic/current
        └─► Backend (FastAPI)
                └─► PostgreSQL (traffic_data mới nhất)
"""

import httpx
import pandas as pd
import pydeck as pdk
import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ─────────────────────────────────────────────────────────────────────────────
# 1. CẤU HÌNH TRANG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Giao thông Đà Nẵng",   # Tên tab trình duyệt
    page_icon="🚦",
    layout="wide",                       # Dùng toàn bộ chiều rộng màn hình
)

# ─────────────────────────────────────────────────────────────────────────────
# 2. AUTO-REFRESH MỖI 60 GIÂY
#    st_autorefresh tự reload trang sau mỗi interval (ms)
#    → Bản đồ luôn hiển thị data mới nhất từ backend
# ─────────────────────────────────────────────────────────────────────────────
st_autorefresh(interval=60_000, key="traffic_refresh")

# ─────────────────────────────────────────────────────────────────────────────
# 3. CONSTANTS — Màu sắc theo mức ùn tắc (định dạng RGBA)
#    congestion_level: 0=Xanh, 1=Vàng, 2=Đỏ, None=Xám (chưa có data)
# ─────────────────────────────────────────────────────────────────────────────
CONGESTION_COLORS = {
    0: [34, 197, 94, 220],    # Xanh lá  — thông thoáng
    1: [234, 179, 8, 220],    # Vàng     — chậm
    2: [239, 68, 68, 220],    # Đỏ       — kẹt xe
    None: [156, 163, 175, 150],  # Xám   — chưa có dữ liệu
}

BACKEND_URL = "http://backend:8000"   # URL backend trong Docker network


# ─────────────────────────────────────────────────────────────────────────────
# 4. HÀM LẤY DATA TỪ BACKEND API
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=55)   # Cache 55 giây (ngay dưới interval refresh 60s)
def fetch_traffic(district_id: int = None) -> dict:
    """
    Gọi GET /api/traffic/current từ backend.

    Trả về dict chứa:
        - total_streets, green_count, yellow_count, red_count, no_data_count
        - streets: list chi tiết từng đường (speed, level, geometry...)

    @st.cache_data(ttl=55): Streamlit cache kết quả 55 giây.
    Nếu nhiều user cùng xem → chỉ gọi API 1 lần/phút thay vì mỗi lần load.
    """
    try:
        params = {}
        if district_id:
            params["district_id"] = district_id

        resp = httpx.get(
            f"{BACKEND_URL}/api/traffic/current",
            params=params,
            timeout=10.0,     # Chờ tối đa 10 giây, không block vô tận
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        # Trả về dict rỗng thay vì crash toàn bộ trang
        st.error(f"❌ Không kết nối được backend: {e}")
        return {"total_streets": 0, "streets": []}


@st.cache_data(ttl=300)   # Cache 5 phút (geometry thay đổi ít)
def fetch_streets(district_id: int = None) -> list:
    """
    Gọi GET /api/streets để lấy geometry (tọa độ) của tất cả đường.

    Pydeck cần danh sách tọa độ (list of [lon, lat]) để vẽ PathLayer.
    Vì geometry thay đổi ít → cache 5 phút để giảm tải backend.
    """
    try:
        params = {"page_size": 100}
        if district_id:
            params["district_id"] = district_id

        resp = httpx.get(
            f"{BACKEND_URL}/api/streets",
            params=params,
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# 5. HÀM TẠO DATAFRAME CHO PYDECK
# ─────────────────────────────────────────────────────────────────────────────
def build_map_dataframe(traffic_data: dict) -> pd.DataFrame:
    """
    Chuyển response JSON từ backend thành DataFrame cho Pydeck.

    MỖI ĐOẠN (SEGMENT) = 1 ROW với path + color riêng.
    Điều này cho phép PathLayer vẽ từng đoạn đường với màu khác nhau
    → Đầu đường đỏ, giữa vàng, cuối xanh (giống Google Maps traffic layer).

    Đường có segments (nhiều zone):
      → Mỗi zone → 1 row trong DataFrame
      → PathLayer: N đoạn nhỏ với N màu khác nhau

    Đường chỉ có path (1 zone, fallback):
      → 1 row toàn bộ path với 1 màu
    """
    rows = []
    for street in traffic_data.get("streets", []):
        segments = street.get("segments", [])

        # Tooltip info chung cho cả đường
        tooltip_info = {
            "street_id"       : street["street_id"],
            "name"            : street["street_name"],
            "district"        : street.get("district_name", ""),
            "avg_speed"       : street.get("avg_speed") or 0,
            "max_speed"       : street.get("max_speed") or 50,
            "congestion_label": street.get("congestion_label") or "Chưa có dữ liệu",
            "timestamp_vn"    : street.get("timestamp_vn") or "—",
        }

        if segments:
            # ── Đường có nhiều zone → 1 row per segment ─────────────
            for seg in segments:
                level = seg.get("congestion_level")
                color = seg.get("color") or CONGESTION_COLORS.get(level, CONGESTION_COLORS[None])
                rows.append({
                    **tooltip_info,
                    "congestion"      : level,
                    "congestion_label": _congestion_label(level) or tooltip_info["congestion_label"],
                    "avg_speed"       : seg.get("avg_speed") or tooltip_info["avg_speed"],
                    "color"           : color,
                    "path"            : seg.get("path"),   # [[lon, lat], ...]
                    "lat"             : None,
                    "lon"             : None,
                })
        else:
            # ── Fallback: đường chưa có segment data ─────────────────
            level = street.get("congestion_level")
            color = CONGESTION_COLORS.get(level, CONGESTION_COLORS[None])
            lat   = street.get("lat") or 16.0544
            lon   = street.get("lon") or 108.2022
            rows.append({
                **tooltip_info,
                "congestion"      : level,
                "color"           : color,
                "path"            : street.get("path"),
                "lat"             : lat,
                "lon"             : lon,
            })

    return pd.DataFrame(rows)


def _congestion_label(level) -> str:
    return {0: "🟢 Thông thoáng", 1: "🟡 Chậm", 2: "🔴 Kẹt xe"}.get(level, "")



# ─────────────────────────────────────────────────────────────────────────────
# 6. XÂY DỰNG CÁC LAYER PYDECK
# ─────────────────────────────────────────────────────────────────────────────
def build_path_layer(df: pd.DataFrame) -> pdk.Layer:
    """
    PathLayer — Vẽ MỖI ĐƯỜNG như ĐƯỜNG THẸNG MÀU TRÊN BẢN ĐỒ (giống Google Maps).

    Khác ScatterplotLayer (chấm tròn):
      PathLayer vẽ đoạn thẳng nối các điểm lat/lon thực của đường.

    Tham số quan trọng:
      get_path       : Cột chứa list [[lon, lat], [lon, lat], ...]
      get_color      : Màu [R, G, B, A] theo mức ùn tắc
      get_width      : Độ rộng đường (mét)
      width_min_pixels: Độ rộng tối thiểu (pixel) — giữ nét khi zoom xa
    """
    # Chỉ lấy những đường có path thực
    df_path = df[df["path"].notna()].copy()

    if df_path.empty:
        return None

    return pdk.Layer(
        "PathLayer",
        data=df_path,
        get_path="path",              # [[lon, lat], [lon, lat], ...]
        get_color="color",            # [R, G, B, A]
        get_width=12,                 # 12 mét — đủ rộng để thấy rõ
        width_min_pixels=3,           # Tối thiểu 3px khi zoom ra xa
        width_max_pixels=20,          # Tối đa 20px khi zoom vào gần
        pickable=True,                # Click/hover được
        auto_highlight=True,          # Sáng lên khi hover
        joint_rounded=True,           # Góc nối tuyến được làm tròn
        cap_rounded=True,             # Đầu đường có viettcap tròn (giống Google Maps)
    )


def build_scatter_fallback_layer(df: pd.DataFrame) -> pdk.Layer:
    """
    ScatterplotLayer nhỏ — Hiển thị những đường KHÔNG có geometry path thực.
    Hiển thị như chấm tròn tại tọa độ trung tâm ước tính.
    """
    df_no_path = df[df["path"].isna()].copy()

    if df_no_path.empty:
        return None

    return pdk.Layer(
        "ScatterplotLayer",
        data=df_no_path,
        get_position=["lon", "lat"],
        get_radius=200,
        get_fill_color="color",
        pickable=True,
        auto_highlight=True,
        opacity=0.8,
    )


def build_text_layer(df: pd.DataFrame) -> pdk.Layer:
    """
    TextLayer — Hiển thị TÊN ĐƯỜNG + TỐC ĐỘ dạng text nổi trên bản đồ.

    Tham số quan trọng:
        get_text      : Chuỗi text hiển thị
        get_size      : Kích thước font (pixels)
        get_angle     : Góc nghiêng (0 = ngang)
        get_text_anchor: Điểm neo text ("middle" = căn giữa)
    """
    # Thêm cột text kết hợp tên + tốc độ
    df = df.copy()
    df["display_text"] = df.apply(
        lambda r: f"{r['name']}\n{r['avg_speed']:.0f} km/h"
        if r["avg_speed"] > 0 else r["name"],
        axis=1
    )

    return pdk.Layer(
        "TextLayer",
        data=df,
        get_position=["lon", "lat"],
        get_text="display_text",
        get_size=12,
        get_color=[255, 255, 255, 220],   # Trắng, hơi trong suốt
        get_angle=0,
        get_text_anchor="'middle'",
        get_alignment_baseline="'center'",
        pickable=False,   # Text không cần click
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. CẤU HÌNH VIEWPORT (GÓC NHÌN BẢN ĐỒ)
# ─────────────────────────────────────────────────────────────────────────────
def get_initial_view() -> pdk.ViewState:
    """
    ViewState định nghĩa:
        latitude/longitude : Tọa độ trung tâm bản đồ (trung tâm Đà Nẵng)
        zoom               : Mức zoom (12 = thấy cả thành phố, 15 = thấy đường phố)
        pitch              : Góc nghiêng 3D (0 = nhìn thẳng từ trên xuống)
        bearing            : Góc xoay bản đồ (0 = Bắc lên trên)
    """
    return pdk.ViewState(
        latitude=16.0544,    # Vĩ độ trung tâm Đà Nẵng
        longitude=108.2022,  # Kinh độ trung tâm Đà Nẵng
        zoom=12,
        pitch=0,
        bearing=0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 8. TOOLTIP KHI HOVER/CLICK VÀO ĐIỂM
# ─────────────────────────────────────────────────────────────────────────────
TOOLTIP = {
    # {column_name} = giá trị từ DataFrame row đang hover
    "html": """
        <div style="
            background: rgba(15,23,42,0.95);
            padding: 12px 16px;
            border-radius: 8px;
            border-left: 4px solid #3b82f6;
            font-family: 'Segoe UI', sans-serif;
            min-width: 200px;
        ">
            <b style="font-size:14px; color:#f1f5f9">{name}</b><br/>
            <span style="color:#94a3b8; font-size:12px">{district}</span>
            <hr style="border-color:#334155; margin:8px 0"/>
            <div style="color:#e2e8f0; font-size:13px">
                🚗 Tốc độ: <b>{avg_speed} km/h</b> / {max_speed} km/h<br/>
                🚦 Tình trạng: <b>{congestion_label}</b><br/>
                🕐 Cập nhật: {timestamp_vn}
            </div>
        </div>
    """,
    "style": {"backgroundColor": "transparent", "color": "white"},
}


# ─────────────────────────────────────────────────────────────────────────────
# 9. GIAO DIỆN CHÍNH
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # ── Header ────────────────────────────────────────────────
    st.title("🚦 Bản đồ Giao thông Đà Nẵng")
    st.caption("Dữ liệu từ TomTom Traffic API · Cập nhật mỗi 30 phút · Tự động làm mới sau 60 giây")

    # ── Sidebar: Bộ lọc ───────────────────────────────────────
    with st.sidebar:
        st.header("🔽 Bộ lọc")

        # Chọn quận — dùng ID thực tế từ DB
        district_options = {
            "Tất cả": None,
            "Hải Châu": 1, "Thanh Khê": 2, "Sơn Trà": 3,
            "Ngũ Hành Sơn": 4, "Liên Chiểu": 5,
            "Cẩm Lệ": 6, "Hòa Vang": 7, "Hoàng Sa": 8,
        }
        selected_district = st.selectbox(
            "Quận/huyện", options=list(district_options.keys())
        )
        district_id = district_options[selected_district]

        st.divider()

        # Chú thích màu sắc
        st.subheader("Chú thích")
        st.markdown("""
        🟢 **Xanh** — Thông thoáng (≥ 70% free flow)
        🟡 **Vàng** — Chậm (40–70% free flow)
        🔴 **Đỏ** — Kẹt xe (< 40% free flow)
        ⚪ **Xám** — Chưa có dữ liệu
        """)

    # ── Lấy dữ liệu từ backend ────────────────────────────────
    with st.spinner("Đang tải dữ liệu giao thông..."):
        traffic = fetch_traffic(district_id)

    if not traffic.get("streets"):
        st.warning("Chưa có dữ liệu giao thông. Backend đang khởi động?")
        return

    # ── KPI Cards (4 chỉ số tổng quan) ───────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🛣️ Tổng tuyến đường", traffic["total_streets"])
    col2.metric("🟢 Thông thoáng",      traffic["green_count"])
    col3.metric("🟡 Chậm",             traffic["yellow_count"])
    col4.metric("🔴 Kẹt xe",           traffic["red_count"])

    st.caption(f"Dữ liệu tính đến: **{traffic.get('data_as_of', '—')}**")
    st.divider()

    # ── Xây dựng DataFrame cho Pydeck ─────────────────────────
    df = build_map_dataframe(traffic)

    if df.empty:
        st.info("Không có dữ liệu để hiển thị.")
        return

    # ── Tạo layers ──────────────────────────────────────────
    # PathLayer: vẽ đường thẳng cho đường có geometry thực
    path_layer = build_path_layer(df)
    # ScatterplotLayer: chấm tròn fallback cho đường chưa có geometry
    scatter_layer = build_scatter_fallback_layer(df)

    # Chỉ thêm layer vào Deck nếu không None
    layers = [l for l in [path_layer, scatter_layer] if l is not None]

    # ── Tạo Pydeck Deck (object chính) ───────────────────────
    deck = pdk.Deck(
        layers=layers,
        initial_view_state=get_initial_view(),
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        tooltip=TOOLTIP,
    )

    # ── Render bản đồ vào Streamlit ──────────────────────────
    # use_container_width=True → bản đồ tự động chiếm toàn bộ chiều rộng
    # height=600 → chiều cao cố định 600px
    st.pydeck_chart(deck, use_container_width=True, height=600)

    # ── Bảng danh sách đường bên dưới bản đồ ─────────────────
    st.subheader("📋 Chi tiết tất cả tuyến đường")

    # Lọc cột hiển thị và đổi tên cho dễ đọc
    display_df = df[[
        "name", "district", "avg_speed", "max_speed",
        "congestion_label", "timestamp_vn"
    ]].rename(columns={
        "name"            : "Tên đường",
        "district"        : "Quận",
        "avg_speed"       : "Tốc độ (km/h)",
        "max_speed"       : "Giới hạn (km/h)",
        "congestion_label": "Tình trạng",
        "timestamp_vn"    : "Cập nhật lúc",
    })

    # Sắp xếp: đường kẹt nhất lên đầu
    display_df = display_df.sort_values("Tốc độ (km/h)")

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 10. ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
