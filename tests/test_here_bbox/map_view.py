"""
tests/test_here_bbox/map_view.py
================================
Dashboard trực quan hóa dữ liệu HERE Traffic Flow Bbox
- PathLayer: vẽ đường theo geometry thực tế từ HERE
- Màu theo mức tắc nghẽn: xanh / vàng / đỏ
- Sidebar: lọc quận, mức tắc, JamFactor
- Tooltip chi tiết: tốc độ, freeflow, confidence, jamFactor

Chạy: streamlit run tests/test_here_bbox/map_view.py
"""

import sys, os, json
from pathlib import Path
from datetime import datetime
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

st.set_page_config(
    page_title="HERE Traffic — Đà Nẵng",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background: #0f172a; color: #e2e8f0; }
    [data-testid="stSidebar"] { background: #1e293b; }
    [data-testid="metric-container"] {
        background: #1e293b; border-radius: 10px; padding: 12px;
    }
</style>
""", unsafe_allow_html=True)

RESULTS_FILE = Path(__file__).parent / "results" / "here_results.json"
CRAWL_SCRIPT = Path(__file__).parent / "crawl.py"


@st.cache_data(ttl=60, show_spinner="Đang tải dữ liệu HERE...")
def load_data(path: str) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def cong_color(level: int, jam: float = 0) -> list:
    alpha = 230
    if level == 0:   return [34,  197,  94,  alpha]   # xanh
    if level == 1:   return [251, 191,  36,  alpha]   # vàng
    if level == 2:   return [239,  68,  68,  alpha]   # đỏ
    return [100, 116, 139, 150]


# ─── HEADER ──────────────────────────────────────────────────────────────────
st.title("🚦 HERE Traffic Flow — Đà Nẵng Real-time")

data = load_data(str(RESULTS_FILE))

if data is None:
    st.warning("⚠️ Chưa có dữ liệu. Chạy trước:")
    st.code("python tests/test_here_bbox/crawl.py", language="bash")
    st.stop()

segments = data.get("segments", [])
crawl_time = data.get("crawl_time", "")
if crawl_time:
    dt = datetime.fromisoformat(crawl_time)
    age_s = (datetime.now() - dt).total_seconds()
    age_str = f"{int(age_s//60)} phút" if age_s >= 60 else f"{int(age_s)} giây"
    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.caption(f"📡 Cập nhật: {dt.strftime('%H:%M:%S %d/%m/%Y')}  ({age_str} trước)")
    col_info2.caption(f"📊 Nguồn: HERE Traffic Flow API v7 · {data['api_calls']} calls · {data['api_time_s']}s")
    col_info3.caption(f"🗺️ Phủ sóng: 7 quận · {len(segments):,} road segments")

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🎛️ Bộ Lọc")

    district_list = sorted(set(s.get("district", "N/A") for s in segments))
    sel_districts = st.multiselect("Quận / Huyện", district_list, default=district_list)

    st.markdown("**Mức tắc nghẽn:**")
    show_smooth = st.checkbox("🟢 Thông thoáng", value=True)
    show_slow   = st.checkbox("🟡 Chậm",         value=True)
    show_cong   = st.checkbox("🔴 Tắc nghẽn",    value=True)
    sel_levels  = set()
    if show_smooth: sel_levels.add(0)
    if show_slow:   sel_levels.add(1)
    if show_cong:   sel_levels.add(2)

    min_conf = st.slider("Confidence tối thiểu", 0.0, 1.0, 0.0, 0.1)
    max_jam  = st.slider("JamFactor tối đa (0=thông, 10=tắc)", 0, 10, 10)
    line_w   = st.slider("Độ dày đường", 2, 15, 6)

    st.divider()
    if st.button("🔄 Cào lại dữ liệu", use_container_width=True):
        import subprocess
        with st.spinner("Đang cào HERE API (~13s)..."):
            r = subprocess.run(
                [sys.executable, str(CRAWL_SCRIPT)],
                capture_output=True, text=True,
                cwd=str(CRAWL_SCRIPT.parent.parent.parent),
            )
        st.cache_data.clear()
        if r.returncode == 0:
            st.success("✅ Xong!")
            st.rerun()
        else:
            st.error(f"❌ Lỗi:\n{r.stderr[-400:]}")

    st.divider()
    st.markdown("**Thống kê toàn TP:**")
    for d in district_list:
        n = sum(1 for s in segments if s["district"] == d)
        st.markdown(f"- **{d}**: {n:,} segs")

# ─── FILTER ──────────────────────────────────────────────────────────────────
filtered = [
    s for s in segments
    if s.get("district") in sel_districts
    and s.get("congestion_level", 0) in sel_levels
    and s.get("confidence", 0) >= min_conf
    and s.get("jam_factor", 0) <= max_jam
]

# ─── METRICS ─────────────────────────────────────────────────────────────────
total  = len(filtered)
smooth = sum(1 for s in filtered if s.get("congestion_level") == 0)
slow   = sum(1 for s in filtered if s.get("congestion_level") == 1)
cong   = sum(1 for s in filtered if s.get("congestion_level") == 2)

speeds    = [s["speed_kmh"]  for s in filtered if s.get("speed_kmh")]
jams      = [s["jam_factor"] for s in filtered if s.get("jam_factor") is not None]
confs     = [s["confidence"] for s in filtered if s.get("confidence") is not None]
avg_speed = sum(speeds) / len(speeds) if speeds else 0
avg_jam   = sum(jams)   / len(jams)   if jams   else 0
avg_conf  = sum(confs)  / len(confs)  if confs  else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("📍 Segments",     f"{total:,}")
c2.metric("🟢 Thông",        f"{smooth:,}")
c3.metric("🟡 Chậm",         f"{slow:,}")
c4.metric("🔴 Tắc",          f"{cong:,}")
c5.metric("🚗 Avg speed",    f"{avg_speed:.1f} km/h")
c6.metric("🌡️ Avg JamFactor", f"{avg_jam:.2f}/10")

# ─── BUILD MAP DATA ───────────────────────────────────────────────────────────
map_rows = []
for s in filtered:
    path = s.get("path")
    if not path or len(path) < 2:
        lo = s.get("center_lon") or 108.206
        la = s.get("center_lat") or 16.047
        path = [[lo - 0.0001, la], [lo + 0.0001, la]]

    jam    = s.get("jam_factor", 0)
    speed  = s.get("speed_kmh", 0)
    ff     = s.get("freeflow_kmh", 60)
    conf   = s.get("confidence", 0)
    district = s.get("district", "N/A")

    map_rows.append({
        "path"     : path,
        "color"    : cong_color(s.get("congestion_level", 0), jam),
        "district" : district,
        "speed"    : speed,
        "freeflow" : ff,
        "jam"      : jam,
        "conf"     : round(conf, 2),
        "status"   : s.get("congestion_label", "N/A"),
        "pts"      : len(path),
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
        highlight_color=[255, 255, 255, 120],
    )

    view = pdk.ViewState(
        latitude=16.047, longitude=108.206,
        zoom=11.5, pitch=0,
    )

    tooltip = {
        "html": (
            "<div style='background:#1e293b;color:#e2e8f0;padding:10px;"
            "border-radius:8px;font-family:sans-serif;min-width:200px'>"
            "<b style='color:#38bdf8'>📍 {district}</b><br/>"
            "🚗 <b>{speed} km/h</b>  |  freeflow: {freeflow} km/h<br/>"
            "🌡️ JamFactor: <b>{jam}</b> / 10<br/>"
            "📊 Confidence: {conf}<br/>"
            "🔖 {status}<br/>"
            "<small style='color:#64748b'>PATH: {pts} điểm</small>"
            "</div>"
        ),
        "style": {"backgroundColor": "transparent"},
    }

    CARTO_DARK = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"

    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        tooltip=tooltip,
        map_style=CARTO_DARK,
    )

    st.pydeck_chart(deck, use_container_width=True, height=580)

except ImportError:
    st.error("Cài pydeck: `pip install pydeck`")
    st.stop()

# ─── LEGEND + INFO ───────────────────────────────────────────────────────────
st.markdown(
    "<div style='display:flex;gap:24px;padding:6px 0;font-size:0.85em;color:#94a3b8'>"
    "<span style='color:#22c55e'>🟢 Thông thoáng (&gt;70% freeflow)</span>"
    "<span style='color:#fbbf24'>🟡 Chậm (40–70%)</span>"
    "<span style='color:#ef4444'>🔴 Tắc nghẽn (&lt;40%)</span>"
    "<span>· Nguồn: HERE Traffic Flow v7 · Geometry: shape links</span>"
    "</div>",
    unsafe_allow_html=True,
)

# ─── DATA TABLE ──────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["📋 Danh sách segments", "📊 Thống kê theo quận"])

with tab1:
    import pandas as pd
    df = pd.DataFrame([{
        "Quận"        : s.get("district"),
        "Speed (km/h)": s.get("speed_kmh"),
        "Freeflow"    : s.get("freeflow_kmh"),
        "JamFactor"   : s.get("jam_factor"),
        "Confidence"  : round(s.get("confidence", 0), 2),
        "Trạng thái"  : s.get("congestion_label"),
    } for s in filtered])
    st.dataframe(df, use_container_width=True, hide_index=True, height=280)

with tab2:
    import pandas as pd
    district_stats = {}
    for s in filtered:
        d = s.get("district", "N/A")
        if d not in district_stats:
            district_stats[d] = {"n": 0, "speeds": [], "jams": [], "c0": 0, "c1": 0, "c2": 0}
        district_stats[d]["n"] += 1
        district_stats[d]["speeds"].append(s.get("speed_kmh", 0))
        district_stats[d]["jams"].append(s.get("jam_factor", 0))
        district_stats[d][f"c{s.get('congestion_level', 0)}"] += 1

    rows = []
    for d, v in sorted(district_stats.items(), key=lambda x: -x[1]["n"]):
        rows.append({
            "Quận"        : d,
            "Segments"    : v["n"],
            "Avg Speed"   : round(sum(v["speeds"])/len(v["speeds"]), 1),
            "Avg Jam"     : round(sum(v["jams"])/len(v["jams"]), 2),
            "🟢 Thông"    : v["c0"],
            "🟡 Chậm"     : v["c1"],
            "🔴 Tắc"      : v["c2"],
        })
    df2 = pd.DataFrame(rows)
    st.dataframe(df2, use_container_width=True, hide_index=True)
