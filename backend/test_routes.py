# -*- coding: utf-8 -*-
import sys; sys.path.insert(0, '/app')
from services.routing import get_route
from data.manual_coords import MANUAL_COORDS

def mid(name):
    coords = MANUAL_COORDS.get(name, [])
    if not coords: return None
    c = coords[len(coords)//2]
    return c[1], c[0]   # (lat, lng)

pairs = [
    ("HC: Bach Dang -> Hung Vuong",        u"Bạch Đằng",         u"Hùng Vương"),
    ("HC: Le Duan -> Phan Chau Trinh",     u"Lê Duẩn",           u"Phan Châu Trinh"),
    ("HC->TK: DBP -> Ton Duc Thang",       u"Điện Biên Phủ",     u"Tôn Đức Thắng"),
    ("TK: NLB -> Hoang Van Thai",          u"Nguyễn Lương Bằng", u"Hoàng Văn Thái"),
    ("TK: Truong Chinh -> Le Trong Tan",   u"Trường Chinh",      u"Lê Trọng Tấn"),
    ("HC->SonTra: Le Duan -> Ngo Quyen",   u"Lê Duẩn",           u"Ngô Quyền"),
    ("HC->SonTra: BachDang -> HoangSa",    u"Bạch Đằng",         u"Hoàng Sa"),
    ("TK: NTT -> Truong Chinh",            u"Nguyễn Tất Thành",  u"Trường Chinh"),
    ("HC->TK: DBP -> Truong Chinh",        u"Điện Biên Phủ",     u"Trường Chinh"),
    ("Same: Nguyen Tat Thanh (2 points)",  u"Nguyễn Tất Thành",  u"Nguyễn Tất Thành"),
]

print("=== ROUTE TEST VUNG HAI CHAU & THANH KHE ===")
ok = err_count = 0
for desc, from_s, to_s in pairs:
    f = mid(from_s)
    t = mid(to_s)
    if not f or not t:
        print("SKIP", desc, from_s, to_s)
        continue
    # For same street: use start and end points
    if from_s == to_s:
        coords = MANUAL_COORDS[from_s]
        f = (coords[0][1], coords[0][0])
        t = (coords[-1][1], coords[-1][0])
    
    r = get_route(f[0], f[1], t[0], t[1], mode='shortest')
    e = r.get("error")
    if e:
        print("ERR ", desc)
        print("    ", e)
        err_count += 1
    else:
        print("OK  ", desc)
        print("    ", r['distance_km'], "km |", r['duration_min'], "min |", r['node_count'], "nodes")
        streets = [s["name"] for s in r.get("streets", []) if s["name"] not in ("[intersection]", "[bridge]")]
        print("     Via:", " -> ".join(streets[:4]))
        ok += 1

print()
print(f"=== KET QUA: {ok} thanh cong, {err_count} that bai ===")
