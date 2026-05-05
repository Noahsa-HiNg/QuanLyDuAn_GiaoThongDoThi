"""
pages/3_route_finder.py — Tìm đường thông minh (Sprint 5)

A* Routing — Ngắn nhất / Nhanh nhất
Bản đồ Leaflet.js nhúng qua st.components.v1.html
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import streamlit as st
import streamlit.components.v1 as components

from shared.utils.css_loader import setup_ui
from shared.components.sidebar import render_sidebar
from shared.api.client import get_route_api

setup_ui()
render_sidebar(
    show_map_controls=False,
    brand_icon="🗺️",
    brand_title="Tìm đường thông minh",
    brand_subtitle="Thuật toán A* — Đà Nẵng",
)

# ── Sidebar decor riêng cho Route Finder ─────────────────────────────────────
with st.sidebar:
    st.divider()
    st.markdown("""
    <div style="background:rgba(129,140,248,0.08);border:1px solid rgba(129,140,248,0.18);
                border-radius:14px;padding:14px 16px;margin-bottom:4px">
        <div style="font-size:0.82rem;font-weight:700;color:#818cf8;margin-bottom:8px">
            🧭 Thuật toán A*
        </div>
        <div style="font-size:0.77rem;color:#94a3b8;line-height:1.7">
            📏 <b style="color:#e2e8f0">Ngắn nhất</b> — tổng km ít nhất<br>
            ⚡ <b style="color:#e2e8f0">Nhanh nhất</b> — thời gian ít nhất<br>
            &nbsp;&nbsp;&nbsp;&nbsp;dựa trên tốc độ thực tế
        </div>
    </div>
    <div style="font-size:0.73rem;color:#475569;padding:6px 2px;line-height:1.7">
        💡 Chọn điểm và bấm <b style="color:#818cf8">🔍 Tìm</b><br>
        Bản đồ sẽ hiển thị tuyến đường tối ưu
    </div>
    """, unsafe_allow_html=True)

# ── Hằng số ───────────────────────────────────────────────────────────────────
MAP_CENTER = (16.0544, 108.2022)   # Đà Nẵng

# Danh sách địa điểm tiêu biểu — (lat, lng)
LOCATIONS: dict[str, tuple[float, float]] = {
    "🌉 Cầu Rồng":               (16.0608, 108.2272),
    "🏪 Chợ Hàn":                (16.0713, 108.2239),
    "🏖️ Biển Mỹ Khê":            (16.0470, 108.2460),
    "✈️ Sân bay Đà Nẵng":        (16.0443, 108.1997),
    "🚌 Bến xe Trung tâm":        (16.0483, 108.2124),
    "🏛️ UBND TP Đà Nẵng":        (16.0678, 108.2208),
    "🏥 Bệnh viện C Đà Nẵng":    (16.0612, 108.2151),
    "🎓 ĐH Bách khoa Đà Nẵng":   (16.0540, 108.2022),
    "🎓 ĐH Đà Nẵng":             (16.0721, 108.2104),
    "⛪ Nhà thờ Con Gà":          (16.0711, 108.2248),
    "🌊 Cầu Thuận Phước":         (16.0850, 108.1980),
    "🛍️ Vincom Đà Nẵng":         (16.0651, 108.2192),
    "🏟️ SVĐ Hoà Xuân":           (16.0288, 108.2168),
    "🌿 Bán đảo Sơn Trà":        (16.1012, 108.2794),
}

LOC_NAMES = list(LOCATIONS.keys())

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:20px 0 4px">
  <h1 style="margin:0;font-size:1.9rem;font-weight:800;letter-spacing:-0.03em;color:#f1f5f9">
    <span>🗺️</span>
    <span style="background:linear-gradient(135deg,#f1f5f9 30%,#818cf8 100%);
                 -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                 background-clip:text">
      Tìm đường thông minh
    </span>
  </h1>
  <p style="color:#64748b;font-size:0.87rem;margin:6px 0 0">
    Thuật toán A* — Ngắn nhất hoặc Nhanh nhất dựa trên tốc độ giao thông thực tế
  </p>
</div>
<hr style="border-color:rgba(255,255,255,0.07);margin:10px 0 18px">
""", unsafe_allow_html=True)

# ── Controls ──────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns([3, 3, 2, 1])

with c1:
    st.markdown('<p style="font-size:0.78rem;color:#94a3b8;margin-bottom:4px">📍 Điểm xuất phát</p>',
                unsafe_allow_html=True)
    from_name = st.selectbox("Xuất phát", LOC_NAMES, index=5,
                             label_visibility="collapsed", key="rf_from")

