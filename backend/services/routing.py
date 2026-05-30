"""
services/routing.py
Tìm đường ngắn nhất / nhanh nhất bằng thuật toán A*.

v2.0 — Lấy geometry từ Database (PostGIS LINESTRING) thay vì MANUAL_COORDS.
  Ưu điểm:
    - Dùng toàn bộ đường trong DB (hàng trăm đường thay vì ~51 đường thủ công)
    - Geometry chính xác từ OSM/HERE thay vì tọa độ nhập tay
    - Tốc độ thực tế từ traffic_data mới nhất

  Luồng build graph:
    1. Query tất cả streets có geometry (LINESTRING) từ DB
    2. Dùng ST_AsGeoJSON để lấy tọa độ [[lng,lat],...]
    3. Build node + edge như cũ
    4. Fallback về MANUAL_COORDS nếu DB không có geometry nào

Fixes giữ nguyên:
  [Fix #1] A* heuristic đúng đơn vị cho cả shortest (km) và fastest (giờ)
  [Fix #4] threading.Lock + serve-stale pattern cho cache
  [Fix #5] Bỏ điểm tọa độ trùng liên tiếp trước khi build graph
  [Fix #7] KDTree scale sang km — tránh snap sai node
"""

import json
import math
import time as _time
import logging
import threading
from typing import Optional

import networkx as nx
from scipy.spatial import KDTree

from utils.geometry import haversine_m   # Trả về MÉT

log = logging.getLogger("routing")

# ── Hằng số địa lý Đà Nẵng ───────────────────────────────────────────────────
_LAT_REF          = 16.07
_KM_PER_DEG_LAT   = 111.0
_KM_PER_DEG_LNG   = 111.0 * math.cos(math.radians(_LAT_REF))   # ≈ 106.7 km/°
_MAX_CITY_SPEED   = 60.0    # km/h — dùng cho heuristic fastest

