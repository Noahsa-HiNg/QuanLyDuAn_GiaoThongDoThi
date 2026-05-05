import sys
sys.path.insert(0, '.')
from data.manual_coords import MANUAL_COORDS

# Đọc thủ công seed_danang (không import model để tránh lỗi geoalchemy2)
import ast, re

with open('data/seed_danang.py', encoding='utf-8') as f:
    content = f.read()

# Lấy tất cả "name" trong STREETS_DATA
in_seed = set(re.findall(r'"name":\s*"([^"]+)"', content))
in_coords = {k for k, v in MANUAL_COORDS.items() if len(v) >= 2}

print("=== DUONG MOI (co trong manual_coords nhung CHUA co trong seed_danang) ===")
new_streets = sorted(in_coords - in_seed)
for n in new_streets:
    pts = MANUAL_COORDS[n]
    avg_lng = round(sum(p[0] for p in pts) / len(pts), 4)
    avg_lat = round(sum(p[1] for p in pts) / len(pts), 4)
    import math
    def hav(lat1,lng1,lat2,lng2):
        R=6371; dl=math.radians(lat2-lat1); dg=math.radians(lng2-lng1)
        a=math.sin(dl/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dg/2)**2
        return R*2*math.asin(math.sqrt(a))
    km = round(sum(hav(pts[i][1],pts[i][0],pts[i+1][1],pts[i+1][0]) for i in range(len(pts)-1)), 2)
    print(f'  "{n}" | lat={avg_lat} | lng={avg_lng} | km={km} | diem={len(pts)}')

print()
print("=== DUONG DA CO TRONG seed_danang ===")
for n in sorted(in_coords & in_seed):
    print(f"  OK: {n}")
