"""
pages/3_route_finder.py — Tìm đường thông minh
Sprint 4 | SCRUM-44/45/46
Layout: 2-row search bar (tên đường + tọa độ) → map full width → kết quả
"""
import sys, os, unicodedata
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import folium
import streamlit as st
from streamlit_folium import st_folium

from shared.utils.css_loader import setup_ui
from shared.components.sidebar import render_sidebar
from shared.api.client import get_route_api, get_traffic_current, get_street_midpoints

setup_ui()
render_sidebar(show_map_controls=False, brand_icon="🗺️",
               brand_title="Tìm đường thông minh",
               brand_subtitle="Thuật toán A* — Đà Nẵng")

MAP_CENTER = [16.0544, 108.2022]
MAP_ZOOM   = 13
_CLR = {0: "#22c55e", 1: "#eab308", 2: "#ef4444"}
_LBL = {0: "Thông thoáng", 1: "Chậm", 2: "Kẹt xe"}

# ── Load tên đường + midpoint từ backend API (cache) ─────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def _load_street_lookup() -> dict:
    """Gọi API 1 lần, cache 5 phút. Trả về {norm_name: (original, (lat, lng))}."""
    def _norm(text: str) -> str:
        text = text.lower().strip().replace("đ", "d")
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))
    rows = get_street_midpoints()   # [{name, lat, lng}, ...]
    return {_norm(r["name"]): (r["name"], (r["lat"], r["lng"]))
            for r in rows if r.get("name") and r.get("lat") and r.get("lng")}

STREET_LOOKUP = _load_street_lookup()

def _norm(text: str) -> str:
    """Chuẩn hóa: viết thường + bỏ dấu + đ→d."""
    text = text.lower().strip().replace("đ", "d")
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def find_streets(query: str) -> list[tuple]:
    """Trả về [(tên, (lat,lng))] khớp với query."""
    q = _norm(query)
    if not q:
        return []
    return [(name, pos) for key, (name, pos) in STREET_LOOKUP.items() if q in key]

