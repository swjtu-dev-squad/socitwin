# Socitwin Memory Docs

## 角色

本目录用于记录 `socitwin` 当前仓库中的记忆系统文档。

这里需要明确区分两类文档：

- 正式文档
  - 用于解释新仓库里记忆系统现在是什么、为什么这样分模式、后续该从哪里继续维护。
- 迁移文档
  - 用于记录从 `oasis-dashboard` 迁入时的对照、决策、实施过程和收尾状态。

后续应以正式文档为主，迁移文档为辅。

## 当前阅读顺序

如果你是要理解新仓库当前记忆系统，建议按下面顺序读：

1. [current-architecture.md](./current-architecture.md)
   - 当前新仓库里的代码事实、模块布局、两模式 wiring、主运行链。
2. [principles-and-modes.md](./principles-and-modes.md)
   - 这条路线为什么存在、`upstream` / `action_v1` 的职责边界、哪些是硬约束。
3. [audit/architecture-audit-plan-20260428.md](./audit/architecture-audit-plan-20260428.md)
   - 当前 `action_v1` 粗糙实现点、B-level 结果边界和后续分模块审查顺序。

如果你是要继续做迁移或整理正式文档，再看：

4. [migration-documentation-plan.md](./archived/migration/migration-documentation-plan.md)
   - 旧仓库记忆文档结构盘点、新仓库正式文档骨架、逐页迁移去向。
5. [migration-archive-readiness.md](./archived/migration/migration-archive-readiness.md)
   - 当前迁移文档是否还保留独占信息、哪些可以归档、哪些应继续作为实施记录保留。

## 正式文档

当前已经建立的正式文档：

- [current-architecture.md](./current-architecture.md)
- [principles-and-modes.md](./principles-and-modes.md)
- [observation-and-evidence.md](./observation-and-evidence.md)
- [prompt-and-shortterm.md](./prompt-and-shortterm.md)
- [longterm-and-recall.md](./longterm-and-recall.md)
- [evaluation/README.md](./evaluation/README.md)
- [config-and-runtime.md](./config-and-runtime.md)
- [evaluation/testing-and-evaluation.md](./evaluation/testing-and-evaluation.md)
- [evaluation/validation-scenarios.md](./evaluation/validation-scenarios.md)
- [audit/README.md](./audit/README.md)
- [audit/audit-and-validation.md](./audit/audit-and-validation.md)
- [audit/architecture-audit-plan-20260428.md](./audit/architecture-audit-plan-20260428.md)

当前正式文档主线已经闭合。

后续重点不再是继续补正式骨架，而是：

- 持续补充场景、审查条目和结果记录；
- 持续完善 `evaluation/` 下的长期记忆测评指标、场景和实施方案；
- 把迁移文档里仍有价值但尚未归入正式文档的内容继续收口；
- 在确认没有关键独占信息后，再把 `migration-*` 文档降级归档。

## 迁移文档

下面这些文档仍然保留，但它们属于迁移实施记录，不应继续充当正式使用文档主体：

- [migration-plan.md](./archived/migration/migration-plan.md)
  - 迁移实施计划总览与索引。
- [migration-decisions.md](./archived/migration/migration-decisions.md)
  - 已确认的迁移边界和目录设计决定。
- [migration-architecture-comparison.md](./archived/migration/migration-architecture-comparison.md)
  - 旧仓库与新仓库的架构对照和插入点判断。
- [migration-module-mapping.md](./archived/migration/migration-module-mapping.md)
  - 旧 memory 模块到新仓库目录的文件级映射。
- [migration-config-and-testing.md](./archived/migration/migration-config-and-testing.md)
  - 配置面、测试面与验证顺序。
- [migration-refactor-principles.md](./archived/migration/migration-refactor-principles.md)
  - 迁移过程中允许的小幅重构边界。
- [migration-phase-checklists.md](./archived/migration/migration-phase-checklists.md)
  - 可直接执行的分阶段 checklist。
- [migration-workstreams.md](./archived/migration/migration-workstreams.md)
  - 迁移范围、阶段顺序、文件级工作流和测试/文档策略。
- [migration-documentation-plan.md](./archived/migration/migration-documentation-plan.md)
  - 旧记忆文档向新正式文档体系迁移的专项计划。
- [migration-archive-readiness.md](./archived/migration/migration-archive-readiness.md)
  - 迁移收尾阶段的文档归档判定清单。

统一归档入口见：

- [archived/README.md](./archived/README.md)

## 当前 Source Of Truth

- 当前代码事实：
  - [current-architecture.md](./current-architecture.md)
- 当前模式边界与设计原则：
  - [principles-and-modes.md](./principles-and-modes.md)
- 迁移期历史判断与结构对照：
  - 各个 `migration-*` 文档

## 维护规则

- 先核对代码事实，再改正式文档。
- 新仓库正式事实优先写进正式文档，不继续只堆在 `migration-*` 里。
- 若只是迁移过程判断、文件映射或历史决策，继续写进 `migration-*`。
- 若正式文档与实现不一致，应先修正文档，不要继续依赖旧仓库页面兜底。
