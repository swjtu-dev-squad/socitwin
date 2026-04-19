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

如果你是要继续做迁移或整理正式文档，再看：

3. [migration-documentation-plan.md](./migration-documentation-plan.md)
   - 旧仓库记忆文档结构盘点、新仓库正式文档骨架、逐页迁移去向。

## 正式文档

当前已经建立的正式文档：

- [current-architecture.md](./current-architecture.md)
- [principles-and-modes.md](./principles-and-modes.md)
- [observation-and-evidence.md](./observation-and-evidence.md)
- [prompt-and-shortterm.md](./prompt-and-shortterm.md)
- [longterm-and-recall.md](./longterm-and-recall.md)
- [config-and-runtime.md](./config-and-runtime.md)
- [testing-and-evaluation.md](./testing-and-evaluation.md)

当前计划继续补齐的正式文档：

- `validation-scenarios.md`
- `audit-and-validation.md`

这些页面会按 [migration-documentation-plan.md](./migration-documentation-plan.md) 里的顺序逐步建立。

## 迁移文档

下面这些文档仍然保留，但它们属于迁移实施记录，不应继续充当正式使用文档主体：

- [migration-plan.md](./migration-plan.md)
  - 迁移实施计划总览与索引。
- [migration-decisions.md](./migration-decisions.md)
  - 已确认的迁移边界和目录设计决定。
- [migration-architecture-comparison.md](./migration-architecture-comparison.md)
  - 旧仓库与新仓库的架构对照和插入点判断。
- [migration-module-mapping.md](./migration-module-mapping.md)
  - 旧 memory 模块到新仓库目录的文件级映射。
- [migration-config-and-testing.md](./migration-config-and-testing.md)
  - 配置面、测试面与验证顺序。
- [migration-refactor-principles.md](./migration-refactor-principles.md)
  - 迁移过程中允许的小幅重构边界。
- [migration-phase-checklists.md](./migration-phase-checklists.md)
  - 可直接执行的分阶段 checklist。
- [migration-workstreams.md](./migration-workstreams.md)
  - 迁移范围、阶段顺序、文件级工作流和测试/文档策略。
- [migration-documentation-plan.md](./migration-documentation-plan.md)
  - 旧记忆文档向新正式文档体系迁移的专项计划。
- [social-monitor-migration-plan.md](./social-monitor-migration-plan.md)
  - 监控页相关的后端合同与后续增强计划。

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
