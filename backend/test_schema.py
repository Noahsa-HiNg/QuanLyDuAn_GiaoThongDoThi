import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models.user import User
from schemas.user import OfficerOut, UserOut
from pydantic import ValidationError

db = SessionLocal()
try:
    users = db.query(User).all()
    print(f"Found {len(users)} users.")
    for u in users:
        print(f"User ID: {u.id}, Email: {u.email}, Role: {u.role}, is_active: {u.is_active}")
        try:
            # Try OfficerOut validation
            if u.role == 'csgt':
                off = OfficerOut.from_orm(u)
                print(f"  OfficerOut OK: {off.id} - {off.email}")
            
            # Try UserOut validation
            usr = UserOut.from_orm(u)
            print(f"  UserOut OK: {usr.id} - {usr.email}")
        except ValidationError as ve:
            print(f"  Pydantic validation error for user {u.email}:")
            print(ve)
finally:
    db.close()
