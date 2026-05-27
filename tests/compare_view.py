"""
tests/compare_view.py
======================
Dashboard so sánh 2 phương pháp cào dữ liệu:
  - TomTom Point (OSM Centroid)
  - HERE Bbox Flow

Chạy: streamlit run tests/compare_view.py
      (từ thư mục gốc QuanLyDuAn_GiaoThongDoThi)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import subprocess
import threading
from pathlib import Path
from datetime import datetime

import streamlit as st

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="So Sánh Phương Pháp Cào Traffic",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── PATHS ───────────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
TOMTOM_RESULT     = BASE / "test_tomtom_centroid" / "results" / "tomtom_results.json"
TOMTOM_ALL_RESULT = BASE / "test_tomtom_centroid" / "results" / "all_streets_results.json"
HERE_RESULT       = BASE / "test_here_bbox"       / "results" / "here_results.json"
TOMTOM_CRAWL      = BASE / "test_tomtom_centroid" / "crawl.py"
TOMTOM_ALL_CRAWL  = BASE / "test_tomtom_centroid" / "crawl_all.py"
HERE_CRAWL        = BASE / "test_here_bbox"       / "crawl.py"


# ─── HELPER ──────────────────────────────────────────────────────────────────
def load_json(path: Path) -> dict | None:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None

def congestion_color(level: int) -> str:
    return {0: "#22c55e", 1: "#f59e0b", 2: "#ef4444"}.get(level, "#9ca3af")

def congestion_badge(level: int, label: str) -> str:
    color = congestion_color(level)
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:9999px;font-size:0.8em">{label}</span>'


# ─── CUSTOM CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #334155;
    }
    .metric-value { font-size: 2em; font-weight: 700; color: #38bdf8; }
    .metric-label { color: #94a3b8; font-size: 0.85em; margin-top: 4px; }
    .method-badge-tomtom {
        background: #1d4ed8; color: white;
        padding: 4px 12px; border-radius: 9999px; font-size: 0.9em;
    }
    .method-badge-here {
        background: #7c3aed; color: white;
        padding: 4px 12px; border-radius: 9999px; font-size: 0.9em;
    }
    .winner { color: #22c55e; font-weight: 600; }
    .loser  { color: #f87171; }
    .stDataFrame { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# ─── HEADER ──────────────────────────────────────────────────────────────────
st.title("🚦 So Sánh Phương Pháp Cào Dữ Liệu Traffic")
st.markdown("Đà Nẵng Urban Traffic Management — Test & Benchmark Dashboard")
st.divider()


# ─── SIDEBAR: RUN CRAWL ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Điều Khiển")

    st.subheader("🔵 TomTom Centroid")
    max_tt = st.number_input("Số đường tối đa", 10, 3588, 100, 10, key="max_tt")
    if st.button("▶ Chạy TomTom Crawl", type="primary", use_container_width=True):
        with st.spinner(f"Đang cào {max_tt} đường (TomTom)..."):
            env = os.environ.copy()
            env["MAX_STREETS"] = str(max_tt)
            result = subprocess.run(
                [sys.executable, str(TOMTOM_CRAWL)],
                capture_output=True, text=True, env=env,
                cwd=str(BASE.parent)
            )
            if result.returncode == 0:
                st.success("✅ Hoàn tất!")
            else:
                st.error(f"❌ Lỗi:\n{result.stderr[-500:]}")
        st.rerun()

    st.divider()

    st.subheader("🟣 HERE Bbox")
    here_key = st.text_input(
        "HERE API Key",
        value=os.getenv("HERE_API_KEY", ""),
        type="password",
        help="Lấy miễn phí tại developer.here.com"
    )
    if st.button("▶ Chạy HERE Crawl", type="primary", use_container_width=True):
        if not here_key:
            st.error("Cần nhập HERE API Key!")
        else:
            with st.spinner("Đang cào 7 quận (HERE Bbox)..."):
                env = os.environ.copy()
                env["HERE_API_KEY"] = here_key
                result = subprocess.run(
                    [sys.executable, str(HERE_CRAWL)],
                    capture_output=True, text=True, env=env,
                    cwd=str(BASE.parent)
                )
                if result.returncode == 0:
                    st.success("✅ Hoàn tất!")
                else:
                    st.error(f"❌ Lỗi:\n{result.stderr[-500:]}")
            st.rerun()

    st.divider()
    if st.button("🔄 Refresh kết quả", use_container_width=True):
        st.rerun()


# ─── LOAD DATA ───────────────────────────────────────────────────────────────
# Ưu tiên dùng full crawl nếu có
tt_data   = load_json(TOMTOM_ALL_RESULT) or load_json(TOMTOM_RESULT)
here_data = load_json(HERE_RESULT)

if not tt_data and not here_data:
    st.info("👆 Chạy ít nhất 1 phương pháp ở sidebar để xem kết quả.")
    st.stop()


# ─── TAB LAYOUT ──────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 So Sánh Tổng Quan",
    "🔵 TomTom Chi Tiết",
    "🟣 HERE Chi Tiết",
    "🗺️ Bản Đồ",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1: SO SÁNH TỔNG QUAN
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("📊 Bảng So Sánh Các Chỉ Số")

    # Build comparison table
    def fmt(val, unit=""):
        return f"{val}{unit}" if val is not None else "N/A"

    # Xác định winner cho từng chỉ số
    def winner(tt_val, here_val, higher_is_better=True):
        if tt_val is None or here_val is None:
            return None, None
        if higher_is_better:
            return ("tt", "here") if tt_val >= here_val else ("here", "tt")
        else:
            return ("tt", "here") if tt_val <= here_val else ("here", "tt")

    rows = []
    metrics = [
        ("API Calls", "api_calls_made", "api_calls", False, "calls"),
        ("Thời gian cào (s)", "total_time_s", "total_time_s", False, "s"),
        ("Số đường/segment lấy được", "success", "total_segments", True, ""),
        ("Tỷ lệ thành công", "success_rate_pct", None, True, "%"),
        ("Mismatch rate", None, "mismatch_rate_pct", False, "%"),
        ("Avg tốc độ (km/h)", "avg_speed_kmh", "avg_speed_kmh", None, "km/h"),
    ]

    for label, tt_key, here_key, hib, unit in metrics:
        tt_val   = tt_data.get(tt_key) if (tt_data and tt_key) else None
        here_val = here_data.get(here_key) if (here_data and here_key) else None

        tt_str   = fmt(tt_val, unit)
        here_str = fmt(here_val, unit)

        if hib is not None and tt_val is not None and here_val is not None:
            w, l = winner(tt_val, here_val, hib)
            if w == "tt":
                tt_str   = f"✅ {tt_str}"
                here_str = f"❌ {here_str}"
            else:
                here_str = f"✅ {here_str}"
                tt_str   = f"❌ {tt_str}"

        rows.append({"Chỉ số": label,
                     "🔵 TomTom Centroid": tt_str,
                     "🟣 HERE Bbox": here_str})

    # Thêm congestion breakdown
    if tt_data:
        cd = tt_data.get("congestion_dist", {})
        rows.append({"Chỉ số": "Phân bố tắc nghẽn (TomTom)",
                     "🔵 TomTom Centroid": f"🟢{cd.get('smooth (🟢)',0)} 🟡{cd.get('slow (🟡)',0)} 🔴{cd.get('congested (🔴)',0)}",
                     "🟣 HERE Bbox": ""})
    if here_data:
        cd = here_data.get("congestion_dist", {})
        rows.append({"Chỉ số": "Phân bố tắc nghẽn (HERE)",
                     "🔵 TomTom Centroid": "",
                     "🟣 HERE Bbox": f"🟢{cd.get('smooth (🟢)',0)} 🟡{cd.get('slow (🟡)',0)} 🔴{cd.get('congested (🔴)',0)}"})

    import pandas as pd
    df_compare = pd.DataFrame(rows)
    st.dataframe(df_compare, use_container_width=True, hide_index=True)

    # Summary verdict
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🔵 TomTom Point (OSM Centroid)")
        st.markdown("""
        **Ưu điểm:**
        - ✅ Không bị mismatch — tọa độ chính xác tuyệt đối
        - ✅ Speed thực tế (km/h) từ probe data
        - ✅ Dữ liệu có thể map 1-1 với street_id

        **Nhược điểm:**
        - ❌ Nhiều API calls (1 call/đường)
        - ❌ Chậm (~phút với nhiều đường)
        - ❌ Tốn quota (cần nhiều key)
        """)

    with col2:
        st.markdown("### 🟣 HERE Bbox Flow")
        st.markdown("""
        **Ưu điểm:**
        - ✅ Rất ít calls (7 calls/toàn TP)
        - ✅ Cực nhanh (~30 giây)
        - ✅ Phủ coverage rộng, kể cả đường không tên
        - ✅ Có thêm jamFactor, confidence

        **Nhược điểm:**
        - ⚠️ Spatial join phức tạp
        - ⚠️ ~20-40% mismatch tại VN
        - ❌ Cần HERE API key riêng
        """)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2: TOMTOM CHI TIẾT
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    if not tt_data:
        st.info("Chưa có kết quả TomTom. Chạy crawl ở sidebar.")
    else:
        st.markdown(f'<span class="method-badge-tomtom">🔵 TomTom Point — OSM Centroid</span>', unsafe_allow_html=True)
        st.caption(f"Cào lúc: {tt_data.get('crawl_time', 'N/A')}")

        # Metric cards
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("✅ Thành công", f"{tt_data.get('success', 0)}/{tt_data.get('total_streets', 0)}")
        with c2:
            st.metric("⏱ Thời gian", f"{tt_data.get('total_time_s', 0):.1f}s")
        with c3:
            st.metric("📡 API Calls", tt_data.get('api_calls_made', 0))
        with c4:
            st.metric("🚗 Avg Speed", f"{tt_data.get('avg_speed_kmh', 0)} km/h")
        with c5:
            st.metric("⏳ Avg/call", f"{tt_data.get('avg_time_per_call_ms', 0):.0f}ms")

        st.divider()

        # Bảng kết quả
        results = tt_data.get("results", [])
        if results:
            df = pd.DataFrame(results)
            show_cols = ["street_name", "district", "speed_kmh", "freeflow_kmh",
                         "congestion_label", "lat", "lon", "api_elapsed_ms"]
            show_cols = [c for c in show_cols if c in df.columns]

            # Filters
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                level_filter = st.multiselect(
                    "Lọc mức tắc nghẽn",
                    ["🟢 Thông", "🟡 Chậm", "🔴 Tắc"],
                    default=["🟢 Thông", "🟡 Chậm", "🔴 Tắc"]
                )
            with col_f2:
                search = st.text_input("Tìm tên đường", "")

            df_show = df[show_cols].copy() if show_cols else df.copy()
            if "congestion_label" in df_show.columns and level_filter:
                df_show = df_show[df_show["congestion_label"].isin(level_filter)]
            if search and "street_name" in df_show.columns:
                df_show = df_show[df_show["street_name"].str.contains(search, case=False, na=False)]

            st.dataframe(
                df_show.rename(columns={
                    "street_name": "Tên đường",
                    "district": "Quận",
                    "speed_kmh": "Tốc độ (km/h)",
                    "freeflow_kmh": "Free Flow (km/h)",
                    "congestion_label": "Trạng thái",
                    "api_elapsed_ms": "API time (ms)",
                }),
                use_container_width=True,
                hide_index=True,
                height=400,
            )
            st.caption(f"Hiển thị {len(df_show)}/{len(results)} kết quả")

        # Lỗi
        if tt_data.get("errors_detail"):
            with st.expander(f"⚠️ Lỗi ({tt_data.get('errors', 0)} đường)"):
                st.json(tt_data["errors_detail"][:10])


# ════════════════════════════════════════════════════════════════════════════
# TAB 3: HERE CHI TIẾT
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    if not here_data:
        st.info("Chưa có kết quả HERE. Chạy crawl ở sidebar (cần HERE API key).")
    else:
        st.markdown(f'<span class="method-badge-here">🟣 HERE Bbox Flow</span>', unsafe_allow_html=True)
        st.caption(f"Cào lúc: {here_data.get('crawl_time', 'N/A')}")

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("📍 Segments", here_data.get("total_segments", 0))
        with c2:
            st.metric("⏱ API time", f"{here_data.get('api_time_s', 0):.1f}s")
        with c3:
            st.metric("📡 API Calls", here_data.get("api_calls", 0))
        with c4:
            st.metric("🚗 Avg Speed", f"{here_data.get('avg_speed_kmh', 0)} km/h")
        with c5:
            miss = here_data.get("mismatch_rate_pct", "N/A")
            st.metric("❌ Miss rate", f"{miss}%" if isinstance(miss, (int, float)) else miss)

        st.divider()

        # Per-district summary
        st.subheader("Kết quả theo quận")
        dist_results = here_data.get("district_results", [])
        if dist_results:
            df_d = pd.DataFrame([{
                "Quận"      : d["district"],
                "Segments"  : d.get("count", 0),
                "API time(s)": d.get("elapsed_s", 0),
                "Lỗi"       : d.get("error", "—") or "—",
            } for d in dist_results])
            st.dataframe(df_d, use_container_width=True, hide_index=True)

        # Bảng segments
        segments = here_data.get("segments", [])
        if segments:
            st.subheader(f"Chi tiết segments ({len(segments)})")
            df_s = pd.DataFrame(segments)

            show_cols = ["district", "speed_kmh", "freeflow_kmh", "jam_factor",
                         "confidence", "congestion_label",
                         "matched_street_name", "match_dist_m", "match_status",
                         "center_lat", "center_lon"]
            show_cols = [c for c in show_cols if c in df_s.columns]

            # Filter
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                dist_filter = st.multiselect(
                    "Lọc quận",
                    list(DISTRICT_BBOXES.keys()) if 'DISTRICT_BBOXES' in dir() else [],
                    default=[]
                )
            with col_f2:
                match_filter = st.selectbox("Lọc match status", ["Tất cả", "matched", "no_match", "skipped_no_db"])

            df_show = df_s[show_cols].copy() if show_cols else df_s.copy()
            if dist_filter and "district" in df_show.columns:
                df_show = df_show[df_show["district"].isin(dist_filter)]
            if match_filter != "Tất cả" and "match_status" in df_show.columns:
                df_show = df_show[df_show["match_status"] == match_filter]

            st.dataframe(
                df_show.rename(columns={
                    "district": "Quận",
                    "speed_kmh": "Tốc độ (km/h)",
                    "freeflow_kmh": "Free Flow",
                    "jam_factor": "JamFactor",
                    "confidence": "Confidence",
                    "congestion_label": "Trạng thái",
                    "matched_street_name": "Đường match",
                    "match_dist_m": "Khoảng cách (m)",
                    "match_status": "Match",
                }),
                use_container_width=True,
                hide_index=True,
                height=400,
            )
            st.caption(f"Hiển thị {len(df_show)}/{len(segments)} segments")


# ════════════════════════════════════════════════════════════════════════════
# TAB 4: BẢN ĐỒ
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("🗺️ Bản Đồ Dữ Liệu Traffic")

    import pandas as pd

    map_source = st.radio("Chọn nguồn dữ liệu:", ["TomTom", "HERE", "Cả hai"], horizontal=True)

    map_points = []

    if map_source in ["TomTom", "Cả hai"] and tt_data:
        for r in tt_data.get("results", []):
            if r.get("lat") and r.get("lon"):
                map_points.append({
                    "lat"      : r["lat"],
                    "lon"      : r["lon"],
                    "speed"    : r["speed_kmh"],
                    "name"     : r.get("street_name", "N/A"),
                    "source"   : "TomTom",
                    "congestion": r["congestion_level"],
                })

    if map_source in ["HERE", "Cả hai"] and here_data:
        for s in here_data.get("segments", []):
            if s.get("center_lat") and s.get("center_lon"):
                map_points.append({
                    "lat"      : s["center_lat"],
                    "lon"      : s["center_lon"],
                    "speed"    : s["speed_kmh"],
                    "name"     : s.get("matched_street_name") or s.get("district", "N/A"),
                    "source"   : "HERE",
                    "congestion": s["congestion_level"],
                })

    if not map_points:
        st.info("Không có dữ liệu để hiển thị. Hãy chạy crawl trước.")
    else:
        df_map = pd.DataFrame(map_points)

        # Color by congestion
        color_map = {0: [34, 197, 94, 180], 1: [245, 158, 11, 180], 2: [239, 68, 68, 180]}
        df_map["color"] = df_map["congestion"].map(color_map)

        st.caption(f"Hiển thị {len(df_map)} điểm")

        # Streamlit map
        try:
            import pydeck as pdk
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=df_map,
                get_position=["lon", "lat"],
                get_color="color",
                get_radius=60,
                pickable=True,
                opacity=0.8,
            )
            view = pdk.ViewState(
                latitude=16.047,
                longitude=108.206,
                zoom=11,
                pitch=0,
            )
            chart = pdk.Deck(
                layers=[layer],
                initial_view_state=view,
                tooltip={"text": "🚦 {name}\n🚗 {speed} km/h\n📡 {source}"},
                map_style="mapbox://styles/mapbox/dark-v10",
            )
            st.pydeck_chart(chart)
        except ImportError:
            # Fallback: streamlit map basic
            st.map(df_map[["lat", "lon"]])
            st.caption("Cài pydeck để xem màu sắc theo tắc nghẽn: pip install pydeck")

        # Legend
        col1, col2, col3 = st.columns(3)
        with col1: st.success(f"🟢 Thông thoáng: {len(df_map[df_map.congestion==0])} điểm")
        with col2: st.warning(f"🟡 Chậm: {len(df_map[df_map.congestion==1])} điểm")
        with col3: st.error(f"🔴 Tắc: {len(df_map[df_map.congestion==2])} điểm")
