"""
R4-02 Custom Dataset Import Gate Verification Script
"""
import requests
import json
import os
import sys
import tempfile
import subprocess

BASE_URL = "http://localhost:3000"
ARTIFACTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(ARTIFACTS_DIR))

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
print("R4-02 Custom Dataset Import Gate Verification")
print("=" * 60)

# ---- Prepare test fixtures ----
VALID_JSON = json.dumps({
    "users": [
        {"username": "alice", "realname": "Alice Smith", "bio": "Tech enthusiast", "age": 28, "gender": "F", "country": "US"},
        {"username": "bob", "realname": "Bob Jones", "bio": "Sports fan", "age": 32, "gender": "M", "country": "UK"},
        {"username": "carol", "realname": "Carol White", "bio": "Artist", "age": 25, "gender": "F", "country": "DE"},
    ],
    "relationships": [
        {"source": "alice", "target": "bob", "type": "follow"},
        {"source": "bob", "target": "carol", "type": "follow"},
    ],
    "posts": [
        {"username": "alice", "content": "Hello world! First post."},
        {"username": "bob", "content": "Loving the new platform!"},
    ]
})

INVALID_JSON = json.dumps({
    "users": [
        {"realname": "No Username User"},  # missing username
    ]
})

VALID_CSV = """username,realname,bio,age,gender,country
dave,Dave Brown,Developer,30,M,CA
eve,Eve Davis,Designer,27,F,AU
frank,Frank Miller,Manager,35,M,FR
"""

# Gate 1: validate endpoint - valid JSON
print("\n[Gate 1] /api/dataset/validate accepts valid JSON")
try:
    files = {"file": ("test_dataset.json", VALID_JSON.encode(), "application/json")}
    r = requests.post(f"{BASE_URL}/api/dataset/validate", files=files, timeout=10)
    data = r.json()
    gate("validate API available", r.status_code == 200, f"HTTP {r.status_code}")
    gate("valid JSON accepted", data.get("status") == "valid", f"status={data.get('status')}, errors={data.get('errors', [])}")
    gate("stats returned", "stats" in data, f"stats={data.get('stats')}")
    gate("preview returned", "preview" in data, f"preview keys={list(data.get('preview', {}).keys())}")
    stats = data.get("stats", {})
    gate("user count correct", stats.get("users") == 3, f"users={stats.get('users')}")
    gate("relationship count correct", stats.get("relationships") == 2, f"relationships={stats.get('relationships')}")
    gate("post count correct", stats.get("posts") == 2, f"posts={stats.get('posts')}")
    # Save sample
    with open(os.path.join(ARTIFACTS_DIR, "r4_02_validate_result.json"), "w") as f:
        json.dump(data, f, indent=2)
except Exception as e:
    gate("validate API available", False, str(e))
    for g in ["valid JSON accepted", "stats returned", "preview returned", "user count correct", "relationship count correct", "post count correct"]:
        gate(g, False, "API failed")

# Gate 2: validate endpoint - invalid JSON returns errors
print("\n[Gate 2] /api/dataset/validate rejects invalid JSON with errors")
try:
    files = {"file": ("bad_dataset.json", INVALID_JSON.encode(), "application/json")}
    r = requests.post(f"{BASE_URL}/api/dataset/validate", files=files, timeout=10)
    data = r.json()
    gate("invalid JSON rejected", data.get("status") == "invalid", f"status={data.get('status')}")
    gate("errors list non-empty", len(data.get("errors", [])) > 0, f"errors={data.get('errors', [])}")
except Exception as e:
    gate("invalid JSON rejected", False, str(e))
    gate("errors list non-empty", False, "API failed")

# Gate 3: validate endpoint - CSV file
print("\n[Gate 3] /api/dataset/validate accepts CSV file")
try:
    files = {"file": ("users.csv", VALID_CSV.encode(), "text/csv")}
    r = requests.post(f"{BASE_URL}/api/dataset/validate", files=files, timeout=10)
    data = r.json()
    gate("CSV accepted", r.status_code == 200, f"HTTP {r.status_code}")
    gate("CSV parsed correctly", data.get("status") == "valid", f"status={data.get('status')}, errors={data.get('errors', [])}")
    gate("CSV user count", data.get("stats", {}).get("users") == 3, f"users={data.get('stats', {}).get('users')}")
    gate("format=csv returned", data.get("format") == "csv", f"format={data.get('format')}")
