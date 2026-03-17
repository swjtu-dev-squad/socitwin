"""
R5-01 验证脚本：推荐策略 × 数据集 对比实验最小闭环

Gate 清单：
  G1: 可选择导入数据集并运行实验
  G2: 可在至少 2 种推荐器间做比较
  G3: 输出统一格式实验结果
  G4: 核心指标至少 4 项可比较
  G5: 结果可复现（固定 seed）
  G6: 有最小对比报告
"""

import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from oasis_dashboard.experiment_runner import (
    ExperimentConfig,
    run_experiment,
    generate_compare_report,
)

DATASET_PATH = Path(__file__).parent / "dataset_demo_reddit.json"
OUTPUT_DIR = Path(__file__).parent / "exp_r5_01_tiktok_vs_xhs"
OUTPUT_DIR_B = Path(__file__).parent / "exp_r5_01_repro"

results = {}

print("=" * 60)
print("R5-01 验证：推荐策略 × 数据集 对比实验最小闭环")
print("=" * 60)

# -----------------------------------------------------------------------
# G1: 可选择导入数据集并运行实验
# -----------------------------------------------------------------------
print("\n[G1] 数据集加载与实验运行...")
try:
    config = ExperimentConfig(
        name="exp_demo_tiktok_vs_xhs",
        dataset_id="dataset_demo_reddit",
        platform="REDDIT",
        recommenders=["TIKTOK", "XIAOHONGSHU", "PINTEREST"],
        steps=15,
        seed=42,
        agent_count=10,
    )
    result = run_experiment(config, DATASET_PATH, output_dir=OUTPUT_DIR)
    assert result is not None, "run_experiment 返回 None"
    assert len(result.runs) == 3, f"期望 3 个 run，实际 {len(result.runs)}"
    results["G1"] = "PASS"
    print(f"  PASS: 实验 ID={result.experiment_id}, runs={len(result.runs)}")
