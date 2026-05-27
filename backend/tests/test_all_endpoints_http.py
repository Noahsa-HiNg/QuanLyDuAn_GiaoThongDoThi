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
            
        if response.status_code in expected_status_codes:
            print("OK")
            return True, response.json() if response.content else None
        else:
            print(f"FAILED (Status: {response.status_code})")
            print(response.text[:200])
            return False, None
    except Exception as e:
        print(f"ERROR: {e}")
        return False, None

def run_all():
    global TOKEN
    TOKEN = get_token()
    
    results = []
    
    # Health check
    res, data = test_endpoint("Health Check", "/api/health")
    results.append(res)

    # Streets
    res, data = test_endpoint("Get Streets List", "/api/streets?page=1&page_size=5")
    results.append(res)
    res, _ = test_endpoint("Get Single Street Not Found", "/api/streets/999999", [404])
    results.append(res)

    # Traffic
    res, data = test_endpoint("Traffic Current", "/api/traffic/current")
    results.append(res)

    res, _ = test_endpoint("Traffic Schedule Jobs", "/api/traffic/schedule/jobs")
    results.append(res)

    res, _ = test_endpoint("Traffic Schedule State", "/api/traffic/schedule/state")
    results.append(res)

    # Prediction
    res, _ = test_endpoint("Prediction 30min", "/api/predict/30min", [200, 503])
    results.append(res)

    res, _ = test_endpoint("Prediction Metrics", "/api/predict/metrics", [200, 503, 404])
    results.append(res)

    # Route
    res, data = test_endpoint("Route Finding (invalid points)", "/api/route?start_lat=0&start_lon=0&end_lat=1&end_lon=1", [400, 404, 500])
    results.append(res)

    if all(results):
        print("\n✅ All basic endpoint tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    run_all()
