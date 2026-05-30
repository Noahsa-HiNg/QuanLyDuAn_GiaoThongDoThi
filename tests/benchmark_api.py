"""
tests/benchmark_api.py — Benchmark response time các endpoint quan trọng
Chạy: python tests/benchmark_api.py
Yêu cầu: backend đang chạy tại BACKEND_URL
"""

import time
import httpx
import statistics
import os
import json

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
N_RUNS = 5  # Số lần đo mỗi endpoint

# Thay bằng token thật nếu muốn test các endpoint yêu cầu auth
JWT_TOKEN = os.getenv("JWT_TOKEN", "")

HEADERS_AUTH = {"Authorization": f"Bearer {JWT_TOKEN}"} if JWT_TOKEN else {}


def measure(label: str, url: str, method: str = "GET",
            headers: dict = None, json_body: dict = None,
            n: int = N_RUNS) -> dict:
    """Đo response time N lần, trả về thống kê."""
    times = []
    status_codes = []
    for i in range(n):
        try:
            t0 = time.perf_counter()
            if method == "GET":
                resp = httpx.get(url, headers=headers or {}, timeout=30)
            elif method == "POST":
                resp = httpx.post(url, headers=headers or {}, json=json_body or {}, timeout=30)
            elapsed = (time.perf_counter() - t0) * 1000  # ms
            times.append(elapsed)
            status_codes.append(resp.status_code)
        except Exception as e:
            times.append(30_000)  # 30s timeout
            status_codes.append(0)
            print(f"  ❌ Run {i+1} lỗi: {e}")

    avg  = statistics.mean(times)
    mn   = min(times)
    mx   = max(times)
    p95  = sorted(times)[int(n * 0.95)] if n > 1 else times[0]

    status_ok = all(s in (200, 201) for s in status_codes)
    status_sym = "✅" if status_ok else "⚠️ "

    print(f"  {status_sym} {label:<40} avg={avg:7.0f}ms  min={mn:6.0f}ms  max={mx:6.0f}ms  p95={p95:6.0f}ms")
    return {"label": label, "avg_ms": avg, "min_ms": mn, "max_ms": mx, "p95_ms": p95}


def run_benchmark():
    print("=" * 80)
    print(f"🔍 Benchmark Backend: {BACKEND_URL}")
    print(f"   Số lần đo: {N_RUNS} lần/endpoint")
    print("=" * 80)

    results = []

    # ── Health check (baseline) ───────────────────────────────────────────
    print("\n📡 Health Checks:")
    results.append(measure("GET /api/health",         f"{BACKEND_URL}/api/health"))
    results.append(measure("GET / (redirect)",        f"{BACKEND_URL}/"))

    # ── Streets / Traffic (public, không cần auth) ────────────────────────
    print("\n🗺️  Traffic & Streets (Public):")
    results.append(measure("GET /api/streets",            f"{BACKEND_URL}/api/streets?page_size=50"))
    results.append(measure("GET /api/traffic/state",      f"{BACKEND_URL}/api/traffic/state"))
    results.append(measure("GET /api/traffic/streets-geometry", f"{BACKEND_URL}/api/traffic/streets-geometry"))
    results.append(measure("GET /api/traffic/current",    f"{BACKEND_URL}/api/traffic/current"))

    # ── Routing (public) ──────────────────────────────────────────────────
    print("\n🔀 Routing (A*):")
    results.append(measure(
        "GET /api/routes (shortest)",
        f"{BACKEND_URL}/api/routes?from_lat=16.0668&from_lng=108.2208&to_lat=16.0544&to_lng=108.2022&mode=shortest"
    ))
    results.append(measure(
        "GET /api/routes (fastest)",
        f"{BACKEND_URL}/api/routes?from_lat=16.0668&from_lng=108.2208&to_lat=16.0544&to_lng=108.2022&mode=fastest"
    ))

    # ── Prediction (public) ───────────────────────────────────────────────
    print("\n🤖 AI Prediction:")
    results.append(measure("GET /api/predict/30min",  f"{BACKEND_URL}/api/predict/30min"))

    # ── Incidents (yêu cầu token CSGT/Admin) ─────────────────────────────
    if JWT_TOKEN:
        print("\n🚧 Incidents (Auth required):")
        results.append(measure(
            "GET /api/incidents",
            f"{BACKEND_URL}/api/incidents?page_size=20",
            headers=HEADERS_AUTH
        ))
        results.append(measure(
            "GET /api/incidents?type=roadblock",
            f"{BACKEND_URL}/api/incidents?type=roadblock&page_size=20",
            headers=HEADERS_AUTH
        ))
    else:
        print("\n⚠️  Bỏ qua Incidents — không có JWT_TOKEN")
        print("   Chạy lại với: JWT_TOKEN=<token> python tests/benchmark_api.py")

    # ── Stats ─────────────────────────────────────────────────────────────
    print("\n📊 Stats:")
    results.append(measure("GET /api/stats/summary",  f"{BACKEND_URL}/api/stats/summary"))

    # ── Tổng kết ──────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("📈 TÓM TẮT:")
    print("=" * 80)

    slow = [r for r in results if r.get("avg_ms", 0) > 500]
    ok   = [r for r in results if r.get("avg_ms", 0) <= 500]

    print(f"\n✅ Nhanh (avg < 500ms): {len(ok)} endpoint")
    print(f"🐢 Chậm (avg > 500ms): {len(slow)} endpoint")

    if slow:
        print("\n🐢 Endpoint cần chú ý:")
        for r in sorted(slow, key=lambda x: -x["avg_ms"]):
            print(f"   ⚠️  {r['label']}: avg={r['avg_ms']:.0f}ms")

    # Lưu kết quả JSON
    out_path = os.path.join(os.path.dirname(__file__), "benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "backend_url": BACKEND_URL,
            "n_runs": N_RUNS,
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Kết quả đã lưu: {out_path}")
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark()