with c2:
    st.markdown('<p style="font-size:0.78rem;color:#94a3b8;margin-bottom:4px">🏁 Điểm đến</p>',
                unsafe_allow_html=True)
    to_name = st.selectbox("Đến", LOC_NAMES, index=7,
                           label_visibility="collapsed", key="rf_to")

with c3:
    st.markdown('<p style="font-size:0.78rem;color:#94a3b8;margin-bottom:4px">⚙️ Chế độ tìm</p>',
                unsafe_allow_html=True)
    mode = st.selectbox(
        "Chế độ", ["shortest", "fastest"],
        format_func=lambda x: "📏 Ngắn nhất" if x == "shortest" else "⚡ Nhanh nhất",
        label_visibility="collapsed", key="rf_mode",
    )

with c4:
    st.markdown('<p style="font-size:0.78rem;color:#94a3b8;margin-bottom:4px">&nbsp;</p>',
                unsafe_allow_html=True)
    search = st.button("🔍 Tìm", use_container_width=True, type="primary", key="rf_search")

# ── Tìm đường khi bấm ────────────────────────────────────────────────────────
if search:
    if from_name == to_name:
        st.warning("⚠️ Điểm xuất phát và điểm đến phải khác nhau.")
    else:
        from_lat, from_lng = LOCATIONS[from_name]
        to_lat, to_lng     = LOCATIONS[to_name]
        with st.spinner("⏳ Đang tính toán tuyến đường..."):
            result = get_route_api(from_lat, from_lng, to_lat, to_lng, mode)
        st.session_state["route_result"]   = result
        st.session_state["route_from"]     = from_name
        st.session_state["route_to"]       = to_name
        st.session_state["route_from_pos"] = LOCATIONS[from_name]
        st.session_state["route_to_pos"]   = LOCATIONS[to_name]

# ── Hiển thị kết quả ─────────────────────────────────────────────────────────
result   = st.session_state.get("route_result")
from_pos = st.session_state.get("route_from_pos")
to_pos   = st.session_state.get("route_to_pos")
r_from   = st.session_state.get("route_from", "")
r_to     = st.session_state.get("route_to",   "")

