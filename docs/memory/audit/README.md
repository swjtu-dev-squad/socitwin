# Memory Audit Docs

- Status: active audit workspace
- Audience: implementers, reviewers, fidelity auditors
- Doc role: entry point for memory architecture audit records and follow-up review plans

## 1. Purpose

本目录集中维护 `action_v1` 记忆架构的审查材料。

这里的文档不替代：

- [../current-architecture.md](../current-architecture.md)
- [../principles-and-modes.md](../principles-and-modes.md)
- [../evaluation/README.md](../evaluation/README.md)

它的职责更窄：

- 记录当前已确认或待核查的架构风险；
- 保存分阶段审查计划；
- 把 `AUD-*` 风险台账和 `VAL-*` 验证场景连接起来；
- 避免审查记录继续散落在 `docs/memory/` 顶层。

## 2. Plan Hierarchy

审查计划只保留一个 source of truth：

- [audit-master-plan-20260428.md](./audit-master-plan-20260428.md)
  - 定义审查目标、阶段顺序、优先级、模型交互视角和后续审查产物。
- [implementation-audit-checklist-20260428.md](./implementation-audit-checklist-20260428.md)
  - 只作为实现级检查清单使用，补充问题簇、代码锚点、逐模块 checklist 和验证回路。

如果两者出现冲突，以 master plan 为准。Checklist 可以补充模块检查项，但不能单独改变审查顺序、优先级、memory contract 或 retrieval task taxonomy；这些变化必须先更新 master plan。

## 3. Reading Order

建议按下面顺序读：

1. [audit-and-validation.md](./audit-and-validation.md)
   - 当前 `AUD-*` 风险台账、状态模型、最小验证要求。
2. [audit-master-plan-20260428.md](./audit-master-plan-20260428.md)
   - 总审查计划：当前粗糙实现点、B-level 结果边界、模型交互视角和后续分阶段审查顺序。
3. [implementation-audit-checklist-20260428.md](./implementation-audit-checklist-20260428.md)
   - 实现级检查清单：问题簇依赖图、逐文件模块 checklist、字段使用率和验证回路。

当前阶段 A 审查记录：

- [prompt-trace-audit-20260429.md](./prompt-trace-audit-20260429.md)
  - 基于 B-level S1 真实运行 trace，审查模型输入、runtime query、recall injection、action target 和 `ActionEpisode` 写入之间的事实边界。
- [summary-topic-audit-20260429.md](./summary-topic-audit-20260429.md)
  - 沿 `summary -> topic -> recall query -> ActionEpisode.topic -> long-term document` 链路，审查 display excerpt 被复用为语义索引和检索意图的结构性问题。

验证场景目录在：

- [../evaluation/runtime/validation-scenarios.md](../evaluation/runtime/validation-scenarios.md)

系统级测试与 harness 入口在：

- [../evaluation/runtime/testing-and-evaluation.md](../evaluation/runtime/testing-and-evaluation.md)
