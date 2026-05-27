import os
import sys
import time
from sqlalchemy import text
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
from database import SessionLocal, engine

def migrate():
    print("=" * 60)
    print("  MIGRATION: XÓA DATA CŨ VÀ NẠP 72,000 SEGMENTS MỚI")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        # 1. Truncate bảng streets (CASCADE sẽ xóa luôn traffic_data, predictions...)
        print("🗑️ Đang xóa toàn bộ dữ liệu streets và các bảng liên quan (CASCADE)...")
        db.execute(text("TRUNCATE TABLE streets CASCADE;"))
        db.commit()
        print("✅ Xóa thành công.")
        
        # 2. Execute SQL file
        sql_file = Path(__file__).parent.parent / "street_district_dump.sql"
        print(f"📥 Đang nạp dữ liệu từ: {sql_file.name} (sẽ mất khoảng 10-30 giây)...")
        
        t0 = time.time()
        # Since the file contains COPY commands and binary/hex data, it's better to run via psql or execute in a specific way.
        # SQLAlchemy connection might not handle the raw COPY ... FROM stdin \. syntax well.
        # Let's run it via command line tool `psql` using os.system.
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()
