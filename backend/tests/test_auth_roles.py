"""
tests/test_auth_roles.py — Kiểm thử phân quyền theo role

Chạy:
    cd backend
    python tests/test_auth_roles.py

Yêu cầu: Backend đang chạy tại http://localhost:8000
"""

import httpx

BASE = "http://localhost:8000/api"

# ── Tài khoản test (thay đổi nếu khác) ───────────────────────
ADMIN_EMAIL    = "admin@danang-traffic.vn"
ADMIN_PASSWORD = "Admin@2026!"
CSGT_EMAIL     = "csgt@danang.gov.vn"
CSGT_PASSWORD  = "Csgt@123"

# ── Màu terminal ──────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def ok(msg):    print(f"  {GREEN}✅ PASS{RESET} — {msg}")
def fail(msg):  print(f"  {RED}❌ FAIL{RESET} — {msg}")
def info(msg):  print(f"  {YELLOW}ℹ️  {msg}{RESET}")
def section(title): print(f"\n{BOLD}{'─'*50}\n  {title}\n{'─'*50}{RESET}")


# ── Helper: login lấy token ───────────────────────────────────
def login(email: str, password: str) -> str | None:
    resp = httpx.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────
# TEST CASES
# ─────────────────────────────────────────────────────────────

def test_public_endpoints():
    """Endpoint public — KHÔNG cần token, ai cũng xem được."""
    section("1. Endpoint Public (không cần đăng nhập)")

    endpoints = [
        ("GET", "/traffic/current",         "Tình trạng giao thông"),
        ("GET", "/traffic/crawl/status",     "Trạng thái crawl 1 lần"),
        ("GET", "/traffic/crawl/loop/status","Trạng thái crawl vòng lặp"),
        ("GET", "/weather/current",          "Thời tiết hiện tại"),
    ]

    for method, path, name in endpoints:
        resp = httpx.request(method, f"{BASE}{path}")
        if resp.status_code in (200, 404):   # 404 chấp nhận được (không có data)
            ok(f"{name} → {resp.status_code}")
        else:
            fail(f"{name} → Mong đợi 200, nhận {resp.status_code}")


def test_no_token_returns_401():
    """Endpoint cần auth — KHÔNG có token → phải nhận 401."""
    section("2. Không có token → 401 Unauthorized")

    protected = [
        ("POST", "/traffic/crawl",              "Cào 1 lần"),
        ("POST", "/traffic/crawl/loop/start",   "Bắt đầu vòng lặp"),
        ("POST", "/traffic/crawl/loop/stop",    "Dừng vòng lặp"),
        ("GET",  "/traffic/schedule/jobs",      "Danh sách jobs"),
        ("POST", "/traffic/schedule/pause",     "Tạm dừng scheduler"),
    ]

    for method, path, name in protected:
        resp = httpx.request(method, f"{BASE}{path}")
        if resp.status_code == 401:
            ok(f"{name} → 401 ✓")
        elif resp.status_code == 403:
            ok(f"{name} → 403 ✓ (Bearer scheme missing)")
        else:
            fail(f"{name} → Mong đợi 401, nhận {resp.status_code}: {resp.text[:80]}")


def test_wrong_token_returns_401():
    """Token sai / giả mạo → 401."""
    section("3. Token sai → 401 Unauthorized")

    fake_token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI5OTkifQ.FAKE_SIGNATURE"
    headers = {"Authorization": f"Bearer {fake_token}"}

    resp = httpx.post(f"{BASE}/traffic/crawl", headers=headers)
    if resp.status_code == 401:
        ok(f"Token giả → 401 ✓")
    else:
        fail(f"Token giả → Mong đợi 401, nhận {resp.status_code}")


