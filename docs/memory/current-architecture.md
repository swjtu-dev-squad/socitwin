# Current Memory Architecture

- Status: active working overview
- Audience: implementers, reviewers, AI tools
- Doc role: describe the current code-facing memory structure in `socitwin`

## 1. Purpose

本文档只回答一个问题：

`socitwin` 当前仓库里的记忆系统实际上是怎么组织的。

这里描述的是当前代码事实，不是旧仓库路线的理想化表述。
如果后续正式规范页与本文不一致，应先以代码核对，再决定是文档漂移还是实现偏差。

## 2. Main Entry Points

当前记忆系统的主入口主要分布在下面几处：

- [backend/app/models/simulation.py](/home/grayg/socitwin/backend/app/models/simulation.py)
  - `SimulationConfig.memory_mode`
  - API 输入面对模式的显式承载。
- [backend/app/core/oasis_manager.py](/home/grayg/socitwin/backend/app/core/oasis_manager.py)
  - 运行时初始化、mode-aware runtime build、模型/agent/env 构造、memory debug 聚合。
- [backend/app/memory/config.py](/home/grayg/socitwin/backend/app/memory/config.py)
  - `MemoryMode`
  - `ActionV1RuntimeSettings`
  - 各类 preset/config surface 与 env override。
- [backend/app/memory/runtime.py](/home/grayg/socitwin/backend/app/memory/runtime.py)
  - `MemoryRuntimeFacade`
  - mode-aware runtime build facade。
- [backend/app/memory/agent.py](/home/grayg/socitwin/backend/app/memory/agent.py)
  - `build_upstream_social_agent`
  - `build_action_v1_social_agent`
  - `ContextSocialAgent`
- [backend/app/memory/environment.py](/home/grayg/socitwin/backend/app/memory/environment.py)
  - `ActionV1SocialEnvironment`
- [backend/app/memory/](/home/grayg/socitwin/backend/app/memory)
  - observation / short-term / long-term / recall / evaluation 各子模块

## 3. Current Mode Set

当前新仓库运行代码里只保留两种模式：

- `upstream`
- `action_v1`

`baseline` 不再作为新仓库运行模式存在。
它只保留在迁移和历史文档中，作为旧仓库阶段的背景说明。

## 4. Runtime Build Flow

当前初始化主链是：

1. API / service 构造 `SimulationConfig`
2. `SimulationConfig.memory_mode` 进入 [simulation.py](/home/grayg/socitwin/backend/app/models/simulation.py)
3. [oasis_manager.py](/home/grayg/socitwin/backend/app/core/oasis_manager.py) 调用 `resolve_memory_runtime_config(...)`
4. 生成 `MemoryRuntimeFacade`
5. `MemoryRuntimeFacade.build_runtime(...)` 统一驱动：
   - `create_model`
   - `build_agent_graph`
   - `create_environment`
6. `OASISManager` 保存 `model / agent_graph / env`
7. `/api/sim/memory` 与 monitor/detail 接口从 manager 汇总 memory debug 信息

需要注意：

- 当前 `MemoryRuntimeFacade` 本身还很轻；
- 真正的模式分叉主要发生在 `OASISManager._build_social_agent(...)`、`build_upstream_social_agent(...)` 和 `build_action_v1_social_agent(...)`；
- 也就是说，现在的 facade 负责统一入口，不负责吞掉所有模式细节。

## 5. Upstream Mode

`upstream` 当前的定位是：

- 显式保留原始 OASIS 路径；
- 不接入 `action_v1` 的 observation shaping、prompt assembly、working memory、long-term、recall 主链；
- 但项目侧仍会修正原生 chat history 的上下文上限接线。

当前实现上，`upstream` 主要通过：

- [agent.py](/home/grayg/socitwin/backend/app/memory/agent.py) 中的 `build_upstream_social_agent(...)`

它做的事很少：

- 直接实例化原始 `SocialAgent`
- 当 `context_token_limit` 可用时，用项目侧 `build_chat_history_memory(...)` 重建 chat history memory

因此 `upstream` 当前仍然保留：

