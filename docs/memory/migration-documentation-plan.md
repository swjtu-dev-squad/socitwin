# Memory Documentation Migration Plan

- Status: active
- Audience: migration implementers, reviewers, AI tools
- Role: migrate old memory docs into new-repo official docs without mechanically copying obsolete material

## 1. Goal And Boundary

本计划只处理记忆系统相关文档迁移，不处理：

- 前端页面文档
- 通用项目介绍文档
- 与 memory 无直接关系的实验/协作文档

本轮文档迁移的目标不是把旧仓库 `docs/memory/` 原样搬到新仓库，而是把其中仍然有效的内容整理成新仓库自己的正式 memory 文档体系。

必须同时满足四条要求：

1. 只迁记忆相关文档，不顺手扩写其他模块。
2. 先尊重新仓库当前代码事实，再迁旧路线和旧审查内容。
3. 过时的阶段性叙述要舍弃，不能把旧仓库的历史包袱原样带过来。
4. 重要的架构边界、验证口径、风险台账不能在迁移中丢失。

## 2. Current Judgment

当前迁移状态需要明确区分三件事：

- 代码主链
  - 基本已经迁入新仓库。
- 测试代码主链
  - `unit / integration / evaluation harness` 主体已经恢复；
  - 但还没有沉淀成新仓库正式的测试说明、验收口径和结果解释文档。
- 文档主链
  - 目前新仓库 `docs/memory/` 仍以 `migration-*` 文档为主；
  - 这说明迁移过程文档已经很多，但新仓库正式 memory 文档体系还没有建立完成。

因此，当前文档迁移的重点不是“再补几篇迁移说明”，而是：

- 建立新仓库正式 memory 文档骨架；
- 把旧仓库里仍然有效的原则、契约、测试口径和审查台账迁进来；
- 再把 `migration-*` 降级为实施记录，而不是继续充当主文档。

当前已经完成的第一步是：

- 新仓库正式 memory 文档骨架已经开始建立；
- 第一批正式文档已落地：
  - `README.md`
  - `current-architecture.md`
  - `principles-and-modes.md`
  - `observation-and-evidence.md`
  - `prompt-and-shortterm.md`
  - `longterm-and-recall.md`
  - `config-and-runtime.md`
  - `testing-and-evaluation.md`
  - `validation-scenarios.md`
  - `audit-and-validation.md`

这意味着当前阶段已经从“只有迁移文档”进入了“正式文档与迁移文档并存”的过渡期。

## 3. Old Documentation Structure

旧仓库 `docs/memory/` 当前实际分成六层：

1. 入口与组织层
   - `README.md`
   - `overview.md`
2. 当前事实层
   - `current-architecture.md`
3. V1 规范层
   - `v1-route.md`
   - `v1-principles-and-modes.md`
   - `v1-observation-and-evidence.md`
   - `v1-prompt-assembly-and-working-memory.md`
   - `v1-longterm-and-recall.md`
   - `v1-budgets-presets-and-failure-recovery.md`
4. 审查与验证层
   - `audit.md`
   - `audit-and-validation.md`
   - `validation-scenarios.md`
   - `system-test-plan.md`
5. 配置参考层
   - `config-surfaces.md`
   - `longterm-recall-report.md`
6. 历史归档层
   - `archived/`

这个分层本身是合理的。真正需要避免的是：

- 把旧仓库三模式语义原样搬过来
  - 新仓库现在只保留 `upstream` 和 `action_v1`。
- 把旧代码路径和旧 runtime 入口继续写进新文档。
- 把阶段性测试报告误写成长期权威文档。

## 4. Migration Principles

### 4.1 Migrate By Problem Domain, Not By Filename

旧文档要按问题域迁移，而不是按文件一比一搬运。

例如：

- observation / evidence 边界迁到新仓库的 action_v1 主链文档；
- budget / runtime / env 入口迁到配置与运行文档；
- harness / metrics / result reading 迁到测试与评测文档；
- 活动风险与回归要求迁到审查台账。

### 4.2 Current Facts Override Historical Route Wording

若旧路线文档和当前新仓库实现不一致：

- 先以新仓库代码事实为准；
- 再判断旧文档里的内容是：
  - 仍然有效的原则
  - 需要改写的规范
  - 应归档的历史叙述

### 4.3 Keep Stable Boundaries, Drop Stale Wiring Details

需要保留的主要是：