if result and "error" not in result:
    dist   = result.get("distance_km", 0)
    dur    = result.get("duration_min", 0)
    streets = result.get("streets", [])
    path   = result.get("path", [])          # [[lng, lat], ...]
    snapped_from = result.get("from", {}).get("snapped", [])
    snapped_to   = result.get("to",   {}).get("snapped", [])

    # ── Thẻ tóm tắt ──────────────────────────────────────────────────────
    km_col, min_col, street_col = st.columns(3)
    with km_col:
        st.markdown(f"""
        <div style="background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.2);
                    border-radius:14px;padding:14px 18px;text-align:center">
            <div style="font-size:1.6rem;font-weight:800;color:#818cf8">{dist:.1f}</div>
            <div style="font-size:0.78rem;color:#64748b;margin-top:2px">km quãng đường</div>
        </div>""", unsafe_allow_html=True)
    with min_col:
        st.markdown(f"""
        <div style="background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.2);
                    border-radius:14px;padding:14px 18px;text-align:center">
            <div style="font-size:1.6rem;font-weight:800;color:#4ade80">{dur:.0f}</div>
            <div style="font-size:0.78rem;color:#64748b;margin-top:2px">phút ước tính</div>
        </div>""", unsafe_allow_html=True)
    with street_col:
        st.markdown(f"""
        <div style="background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.2);
                    border-radius:14px;padding:14px 18px;text-align:center">
            <div style="font-size:1.6rem;font-weight:800;color:#fbbf24">{len(streets)}</div>
            <div style="font-size:0.78rem;color:#64748b;margin-top:2px">đoạn đường đi qua</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

    # ── Bản đồ Leaflet ────────────────────────────────────────────────────
    # Đảo path [lng, lat] → [lat, lng] cho Leaflet
    latlng_path = [[pt[1], pt[0]] for pt in path]
    path_js = json.dumps(latlng_path)

    from_lat_snap = snapped_from[1] if len(snapped_from) == 2 else from_pos[0]
    from_lng_snap = snapped_from[0] if len(snapped_from) == 2 else from_pos[1]
    to_lat_snap   = snapped_to[1]   if len(snapped_to)   == 2 else to_pos[0]
    to_lng_snap   = snapped_to[0]   if len(snapped_to)   == 2 else to_pos[1]

    center_lat = (from_lat_snap + to_lat_snap) / 2
    center_lng = (from_lng_snap + to_lng_snap) / 2

    map_html = f"""
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body{{margin:0;padding:0;background:#0f172a}}
  #map{{width:100%;height:480px;border-radius:16px;overflow:hidden}}
</style>
</head>
<body>
<div id="map"></div>
<script>
  var map = L.map('map', {{zoomControl:true}}).setView([{center_lat},{center_lng}], 14);

  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{
    attribution:'&copy; OpenStreetMap | CartoDB',
    subdomains:'abcd', maxZoom:19
  }}).addTo(map);

  // Vẽ route polyline
  var path = {path_js};
  var poly = L.polyline(path, {{
    color: '#818cf8',
    weight: 5,
    opacity: 0.9,
    lineJoin: 'round',
    lineCap: 'round',
  }}).addTo(map);

  // Fit bounds
  map.fitBounds(poly.getBounds(), {{padding:[32,32]}});

  // Marker xuất phát (xanh)
  var startIcon = L.divIcon({{
    html: '<div style="background:#4ade80;width:16px;height:16px;border-radius:50%;border:3px solid #fff;box-shadow:0 0 10px #4ade8080"></div>',
    iconSize:[16,16], iconAnchor:[8,8], className:''
  }});
  L.marker([{from_lat_snap},{from_lng_snap}], {{icon:startIcon}})
    .addTo(map)
    .bindPopup('<b style="color:#111">🟢 Xuất phát</b><br>{r_from}');

  // Marker đích (đỏ)
  var endIcon = L.divIcon({{
    html: '<div style="background:#f87171;width:16px;height:16px;border-radius:50%;border:3px solid #fff;box-shadow:0 0 10px #f8717180"></div>',
    iconSize:[16,16], iconAnchor:[8,8], className:''
  }});
  L.marker([{to_lat_snap},{to_lng_snap}], {{icon:endIcon}})
    .addTo(map)
    .bindPopup('<b style="color:#111">🔴 Điểm đến</b><br>{r_to}');

</script>
</body></html>
"""
    components.html(map_html, height=496)

    # ── Danh sách đường đi qua ────────────────────────────────────────────
    if streets:
        clean_streets = [s for s in streets if s and s != "[intersection]"]
        if clean_streets:
            st.markdown("""
            <div style="margin-top:12px">
              <p style="font-size:0.78rem;color:#64748b;font-weight:700;
                        letter-spacing:0.07em;text-transform:uppercase;margin-bottom:8px">
                📍 Tuyến đường đi qua
              </p>
            </div>""", unsafe_allow_html=True)
            cols = st.columns(min(len(clean_streets), 4))
            for i, s in enumerate(clean_streets):
                with cols[i % len(cols)]:
                    st.markdown(
                        f'<span style="background:rgba(255,255,255,0.05);'
                        f'border:1px solid rgba(255,255,255,0.08);border-radius:8px;'
                        f'padding:4px 10px;font-size:0.8rem;color:#cbd5e1;'
                        f'display:inline-block;margin:2px 0">{s}</span>',
                        unsafe_allow_html=True,
                    )

elif result and "error" in result:
    st.error(f"❌ {result['error']}")

else:
    # Trạng thái chờ — bản đồ mặc định Đà Nẵng
    default_map = f"""
<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body{{margin:0;background:#0f172a}}
  #map{{width:100%;height:420px;border-radius:16px;overflow:hidden}}
</style>
</head>
<body>
<div id="map"></div>
<script>
  var map = L.map('map').setView([{MAP_CENTER[0]},{MAP_CENTER[1]}], 13);
  L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{
    attribution:'&copy; OpenStreetMap | CartoDB',
    subdomains:'abcd', maxZoom:19
  }}).addTo(map);

  // Hiện markers tất cả địa điểm
  var locs = {json.dumps({k: list(v) for k, v in LOCATIONS.items()}, ensure_ascii=False)};
  for(var name in locs) {{
    var pos = locs[name];
    var icon = L.divIcon({{
      html: '<div style="background:#818cf8;width:10px;height:10px;border-radius:50%;border:2px solid #fff;opacity:0.8"></div>',
      iconSize:[10,10], iconAnchor:[5,5], className:''
    }});
    L.marker(pos, {{icon:icon}}).addTo(map).bindPopup(name);
  }}
</script>
</body></html>
"""
    components.html(default_map, height=436)
    st.markdown("""
    <div style="text-align:center;color:#475569;font-size:0.84rem;padding:8px 0">
        ☝️ Chọn điểm xuất phát, điểm đến và bấm <b style="color:#818cf8">🔍 Tìm</b> để hiện tuyến đường
    </div>
    """, unsafe_allow_html=True)
