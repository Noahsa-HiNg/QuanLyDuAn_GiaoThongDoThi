"""
scripts/add_manual_streets.py — Thêm thủ công các tuyến đường mới vào CSDL

HƯỚNG DẪN:
1. Thêm các tuyến đường bạn muốn vào danh sách `NEW_STREETS` bên dưới.
2. Chạy script bằng lệnh:
   cd backend
   python scripts/add_manual_streets.py

LƯU Ý: 
- Nếu đường đã tồn tại (trùng tên), script sẽ tự động bỏ qua để tránh lỗi.
- `geometry` có thể để None, nhưng nếu muốn vẽ trên bản đồ thì cần định dạng WKT, 
  ví dụ: "LINESTRING(108.21 16.06, 108.22 16.07)"
"""

import sys
import os

# Đảm bảo có thể import các module từ thư mục backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal
from models.street import Street

# ==============================================================================
# NHẬP DANH SÁCH CÁC ĐƯỜNG MỚI VÀO ĐÂY
# ==============================================================================
NEW_STREETS = [
    # ─── ĐƯỜNG 2 CHIỀU (Tách thành 2 đường theo yêu cầu) ───
    #"geometry": "LINESTRING(108.225725 16.061245, 108.226884 16.061036, 108.231267 16.061298)"
    # {
    #     "name": "Hùng Vương 1",
    #     "district_id": 1,         # Quận Hải Châu
    #     "length_km": 1.5,
    #     "max_speed": 40,
    #     "is_one_way": True,       # Đã tách thì mỗi đường coi như 1 chiều
    #     "geometry": None
    # },
    # {
    #     "name": "Hùng Vương 2",
    #     "district_id": 1,
    #     "length_km": 1.5,
    #     "max_speed": 40,
    #     "is_one_way": True,
    #     "geometry": None
    # },

    # ─── ĐƯỜNG 1 CHIỀU (Các đường dọc) ───
    {
        "name": "Bạch Đằng",
        "district_id": 1,
        "length_km": 2.0,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },
    {
        "name": "Trần Phú",
        "district_id": 1,
        "length_km": 2.0,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },
    {
        "name": "Yên Bái",
        "district_id": 1,
        "length_km": 1.5,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },
    {
        "name": "Nguyễn Chí Thanh",
        "district_id": 1,
        "length_km": 1.5,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },
    {
        "name": "Phan Châu Trinh",
        "district_id": 1,
        "length_km": 1.8,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },
    {
        "name": "Hoàng Diệu",
        "district_id": 1,
        "length_km": 1.8,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },

    # ─── ĐƯỜNG 1 CHIỀU (Các đường ngang) ───
    {
        "name": "Nguyễn Thái Học",
        "district_id": 1,
        "length_km": 0.8,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },
    {
        "name": "Trần Quốc Toản",
        "district_id": 1,
        "length_km": 0.8,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },
    {
        "name": "Thái Phiên",
        "district_id": 1,
        "length_km": 0.8,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },
    {
        "name": "Lê Hồng Phong",
        "district_id": 1,
        "length_km": 0.8,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    },
    {
        "name": "Phạm Phú Thứ",
        "district_id": 1,
        "length_km": 0.4,
        "max_speed": 40,
        "is_one_way": True,
        "geometry": None
    }
]
# ==============================================================================

def add_streets():
    db = SessionLocal()
    added_count = 0
    skipped_count = 0

    try:
        print("🚀 Bắt đầu thêm đường mới vào Database...\n")
        
        for data in NEW_STREETS:
            name = data.get("name")
            
            # Kiểm tra xem đường này đã có trong DB chưa (tránh thêm trùng lặp)
            existing = db.query(Street).filter(Street.name == name).first()
            if existing:
                print(f"⏩ Đã bỏ qua: '{name}' (Đường này đã tồn tại trong hệ thống)")
                skipped_count += 1
                continue

            # Tạo đối tượng Street mới
            new_street = Street(
                name=name,
                district_id=data.get("district_id"),
                length_km=data.get("length_km"),
                max_speed=data.get("max_speed"),
                is_one_way=data.get("is_one_way", False),
                # geometry yêu cầu cú pháp đặc biệt của PostGIS (WKT element)
                geometry=f"SRID=4326;{data['geometry']}" if data.get("geometry") else None
            )
            
            db.add(new_street)
            added_count += 1
            print(f"✅ Đã thêm: '{name}'")
        
        # Lưu toàn bộ thay đổi vào CSDL
        db.commit()
        
        print(f"\n🎉 Hoàn tất! Đã thêm thành công {added_count} đường mới. (Bỏ qua {skipped_count} đường trùng).")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Có lỗi xảy ra trong quá trình thêm vào DB: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    add_streets()