except Exception as e:
    results["G1"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")
    result = None

# -----------------------------------------------------------------------
# G2: 可在至少 2 种推荐器间做比较
# -----------------------------------------------------------------------
print("\n[G2] 推荐器对比（至少 2 种）...")
try:
    assert result is not None, "前置 G1 失败"
    rec_names = [r.recommender for r in result.runs]
    assert len(set(rec_names)) >= 2, f"推荐器种类不足 2：{rec_names}"
    results["G2"] = "PASS"
    print(f"  PASS: 推荐器列表={rec_names}")
except Exception as e:
    results["G2"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G3: 输出统一格式实验结果
# -----------------------------------------------------------------------
print("\n[G3] 结果格式验证...")
try:
    assert result is not None, "前置 G1 失败"
    result_json_path = OUTPUT_DIR / "result.json"
    assert result_json_path.exists(), "result.json 不存在"
    with open(result_json_path) as f:
        data = json.load(f)
    assert "experimentId" in data, "缺少 experimentId"
    assert "config" in data, "缺少 config"
    assert "runs" in data, "缺少 runs"
    for run in data["runs"]:
        assert "recommender" in run, "run 缺少 recommender"
        assert "metrics" in run, "run 缺少 metrics"
        assert "stepsTrace" in run, "run 缺少 stepsTrace"
    results["G3"] = "PASS"
    print(f"  PASS: result.json 结构完整，runs={len(data['runs'])}")
except Exception as e:
    results["G3"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G4: 核心指标至少 4 项可比较
# -----------------------------------------------------------------------
print("\n[G4] 核心指标数量验证...")
try:
    assert result is not None, "前置 G1 失败"
    required_metrics = ["polarization_final", "herd_index_final", "velocity_avg",
                        "total_posts", "unique_active_agents"]
    for run in result.runs:
        present = [m for m in required_metrics if m in run.metrics]
        assert len(present) >= 4, f"{run.recommender} 指标不足 4 项：{present}"
    results["G4"] = "PASS"
    print(f"  PASS: 每个 run 均有 {len(required_metrics)} 项核心指标")
    # 打印指标对比
    print(f"\n  {'推荐器':<15} {'极化':<10} {'羊群':<10} {'速度':<10} {'帖子数':<10} {'活跃Agent':<10}")
    for run in result.runs:
        m = run.metrics
        print(f"  {run.recommender:<15} {m['polarization_final']:<10.4f} "
              f"{m['herd_index_final']:<10.4f} {m['velocity_avg']:<10.4f} "
              f"{m['total_posts']:<10} {m['unique_active_agents']:<10}")
except Exception as e:
    results["G4"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G5: 结果可复现（固定 seed）
# -----------------------------------------------------------------------
print("\n[G5] 可复现性验证（固定 seed=42，重复运行）...")
try:
    result2 = run_experiment(config, DATASET_PATH, output_dir=OUTPUT_DIR_B)
    for r1, r2 in zip(result.runs, result2.runs):
        assert r1.recommender == r2.recommender, "推荐器顺序不一致"
        pol1 = r1.metrics["polarization_final"]
        pol2 = r2.metrics["polarization_final"]
        assert abs(pol1 - pol2) < 1e-9, (
            f"{r1.recommender}: 极化值不一致 {pol1} vs {pol2}"
        )
    results["G5"] = "PASS"
    print(f"  PASS: 两次运行结果完全一致（seed=42）")
except Exception as e:
    results["G5"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G6: 有最小对比报告
# -----------------------------------------------------------------------
print("\n[G6] 对比报告生成...")
try:
    assert result is not None, "前置 G1 失败"
    report = generate_compare_report(result)
    assert len(report) > 200, "报告内容过短"
    assert "极化" in report or "polarization" in report.lower(), "报告缺少极化分析"
    assert "羊群" in report or "herd" in report.lower(), "报告缺少羊群分析"
    # 保存报告
    report_path = OUTPUT_DIR / "compare.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    # 同时保存到 r5 根目录
    with open(Path(__file__).parent / "r5_01_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    results["G6"] = "PASS"
    print(f"  PASS: 报告已生成，长度={len(report)} 字符")
    print(f"  保存至: {report_path}")
except Exception as e:
    results["G6"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# 汇总
# -----------------------------------------------------------------------
print("\n" + "=" * 60)
print("Gate 汇总")
print("=" * 60)
passed = 0
failed = 0
for gate, status in results.items():
    icon = "✅" if status == "PASS" else "❌"
    print(f"  {icon} {gate}: {status}")
    if status == "PASS":
        passed += 1
    else:
        failed += 1

print(f"\n总计：{passed} PASS / {failed} FAIL / {passed + failed} 总计")

# 保存 gate 结果
gate_path = Path(__file__).parent / "r5_01_gate_results.json"
with open(gate_path, "w", encoding="utf-8") as f:
    json.dump({
        "task": "R5-01",
        "gates": results,
        "summary": {"passed": passed, "failed": failed, "total": passed + failed},
    }, f, indent=2, ensure_ascii=False)
print(f"\nGate 结果已保存至: {gate_path}")

# 保存主要实验结果到 r5_01_experiment_result.json
if result is not None:
    exp_result_path = Path(__file__).parent / "r5_01_experiment_result.json"
    with open(exp_result_path, "w", encoding="utf-8") as f:
        json.dump({
            "experimentId": result.experiment_id,
            "createdAt": result.created_at,
            "config": {
                "name": result.config.name,
                "datasetId": result.config.dataset_id,
                "platform": result.config.platform,
                "recommenders": result.config.recommenders,
                "steps": result.config.steps,
                "seed": result.config.seed,
            },
            "runs": [
                {
                    "recommender": run.recommender,
                    "metrics": run.metrics,
                }
                for run in result.runs
            ],
        }, f, indent=2, ensure_ascii=False)
    print(f"实验结果已保存至: {exp_result_path}")

sys.exit(0 if failed == 0 else 1)
