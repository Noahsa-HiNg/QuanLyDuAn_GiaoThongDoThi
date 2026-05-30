"""
services/routing.py
Tìm đường ngắn nhất / nhanh nhất bằng thuật toán A*.

Optimizations (v1.1):
  [Fix #1] A* heuristic đúng đơn vị cho cả shortest (km) và fastest (giờ)
  [Fix #2] DB query chỉ load các đường có trong MANUAL_COORDS (~51 thay vì 49K)
  [Fix #3] SQL tối ưu: join bằng street_id, gợi ý index (street_id, timestamp DESC)
  [Fix #4] threading.Lock ngăn race condition khi nhiều request song song rebuild cache
  [Fix #5] Bỏ điểm tọa độ trùng liên tiếp trong MANUAL_COORDS trước khi build graph
  [Fix #6] KDTree dùng đúng hệ số km/degree cho cả lat lẫn lng tại vĩ độ Đà Nẵng
"""

import math
import time as _time
import logging
import threading

import networkx as nx
from scipy.spatial import KDTree

from data.manual_coords import MANUAL_COORDS
from utils.geometry import haversine_m   # Hàm có sẵn, trả về MÉT

log = logging.getLogger("routing")

# ── Hằng số địa lý Đà Nẵng ───────────────────────────────────────────────────
_LAT_REF          = 16.07          # Vĩ độ trung tâm Đà Nẵng (độ)
_KM_PER_DEG_LAT   = 111.0          # km / 1° vĩ độ (gần như hằng số)
_KM_PER_DEG_LNG   = 111.0 * math.cos(math.radians(_LAT_REF))  # ≈ 106.7 km / 1° kinh độ
_MAX_CITY_SPEED   = 60.0           # km/h — tốc độ tối đa thành phố, dùng cho heuristic fastest

