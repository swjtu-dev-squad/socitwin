"""
R5-02: 推荐策略影响下的传播 / 极化 / 羊群对比分析模块

提供：
- CompareResult 数据结构
- compare_runs(): 从实验结果生成对比分析
- generate_compare_charts(): 生成 matplotlib 可视化图表
- generate_compare_json(): 导出 JSON 格式对比结果
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class CompareResult:
    """两个推荐器的对比结果"""
    recommender_a: str
    recommender_b: str
    polarization_delta: list[float]   # 每步极化差值 (A - B)
    herd_delta: list[float]           # 每步羊群差值 (A - B)
    velocity_delta: float             # 平均速度差值 (A - B)
    polarization_final_a: float
    polarization_final_b: float
    herd_final_a: float
    herd_final_b: float
    velocity_avg_a: float
    velocity_avg_b: float
    total_posts_a: int
    total_posts_b: int
    propagation_summary_a: dict[str, Any]
    propagation_summary_b: dict[str, Any]
    conclusion: str


# ---------------------------------------------------------------------------
# 核心分析函数
# ---------------------------------------------------------------------------

def compare_runs(result_json_path: str | Path) -> list[CompareResult]:
    """
    从实验结果 JSON 文件生成所有推荐器两两对比结果。

    Args:
        result_json_path: R5-01 输出的 result.json 路径

    Returns:
        CompareResult 列表（每对推荐器一个）
    """
    with open(result_json_path, encoding="utf-8") as f:
        data = json.load(f)

    runs = data["runs"]
    compare_results = []

    # 两两对比
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            run_a = runs[i]
            run_b = runs[j]

            trace_a = run_a["stepsTrace"]
            trace_b = run_b["stepsTrace"]
            min_steps = min(len(trace_a), len(trace_b))

            # 逐步差值
            pol_delta = [
                round(trace_a[k]["polarization"] - trace_b[k]["polarization"], 4)
                for k in range(min_steps)
            ]
            herd_delta = [
                round(trace_a[k]["herd_index"] - trace_b[k]["herd_index"], 4)
                for k in range(min_steps)
            ]

            m_a = run_a["metrics"]
            m_b = run_b["metrics"]
            vel_delta = round(m_a["velocity_avg"] - m_b["velocity_avg"], 4)

            # 生成结论
            conclusion = _generate_conclusion(
                run_a["recommender"], run_b["recommender"],
                m_a, m_b, pol_delta, herd_delta, vel_delta
            )

            compare_results.append(CompareResult(
                recommender_a=run_a["recommender"],
                recommender_b=run_b["recommender"],
                polarization_delta=pol_delta,
                herd_delta=herd_delta,
                velocity_delta=vel_delta,
                polarization_final_a=m_a["polarization_final"],
                polarization_final_b=m_b["polarization_final"],
                herd_final_a=m_a["herd_index_final"],
                herd_final_b=m_b["herd_index_final"],
                velocity_avg_a=m_a["velocity_avg"],
                velocity_avg_b=m_b["velocity_avg"],
                total_posts_a=m_a["total_posts"],
                total_posts_b=m_b["total_posts"],
                propagation_summary_a=run_a.get("propagationSnapshot", {}).get("metrics", {}),
                propagation_summary_b=run_b.get("propagationSnapshot", {}).get("metrics", {}),
                conclusion=conclusion,
            ))

    return compare_results


def _generate_conclusion(
    name_a: str, name_b: str,
    m_a: dict, m_b: dict,
    pol_delta: list[float],
    herd_delta: list[float],
    vel_delta: float,
) -> str:
    """生成自然语言结论"""
    pol_diff = m_a["polarization_final"] - m_b["polarization_final"]
    herd_diff = m_a["herd_index_final"] - m_b["herd_index_final"]

    parts = []

    if abs(pol_diff) > 0.01:
        higher = name_a if pol_diff > 0 else name_b
        parts.append(f"{higher} 策略下极化程度更高（差值 {abs(pol_diff):.4f}），"
                     f"说明其信息茧房效应更显著")
    else:
        parts.append(f"两种策略极化程度接近（差值 {abs(pol_diff):.4f}）")

    if abs(herd_diff) > 0.01:
        higher = name_a if herd_diff > 0 else name_b
        parts.append(f"{higher} 策略下羊群效应更强（差值 {abs(herd_diff):.4f}），"
                     f"内容集中度更高")
    else:
        parts.append(f"两种策略羊群效应接近（差值 {abs(herd_diff):.4f}）")

    if abs(vel_delta) > 0.01:
        faster = name_a if vel_delta > 0 else name_b
        parts.append(f"{faster} 策略传播速度更快（差值 {abs(vel_delta):.4f}），"
                     f"新鲜内容扩散更迅速")
    else:
        parts.append(f"两种策略传播速度接近（差值 {abs(vel_delta):.4f}）")

    # 判断是否有显著差异
    any_significant = abs(pol_diff) > 0.01 or abs(herd_diff) > 0.01 or abs(vel_delta) > 0.01
    if any_significant:
        parts.append(f"综合来看，{name_a} 与 {name_b} 在社交动力学上存在可观察差异，"
                     f"推荐算法设计对平台生态有实质性影响")
    else:
        parts.append(f"两种策略整体差异较小，建议增加步数或使用更多样化的数据集")

    return "；".join(parts) + "。"


# ---------------------------------------------------------------------------
# 可视化生成
# ---------------------------------------------------------------------------

def generate_compare_charts(
    result_json_path: str | Path,
    output_dir: str | Path,
) -> list[Path]:
    """
    生成对比分析图表（PNG 格式）。

    返回生成的图表文件路径列表。
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker

    with open(result_json_path, encoding="utf-8") as f:
        data = json.load(f)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runs = data["runs"]
    generated = []

    # 颜色映射
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6"]
    rec_colors = {r["recommender"]: colors[i % len(colors)] for i, r in enumerate(runs)}

    # -----------------------------------------------------------------------
    # 图 1：极化曲线对比
    # -----------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    for run in runs:
        steps = [s["step"] for s in run["stepsTrace"]]
        pols = [s["polarization"] for s in run["stepsTrace"]]
        ax.plot(steps, pols, label=run["recommender"],
                color=rec_colors[run["recommender"]], linewidth=2.0, marker="o", markersize=3)
    ax.set_title("Polarization Curve Comparison", fontsize=14, fontweight="bold")
    ax.set_xlabel("Step")
    ax.set_ylabel("Polarization Index")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.3f"))
    plt.tight_layout()
    p1 = output_dir / "compare_polarization.png"
    fig.savefig(p1, dpi=120)
    plt.close(fig)
    generated.append(p1)

    # -----------------------------------------------------------------------
    # 图 2：羊群效应曲线对比
    # -----------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    for run in runs:
        steps = [s["step"] for s in run["stepsTrace"]]
        herds = [s["herd_index"] for s in run["stepsTrace"]]
        ax.plot(steps, herds, label=run["recommender"],
                color=rec_colors[run["recommender"]], linewidth=2.0, marker="s", markersize=3)
    ax.set_title("Herd Effect (HHI) Curve Comparison", fontsize=14, fontweight="bold")
    ax.set_xlabel("Step")
    ax.set_ylabel("Herd Index (HHI)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.3f"))
    plt.tight_layout()
    p2 = output_dir / "compare_herd.png"
    fig.savefig(p2, dpi=120)
    plt.close(fig)
    generated.append(p2)

    # -----------------------------------------------------------------------
    # 图 3：传播速度柱状图对比
    # -----------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 5))
    rec_names = [r["recommender"] for r in runs]
    vel_avgs = [r["metrics"]["velocity_avg"] for r in runs]
    bar_colors = [rec_colors[n] for n in rec_names]
    bars = ax.bar(rec_names, vel_avgs, color=bar_colors, edgecolor="white", linewidth=1.5)
    for bar, val in zip(bars, vel_avgs):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:.4f}", ha="center", va="bottom", fontsize=10)
    ax.set_title("Average Information Velocity Comparison", fontsize=14, fontweight="bold")
    ax.set_xlabel("Recommender")
    ax.set_ylabel("Avg Velocity")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    p3 = output_dir / "compare_velocity.png"
    fig.savefig(p3, dpi=120)
    plt.close(fig)
    generated.append(p3)

    # -----------------------------------------------------------------------
    # 图 4：最终指标雷达图（综合对比）
    # -----------------------------------------------------------------------
    import numpy as np

    categories = ["Polarization", "Herd Index", "Velocity", "Posts/10"]
    n_cat = len(categories)
    angles = np.linspace(0, 2 * np.pi, n_cat, endpoint=False).tolist()
    angles += angles[:1]  # 闭合

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw=dict(polar=True))
    for run in runs:
        m = run["metrics"]
        values = [
            m["polarization_final"],
            m["herd_index_final"],
            m["velocity_avg"],
            min(1.0, m["total_posts"] / 50),  # 归一化到 0-1
        ]
        values += values[:1]
        ax.plot(angles, values, label=run["recommender"],
                color=rec_colors[run["recommender"]], linewidth=2)
        ax.fill(angles, values, alpha=0.1, color=rec_colors[run["recommender"]])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_title("Recommender Impact Radar Chart", fontsize=14, fontweight="bold", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    plt.tight_layout()
    p4 = output_dir / "compare_radar.png"
    fig.savefig(p4, dpi=120, bbox_inches="tight")
    plt.close(fig)
    generated.append(p4)

    return generated


# ---------------------------------------------------------------------------
# JSON 导出
# ---------------------------------------------------------------------------

def generate_compare_json(
    result_json_path: str | Path,
    output_path: str | Path,
) -> dict:
    """生成并保存 JSON 格式对比结果"""
    compare_results = compare_runs(result_json_path)

    output = {
        "source_experiment": str(result_json_path),
        "comparisons": [
            {
                "recommender_a": cr.recommender_a,
                "recommender_b": cr.recommender_b,
                "polarization_delta_final": round(
                    cr.polarization_final_a - cr.polarization_final_b, 4),
                "herd_delta_final": round(cr.herd_final_a - cr.herd_final_b, 4),
                "velocity_delta": cr.velocity_delta,
                "metrics_a": {
                    "polarization_final": cr.polarization_final_a,
                    "herd_index_final": cr.herd_final_a,
                    "velocity_avg": cr.velocity_avg_a,
                    "total_posts": cr.total_posts_a,
                },
                "metrics_b": {
                    "polarization_final": cr.polarization_final_b,
                    "herd_index_final": cr.herd_final_b,
                    "velocity_avg": cr.velocity_avg_b,
                    "total_posts": cr.total_posts_b,
                },
                "propagation_summary_a": cr.propagation_summary_a,
                "propagation_summary_b": cr.propagation_summary_b,
                "conclusion": cr.conclusion,
            }
            for cr in compare_results
        ],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return output


# ---------------------------------------------------------------------------
# Markdown 报告
# ---------------------------------------------------------------------------

def generate_compare_report_md(
    result_json_path: str | Path,
    chart_dir: str | Path | None = None,
) -> str:
    """生成 Markdown 格式的完整对比报告"""
    with open(result_json_path, encoding="utf-8") as f:
        data = json.load(f)

    compare_results = compare_runs(result_json_path)
    runs = data["runs"]

    lines = [
        "# R5-02 推荐策略影响对比分析报告",
        "",
        f"**实验 ID**：`{data.get('experimentId', 'N/A')}`  ",
        f"**数据集**：{data.get('config', {}).get('datasetId', 'N/A')}  ",
        f"**平台**：{data.get('config', {}).get('platform', 'N/A')}  ",
        f"**步数**：{data.get('config', {}).get('steps', 'N/A')}  ",
        "",
        "---",
        "",
        "## 1. 核心指标汇总",
        "",
        "| 推荐器 | 极化值（最终） | 羊群指数（最终） | 平均传播速度 | 总帖子数 |",
        "|---|---|---|---|---|",
    ]

    for run in runs:
        m = run["metrics"]
        lines.append(
            f"| **{run['recommender']}** "
            f"| {m['polarization_final']:.4f} "
            f"| {m['herd_index_final']:.4f} "
            f"| {m['velocity_avg']:.4f} "
            f"| {m['total_posts']} |"
        )

    lines += ["", "---", "", "## 2. 可视化对比"]

    if chart_dir is not None:
        chart_dir = Path(chart_dir)
        for chart_name, title in [
            ("compare_polarization.png", "图 1：极化曲线对比"),
            ("compare_herd.png", "图 2：羊群效应曲线对比"),
            ("compare_velocity.png", "图 3：传播速度柱状图对比"),
            ("compare_radar.png", "图 4：综合指标雷达图"),
        ]:
            lines += [
                "",
                f"**{title}**",
                "",
                f"![{title}]({chart_name})",
                "",
            ]

    lines += ["", "---", "", "## 3. 两两差异分析", ""]

    for cr in compare_results:
        lines += [
            f"### {cr.recommender_a} vs {cr.recommender_b}",
            "",
            f"| 指标 | {cr.recommender_a} | {cr.recommender_b} | 差值 (A-B) |",
            "|---|---|---|---|",
            f"| 极化值（最终） | {cr.polarization_final_a:.4f} | {cr.polarization_final_b:.4f} "
            f"| `{cr.polarization_final_a - cr.polarization_final_b:+.4f}` |",
            f"| 羊群指数（最终） | {cr.herd_final_a:.4f} | {cr.herd_final_b:.4f} "
            f"| `{cr.herd_final_a - cr.herd_final_b:+.4f}` |",
            f"| 平均传播速度 | {cr.velocity_avg_a:.4f} | {cr.velocity_avg_b:.4f} "
            f"| `{cr.velocity_delta:+.4f}` |",
            "",
            f"**结论**：{cr.conclusion}",
            "",
        ]

    lines += [
        "---",
        "",
        "## 4. 综合结论",
        "",
    ]

    # 找出各维度最高/最低
    pol_sorted = sorted(runs, key=lambda r: r["metrics"]["polarization_final"], reverse=True)
    herd_sorted = sorted(runs, key=lambda r: r["metrics"]["herd_index_final"], reverse=True)
    vel_sorted = sorted(runs, key=lambda r: r["metrics"]["velocity_avg"], reverse=True)

    lines += [
        f"在本次实验中，**{pol_sorted[0]['recommender']}** 策略产生了最高的极化效应，"
        f"**{pol_sorted[-1]['recommender']}** 策略极化最低。"
        f"**{herd_sorted[0]['recommender']}** 策略下羊群效应最强，"
        f"**{vel_sorted[0]['recommender']}** 策略下信息传播速度最快。",
        "",
        "上述差异表明，推荐算法的权重设计对社交平台的信息生态具有显著影响：",
        "短期兴趣权重越高，信息茧房效应越强，极化越严重；"
        "社交互动权重越高，内容集中度越高，羊群效应越明显；"
        "新鲜度权重越高，信息传播越迅速。",
        "",
        "这一结论为平台设计者提供了可量化的参考依据，"
        "有助于在推荐效率与信息生态健康之间寻求平衡。",
    ]

    return "\n".join(lines)
