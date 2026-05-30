# tests/comprehensive_test_suite.py
"""
comprehensive_test_suite.py — Bộ kiểm thử tự động hóa toàn diện API của dự án
Đóng vai trò là Senior QA:
  - Tự động chạy qua 6 Module API
  - Đo thời gian phản hồi (Performance check)
  - Xác thực cấu trúc dữ liệu trả về
  - Kiểm tra phân quyền (Role-based access control)
  
Chạy từ trong Docker:
    docker compose exec backend python tests/comprehensive_test_suite.py
"""

import urllib.request
import urllib.error
import json
import time
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000/api"
ADMIN_EMAIL = "admin@danang-traffic.vn"
ADMIN_PASSWORD = "Admin@2026!"

# Biến lưu trữ tokens cho các bước sau
tokens = {
    "admin": None,
    "csgt": None
}
user_ids = {
    "csgt": None
}
created_incident_id = None

SEP = "=" * 80
SUB_SEP = "-" * 80

def request_api(path, method="GET", payload=None, token=None):
    """Hàm helper gửi HTTP Request và đo thời gian phản hồi"""
    url = f"{BASE_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = response.read().decode("utf-8")
            elapsed = time.time() - start_time
            res_obj = json.loads(res_data) if res_data else {}
            return response.status, res_obj, elapsed, None
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start_time
        try:
            err_data = e.read().decode("utf-8")
            err_obj = json.loads(err_data)
        except Exception:
            err_obj = {"detail": str(e)}
        return e.code, err_obj, elapsed, str(e)
    except Exception as e:
        elapsed = time.time() - start_time
        return 500, {"detail": str(e)}, elapsed, str(e)

def run_test_case(name, action):
    """Chạy 1 test case và in kết quả đẹp mắt"""
    print(f"👉 Running: {name}")
    status, body, elapsed, err = action()
    
    # Định dạng kết quả
    if err:
        status_text = f"\033[91mFAILED (HTTP {status})\033[0m"
    else:
        status_text = f"\033[92mPASSED (HTTP {status})\033[0m"
        
    print(f"   Result  : {status_text}")
    print(f"   Duration: {elapsed:.3f}s")
    if err or status >= 400:
        print(f"   Response: {json.dumps(body, ensure_ascii=False)[:300]}...")
    return status, body, elapsed, err

# ══════════════════════════════════════════════════════════════════════════════
# MODULE 1: AUTHENTICATION & AUTHORIZATION (Xác thực & Phân quyền)
# ══════════════════════════════════════════════════════════════════════════════
def test_module_auth():
    print(f"\n{SEP}")
    print(" MODULE 1: AUTHENTICATION & AUTHORIZATION")
    print(SEP)
    
    # TC-AUTH-01: Đăng nhập Admin thành công
    def login_admin():
        payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        status, body, elapsed, err = request_api("/auth/login", "POST", payload)
        if status == 200 and "access_token" in body:
            tokens["admin"] = body["access_token"]
            return status, body, elapsed, None
        return status, body, elapsed, err or "Token not found"
    run_test_case("TC-AUTH-01: Đăng nhập Admin hợp lệ", login_admin)
    
    # TC-AUTH-02: Đăng nhập thất bại (Sai mật khẩu)
    def login_fail():
        payload = {"email": ADMIN_EMAIL, "password": "WrongPassword123!"}
        status, body, elapsed, err = request_api("/auth/login", "POST", payload)
        if status == 401:
            return status, body, elapsed, None
        return status, body, elapsed, "Kỳ vọng trả về 401 do sai mật khẩu"
    run_test_case("TC-AUTH-02: Đăng nhập sai mật khẩu", login_fail)

    # TC-AUTH-04: Gọi thông tin cá nhân /auth/me
    def get_me():
        status, body, elapsed, err = request_api("/auth/me", "GET", token=tokens["admin"])
        if status == 200 and body.get("email") == ADMIN_EMAIL:
            return status, body, elapsed, None
        return status, body, elapsed, err or "Email mismatched"
    run_test_case("TC-AUTH-04: Lấy thông tin cá nhân Admin", get_me)

    # TC-AUTH-05: Gọi /auth/me không kèm token
    def get_me_unauthorized():
        status, body, elapsed, err = request_api("/auth/me", "GET")
        if status == 401:
            return status, body, elapsed, None
        return status, body, elapsed, "Kỳ vọng 401 khi không có token"
    run_test_case("TC-AUTH-05: Gọi API yêu cầu auth mà không truyền token", get_me_unauthorized)

