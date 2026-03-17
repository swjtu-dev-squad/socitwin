#!/usr/bin/env bash
# R5 可复现实验模板一键运行脚本
# 用法：bash scripts/run_r5_template.sh
# 可选环境变量：
#   RECOMMENDERS  推荐器列表，逗号分隔（默认：TIKTOK,XIAOHONGSHU）
#   STEPS         仿真步数（默认：15）
#   SEED          随机种子（默认：42）
#   DATASET       数据集 JSON 路径（默认：artifacts/r5/dataset_demo_reddit.json）
#   OUTPUT_DIR    结果输出目录（默认：artifacts/experiments/exp_demo_tiktok_vs_xhs）

set -e

# 默认参数
RECOMMENDERS="${RECOMMENDERS:-TIKTOK,XIAOHONGSHU}"
STEPS="${STEPS:-15}"
SEED="${SEED:-42}"
DATASET="${DATASET:-artifacts/r5/dataset_demo_reddit.json}"
OUTPUT_DIR="${OUTPUT_DIR:-artifacts/experiments/exp_demo_tiktok_vs_xhs}"

# 切换到项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "============================================================"
echo "  OASIS Dashboard R5 可复现实验模板"
echo "============================================================"
echo "  推荐器：$RECOMMENDERS"
echo "  步数：$STEPS"
echo "  随机种子：$SEED"
echo "  数据集：$DATASET"
echo "  输出目录：$OUTPUT_DIR"
echo "============================================================"

# 检查数据集文件
if [ ! -f "$DATASET" ]; then
    echo "错误：数据集文件不存在：$DATASET"
    echo "请确保 artifacts/r5/dataset_demo_reddit.json 存在"
    exit 1
fi

# 运行实验
python3.11 - <<PYTHON_SCRIPT
import sys, json
from pathlib import Path

sys.path.insert(0, '.')

from oasis_dashboard.experiment_runner import ExperimentConfig, run_experiment
from oasis_dashboard.compare_analyzer import generate_compare_charts, generate_compare_report_md, generate_compare_json

recommenders = "${RECOMMENDERS}".split(",")
steps = int("${STEPS}")
seed = int("${SEED}")
dataset_path = Path("${DATASET}")
output_dir = Path("${OUTPUT_DIR}")

print(f"\n[1/4] 加载数据集：{dataset_path}")
config = ExperimentConfig(
    name=output_dir.name,
    dataset_id=dataset_path.stem,
    platform="REDDIT",
    recommenders=recommenders,
    steps=steps,
    seed=seed,
    agent_count=10,
)

print(f"[2/4] 运行实验（{len(recommenders)} 个推荐器 × {steps} 步）...")
result = run_experiment(config, dataset_path, output_dir=output_dir)
print(f"  实验 ID：{result.experiment_id}")

print(f"[3/4] 生成对比图表...")
result_json = output_dir / "result.json"
charts = generate_compare_charts(result_json, output_dir)
print(f"  生成 {len(charts)} 张图表")

print(f"[4/4] 生成对比报告...")
generate_compare_json(result_json, output_dir / "compare_detail.json")
report = generate_compare_report_md(result_json, chart_dir=output_dir)
with open(output_dir / "compare.md", "w", encoding="utf-8") as f:
    f.write(report)

print(f"\n============================================================")
print(f"  实验完成！结果保存至：{output_dir}")
print(f"============================================================")
print(f"  核心指标汇总：")
for run in result.runs:
    m = run.metrics
    print(f"  [{run.recommender}] 极化={m['polarization_final']:.4f}  "
          f"羊群={m['herd_index_final']:.4f}  速度={m['velocity_avg']:.4f}")
print(f"\n  查看报告：{output_dir}/compare.md")
PYTHON_SCRIPT

echo ""
echo "完成！"
