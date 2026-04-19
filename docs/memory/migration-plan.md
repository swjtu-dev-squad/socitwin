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
- 社交网络监控页功能迁移与 monitor/detail 接口计划：
  - [`social-monitor-migration-plan.md`](./social-monitor-migration-plan.md)

## 4. Current Main Risks

- 旧仓库 `context/llm.py` 的独立模型 runtime 包装尚未以等价形态恢复；
- 迁移主链已基本闭合，但仍需把“非阻塞遗留项”和“后续增强项”从主线验收中明确剥离，避免继续把迁移收尾和后续评测混在一起。

## 5. Current Next Step

当前迁移已经进入收尾验收与剩余缺口盘点阶段。按“后端功能模块迁移”视角，下一轮重点应收口为：

1. 确认 `context/llm.py` 对应的模型 runtime 包装差异是否需要后续小 helper；
2. 明确 `topic activation`、monitor/debug drill-down 等已知边界是否继续保持为非阻塞项；
3. 盘点迁移完成后的结构清理项，例如过大的 facade / agent / config / evaluation harness。

关于社交网络监控：

- monitor/detail 后端第一版已经落地；
- 它不再属于当前 memory 主链迁移的主阻塞项；
- 后续若继续推进，重点应是展示增强和真实长跑联调，而不是“功能模块是否已迁入”。

关于 `comparison`：

- 两模式代码/单测层已经恢复；
- 真实 provider 级长跑验证保留为后续按需评测；
- 当前迁移收尾阶段暂不把它作为阻塞项。

当前这些事项已经拆到独立页面持续维护，后续总览页只保留高层边界与进度。