def test_csgt_permissions(token: str):
    """CSGT có thể cào (Chế độ 1 + 3) nhưng KHÔNG quản lý scheduler."""
    section("4. Role CSGT — Quyền hạn")

    headers = auth_header(token)

    # ✅ Được phép: cào 1 đường cụ thể
    resp = httpx.post(f"{BASE}/traffic/crawl/1", headers=headers)
    if resp.status_code in (200, 404):
        ok(f"Cào 1 đường (chế độ 3) → {resp.status_code} ✓")
    else:
        fail(f"Cào 1 đường → Mong đợi 200, nhận {resp.status_code}: {resp.text[:80]}")

    # ❌ Bị chặn: quản lý scheduler (chỉ Admin)
    admin_only = [
        ("GET",  "/traffic/schedule/jobs",   "Xem danh sách jobs"),
        ("POST", "/traffic/schedule/pause",  "Tạm dừng scheduler"),
        ("POST", "/traffic/crawl/loop/start","Bắt đầu vòng lặp"),
    ]

    for method, path, name in admin_only:
        resp = httpx.request(method, f"{BASE}{path}", headers=headers)
        if resp.status_code == 403:
            ok(f"{name} bị chặn → 403 ✓")
        else:
            fail(f"{name} → Mong đợi 403, nhận {resp.status_code}: {resp.text[:80]}")


def test_admin_permissions(token: str):
    """Admin có toàn quyền."""
    section("5. Role Admin — Toàn quyền")

    headers = auth_header(token)

    full_access = [
        ("GET",  "/traffic/schedule/jobs",   "Xem danh sách jobs"),
        ("GET",  "/traffic/schedule/state",  "Trạng thái scheduler"),
        ("POST", "/traffic/crawl",           "Cào 1 lần"),
    ]

    for method, path, name in full_access:
        resp = httpx.request(method, f"{BASE}{path}", headers=headers)
        if resp.status_code in (200, 202, 409):  # 409 = đang chạy, cũng OK
            ok(f"{name} → {resp.status_code} ✓")
        else:
            fail(f"{name} → Mong đợi 200/202, nhận {resp.status_code}: {resp.text[:80]}")


def test_get_me(token: str, expected_role: str):
    """GET /auth/me phải trả đúng thông tin user."""
    section(f"6. GET /auth/me — role={expected_role}")

    headers = auth_header(token)
    resp = httpx.get(f"{BASE}/auth/me", headers=headers)

    if resp.status_code == 200:
        data = resp.json()
        if data.get("role") == expected_role:
            ok(f"role='{data['role']}', email='{data['email']}' ✓")
        else:
            fail(f"role sai: mong '{expected_role}', nhận '{data.get('role')}'")
    else:
        fail(f"GET /auth/me → {resp.status_code}: {resp.text[:80]}")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{BOLD}🔐 KIỂM THỬ PHÂN QUYỀN THEO ROLE{RESET}")
    print(f"   Backend: {BASE}")

    # Test public endpoints
    test_public_endpoints()

    # Test không có token
    test_no_token_returns_401()

    # Test token giả
    test_wrong_token_returns_401()

    # Login admin
    section("LOGIN")
    admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if admin_token:
        ok(f"Admin login thành công")
        test_get_me(admin_token, "admin")
        test_admin_permissions(admin_token)
    else:
        fail(f"Admin login thất bại — kiểm tra email/password trong script")
        info(f"Email: {ADMIN_EMAIL} | Password: {ADMIN_PASSWORD}")

    # Login csgt
    csgt_token = login(CSGT_EMAIL, CSGT_PASSWORD)
    if csgt_token:
        ok(f"CSGT login thành công")
        test_get_me(csgt_token, "csgt")
        test_csgt_permissions(csgt_token)
    else:
        fail(f"CSGT login thất bại — kiểm tra email/password trong script")
        info(f"Email: {CSGT_EMAIL} | Password: {CSGT_PASSWORD}")
        info("Nếu chưa có tài khoản CSGT, chỉ chạy test Admin là đủ.")

    print(f"\n{BOLD}✅ Kiểm thử hoàn tất{RESET}\n")
