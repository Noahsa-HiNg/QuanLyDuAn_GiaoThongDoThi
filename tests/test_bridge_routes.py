import httpx

BASE = "http://localhost:8000"

tests = [
    ("Noi quan Hai Chau (control)", "16.0680", "108.2240", "16.0720", "108.2050"),
    ("Hai Chau -> Son Tra qua Cau Rong", "16.0614", "108.2240", "16.0614", "108.2325"),
    ("Hai Chau -> Son Tra qua Cau Song Han", "16.0717", "108.2240", "16.0728", "108.2318"),
    ("Lien Chieu -> Hai Chau qua Dien Bien Phu", "16.0655", "108.1795", "16.0715", "108.2235"),
]

print("=" * 65)
print("Kiem tra route qua cau va lien quan")
print("=" * 65)

for label, flat, flng, tlat, tlng in tests:
    try:
        url = f"{BASE}/api/routes?from_lat={flat}&from_lng={flng}&to_lat={tlat}&to_lng={tlng}&mode=shortest"
        r = httpx.get(url, timeout=20)
        data = r.json()
        if "error" in data:
            print(f"  FAIL {label}")
            print(f"       Loi: {data['error']}")
        else:
            km = data.get("distance_km", "?")
            mins = data.get("duration_min", "?")
            streets = data.get("streets", [])
            print(f"  OK   {label}")
            print(f"       {km}km | {mins} phut | {' -> '.join(streets[:5])}")
    except Exception as e:
        print(f"  ERR  {label}: {e}")

print("=" * 65)
