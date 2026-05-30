import requests

base_url = "http://localhost:8000/api"

def test_user(email, password):
    print(f"\n--- Testing login for {email} ---")
    login_res = requests.post(f"{base_url}/auth/login", json={"email": email, "password": password})
    print(f"Login Status: {login_res.status_code}")
    if login_res.status_code != 200:
        print(f"Login Response: {login_res.json()}")
        return
    
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test GET /api/users/officers
    off_res = requests.get(f"{base_url}/users/officers", headers=headers)
    print(f"GET /api/users/officers Status: {off_res.status_code}")
    if off_res.status_code != 200:
        print(f"GET /api/users/officers Response: {off_res.json()}")
    else:
        print(f"GET /api/users/officers: Found {len(off_res.json())} officers.")
        
    # Test GET /api/users
    usr_res = requests.get(f"{base_url}/users", headers=headers)
    print(f"GET /api/users Status: {usr_res.status_code}")
    if usr_res.status_code != 200:
         print(f"GET /api/users Response: {usr_res.json()}")
    else:
         print(f"GET /api/users: Found {len(usr_res.json())} users.")

# Test with Admin
test_user("admin@danang-traffic.vn", "Admin@2026!")

# Test with CSGT
test_user("csgt@danang.gov.vn", "password123")
