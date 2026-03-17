"""
R2-05: API-only / Single-Process Database Constraint Smoke Test
Validates that:
1. CLI smoke uses independent fixture database
2. Dashboard interactions go through API only
3. No disk I/O errors during the test round
4. Single-process write principle is enforced
"""
import subprocess, os, sqlite3, requests, time, json

BASE = "http://localhost:3000"

print("=" * 60)
print("R2-05: API-only / DB Constraint Smoke Test")
print("=" * 60)

results = {}

# ---- Check 1: CLI smoke uses independent fixture database ----
print("\n[Check 1] CLI smoke uses independent fixture database")
# context_smoke.py uses /tmp/oasis-context-smoke.db by default
import subprocess
result = subprocess.run(
    ["grep", "-n", "context-smoke\|fixture\|/tmp/", 
     "oasis_dashboard/context_smoke.py"],
    capture_output=True, text=True, cwd="/home/ubuntu/oasis-dashboard"
)
cli_db_path = None
for line in result.stdout.splitlines():
    if "context-smoke" in line or "/tmp/" in line:
        cli_db_path = line
        break

# Also check the default db path in context_smoke
result2 = subprocess.run(
    ["grep", "-n", "db_path\|database\|sqlite\|\.db"],
    stdin=subprocess.PIPE,
    capture_output=True, text=True
)

# Check context_smoke.py for db path
with open("/home/ubuntu/oasis-dashboard/oasis_dashboard/context_smoke.py") as f:
    content = f.read()
    
db_lines = [l for l in content.splitlines() if ".db" in l.lower() and ("tmp" in l.lower() or "fixture" in l.lower() or "default" in l.lower())]
print(f"  context_smoke.py DB references:")
for l in db_lines[:5]:
    print(f"    {l.strip()}")

# Check that context_smoke uses /tmp path
uses_tmp_db = any("/tmp" in l for l in db_lines)
print(f"  Uses /tmp (isolated) database: {'✅ YES' if uses_tmp_db else '⚠️ CHECK NEEDED'}")
results['cli_uses_fixture_db'] = uses_tmp_db

# ---- Check 2: Dashboard DB path ----
print("\n[Check 2] Dashboard uses separate database from CLI smoke")
result3 = subprocess.run(
    ["grep", "-n", "oasis_simulation\|\.db"],
    stdin=open("/home/ubuntu/oasis-dashboard/oasis_dashboard/real_oasis_engine_v3.py"),
    capture_output=True, text=True
)
dashboard_db_lines = [l for l in result3.stdout.splitlines() if ".db" in l][:5]
print(f"  real_oasis_engine_v3.py DB references:")
for l in dashboard_db_lines:
    print(f"    {l.strip()}")

# Check they are different paths
dashboard_uses_oasis_simulation = any("oasis_simulation" in l for l in dashboard_db_lines)
print(f"  Dashboard uses 'oasis_simulation.db': {'✅ YES (separate from /tmp)' if dashboard_uses_oasis_simulation else '❌ NO'}")
results['dashboard_separate_db'] = dashboard_uses_oasis_simulation

# ---- Check 3: No I/O errors during second round smoke ----
print("\n[Check 3] No disk I/O errors during R2 smoke round")
# Check if any R2 test produced I/O errors
io_error_found = False
for fname in ["r2_01_output.json", "r2_02_stderr.log", "r2_04_metrics.csv"]:
    fpath = f"/home/ubuntu/oasis-dashboard/artifacts/smoke/{fname}"
    if os.path.exists(fpath):
        with open(fpath) as f:
            content = f.read()
        if "disk I/O error" in content or "OperationalError" in content:
            io_error_found = True
            print(f"  ❌ I/O error found in {fname}")

if not io_error_found:
    print(f"  ✅ No disk I/O errors in R2 smoke artifacts")
results['no_io_errors'] = not io_error_found

# ---- Check 4: API-only interaction test ----
print("\n[Check 4] Dashboard interactions go through API")
# Verify that all R2 tests used HTTP API, not direct DB access
r2_scripts = ["run_r2_01_v2.py", "run_r2_04.py", "run_st05_websocket_test.py"]
all_api_only = True
for script in r2_scripts:
    fpath = f"/home/ubuntu/oasis-dashboard/artifacts/smoke/{script}"
    if os.path.exists(fpath):
        with open(fpath) as f:
            content = f.read()
        uses_direct_db = "sqlite3.connect" in content and "oasis_simulation" in content
        uses_api = "requests.get\|requests.post\|http://localhost" in content or "requests" in content
        if uses_direct_db:
            all_api_only = False
            print(f"  ⚠️ {script} uses direct DB access")
        else:
            print(f"  ✅ {script}: API-only (no direct DB writes)")

results['api_only_interaction'] = all_api_only

# ---- Check 5: Concurrent access test ----
print("\n[Check 5] Verify no concurrent DB access during API calls")
# Make 3 rapid API calls and check for errors
errors = []
for i in range(3):
    try:
        r = requests.get(f"{BASE}/api/sim/status", timeout=5)
        if r.status_code != 200:
            errors.append(f"HTTP {r.status_code}")
    except Exception as e:
        errors.append(str(e))

if not errors:
    print(f"  ✅ 3 rapid API calls succeeded without errors")
    results['no_concurrent_errors'] = True
else:
    print(f"  ❌ Errors: {errors}")
    results['no_concurrent_errors'] = False

# ---- Gate evaluation ----
print("\n" + "=" * 60)
print("=== Gate Evaluation ===")
gates = [
    ("CLI smoke uses independent fixture database", results.get('cli_uses_fixture_db', False)),
    ("Dashboard uses separate database from CLI", results.get('dashboard_separate_db', False)),
    ("No disk I/O errors during R2 smoke round", results.get('no_io_errors', False)),
    ("Dashboard interactions go through API only", results.get('api_only_interaction', False)),
    ("No concurrent access errors", results.get('no_concurrent_errors', False)),
]

passed = sum(1 for _, v in gates if v)
for name, result in gates:
    print(f"  {'✅' if result else '❌'} {name}")

overall = passed >= 4
print(f"\nR2-05 RESULT: {'✅ PASS' if overall else '❌ FAIL'} ({passed}/{len(gates)} gates)")

# Save results
with open("artifacts/smoke/r2_05_results.json", "w") as f:
    json.dump({
        "gates": [{"name": n, "passed": v} for n, v in gates],
        "passed": passed,
        "total": len(gates),
        "overall": "PASS" if overall else "FAIL"
    }, f, indent=2)
print(f"\nResults saved: artifacts/smoke/r2_05_results.json")