except Exception as e:
    gate("CSV accepted", False, str(e))
    for g in ["CSV parsed correctly", "CSV user count", "format=csv returned"]:
        gate(g, False, "API failed")

# Gate 4: import endpoint - valid JSON
print("\n[Gate 4] /api/dataset/import imports valid JSON and returns agentConfig")
try:
    files = {"file": ("test_dataset.json", VALID_JSON.encode(), "application/json")}
    r = requests.post(f"{BASE_URL}/api/dataset/import", files=files, timeout=10)
    data = r.json()
    gate("import API available", r.status_code == 200, f"HTTP {r.status_code}")
    gate("import success", data.get("status") == "success", f"status={data.get('status')}, message={data.get('message')}")
    gate("agentConfig returned", "agentConfig" in data, f"agentConfig length={len(data.get('agentConfig', []))}")
    gate("analytics returned", "analytics" in data, f"analytics={data.get('analytics')}")
    agent_config = data.get("agentConfig", [])
    gate("agentConfig has user_name", all("user_name" in a for a in agent_config), f"first agent keys={list(agent_config[0].keys()) if agent_config else []}")
    # Save result
    with open(os.path.join(ARTIFACTS_DIR, "r4_02_import_result.json"), "w") as f:
        json.dump(data, f, indent=2)
except Exception as e:
    gate("import API available", False, str(e))
    for g in ["import success", "agentConfig returned", "analytics returned", "agentConfig has user_name"]:
        gate(g, False, "API failed")

# Gate 5: import endpoint - invalid JSON returns error
print("\n[Gate 5] /api/dataset/import rejects invalid JSON")
try:
    files = {"file": ("bad_dataset.json", INVALID_JSON.encode(), "application/json")}
    r = requests.post(f"{BASE_URL}/api/dataset/import", files=files, timeout=10)
    data = r.json()
    gate("invalid import rejected", r.status_code == 400, f"HTTP {r.status_code}")
    gate("error message returned", data.get("status") == "error", f"status={data.get('status')}")
except Exception as e:
    gate("invalid import rejected", False, str(e))
    gate("error message returned", False, "API failed")

# Gate 6: Frontend component exists
print("\n[Gate 6] DatasetImport component exists and is integrated")
comp_path = os.path.join(PROJECT_DIR, "src", "components", "DatasetImport.tsx")
gate("DatasetImport.tsx exists", os.path.exists(comp_path), comp_path)
if os.path.exists(comp_path):
    with open(comp_path) as f:
        content = f.read()
    gate("drag-drop upload", "onDrop" in content, "drag-and-drop handler present")
    gate("validation display", "ValidationResult" in content, "validation result interface")
    gate("preview table", "preview" in content, "preview table rendering")

settings_path = os.path.join(PROJECT_DIR, "src", "pages", "Settings.tsx")
if os.path.exists(settings_path):
    with open(settings_path) as f:
        settings_content = f.read()
    gate("DatasetImport in Settings", "DatasetImport" in settings_content, "component integrated in Settings page")

# Gate 7: TypeScript compiles
print("\n[Gate 7] TypeScript compiles without errors")
result = subprocess.run(["npx", "tsc", "--noEmit"], capture_output=True, text=True, cwd=PROJECT_DIR)
gate("TypeScript compilation passes", result.returncode == 0, result.stderr[:200] if result.stderr else "clean")

# Summary
print("\n" + "=" * 60)
passed = sum(1 for v in results.values() if v["status"] == "PASS")
total = len(results)
print(f"R4-02 Gates: {passed}/{total} PASS")
print("=" * 60)

report = {
    "task": "R4-02",
    "gates": results,
    "summary": {"passed": passed, "total": total, "status": "PASS" if passed == total else "FAIL"}
}
with open(os.path.join(ARTIFACTS_DIR, "r4_02_gate_results.json"), "w") as f:
    json.dump(report, f, indent=2)
print(f"\nSaved gate results to r4_02_gate_results.json")

sys.exit(0 if passed == total else 1)
