# 任务卡：R5-03 基于导入数据与推荐策略的可复现实验模板

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P1 |
| **类型** | Reproducibility / Experiment Template / Operationalization |
| **负责人** | 工程负责人 |
| **协作人** | 测试负责人、数据导入负责人、推荐算法负责人 |
| **关联 Issue** | #34, #32, #30 |

---

## 1. 背景

现在系统已经具备数据导入、推荐接口、Analytics 可视化、Sidecar 最小联调等能力。但如果没有一个可复现实验模板，这些功能仍然偏“开发者自己知道怎么点”。R5 的目标是给出一套轻量可复现模板，让实验不靠口口相传。

## 2. 目标

建立一套最小可复现实验模板，使团队成员可以：

- 选定示例数据集；
- 选定推荐策略；
- 运行固定步数实验；
- 导出传播 / 极化 / HerdIndex 结果；
- 复现实验结论。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| 示例数据集 | 完整任务调度平台 |
| 示例实验配置 | GUI 实验管理器 |
| 运行步骤文档 | 大规模批量实验自动化 |
| 一键脚本（可选） | |
| 结果目录规范 | |

## 4. 建议模板内容

- **示例数据集**：`dataset_demo_reddit.json`, `dataset_demo_reddit.csv`
- **示例实验配置**：
  ```json
  {
    "name": "exp_demo_tiktok_vs_xhs",
    "datasetId": "dataset_demo_reddit",
    "platform": "REDDIT",
    "recommenders": ["TIKTOK", "XIAOHONGSHU"],
    "steps": 15,
    "seed": 42
  }
  ```
- **结果目录规范**：
  ```
  artifacts/
  └── experiments/
      └── exp_demo_tiktok_vs_xhs/
          ├── config.json
          ├── result.json
          ├── compare.md
          ├── propagation.png
          └── metrics.csv
  ```

## 5. 实现方案

- **文档**：新增 `docs/experiments/R5-EXPERIMENT-TEMPLATE.md`，包含输入格式、运行命令、输出解释、常见错误等。
- **脚本（可选）**：提供最小脚本 `bash scripts/run_r5_template.sh`。
- **成果导出**：要求每次实验自动保存 config, metrics, compare summary, 可视化截图（可选）。

## 6. 测试用例

- **T1**：新同学按文档能跑通。
- **T2**：示例数据集可直接用。
- **T3**：结果目录结构统一。
- **T4**：重复运行结果可接受（固定 seed 基本稳定）。

## 7. 通过标准 (Gate)

- [ ] 有示例数据集
- [ ] 有示例实验配置
- [ ] 有可执行步骤或脚本
- [ ] 有统一结果目录
- [ ] 一名未参与开发的同学可按文档复现

## 8. 失败标准

- 实验仍依赖口头说明
- 配置分散，结果难以复盘
- 同样流程不同人跑不出来
- 文档缺少关键步骤

## 9. 证据要求

- `docs/experiments/R5-EXPERIMENT-TEMPLATE.md`
- `artifacts/r5/r5_03_repro_run.md`
- 一份完整示例输出目录截图

## 10. 建议提交信息

```bash
git commit -m "docs(experiment): add reproducible template for dataset x recommender runs"
```
