# Memory Migration Decisions

- Status: active
- Audience: migration implementers, reviewers, AI tools
- Role: record the migration baseline decisions that should not drift silently

## 1. Confirmed Decisions

### 1.1 Modes kept in socitwin

新仓库迁移后只保留两条模式线：

- `upstream`
- `action_v1`

不再把旧仓库中的 `baseline` 作为新仓库运行模式迁移。

`baseline` 的处理原则：

- 不迁运行代码；
- 在文档中保留它作为旧仓库阶段性过渡路线的历史说明；
- 如后续确有实验或汇报需要，再评估是否做轻量文档级恢复，而不是默认保留一整条运行主线。

### 1.2 Memory module location

新仓库的记忆系统单独落在：

- `backend/app/memory/`

而不是继续堆进：

- `backend/app/core/`

原因：

- 记忆系统迁入后不是几个辅助函数，而是一整套子系统；
- 旧仓库需要迁入的 observation / working memory / recall / long-term / evaluation 模块很多；
- 如果继续塞进 `core/`，会让 `core/` 混入过多领域逻辑，失去“基础设施层”的边界。

### 1.3 Agent source migration boundary

`action_v1` 在新仓库第一阶段已经接入：

- `template`
- `manual`
- `file`

`agent_source=file` 当前已经补入 `action_v1`，但补法不是继续依赖上游 graph generator，而是：

- `upstream`
  - 继续允许直接走 OASIS 上游 `generate_*_agent_graph(...)`
- `action_v1`
  - 自己解析 file profile
  - 再进入新仓库自己的 `_build_social_agent(...)`

这样做的目的是：

- 不污染 `upstream` 路径；
- 不把 `action_v1` 再绕回原生 `SocialAgent`；
- 用最小实现把 `file` 纳入新仓库自己的 agent builder 体系。

原因是：

- `template/manual` 路径本来就是新仓库自己逐个构造 `UserInfo -> SocialAgent -> AgentGraph`；
- 这两条路径只需要把 agent builder 从原生 `SocialAgent` 切到 `ContextSocialAgent`，即可接入 `action_v1`；
- `file` 路径不同，它当前直接调用 OASIS 上游：
  - `generate_twitter_agent_graph(...)`
  - `generate_reddit_agent_graph(...)`
- 上游这两个函数会在内部直接创建原生 `SocialAgent`，不会经过新仓库的 `memory/runtime.py` 和 `memory/agent.py` 装配层。

因此当前的落地结论是：

- `file` 已不再是 `action_v1` 的迁移阻塞项；
- 但 `upstream` 与 `action_v1` 在 file source 下的实现路径仍然不同：
  - `upstream` 保持原生；
  - `action_v1` 走自建解析与装配。

## 2. Directory Responsibility Notes

结合当前 `socitwin` 目录结构，后端子目录职责应理解为：

- `backend/app/api/`
  - 对外 HTTP 接口层；
  - 负责请求解析、响应封装；
  - 不承载记忆主链。
- `backend/app/services/`
  - 业务协调层；
  - 负责 orchestrate 调用、状态聚合、接口输出；
  - 不承载底层记忆算法与 prompt 主链。
- `backend/app/core/`
  - 系统骨架与基础设施层；
  - 负责配置、依赖注入、OASIS manager 等通用运行基础；
  - 是 memory runtime 的接入点，但不是记忆子系统的主要存放目录。
- `backend/app/models/`
  - 数据模型层；
  - 负责请求、响应、状态、配置对象建模。
- `backend/app/utils/`
  - 通用工具层；
  - 不适合承载核心记忆路径。
- `backend/app/memory/`
  - 记忆子系统层；
  - 负责承载迁入的 observation shaping、working memory、prompt assembly、long-term、recall 等主链。

## 3. Memory Placement Rationale

把记忆系统放到 `backend/app/memory/` 的合理性在于：

- 它符合这套功能的真实规模和复杂度；
- 它能让 `action_v1` 的运行边界更清楚；
- 它能把 memory 相关单测、集成测、系统测的映射关系整理得更清晰；
- 它避免 `core/` 变成“所有复杂逻辑最后都塞进去”的杂糅目录。

当前推荐的责任关系：

- `core/oasis_manager.py`
  - 作为接入中心；
  - 调用 mode-aware memory runtime。
- `memory/*`
  - 作为实际记忆运行模块层。
- `services/simulation_service.py`
  - 负责把 memory runtime 的状态与结果组织给 API 层。
- `api/*`
  - 负责对外暴露配置、状态、调试与测试接口。

## 4. Deferred Decisions

下面这些问题尚未最终冻结：

- 前端 memory API 本轮是否只定义契约，不实现真实展示。

这些问题不影响当前先确定“两模式 + 独立 memory 目录”这两个基础边界。

