"""
models/__init__.py — Export tất cả ORM models

File này BẮT BUỘC phải import tất cả models vì 2 lý do:

1. ALEMBIC AUTOGENERATE:
   Khi chạy `alembic revision --autogenerate`, Alembic cần
   import Base và tất cả models để phát hiện bảng nào cần tạo/sửa.
   Nếu không import ở đây → Alembic bỏ sót bảng → migration thiếu cột.

2. SQLALCHEMY RELATIONSHIP:
   Khi khai báo relationship("Street", ...) trong model khác,
   SQLAlchemy cần class Street đã được import vào memory.
   Nếu chưa import → lỗi: "NoReferencedTableError: 'streets' is not defined"

Thứ tự import QUAN TRỌNG:
   - Import bảng "cha" trước (không có FK)
   - Import bảng "con" sau (có FK trỏ về bảng cha)
"""

# ── Bảng gốc (không có foreign key) ──────────────────────────
from .district import District          # districts
from .user import User                  # users

# ── Bảng phụ thuộc vào districts ─────────────────────────────
from .street import Street              # streets → FK: districts.id

# ── Bảng phụ thuộc vào streets ───────────────────────────────
from .traffic_data import TrafficData   # traffic_data → FK: streets.id
from .prediction import Prediction      # predictions  → FK: streets.id
from .incident import Incident          # incidents    → FK: streets.id, users.id
from .feedback import Feedback          # feedback     → FK: streets.id

# ── Bảng phụ thuộc vào users ─────────────────────────────────
from .audit_log import AuditLog         # audit_log     → FK: users.id
from .system_config import SystemConfig # system_config → FK: users.id

# Export rõ ràng — giúp IDE gợi ý autocomplete đúng
__all__ = [
    "District",
    "Street",
    "TrafficData",
    "Prediction",
    "Incident",
    "User",
    "Feedback",
    "AuditLog",
    "SystemConfig",
]
