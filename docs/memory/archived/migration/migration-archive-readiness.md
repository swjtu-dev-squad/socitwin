# Memory Migration Archive Readiness

- Status: active
- Audience: migration implementers, reviewers, maintainers
- Role: determine which migration documents still contain unique information, and when they are safe to demote into archive/implementation-record status

## 1. Purpose

本页只回答两个问题：

1. 当前 `migration-*` 文档里，是否还保留正式文档没有吸收的关键信息；
2. 哪些迁移文档已经可以视为实施记录，等待归档。

它不是新的迁移计划页，也不是新的正式架构页。

## 2. Current Archive Criterion

一份迁移文档可以进入归档候选状态，至少要满足：

1. 它不再承担新仓库正式说明职责；
2. 其中涉及当前代码事实、当前模式边界、当前配置语义、当前测试口径的关键内容，已经有正式文档落点；
3. 它剩余的价值主要是：
   - 历史决策记录
   - 文件映射记录
   - 实施顺序记录
   - 阶段性测试记录

## 3. Current Review Result

当前复核后的结论是：

- 正式文档主线已经闭合；
- 迁移文档当前已不再承担主说明职责；
- 剩余迁移文档大多已经满足“实施记录”定位；
- 当前还需要的不是继续扩写迁移文档，而是决定何时整体降级归档。

同时，下面这些曾经只在迁移文档里讨论的内容，当前已经有正式文档落点：

- `context/llm.py` 未原样迁回，但不是迁移阻塞项
  - 已写入 [config-and-runtime.md](../../config-and-runtime.md)
- upstream 的 `max_tokens` / `OASIS_CONTEXT_TOKEN_LIMIT` 语义分离
  - 已写入 [config-and-runtime.md](../../config-and-runtime.md)
- monitor/debug 当前已足够支撑迁移完成态，更细 drill-down 属于后续增强
  - 已写入 [current-architecture.md](../../current-architecture.md)
- `topic activation` 作为环境种子而不是普通 `ActionEpisode`
  - 已写入 [current-architecture.md](../../current-architecture.md)
  - 已写入 [principles-and-modes.md](../../principles-and-modes.md)
- memory 大文件和宽 facade 属于后续工程清理项
  - 已写入 [current-architecture.md](../../current-architecture.md)
- 测试代码主链已恢复，剩余工作主要是口径细化、结果沉淀和场景扩充
  - 已写入 [testing-and-evaluation.md](../../testing-and-evaluation.md)

## 4. Per-Document Judgment

| Doc | Current value | Still has unique critical info? | Archive judgment |
| --- | --- | --- | --- |
| `migration-plan.md` | 迁移总览与阶段结论 | `no` | 可归档为总览记录 |
| `migration-decisions.md` | 迁移期关键决策记录 | `no` | 可归档为决策记录 |
| `migration-architecture-comparison.md` | 新旧架构对照分析 | `no` | 可归档为对照记录 |
| `migration-module-mapping.md` | 旧模块到新目录的映射 | `no` | 可归档为实施映射记录 |
| `migration-config-and-testing.md` | 配置/测试迁移过程记录 | `no` | 可归档为迁移实施记录 |
| `migration-refactor-principles.md` | 迁移期允许/禁止的重构边界 | `no` | 可归档为实施原则记录 |
| `migration-phase-checklists.md` | 分阶段执行清单 | `no` | 可归档为执行记录 |
| `migration-workstreams.md` | 范围、阶段、工作流拆分 | `no` | 可归档为工作流记录 |
| `migration-documentation-plan.md` | 文档迁移计划和映射 | `no` | 可归档为文档迁移记录 |
| `post-migration/social-monitor-migration-plan.md` | monitor 页功能迁移记录 | `no` | 已归档为 post-migration 专项记录 |
| `post-migration/e2e-reddit-action-v1-20260418.md` | 单次真实运行测试记录 | `no` | 已归档为 post-migration 历史测试记录 |

## 5. Remaining Pre-Archive Work

当前真正还需要做的只剩：

1. 再做一轮最终一致性检查：
   - 正式文档
   - 迁移文档
   - 当前代码事实
2. `migration-*` 已统一位于 `archived/migration/`；
3. `social-monitor-migration-plan.md`、`e2e-reddit-action-v1-20260418.md`、`main-sync-validation-20260419.md` 已统一归档到 `archived/post-migration/`。

## 6. Current Judgment

按当前状态，memory migration 的“主链迁移是否完成”已经不再取决于任何一份 `migration-*` 文档。

更准确地说：

- 代码主链：已闭合
- 测试主链：已闭合
- 正式文档主链：已闭合
- 迁移文档：当前主要只剩实施记录价值

因此，下一步已经不是“继续补迁移内容”，而是“决定如何归档迁移文档”。
