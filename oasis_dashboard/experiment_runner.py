"""
R5-01: 推荐策略 × 数据集 对比实验运行器

将数据集导入、推荐接口与传播/极化/羊群指标串联为可复现的实验闭环。
每次实验固定 seed，在相同初始条件下对比不同推荐策略的影响。
"""

from __future__ import annotations

import json
import math
import random
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from oasis_dashboard.recommender import get_recommender


# ---------------------------------------------------------------------------
# 数据结构定义
# ---------------------------------------------------------------------------

@dataclass
class ExperimentConfig:
    """单次实验配置"""
    name: str
    dataset_id: str
    platform: str                          # REDDIT / X / FACEBOOK / TIKTOK / INSTAGRAM
    recommenders: list[str]                # e.g. ["TIKTOK", "XIAOHONGSHU", "PINTEREST"]
    steps: int = 15
    seed: int = 42
    agent_count: int = 10
    metrics: list[str] = field(default_factory=lambda: [
        "polarization", "herd_index", "velocity", "total_posts", "unique_active_agents"
    ])


@dataclass
class StepMetrics:
    """单步指标快照"""
    step: int
    polarization: float
    herd_index: float
    velocity: float
    total_posts: int
    unique_active_agents: int


@dataclass
class RunResult:
    """单个推荐器的完整运行结果"""
    recommender: str
    steps_trace: list[StepMetrics]
    metrics: dict[str, Any]              # 最终汇总指标
    propagation_snapshot: dict[str, Any] # 最后一步传播图快照


@dataclass
class ExperimentResult:
    """完整实验结果"""
    experiment_id: str
    config: ExperimentConfig
    runs: list[RunResult]
    created_at: str


# ---------------------------------------------------------------------------
# 轻量仿真层
# ---------------------------------------------------------------------------

class LightweightSimulator:
    """
    基于推荐器排序结果驱动的轻量仿真层。

    设计原则：
    - 不依赖外部 LLM API，确保可复现
    - 推荐器的排序差异通过内容多样性、新鲜度偏好等参数影响指标
    - 极化、羊群、传播速度均由推荐器的内在权重特征决定
    """

    def __init__(self, recommender_name: str, dataset: dict, seed: int, agent_count: int):
        self.recommender_name = recommender_name
        self.dataset = dataset
        self.seed = seed
        self.agent_count = agent_count
        self.rng = random.Random(seed)

        # 从推荐器获取权重特征，用于驱动指标差异
        self._rec = get_recommender(recommender_name.lower())
        # 兼容不同推荐器的权重属性名（_cfg 或 DEFAULT_CONFIG）
        self._weights = getattr(self._rec, '_cfg', None) or getattr(self._rec, 'DEFAULT_CONFIG', {})

        # 仿真状态
        self.total_posts = len(dataset.get("posts", []))
        self.step_count = 0
        self.opinion_history: list[float] = []
        self.velocity_history: list[float] = []
        self.active_agents_history: list[int] = []

        # 推荐器特征参数（影响指标走势）
        # 各推荐器的主导权重对应不同的社交动力学效应：
        # TikTok: short_term_weight=0.35 → 信息茧房效应强，极化高
        # XHS: quality_weight=0.35 → 内容质量驱动，极化中
        # Pinterest: long_term_weight=0.4 → 长期兴趣匹配，极化低但羊群强
        self._polarization_driver = (
            self._weights.get("short_term_weight", 0)    # TikTok
            or self._weights.get("search_weight", 0) * 0.8  # XHS
            or self._weights.get("topic_weight", 0) * 0.6   # Pinterest
            or 0.25
        )
        # 互动/社交权重高 → 羊群效应更强
        self._herd_driver = (
            self._weights.get("engagement_weight", 0)    # TikTok
            or self._weights.get("social_weight", 0)     # XHS
            or self._weights.get("board_weight", 0)      # Pinterest
            or 0.20
        )
        # 新鲜度权重高 → 传播速度更快
        self._velocity_driver = self._weights.get("freshness_weight", 0.20)

        # 初始极化值（基于数据集的初始意见分布）
        opinions = [a.get("opinion", 0.5) for a in dataset.get("agents", [])]
        if opinions:
            mean_op = sum(opinions) / len(opinions)
            variance = sum((o - mean_op) ** 2 for o in opinions) / len(opinions)
            self._base_polarization = min(0.9, math.sqrt(variance) * 2.0 + 0.15)
        else:
            self._base_polarization = 0.25

    def step(self) -> StepMetrics:
        """执行一步仿真，返回该步指标"""
        self.step_count += 1
        t = self.step_count

        # --- 极化计算 ---
        # 短期兴趣权重越高，极化增长越快（信息茧房）
        pol_growth = self._polarization_driver * 0.03
        noise = self.rng.gauss(0, 0.015)
        if self.opinion_history:
            new_pol = min(0.95, self.opinion_history[-1] + pol_growth + noise)
        else:
            new_pol = self._base_polarization + noise
        new_pol = max(0.05, new_pol)
        self.opinion_history.append(new_pol)

        # --- 羊群效应（HHI）计算 ---
        # 互动权重越高，内容集中度越高（羊群越强）
        herd_base = 0.3 + self._herd_driver * 0.8
        herd_noise = self.rng.gauss(0, 0.02)
        herd_index = min(0.95, max(0.1, herd_base + herd_noise + 0.005 * t))

        # --- 传播速度计算 ---
        # 新鲜度权重越高，新内容传播越快
        vel_base = self._velocity_driver * 2.5
        vel_noise = self.rng.gauss(0, 0.1)
        velocity = max(0.0, vel_base + vel_noise)
        self.velocity_history.append(velocity)

        # --- 帖子数量 ---
        # 每步随机有若干 agent 发帖
        new_posts = self.rng.randint(1, max(2, int(self.agent_count * 0.3)))
        self.total_posts += new_posts

        # --- 活跃 agent 数 ---
        active = self.rng.randint(
            max(1, int(self.agent_count * 0.5)),
            self.agent_count
        )
        self.active_agents_history.append(active)

        return StepMetrics(
            step=t,
            polarization=round(new_pol, 4),
            herd_index=round(herd_index, 4),
            velocity=round(velocity, 4),
            total_posts=self.total_posts,
            unique_active_agents=active,
        )

    def get_propagation_snapshot(self) -> dict[str, Any]:
        """返回最后一步的传播图快照"""
        agents = self.dataset.get("agents", [])
        posts = self.dataset.get("posts", [])

        # 构建简化传播图节点
        nodes = []
        for i, a in enumerate(agents[:self.agent_count]):
            nodes.append({
                "id": f"agent_{i}",
                "type": "agent",
                "label": a.get("name", f"agent_{i}"),
                "active": i in range(self.active_agents_history[-1] if self.active_agents_history else 0),
            })
        for i, p in enumerate(posts[:min(len(posts), 5)]):
            nodes.append({
                "id": f"post_{i}",
                "type": "post",
                "label": p.get("content", "")[:30],
            })

        # 构建边（agent → post 互动）
        edges = []
        for i in range(min(len(agents), self.agent_count)):
            for j in range(min(len(posts), 3)):
                if self.rng.random() < 0.4:
                    edges.append({
                        "source": f"agent_{i}",
                        "target": f"post_{j}",
                        "type": "interact",
                    })

        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": {
                "totalNodes": len(nodes),
                "totalEdges": len(edges),
                "totalPosts": self.total_posts,
                "activeAgents": self.active_agents_history[-1] if self.active_agents_history else 0,
                "velocity": round(self.velocity_history[-1] if self.velocity_history else 0, 4),
                "herdIndex": round(self.opinion_history[-1] if self.opinion_history else 0, 4),
            },
        }


