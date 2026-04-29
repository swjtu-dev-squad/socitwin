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

## 2. Reading Order

建议按下面顺序读：

1. [audit-and-validation.md](./audit-and-validation.md)
   - 当前 `AUD-*` 风险台账、状态模型、最小验证要求。
2. [architecture-audit-plan-20260428.md](./architecture-audit-plan-20260428.md)
   - 当前粗糙实现点、B-level 结果边界和后续分模块审查顺序。

验证场景目录在：

- [../evaluation/runtime/validation-scenarios.md](../evaluation/runtime/validation-scenarios.md)

系统级测试与 harness 入口在：

- [../evaluation/runtime/testing-and-evaluation.md](../evaluation/runtime/testing-and-evaluation.md)