# ── Cache Graph ───────────────────────────────────────────────────────────────
_cache_lock: threading.Lock = threading.Lock()
_cache: dict = {"graph": None, "tree": None, "nodes": None, "built_at": 0.0}
CACHE_TTL = 300   # giây — làm mới mỗi 5 phút


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Khoảng cách đường chim bay (km). haversine_m nhận (lon, lat, lon, lat)."""
    return haversine_m(lng1, lat1, lng2, lat2) / 1000.0


def _dedup_coords(raw: list) -> list:
    """Loại bỏ điểm [lng, lat] trùng liên tiếp (Fix #5)."""
    if not raw:
        return []
    result = [raw[0]]
    for pt in raw[1:]:
        if pt != result[-1]:
            result.append(pt)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Load dữ liệu đường từ DB
# ─────────────────────────────────────────────────────────────────────────────

def _load_streets_from_db(db_session) -> list[dict]:
    """
    Query tất cả tuyến đường có geometry từ DB.

    Trả về list[dict]:
        name       : str
        coords     : [[lng, lat], ...]   — từ ST_AsGeoJSON
        max_speed  : int
        is_one_way : bool
        live_speed : float | None        — tốc độ mới nhất từ traffic_data
    """
    from sqlalchemy import text

    # ── 1. Load geometry + meta của tất cả đường ────────────────────────────
    rows = db_session.execute(text("""
        SELECT
            s.id,
            s.name,
            s.max_speed,
            s.is_one_way,
            (ST_AsGeoJSON(s.geometry)::json -> 'coordinates') AS coords
        FROM streets s
        WHERE s.geometry IS NOT NULL
        ORDER BY s.name
    """)).fetchall()

    if not rows:
        log.warning("DB không có đường nào có geometry — fallback sang MANUAL_COORDS")
        return []

    log.info(f"Loaded {len(rows)} streets with geometry from DB")

    # ── 2. Load tốc độ thực tế mới nhất của từng đường ──────────────────────
    speed_rows = db_session.execute(text("""
        SELECT DISTINCT ON (td.street_id)
               td.street_id,
               td.avg_speed
        FROM   traffic_data td
        WHERE  td.avg_speed IS NOT NULL
        ORDER  BY td.street_id, td.timestamp DESC
    """)).fetchall()
    live_speed_map = {r[0]: r[1] for r in speed_rows}
    log.info(f"Live speeds loaded for {len(live_speed_map)} streets")

    # ── 3. Ghép thành list[dict] ─────────────────────────────────────────────
    result = []
    for row in rows:
        raw_coords = row.coords
        if raw_coords is None:
            continue
        if isinstance(raw_coords, str):
            raw_coords = json.loads(raw_coords)
        if not raw_coords or len(raw_coords) < 2:
            continue

        # Đảm bảo mỗi điểm chỉ có 2 phần tử [lng, lat] (bỏ elevation nếu có)
        coords_2d = [[float(pt[0]), float(pt[1])] for pt in raw_coords]
        coords_2d = _dedup_coords(coords_2d)
        if len(coords_2d) < 2:
            continue

        result.append({
            "id"        : row.id,
            "name"      : row.name,
            "coords"    : coords_2d,
            "max_speed" : row.max_speed or 40,
            "is_one_way": row.is_one_way or False,
            "live_speed": live_speed_map.get(row.id),
        })

    return result


def _load_streets_from_manual() -> list[dict]:
    """Fallback: đọc từ MANUAL_COORDS khi DB không có geometry."""
    from data.manual_coords import MANUAL_COORDS
    result = []
    for name, raw_coords in MANUAL_COORDS.items():
        coords = _dedup_coords(raw_coords)
        if len(coords) < 2:
            continue
        result.append({
            "id"        : None,
            "name"      : name,
            "coords"    : coords,
            "max_speed" : 40,
            "is_one_way": False,
            "live_speed": None,
        })
    log.info(f"Fallback MANUAL_COORDS: {len(result)} streets")
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Build Graph
# ─────────────────────────────────────────────────────────────────────────────

def build_traffic_graph(db_session=None) -> nx.DiGraph:
    """
    Dựng đồ thị có hướng từ geometry tuyến đường.

    Nguồn dữ liệu (ưu tiên):
      1. PostGIS geometry trong bảng `streets` (tất cả đường có LINESTRING)
      2. Fallback: MANUAL_COORDS nếu DB không trả về geometry nào

    Node : tuple (lng, lat)
    Edge : weight_km (km) và weight_time (giờ)
    """
    G = nx.DiGraph()

    # Chọn nguồn dữ liệu
    streets = []
    if db_session:
        try:
            streets = _load_streets_from_db(db_session)
        except Exception as e:
            log.error(f"Lỗi khi load streets từ DB: {e}")

    if not streets:
        streets = _load_streets_from_manual()

    if not streets:
        log.error("Không có dữ liệu đường nào để build graph!")
        return G

    # Dựng Node + Edge
    for s in streets:
        coords    = s["coords"]
        max_spd   = s["max_speed"]
        one_way   = s["is_one_way"]
        name      = s["name"]
        # Tốc độ thực tế; tối thiểu 5 km/h để tránh chia cho 0
        live_spd  = s["live_speed"]
        act_spd   = max(live_spd if live_spd else max_spd, 5.0)

        for i in range(len(coords) - 1):
            lng_a, lat_a = coords[i]
            lng_b, lat_b = coords[i + 1]
            A = (lng_a, lat_a)
            B = (lng_b, lat_b)
            d_km  = _haversine_km(lat_a, lng_a, lat_b, lng_b)
            if d_km <= 0:
                continue
            t_hrs = d_km / act_spd
            G.add_node(A, lat=lat_a, lng=lng_a)
            G.add_node(B, lat=lat_b, lng=lng_b)
            G.add_edge(A, B, weight_km=d_km, weight_time=t_hrs, street=name)
            if not one_way:
                G.add_edge(B, A, weight_km=d_km, weight_time=t_hrs, street=name)

    log.info(f"Graph raw: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    # Với graph từ DB (OSM geometry), các đường đã chia sẻ điểm tại ngã tư chính xác
    # → chỉ chạy _connect_nearby_nodes khi graph nhỏ (MANUAL_COORDS fallback)
    n_nodes = G.number_of_nodes()
    if n_nodes < 5000:
        # MANUAL_COORDS: cần nối ngã tư thủ công
        _connect_nearby_nodes(G, threshold_km=0.05)
    else:
        log.info(f"Graph lớn ({n_nodes} nodes từ DB) — bỏ qua _connect_nearby_nodes (OSM đã có intersection)")

    _bridge_isolated_components(G, max_gap_km=0.3)  # Nối component cô lập ≤ 300m

    comps = nx.number_weakly_connected_components(G)
    log.info(f"Graph final: {G.number_of_nodes()} nodes, "
             f"{G.number_of_edges()} edges, {comps} components")
    return G


# ─────────────────────────────────────────────────────────────────────────────
# Nối ngã tư & component cô lập
# ─────────────────────────────────────────────────────────────────────────────

def _connect_nearby_nodes(G: nx.DiGraph, threshold_km: float = 0.05):
    """
    Nối các Node gần nhau (≤ threshold_km) bằng cạnh ảo để nối ngã tư.
    KDTree dùng tọa độ đã scale sang km (Fix #7).
    """
    nodes = list(G.nodes())
    if not nodes:
        return

    scaled = [[lng * _KM_PER_DEG_LNG, lat * _KM_PER_DEG_LAT] for lng, lat in nodes]
    tree   = KDTree(scaled)

    added = 0
    for i, node in enumerate(nodes):
        lng, lat = node
        idxs = tree.query_ball_point(
            [lng * _KM_PER_DEG_LNG, lat * _KM_PER_DEG_LAT],
            r=threshold_km
        )
        for j in idxs:
            if j <= i:          # tránh xét lại cặp đã xét
                continue
            neighbor = nodes[j]
            d_km = _haversine_km(lat, lng, neighbor[1], neighbor[0])
            if d_km > threshold_km:
                continue
            if G.has_edge(node, neighbor):
                continue
            t_hrs = d_km / 10.0   # 10 km/h qua ngã tư
            G.add_edge(node, neighbor, weight_km=d_km, weight_time=t_hrs, street="[intersection]")
            G.add_edge(neighbor, node, weight_km=d_km, weight_time=t_hrs, street="[intersection]")
            added += 1

    log.info(f"Intersection bridges added: {added} pairs")


def _bridge_isolated_components(G: nx.DiGraph, max_gap_km: float = 0.3):
    """
    Nối các component cô lập vào component lớn nhất bằng 1 cạnh bridge.
    Chỉ bridge nếu khoảng cách ≤ max_gap_km (mặc định 300m).
    KDTree dùng tọa độ đã scale sang km (Fix #7).
    """
    comps = list(nx.weakly_connected_components(G))
    if len(comps) <= 1:
        log.info("Graph already connected — no bridging needed")
        return

    main_idx  = max(range(len(comps)), key=lambda i: len(comps[i]))
    main_list = list(comps[main_idx])
    main_tree = KDTree([
        [n[0] * _KM_PER_DEG_LNG, n[1] * _KM_PER_DEG_LAT] for n in main_list
    ])

    bridged = 0
    for ci, comp in enumerate(comps):
        if ci == main_idx:
            continue

        min_d = float('inf')
        best_a = best_b = None
        for node in comp:
            _, idx = main_tree.query([node[0] * _KM_PER_DEG_LNG, node[1] * _KM_PER_DEG_LAT])
            nb  = main_list[idx]
            d   = _haversine_km(node[1], node[0], nb[1], nb[0])
            if d < min_d:
                min_d, best_a, best_b = d, node, nb

        if best_a and min_d <= max_gap_km:
            t_hrs = min_d / 15.0
            G.add_edge(best_a, best_b, weight_km=min_d, weight_time=t_hrs, street="[bridge]")
            G.add_edge(best_b, best_a, weight_km=min_d, weight_time=t_hrs, street="[bridge]")
            bridged += 1
            log.info(f"Bridge comp {ci}({len(comp)}) → {min_d*1000:.0f}m → main({len(main_list)})")
        else:
            log.warning(
                f"Comp {ci}({len(comp)} nodes) quá xa "
                f"({min_d*1000:.0f}m > {max_gap_km*1000:.0f}m) — bỏ qua"
            )

    final = nx.number_weakly_connected_components(G)
    log.info(f"Bridged {bridged} components → {final} components remain")


# ─────────────────────────────────────────────────────────────────────────────
# KDTree helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_kdtree(G: nx.DiGraph):
    """
    Tạo KDTree từ tất cả node trong Graph.
    Tọa độ được scale sang km (Fix #7) để đo khoảng cách đúng.
    Trả về (tree, nodes) — nodes giữ thứ tự khớp với tree.
    """
    nodes  = list(G.nodes())
    scaled = [[lng * _KM_PER_DEG_LNG, lat * _KM_PER_DEG_LAT] for lng, lat in nodes]
    tree   = KDTree(scaled)
    return tree, nodes


def find_nearest_node(tree: KDTree, nodes: list, lat: float, lng: float) -> tuple:
    """
    Snap điểm (lat, lng) bất kỳ về node gần nhất trong Graph.
    Query KDTree với tọa độ đã scale sang km (Fix #7).
    Returns: (lng, lat) của node gần nhất.
    """
    _, idx = tree.query([lng * _KM_PER_DEG_LNG, lat * _KM_PER_DEG_LAT])
    return nodes[idx]


# ─────────────────────────────────────────────────────────────────────────────
# A* routing
# ─────────────────────────────────────────────────────────────────────────────

def find_route(
    G    : nx.DiGraph,
    start: tuple,
    end  : tuple,
    mode : str = "shortest",
) -> dict:
    """
    Chạy A* từ node start → end.
    mode="shortest" → tối thiểu weight_km   (ngắn nhất km)
    mode="fastest"  → tối thiểu weight_time (nhanh nhất giờ)

    Heuristic admissible: haversine ≤ đường thực → A* đảm bảo tối ưu (Fix #1).
    """
    wkey = "weight_km" if mode == "shortest" else "weight_time"

    if mode == "shortest":
        def heuristic(n1, n2):
            return _haversine_km(n1[1], n1[0], n2[1], n2[0])
    else:
        def heuristic(n1, n2):
            return _haversine_km(n1[1], n1[0], n2[1], n2[0]) / _MAX_CITY_SPEED

    try:
        path = nx.astar_path(G, source=start, target=end,
                             heuristic=heuristic, weight=wkey)
    except nx.NetworkXNoPath:
        return {"error": "Không tìm được đường — hai điểm không kết nối."}
    except nx.NodeNotFound as e:
        return {"error": f"Node không tồn tại: {e}"}

    total_km = total_hrs = 0.0
    streets: list[str] = []
    for i in range(len(path) - 1):
        ed = G[path[i]][path[i + 1]]
        total_km  += ed.get("weight_km",   0.0)
        total_hrs += ed.get("weight_time", 0.0)
        st = ed.get("street", "")
        if not streets or streets[-1] != st:
            streets.append(st)

    return {
        "path"        : [[lng, lat] for lng, lat in path],  # [[lng,lat],...]
        "distance_km" : round(total_km, 2),
        "duration_min": round(total_hrs * 60, 1),
        "streets"     : streets,
        "node_count"  : len(path),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cache — serve-stale pattern (Fix #4)
# ─────────────────────────────────────────────────────────────────────────────

def _get_cached(db_session=None):
    """
    Trả về (Graph, KDTree, nodes) từ cache.

    Serve-stale pattern:
      - Cache còn mới → trả về ngay (không lock).
      - Cache hết hạn + graph đã có → serve cũ ngay, rebuild nền.
      - Cache hết hạn + graph chưa có → rebuild đồng bộ (lần đầu boot).
    """
    now = _time.time()

    # Fast path — không cần lock
    if (_cache["graph"] is not None
            and (now - _cache["built_at"]) <= CACHE_TTL):
        return _cache["graph"], _cache["tree"], _cache["nodes"]

    with _cache_lock:
        # Double-check sau khi lấy lock
        now = _time.time()
        if (_cache["graph"] is not None
                and (now - _cache["built_at"]) <= CACHE_TTL):
            return _cache["graph"], _cache["tree"], _cache["nodes"]

        if _cache["graph"] is None:
            # Lần đầu khởi động — bắt buộc build đồng bộ
            log.info("🔨 Lần đầu build traffic graph (đồng bộ)...")
            G = build_traffic_graph(db_session)
            tree, nodes = _build_kdtree(G)
            _cache.update(graph=G, tree=tree, nodes=nodes, built_at=_time.time())
        else:
            # Cache hết hạn — serve stale, rebuild trong background
            if not _cache.get("_rebuilding", False):
                _cache["_rebuilding"] = True
                log.info("⏳ Cache hết hạn — rebuild nền, serving kết quả cũ...")

                def _rebuild_bg():
                    try:
                        from database import SessionLocal
                        _db = SessionLocal()
                        try:
                            G_new = build_traffic_graph(_db)
                            t_new, n_new = _build_kdtree(G_new)
                            with _cache_lock:
                                _cache.update(graph=G_new, tree=t_new,
                                              nodes=n_new, built_at=_time.time(),
                                              _rebuilding=False)
                            log.info("✅ Background rebuild hoàn tất")
                        finally:
                            _db.close()
                    except Exception as e:
                        log.error(f"❌ Background rebuild lỗi: {e}")
                        with _cache_lock:
                            _cache["_rebuilding"] = False

                threading.Thread(target=_rebuild_bg, daemon=True).start()

    return _cache["graph"], _cache["tree"], _cache["nodes"]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_route(
    from_lat  : float,
    from_lng  : float,
    to_lat    : float,
    to_lng    : float,
    mode      : str  = "shortest",
    db_session       = None,
) -> dict:
    """
    Hàm ALL-IN-ONE — gọi từ Router FastAPI.
    1. Lấy Graph từ cache (hoặc build mới từ DB)
    2. Snap điểm user về Node gần nhất trong Graph
    3. Chạy A*
    4. Trả về kết quả
    """
    G, tree, nodes = _get_cached(db_session)
    if G.number_of_nodes() == 0:
        return {"error": "Đồ thị rỗng — DB không có dữ liệu geometry."}

    start = find_nearest_node(tree, nodes, from_lat, from_lng)
    end   = find_nearest_node(tree, nodes, to_lat,   to_lng)

    if start == end:
        return {"error": "Điểm xuất phát và đích quá gần nhau."}

    result = find_route(G, start, end, mode)
    result["from"] = {"lat": from_lat, "lng": from_lng, "snapped": start}
    result["to"]   = {"lat": to_lat,   "lng": to_lng,   "snapped": end}
    return result