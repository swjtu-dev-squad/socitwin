# Memory Migration Docs

## Role

本目录用于记录 `oasis-dashboard` 记忆系统迁移到 `socitwin` 的准备、实施和复核过程。

当前文档分工：

- `migration-plan.md`
  - 迁移实施计划总览与索引。
- `migration-decisions.md`
  - 记录已确认的迁移边界和目录设计决定。
- `migration-architecture-comparison.md`
  - 记录旧仓库与新仓库的架构对照和插入点判断。
- `migration-module-mapping.md`
  - 记录旧 memory 模块到新仓库目录的文件级映射。
- `migration-config-and-testing.md`
  - 记录配置面、测试面与验证顺序。
- `migration-refactor-principles.md`
  - 记录迁移过程中允许的小幅重构边界，防止机械迁移或失控重构。
- `migration-phase-checklists.md`
  - 记录可直接执行的分阶段 checklist。
- `migration-workstreams.md`
  - 记录迁移范围、阶段顺序、文件级工作流和测试/文档策略。
- `social-monitor-migration-plan.md`
  - 记录旧仓库社交网络监控页功能迁入新仓库的页面展示目标、后端接口合同、memory debug 对接方式和实施阶段。

## Editing Rule

- 先核对代码事实，再更新文档。
- 新发现的架构差异，优先补到 `migration-architecture-comparison.md`。
- 新确认的文件级模块归属，优先补到 `migration-module-mapping.md`。
- 新确认的配置/测试策略，优先补到 `migration-config-and-testing.md`。
- 新确认的“迁移时允许的重构边界”，优先补到 `migration-refactor-principles.md`。
- 已确认决策，优先补到 `migration-decisions.md`。
- 新增的可执行阶段步骤，优先补到 `migration-phase-checklists.md`。
- 实施阶段与文件级任务，优先补到 `migration-workstreams.md`。
- 前端社交网络监控页迁移和 monitor/detail 接口设计，优先补到 `social-monitor-migration-plan.md`。