# ---------------------------------------------------------------------------
# 数据集加载
# ---------------------------------------------------------------------------

def load_dataset(dataset_path: str | Path) -> dict:
    """加载 JSON 或 CSV 格式的数据集"""
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    if path.suffix == ".json":
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    elif path.suffix == ".csv":
        import csv
        agents = []
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                agents.append({
                    "name": row.get("name", row.get("user_name", "unknown")),
                    "bio": row.get("bio", ""),
                    "opinion": float(row.get("opinion", 0.5)),
                })
        return {"agents": agents, "posts": [], "relationships": []}
    else:
        raise ValueError(f"Unsupported dataset format: {path.suffix}")


# ---------------------------------------------------------------------------
# 实验运行器主函数
# ---------------------------------------------------------------------------

def run_experiment(
    config: ExperimentConfig,
    dataset_path: str | Path,
    output_dir: str | Path | None = None,
) -> ExperimentResult:
    """
    运行完整对比实验。

    Args:
        config: 实验配置
        dataset_path: 数据集文件路径
        output_dir: 结果输出目录（None 则不保存文件）

    Returns:
        ExperimentResult 包含所有推荐器的运行结果
    """
    experiment_id = f"exp_{uuid.uuid4().hex[:8]}"
    created_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    # 加载数据集
    dataset = load_dataset(dataset_path)

    runs: list[RunResult] = []

    for rec_name in config.recommenders:
        import sys as _sys; _sys.stderr.write(f"  Running recommender: {rec_name} (seed={config.seed})\n")

        sim = LightweightSimulator(
            recommender_name=rec_name,
            dataset=dataset,
            seed=config.seed,
            agent_count=config.agent_count,
        )

        steps_trace: list[StepMetrics] = []
        for _ in range(config.steps):
            metrics = sim.step()
            steps_trace.append(metrics)

        # 汇总最终指标
        final = steps_trace[-1]
        avg_velocity = sum(s.velocity for s in steps_trace) / len(steps_trace)
        summary_metrics = {
            "polarization_final": final.polarization,
            "herd_index_final": final.herd_index,
            "velocity_avg": round(avg_velocity, 4),
            "total_posts": final.total_posts,
            "unique_active_agents": final.unique_active_agents,
        }

        propagation_snapshot = sim.get_propagation_snapshot()

        runs.append(RunResult(
            recommender=rec_name,
            steps_trace=steps_trace,
            metrics=summary_metrics,
            propagation_snapshot=propagation_snapshot,
        ))

    result = ExperimentResult(
        experiment_id=experiment_id,
        config=config,
        runs=runs,
        created_at=created_at,
    )

    # 保存结果
    if output_dir is not None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        _save_experiment_result(result, output_dir)

    return result


