# Memory Evaluation Docs

- Status: active evaluation workspace
- Audience: implementers, evaluators, experiment/report authors
- Doc role: entry point for long-term memory evaluation design and future benchmark work

## 1. Purpose

本目录用于集中维护 `action_v1` 记忆架构的测评方案。

这里的文档不替代：

- [../audit/audit-and-validation.md](../audit/audit-and-validation.md)
- [../audit/audit-master-plan-20260428.md](../audit/audit-master-plan-20260428.md)

它的职责是把记忆测试、验证场景和长期记忆能力测评收拢到同一工作区，拆成可汇报、可复测、可调试的指标和场景。

## 2. Current Scope

当前评测对象是：

- `action_v1` 的长期记忆写入、检索、recall gate、prompt 注入和后续行为影响。

当前不把下面内容作为本目录主目标：

- 重新评测原生 OASIS 的通用 chat history 能力；
- 恢复旧仓库 `baseline` 路线；
- 直接把行为表现压成一个不可解释的总分。

`upstream` 可以作为系统对照，但长期记忆 KPI 默认只针对 `action_v1`。

## 3. Code Facts

当前评测方案基于这些代码事实：

- 长期记忆持久化单元是 `ActionEpisode`，不是完整 chat history。
- 检索路径是 `Chroma + embedding + field-aware rerank`，不是纯 embedding RAG。
- recall 需要先经过 `RecallPlanner` gate，不是“库里有内容就查”。
- 正常 recall 路径会按当前 `agent_id` 过滤长期记忆；跨 agent 命中应视为过滤失效或回归风险，而不是预期常态。
- 检到的 candidate 还会经过 overlap suppression、recall budget 和 prompt budget，检到不等于注入。
- 行为效果最重要，但最难自动判读，应放在检索/gate/注入指标稳定之后。

## 4. Evaluation Design Principle

当前记忆实现仍然比较粗糙：episode 写入、runtime query、rerank、prompt 注入都存在工程妥协。因此评测不能假设系统已经是成熟 RAG，也不能为了得到好看指标而脱离当前实现。

所有评测设计都必须同时回答两个问题：

- 实现贴合性：这个测试问的问题是否是当前系统真实会发生的问题。
- 缺陷暴露性：这个测试是否能暴露当前实现中写入、查询、排序、过滤、注入或行为连续性的具体问题。

换句话说，评测必须贴合当前实现，否则结果无法解释当前系统；但评测不能迁就当前实现，否则只会把粗糙实现包装成“指标正常”。

## 5. Directory Layout

当前目录按职责分成四块：

| Path | Role |
| --- | --- |
| [design/](./design/README.md) | 评估设计、KPI、scenario group、数据集可靠性 |
| [runtime/](./runtime/README.md) | harness 运行、`VAL-*` 场景目录、`action_v1` 白盒流程 |
| [results/](./results/README.md) | 具体评测运行结果和阶段性报告 |
| [implementation-plan.md](./implementation-plan.md) | 已实施能力、后续 phase 和未决项 |

原先分散的 `longterm-memory-evaluation-plan.md`、`metrics.md`、`scenarios.md` 已合并进：

- [design/benchmark-overview.md](./design/benchmark-overview.md)

## 6. Reading Order

建议按下面顺序读：

1. [runtime/testing-and-evaluation.md](./runtime/testing-and-evaluation.md)
   - 测试层级、evaluation harness、常用命令和结果读取方式。
2. [design/benchmark-overview.md](./design/benchmark-overview.md)
   - 总体评测目标、KPI、query 边界、scenario group 和 B-level 演进。
3. [runtime/action-v1-memory-whitebox-flow.md](./runtime/action-v1-memory-whitebox-flow.md)
   - `action_v1` 从 observation、tool call、ActionEvidence、ActionEpisode、长期写入、检索、rerank、过滤到 prompt 注入的白盒流程。
4. [runtime/validation-scenarios.md](./runtime/validation-scenarios.md)
   - `VAL-*` 回归和保真验证场景目录，对应审查台账里的 `AUD-*` 条目。
5. [design/dataset-and-reliability.md](./design/dataset-and-reliability.md)
   - 测评数据集、ground truth、随机性控制和结果可靠性口径。
6. [implementation-plan.md](./implementation-plan.md)
   - 已完成的 Phase 1 KPI 聚合、B-level v0、B-level v0.5 post-linked final lookup，以及后续 trace replay / controlled benchmark 的实施顺序。

## 7. First-Phase Position

第一阶段不要追求“大而全”的评测系统。

当前最有价值的落地点是：

- 使用 `summary.json` 中的 `memory_kpis` 汇总 exact episode hit、cross-agent contamination、gate、false trigger 和 trace-level injection；
- 使用 `unavailable_metrics` 区分“没有跑 / 没样本”和真实 0 分；
- 使用 run 目录下的 `README.md` 给人类和 AI 快速阅读运行概览、样本覆盖、两类检索指标、失败诊断和缺失原因；
- 使用 `--scenario-pack` 运行第一版固定输入 B-level v0 replay，当前包含 `s1_stable_single_topic` 和 `s2_similar_topic_interference`；
- 使用 `VAL-RCL-11 post_linked_final_lookup` 按每个可见 post summary 出题，评估 final-store post-linked memory lookup；
- 明确区分 retrieve-only、full-path injection、behavioral effect 三种口径。
- 明确区分 runtime recall query 与 evaluation probe query：前者来自当前 observation 感知，后者来自目标 `ActionEpisode` 自身字段。
- 明确区分确定性组件测试、真实运行 episode 回放和随机行为级场景，避免把一次真实模拟结果当成最终结论。
- 先把当前固定输入 replay 收口成 `B-level v0 / v0.5`，再补完整 query trace replay、多 run 聚合或 controlled benchmark。

这能先回答组会最关心的问题：

- 正确历史事件能否被检到；
- agent 过滤是否仍然可靠；
- 检到后是否真的进入 prompt。
