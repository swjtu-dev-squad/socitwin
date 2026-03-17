"""
R5-03 验证脚本：可复现实验模板

Gate 清单：
  G1: 有示例数据集（JSON + CSV）
  G2: 有示例实验配置
  G3: 有可执行步骤或脚本（run_r5_template.sh）
  G4: 有统一结果目录（artifacts/experiments/）
  G5: 按文档可复现（固定 seed 结果稳定）
  G6: 有实验模板文档（docs/experiments/R5-EXPERIMENT-TEMPLATE.md）
  G7: 结果目录包含所有规范文件
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

PROJECT_ROOT = Path(__file__).parent.parent.parent

results = {}

print("=" * 60)
print("R5-03 验证：可复现实验模板")
print("=" * 60)

# -----------------------------------------------------------------------
# G1: 有示例数据集（JSON + CSV）
# -----------------------------------------------------------------------
print("\n[G1] 示例数据集验证...")
try:
    json_ds = PROJECT_ROOT / "artifacts/r5/dataset_demo_reddit.json"
    csv_ds = PROJECT_ROOT / "artifacts/r5/dataset_demo_reddit.csv"
    assert json_ds.exists(), f"JSON 数据集不存在：{json_ds}"
    assert csv_ds.exists(), f"CSV 数据集不存在：{csv_ds}"
    with open(json_ds) as f:
        data = json.load(f)
    assert "agents" in data, "JSON 数据集缺少 agents 字段"
    assert len(data["agents"]) >= 5, f"agents 数量不足 5：{len(data['agents'])}"
    assert "posts" in data, "JSON 数据集缺少 posts 字段"
    # 检查 CSV 行数
    csv_lines = csv_ds.read_text().strip().split("\n")
    assert len(csv_lines) >= 6, f"CSV 行数不足（含表头）：{len(csv_lines)}"
    results["G1"] = "PASS"
    print(f"  PASS: JSON={json_ds.name}（{len(data['agents'])} agents），CSV={csv_ds.name}（{len(csv_lines)-1} 行）")
except Exception as e:
    results["G1"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G2: 有示例实验配置
# -----------------------------------------------------------------------
print("\n[G2] 示例实验配置验证...")
try:
    config_path = PROJECT_ROOT / "artifacts/experiments/exp_demo_tiktok_vs_xhs/config.json"
    assert config_path.exists(), f"config.json 不存在：{config_path}"
    with open(config_path) as f:
        config = json.load(f)
    required_fields = ["name", "datasetId", "platform", "recommenders", "steps", "seed"]
    for field in required_fields:
        assert field in config, f"config.json 缺少字段：{field}"
    assert len(config["recommenders"]) >= 2, "recommenders 不足 2 个"
    results["G2"] = "PASS"
    print(f"  PASS: config.json 包含所有必要字段，推荐器={config['recommenders']}")
except Exception as e:
    results["G2"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G3: 有可执行步骤或脚本
# -----------------------------------------------------------------------
print("\n[G3] 一键脚本验证...")
try:
    script_path = PROJECT_ROOT / "scripts/run_r5_template.sh"
    assert script_path.exists(), f"脚本不存在：{script_path}"
    assert script_path.stat().st_mode & 0o111, "脚本没有执行权限"
    content = script_path.read_text()
    assert "run_experiment" in content, "脚本未调用 run_experiment"
    assert "generate_compare_charts" in content, "脚本未调用 generate_compare_charts"
    assert "RECOMMENDERS" in content, "脚本未支持 RECOMMENDERS 参数"
    results["G3"] = "PASS"
    print(f"  PASS: {script_path.name} 存在且有执行权限，包含核心调用")
except Exception as e:
    results["G3"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G4: 有统一结果目录
# -----------------------------------------------------------------------
print("\n[G4] 统一结果目录验证...")
try:
    exp_dir = PROJECT_ROOT / "artifacts/experiments/exp_demo_tiktok_vs_xhs"
    assert exp_dir.exists(), f"结果目录不存在：{exp_dir}"
    assert exp_dir.is_dir(), "不是目录"
    files = list(exp_dir.iterdir())
    assert len(files) >= 5, f"结果文件不足 5 个：{len(files)}"
    results["G4"] = "PASS"
    print(f"  PASS: 结果目录存在，包含 {len(files)} 个文件")
    for f in sorted(files):
        print(f"    - {f.name} ({f.stat().st_size} bytes)")
except Exception as e:
    results["G4"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G5: 按文档可复现（固定 seed 结果稳定）
# -----------------------------------------------------------------------
print("\n[G5] 可复现性验证（固定 seed=42，重复运行两次）...")
try:
    from oasis_dashboard.experiment_runner import ExperimentConfig, run_experiment

    config = ExperimentConfig(
        name="repro_test",
        dataset_id="dataset_demo_reddit",
        platform="REDDIT",
        recommenders=["TIKTOK", "XIAOHONGSHU"],
        steps=15,
        seed=42,
        agent_count=10,
    )
    dataset_path = PROJECT_ROOT / "artifacts/r5/dataset_demo_reddit.json"

    r1 = run_experiment(config, dataset_path)
    r2 = run_experiment(config, dataset_path)

    for run1, run2 in zip(r1.runs, r2.runs):
        assert run1.recommender == run2.recommender
        pol1 = run1.metrics["polarization_final"]
        pol2 = run2.metrics["polarization_final"]
        assert abs(pol1 - pol2) < 1e-9, f"{run1.recommender}: 极化值不一致 {pol1} vs {pol2}"

    results["G5"] = "PASS"
    print(f"  PASS: 两次运行结果完全一致（seed=42）")
    for run in r1.runs:
        m = run.metrics
        print(f"    [{run.recommender}] 极化={m['polarization_final']:.4f}  羊群={m['herd_index_final']:.4f}")
except Exception as e:
    results["G5"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G6: 有实验模板文档
# -----------------------------------------------------------------------
print("\n[G6] 实验模板文档验证...")
try:
    doc_path = PROJECT_ROOT / "docs/experiments/R5-EXPERIMENT-TEMPLATE.md"
    assert doc_path.exists(), f"模板文档不存在：{doc_path}"
    content = doc_path.read_text(encoding="utf-8")
    assert len(content) > 1000, f"文档过短：{len(content)} 字符"
    required_sections = ["环境准备", "示例数据集", "运行步骤", "结果目录规范", "输出解释", "常见错误", "可复现性"]
    for section in required_sections:
        assert section in content, f"文档缺少章节：{section}"
    results["G6"] = "PASS"
    print(f"  PASS: 模板文档存在，{len(content)} 字符，包含所有必要章节")
except Exception as e:
    results["G6"] = f"FAIL: {e}"
    print(f"  FAIL: {e}")

# -----------------------------------------------------------------------
# G7: 结果目录包含所有规范文件
# -----------------------------------------------------------------------
print("\n[G7] 结果目录规范文件验证...")
try:
    exp_dir = PROJECT_ROOT / "artifacts/experiments/exp_demo_tiktok_vs_xhs"
    required_files = [
        "config.json",
        "result.json",
        "metrics.csv",
        "compare.md",
        "compare_polarization.png",
        "compare_herd.png",
        "compare_velocity.png",
        "compare_radar.png",
    ]
    missing = []
    for fname in required_files:
        fpath = exp_dir / fname
        if not fpath.exists():
            missing.append(fname)
        elif fpath.stat().st_size < 100:
            missing.append(f"{fname}（文件过小）")
    assert not missing, f"缺少规范文件：{missing}"
    results["G7"] = "PASS"
    print(f"  PASS: 所有 {len(required_files)} 个规范文件均存在且非空")
except Exception as e:
    results["G7"] = f"FAIL: {e}"
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
gate_path = Path(__file__).parent / "r5_03_gate_results.json"
with open(gate_path, "w", encoding="utf-8") as f:
    json.dump({
        "task": "R5-03",
        "gates": results,
        "summary": {"passed": passed, "failed": failed, "total": passed + failed},
    }, f, indent=2, ensure_ascii=False)
print(f"\nGate 结果已保存至: {gate_path}")

# 生成复现运行记录
repro_run_path = Path(__file__).parent / "r5_03_repro_run.md"
with open(repro_run_path, "w", encoding="utf-8") as f:
    f.write("# R5-03 复现运行记录\n\n")
    f.write(f"**运行时间**：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write("## Gate 验证结果\n\n")
    f.write("| Gate | 状态 |\n|---|---|\n")
    for gate, status in results.items():
        icon = "✅" if status == "PASS" else "❌"
        f.write(f"| {gate} | {icon} {status} |\n")
    f.write(f"\n**总计**：{passed} PASS / {failed} FAIL\n\n")
    f.write("## 复现步骤\n\n")
    f.write("```bash\n")
    f.write("# 在项目根目录执行\n")
    f.write("bash scripts/run_r5_template.sh\n")
    f.write("```\n\n")
    f.write("## 结果目录\n\n")
    f.write("```\n")
    exp_dir = PROJECT_ROOT / "artifacts/experiments/exp_demo_tiktok_vs_xhs"
    if exp_dir.exists():
        for fpath in sorted(exp_dir.iterdir()):
            f.write(f"artifacts/experiments/exp_demo_tiktok_vs_xhs/{fpath.name}\n")
    f.write("```\n")

print(f"复现运行记录已保存至: {repro_run_path}")

sys.exit(0 if failed == 0 else 1)
