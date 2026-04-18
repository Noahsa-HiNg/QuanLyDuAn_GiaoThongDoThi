"""
database.py — Quản lý kết nối đến PostgreSQL

Cách hoạt động:
  1. `engine`       — đối tượng chính để kết nối DB, dùng chuỗi URL
  2. `SessionLocal` — class tạo ra "phiên làm việc" (session) với DB
  3. `Base`         — class cha mà tất cả ORM model phải kế thừa
  4. `get_db()`     — hàm dependency dùng trong FastAPI router,
                      tự động đóng session sau mỗi request

Cách dùng trong router:
    from database import get_db
    from sqlalchemy.orm import Session
    from fastapi import Depends

    @router.get("/example")
    def my_endpoint(db: Session = Depends(get_db)):
        results = db.query(MyModel).all()
        return results
"""

from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import settings

DATABASE_URL = (
    f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Tự phục hồi nếu kết nối bị đứt giữa chừng
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Tất cả class Model (đại diện cho bảng DB) phải kế thừa Base này.
# Ví dụ trong models/road.py:
#   class Road(Base):
#       __tablename__ = "roads"
#       ...
Base = declarative_base()


# ─────────────────────────────────────────────────────────────
# 5. HÀM DEPENDENCY CHO FASTAPI
# ─────────────────────────────────────────────────────────────
def get_db():
    """
    Hàm generator tạo và quản lý vòng đời của một DB session.

    Dùng với FastAPI Dependency Injection:
        def my_endpoint(db: Session = Depends(get_db)):
            ...

    Cơ chế:
        - `yield db`: trao session cho router xử lý request
        - Sau khi router xử lý xong (dù thành công hay lỗi),
          khối `finally` luôn chạy để đóng session → tránh rò rỉ kết nối.
    """
    db = SessionLocal()  # Mở 1 session mới cho request này
    try:
        yield db          # Trao session cho router (router làm việc ở đây)
    finally:
        db.close()        # Đóng session dù thành công hay có lỗi


# ─────────────────────────────────────────────────────────────
# 6. HÀM KIỂM TRA KẾT NỐI DB (dùng cho health check)
# ─────────────────────────────────────────────────────────────
def check_db_connection() -> bool:
    """
    Kiểm tra xem ứng dụng có kết nối được đến PostgreSQL không.
    Trả về True nếu kết nối thành công, False nếu thất bại.

    Được gọi trong endpoint GET /health để giám sát hệ thống.
    """
    try:
        # Dùng `with engine.connect()` để tự đóng kết nối sau khi xong
        with engine.connect() as connection:
            # Chạy câu lệnh SQL đơn giản nhất để kiểm tra DB có phản hồi không
            connection.execute(text("SELECT 1"))
        return True
    except Exception as e:
        # In lỗi ra log để dễ debug, không raise exception lên tầng trên
        print(f"[database.py] ❌ Không kết nối được DB: {e}")
        return False