当前已经采用的方向：

- memory 配置命名先采用“兼容层”策略；
  - 先支持旧仓库 `OASIS_MODEL_*` / `OASIS_V1_*`；
  - 内部再映射到新仓库 settings；
  - 等主链稳定后再考虑是否统一改名。

当前推荐但尚未最终确认的方向：

- 前端本轮不作为迁移阻塞项；
  - 先保证后端 memory 主链、配置、测试、文档完整可靠；
  - 前端只保留最小契约盘点，不抢占主链迁移优先级。
- 测试根目录统一为：
  - `backend/tests/e2e/`
  - `backend/tests/memory/unit/`
  - `backend/tests/memory/integration/`
  - `backend/tests/memory/evaluation/`

### 4.1 `file` source support in `action_v1`

`action_v1 + agent_source=file` 当前已经按下面路线落地：

- 不继续依赖 OASIS 上游 `generate_*_agent_graph()` 作为 `action_v1` 的最终装配入口；
- 读取 file profile 后，在 `socitwin` 内部重建：
  - `UserInfo`
  - `ActionV1RuntimeSettings`
  - `ContextSocialAgent`
  - `AgentGraph`

也就是说，当前补法已经把 file 路径纳入新仓库自己的 agent builder 体系，而不是继续把它留在原生 OASIS 快捷入口之外。

当前支持边界是：

- Twitter CSV：
  - 兼容上游常用字段 `name,username,user_char,description`
  - 同时兼容新仓库整理过的 `agent_id/user_name/profile/interests` 等统一字段子集
- Reddit JSON：
  - 兼容上游常用字段 `username,realname,bio,persona,age,gender,mbti,country`
  - 同时兼容统一字段子集

当前验证边界是 parser / builder 单测级别，真实 provider 级长跑仍属于更重的按需验证。

### 4.2 Memory status exposure route

memory 运行状态不继续主要堆进：

- `/api/sim/status`

当前已确认方向是：

- 保持 `/api/sim/status` 继续偏模拟总状态；
- 将 memory trace / recall / prompt budget / debug snapshot 迁到单独的 monitor/debug 接口。

原因：

- 避免 `SimulationStatus` 持续膨胀成混杂模型；
- 避免把 `upstream` 和 `action_v1` 的内部状态边界搅混；
- 更利于后续测试、调试和前端渐进接入。

### 4.3 Mode config entry

当前推荐方案：

- 在 `backend/app/models/simulation.py` 中新增显式 `memory_mode` 字段；
- 使用枚举，而不是自由字符串；
- Phase 1 默认值先设为：
  - `upstream`

原因：

- 新仓库当前实际运行行为本来就更接近原生 OASIS；
- 先用 `upstream` 作为默认值，更利于平滑引入 memory runtime facade；
- 可以把 `action_v1` 的迁入过程和默认运行行为解耦，降低回归风险。

待迁移主链稳定后，再评估默认值是否需要改成 `action_v1`。

### 4.4 Deferred model runtime packaging

旧仓库 `context/llm.py` 负责的不是记忆主 contract，而是一层模型 runtime 包装，主要包括：

- shared model runtime 构造
- `context_token_limit` 与 `generation_max_tokens` 的显式分离
- token counter 解析 / fallback
- pooled model 一致性约束

结合当前迁移定位，本轮决策应明确为：

- 不机械迁移旧 `context/llm.py` 原文件；
- 不把这层包装当成当前记忆主链未恢复的阻塞项；
- 只把其中“context / generation 语义分离”等仍有工程价值的部分，记录为后续按需补强点。

当前进一步确认：

- 新仓库已经恢复了当前运行所需的主要 runtime 语义；
- 因此这条差异当前不作为迁移完成态的阻塞项；
- 后续只有在 pooled model、统一 runtime spec、或多 backend 运行语义再次成为明确痛点时，才建议补一个更小的 helper。

原因：

- 这层属于模型基础设施包装，不是 `action_v1` 记忆语义主链本身；
- 迁移期整块搬回容易把旧壳重新带入新仓库；
- 也容易借机重新打开预算树 / token limit 语义问题，偏离本轮“保主 contract、清结构债、禁止语义重开”的边界。

## 5. Migration-As-Refactor Position

本轮迁移对记忆子系统的定位已经明确为：

- 不是机械复制旧实现；
- 也不是重新开启一轮路线级重构；
- 而是在保留当前记忆主 contract 的前提下，允许进行结构清污和小幅工程化重构。

这意味着：

- 允许清理旧仓库中不值得继续带入新仓库的结构债；
- 不允许借迁移重新打开已经多轮审查过的核心语义问题。

详细边界见：

- [`migration-refactor-principles.md`](./migration-refactor-principles.md)
