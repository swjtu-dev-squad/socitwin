"""
R6 综合验证脚本
验证 R6-01（实验运行 API）、R6-02（对比分析）、R6-03（历史归档）的所有 Gate
"""
import sys
import json
import requests
from pathlib import Path

BASE_URL = "http://localhost:3000"
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results = []

def gate(name, condition, detail=""):
    status = PASS if condition else FAIL
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    results.append((name, condition))
    return condition


print("\n" + "="*60)
print("R6-01: Experiment Runner Console")
print("="*60)

# Gate 1: POST /api/experiments/run 存在且返回 success
try:
    r = requests.post(f"{BASE_URL}/api/experiments/run", json={
        "name": "verify_r6_01",
        "datasetId": "demo",
        "recommenders": ["tiktok", "xiaohongshu"],
        "platform": "REDDIT",
        "steps": 5,
        "seed": 42,
        "agentCount": 5,
    }, timeout=60)
    d = r.json()
    gate("POST /api/experiments/run 返回 200", r.status_code == 200, f"status={r.status_code}")
    gate("success=True", d.get("success") is True, str(d.get("success")))
    gate("experimentId 存在", bool(d.get("experimentId")), d.get("experimentId", ""))
    gate("runs 包含 2 个推荐器", len(d.get("runs", [])) == 2, f"runs={len(d.get('runs', []))}")
    runs = d.get("runs", [])
    if runs:
        m0 = runs[0]["metrics"]
        gate("每个 run 包含 polarization_final", "polarization_final" in m0)
        gate("每个 run 包含 herd_index_final", "herd_index_final" in m0)
        gate("每个 run 包含 velocity_avg", "velocity_avg" in m0)
        gate("每个 run 包含 total_posts", "total_posts" in m0)
        gate("polarization_final 在 [0,1]", 0 <= m0["polarization_final"] <= 1, str(m0["polarization_final"]))
        gate("herd_index_final 在 [0,1]", 0 <= m0["herd_index_final"] <= 1, str(m0["herd_index_final"]))
    exp_id = d.get("experimentId")
except Exception as e:
    gate("POST /api/experiments/run 可访问", False, str(e))
    exp_id = None

# Gate: GET /api/experiments/:id/result
if exp_id:
    try:
        r2 = requests.get(f"{BASE_URL}/api/experiments/{exp_id}/result", timeout=10)
        d2 = r2.json()
        gate("GET /api/experiments/:id/result 返回 200", r2.status_code == 200, f"status={r2.status_code}")
        gate("result 包含 runs", len(d2.get("runs", [])) >= 1)
    except Exception as e:
        gate("GET /api/experiments/:id/result 可访问", False, str(e))

# Gate: 缺少 recommenders 时返回 400
try:
    r3 = requests.post(f"{BASE_URL}/api/experiments/run", json={
        "name": "bad_request",
        "datasetId": "demo",
        "recommenders": [],
        "steps": 5,
    }, timeout=10)
    gate("空 recommenders 返回 400", r3.status_code == 400, f"status={r3.status_code}")
except Exception as e:
    gate("空 recommenders 返回 400", False, str(e))


print("\n" + "="*60)
print("R6-02: Compare Panel Frontend")
print("="*60)

# Gate: GET /api/experiments 返回列表
try:
    r4 = requests.get(f"{BASE_URL}/api/experiments", timeout=10)
    d4 = r4.json()
    gate("GET /api/experiments 返回 200", r4.status_code == 200)
    gate("experiments 字段存在", "experiments" in d4)
    exps = d4.get("experiments", [])
    gate("至少有 1 个历史实验", len(exps) >= 1, f"count={len(exps)}")
    if exps:
        e0 = exps[0]
        gate("实验包含 experimentId", "experimentId" in e0)
        gate("实验包含 recommenders", "recommenders" in e0)
        gate("实验包含 summary", "summary" in e0)
except Exception as e:
    gate("GET /api/experiments 可访问", False, str(e))

