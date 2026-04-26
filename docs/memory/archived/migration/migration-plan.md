# Oasis Memory Migration Plan

- Status: active
- Audience: migration implementers, reviewers, AI tools
- Scope: migrate the memory optimization route from `oasis-dashboard` into `socitwin`
- Current branch: `feature/oasis-memory-migration-plan`

## 1. Purpose

本页只作为迁移 planning 的总览页，回答三件事：

1. 当前迁移目标是什么；
2. 已经确认了哪些关键边界；
3. 详细对照和实施细节分别去哪里看。

详细分析已经拆到独立页面，避免所有迁移内容堆进一个超长文档。

## 2. Current Target

当前已确认的迁移目标：

- 新仓库只保留两条模式线：
  - `upstream`
  - `action_v1`
- 旧仓库 `baseline` 不再作为新仓库运行模式迁移；
  - 只保留历史说明与必要对照背景。
- 记忆系统单独落在：
  - `backend/app/memory/`
- 迁移第一优先级是：
  - 后端运行主链
  - 记忆主链
  - 测试主链
  - 文档主链
- 前端不是当前阻塞项，但要保留最小接口契约盘点。
- memory 运行细节不继续主要堆进 `/api/sim/status`；
  - 改走单独的 monitor/debug 接口。

## 3. Detailed Pages

- 已确认决策与目录设计：
  - [`migration-decisions.md`](./migration-decisions.md)
- 新旧仓库架构对照与插入点分析：
  - [`migration-architecture-comparison.md`](./migration-architecture-comparison.md)
- 旧模块到新目录的文件级映射：
  - [`migration-module-mapping.md`](./migration-module-mapping.md)
- 配置面、测试面与迁移顺序：
  - [`migration-config-and-testing.md`](./migration-config-and-testing.md)
- 迁移时允许的小幅重构边界：
  - [`migration-refactor-principles.md`](./migration-refactor-principles.md)
- 分阶段实施 checklist：
  - [`migration-phase-checklists.md`](./migration-phase-checklists.md)
- 迁移范围、阶段拆分、文件级工作流：
  - [`migration-workstreams.md`](./migration-workstreams.md)
- 迁移文档是否已具备归档条件：
  - [`migration-archive-readiness.md`](./migration-archive-readiness.md)
- 社交网络监控页功能迁移与 monitor/detail 接口计划：
  - [`social-monitor-migration-plan.md`](../../social-monitor-migration-plan.md)

## 4. Current Main Risks

当前主风险已经不再是“主链有没有迁回来”，而是：

- 迁移文档里是否还残留正式文档未吸收的关键信息；
- 迁移收尾与后续增强项是否仍被混写，导致归档判断失真。

像下面这些内容，当前都已经明确为非阻塞边界，而不是迁移主风险：

- 旧仓库 `context/llm.py` 的独立模型 runtime 包装没有原样迁回；
- monitor/debug 更细的 per-agent drill-down 仍待后续增强；
- 过大的 facade / agent / config / evaluation harness 仍待后续工程清理；
- `comparison` 的真实 provider 级长跑仍属于后续按需评测。

## 5. Current Next Step

当前迁移已经进入归档前的最终核对阶段。下一轮重点应收口为：

1. 再核对一轮 `migration-*` 文档，确认没有正式文档尚未吸收的独占关键信息；
2. 把仍需后续完善的事项明确沉淀到正式文档或正式审查台账；
3. 在确认主线代码、测试、正式文档都已闭合后，再把 `migration-*` 文档降级归档。

关于社交网络监控：

- monitor/detail 后端第一版已经落地；
- 它不再属于当前 memory 主链迁移的主阻塞项；
- 后续若继续推进，重点应是展示增强和真实长跑联调，而不是“功能模块是否已迁入”。

关于 `comparison`：

- 两模式代码/单测层已经恢复；
- 真实 provider 级长跑验证保留为后续按需评测；
- 当前迁移收尾阶段暂不把它作为阻塞项。

当前这些事项已经拆到独立页面持续维护，后续总览页只保留高层边界与进度。