- 原始 `SocialAgent`
- 原始 `SocialEnvironment`
- 原始 `astep() -> memory.get_context()` 路径

但它已经不是“完全不受项目侧影响”的默认隐式模式，因为：

- `memory_mode` 已显式化；
- `context_token_limit` 会被项目侧明确传入 chat history memory；
- 状态与 debug 接口会把它作为独立模式展示。

## 6. Action_V1 Mode

`action_v1` 是当前新仓库唯一的新记忆架构主线。

它的核心接线位于：

- [agent.py](/home/grayg/socitwin/backend/app/memory/agent.py)
  - `ContextSocialAgent`
  - `build_action_v1_social_agent(...)`
- [environment.py](/home/grayg/socitwin/backend/app/memory/environment.py)
  - `ActionV1SocialEnvironment`

当前主链可以按下面顺序理解：

1. 当前步 observation 获取
   - `ActionV1SocialEnvironment.to_text_prompt()`
   - 从平台拉取：
     - `refresh()`
     - `listen_from_group()`
2. observation shaping
   - [observation_shaper.py](/home/grayg/socitwin/backend/app/memory/observation_shaper.py)
   - 产出 `ObservationArtifact`
   - 包括：
     - `observation_prompt`
     - `prompt_visible_snapshot`
     - `render_stats`
     - `visible_payload`
3. perception 与 recall 准备
   - `DefaultObservationPolicy`
   - `RecallPlanner.prepare(...)`
4. prompt 装配
   - [prompt_assembler.py](/home/grayg/socitwin/backend/app/memory/prompt_assembler.py)
   - 在 observation / recent / compressed / recall 之间做统一裁决
5. 模型决策与工具执行
   - `ContextSocialAgent._astep_with_assembled_messages(...)`
6. 结构化 step contract 写入
   - `StepSegment`
   - `StepRecord`
   - `ActionEvidence`
7. 长期记忆写入
   - `ActionEpisode`
   - long-term store
8. 短期记忆维护
   - `RecentWorkingMemory`
   - `CompressedWorkingMemory`
   - `Consolidator`

## 7. Current Module Map

当前 `backend/app/memory/` 下的主要模块职责如下：

- [config.py](/home/grayg/socitwin/backend/app/memory/config.py)
  - mode、runtime settings、preset、env override
- [environment.py](/home/grayg/socitwin/backend/app/memory/environment.py)
  - action_v1 observation 获取与 artifact 发布
- [observation_shaper.py](/home/grayg/socitwin/backend/app/memory/observation_shaper.py)
  - raw guard、long-text hard cap、interaction shrink、physical fallback
- [observation_semantics.py](/home/grayg/socitwin/backend/app/memory/observation_semantics.py)
  - prompt-visible snapshot 语义化
- [action_evidence.py](/home/grayg/socitwin/backend/app/memory/action_evidence.py)
  - 从 prompt-visible snapshot 和工具结果构建动作证据
- [working_memory.py](/home/grayg/socitwin/backend/app/memory/working_memory.py)
  - `MemoryState`、recent、compressed 结构
- [memory_rendering.py](/home/grayg/socitwin/backend/app/memory/memory_rendering.py)
  - recent/compressed 的受控渲染视图
- [consolidator.py](/home/grayg/socitwin/backend/app/memory/consolidator.py)
  - recent -> compressed 的维护与合并
- [prompt_assembler.py](/home/grayg/socitwin/backend/app/memory/prompt_assembler.py)
  - prompt 单一装配者
- [episodic_memory.py](/home/grayg/socitwin/backend/app/memory/episodic_memory.py)
  - `StepSegment`、`ActionEpisode`、`HeartbeatRange`
- [longterm.py](/home/grayg/socitwin/backend/app/memory/longterm.py)
  - long-term store、embedding、payload 序列化
- [retrieval_policy.py](/home/grayg/socitwin/backend/app/memory/retrieval_policy.py)
  - recall 结果格式化与排序辅助
- [recall_planner.py](/home/grayg/socitwin/backend/app/memory/recall_planner.py)
  - gate、query、candidate preparation