# ── Session state ─────────────────────────────────────────────────────────────
for _k, _v in {
    "rf_from_pos":  None,
    "rf_to_pos":    None,
    "rf_last_click": None,
    "rf_res_short": None,
    "rf_res_fast":  None,
    "rf_selected":  "shortest",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.rf-fade{animation:fadeUp .3s ease-out}
.search-panel{
  background:rgba(255,255,255,0.03);
  border:1px solid rgba(255,255,255,0.08);
  border-radius:16px;padding:16px 20px;margin-bottom:14px;
}
.coord-badge{
  font-size:0.74rem;font-family:monospace;
  padding:4px 10px;border-radius:20px;
  display:inline-block;margin-top:4px;
}
.route-card{
  background:rgba(255,255,255,0.03);
  border:1px solid rgba(255,255,255,0.08);
  border-radius:14px;padding:16px 18px;transition:all .2s;
}
.route-card.best{border-color:rgba(99,102,241,0.45);background:rgba(99,102,241,0.07)}
/* Căn chỉnh column gap đều nhau */
[data-testid="column"]{padding-left:6px!important;padding-right:6px!important}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rf-fade" style="padding:12px 0 6px">
  <h1 style="margin:0;font-size:1.85rem;font-weight:800;letter-spacing:-0.03em">
    🗺️ <span style="background:linear-gradient(135deg,#f1f5f9 30%,#818cf8);
    -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text">
    Tìm đường thông minh</span>
  </h1>
  <p style="color:#64748b;font-size:0.83rem;margin:4px 0 0">
    Thuật toán A* · Gõ tên đường hoặc click bản đồ · So sánh 2 tuyến
  </p>
</div>
""", unsafe_allow_html=True)

st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  SEARCH PANEL — 2 hàng, 3 cột thẳng hàng                              ║
# ╚══════════════════════════════════════════════════════════════════════════╝
from_pos = st.session_state.rf_from_pos
to_pos   = st.session_state.rf_to_pos



# ── Hàng 1: Text input ──────────────────────────────────────────────────────
c_from, c_to, c_btn = st.columns([5, 5, 2])

with c_from:
    st.markdown('<p style="font-size:0.74rem;color:#4ade80;font-weight:700;'
                'margin:0 0 4px;letter-spacing:0.04em">📍 ĐIỂM XUẤT PHÁT</p>',
                unsafe_allow_html=True)
    from_input = st.text_input(
        "from", label_visibility="collapsed",
        placeholder="Gõ tên đường... (vd: le duan)",
        key="rf_from_input",
    )

with c_to:
    st.markdown('<p style="font-size:0.74rem;color:#f87171;font-weight:700;'
                'margin:0 0 4px;letter-spacing:0.04em">🏁 ĐIỂM ĐẾN</p>',
                unsafe_allow_html=True)
    to_input = st.text_input(
        "to", label_visibility="collapsed",
        placeholder="Gõ tên đường...",
        key="rf_to_input",
    )

with c_btn:
    st.markdown('<p style="font-size:0.74rem;color:transparent;margin:0 0 4px">.</p>',
                unsafe_allow_html=True)
    find_disabled = from_pos is None or to_pos is None
    find_clicked  = st.button("🔍 Tìm đường", use_container_width=True,
                               type="primary", key="rf_find",
                               disabled=find_disabled)

# ── Hàng 2: Tọa độ + Reset ──────────────────────────────────────────────────
d_from, d_to, d_rst = st.columns([5, 5, 2])

with d_from:
    if from_pos:
        st.markdown(
            f'<span class="coord-badge" style="background:rgba(74,222,128,0.12);'
            f'color:#4ade80;border:1px solid rgba(74,222,128,0.3)">'
            f'✅ {from_pos[0]:.5f}, {from_pos[1]:.5f}</span>',
            unsafe_allow_html=True)
        if st.button("✕ Xóa điểm đi", key="rf_clear_from", use_container_width=True):
            st.session_state.rf_from_pos  = None
            st.session_state.rf_res_short = None
            st.session_state.rf_res_fast  = None
            st.rerun()
    else:
        st.markdown(
            '<span class="coord-badge" style="background:rgba(255,255,255,0.04);'
            'color:#475569;border:1px solid rgba(255,255,255,0.08)">'
            '⚪ Chưa chọn điểm xuất phát</span>',
            unsafe_allow_html=True)

with d_to:
    if to_pos:
        st.markdown(
            f'<span class="coord-badge" style="background:rgba(248,113,113,0.12);'
            f'color:#f87171;border:1px solid rgba(248,113,113,0.3)">'
            f'✅ {to_pos[0]:.5f}, {to_pos[1]:.5f}</span>',
            unsafe_allow_html=True)
        if st.button("✕ Xóa điểm đến", key="rf_clear_to", use_container_width=True):
            st.session_state.rf_to_pos    = None
            st.session_state.rf_res_short = None
            st.session_state.rf_res_fast  = None
            st.rerun()
    else:
        st.markdown(
            '<span class="coord-badge" style="background:rgba(255,255,255,0.04);'
            'color:#475569;border:1px solid rgba(255,255,255,0.08)">'
            '⚪ Chưa chọn điểm đến</span>',
            unsafe_allow_html=True)

with d_rst:
    if st.button("🔄 Reset", use_container_width=True, key="rf_reset"):
        for k in ("rf_from_pos","rf_to_pos","rf_last_click","rf_res_short","rf_res_fast"):
            st.session_state[k] = None
        st.rerun()



st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)

# ── Xử lý text input → fuzzy match → pin ────────────────────────────────────
def _apply_street(field: str, query: str):
    """Tìm đường khớp với query và set pin nếu khớp đúng 1."""
    matches = find_streets(query)
    if len(matches) == 1:
        name, pos = matches[0]
        st.session_state[field] = pos
        st.session_state.rf_res_short = None
        st.session_state.rf_res_fast  = None
        st.rerun()
    elif len(matches) > 1:
        # Hiện gợi ý nếu nhiều kết quả
        st.session_state[f"_suggestions_{field}"] = matches
    else:
        st.session_state[f"_suggestions_{field}"] = []

if from_input and from_input.strip() and from_pos is None:
    _apply_street("rf_from_pos", from_input)

if to_input and to_input.strip() and to_pos is None:
    _apply_street("rf_to_pos", to_input)

# Gợi ý khi có nhiều kết quả
for field, label, color in [
    ("rf_from_pos", "điểm xuất phát", "#4ade80"),
    ("rf_to_pos",   "điểm đến",       "#f87171"),
]:
    key = f"_suggestions_{field}"
    suggestions = st.session_state.get(key, [])
    if suggestions:
        st.markdown(f'<p style="font-size:0.78rem;color:{color};margin:0 0 4px">'
                    f'Chọn {label}:</p>', unsafe_allow_html=True)
        cols = st.columns(min(len(suggestions), 4))
        for i, (name, pos) in enumerate(suggestions[:4]):
            if cols[i].button(name, key=f"sug_{field}_{i}"):
                st.session_state[field]     = pos
                st.session_state.rf_res_short = None
                st.session_state.rf_res_fast  = None
                st.session_state[key] = []
                st.rerun()

# ── Tìm đường khi bấm nút ────────────────────────────────────────────────────
if find_clicked and from_pos and to_pos:
    with st.spinner("⏳ Thuật toán A* đang tính..."):
        st.session_state.rf_res_short = get_route_api(*from_pos, *to_pos, "shortest")
        st.session_state.rf_res_fast  = get_route_api(*from_pos, *to_pos, "fastest")
    st.rerun()

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  BẢN ĐỒ FOLIUM — full width, click-to-pin                             ║
# ╚══════════════════════════════════════════════════════════════════════════╝
from_pos = st.session_state.rf_from_pos
to_pos   = st.session_state.rf_to_pos
res_s    = st.session_state.rf_res_short
res_f    = st.session_state.rf_res_fast

# Smart center/zoom
if from_pos and to_pos:
    center = [(from_pos[0]+to_pos[0])/2, (from_pos[1]+to_pos[1])/2]
    span   = max(abs(from_pos[0]-to_pos[0]), abs(from_pos[1]-to_pos[1]))
    zoom   = 14 if span < 0.02 else 13 if span < 0.05 else 12
elif from_pos:
    center, zoom = list(from_pos), 15
else:
    center, zoom = MAP_CENTER, MAP_ZOOM

m = folium.Map(location=center, zoom_start=zoom,
               tiles="CartoDB dark_matter", prefer_canvas=True, attr="© CartoDB")

# Vẽ route
sel = st.session_state.rf_selected
rd  = res_s if sel == "shortest" else res_f
if rd and "path" in rd and not rd.get("error"):
    clr = "#818cf8" if sel == "shortest" else "#4ade80"
    folium.PolyLine([[p[1],p[0]] for p in rd["path"]],
                    color=clr, weight=5, opacity=0.92).add_to(m)

# Markers
if from_pos:
    folium.Marker(list(from_pos), tooltip="📍 Điểm xuất phát",
        icon=folium.DivIcon(
            html='<div style="background:#4ade80;width:16px;height:16px;border-radius:50%;'
                 'border:3px solid #fff;box-shadow:0 0 12px rgba(74,222,128,.7)"></div>',
            icon_size=(16,16), icon_anchor=(8,8))).add_to(m)
if to_pos:
    folium.Marker(list(to_pos), tooltip="🏁 Điểm đến",
        icon=folium.DivIcon(
            html='<div style="background:#f87171;width:16px;height:16px;border-radius:50%;'
                 'border:3px solid #fff;box-shadow:0 0 12px rgba(248,113,113,.7)"></div>',
            icon_size=(16,16), icon_anchor=(8,8))).add_to(m)

map_data = st_folium(m, height=460, use_container_width=True,
                     returned_objects=["last_clicked"], key="rf_map")

# Xử lý click map
if map_data and map_data.get("last_clicked"):
    c = map_data["last_clicked"]
    nc = (round(c["lat"],6), round(c["lng"],6))
    if nc != st.session_state.rf_last_click:
        st.session_state.rf_last_click = nc
        if st.session_state.rf_from_pos is None:
            st.session_state.rf_from_pos = nc
        elif st.session_state.rf_to_pos is None:
            st.session_state.rf_to_pos = nc
        else:
            st.session_state.rf_from_pos  = nc
            st.session_state.rf_to_pos    = None
            st.session_state.rf_res_short = None
            st.session_state.rf_res_fast  = None
        st.rerun()

# Hint text
if from_pos is None:
    hint = "☝️ Gõ tên đường hoặc click bản đồ để chọn điểm xuất phát"
elif to_pos is None:
    hint = "☝️ Chọn tiếp điểm đến rồi bấm <b>🔍 Tìm đường</b>"
elif res_s is None:
    hint = "✅ Đã chọn 2 điểm — bấm <b>🔍 Tìm đường</b>"
else:
    hint = "🗺️ Tím = Ngắn nhất · Xanh = Nhanh nhất · Click bản đồ để reset"
st.markdown(f'<p style="font-size:0.75rem;color:#475569;text-align:center;'
            f'padding:4px 0">{hint}</p>', unsafe_allow_html=True)

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  KẾT QUẢ SO SÁNH                                                       ║
# ╚══════════════════════════════════════════════════════════════════════════╝
if res_s and res_f:
    if res_s.get("error") or res_f.get("error"):
        st.error(f"❌ {res_s.get('error') or res_f.get('error')}")
    else:
        st.markdown("<hr style='border-color:rgba(255,255,255,0.06);margin:14px 0'>",
                    unsafe_allow_html=True)
        st.markdown("### 📊 So sánh 2 Tuyến đường")

        dist_s,dur_s = res_s.get("distance_km",0), res_s.get("duration_min",0)
        dist_f,dur_f = res_f.get("distance_km",0), res_f.get("duration_min",0)
        best = "fastest" if dur_f <= dur_s else "shortest"

        c1, c2 = st.columns(2)
        for col,mode,icon,title,dist,dur,ns in [
            (c1,"shortest","📏","Ngắn nhất",dist_s,dur_s,len(res_s.get("streets",[]))),
            (c2,"fastest", "⚡","Nhanh nhất",dist_f,dur_f,len(res_f.get("streets",[]))),
        ]:
            is_best = mode == best
            badge = ('<span style="background:rgba(99,102,241,.15);color:#818cf8;'
                     'border:1px solid rgba(99,102,241,.3);border-radius:20px;'
                     'padding:2px 10px;font-size:0.7rem;font-weight:700">⭐ Khuyến nghị</span>'
                     if is_best else "")
            cls = "route-card best" if is_best else "route-card"
            col.markdown(f"""
            <div class="{cls} rf-fade">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
                <span style="font-size:1.25rem">{icon}</span>
                <div>
                  <div style="font-size:0.92rem;font-weight:700;color:#e2e8f0">{title}</div>
                  {badge}
                </div>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <div style="text-align:center;background:rgba(255,255,255,.04);
                            border-radius:10px;padding:10px">
                  <div style="font-size:1.3rem;font-weight:800;color:#818cf8">{dist:.1f}</div>
                  <div style="font-size:0.7rem;color:#64748b">km</div>
                </div>
                <div style="text-align:center;background:rgba(255,255,255,.04);
                            border-radius:10px;padding:10px">
                  <div style="font-size:1.3rem;font-weight:800;color:#4ade80">{dur:.0f}</div>
                  <div style="font-size:0.7rem;color:#64748b">phút</div>
                </div>
              </div>
              <div style="text-align:center;margin-top:6px;font-size:0.71rem;color:#475569">
                {ns} đoạn đường đi qua
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        st.radio("Xem trên bản đồ:", ["shortest","fastest"],
                 format_func=lambda x:"📏 Ngắn nhất" if x=="shortest" else "⚡ Nhanh nhất",
                 horizontal=True, key="rf_selected")

        # Danh sách đường + traffic
        active = res_s if st.session_state.rf_selected == "shortest" else res_f
        streets = [s for s in active.get("streets",[]) if s and s!="[intersection]"]
        if streets:
            st.markdown('<p style="font-size:0.76rem;color:#64748b;font-weight:700;'
                        'letter-spacing:.07em;text-transform:uppercase;margin:14px 0 8px">'
                        '📍 Đường đi qua & Trạng thái giao thông</p>',
                        unsafe_allow_html=True)
            traffic = get_traffic_current()
            tmap = {s.get("street_name",""): s for s in traffic.get("streets",[])
                    if s.get("street_name")}
            n = 3
            for row in [streets[i:i+n] for i in range(0,len(streets),n)]:
                cols = st.columns(n)
                for col,s in zip(cols,row):
                    td  = tmap.get(s,{})
                    lv  = td.get("congestion_level")
                    spd = td.get("avg_speed")
                    if lv is not None and spd is not None:
                        th = (f'<span style="color:{_CLR[lv]};font-size:.69rem;font-weight:600">'
                              f'● {_LBL[lv]} · {spd} km/h</span>')
                    else:
                        th = '<span style="color:#334155;font-size:.69rem">— Không có data</span>'
                    col.markdown(
                        f'<div style="background:rgba(255,255,255,.03);border:1px solid '
                        f'rgba(255,255,255,.07);border-radius:8px;padding:6px 10px;margin:2px 0">'
                        f'<div style="font-size:.78rem;color:#cbd5e1;font-weight:500;'
                        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{s}</div>'
                        f'{th}</div>',
                        unsafe_allow_html=True)
