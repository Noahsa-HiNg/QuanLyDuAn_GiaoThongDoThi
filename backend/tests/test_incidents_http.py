import requests
import json
import sys

BASE_URL = "http://localhost:8000"
TOKEN = None

def get_token():
    print("Testing Login (/api/auth/login)...", end=" ")
    payload = {
        "email": "admin@danang-traffic.vn",
        "password": "Admin@2026!"
    }
    try:
        response = requests.post(f"{BASE_URL}/api/auth/login", json=payload, timeout=10)
        if response.status_code == 200:
            print("OK")
            return response.json().get("access_token")
        else:
            print(f"FAILED (Status: {response.status_code})")
            print(response.text)
            return None
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def test_endpoint(name, url, expected_status_codes=[200], method="GET", json_payload=None):
    print(f"Testing {name} ({method} {url})...", end=" ")
    headers = {}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    try:
        if method == "GET":
            response = requests.get(f"{BASE_URL}{url}", headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(f"{BASE_URL}{url}", json=json_payload, headers=headers, timeout=10)
        elif method == "PUT":
            response = requests.put(f"{BASE_URL}{url}", json=json_payload, headers=headers, timeout=10)
        elif method == "DELETE":
            response = requests.delete(f"{BASE_URL}{url}", headers=headers, timeout=10)
            
        if response.status_code in expected_status_codes:
            print("OK")
            return True, response.json() if response.content else None
        else:
            print(f"FAILED (Status: {response.status_code})")
            print(response.text[:300])
            return False, None
    except Exception as e:
        print(f"ERROR: {e}")
        return False, None

def run_all():
    global TOKEN
    
    # 1. Gọi GET danh sách không có token -> Lỗi 401
    print("Testing Unauthorized access...", end=" ")
    try:
        response = requests.get(f"{BASE_URL}/api/incidents", timeout=10)
        if response.status_code == 401:
            print("OK (401 Unauthorized as expected)")
        else:
            print(f"FAILED (Expected 401, got {response.status_code})")
    except Exception as e:
        print(f"ERROR: {e}")

    # Lấy token đăng nhập
    TOKEN = get_token()
    if not TOKEN:
        print("❌ Cannot authenticate. Aborting tests.")
        sys.exit(1)

    results = []

    # 2. Lấy danh sách đường để có street_id hợp lệ
    res, data = test_endpoint("Get Streets List", "/api/streets?page=1&page_size=1")
    results.append(res)
    if not res or not data.get("data"):
        print("❌ Cannot get a valid street_id to test incidents. Aborting.")
        sys.exit(1)
        
    street_id = data["data"][0]["id"]
    print(f"Using street_id: {street_id} for incident testing.")

    # 3. POST /api/incidents — Tạo sự cố mới (loại roadblock)
    create_payload = {
        "street_id": street_id,
        "type": "roadblock",
        "start_time": "2026-05-27T08:00:00Z",
        "severity": 2,
        "description": "Thi công đường ống thoát nước",
        "status": "active",
        "is_active": True
    }
    res, created_incident = test_endpoint(
        "Create Incident", 
        "/api/incidents", 
        expected_status_codes=[201], 
        method="POST", 
        json_payload=create_payload
    )
    results.append(res)
    if not res or not created_incident:
        print("❌ Failed to create incident. Aborting remaining tests.")
        sys.exit(1)

    incident_id = created_incident["id"]

    # 4. GET /api/incidents/{id} — Lấy chi tiết sự cố vừa tạo
    res, _ = test_endpoint(f"Get Incident {incident_id}", f"/api/incidents/{incident_id}")
    results.append(res)

    # 5. GET /api/incidents — Lấy danh sách sự cố
    res, list_data = test_endpoint("Get Incidents List", "/api/incidents?page=1&page_size=10")
    results.append(res)
    if res and list_data:
        found = any(inc["id"] == incident_id for inc in list_data)
        print(f"   Verification: Created incident in list? {'YES' if found else 'NO'}")
        results.append(found)

    # 6. PUT /api/incidents/{id} — Cập nhật thông tin (đổi mô tả và độ nghiêm trọng)
    update_payload = {
        "severity": 3,
        "description": "Thi công đường ống thoát nước khẩn cấp"
    }
    res, updated_incident = test_endpoint(
        f"Update Incident {incident_id}", 
        f"/api/incidents/{incident_id}", 
        method="PUT", 
        json_payload=update_payload
    )
    results.append(res)
    if res and updated_incident:
        print(f"   Verification: severity updated to 3? {'YES' if updated_incident['severity'] == 3 else 'NO'}")
        results.append(updated_incident["severity"] == 3)

    # 7. PUT /api/incidents/{id} — Chuyển trạng thái sang resolved
    # Kiểm tra xem logic tự động đổi is_active thành False và điền end_time có hoạt động không
    resolve_payload = {
        "status": "resolved"
    }
    res, resolved_incident = test_endpoint(
        f"Resolve Incident {incident_id}", 
        f"/api/incidents/{incident_id}", 
        method="PUT", 
        json_payload=resolve_payload
    )
    results.append(res)
    if res and resolved_incident:
        is_inactive = resolved_incident["is_active"] is False
        has_end_time = resolved_incident["end_time"] is not None
        print(f"   Verification: is_active=False? {'YES' if is_inactive else 'NO'}, end_time set? {'YES' if has_end_time else 'NO'}")
        results.append(is_inactive and has_end_time)

    # 8. POST /api/incidents — Tạo sự cố với type không hợp lệ -> Phải lỗi 422
    invalid_payload = {
        "street_id": street_id,
        "type": "traffic_jam",  # không có trong validation
        "start_time": "2026-05-27T08:00:00Z",
        "severity": 2,
        "status": "active"
    }
    res, _ = test_endpoint(
        "Create Incident with Invalid Type (Expected 422)", 
        "/api/incidents", 
        expected_status_codes=[422], 
        method="POST", 
        json_payload=invalid_payload
    )
    results.append(res)

    # 9. DELETE /api/incidents/{id} — Xóa sự cố khỏi hệ thống
    res, _ = test_endpoint(f"Delete Incident {incident_id}", f"/api/incidents/{incident_id}", method="DELETE")
    results.append(res)

    # 10. GET /api/incidents/{id} sau khi xóa -> Trả về 404
    res, _ = test_endpoint(f"Get Deleted Incident {incident_id} (Expected 404)", f"/api/incidents/{incident_id}", expected_status_codes=[404])
    results.append(res)

    if all(results):
        print("\n✅ All Incident CRUD tests passed successfully over HTTP!")
        sys.exit(0)
    else:
        print("\n❌ Some Incident CRUD tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    run_all()
