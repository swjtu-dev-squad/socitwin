# 任务卡：R5-01 推荐策略 × 数据集 对比实验最小闭环

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Experiment Pipeline / A-B Comparison |
| **负责人** | 实验框架负责人 |
| **协作人** | 推荐算法负责人、数据导入负责人、分析负责人 |
| **关联 Issue** | #32, #34, #24 |

---

## 1. 背景

当前项目已经具备三项关键基础：

- 自定义数据集导入与 agentConfig 生成入口（#34 主线）
- 统一推荐接口与三平台最小 scorer（#32 主线）
- 三大指标与 Analytics 面板基础（#24、#33 主线）

但这三者目前仍偏“并列存在”，还没有被真正串成一条实验闭环。R5-01 的目标就是建立这个最小闭环：**同一数据集，在不同推荐策略下运行同一批模拟，输出可比较的结果**。

## 2. 目标

实现一个最小对比实验框架，使系统能够：

- 选择一个导入数据集；
- 选择两个或多个推荐策略；
- 使用相同初始条件运行模拟；
- 输出可比较的核心指标结果；
- 保存单次实验的配置与结果，供复现使用。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| 单次实验配置定义 | 多任务并行调度系统（#30 完整版） |
| 数据集选择 | 大规模批量参数搜索 |
| 推荐器选择 | Dashboard 内复杂实验管理后台 |
| 最小 A/B 运行入口 | |
| 指标结果导出 | |
| 结果归档 | |

## 4. 建议实验配置结构

```typescript
type ExperimentConfig = {
  name: string;
  datasetId: string;
  platform: "REDDIT" | "X" | "FACEBOOK" | "TIKTOK" | "INSTAGRAM";
  recommenders: string[]; // e.g. ["TIKTOK", "XIAOHONGSHU", "PINTEREST"]
  steps: number;
  seed: number;
  metrics: string[]; // ["polarization", "herdIndex", "velocity", "coverage"]
};
```

## 5. 实现方案

- **最小运行方式**：先不实现复杂 UI，提供 REST API (`POST /api/experiments/run`, `GET /api/experiments/:id/result`) 或后端脚本 (`run_experiment_compare.py`)。
- **对比维度**：每次至少比较 `polarization`, `herdIndex`, `velocity`, `totalPosts`, `uniqueActiveAgents`。
- **结果结构**：
  ```json
  {
    "experimentId": "exp_001",
    "datasetId": "dataset_demo",
    "runs": [
      {
        "recommender": "TIKTOK",
        "metrics": {
          "polarization_final": 0.37,
          "herdIndex_final": 0.42,
          "velocity_avg": 0.18,
          "totalPosts": 24
        }
      }
    ]
  }
  ```

## 6. 测试用例

- **T1**：同一数据集可在三种推荐器下运行。
- **T2**：结果结构完整，可导出 JSON。
- **T3**：推荐器之间存在可观察差异（至少一个核心指标不同）。
- **T4**：重复运行可复现（固定 seed 下差异在合理范围内）。

## 7. 通过标准 (Gate)

- [ ] 可选择导入数据集并运行实验
- [ ] 可在至少 2 种推荐器间做比较
- [ ] 输出统一格式实验结果
- [ ] 核心指标至少 4 项可比较
- [ ] 结果可复现（固定 seed）
- [ ] 有最小对比报告

## 8. 失败标准

- 数据集与推荐器不能在同一入口联动
- 对比结果结构不统一
- 三种推荐器跑出来完全同质，无法解释
- 实验无法复现

## 9. 证据要求

- `artifacts/r5/r5_01_experiment_result.json`
- `artifacts/r5/r5_01_report.md`
- 一份固定 seed 的重复运行对照

## 10. 建议提交信息

```bash
git commit -m "feat(experiment): add minimal dataset x recommender comparison pipeline"
```
