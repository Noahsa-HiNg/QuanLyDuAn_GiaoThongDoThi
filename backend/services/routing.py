"""
services/routing.py
Tìm đường ngắn nhất / nhanh nhất bằng thuật toán A*.
"""
import time as _time
import logging
import networkx as nx
from scipy.spatial import KDTree
from data.manual_coords import MANUAL_COORDS
from utils.geometry import haversine_m   # Hàm có sẵn, trả về MÉT
log = logging.getLogger("routing")
# Cache Graph trong memory (tránh dựng lại mỗi request)
_cache: dict = {"graph": None, "tree": None, "nodes": None, "built_at": 0.0}
CACHE_TTL = 300  # Làm mới mỗi 5 phút

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Khoảng cách đường chim bay giữa 2 điểm GPS, đơn vị KM.
    Dùng làm: (1) trọng số cạnh, (2) heuristic h(n) cho A*.
    Gọi hàm haversine_m có sẵn (trả về mét) → chia 1000 → km.
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
    # --- Đọc thông tin đường từ DB -----------------------------------
    street_meta = {}   # {"Tên đường": {"max_speed": 50, "is_one_way": True}}
    if db_session:
        try:
            from models.street import Street
            for s in db_session.query(Street).all():
                street_meta[s.name] = {
                    "max_speed" : s.max_speed  or 40,
                    "is_one_way": s.is_one_way or False,
                }
        except Exception as e:
            log.warning(f"Không đọc được bảng streets: {e}")
    # --- Đọc tốc độ thực tế mới nhất từ traffic_data ----------------
    live_speeds = {}   # {"Tên đường": avg_speed (km/h)}
    if db_session:
        try:
            from sqlalchemy import text
            rows = db_session.execute(text("""
                SELECT DISTINCT ON (s.name)
                       s.name, td.avg_speed
                FROM   traffic_data td
                JOIN   streets s ON td.street_id = s.id
                WHERE  td.avg_speed IS NOT NULL
                ORDER  BY s.name, td.timestamp DESC
            """)).fetchall()
            live_speeds = {r[0]: r[1] for r in rows}
        except Exception as e:
            log.warning(f"Không đọc được traffic_data: {e}")
    # --- Dựng Node + Edge từ MANUAL_COORDS --------------------------
    for name, coords in MANUAL_COORDS.items():
        if len(coords) < 2:
            continue   # Bỏ đường chưa có tọa độ
        meta       = street_meta.get(name, {})
        max_spd    = meta.get("max_speed",  40)
        one_way    = meta.get("is_one_way", False)
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
            # Cạnh A → B (luôn có)
            G.add_edge(A, B, weight_km=d_km, weight_time=t_hrs, street=name)
            # Cạnh B → A (chỉ có nếu 2 chiều)
            if not one_way:
                G.add_edge(B, A, weight_km=d_km, weight_time=t_hrs, street=name)
    log.info(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    _connect_nearby_nodes(G)
    comps = nx.number_weakly_connected_components(G)
    log.info(f"After merging: {G.number_of_edges()} edges, {comps} components")
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
    """
    nodes = list(G.nodes())
    if not nodes:
        return

    tree = KDTree([[lng, lat] for lng, lat in nodes])

    added = 0
    for i, node in enumerate(nodes):
        lng, lat = node
        # Tìm tất cả Node trong vòng threshold_km
        idxs = tree.query_ball_point([lng, lat], r=threshold_km / 111.0)
        # 111 km ≈ 1 độ lat/lng (xấp xỉ nhanh, đủ dùng)

        for j in idxs:
            if j == i:
                continue
            neighbor = nodes[j]
            if G.has_edge(node, neighbor):
                continue  # Đã có cạnh thực → bỏ qua
            d_km  = _haversine_km(lat, lng, neighbor[1], neighbor[0])
            if d_km > threshold_km:
                continue  # Lọc lại bằng Haversine chính xác
            t_hrs = d_km / 10.0  # Giả định đi bộ 10 km/h qua ngã tư
            G.add_edge(node, neighbor, weight_km=d_km, weight_time=t_hrs, street="[intersection]")
            G.add_edge(neighbor, node, weight_km=d_km, weight_time=t_hrs, street="[intersection]")
            added += 1

    log.info(f"Intersection bridges added: {added} pairs")


def _build_kdtree(G: nx.DiGraph):
    """
    Tạo KD-Tree từ tất cả Node trong Graph.
    KD-Tree giúp tìm điểm gần nhất O(log N) thay vì O(N).
    Trả về (tree, nodes):
        tree  : KDTree object
        nodes : list[(lng, lat)] — thứ tự phải khớp với tree
    """
    nodes = list(G.nodes())
    tree  = KDTree([[lng, lat] for lng, lat in nodes])
    return tree, nodes
def find_nearest_node(tree: KDTree, nodes: list, lat: float, lng: float) -> tuple:
    """
    Tìm Node trong Graph gần với điểm (lat, lng) nhất.
    Tại sao cần?
        User click bất kỳ điểm nào trên bản đồ.
        Điểm đó hầu như không bao giờ khớp đúng tọa độ Node trong Graph.
        → Phải snap về Node gần nhất để A* có thể chạy.
    Returns: (lng, lat) của Node gần nhất.
    """
    _, idx = tree.query([lng, lat])
    return nodes[idx]

def find_route(
    G         : nx.DiGraph,
    start     : tuple,
    end       : tuple,
    mode      : str = "shortest",
) -> dict:
    """
    Chạy A* từ Node start đến Node end.
    mode="shortest" → dùng weight_km   (tìm đường ngắn nhất km)
    mode="fastest"  → dùng weight_time (tìm đường nhanh nhất theo tốc độ thực)
    A* cần hàm heuristic h(n) = ước tính chi phí từ n đến đích.
    Dùng Haversine (đường chim bay) vì:
      - Luôn <= đường thực → heuristic admissible → A* đảm bảo tối ưu
      - Tính O(1), rất nhanh
    """
    wkey = "weight_km" if mode == "shortest" else "weight_time"
    def heuristic(n1, n2):
        # n1, n2 là tuple (lng, lat)
        return _haversine_km(n1[1], n1[0], n2[1], n2[0])
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
    """
    now = _time.time()
    if _cache["graph"] is None or (now - _cache["built_at"]) > CACHE_TTL:
        log.info("Rebuilding traffic graph...")
        G = build_traffic_graph(db_session)
        tree, nodes = _build_kdtree(G)
        _cache.update(graph=G, tree=tree, nodes=nodes, built_at=now)
    return _cache["graph"], _cache["tree"], _cache["nodes"]
def get_route(
    from_lat   : float,
    from_lng   : float,
    to_lat     : float,
    to_lng     : float,
    mode       : str  = "shortest",
    db_session        = None,
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