# ══════════════════════════════════════════════════════════════════════════════
# MODULE 2: STREETS & TRAFFIC DATA (Dữ liệu đường phố & Traffic)
# ══════════════════════════════════════════════════════════════════════════════
def test_module_traffic():
    print(f"\n{SEP}")
    print(" MODULE 2: STREETS & TRAFFIC DATA")
    print(SEP)
    
    # TC-TRAFFIC-01: Lấy danh sách đường phố
    def get_streets():
        status, body, elapsed, err = request_api("/streets", "GET")
        if status == 200 and isinstance(body, list) and len(body) > 0:
            return status, body, elapsed, None
        return status, body, elapsed, err or "Danh sách đường trống"
    run_test_case("TC-TRAFFIC-01: Lấy danh sách đường phố", get_streets)
    
    # TC-TRAFFIC-02: Lấy trạng thái traffic nhẹ (state)
    global time_miss, time_hit
    time_miss, time_hit = 0, 0
    
    def get_traffic_state_miss():
        global time_miss
        status, body, elapsed, err = request_api("/traffic/state", "GET")
        time_miss = elapsed
        if status == 200 and "streets" in body:
            # Kiểm tra xem có chứa trường cấm không (geometry)
            sample = body["streets"][0]
            if "path" in sample or "geometry" in sample:
                return status, body, elapsed, "Lỗi bảo mật dữ liệu: Trạng thái traffic nhẹ chứa geometry!"
            return status, body, elapsed, None
        return status, body, elapsed, err or "Format error"
    run_test_case("TC-TRAFFIC-02a: Lấy trạng thái traffic nhẹ (Lần 1 - Cold/Cache Miss)", get_traffic_state_miss)
    
    def get_traffic_state_hit():
        global time_hit
        status, body, elapsed, err = request_api("/traffic/state", "GET")
        time_hit = elapsed
        if status == 200:
            return status, body, elapsed, None
        return status, body, elapsed, err
    run_test_case("TC-TRAFFIC-02b: Lấy trạng thái traffic nhẹ (Lần 2 - Hot/Cache Hit)", get_traffic_state_hit)
    
    speedup = time_miss / time_hit if time_hit > 0 else 0
    print(f"   ℹ️  Redis Cache Speedup: {speedup:.2f}x (Cold: {time_miss:.3f}s -> Hot: {time_hit:.3f}s)")
    
    # TC-TRAFFIC-03: Lấy geometry tĩnh của các đường phố
    def get_traffic_geometry():
        status, body, elapsed, err = request_api("/traffic/streets-geometry", "GET")
        if status == 200 and "streets" in body:
            sample = body["streets"][0]
            if "path" not in sample:
                return status, body, elapsed, "Thiếu trường 'path' (geometry)"
            if "congestion_level" in sample:
                return status, body, elapsed, "Dữ liệu geometry tĩnh chứa thông tin traffic!"
            return status, body, elapsed, None
        return status, body, elapsed, err or "Format error"
    run_test_case("TC-TRAFFIC-03: Lấy geometry tĩnh đường phố", get_traffic_geometry)

# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3: ROUTING & BRIDGES (Thuật toán tìm đường qua sông & cầu)
# ══════════════════════════════════════════════════════════════════════════════
def test_module_routing():
    print(f"\n{SEP}")
    print(" MODULE 3: ROUTING (A* ALGORITHM)")
    print(SEP)
    
    # Tọa độ kiểm thử
    cases = [
        ("Nội quận Hải Châu (Bạch Đằng -> Trần Phú)", 16.0676, 108.2218, 16.0660, 108.2125),
        ("Qua Sông Hàn (Bờ Tây Bạch Đằng -> Bờ Đông Trần Hưng Đạo qua Cầu Rồng)", 16.0609, 108.2218, 16.0609, 108.2301),
        ("Qua Cầu Sông Hàn (Hải Châu -> Sơn Trà)", 16.0734, 108.2218, 16.0734, 108.2270),
        ("Liên quận (Liên Chiểu Nguyễn Lương Bằng -> Hải Châu Bạch Đằng)", 16.0920, 108.1690, 16.0676, 108.2218),
    ]
    
    for idx, (label, f_lat, f_lng, t_lat, t_lng) in enumerate(cases, 1):
        def run_routing_shortest():
            path = f"/routes?from_lat={f_lat}&from_lng={f_lng}&to_lat={t_lat}&to_lng={t_lng}&mode=shortest"
            status, body, elapsed, err = request_api(path, "GET")
            if status == 200 and "nodes" in body and len(body["nodes"]) > 0:
                return status, body, elapsed, None
            return status, body, elapsed, err or "Không tìm thấy đường đi"
        run_test_case(f"TC-ROUTE-0{idx}a: {label} (Shortest Mode)", run_routing_shortest)
        
        def run_routing_fastest():
            path = f"/routes?from_lat={f_lat}&from_lng={f_lng}&to_lat={t_lat}&to_lng={t_lng}&mode=fastest"
            status, body, elapsed, err = request_api(path, "GET")
            if status == 200 and "nodes" in body and len(body["nodes"]) > 0:
                return status, body, elapsed, None
            return status, body, elapsed, err or "Không tìm thấy đường đi"
        run_test_case(f"TC-ROUTE-0{idx}b: {label} (Fastest Mode)", run_routing_fastest)

    # TC-ROUTE-05: Điểm lỗi ngoài phạm vi Đà Nẵng
    def run_routing_error():
        # Điểm Hà Nội
        path = f"/routes?from_lat=21.0285&from_lng=105.8542&to_lat=16.0676&to_lng=108.2218"
        status, body, elapsed, err = request_api(path, "GET")
        if status == 400:
            return status, body, elapsed, None
        return status, body, elapsed, "Kỳ vọng trả về 400 do điểm ngoài phạm vi"
    run_test_case("TC-ROUTE-05: Tìm đường ngoài khu vực hỗ trợ (Hà Nội -> Đà Nẵng)", run_routing_error)

# ══════════════════════════════════════════════════════════════════════════════
# MODULE 4: INCIDENTS CRUD (Quản lý Sự cố / Lô cốt)
# ══════════════════════════════════════════════════════════════════════════════
def test_module_incidents():
    print(f"\n{SEP}")
    print(" MODULE 4: INCIDENTS (CRUD & RBAC)")
    print(SEP)
    
    global created_incident_id
    
    # 1. Admin tạo tài khoản CSGT mới để thực hiện test
    def create_csgt_user():
        payload = {
            "email": "test_csgt@danang-traffic.vn",
            "password": "Csgt@2026!",
            "full_name": "CSGT Kiểm Thử",
            "role": "csgt"
        }
        status, body, elapsed, err = request_api("/users", "POST", payload, token=tokens["admin"])
        if status == 201:
            user_ids["csgt"] = body["id"]
            return status, body, elapsed, None
        elif status == 400 and "đã được sử dụng" in body.get("detail", ""):
            # Lấy danh sách user để tìm ID nếu đã tồn tại
            u_status, u_body, _, _ = request_api("/users", "GET", token=tokens["admin"])
            for u in u_body:
                if u["email"] == "test_csgt@danang-traffic.vn":
                    user_ids["csgt"] = u["id"]
                    break
            return 200, {"message": "User đã tồn tại, dùng lại"}, elapsed, None
        return status, body, elapsed, err
    run_test_case("TC-USER-01: Admin tạo tài khoản CSGT mới", create_csgt_user)
    
    # 2. Đăng nhập tài khoản CSGT để lấy token
    def login_csgt():
        payload = {"email": "test_csgt@danang-traffic.vn", "password": "Csgt@2026!"}
        status, body, elapsed, err = request_api("/auth/login", "POST", payload)
        if status == 200 and "access_token" in body:
            tokens["csgt"] = body["access_token"]
            return status, body, elapsed, None
        return status, body, elapsed, err
    run_test_case("TC-AUTH-06: Đăng nhập với tài khoản CSGT vừa tạo", login_csgt)
    
    # 3. CSGT tạo mới sự cố
    def create_incident():
        global created_incident_id
        payload = {
            "street_id": 1,
            "type": "accident",
            "start_time": datetime.now().isoformat(),
            "severity": 2,
            "description": "Tai nạn xe máy nghiêm trọng gây ách tắc nhẹ",
            "status": "active",
            "is_active": True
        }
        status, body, elapsed, err = request_api("/incidents", "POST", payload, token=tokens["csgt"])
        if status == 201 and "id" in body:
            created_incident_id = body["id"]
            return status, body, elapsed, None
        return status, body, elapsed, err
    run_test_case("TC-INCIDENT-02: CSGT tạo mới sự cố giao thông", create_incident)
    
    # 4. Lấy danh sách sự cố công khai (cần token CSGT/Admin để xem chi tiết)
    def list_incidents():
        status, body, elapsed, err = request_api("/incidents", "GET", token=tokens["csgt"])
        if status == 200 and isinstance(body, list) and len(body) > 0:
            return status, body, elapsed, None
        return status, body, elapsed, err or "Không có sự cố nào"
    run_test_case("TC-INCIDENT-01: Lấy danh sách sự cố giao thông", list_incidents)
    
    # 5. Cập nhật sự cố (chuyển sang trạng thái resolved)
    def update_incident():
        payload = {
            "status": "resolved"
        }
        status, body, elapsed, err = request_api(f"/incidents/{created_incident_id}", "PUT", payload, token=tokens["csgt"])
        if status == 200 and body.get("status") == "resolved" and body.get("is_active") is False:
            return status, body, elapsed, None
        return status, body, elapsed, err or "Status hoặc is_active không đổi đúng kỳ vọng"
    run_test_case("TC-INCIDENT-04: Cập nhật sự cố giao thông -> Resolved", update_incident)
    
    # 6. Xóa sự cố vật lý
    def delete_incident():
        status, body, elapsed, err = request_api(f"/incidents/{created_incident_id}", "DELETE", token=tokens["csgt"])
        if status == 200:
            return status, body, elapsed, None
        return status, body, elapsed, err
    run_test_case("TC-INCIDENT-05: CSGT xóa sự cố giao thông khỏi hệ thống", delete_incident)