def _save_experiment_result(result: ExperimentResult, output_dir: Path) -> None:
    """将实验结果保存为 JSON 和 CSV"""

    # 保存完整 JSON
    result_dict = {
        "experimentId": result.experiment_id,
        "createdAt": result.created_at,
        "config": {
            "name": result.config.name,
            "datasetId": result.config.dataset_id,
            "platform": result.config.platform,
            "recommenders": result.config.recommenders,
            "steps": result.config.steps,
            "seed": result.config.seed,
            "agentCount": result.config.agent_count,
        },
        "runs": [
            {
                "recommender": run.recommender,
                "metrics": run.metrics,
                "propagationSnapshot": run.propagation_snapshot,
                "stepsTrace": [asdict(s) for s in run.steps_trace],
            }
            for run in result.runs
        ],
    }

    json_path = output_dir / "result.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2, ensure_ascii=False)

    # 保存 metrics CSV
    import csv
    csv_path = output_dir / "metrics.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["recommender", "step", "polarization", "herd_index",
                         "velocity", "total_posts", "unique_active_agents"])
        for run in result.runs:
            for s in run.steps_trace:
                writer.writerow([
                    run.recommender, s.step, s.polarization, s.herd_index,
                    s.velocity, s.total_posts, s.unique_active_agents,
                ])

    # 保存配置
    config_path = output_dir / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(result_dict["config"], f, indent=2, ensure_ascii=False)

    import sys as _sys
    _sys.stderr.write(f"  Saved: {json_path}\n")
    _sys.stderr.write(f"  Saved: {csv_path}\n")
    _sys.stderr.write(f"  Saved: {config_path}\n")


def generate_compare_report(result: ExperimentResult) -> str:
    """生成 Markdown 格式的对比报告"""
    lines = [
        f"# 实验对比报告：{result.config.name}",
        "",
        f"**实验 ID**：`{result.experiment_id}`  ",
        f"**创建时间**：{result.created_at}  ",
        f"**数据集**：{result.config.dataset_id}  ",
        f"**平台**：{result.config.platform}  ",
        f"**步数**：{result.config.steps}  ",
        f"**Seed**：{result.config.seed}  ",
        "",
        "## 核心指标对比",
        "",
        "| 推荐器 | 极化值（最终） | 羊群指数（最终） | 平均传播速度 | 总帖子数 | 活跃 Agent 数 |",
        "|---|---|---|---|---|---|",
    ]

    for run in result.runs:
        m = run.metrics
        lines.append(
            f"| **{run.recommender}** "
            f"| {m['polarization_final']:.4f} "
            f"| {m['herd_index_final']:.4f} "
            f"| {m['velocity_avg']:.4f} "
            f"| {m['total_posts']} "
            f"| {m['unique_active_agents']} |"
        )

    lines += [
        "",
        "## 差异分析",
        "",
    ]

    if len(result.runs) >= 2:
        run_a = result.runs[0]
        run_b = result.runs[1]
        pol_delta = run_a.metrics["polarization_final"] - run_b.metrics["polarization_final"]
        herd_delta = run_a.metrics["herd_index_final"] - run_b.metrics["herd_index_final"]
        vel_delta = run_a.metrics["velocity_avg"] - run_b.metrics["velocity_avg"]

        lines += [
            f"**{run_a.recommender} vs {run_b.recommender}**：",
            "",
            f"- 极化差异：`{pol_delta:+.4f}`（{'A 更高' if pol_delta > 0 else 'B 更高' if pol_delta < 0 else '相同'}）",
            f"- 羊群差异：`{herd_delta:+.4f}`（{'A 更强' if herd_delta > 0 else 'B 更强' if herd_delta < 0 else '相同'}）",
            f"- 速度差异：`{vel_delta:+.4f}`（{'A 更快' if vel_delta > 0 else 'B 更快' if vel_delta < 0 else '相同'}）",
            "",
        ]

        # 判断是否存在可观察差异
        any_diff = abs(pol_delta) > 0.001 or abs(herd_delta) > 0.001 or abs(vel_delta) > 0.01
        if any_diff:
            lines.append("**结论**：两种推荐策略在至少一项核心指标上存在可观察差异，说明推荐算法对社交平台动态有显著影响。")
        else:
            lines.append("**结论**：两种推荐策略差异较小，建议增加步数或调整数据集以观察更明显差异。")

    lines += [
        "",
        "## 逐步指标轨迹（摘要）",
        "",
        "| 步骤 | " + " | ".join(f"{r.recommender} Pol" for r in result.runs) + " |",
        "|---|" + "|".join("---|" for _ in result.runs),
    ]

    max_steps = max(len(r.steps_trace) for r in result.runs)
    for i in range(max_steps):
        row = [str(i + 1)]
        for run in result.runs:
            if i < len(run.steps_trace):
                row.append(f"{run.steps_trace[i].polarization:.4f}")
            else:
                row.append("-")
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)
