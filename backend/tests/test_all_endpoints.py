import pytest
from dotenv import load_dotenv
load_dotenv("../.env")
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

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
    response = client.get("/api/traffic/schedule/jobs")
    assert response.status_code == 200

def test_scheduler_state():
    response = client.get("/api/traffic/schedule/state")
    assert response.status_code == 200

def test_traffic_history():
    response = client.get("/api/traffic/history?street_id=1&hours=1")
    assert response.status_code in [200, 404, 400]

def test_traffic_map_data():
    response = client.get("/api/traffic/map-data")
    assert response.status_code == 200

if __name__ == "__main__":
    pytest.main(["-v", __file__])
