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
   - 指标定义、当前代码字段映射、哪些指标可直接算、哪些还需要补聚合。
3. [scenarios.md](./scenarios.md)
   - 真实运行回查、受控 episode benchmark、行为级场景的设计。
4. [implementation-plan.md](./implementation-plan.md)
   - 后续实际修改 `evaluation_harness.py` 和测试输出的实施顺序。

## 5. First-Phase Position

第一阶段不要追求“大而全”的评测系统。

当前最有价值的落地点是：

- 把 `real-scenarios` 已有的 exact episode hit 指标正式汇总到 `summary.json`；
- 把 cross-agent contamination 作为 agent 过滤回归防线保留到 summary；
- 把 `real-longwindow` 的 recalled -> injected 统计整理成可读指标；
- 明确区分 retrieve-only、full-path injection、behavioral effect 三种口径。

这能先回答组会最关心的问题：

- 正确历史事件能否被检到；
- agent 过滤是否仍然可靠；
- 检到后是否真的进入 prompt。