# ══════════════════════════════════════════════════════════════════════════════
# MODULE 5: PREDICTION AI & METRICS (Dự báo giao thông 30 phút)
# ══════════════════════════════════════════════════════════════════════════════
def test_module_prediction():
    print(f"\n{SEP}")
    print(" MODULE 5: PREDICTION & AI MODELS")
    print(SEP)
    
    # TC-PREDICT-01: Lấy metrics của model
    def get_metrics():
        status, body, elapsed, err = request_api("/predict/metrics", "GET")
        if status == 200:
            return status, body, elapsed, None
        return status, body, elapsed, err
    run_test_case("TC-PREDICT-01: Lấy metrics huấn luyện của model AI", get_metrics)
    
    # TC-PREDICT-02: Dự báo 30 phút cho tất cả các đường
    def predict_all():
        status, body, elapsed, err = request_api("/predict/30min", "GET")
        if status == 200 and isinstance(body, list):
            return status, body, elapsed, None
        return status, body, elapsed, err
    run_test_case("TC-PREDICT-02: Dự báo ùn tắc 30 phút cho toàn bộ mạng lưới đường", predict_all)

# ══════════════════════════════════════════════════════════════════════════════
# DỌN DẸP TÀI NGUYÊN (CLEANUP)
# ══════════════════════════════════════════════════════════════════════════════
def cleanup():
    print(f"\n{SEP}")
    print(" CLEANUP RESOURCES")
    print(SEP)
    if user_ids["csgt"]:
        # Vô hiệu hóa user csgt test
        def deactivate_user():
            status, body, elapsed, err = request_api(f"/users/{user_ids['csgt']}", "DELETE", token=tokens["admin"])
            if status == 200:
                return status, body, elapsed, None
            return status, body, elapsed, err
        run_test_case("CLEANUP: Vô hiệu hóa tài khoản CSGT test", deactivate_user)

if __name__ == "__main__":
    print(SEP)
    print(" 🛠️  SENIOR QA API TEST SUITE STARTED 🛠️")
    print(SEP)
    
    try:
        test_module_auth()
        test_module_traffic()
        test_module_routing()
        test_module_incidents()
        test_module_prediction()
    finally:
        cleanup()
        
    print(f"\n{SEP}")
    print(" 🏁 TEST SUITE FINISHED")
    print(SEP)
