"""ST-05 复测（通过 HTTP API，修复后）"""
import requests
import json
import time

BASE = "http://localhost:3000"

def api(path, method="GET", body=None):
    if method == "POST":
        r = requests.post(f"{BASE}{path}", json=body or {}, timeout=180)
    else:
        r = requests.get(f"{BASE}{path}", timeout=30)
    r.raise_for_status()
    return r.json()

print("=== ST-05 复测（通过 HTTP API，修复后） ===")

# 重置
print("[1] 重置...")
api("/api/sim/reset", "POST")
time.sleep(2)

# 初始化
print("[2] 初始化（1 agent, reddit, AI）...")
init = api("/api/sim/config", "POST", {
    "agentCount": 1, "platform": "reddit", "recsys": "hot-score",
    "topics": ["AI"], "regions": ["General"]
})
print(f"    init status: {init.get('status')}")
time.sleep(3)

# 5 步
all_keys = []
step_results = []
for i in range(1, 6):
    print(f"[Step {i}] 执行...")
    t0 = time.time()
    r = api("/api/sim/step", "POST")
    elapsed = time.time() - t0
    new_logs = r.get("new_logs", [])
    if not isinstance(new_logs, list):
        new_logs = []
    keys = [(l.get("agent_id"), l.get("action_type"), l.get("content", "")[:60]) for l in new_logs]
    unique_keys = list(dict.fromkeys(keys))
    dup = len(keys) - len(unique_keys)
    step_results.append({"step": i, "count": len(new_logs), "dup": dup, "elapsed": round(elapsed, 1)})
    all_keys.extend(keys)
    print(f"    new_logs={len(new_logs)} dup={dup} time={elapsed:.1f}s")

# 汇总
global_dup = len(all_keys) - len(list(dict.fromkeys(all_keys)))
dup_rate = global_dup / len(all_keys) * 100 if all_keys else 0.0
per_step_pass = all(s["dup"] == 0 for s in step_results)
overall = "PASS" if (per_step_pass and global_dup == 0) else "FAIL"

print()
print("=== 汇总 ===")
print(f"总 new_logs: {len(all_keys)}")
print(f"全局重复: {global_dup}  重复率: {dup_rate:.1f}%")
print(f"每步无重复: {'✅' if per_step_pass else '❌'}")
print(f"全局无重复: {'✅' if global_dup == 0 else '❌'}")
print(f"ST-05 复测结论: {'✅ PASS' if overall == 'PASS' else '❌ FAIL'}")

result = {
    "test": "ST-05-RETEST",
    "verdict": overall,
    "global_duplicate_rate": round(dup_rate, 2),
    "total_logs": len(all_keys),
    "global_duplicates": global_dup,
    "steps": step_results,
}
with open("artifacts/smoke/st05_retest_result.json", "w") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print("结果已保存至 artifacts/smoke/st05_retest_result.json")
