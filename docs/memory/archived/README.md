# Memory Archived Docs

## 角色

本目录用于存放已经退出正式主文档位置、但仍需保留的历史记录。

这里的文档默认不再承担：

- 当前代码事实说明
- 当前模式边界说明
- 当前配置与测试口径说明

这些职责应回到 `docs/memory/` 下的正式文档。

## 当前归档内容

### migration/

这批文档记录了从 `oasis-dashboard` 向 `socitwin` 迁移记忆系统时的：

- 决策
- 架构对照
- 模块映射
- 分阶段 checklist
- 配置与测试迁移过程
- 文档迁移与归档判断

入口见：

- [migration-plan.md](./migration/migration-plan.md)
- [migration-archive-readiness.md](./migration/migration-archive-readiness.md)

## 使用规则

- 要看当前正式 memory 文档：
  - 返回 [../README.md](../README.md)
- 要看迁移历史和实施记录：
  - 进入 `migration/`
- 若归档文档与当前实现不一致：
  - 以 `docs/memory/` 下的正式文档和当前代码事实为准
