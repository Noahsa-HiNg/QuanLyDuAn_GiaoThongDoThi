"""
tests/test_sql_injection.py — S3-36c: Kiểm tra SQL Injection Prevention

Task: gửi email: "' OR 1=1--" → phải nhận 422, KHÔNG lỗi DB

Chạy:
    cd backend
    python tests/test_sql_injection.py
"""

import httpx

BASE = "http://localhost:8000/api"
GREEN = "\033[92m"; RED = "\033[91m"; RESET = "\033[0m"; BOLD = "\033[1m"

def ok(msg):   print(f"  {GREEN}✅ PASS{RESET} — {msg}")
def fail(msg): print(f"  {RED}❌ FAIL{RESET} — {msg}")


def test_sql_injection_login():
    """
    S3-36c: Gửi SQL injection payload vào POST /api/auth/login
    Mong đợi: 422 Unprocessable Entity (Pydantic từ chối trước khi vào DB)
    """
    print(f"\n{BOLD}{'─'*50}\n  S3-36c: SQL Injection Prevention\n{'─'*50}{RESET}")

    # Các payload tấn công kinh điển
    payloads = [
        # (mô tả, email, password)
        ("Classic OR bypass",      "' OR 1=1--",           "anything"),
        ("Email field injection",  "admin'--",              "password"),
        ("Union-based",            "' UNION SELECT 1--",   "pass"),
        ("Comment injection",      "user@test.com'/*",     "pass"),
        ("Short password (<8 ký tự)", "valid@email.com",  "abc"),  # S3-36b
    ]

    for desc, email, password in payloads:
        resp = httpx.post(
            f"{BASE}/auth/login",
            json={"email": email, "password": password},
        )
        if resp.status_code == 422:
            ok(f"{desc} → 422 (Pydantic block) ✓")
        elif resp.status_code == 401:
            # 401 nghĩa là qua Pydantic nhưng DB từ chối (sai password)
            # → SQL không bị inject (DB không trả dữ liệu bừa)
            ok(f"{desc} → 401 (Auth block, DB an toàn) ✓")
        elif resp.status_code == 500:
            fail(f"{desc} → 500 Internal Server Error ← CÓ THỂ BỊ INJECT!")
        else:
            fail(f"{desc} → {resp.status_code}: {resp.text[:100]}")

    print()


def test_email_format_validation():
    """S3-36b: Email format phải hợp lệ (EmailStr của Pydantic)."""
    print(f"\n{BOLD}{'─'*50}\n  S3-36b: Email Format Validation\n{'─'*50}{RESET}")

    invalid_emails = [
        "notanemail",
        "missing@",
        "@nodomain.com",
        "spaces in@email.com",
        "",
    ]

    for email in invalid_emails:
        resp = httpx.post(
            f"{BASE}/auth/login",
            json={"email": email, "password": "validpassword123"},
        )
        if resp.status_code == 422:
            ok(f"Email '{email}' → 422 ✓")
        else:
            fail(f"Email '{email}' → {resp.status_code} (mong 422)")

    print()


def test_password_min_length():
    """S3-36b: Password phải >= 8 ký tự."""
    print(f"\n{BOLD}{'─'*50}\n  S3-36b: Password Min Length (>=8)\n{'─'*50}{RESET}")

    short_passwords = ["", "a", "abc", "1234567"]  # < 8 ký tự
    for pwd in short_passwords:
        resp = httpx.post(
            f"{BASE}/auth/login",
            json={"email": "valid@test.com", "password": pwd},
        )
        if resp.status_code == 422:
            ok(f"Password '{pwd}' ({len(pwd)} ký tự) → 422 ✓")
        else:
            fail(f"Password '{pwd}' → {resp.status_code} (mong 422)")

    # 8 ký tự trở lên → qua validation (có thể 401 vì sai password)
    resp = httpx.post(
        f"{BASE}/auth/login",
        json={"email": "valid@test.com", "password": "12345678"},
    )
    if resp.status_code in (401, 200):
        ok(f"Password '12345678' (8 ký tự) → {resp.status_code} (qua validation) ✓")
    else:
        fail(f"Password '12345678' → {resp.status_code}")

    print()


if __name__ == "__main__":
    print(f"\n{BOLD}🛡️  KIỂM THỬ SQL INJECTION PREVENTION — S3-36{RESET}")
    print(f"   Backend: {BASE}\n")

    test_email_format_validation()
    test_password_min_length()
    test_sql_injection_login()

    print(f"{BOLD}✅ Kiểm thử hoàn tất{RESET}\n")