# ── Cache Graph trong memory ──────────────────────────────────────────────────
# [Fix #4] Thêm Lock để tránh race condition khi nhiều request song song
_cache_lock: threading.Lock = threading.Lock()
_cache: dict = {"graph": None, "tree": None, "nodes": None, "built_at": 0.0}
CACHE_TTL = 300   # Làm mới mỗi 5 phút


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Khoảng cách đường chim bay giữa 2 điểm GPS, đơn vị KM.
    Gọi haversine_m có sẵn (mét) → chia 1000 → km.
    Chú ý thứ tự tham số: haversine_m(lng, lat, lng, lat).
    """
    return haversine_m(lng1, lat1, lng2, lat2) / 1000.0


def build_traffic_graph(db_session=None) -> nx.DiGraph:
    """
    Dựng đồ thị có hướng từ tọa độ đường phố.
    Node : tuple (lng, lat) — mỗi điểm trong MANUAL_COORDS
    Edge : nối 2 điểm liền kề, lưu 2 trọng số:
           weight_km   = khoảng cách thực (km)
           weight_time = thời gian đi (giờ) = km / tốc_độ_thực_tế
    Khi db_session=None → dùng tốc độ fallback 40 km/h.
    """
    G = nx.DiGraph()

    # --- [Fix #2] Chỉ load đúng các đường có trong MANUAL_COORDS -----------
    street_meta = {}   # {"Tên đường": {"max_speed": 50, "is_one_way": True}}
    if db_session:
        try:
            from models.street import Street
            street_names = list(MANUAL_COORDS.keys())
            rows = (
                db_session.query(Street.name, Street.max_speed, Street.is_one_way)
                .filter(Street.name.in_(street_names))
                .all()
            )
            street_meta = {
                r.name: {
                    "max_speed" : r.max_speed  or 40,
                    "is_one_way": r.is_one_way or False,
                }
                for r in rows
            }
            log.info(f"Loaded {len(street_meta)}/{len(street_names)} streets from DB")
        except Exception as e:
            log.warning(f"Không đọc được bảng streets: {e}")

    # --- [Fix #3] Query tốc độ thực tế — tối ưu dùng street_id thay name ---
    # Gợi ý: tạo index trên DB (chạy 1 lần):
    #   CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_traffic_data_street_ts
    #     ON traffic_data (street_id, timestamp DESC);
    live_speeds = {}   # {"Tên đường": avg_speed (km/h)}
    if db_session:
        try:
            from sqlalchemy import text
            # Dùng street_id (integer) thay name (string) → nhanh hơn, tránh collation issue
            rows = db_session.execute(text("""
                SELECT DISTINCT ON (td.street_id)
                       s.name, td.avg_speed
                FROM   traffic_data td
                JOIN   streets s ON td.street_id = s.id
                WHERE  td.avg_speed IS NOT NULL
                  AND  s.name = ANY(:names)
                ORDER  BY td.street_id, td.timestamp DESC
            """), {"names": list(MANUAL_COORDS.keys())}).fetchall()
            live_speeds = {r[0]: r[1] for r in rows}
            log.info(f"Live speeds loaded for {len(live_speeds)} streets")
        except Exception as e:
            log.warning(f"Không đọc được traffic_data: {e}")

    # --- [Fix #5] Bỏ điểm trùng liên tiếp + Dựng Node + Edge ---------------
    for name, raw_coords in MANUAL_COORDS.items():
        if len(raw_coords) < 2:
            continue

        # Loại bỏ điểm [lng, lat] trùng với điểm liền trước (self-loop)
        coords = [raw_coords[0]]
        for pt in raw_coords[1:]:
            if pt != coords[-1]:
                coords.append(pt)

        if len(coords) < 2:
            continue

        meta    = street_meta.get(name, {})
        max_spd = meta.get("max_speed",  40)
        one_way = meta.get("is_one_way", False)
        # Tốc độ thực tế; tối thiểu 5 km/h để tránh chia cho 0
        act_spd = max(live_speeds.get(name, max_spd), 5.0)

        for i in range(len(coords) - 1):
            lng_a, lat_a = coords[i]
            lng_b, lat_b = coords[i + 1]
            A = (lng_a, lat_a)
            B = (lng_b, lat_b)
            d_km  = _haversine_km(lat_a, lng_a, lat_b, lng_b)
            t_hrs = d_km / act_spd   # Thời gian qua đoạn này (giờ)
            G.add_node(A, lat=lat_a, lng=lng_a)
            G.add_node(B, lat=lat_b, lng=lng_b)
            G.add_edge(A, B, weight_km=d_km, weight_time=t_hrs, street=name)
            if not one_way:
                G.add_edge(B, A, weight_km=d_km, weight_time=t_hrs, street=name)

    log.info(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    _connect_nearby_nodes(G)                 # Pass 1: nối ngã tư ≤ 80m
    _bridge_isolated_components(G)           # Pass 2: nối component cô lập ≤ 1km
    comps = nx.number_weakly_connected_components(G)
    log.info(f"Final: {G.number_of_edges()} edges, {comps} components")
    return G


def _connect_nearby_nodes(G: nx.DiGraph, threshold_km: float = 0.08):
    """
    Nối các Node gần nhau (trong vòng threshold_km = 80m) bằng cạnh ảo.

    Tại sao cần?
    Trong manual_coords.py, tọa độ tại ngã tư giữa 2 đường không bao giờ
    trùng khớp hoàn toàn. Ví dụ:
      Bạch Đằng điểm cuối : (108.2210, 16.0680)
      Hùng Vương điểm đầu: (108.2212, 16.0681)  ← cách nhau ~25m
    → Đồ thị bị đứt gãy vì 2 Node khác nhau, không có cạnh nối.

    Giải pháp: Dùng KDTree dò tìm mọi cặp Node cách nhau <= 80m,
    thêm cạnh 2 chiều với trọng số = khoảng cách thực.

    [Fix #6] Dùng hệ số km/degree riêng cho lat và lng tại vĩ độ Đà Nẵng.
    """
    nodes = list(G.nodes())
    if not nodes:
        return

    # [Fix #6+#7] Scale sang km → dùng threshold_km trực tiếp, nhất quán với _build_kdtree
    scaled_nodes = [[lng * _KM_PER_DEG_LNG, lat * _KM_PER_DEG_LAT] for lng, lat in nodes]
    tree = KDTree(scaled_nodes)

    added = 0
    for i, node in enumerate(nodes):
        lng, lat = node
        # Query với threshold_km (đơn vị km, khớp với tọa độ đã scale)
        idxs = tree.query_ball_point([lng * _KM_PER_DEG_LNG, lat * _KM_PER_DEG_LAT],
                                     r=threshold_km)

        for j in idxs:
            if j == i:
                continue
            neighbor = nodes[j]
            if G.has_edge(node, neighbor):
                continue  # Đã có cạnh thực → bỏ qua
            d_km = _haversine_km(lat, lng, neighbor[1], neighbor[0])
            if d_km > threshold_km:
                continue  # Xác nhận lại bằng Haversine chính xác
            t_hrs = d_km / 10.0  # Giả định đi bộ 10 km/h qua ngã tư
            G.add_edge(node, neighbor, weight_km=d_km, weight_time=t_hrs, street="[intersection]")
            G.add_edge(neighbor, node, weight_km=d_km, weight_time=t_hrs, street="[intersection]")
            added += 1

    log.info(f"Intersection bridges added: {added} pairs")


def _bridge_isolated_components(G: nx.DiGraph, max_gap_km: float = 1.0):
    """
    Nối các component bị tách rời bằng 1 cạnh bridge ngắn nhất.

    Tại sao cần?
    Sau Pass 1 (80m), nhiều đường vẫn còn cô lập vì khoảng cách
    giữa các tuyến đường vượt ngưỡng 80m:
      - Comp Hải Châu ↔ Comp Nguyễn Lương Bằng : 239m
      - Comp Hải Châu ↔ Comp Phạm Văn Đồng      : 103m
      - Comp Hải Châu ↔ Comp Trường Chinh       : 312m

    Giải pháp: Với mỗi component nhỏ, tìm node gần nhất trong
    component LỚN NHẤT và thêm 1 cạnh bridge 2 chiều.
    Tốc độ ảo 15 km/h (tượng trưng cho đường kết nối chưa nhập data).

    max_gap_km: khoảng cách tối đa chấp nhận (mặc định 1km).
                Nếu gap > 1km → component đó thực sự xa, không bridge.
    """
    comps = list(nx.weakly_connected_components(G))
    if len(comps) <= 1:
        log.info("Graph already fully connected — no bridging needed")
        return

    # Component lớn nhất làm "neo" trung tâm
    main_idx  = max(range(len(comps)), key=lambda i: len(comps[i]))
    main_list = list(comps[main_idx])
    # [Fix #7] Scale sang km để KDTree đo khoảng cách đúng
    main_tree = KDTree([[n[0] * _KM_PER_DEG_LNG, n[1] * _KM_PER_DEG_LAT] for n in main_list])

    bridged = 0
    for ci, comp in enumerate(comps):
        if ci == main_idx:
            continue

        # Tìm cặp node (comp ↔ main) có khoảng cách ngắn nhất
        min_d    = float('inf')
        best_a, best_b = None, None
        for node in comp:
            _, idx = main_tree.query([node[0] * _KM_PER_DEG_LNG, node[1] * _KM_PER_DEG_LAT])
            nb     = main_list[idx]
            d      = _haversine_km(node[1], node[0], nb[1], nb[0])
            if d < min_d:
                min_d  = d
                best_a = node
                best_b = nb

        if best_a and min_d <= max_gap_km:
            t_hrs = min_d / 15.0   # 15 km/h ảo
            G.add_edge(best_a, best_b,
                       weight_km=min_d, weight_time=t_hrs, street="[bridge]")
            G.add_edge(best_b, best_a,
                       weight_km=min_d, weight_time=t_hrs, street="[bridge]")
            bridged += 1
            log.info(
                f"Bridge comp {ci}({len(comp)} nodes) "
                f"→ {min_d*1000:.0f}m → main({len(main_list)} nodes)"
            )
        else:
            log.warning(
                f"Comp {ci}({len(comp)} nodes) too far "
                f"({min_d*1000:.0f}m > {max_gap_km*1000:.0f}m) — left isolated"
            )

    final = nx.number_weakly_connected_components(G)
    log.info(f"Bridged {bridged} isolated components → {final} components remain")


def _build_kdtree(G: nx.DiGraph):
    """
    Tạo KD-Tree từ tất cả Node trong Graph.
    KD-Tree giúp tìm điểm gần nhất O(log N) thay vì O(N).
    Trả về (tree, nodes):
        tree  : KDTree object — dùng tọa độ đã scale sang km
        nodes : list[(lng, lat)] — thứ tự phải khớp với tree

    [Fix #7] Scale lat/lng → km trước khi build KDTree.
    Tại Đà Nẵng (vĩ độ ~16°):
      1° lat ≈ 111 km, 1° lng ≈ 106.7 km
    Không scale → KDTree tính khoảng cách sai → snap sai node.
    """
    nodes = list(G.nodes())
    # Chuyển (lng, lat) → (x_km, y_km) để KDTree đo đúng khoảng cách
    scaled = [[lng * _KM_PER_DEG_LNG, lat * _KM_PER_DEG_LAT] for lng, lat in nodes]
    tree  = KDTree(scaled)
    return tree, nodes


def find_nearest_node(tree: KDTree, nodes: list, lat: float, lng: float) -> tuple:
    """
    Tìm Node trong Graph gần với điểm (lat, lng) nhất.
    Tại sao cần?
        User click bất kỳ điểm nào trên bản đồ.
        Điểm đó hầu như không bao giờ khớp đúng tọa độ Node trong Graph.
        → Phải snap về Node gần nhất để A* có thể chạy.
    [Fix #7] Phải scale (lng, lat) → km khớp với cách build KDTree.
    Returns: (lng, lat) của Node gần nhất.
    """
    _, idx = tree.query([lng * _KM_PER_DEG_LNG, lat * _KM_PER_DEG_LAT])
    return nodes[idx]


def find_route(
    G    : nx.DiGraph,
    start: tuple,
    end  : tuple,
    mode : str = "shortest",
) -> dict:
    """
    Chạy A* từ Node start đến Node end.
    mode="shortest" → dùng weight_km   (tìm đường ngắn nhất km)
    mode="fastest"  → dùng weight_time (tìm đường nhanh nhất theo tốc độ thực)

    [Fix #1] Heuristic phải cùng đơn vị với weight:
      - shortest: heuristic = haversine_km      (đơn vị km)
      - fastest : heuristic = haversine_km / MAX_CITY_SPEED  (đơn vị giờ)
    Haversine luôn <= đường thực → admissible → A* đảm bảo tối ưu.
    """
    wkey = "weight_km" if mode == "shortest" else "weight_time"

    # [Fix #1] Heuristic đúng đơn vị cho từng mode
    if mode == "shortest":
        def heuristic(n1, n2):
            # n1, n2 là tuple (lng, lat) — đơn vị: km
            return _haversine_km(n1[1], n1[0], n2[1], n2[0])
    else:  # fastest — đơn vị: giờ
        def heuristic(n1, n2):
            dist_km = _haversine_km(n1[1], n1[0], n2[1], n2[0])
            return dist_km / _MAX_CITY_SPEED   # giờ = km / (km/h)

    try:
        path = nx.astar_path(G, source=start, target=end,
                             heuristic=heuristic, weight=wkey)
    except nx.NetworkXNoPath:
        return {"error": "Không tìm được đường — hai điểm không kết nối."}
    except nx.NodeNotFound as e:
        return {"error": f"Node không tồn tại: {e}"}

    # --- Tính tổng chiều dài & thời gian ---
    total_km = total_hrs = 0.0
    streets: list[str] = []
    for i in range(len(path) - 1):
        ed = G[path[i]][path[i + 1]]
        total_km  += ed.get("weight_km",   0.0)
        total_hrs += ed.get("weight_time", 0.0)
        st = ed.get("street", "")
        if not streets or streets[-1] != st:
            streets.append(st)   # Loại bỏ tên đường trùng liên tiếp

    return {
        "path"        : [[lng, lat] for lng, lat in path],  # [[lng,lat],...]
        "distance_km" : round(total_km, 2),
        "duration_min": round(total_hrs * 60, 1),
        "streets"     : streets,
        "node_count"  : len(path),
    }


def _get_cached(db_session=None):
    """
    Trả về (Graph, KDTree, nodes) từ cache.
    Tự động dựng lại nếu cache hết hạn (> CACHE_TTL giây).

    [Fix #4] Dùng threading.Lock để đảm bảo chỉ 1 thread rebuild graph
    khi nhiều request FastAPI đến cùng lúc.
    """
    with _cache_lock:
        now = _time.time()
        if _cache["graph"] is None or (now - _cache["built_at"]) > CACHE_TTL:
            log.info("Rebuilding traffic graph...")
            G = build_traffic_graph(db_session)
            tree, nodes = _build_kdtree(G)
            _cache.update(graph=G, tree=tree, nodes=nodes, built_at=now)
    return _cache["graph"], _cache["tree"], _cache["nodes"]


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
    Luồng:
      1. Lấy Graph từ cache (hoặc build mới nếu hết hạn)
      2. Snap điểm user về Node gần nhất trong Graph
      3. Chạy A*
      4. Trả về kết quả
    """
    G, tree, nodes = _get_cached(db_session)
    if G.number_of_nodes() == 0:
        return {"error": "Đồ thị rỗng — kiểm tra MANUAL_COORDS."}

    start = find_nearest_node(tree, nodes, from_lat, from_lng)
    end   = find_nearest_node(tree, nodes, to_lat,   to_lng)

    if start == end:
        return {"error": "Điểm xuất phát và đích quá gần nhau."}

    result = find_route(G, start, end, mode)
    result["from"] = {"lat": from_lat, "lng": from_lng, "snapped": start}
    result["to"]   = {"lat": to_lat,   "lng": to_lng,   "snapped": end}
    return result