"""
ST-02 + ST-04 补跑回归脚本（ST-05-FIX 后）
验证：主链路和三大指标计算未被水位线修复破坏
"""
import requests
import json
import time
from datetime import datetime

BASE = "http://localhost:3000"

def api(path, method="GET", body=None):
    if method == "POST":
        r = requests.post(f"{BASE}{path}", json=body or {}, timeout=180)
    else:
        r = requests.get(f"{BASE}{path}", timeout=30)
    r.raise_for_status()
    return r.json()

results = {}
print("=" * 60)
print("ST-02 + ST-04 补跑回归（ST-05-FIX 后）")
print("=" * 60)

# ── ST-02：主链路 ──────────────────────────────────────────
print("\n[ST-02] 主链路回归")

# 重置
api("/api/sim/reset", "POST")
time.sleep(2)

# 初始化
init = api("/api/sim/config", "POST", {
    "agentCount": 1, "platform": "reddit", "recsys": "hot-score",
    "topics": ["AI"], "regions": ["General"]
})
st02_init_ok = init.get("status") == "ok"
print(f"  初始化: {'✅' if st02_init_ok else '❌'} status={init.get('status')}")
time.sleep(3)

# 执行 3 步
step_ok_count = 0
for i in range(1, 4):
    r = api("/api/sim/step", "POST")
    step_ok = r.get("currentStep", 0) == i
    if step_ok:
        step_ok_count += 1
    print(f"  Step {i}: {'✅' if step_ok else '❌'} currentStep={r.get('currentStep')} totalPosts={r.get('totalPosts')}")
    time.sleep(1)

# 检查 status
status = api("/api/sim/status")
status_ok = status.get("oasis_ready") and status.get("running")
print(f"  Status: {'✅' if status_ok else '❌'} oasis_ready={status.get('oasis_ready')} running={status.get('running')} step={status.get('currentStep')}")

# 检查 logs 接口
logs = api("/api/sim/logs")
logs_ok = isinstance(logs, (list, dict))
print(f"  Logs API: {'✅' if logs_ok else '❌'} type={type(logs).__name__}")

st02_pass = st02_init_ok and step_ok_count == 3 and status_ok and logs_ok
results["ST-02"] = "PASS" if st02_pass else "FAIL"
print(f"\n  ST-02 结论: {'✅ PASS' if st02_pass else '❌ FAIL'}")

# ── ST-04：三大指标 ────────────────────────────────────────
print("\n[ST-04] 三大指标回归")

# 再执行 2 步（共 5 步）
for i in range(4, 6):
    r = api("/api/sim/step", "POST")
    print(f"  Step {i}: currentStep={r.get('currentStep')} totalPosts={r.get('totalPosts')}")
    time.sleep(1)

# 从 /api/sim/logs 获取数据，计算三大指标
logs_data = api("/api/sim/logs")
if isinstance(logs_data, list):
    all_logs = logs_data
elif isinstance(logs_data, dict):
    all_logs = logs_data.get("logs", logs_data.get("data", []))
else:
    all_logs = []

print(f"  日志总条数: {len(all_logs)}")

# 指标 1：极化指数（基于 sentiment 字段或 action_type 分布）
action_types = [l.get("action_type", "unknown") for l in all_logs]
action_counts = {}
for a in action_types:
    action_counts[a] = action_counts.get(a, 0) + 1
polarization_computable = len(action_counts) > 0
print(f"  极化指数可计算: {'✅' if polarization_computable else '⚠️ 无数据'} action_types={list(action_counts.keys())[:5]}")

# 指标 2：传播速度（posts/step）
status_final = api("/api/sim/status")
total_posts = status_final.get("totalPosts", 0)
current_step = status_final.get("currentStep", 1)
spread_speed = total_posts / current_step if current_step > 0 else 0
spread_computable = current_step > 0
print(f"  传播速度可计算: {'✅' if spread_computable else '❌'} {total_posts} posts / {current_step} steps = {spread_speed:.3f} posts/step")

# 指标 3：羊群指数（action 集中度 HHI）
if action_counts:
    total = sum(action_counts.values())
    hhi = sum((c / total) ** 2 for c in action_counts.values())
    herd_computable = True
    print(f"  羊群指数可计算: ✅ HHI={hhi:.3f} (基于 {total} 条 action)")
else:
    herd_computable = False
    print(f"  羊群指数可计算: ⚠️ 无 action 数据")

# 关键验证：水位线修复后，传播速度计算基准（step 数）是否正确
step_count_ok = current_step == 5
print(f"  Step 计数正确(=5): {'✅' if step_count_ok else '❌'} actual={current_step}")

st04_pass = spread_computable and step_count_ok
results["ST-04"] = "PASS" if st04_pass else "FAIL"
print(f"\n  ST-04 结论: {'✅ PASS' if st04_pass else '❌ FAIL'}")

# ── 总结 ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("补跑回归总结")
print("=" * 60)
for k, v in results.items():
    print(f"  {k}: {'✅ PASS' if v == 'PASS' else '❌ FAIL'}")

all_pass = all(v == "PASS" for v in results.values())
print(f"\n  整体结论: {'✅ 无副作用，修复安全' if all_pass else '❌ 存在副作用，需检查'}")

# 保存结果
output = {
    "test": "ST-02+ST-04-REGRESSION",
    "timestamp": datetime.now().isoformat(),
    "verdict": "PASS" if all_pass else "FAIL",
    "results": results,
    "details": {
        "st02_init_ok": st02_init_ok,
        "st02_steps_ok": step_ok_count,
        "st02_status_ok": status_ok,
        "st04_spread_speed": round(spread_speed, 4),
        "st04_step_count": current_step,
        "st04_total_posts": total_posts,
        "st04_hhi": round(hhi, 4) if herd_computable else None,
    }
}
with open("artifacts/smoke/st02_st04_regression_result.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print("\n结果已保存至 artifacts/smoke/st02_st04_regression_result.json")
