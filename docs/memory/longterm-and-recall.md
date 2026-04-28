# Long-Term And Recall

- Status: active working spec
- Audience: implementers, reviewers, AI tools
- Doc role: describe the current ActionEpisode, persistence, retrieval, and recall path in `action_v1`

## 1. Purpose

本文档讨论 `action_v1` 的长期记忆与 recall 主链。

重点包括：

- 长期记忆写入单位是什么；
- 何时写、写什么；
- recall 何时触发；
- recall 如何作为 side-context 回到 prompt。

## 2. Core Position

当前 `action_v1` 的长期层目标不是复刻整段 chat history，而是：

- 以动作为中心记录可检索事实；
- 让 recall 在正确时机回到 prompt；
- 防止 recall 原文重新污染 observation 和长期事实边界。

## 3. Current Long-Term Unit

当前长期层的主单位是：

- `ActionEpisode`

定义在：

- [episodic_memory.py](/home/grayg/socitwin/backend/app/memory/episodic_memory.py)

它当前至少承载：

- `agent_id`
- `step_id`
- `action_index`
- `timestamp`
- `platform`
- `action_name`
- `action_category`
- `action_fact`
- `target_type`
- `target_id`
- `target_snapshot`
- `target_visible_in_prompt`
- `target_resolution_status`
- `execution_status`
- `local_context`
- `authored_content`
- `state_changes`
- `outcome`
- `idle_step_gap`
- `topic`
- `query_source`
- `evidence_quality`
- `degraded_evidence`
- `action_significance`

这说明当前长期层已经不是“写一段摘要文本”，而是围绕动作、目标、局部语境和结果组织的结构化单元。

## 4. Write Timing

当前长期记忆写入发生在 step close 之后，而不是等它离开 recent 之后。

主要链路在：

- [agent.py](/home/grayg/socitwin/backend/app/memory/agent.py)
  - `_record_step_memory_contract(...)`
  - `_persist_action_episodes(...)`

当前顺序是：

1. 本步 response 生成完成
2. 构造 `StepSegment`
3. 平台 adapter 生成 `ActionEpisode`
4. 先判断哪些 episode 可持久化
5. 立即写入 long-term store
6. 再交给 consolidator 维护 short-term

这条边界很关键，因为它说明：

- long-term persistence 不依赖 recent eviction；
- short-term 和 long-term 共享事实链，但不共享写入时机。

## 5. Persistable Boundary

当前并不是所有 episode 都会进入长期层。

当前过滤规则主要是：

- `execution_status == hallucinated`
  - 不持久化
- `target_resolution_status == invalid_target`
  - 不持久化

这条边界的目的是：

- 避免明显伪造目标或无效执行结果进入长期层；
- 让后续 recall 尽量依赖较可信的 episode。

## 6. Platform Adapter

`ActionEpisode` 的生成当前不是散落在多处，而是由 platform adapter 统一负责。

主要入口在：

- [episodic_memory.py](/home/grayg/socitwin/backend/app/memory/episodic_memory.py)
  - `PlatformMemoryAdapter`
  - `build_action_episodes(...)`

adapter 当前负责：

- 从 `StepSegment` 里抽 perception / decision / action_result / outcome
- 结合 `ActionEvidence`
- 生成结构化 `ActionEpisode`

这意味着长期层和 short-term 层当前共享同一条 step contract 事实链，而不是各自发明一套动作摘要模型。

### 6.1 `outcome` 的当前来源与边界

`ActionEpisode.outcome` 当前不是长期层单独生成的“动作级总结”，而是从 `StepSegment` 里抽取出来的 step 级结果字段。

当前优先级是：

1. `FINAL_OUTCOME`
   - 对应模型在本轮 tool call 之后留下的最终 assistant 文本；
   - 会先去掉 think block，再作为 `StepRecordKind.FINAL_OUTCOME` 进入 `StepSegment`。
2. `ACTION_RESULT`
   - 如果没有最终 assistant 文本，就退回到 tool result 的字符串结果。
3. `DECISION`
   - 如果既没有最终 assistant 文本，也没有可用 tool result，就退回动作决策文本本身。

这说明当前 `outcome` 更准确的定义是：

- “本 step 最终留下来的结果性文本”

而不是：

- “每个 action 独立计算出来的严格动作结果摘要”

当前还有一个需要明确记录的实现边界：

- 一步如果包含多个动作，当前多个 `ActionEpisode` 会共享同一个 step 级 `outcome`；
- 因为 adapter 目前是先对整个 `StepSegment` 抽一次 `outcome`，再分发给本步内每个 `ActionEpisode`。

这在“一步一个动作”的常态下通常够用，但在“一步多动作”场景下会带来两个风险：

- `outcome` 更像该步总结果，而不是某个单动作的专属结果；
- 如果最终 assistant 文本只解释了其中一个动作，其他 action episode 也会继承同一条 `outcome`。

当前工程判断：

- 该字段可以继续保留，因为它至少提供了一个稳定的结果文本兜底；
- 但后续审查和优化时，不能把它误认为已经实现了动作级 outcome 对齐；
- 如果后续出现多动作 step 增多、或 recall 过度依赖 `outcome` 的问题，应优先考虑补“按 action 粒度生成 outcome digest”，而不是继续扩大这个 step 级字段的语义。

## 7. Current Long-Term Backends

当前长期层的后端重点仍是 Chroma。

主要实现位于：

- [longterm.py](/home/grayg/socitwin/backend/app/memory/longterm.py)