- [budget_recovery.py](/home/grayg/socitwin/backend/app/memory/budget_recovery.py)
  - budget 恢复与 observation / memory 降级
- [runtime_failures.py](/home/grayg/socitwin/backend/app/memory/runtime_failures.py)
  - provider overflow / normalized error
- [evaluation_harness.py](/home/grayg/socitwin/backend/app/memory/evaluation_harness.py)
  - 系统级 memory evaluation harness

## 8. Agent Source Support

当前 `SimulationConfig.agent_source.source_type` 支持：

- `template`
- `manual`
- `file`

并且两模式对 `file` 的处理不同：

- `upstream`
  - 继续走 OASIS 自己的 graph 生成/文件加载路径
- `action_v1`
  - 由 [oasis_manager.py](/home/grayg/socitwin/backend/app/core/oasis_manager.py) 自己解析 profile 文件
  - 再逐个构建 `ContextSocialAgent`

这意味着：

- `action_v1 + file` 已经不再依赖旧仓库 runtime 壳；
- 它使用的是新仓库自己的 parser + builder。

## 9. Current Long-Term Backends

当前 `action_v1` 的长期记忆后端重点仍是 Chroma。

主要实现位于：

- [longterm.py](/home/grayg/socitwin/backend/app/memory/longterm.py)

当前支持的 embedding 路径包括：

- `HeuristicTextEmbedding`
  - 本地 fallback / 测试用途
- `OpenAICompatibleTextEmbedding`
  - 当前工程主路线

当前文档和代码都应按这个事实理解：

- InMemory/heuristic 不是最终工程主线；
- 新仓库落地重心仍是 `Chroma + OpenAI-compatible embedding`。

## 10. Observability And Debug

当前 memory 相关观测面主要有三层：

1. manager 级 memory debug 聚合
   - [oasis_manager.py](/home/grayg/socitwin/backend/app/core/oasis_manager.py)
   - `get_memory_debug_info()`
2. 独立 memory 接口
   - `/api/sim/memory`
3. monitor/detail 聚合接口
   - `/api/sim/agents/monitor`
   - `/api/sim/agents/{agent_id}/monitor`

当前 `ContextSocialAgent.memory_debug_snapshot()` 已经能暴露：

- recent/compressed 保留步数
- observation shaping stage
- last prompt token usage
- recall gate / recalled / injected
- overlap filtered 信息
- last selected recent / compressed / recall
- recall candidate / selected item summaries

当前这层观测面已经足够支撑：

- 迁移收尾验收
- 基本调试
- harness 结果解释

但更细的 per-agent drill-down、历史链路追踪和更重的 monitor/debug 展示仍属于后续增强项，不作为本轮迁移收尾阻塞项。

## 11. Current Accepted Boundaries

当前还需要明确几个已接受的实现边界：

- 新仓库没有运行态 `baseline`
  - 只保留历史说明。
- `topic activation`
  - 通过 `ManualAction(CREATE_POST/REFRESH)` 进入平台环境；
  - 但不写入普通 `ActionEpisode` 主链；
  - 当前把它视为环境种子，而不是 agent 自主记忆事件。
- `MemoryRuntimeFacade`
  - 当前仍是轻 facade；
  - 模式语义没有被抽成更重的独立 runtime helper。
- monitor/debug
  - 当前聚合输出已足够支撑迁移完成态；
  - 更细的 per-agent drill-down 继续留作后续增强。
- memory 工程化清理
  - `backend/app/memory/__init__.py` 当前 facade 仍偏宽；
  - `agent.py`、`config.py`、`evaluation_harness.py` 当前仍偏大；
  - 这些属于迁移后的结构清理项，不阻塞本轮迁移收尾。

这些边界目前不作为迁移阻塞项，但文档里必须写清楚，避免后续误判。

## 12. Related Docs

- 模式原则与硬约束：
  - [principles-and-modes.md](./principles-and-modes.md)
- 迁移记录与旧仓库映射：
  - [migration-plan.md](./archived/migration/migration-plan.md)
  - [migration-module-mapping.md](./archived/migration/migration-module-mapping.md)
  - [migration-documentation-plan.md](./archived/migration/migration-documentation-plan.md)
