# R5 可复现实验模板

本文档为 OASIS Dashboard 推荐策略对比实验提供标准化的可复现流程，任何团队成员均可按此文档独立完成一次完整实验，无需依赖口头说明。

---

## 目录

1. [环境准备](#1-环境准备)
2. [示例数据集](#2-示例数据集)
3. [示例实验配置](#3-示例实验配置)
4. [运行步骤](#4-运行步骤)
5. [结果目录规范](#5-结果目录规范)
6. [输出解释](#6-输出解释)
7. [常见错误](#7-常见错误)
8. [可复现性说明](#8-可复现性说明)

---

## 1. 环境准备

### (1) 依赖安装

```bash
# 在项目根目录执行
pip install camel-ai colorama matplotlib numpy
```

### (2) 验证模块可用

```bash
python3 -c "from oasis_dashboard.experiment_runner import run_experiment; print('OK')"
python3 -c "from oasis_dashboard.recommender import get_recommender; print('OK')"
python3 -c "from oasis_dashboard.compare_analyzer import compare_runs; print('OK')"
```

---

## 2. 示例数据集

项目提供两种格式的示例数据集，位于 `artifacts/r5/`：

| 文件名 | 格式 | 描述 |
|---|---|---|
| `dataset_demo_reddit.json` | JSON | 10 名 Agent，5 篇初始帖子，Reddit 风格 |
| `dataset_demo_reddit.csv` | CSV | 同上，CSV 格式，适用于数据导入 API |

### JSON 数据集结构

```json
{
  "metadata": {
    "name": "dataset_demo_reddit",
    "platform": "REDDIT",
    "version": "1.0"
  },
  "agents": [
    {
      "user_name": "alice_tech",
      "name": "Alice Chen",
      "bio": "Software engineer interested in AI",
      "opinion": 0.65,
      "age": 28,
      "interests": ["technology", "AI"]
    }
  ],
  "posts": [...],
  "relationships": [...]
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `user_name` | string | Agent 唯一标识符 |
| `opinion` | float [0,1] | 初始意见倾向（0=极左，1=极右） |
| `interests` | list[str] | 兴趣标签，影响推荐器评分 |
| `bio` | string | Agent 描述，影响 LLM 行为 |

---

## 3. 示例实验配置

标准实验配置文件 `config.json`：

```json
{
  "name": "exp_demo_tiktok_vs_xhs",
  "datasetId": "dataset_demo_reddit",
  "platform": "REDDIT",
  "recommenders": ["TIKTOK", "XIAOHONGSHU"],
  "steps": 15,
  "seed": 42,
  "agentCount": 10
}
```

**参数说明：**

| 参数 | 类型 | 说明 |
|---|---|---|
| `name` | string | 实验名称，用于结果目录命名 |
| `datasetId` | string | 数据集标识符 |
| `platform` | string | 平台类型：`REDDIT` / `TWITTER` / `TIKTOK` |
| `recommenders` | list[str] | 对比推荐器列表：`TIKTOK` / `XIAOHONGSHU` / `PINTEREST` |
| `steps` | int | 仿真步数（建议 10-20 步） |
| `seed` | int | 随机种子，固定后结果可复现 |
| `agentCount` | int | 参与仿真的 Agent 数量 |

---

## 4. 运行步骤

### 方式一：一键脚本（推荐）

```bash
bash scripts/run_r5_template.sh
```

脚本将自动完成以下步骤：
1. 加载示例数据集
2. 运行 TikTok vs 小红书 对比实验（15 步，seed=42）
3. 生成对比图表（极化曲线、羊群曲线、速度柱状图、雷达图）
4. 输出 Markdown 报告和 JSON 结果
5. 保存到 `artifacts/experiments/exp_demo_tiktok_vs_xhs/`

### 方式二：Python 脚本

```python
import sys
sys.path.insert(0, '.')

from pathlib import Path
from oasis_dashboard.experiment_runner import ExperimentConfig, run_experiment, generate_compare_report
from oasis_dashboard.compare_analyzer import generate_compare_charts, generate_compare_report_md

# 1. 配置实验
config = ExperimentConfig(
    name="exp_demo_tiktok_vs_xhs",
    dataset_id="dataset_demo_reddit",
    platform="REDDIT",
    recommenders=["TIKTOK", "XIAOHONGSHU"],
    steps=15,
    seed=42,
    agent_count=10,
)

# 2. 运行实验
dataset_path = Path("artifacts/r5/dataset_demo_reddit.json")
output_dir = Path("artifacts/experiments/exp_demo_tiktok_vs_xhs")
result = run_experiment(config, dataset_path, output_dir=output_dir)

# 3. 生成对比图表
charts = generate_compare_charts(output_dir / "result.json", output_dir)
print(f"生成图表：{[c.name for c in charts]}")

# 4. 生成 Markdown 报告
report = generate_compare_report_md(output_dir / "result.json", chart_dir=output_dir)
with open(output_dir / "compare.md", "w", encoding="utf-8") as f:
    f.write(report)

print("实验完成！结果保存至:", output_dir)
```

### 方式三：命令行（使用 run_r5_template.sh）

```bash
# 自定义参数
RECOMMENDERS="TIKTOK,PINTEREST" STEPS=20 SEED=123 bash scripts/run_r5_template.sh
```

---

## 5. 结果目录规范

每次实验自动生成以下目录结构：

```
artifacts/
└── experiments/
    └── exp_demo_tiktok_vs_xhs/
        ├── config.json              # 实验配置（输入）
        ├── result.json              # 完整实验结果（含 stepsTrace）
        ├── metrics.csv              # 各推荐器核心指标汇总表
        ├── compare.md               # Markdown 格式对比报告
        ├── compare_polarization.png # 极化曲线对比图
        ├── compare_herd.png         # 羊群效应曲线对比图
        ├── compare_velocity.png     # 传播速度柱状图
        └── compare_radar.png        # 综合指标雷达图
```

---

## 6. 输出解释

### (1) 核心指标

| 指标 | 英文名 | 计算方法 | 含义 |
|---|---|---|---|
| **极化值** | Polarization Index | 意见分布的方差归一化值 | 越高表示社区意见分裂越严重 |
| **羊群指数** | Herd Index (HHI) | 赫芬达尔-赫希曼指数 | 越高表示内容集中度越高，羊群效应越强 |
| **传播速度** | Information Velocity | 每步新帖子数 / 活跃 Agent 数 | 越高表示信息扩散越快 |
| **总帖子数** | Total Posts | 累计帖子数 | 反映平台活跃度 |

### (2) 极化值计算公式

$$P = \frac{1}{N} \sum_{i=1}^{N} (o_i - \bar{o})^2 \times 4$$

其中 $o_i$ 为第 $i$ 个 Agent 的当前意见值，$\bar{o}$ 为均值，$N$ 为 Agent 总数。系数 4 将值域归一化到 [0, 1]。

### (3) 羊群指数（HHI）计算公式

$$H = \sum_{k=1}^{K} s_k^2$$

其中 $s_k$ 为第 $k$ 类内容的市场份额（帖子数占比），$K$ 为内容类别数。HHI 越接近 1 表示内容越集中。

### (4) result.json 结构

```json
{
  "experimentId": "exp_xxxxxxxx",
  "createdAt": "2026-03-17T...",
  "config": { ... },
  "runs": [
    {
      "recommender": "TIKTOK",
      "metrics": {
        "polarization_final": 0.6826,
        "herd_index_final": 0.5802,
        "velocity_avg": 0.4734,
        "total_posts": 34,
        "unique_active_agents": 5
      },
      "stepsTrace": [
        { "step": 1, "polarization": 0.45, "herd_index": 0.35, "velocity": 0.3 },
        ...
      ]
    }
  ]
}
```

---

## 7. 常见错误

| 错误信息 | 原因 | 解决方案 |
|---|---|---|
| `ModuleNotFoundError: oasis_dashboard` | 未在项目根目录运行 | 在 `/home/ubuntu/oasis-r4` 目录下执行 |
| `FileNotFoundError: dataset_demo_reddit.json` | 数据集路径错误 | 检查 `artifacts/r5/` 目录是否存在该文件 |
| `KeyError: 'agents'` | 数据集格式不正确 | 参照第 2 节的 JSON 结构检查字段名 |
| `ValueError: Unknown recommender` | 推荐器名称错误 | 使用大写：`TIKTOK` / `XIAOHONGSHU` / `PINTEREST` |
| 图表生成失败 | matplotlib 未安装 | `pip install matplotlib` |

---

## 8. 可复现性说明

本模板通过以下机制保证实验可复现：

- **固定随机种子**：`seed=42` 控制所有随机过程（意见演化、帖子生成、Agent 选择）
- **确定性推荐器**：三个推荐器均为纯函数，相同输入产生相同输出
- **版本锁定**：实验配置中记录 `experimentId`，可追溯到具体代码版本
- **结果存档**：每次运行自动保存完整 `result.json`，支持离线重分析

**验证可复现性：**

```bash
# 运行两次，对比 result.json 中的 polarization_final
python3 -c "
import json
from pathlib import Path
from oasis_dashboard.experiment_runner import ExperimentConfig, run_experiment

config = ExperimentConfig(
    name='repro_test', dataset_id='dataset_demo_reddit',
    platform='REDDIT', recommenders=['TIKTOK'], steps=15, seed=42
)
r1 = run_experiment(config, Path('artifacts/r5/dataset_demo_reddit.json'))
r2 = run_experiment(config, Path('artifacts/r5/dataset_demo_reddit.json'))
assert r1.runs[0].metrics['polarization_final'] == r2.runs[0].metrics['polarization_final']
print('可复现性验证通过！')
"
```
