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

## 4. Current Main Risks

- 新仓库当前仍没有显式 memory runtime；
- 新仓库当前测试面仍远小于旧仓库记忆主线所需覆盖面；
- 如果直接把旧实现按 git 历史硬合进来，极易把新架构与旧 runtime 污染在一起。

## 5. Current Next Step

下一轮对照重点：

1. 继续把旧仓库 `context/*` 模块映射到新仓库 `backend/app/memory/` 的文件级任务清单；
2. 继续梳理新仓库配置命名与旧仓库 memory 配置面的对应关系；
3. 把测试迁移计划压实到“哪些先迁、哪些重写、哪些只保留验证目标”。

当前这三项已经拆到独立页面持续维护，后续总览页只保留高层边界与进度。
