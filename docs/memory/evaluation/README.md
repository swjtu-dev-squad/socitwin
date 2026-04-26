# Memory Evaluation Docs

- Status: active evaluation workspace
- Audience: implementers, evaluators, experiment/report authors
- Doc role: entry point for long-term memory evaluation design and future benchmark work

## 1. Purpose

本目录用于集中维护 `action_v1` 记忆架构的测评方案。

这里的文档不替代：

- [../testing-and-evaluation.md](../testing-and-evaluation.md)
- [../validation-scenarios.md](../validation-scenarios.md)
- [../audit-and-validation.md](../audit-and-validation.md)

它的职责更窄：把长期记忆能力拆成可汇报、可复测、可调试的指标和场景。

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

## 4. Reading Order

建议按下面顺序读：

1. [longterm-memory-evaluation-plan.md](./longterm-memory-evaluation-plan.md)
   - 总体评测目标、分层思路和第一阶段落地范围。
2. [metrics.md](./metrics.md)
   - 指标定义、当前代码字段映射、summary KPI 输出和不可用指标口径。
3. [action-v1-memory-whitebox-flow.md](./action-v1-memory-whitebox-flow.md)
   - `action_v1` 从 observation、tool call、ActionEvidence、ActionEpisode、长期写入、检索、rerank、过滤到 prompt 注入的白盒流程。
4. [scenarios.md](./scenarios.md)
   - 真实运行回查、受控 episode benchmark、行为级场景的设计。
5. [dataset-and-reliability.md](./dataset-and-reliability.md)
   - 测评数据集、ground truth、随机性控制和结果可靠性口径。
6. [implementation-plan.md](./implementation-plan.md)
   - 已完成的 Phase 1 KPI 聚合，以及 B-level v0、runtime-query replay 和 optional controlled benchmark 的实施顺序。

## 5. First-Phase Position

第一阶段不要追求“大而全”的评测系统。

当前最有价值的落地点是：

- 使用 `summary.json` 中的 `memory_kpis` 汇总 exact episode hit、cross-agent contamination、gate、false trigger 和 trace-level injection；
- 使用 `unavailable_metrics` 区分“没有跑 / 没样本”和真实 0 分；
- 使用 run 目录下的 `README.md` 给人类和 AI 快速阅读 KPI 与缺失原因；
- 使用 `--scenario-pack` 运行第一版固定输入 B-level v0 replay，当前包含 `s1_stable_single_topic` 和 `s2_similar_topic_interference`；
- 明确区分 retrieve-only、full-path injection、behavioral effect 三种口径。
- 明确区分 runtime recall query 与 evaluation probe query：前者来自当前 observation 感知，后者来自目标 `ActionEpisode` 自身字段。
- 明确区分确定性组件测试、真实运行 episode 回放和随机行为级场景，避免把一次真实模拟结果当成最终结论。
- 先把当前固定输入 replay 收口成 `B-level v0`，再补 runtime-query replay，最后再考虑多 run 聚合或 controlled benchmark。

这能先回答组会最关心的问题：

- 正确历史事件能否被检到；
- agent 过滤是否仍然可靠；
- 检到后是否真的进入 prompt。