- 为什么要有这条记忆路线
- 两模式边界
- observation / short-term / long-term / recall 契约
- 配置面与预算语义
- 测试口径和指标解释
- 审查台账与验证场景

不应直接迁移的主要是：

- 旧仓库 `baseline` 的正式运行模式叙述
- 只服务于旧目录结构的代码入口说明
- 只适用于旧阶段的修补性历史文字
- 单次测试结果报告被写成长期规范

### 4.4 Documentation Should Shrink, Not Re-Expand

旧仓库文档已经很大，新仓库不应继续复制出一套同体量、同复杂度的迁移版。

因此本轮目标不是“保留所有页面”，而是：

- 保留核心内容
- 合并重复页面
- 降低阅读入口复杂度
- 让正式文档和迁移记录分层

## 5. Proposed Official Documentation Set

新仓库正式 memory 文档建议最终收敛为下面 9 份：

1. `docs/memory/README.md`
   - 记忆文档总入口、阅读顺序、source of truth 说明。
2. `docs/memory/current-architecture.md`
   - 当前新仓库代码事实、两模式 wiring、主链入口和关键数据流。
3. `docs/memory/principles-and-modes.md`
   - 设计原则、`upstream` / `action_v1` 边界、非目标范围、历史说明。
4. `docs/memory/observation-and-evidence.md`
   - observation shaping、prompt-visible snapshot、evidence 边界。
5. `docs/memory/prompt-and-shortterm.md`
   - prompt assembly、recent / compressed、consolidator、短期预算边界。
6. `docs/memory/longterm-and-recall.md`
   - `ActionEpisode`、持久化、检索、recall gate、注入边界。
7. `docs/memory/config-and-runtime.md`
   - 模式、模型 runtime、预算、embedding、env/config surfaces。
8. `docs/memory/testing-and-evaluation.md`
   - 测试层次、harness phases、指标字段、结果读取、最小验收口径。
9. `docs/memory/audit-and-validation.md`
   - 活动审查台账、风险登记规则、验证记录要求；
   - `validation-scenarios` 可保留为独立配套页，也可作为本页的附属页面。

补充说明：

- `validation-scenarios.md`
  - 仍然很有价值，建议保留为独立页；
  - 它和 `testing-and-evaluation.md` 的关系应是：
    - 前者负责“测什么场景”
    - 后者负责“怎么跑、怎么看结果”
- `audit.md`
  - 不建议继续保留为单独 landing page；
  - 其职责可以并入 `README.md` 与 `audit-and-validation.md`。
- `overview.md`
  - 不建议在新仓库继续单独保留；
  - 其背景说明应合并进 `README.md` 和 `principles-and-modes.md`。
- `v1-route.md`
  - 不建议继续作为 umbrella 页面保留；
  - 新仓库应直接以专题文档集合替代它。

## 6. Old-To-New Mapping

| Old doc | Old role | Migration decision | New destination | Notes |
| --- | --- | --- | --- | --- |
| `docs/memory/README.md` | 文档索引 | `rewrite` | `docs/memory/README.md` | 保留索引职责，但改成新仓库正式入口 |
| `docs/memory/overview.md` | 背景与组织原则 | `merge` | `README.md` + `principles-and-modes.md` | 不单独保留页面 |
| `docs/memory/current-architecture.md` | 当前代码事实 | `rewrite` | `current-architecture.md` | 必须重写为新仓库代码路径 |
| `docs/memory/v1-route.md` | V1 umbrella | `dissolve` | `README.md` + 专题页 | 不建议继续保留 umbrella 壳 |
| `docs/memory/v1-principles-and-modes.md` | 原则与三模式边界 | `rewrite-and-shrink` | `principles-and-modes.md` | 去掉 `baseline` 的正式模式地位，只保留历史说明 |
| `docs/memory/v1-observation-and-evidence.md` | observation/evidence 契约 | `rewrite` | `observation-and-evidence.md` | 高价值，必须迁 |
| `docs/memory/v1-prompt-assembly-and-working-memory.md` | prompt/short-term 契约 | `rewrite` | `prompt-and-shortterm.md` | 高价值，必须迁 |
| `docs/memory/v1-longterm-and-recall.md` | long-term/recall 契约 | `rewrite` | `longterm-and-recall.md` | 高价值，必须迁 |
| `docs/memory/v1-budgets-presets-and-failure-recovery.md` | 预算/preset/failure | `split-and-rewrite` | `config-and-runtime.md` + `testing-and-evaluation.md` | 保留语义，不保留旧结构 |
| `docs/memory/audit.md` | 审查入口 | `merge` | `README.md` + `audit-and-validation.md` | 不单独保留 landing |
| `docs/memory/audit-and-validation.md` | 活动审查台账 | `rewrite` | `audit-and-validation.md` | 高价值，必须迁 |
| `docs/memory/validation-scenarios.md` | 场景目录 | `rewrite` | `validation-scenarios.md` | 高价值，建议保留独立页 |
| `docs/memory/system-test-plan.md` | harness 与指标指南 | `rewrite` | `testing-and-evaluation.md` | 必须改成新仓库命令、路径、输出 |
| `docs/memory/config-surfaces.md` | 配置面参考 | `rewrite` | `config-and-runtime.md` | 旧 env 名、旧路径必须全部改写 |
| `docs/memory/longterm-recall-report.md` | 单轮测试报告 | `archive-or-appendix` | 不作为正式主文档 | 可作为历史报告保留，但不进入正式骨架 |
| `docs/memory/archived/*` | 历史归档 | `archive-only` | 暂不迁正文 | 新仓库若需要，只迁索引，不迁内容 |

