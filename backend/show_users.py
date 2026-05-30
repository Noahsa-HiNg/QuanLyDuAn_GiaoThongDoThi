from database import SessionLocal
from models.user import User

db = SessionLocal()
try:
    users = db.query(User).all()
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}, Role: {u.role}, Active: {u.is_active}, Locked: {u.is_locked}")
finally:
    db.close()