# Gate: 前端组件文件存在
comp_dir = Path(__file__).parent.parent.parent / "src" / "components"
gate("ExperimentRunnerPanel.tsx 存在", (comp_dir / "ExperimentRunnerPanel.tsx").exists())
gate("ExperimentComparePanel.tsx 存在", (comp_dir / "ExperimentComparePanel.tsx").exists())
gate("ExperimentArchiveTable.tsx 存在", (comp_dir / "ExperimentArchiveTable.tsx").exists())
gate("ExperimentDetailDrawer.tsx 存在", (comp_dir / "ExperimentDetailDrawer.tsx").exists())

# Gate: 页面文件存在
pages_dir = Path(__file__).parent.parent.parent / "src" / "pages"
gate("Experiments.tsx 页面存在", (pages_dir / "Experiments.tsx").exists())

# Gate: App.tsx 包含 /experiments 路由
app_tsx = (Path(__file__).parent.parent.parent / "src" / "App.tsx").read_text()
gate("App.tsx 包含 /experiments 路由", "/experiments" in app_tsx)

# Gate: DashboardLayout.tsx 包含实验控制台导航
layout_tsx = (Path(__file__).parent.parent.parent / "src" / "components" / "DashboardLayout.tsx").read_text()
gate("DashboardLayout.tsx 包含实验控制台", "实验控制台" in layout_tsx)

# Gate: experimentApi.ts 存在
lib_dir = Path(__file__).parent.parent.parent / "src" / "lib"
gate("experimentApi.ts 存在", (lib_dir / "experimentApi.ts").exists())
gate("compareApi.ts 存在", (lib_dir / "compareApi.ts").exists())


print("\n" + "="*60)
print("R6-03: Experiment Archive UI")
print("="*60)

# Gate: 多个实验存在于 artifacts/experiments
exp_dir = Path(__file__).parent.parent.parent / "artifacts" / "experiments"
if exp_dir.exists():
    exp_dirs = [d for d in exp_dir.iterdir() if d.is_dir()]
    gate("artifacts/experiments 目录存在", True)
    gate("至少 2 个实验目录", len(exp_dirs) >= 2, f"count={len(exp_dirs)}")
    # 检查每个实验目录的文件完整性
    complete_count = 0
    for d in exp_dirs[:3]:
        has_result = (d / "result.json").exists()
        has_config = (d / "config.json").exists()
        if has_result and has_config:
            complete_count += 1
    gate("至少 2 个实验有完整 result.json + config.json", complete_count >= 2, f"count={complete_count}")
else:
    gate("artifacts/experiments 目录存在", False)

# Gate: result.json 包含 stepsTrace
try:
    result_files = list(exp_dir.glob("*/result.json"))
    if result_files:
        with open(result_files[0]) as f:
            rd = json.load(f)
        runs = rd.get("runs", [])
        if runs:
            has_trace = "stepsTrace" in runs[0]
            gate("result.json 包含 stepsTrace", has_trace)
            if has_trace:
                trace = runs[0]["stepsTrace"]
                gate("stepsTrace 非空", len(trace) > 0, f"len={len(trace)}")
        else:
            gate("result.json 包含 runs", False)
    else:
        gate("result.json 文件存在", False)
except Exception as e:
    gate("result.json 可解析", False, str(e))

# Gate: 前端构建成功（dist 目录存在）
dist_dir = Path(__file__).parent.parent.parent / "dist"
gate("前端构建产物 dist/ 存在", dist_dir.exists())
if dist_dir.exists():
    gate("dist/index.html 存在", (dist_dir / "index.html").exists())


print("\n" + "="*60)
total = len(results)
passed = sum(1 for _, ok in results if ok)
print(f"总计: {passed}/{total} Gate 通过")
print("="*60)

# 保存结果
output = {
    "total": total,
    "passed": passed,
    "gates": [{"name": n, "passed": ok} for n, ok in results]
}
out_path = Path(__file__).parent / "r6_verify_result.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)
print(f"\n结果已保存到: {out_path}")

sys.exit(0 if passed == total else 1)
