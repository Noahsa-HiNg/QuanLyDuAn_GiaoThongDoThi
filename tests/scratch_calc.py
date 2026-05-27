"""
Phân tích độ chính xác dữ liệu tốc độ HERE Traffic Flow
"""
import json
from pathlib import Path

data = json.loads(Path('tests/test_here_bbox/results/here_results.json').read_text(encoding='utf-8'))
segs = data['segments']

print('=' * 65)
print('  PHAN TICH DO CHINH XAC — HERE TRAFFIC FLOW')
print('=' * 65)

# 1. Kiem tra don vi speed
speeds   = [s['speed_kmh']  for s in segs if s.get('speed_kmh')]
freeflow = [s['freeflow_kmh'] for s in segs if s.get('freeflow_kmh')]
confs    = [s['confidence']   for s in segs if s.get('confidence') is not None]
jams     = [s['jam_factor']   for s in segs if s.get('jam_factor')  is not None]

print(f'\n1. PHAN BO TOC DO:')
print(f'   Min speed   : {min(speeds):.1f}')
print(f'   Max speed   : {max(speeds):.1f}')
print(f'   Avg speed   : {sum(speeds)/len(speeds):.1f}')
print(f'   Median speed: {sorted(speeds)[len(speeds)//2]:.1f}')

# Phan bo theo khoang
ranges = [(0,5),(5,10),(10,20),(20,40),(40,60),(60,100),(100,200)]
print(f'\n   Phan bo (co the la m/s hay km/h?):')
for lo, hi in ranges:
    cnt = sum(1 for s in speeds if lo <= s < hi)
    bar = '#' * (cnt // 20)
    print(f'   {lo:>3}-{hi:<3}: {cnt:>5} segs  {bar}')

print(f'\n   Neu la km/h: avg {sum(speeds)/len(speeds):.1f} km/h (giao thong Da Nang)')
print(f'   Neu la m/s : avg {sum(speeds)/len(speeds)*3.6:.1f} km/h (quy doi: nhieu kha nang hon)')

print(f'\n2. CONFIDENCE (do tin cay):')
print(f'   Thang do 0.0 - 1.0')
print(f'   1.0 = du lieu GPS thuc te (probe data)')
print(f'   0.5 = uoc tinh tu lich su')
print(f'   Avg confidence: {sum(confs)/len(confs):.3f}')
c_ranges = [(0.0,0.3,'Rat thap - historical'), (0.3,0.6,'Thap - uoc tinh'),
            (0.6,0.8,'Trung binh'), (0.8,1.01,'Cao - real-time probe')]
for lo, hi, label in c_ranges:
    cnt = sum(1 for c in confs if lo <= c < hi)
    pct = cnt/len(confs)*100
    print(f'   [{lo:.1f}-{hi:.1f}] {label:<28}: {cnt:>5} ({pct:.1f}%)')

print(f'\n3. JAM FACTOR (0=thong, 10=tac):')
print(f'   Avg jam factor: {sum(jams)/len(jams):.2f} / 10')
j_ranges = [(0,0.01,'0 - Khong tac'), (0.01,3,'0-3 - Thong'),
            (3,7,'3-7 - Cham'), (7,10.1,'7-10 - Tac nang')]
for lo, hi, label in j_ranges:
    cnt = sum(1 for j in jams if lo <= j < hi)
    pct = cnt/len(jams)*100
    print(f'   {label:<25}: {cnt:>5} ({pct:.1f}%)')

print(f'\n4. MUC DO PHAN DOAN (granularity):')
paths = [s['path'] for s in segs if s.get('path')]
path_lens = [len(p) for p in paths]
print(f'   Segments co geometry : {len(paths)}/{len(segs)} ({len(paths)/len(segs)*100:.1f}%)')
if path_lens:
    print(f'   Points/segment (min) : {min(path_lens)}')
    print(f'   Points/segment (max) : {max(path_lens)}')
    print(f'   Points/segment (avg) : {sum(path_lens)/len(path_lens):.1f}')
    short = sum(1 for l in path_lens if l <= 2)
    medium = sum(1 for l in path_lens if 3 <= l <= 10)
    long_ = sum(1 for l in path_lens if l > 10)
    print(f'   Segment ngan (2 pts) : {short:>5} - chi co diem dau cuoi')
    print(f'   Segment vua (3-10)   : {medium:>5} - chi tiet trung binh')
    print(f'   Segment dai (>10)    : {long_:>5} - geometry day du')

print(f'\n5. SO SANH HERE vs TOMTOM:')
print(f'   {"Tieu chi":<30} {"HERE Bbox":>15} {"TomTom Point":>15}')
print(f'   {"-"*60}')
rows = [
    ("Calls/toan TP/lan",      "7",               "~3,500 (zoom 18)"),
    ("Speed per segment",       "Co (per link)",    "Co (per point)"),
    ("Geometry tra ve",         "Co (shape links)", "Co (coordinates)"),
    ("Confidence score",        "Co (0-1)",         "Khong"),
    ("JamFactor (0-10)",        "Co",               "Khong"),
    ("Probe data VN (uoc tinh)","Trung binh",       "Tot hon"),
    ("Coverage viet nam",       "~80% duong chinh", "~95% co ten"),
    ("Real-time vs Historical", "74% confidence",   "Thuong real-time"),
]
for row in rows:
    print(f'   {row[0]:<30} {row[1]:>15} {row[2]:>15}')

print(f'\n6. KET LUAN DO CHINH XAC:')
print(f"""
   HERE Traffic Flow API:
   - CAN xac dinh toc do per-segment: YES
   - Do chinh xac phu thuoc confidence score:
     * Confidence >= 0.8 (19.1%): real-time GPS probe -> chinh xac
     * Confidence 0.5-0.8 (dao): ket hop probe + historical -> kha chinh xac
     * Confidence < 0.5: du lieu lich su -> uoc tinh, kem chinh xac hon

   Voi Da Nang cu the:
   - Avg confidence = 0.74 → du lieu chat luong TRUNG BINH
   - Duong chinh (Hai Chau, Son Tra): chinh xac tot hon
   - Duong nho, nong thon (Hoa Vang): confidence thap, it probe data
   - KHONG phai walking-speed (7.3 km/h) - day co the la m/s (= 26 km/h)
""")
print('=' * 65)
