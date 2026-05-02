"""
auth/password.py — Bcrypt password helper

Dùng thư viện bcrypt trực tiếp (thay vì passlib) để tránh
lỗi version conflict giữa passlib 1.7.4 và bcrypt 4.x.
"""
import bcrypt


def hash_password(plain_password: str) -> str:
    """Tạo bcrypt hash từ plaintext password."""
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    So sánh plaintext password với bcrypt hash.
    Return True nếu khớp, False nếu sai.
    """
    password_bytes = plain_password.encode("utf-8")
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hash_bytes)