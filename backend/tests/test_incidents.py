import pytest
from dotenv import load_dotenv
load_dotenv("../.env")
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Helper để lấy headers với JWT token của admin
def get_auth_headers():
    login_payload = {
        "email": "admin@danang-traffic.vn",
        "password": "Admin@2026!"
    }
    response = client.post("/api/auth/login", json=login_payload)
    if response.status_code == 200:
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return {}

def test_crud_incidents_lifecycle():
    # 1. Gọi GET danh sách không có token -> Lỗi 401
    response = client.get("/api/incidents")
    assert response.status_code == 401

    # Lấy headers xác thực cho các bước tiếp theo
    headers = get_auth_headers()
    assert headers != {}

    # 2. Lấy danh sách đường để có street_id hợp lệ
    streets_response = client.get("/api/streets?page=1&page_size=1")
    assert streets_response.status_code == 200
    streets_data = streets_response.json()
    assert "data" in streets_data
    assert len(streets_data["data"]) > 0
    street_id = streets_data["data"][0]["id"]

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
    create_response = client.post("/api/incidents", json=create_payload, headers=headers)
    assert create_response.status_code == 201
    created_incident = create_response.json()
    assert created_incident["id"] is not None
    assert created_incident["street_id"] == street_id
    assert created_incident["type"] == "roadblock"
    assert created_incident["severity"] == 2
    assert created_incident["status"] == "active"
    assert created_incident["is_active"] is True
    assert created_incident["created_by"] is not None

    incident_id = created_incident["id"]

    # 4. GET /api/incidents/{id} — Lấy chi tiết sự cố vừa tạo
    get_response = client.get(f"/api/incidents/{incident_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["id"] == incident_id

    # 5. GET /api/incidents — Lấy danh sách và kiểm tra xem có chứa phần tử vừa tạo
    list_response = client.get("/api/incidents?page=1&page_size=10", headers=headers)
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert isinstance(list_data, list)
    assert any(inc["id"] == incident_id for inc in list_data)

    # 6. PUT /api/incidents/{id} — Cập nhật thông tin (đổi mô tả và độ nghiêm trọng)
    update_payload = {
        "severity": 3,
        "description": "Thi công đường ống thoát nước khẩn cấp"
    }
    update_response = client.put(f"/api/incidents/{incident_id}", json=update_payload, headers=headers)
    assert update_response.status_code == 200
    updated_incident = update_response.json()
    assert updated_incident["severity"] == 3
    assert updated_incident["description"] == "Thi công đường ống thoát nước khẩn cấp"
    assert updated_incident["status"] == "active"  # Vẫn giữ nguyên
    assert updated_incident["is_active"] is True

    # 7. PUT /api/incidents/{id} — Chuyển trạng thái sang resolved
    # Kiểm tra xem logic tự động đổi is_active thành False và điền end_time có hoạt động không
    resolve_payload = {
        "status": "resolved"
    }
    resolve_response = client.put(f"/api/incidents/{incident_id}", json=resolve_payload, headers=headers)
    assert resolve_response.status_code == 200
    resolved_incident = resolve_response.json()
    assert resolved_incident["status"] == "resolved"
    assert resolved_incident["is_active"] is False
    assert resolved_incident["end_time"] is not None

    # 8. DELETE /api/incidents/{id} — Xóa sự cố khỏi hệ thống
    delete_response = client.delete(f"/api/incidents/{incident_id}", headers=headers)
    assert delete_response.status_code == 200
    assert "Đã xóa thành công" in delete_response.json()["message"]

    # 9. GET /api/incidents/{id} sau khi xóa -> Trả về 404
    get_after_delete = client.get(f"/api/incidents/{incident_id}", headers=headers)
    assert get_after_delete.status_code == 404

def test_create_incident_invalid_type():
    headers = get_auth_headers()
    # Loại sự cố không hợp lệ (ví dụ: 'traffic_jam' thay vì roadblock/event/accident/community)
    invalid_payload = {
        "street_id": 1,
        "type": "traffic_jam",
        "start_time": "2026-05-27T08:00:00Z",
        "severity": 2,
        "status": "active"
    }
    response = client.post("/api/incidents", json=invalid_payload, headers=headers)
    assert response.status_code == 422  # Validation Error
