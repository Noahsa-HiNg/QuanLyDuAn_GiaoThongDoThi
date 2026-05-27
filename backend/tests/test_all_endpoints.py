import pytest
from dotenv import load_dotenv
load_dotenv("../.env")
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Helper để đăng nhập và lấy access token cho các API yêu cầu xác thực
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

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "db" in data
    assert "redis" in data

def test_get_streets():
    response = client.get("/api/streets?page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "data" in data
    assert isinstance(data["data"], list)

def test_get_street_by_id_not_found():
    response = client.get("/api/streets/999999999")
    assert response.status_code == 404

def test_predict_metrics():
    response = client.get("/api/predict/metrics")
    assert response.status_code in [200, 503]

def test_predict_30min():
    response = client.get("/api/predict/30min")
    assert response.status_code in [200, 503]

def test_scheduler_jobs():
    headers = get_auth_headers()
    response = client.get("/api/traffic/schedule/jobs", headers=headers)
    assert response.status_code == 200

def test_scheduler_state():
    headers = get_auth_headers()
    response = client.get("/api/traffic/schedule/state", headers=headers)
    assert response.status_code == 200

def test_traffic_current():
    response = client.get("/api/traffic/current")
    assert response.status_code == 200

# --- KIỂM THỬ PHÂN HỆ THỐNG KÊ (STATS ENDPOINTS) ---

def test_stats_top_congested_unauthorized():
    # Gọi không có token -> phải lỗi 401
    response = client.get("/api/stats/top-congested?limit=5")
    assert response.status_code == 401

def test_stats_top_congested():
    headers = get_auth_headers()
    response = client.get("/api/stats/top-congested?limit=5", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5

def test_stats_congested_ranking():
    headers = get_auth_headers()
    # Thử cào theo ngày, tuần, tháng
    for period in ["1d", "1w", "1m"]:
        response = client.get(f"/api/stats/congested-ranking?period={period}&limit=5", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 5
        if data:
            item = data[0]
            assert "street_id" in item
            assert "street_name" in item
            assert "congestion_rate" in item

def test_stats_congested_by_district():
    headers = get_auth_headers()
    for period in ["realtime", "1d", "1w", "1m"]:
        response = client.get(f"/api/stats/congested-by-district?period={period}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "district_id" in item
            assert "district_name" in item
            assert "total_streets" in item
            assert "congested_occurrences" in item
            assert "avg_congestion_rate" in item

def test_stats_hourly_trend():
    headers = get_auth_headers()
    response = client.get("/api/stats/hourly-trend", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 24
    assert data[0]["hour"] == 0
    assert data[23]["hour"] == 23

def test_stats_incidents():
    headers = get_auth_headers()
    response = client.get("/api/stats/incidents", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_active" in data
    assert "by_type" in data
    assert "by_severity" in data
    assert "avg_resolve_time_minutes" in data

def test_stats_feedback_summary():
    headers = get_auth_headers()
    response = client.get("/api/stats/feedback-summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_reports" in data
    assert "by_type" in data
    assert "top_reported_streets" in data
    assert isinstance(data["top_reported_streets"], list)

if __name__ == "__main__":
    pytest.main(["-v", __file__])
