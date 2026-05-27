import json
import time
from pathlib import Path
try:
    from scipy.spatial import cKDTree
    import numpy as np
except ImportError:
    print("Cần cài đặt scipy: pip install scipy")
    import sys
    sys.exit(1)

def main():
    print("=" * 60)
    print("  GẮN DỮ LIỆU HERE LÊN 72,742 OSM SEGMENTS")
    print("=" * 60)
    
    # 1. Load HERE data
    here_file = Path('tests/test_here_bbox/results/here_results.json')
    if not here_file.exists():
        print("Không tìm thấy here_results.json. Chạy crawl.py trước.")
        return
    
    here_data = json.loads(here_file.read_text(encoding='utf-8'))
    here_segs = here_data['segments']
    
    # Extract points for KDTree
    here_pts = []
    valid_here_segs = []
    for s in here_segs:
        lat = s.get('center_lat')
        lon = s.get('center_lon')
        if lat and lon:
            here_pts.append([lat, lon])
            valid_here_segs.append(s)
            
    print(f"📍 Đã nạp {len(valid_here_segs)} segments từ HERE.")
    
    t0 = time.time()
    tree = cKDTree(here_pts)
    print(f"🌳 Đã xây dựng KDTree trong {time.time()-t0:.3f}s")
    
    # 2. Load OSM data
    osm_file = Path('tests/test_tomtom_centroid/results/display_data.json')
    osm_data = json.loads(osm_file.read_text(encoding='utf-8'))
    osm_segs = osm_data['segments']
    print(f"🗺️ Đã nạp {len(osm_segs)} segments từ OSM (SQL dump).")
    
    # 3. MAPPING
    t1 = time.time()
    mapped_count = 0
    
    # Convert all OSM points to array for fast query
    osm_pts = []
    for s in osm_segs:
        osm_pts.append([s['lat'], s['lon']])
        
    distances, indices = tree.query(osm_pts, k=1)
    
    for i, s in enumerate(osm_segs):
        dist = distances[i]
        # dist là khoảng cách Euclidean trên độ.
        # 1 độ ~ 111km. Khoảng 0.005 độ ~ 500m. Khoảng 0.002 ~ 200m.
        # Nâng lên 0.005 để phủ hết các đường gần đó
        if dist < 0.005:
            hs = valid_here_segs[indices[i]]
            s['speed_kmh'] = hs['speed_kmh']
            s['freeflow_kmh'] = hs.get('freeflow_kmh', 60)
            s['congestion_level'] = hs['congestion_level']
            s['congestion_label'] = hs.get('congestion_label', '')
            s['jam_factor'] = hs.get('jam_factor', 0)
            mapped_count += 1
        else:
            s['speed_kmh'] = None
            s['freeflow_kmh'] = None
            s['congestion_level'] = None
            s['congestion_label'] = 'Không có dữ liệu'
            s['jam_factor'] = None
            
    print(f"🔗 Đã map xong: {mapped_count}/{len(osm_segs)} segments có dữ liệu HERE.")
    print(f"⏱️ Thời gian mapping: {time.time()-t1:.3f}s")
    
    # Thống kê
    c0 = sum(1 for s in osm_segs if s.get('congestion_level') == 0)
    c1 = sum(1 for s in osm_segs if s.get('congestion_level') == 1)
    c2 = sum(1 for s in osm_segs if s.get('congestion_level') == 2)
    print(f"📊 Phân bố 72k OSM: 🟢 {c0} | 🟡 {c1} | 🔴 {c2}")
    
    # 4. Save result
    out_file = Path('tests/test_here_bbox/results/display_here_72k.json')
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({
            "source": "here_mapped_to_osm",
            "mapped_count": mapped_count,
            "total_segments": len(osm_segs),
            "segments": osm_segs
        }, f, ensure_ascii=False)
    
    print(f"✅ Đã lưu kết quả vào: {out_file}")

if __name__ == "__main__":
    main()