## 7. Migration Order

文档迁移建议按下面顺序进行，而不是一上来重写全部页面。

### Phase A: Freeze Doc Skeleton

先确定正式文档骨架和每份旧文档去向。

交付物：

- 本计划文档
- 新仓库正式 memory 文档清单

### Phase B: Build Official Landing And Current Facts

优先建立：

- `README.md`
- `current-architecture.md`
- `principles-and-modes.md`

原因：

- 只有先把“现在代码是什么”和“模式边界是什么”写准，后续 observation / recall / testing 文档才不会漂。

### Phase C: Port Action_V1 Mainline Specs

再迁：

- `observation-and-evidence.md`
- `prompt-and-shortterm.md`
- `longterm-and-recall.md`

要求：

- 只保留仍然成立的架构契约；
- 明确当前代码事实和未来待继续优化项；
- 不把旧仓库的过渡性实现当成新仓库正式事实。

### Phase D: Port Config And Test Docs

再迁：

- `config-and-runtime.md`
- `testing-and-evaluation.md`
- `validation-scenarios.md`

这一步是关闭“测试主链只剩代码、没有正式文档说明”的关键。

### Phase E: Port Audit Register

最后迁：

- `audit-and-validation.md`

原因：

- 审查台账必须建立在新的正式文档骨架之上；
- 否则很容易再次变成“用旧术语审新代码”。

### Phase F: Demote Migration Docs

当正式文档体系写完后，再处理当前这些：

- `migration-plan.md`
- `migration-workstreams.md`
- `migration-phase-checklists.md`
- `migration-module-mapping.md`
- `migration-config-and-testing.md`
- `migration-architecture-comparison.md`
- `migration-decisions.md`
- `migration-refactor-principles.md`
- `social-monitor-migration-plan.md`

处理方式不是立即删除，而是：

- 作为迁移实施记录保留；
- 不再作为正式 memory 使用文档的主入口。

## 8. Do Not

文档迁移过程中明确禁止：

- 把旧仓库 `baseline` 当作新仓库正式模式继续写进主文档；
- 继续用 `oasis_dashboard/...` 作为正式代码入口说明；
- 把迁移阶段的临时判断直接写成长期规范；
- 把单次测试结果报告当成正式测试方案；
- 因为怕遗漏而把所有旧文档机械复制过来。

## 9. Acceptance Criteria

文档主链迁移完成时，至少应满足：

1. 新仓库 `docs/memory/` 可以独立解释：
   - 两模式边界
   - action_v1 主链
   - 配置面
   - 测试面
   - 审查面
2. 正式文档不再依赖读者回到旧仓库才能理解主链。
3. `migration-*` 文档退回实施记录层，不再充当正式说明主体。
4. 测试主链不再只是“测试代码存在”，而是有明确的运行入口、指标解释和验收口径。

## 10. Immediate Next Step

当前第一批正式文档已经起步，下一步按以下顺序继续推进：

1. 等正式文档体系能独立解释主链后，再降级 `migration-*` 为实施记录层。
2. 后续正式文档的新增工作转为：
   - 持续补具体场景
   - 持续补审查条目
   - 持续补真实运行记录和回归证据