当前支持：

- `ChromaLongtermStore`
- `HeuristicTextEmbedding`
- `OpenAICompatibleTextEmbedding`

当前工程判断仍然是：

- `HeuristicTextEmbedding` 主要用于本地 fallback / 测试
- 工程落地主路线仍是：
  - `Chroma + OpenAI-compatible embedding`

这里再补一个当前已经明确的运行判断：

- `HeuristicTextEmbedding` 可以继续作为显式配置存在；
- 但不再作为 `openai_compatible` 失败后的自动兼容回退；
- 当前如果 `action_v1` 选择真实 embedding 路线，就应该在启动期先完成 preflight；
- 若 embedding 服务或指定模型不可用，应直接报错并拒绝启动，而不是静默降级到 heuristic。

这样做是为了保持：

- 同一 simulation 内部的 embedding 空间一致；
- recall 评测和实验报告可解释；
- Chroma collection 的语义边界清晰。

后续如果要增强可用性，更合理的方向不是跨到 heuristic，而是：

- 在 `openai_compatible` 后端内部做 embedding 模型候选和启动期回退；
- 并把本次 simulation 的实际生效模型暴露到状态和测试结果里。

## 8. Recall Entry

当前 recall 入口在：

- [recall_planner.py](/home/grayg/socitwin/backend/app/memory/recall_planner.py)

主要对象包括：

- `RecallPlanner`
- `RecallPreparation`
- `RecallRuntimeState`

`prepare(...)` 当前会接收：

- `topic`
- `semantic_anchors`
- `entities`
- `snapshot`
- `memory_state`
- `longterm_store`
- `next_step_id`
- `runtime_state`

并输出：

- query source
- query text
- candidates
- recalled step ids
- gate decision
- gate reason flags

## 9. Current Recall Gate

当前 recall gate 不是“长期层非空就查”，而是看是否有触发信号。

当前主要 trigger 包括：

- `topic_trigger`
- `anchor_trigger`
- `recent_action_trigger`
- `self_authored_trigger`
- `entity_trigger`

同时还会受到两类约束：

- `cooldown_steps`
- `deny_repeated_query_within_steps`

所以当前 recall gate 的结构是：

- 先判断有没有足够强的触发信号；
- 再判断是否被 cooldown/repeated-query 抑制；
- 通过后才真正去 long-term store 检索。

## 10. Recent-Action Rehit

当前 recall 还有一个值得保留的触发逻辑：

- `recent_action_trigger`

它会检查：

- 最近两步 recent 里出现过的 target refs
- 是否在当前 snapshot 里再次出现

这条路径的作用是：

- 让“刚发生过的相关动作再次被环境提起”时，recall 更容易被触发；
- 但它依赖的不是外部黑盒，而是 recent + snapshot 的结构化可见实体。

## 11. Current Self-Authored Trigger

当前 recall 已经支持：

- `allow_self_authored_trigger`

它并不意味着完整“自我认知机制”已经进入模型主链，而是：

- 若当前 snapshot 中出现 `relation_anchor == self_authored`
- recall gate 可以把它作为一种触发信号

因此当前 `self_authored` 在 recall 侧已经开始有实际作用，但仍然主要体现在：

- trigger 条件

而不是：

- 检索排序显式加权
- 统一的自我记忆主逻辑

## 12. Recall Commit And Injection

当前 recall 不只是检索，还要经过选择后再 commit 到 runtime state。

主要逻辑分成两步：

1. `RecallPlanner.prepare(...)`
   - 决定要不要检索、检索到了什么
2. `PromptAssembler.assemble(...)`
   - 决定哪些 recall candidates 真正进入 prompt
3. `RecallPlanner.commit_selection(...)`
   - 回写：
     - recalled count
     - injected count
     - recalled/injected step ids
     - injected action keys
     - reason trace

这意味着当前要看 recall 表现，必须区分：

- gate 是否打开
- retrieval 是否命中
- injected 是否真正进入 prompt

这三件事不能混成一个指标。

## 13. Overlap Suppression

当前 recall 仍然有 overlap suppression。

它当前主要发生在：

- [prompt_assembler.py](/home/grayg/socitwin/backend/app/memory/prompt_assembler.py)

抑制依据来自：

- recent turn views
- compressed notes
- action keys / step ids

当前这条边界的意义是：

- recall 不是越多越好；
- 已经被 recent/compressed 明确覆盖的动作，不应无意义重复注入 prompt。

因此，当出现：

- recalled > 0
- injected = 0

时，不能直接判定为 recall 主链失效，还要继续区分：

- 被 overlap suppression 挡掉
- 被 recall budget 挡掉
- 被 overall prompt budget 挡掉

## 14. Current Accepted Boundaries

当前长期层和 recall 主链需要明确接受的边界包括：

- 长期层只围绕 `ActionEpisode` 做结构化持久化；
- 不是所有 OASIS 原始动作都进入 `ActionEpisode` 主链的一等公民集合；
- recall 只作为 side-context，不回流成新事实源；
- overlap suppression 当前是主链的一部分，不是可随意删除的附加装饰。

## 15. Related Docs

- 当前整体实现：
  - [current-architecture.md](./current-architecture.md)
- observation/evidence 事实边界：
  - [observation-and-evidence.md](./observation-and-evidence.md)
- prompt 与 short-term：
  - [prompt-and-shortterm.md](./prompt-and-shortterm.md)
- testing 与评测：
  - [testing-and-evaluation.md](./testing-and-evaluation.md)
