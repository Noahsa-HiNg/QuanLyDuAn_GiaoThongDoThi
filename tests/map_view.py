"""
tests/map_view.py  (v2 — PathLayer đúng, CARTO tiles, không cần Mapbox token)
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from datetime import datetime
import streamlit as st

st.set_page_config(
    page_title="🗺️ Traffic Map — Đà Nẵng",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background: #0f172a; color: #e2e8f0; }
    [data-testid="stSidebar"] { background: #1e293b; }
</style>
""", unsafe_allow_html=True)

BASE         = Path(__file__).parent
PER_SEG_FILE = BASE / "test_tomtom_centroid" / "results" / "per_segment_results.json"
DISPLAY_FILE = BASE / "test_tomtom_centroid" / "results" / "display_data.json"
HERE_MAPPED_FILE = BASE / "test_here_bbox" / "results" / "display_here_72k.json"
SPEED_FILE   = BASE / "test_tomtom_centroid" / "results" / "all_streets_results.json"
PER_SEG_CRAWL= BASE / "test_tomtom_centroid" / "crawl_per_segment.py"


@st.cache_data(ttl=120, show_spinner="Đang tải dữ liệu...")
def load_data(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def cong_color(level: int, alpha: int = 220) -> list:
    return {
        -1: [100, 116, 139, 120],  # xám — không có data
         0: [34,  197,  94, alpha],  # xanh
         1: [251, 191,  36, alpha],  # vàng
         2: [239,  68,  68, alpha],  # đỏ
    }.get(level, [100, 116, 139, 120])


# ─── HEADER ──────────────────────────────────────────────────────────────────
st.title("🚦 Bản Đồ Giao Thông Thời Gian Thực — Đà Nẵng")

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🎛️ Nguồn Dữ Liệu")
    data_source = st.radio(
        "Chọn nguồn dữ liệu (72,742 OSM segments):",
        ["HERE Bbox (Map từ 2004 HERE segs)", "TomTom (Data cũ)"],
        index=0
    )

# ─── LOAD DATA ───────────────────────────────────────────────────────────────
if "HERE" in data_source:
    data = load_data(str(HERE_MAPPED_FILE))
    data_mode = "display"
else:
    per_seg_data = load_data(str(PER_SEG_FILE))
    display_data = load_data(str(DISPLAY_FILE))
    if per_seg_data and len(per_seg_data.get("results", [])) >= 1000:
        data = per_seg_data
        data_mode = "per_segment"
    else:
        data = display_data
        data_mode = "display"

if data is None:
    st.warning("⚠️ Chưa có dữ liệu cho nguồn này.")
    st.stop()

# Per-segment hoặc display_data đều dùng chung interface
if data_mode == "per_segment":
    segments = data.get("results", [])
    def get_path(r): return r.get("tomtom_path") or []
else:
    segments = data.get("segments", [])
    def get_path(r): return r.get("path") or []

built_at = data.get("built_at", "")
if built_at:
    dt = datetime.fromisoformat(built_at)
    st.caption(f"📡 Dữ liệu: {dt.strftime('%H:%M %d/%m/%Y')} · {len(segments):,} segments")
else:
    st.caption(f"📡 Nguồn: {data.get('source', 'Unknown')} · {len(segments):,} segments")

# ─── SIDEBAR FILTERS ─────────────────────────────────────────────────────────
with st.sidebar:
    st.divider()
    st.header("🎛️ Bộ Lọc")

    district_list = sorted(set(s.get("district", "N/A") for s in segments))
    sel_districts = st.multiselect("Quận/Huyện", district_list, default=district_list)

    sel_cong = st.multiselect(
        "Mức tắc nghẽn",
        ["🟢 Thông thoáng", "🟡 Chậm", "🔴 Tắc nghẽn", "⬜ Không có dữ liệu"],
        default=["🟢 Thông thoáng", "🟡 Chậm", "🔴 Tắc nghẽn"],
    )
    cong_filter = {"🟢 Thông thoáng": 0, "🟡 Chậm": 1, "🔴 Tắc nghẽn": 2, "⬜ Không có dữ liệu": -1}
    sel_levels = {cong_filter[s] for s in sel_cong}

    show_unnamed = st.checkbox("Hiện đường không có tốc độ (xám)", value=False)

    line_w = st.slider("Độ dày đường", 1, 12, 5)

    st.divider()
    if st.button("🔄 Rebuild display data", use_container_width=True):
        with st.spinner("Đang build lại..."):
            import subprocess
            r = subprocess.run(
                [sys.executable, str(BUILD_SCRIPT)],
                capture_output=True, text=True, cwd=str(BASE.parent)
            )
        st.cache_data.clear()
        st.rerun()

    st.divider()
    cd = data.get("congestion_dist", {})
    st.markdown("**Thống kê toàn TP:**")
    st.markdown(f"- ⬜ Không data: {cd.get('no_data (⬜)', 0):,}")
    st.markdown(f"- 🟢 Thông: {cd.get('smooth (🟢)', 0):,}")
    st.markdown(f"- 🟡 Chậm: {cd.get('slow (🟡)', 0):,}")
    st.markdown(f"- 🔴 Tắc: {cd.get('congested (🔴)', 0):,}")

# ─── FILTER ──────────────────────────────────────────────────────────────────
filtered = []
for s in segments:
    lvl  = s.get("congestion_level", -1)
    dist = s.get("district", "N/A")
    if dist not in sel_districts:
        continue
    if lvl == -1 and not show_unnamed:
        continue
    if lvl not in sel_levels and not (lvl == -1 and show_unnamed):
        continue
    filtered.append(s)

# ─── METRICS ─────────────────────────────────────────────────────────────────
total  = len(filtered)
smooth = sum(1 for s in filtered if s.get("congestion_level") == 0)
slow   = sum(1 for s in filtered if s.get("congestion_level") == 1)
cong   = sum(1 for s in filtered if s.get("congestion_level") == 2)
nodata = sum(1 for s in filtered if s.get("congestion_level") == -1)

speeds = [s["speed_kmh"] for s in filtered if s.get("speed_kmh") is not None]
avg_spd = sum(speeds) / len(speeds) if speeds else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("📍 Segments", f"{total:,}")
c2.metric("🟢 Thông",    f"{smooth:,}")
c3.metric("🟡 Chậm",     f"{slow:,}")
c4.metric("🔴 Tắc",      f"{cong:,}")
c5.metric("🚗 Avg speed", f"{avg_spd:.1f} km/h" if avg_spd else "N/A")

# ─── BUILD MAP ROWS ──────────────────────────────────────────────────────────
map_rows = []
for s in filtered:
    path = get_path(s)
    if not path or len(path) < 2:
        lo, la = s.get("lon", 108.2), s.get("lat", 16.05)
        path = [[lo - 0.0001, la], [lo + 0.0001, la]]

    # Tên hiển thị trong tooltip
    seg_len = s.get("length_km") or 0
    len_str = f"{seg_len:.2f} km" if seg_len else "N/A"

    map_rows.append({
        "path"    : path,
        "color"   : cong_color(s.get("congestion_level", -1)),
        "name"    : s.get("name", "N/A"),
        "district": s.get("district", "N/A"),
        "speed"   : s.get("speed_kmh") or "N/A",
        "freeflow": s.get("freeflow_kmh", "N/A"),
        "status"  : s.get("congestion_label", "N/A"),
        "length"  : len_str,
    })

# ─── PYDECK MAP ──────────────────────────────────────────────────────────────
try:
    import pydeck as pdk

    layer = pdk.Layer(
        "PathLayer",
        data=map_rows,
        get_path="path",
        get_color="color",
        get_width=line_w,
        width_min_pixels=2,
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 100],
    )

    view = pdk.ViewState(
        latitude=16.047, longitude=108.206,
        zoom=11.5, pitch=0,
    )

    tooltip = {
        "html": (
            "<div style='background:#1e293b;color:#e2e8f0;padding:10px;"
            "border-radius:8px;font-family:sans-serif;min-width:180px'>"
            "<b style='color:#38bdf8;font-size:1em'>{name}</b><br/>"
            "📍 {district}<br/>"
            "🚗 <b>{speed} km/h</b> | free flow: {freeflow}<br/>"
            "{status}<br/>"
            "📏 {length}"
            "</div>"
        ),
        "style": {"backgroundColor": "transparent"},
    }

    # CARTO Dark Matter — miễn phí, không cần Mapbox token
    CARTO_DARK = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip=tooltip,
        map_style=CARTO_DARK,
    )

    st.pydeck_chart(deck, use_container_width=True, height=600)

except ImportError:
    st.error("Cài pydeck: `pip install pydeck`")

# ─── LEGEND ──────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='display:flex;gap:24px;padding:8px 0;font-size:0.9em'>"
    "<span>🟢 Thông thoáng (>70% free flow)</span>"
    "<span>🟡 Chậm (40–70%)</span>"
    "<span>🔴 Tắc nghẽn (<40%)</span>"
    "<span style='color:#94a3b8'>⬜ Không có dữ liệu TomTom</span>"
    "</div>",
    unsafe_allow_html=True
)

# ─── TABLE ───────────────────────────────────────────────────────────────────
with st.expander(f"📋 Danh sách {total:,} segments"):
    import pandas as pd
    df = pd.DataFrame([{
        "Tên đường" : s.get("name", "N/A"),
        "Quận"      : s.get("district", "N/A"),
        "Tốc độ"    : f"{s.get('speed_kmh', 'N/A')} km/h",
        "Trạng thái": s.get("congestion_label", "N/A"),
        "Chiều dài" : f"{s.get('length_km', 0):.2f} km",
    } for s in filtered])
    st.dataframe(df, use_container_width=True, hide_index=True, height=300)
