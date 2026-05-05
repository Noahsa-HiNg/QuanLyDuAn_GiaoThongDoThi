"""
scripts/generate_map_preview.py — Sinh HTML xem toa do co ban do nen OSM

Chay:
    cd backend
    python scripts/generate_map_preview.py
    -> Mo file: map_preview.html bang trinh duyet (can internet de tai ban do nen)
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.manual_coords import MANUAL_COORDS

streets = {k: v for k, v in MANUAL_COORDS.items() if len(v) >= 2}
streets_json = json.dumps(streets, ensure_ascii=False)

COLORS = [
    "#e74c3c","#3498db","#2ecc71","#f39c12","#9b59b6",
    "#1abc9c","#e67e22","#e91e63","#00bcd4","#ff5722",
    "#607d8b","#8bc34a","#ff9800","#673ab7","#03a9f4",
    "#4caf50","#f44336","#9c27b0","#795548","#009688",
]
colors_json = json.dumps(COLORS)
n = len(streets)

html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<title>Ban do toa do - Da Nang</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:Arial,sans-serif;display:flex;height:100vh;overflow:hidden;background:#1e1e2e;color:#cdd6f4;}}

#sidebar{{width:210px;overflow-y:auto;background:#181825;padding:8px;
  flex-shrink:0;border-right:2px solid #313244;}}
#sidebar h2{{color:#89b4fa;font-size:12px;margin-bottom:8px;padding-bottom:5px;
  border-bottom:1px solid #313244;}}
.road-item{{display:flex;align-items:center;gap:6px;padding:4px 5px;
  border-radius:4px;cursor:pointer;margin-bottom:2px;font-size:11px;}}
.road-item:hover{{background:#313244;}}
.road-item.active{{background:#45475a;font-weight:bold;}}
.dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0;}}

#map{{flex:1;}}

#detail{{width:300px;display:flex;flex-direction:column;overflow:hidden;
  background:#181825;border-left:2px solid #313244;}}
#d-header{{padding:8px 10px;background:#1e1e2e;flex-shrink:0;border-bottom:1px solid #313244;}}
#d-header h3{{color:#89b4fa;font-size:13px;margin-bottom:2px;}}
#d-header .meta{{color:#a6adc8;font-size:11px;}}
#table-scroll{{overflow-y:auto;flex:1;}}
table{{width:100%;border-collapse:collapse;font-size:11px;}}
th{{background:#313244;color:#89b4fa;padding:4px 7px;position:sticky;top:0;text-align:left;}}
td{{padding:3px 7px;border-bottom:1px solid #1e1e2e;font-family:monospace;cursor:pointer;}}
tr:hover td{{background:#313244;}}
tr.hl td{{background:#45475a!important;color:#f9e2af;}}
tr.first td{{color:#a6e3a1;}}
tr.last td{{color:#f38ba8;}}
#copy-btn{{margin:7px;padding:6px;background:#313244;color:#cdd6f4;
  border:1px solid #45475a;border-radius:5px;cursor:pointer;font-size:11px;flex-shrink:0;}}
#copy-btn:hover{{background:#45475a;}}
#placeholder{{color:#6c7086;text-align:center;padding:50px 12px;font-size:12px;line-height:1.8;}}
</style>
</head>
<body>

<div id="sidebar">
  <h2>Danh sach ({n} duong)</h2>
  <div id="road-list"></div>
</div>

<div id="map"></div>

<div id="detail">
  <div id="placeholder">&#8592; Chon duong de<br>xem chi tiet toa do</div>
  <div id="detail-body" style="display:none;">
    <div id="d-header">
      <h3 id="d-name"></h3>
      <div class="meta" id="d-meta"></div>
    </div>
    <div id="table-scroll">
      <table>
        <thead><tr><th>#</th><th>Lng (Kinh do)</th><th>Lat (Vi do)</th></tr></thead>
        <tbody id="d-tbody"></tbody>
      </table>
    </div>
    <button id="copy-btn" onclick="copyCoords()">Copy Python format</button>
  </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
window.addEventListener('load', function() {{

const STREETS = {streets_json};
const COLORS  = {colors_json};
const names   = Object.keys(STREETS);

// ── Leaflet map ──────────────────────────────────────────────────────────────
const map = L.map('map', {{zoomControl:true}}).setView([16.068, 108.212], 13);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap contributors',
  maxZoom: 19
}}).addTo(map);

// ── State ────────────────────────────────────────────────────────────────────
let currentName   = null;
let currentCoords = [];
let activeRow     = null;
let highlightPin  = null;
const polylines   = {{}};

// ── Vẽ tất cả đường ──────────────────────────────────────────────────────────
names.forEach((name, i) => {{
  const coords  = STREETS[name];
  const color   = COLORS[i % COLORS.length];
  const latlngs = coords.map(c => [c[1], c[0]]);

  const poly = L.polyline(latlngs, {{color, weight:3, opacity:0.7}}).addTo(map);

  // Marker điểm đầu
  L.circleMarker(latlngs[0], {{
    radius:4, color:'#fff', fillColor:color, fillOpacity:1, weight:1.5
  }}).addTo(map);

  // Marker điểm cuối
  L.circleMarker(latlngs[latlngs.length-1], {{
    radius:4, color:'#fff', fillColor:'#f38ba8', fillOpacity:1, weight:1.5
  }}).addTo(map);

  poly.on('click', () => selectRoad(name));
  polylines[name] = {{poly, color}};
}});

// ── Sidebar ───────────────────────────────────────────────────────────────────
const listEl = document.getElementById('road-list');
names.forEach((name, i) => {{
  const color = COLORS[i % COLORS.length];
  const item  = document.createElement('div');
  item.className = 'road-item';
  item.id = 'ri' + i;
  item.innerHTML = '<span class="dot" style="background:' + color + '"></span>' + name;
  item.onclick = () => selectRoad(name);
  listEl.appendChild(item);
}});

// ── Select road ───────────────────────────────────────────────────────────────
function selectRoad(name) {{
  currentName   = name;
  currentCoords = STREETS[name];
  activeRow     = null;
  if (highlightPin) {{ map.removeLayer(highlightPin); highlightPin = null; }}

  // Reset style tất cả đường
  names.forEach(n => {{
    polylines[n].poly.setStyle({{weight:3, opacity:0.7}});
  }});
  // Highlight đường được chọn
  polylines[name].poly.setStyle({{weight:5, opacity:1, color:'#f9e2af'}});

  const latlngs = currentCoords.map(c => [c[1], c[0]]);
  map.fitBounds(L.latLngBounds(latlngs), {{padding:[30,30]}});

  // Sidebar
  document.querySelectorAll('.road-item').forEach(e => e.classList.remove('active'));
  const idx = names.indexOf(name);
  const item = document.getElementById('ri' + idx);
  if (item) {{ item.classList.add('active'); item.scrollIntoView({{block:'nearest'}}); }}

  // Detail panel
  document.getElementById('placeholder').style.display = 'none';
  const body = document.getElementById('detail-body');
  body.style.display = 'flex';
  body.style.flexDirection = 'column';
  body.style.flex = '1';
  body.style.overflow = 'hidden';
  document.getElementById('d-name').textContent = name;
  document.getElementById('d-meta').textContent = 'So diem: ' + currentCoords.length;

  const tbody = document.getElementById('d-tbody');
  tbody.innerHTML = '';
  currentCoords.forEach((c, i) => {{
    const tr = document.createElement('tr');
    if (i === 0) tr.className = 'first';
    else if (i === currentCoords.length - 1) tr.className = 'last';
    const mark = i===0 ? ' [dau]' : i===currentCoords.length-1 ? ' [cuoi]' : '';
    tr.innerHTML = '<td>' + i + mark + '</td>'
      + '<td>' + c[0].toFixed(7) + '</td>'
      + '<td>' + c[1].toFixed(7) + '</td>';
    tr.onclick = () => {{
      if (activeRow) activeRow.classList.remove('hl');
      tr.classList.add('hl');
      activeRow = tr;
      if (highlightPin) map.removeLayer(highlightPin);
      highlightPin = L.circleMarker([c[1], c[0]], {{
        radius:9, color:'#f9e2af', fillColor:'#f9e2af', fillOpacity:0.9, weight:2
      }}).addTo(map)
        .bindPopup('<b>#' + i + '</b><br>lng=' + c[0].toFixed(6) + '<br>lat=' + c[1].toFixed(6))
        .openPopup();
      map.panTo([c[1], c[0]]);
    }};
    tbody.appendChild(tr);
  }});
}}

// ── Copy ─────────────────────────────────────────────────────────────────────
window.copyCoords = function() {{
  const lines = currentCoords.map(c => '    [' + c[0] + ', ' + c[1] + '],').join('\\n');
  navigator.clipboard.writeText('"' + currentName + '": [\\n' + lines + '\\n]').then(() => {{
    document.getElementById('copy-btn').textContent = 'Da copy!';
    setTimeout(() => document.getElementById('copy-btn').textContent = 'Copy Python format', 2000);
  }});
}};

}});  // end window.onload
</script>
</body>
</html>"""

out_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "map_preview.html"
)
with open(out_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Tao: {out_path}")
print(f"Tong duong: {n}")
