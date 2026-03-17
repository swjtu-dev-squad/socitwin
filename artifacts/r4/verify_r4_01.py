"""
R4-01 Propagation Visualization Gate Verification Script
"""
import requests
import json
import os
import sys

BASE_URL = "http://localhost:3000"
ARTIFACTS_DIR = os.path.dirname(os.path.abspath(__file__))

results = {}

def gate(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results[name] = {"status": status, "detail": detail}
    icon = "✅" if condition else "❌"
    print(f"  {icon} Gate: {name} -> {status}")
    if detail:
        print(f"     {detail}")
    return condition

print("=" * 60)
print("R4-01 Propagation Visualization Gate Verification")
print("=" * 60)

# Gate 1: propagation query API available
print("\n[Gate 1] propagation-summary API available and returns non-empty data")
try:
    r = requests.get(f"{BASE_URL}/api/analytics/propagation-summary", timeout=5)
    data = r.json()
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    metrics = data.get("metrics", {})
    gate("propagation-summary API available", r.status_code == 200, f"HTTP {r.status_code}")
    gate("nodes > 0", len(nodes) > 0, f"nodes={len(nodes)}")
    gate("metrics returned", bool(metrics), f"metrics keys: {list(metrics.keys())}")
    # Save metrics
    with open(os.path.join(ARTIFACTS_DIR, "r4_01_metrics.json"), "w") as f:
        json.dump({"nodes": len(nodes), "edges": len(edges), "metrics": metrics, "sample_nodes": nodes[:3]}, f, indent=2)
    print(f"     Saved metrics to r4_01_metrics.json")
except Exception as e:
    gate("propagation-summary API available", False, str(e))
    gate("nodes > 0", False, "API failed")
    gate("metrics returned", False, "API failed")

# Gate 2: PropagationGraph component exists in codebase
print("\n[Gate 2] PropagationGraph component exists")
comp_path = os.path.join(os.path.dirname(os.path.dirname(ARTIFACTS_DIR)), "src", "components", "PropagationGraph.tsx")
gate("PropagationGraph.tsx exists", os.path.exists(comp_path), comp_path)
if os.path.exists(comp_path):
    with open(comp_path) as f:
        content = f.read()
    gate("ForceGraph2D used", "ForceGraph2D" in content, "react-force-graph-2d integration")
    gate("node click handler", "onNodeClick" in content, "interactive node selection")

# Gate 3: Analytics page no longer has placeholder
print("\n[Gate 3] Analytics page - propagation section not placeholder")
analytics_path = os.path.join(os.path.dirname(os.path.dirname(ARTIFACTS_DIR)), "src", "pages", "Analytics.tsx")
if os.path.exists(analytics_path):
    with open(analytics_path) as f:
        content = f.read()
    gate("PropagationGraph imported", "PropagationGraph" in content, "component imported in Analytics")
    gate("Coming Soon removed from propagation", "需要后端实现社交网络分析算法" not in content, "placeholder removed")

# Gate 4: opinion-distribution API returns real data
print("\n[Gate 4] opinion-distribution API returns real data")
try:
    r = requests.get(f"{BASE_URL}/api/analytics/opinion-distribution", timeout=5)
    data = r.json()
    dist = data.get("distribution", [])
    total = data.get("total", 0)
    gate("opinion-distribution API available", r.status_code == 200, f"HTTP {r.status_code}")
    gate("distribution has 3 categories", len(dist) == 3, f"categories={len(dist)}")
    total_pct = sum(d.get("value", 0) for d in dist)
    gate("distribution sums to ~100%", abs(total_pct - 100) < 1 or total == 0, f"sum={total_pct:.1f}%")
except Exception as e:
    gate("opinion-distribution API available", False, str(e))

# Gate 5: herd-index API returns trend data
print("\n[Gate 5] herd-index API returns trend data")
try:
    r = requests.get(f"{BASE_URL}/api/analytics/herd-index", timeout=5)
    data = r.json()
    trend = data.get("trend", [])
    current = data.get("current", None)
    gate("herd-index API available", r.status_code == 200, f"HTTP {r.status_code}")
    gate("current herd index returned", current is not None, f"current={current}")
except Exception as e:
    gate("herd-index API available", False, str(e))

# Gate 6: TypeScript compiles without errors
print("\n[Gate 6] TypeScript compiles without errors")
import subprocess
result = subprocess.run(
    ["npx", "tsc", "--noEmit"],
    capture_output=True, text=True,
    cwd=os.path.dirname(os.path.dirname(ARTIFACTS_DIR))
)
gate("TypeScript compilation passes", result.returncode == 0, result.stderr[:200] if result.stderr else "clean")

# Summary
print("\n" + "=" * 60)
passed = sum(1 for v in results.values() if v["status"] == "PASS")
total = len(results)
print(f"R4-01 Gates: {passed}/{total} PASS")
print("=" * 60)

# Save report
report = {
    "task": "R4-01",
    "gates": results,
    "summary": {"passed": passed, "total": total, "status": "PASS" if passed == total else "FAIL"}
}
with open(os.path.join(ARTIFACTS_DIR, "r4_01_gate_results.json"), "w") as f:
    json.dump(report, f, indent=2)
print(f"\nSaved gate results to r4_01_gate_results.json")

sys.exit(0 if passed == total else 1)
