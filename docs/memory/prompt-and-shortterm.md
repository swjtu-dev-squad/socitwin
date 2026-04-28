# Prompt And Short-Term Memory

- Status: active working spec
- Audience: implementers, reviewers, AI tools
- Doc role: describe prompt assembly and short-term maintenance in current `action_v1`

## 1. Purpose

本文档讨论 `action_v1` 里的两块内容：

- prompt 是怎么被统一装配的；
- recent / compressed 是怎么维护的。

这里讲的是当前新仓库里的 short-term 主链，不是旧仓库路线里的抽象理想版本。

## 2. Core Position

当前 `action_v1` 的 short-term 层已经不再等同于默认 chat history。

它的核心结构是：

- `recent`
- `compressed`
- `recall`
- 当前 observation

其中：

- `recent`
  - 负责保住近端行为连续性；
- `compressed`
  - 负责承接 recent 驱逐后的中程背景；
- `recall`
  - 只作为 side-context；
- 当前 observation
  - 仍然是本轮最终 user turn。

## 3. Current Prompt Assembly Entry

当前 prompt 装配入口在：

- [prompt_assembler.py](/home/grayg/socitwin/backend/app/memory/prompt_assembler.py)

当前 `PromptAssembler` 是单一装配者。

它当前负责：

- 接收当前 observation prompt
- 接收 `MemoryState`
- 接收 recall candidates
- 按预算选择：
  - recent turns
  - compressed notes
  - recall note
- materialize 成最终 `openai_messages`

## 4. Current Prompt Shape

当前 prompt 的物理形态仍然保持四层结构：

1. system message
2. compressed short-term note
3. replayed recent turns
4. optional recall note
5. 当前 observation user turn

这里最关键的不是顺序本身，而是：

- current observation 永远保留为本轮最终 user turn；
- recent / compressed / recall 都不会伪装成“新的 observation”；
- recall 也不会回流成新的事实源。

## 5. Current Budget Semantics

当前 `PromptAssembler` 的预算来源是：

- `ActionV1RuntimeSettings.effective_prompt_budget`

它来自：

- `context_token_limit`
- 减去 `generation_reserve_tokens`

再继续拆成：

- `recent_budget_ratio`
- `compressed_budget_ratio`
- `recall_budget_ratio`

当前默认配置在：

- [config.py](/home/grayg/socitwin/backend/app/memory/config.py)
  - `WorkingMemoryBudgetConfig`

当前还要保留一个现实判断：

- 这套预算语义已经比旧阶段更清楚；
- 但 observation 预算和 prompt 内 recent/compressed/recall 预算仍不完全处在同一层预算面上；
- 这是后续可继续收敛的问题，不是当前 short-term 主链不存在的问题。

## 6. Current Recent Unit

当前 recent 的底层承载单位是：

- `StepSegment`

定义在：

- [episodic_memory.py](/home/grayg/socitwin/backend/app/memory/episodic_memory.py)

`StepSegment` 当前按 `StepRecordKind` 继续拆成：

- `PERCEPTION`
- `DECISION`
- `ACTION_RESULT`
- `FINAL_OUTCOME`
- `REASONING_NOISE`

这意味着当前 recent 保存的不是：

- 原始 chat history 片段
- 工具日志原文

而是：

- 一步行为合同的结构化记录

## 7. Current Recent View

recent 真正进入 prompt 时，不直接回放 raw 历史，而是先构造成受控视图。

主要逻辑位于：

- [memory_rendering.py](/home/grayg/socitwin/backend/app/memory/memory_rendering.py)
  - `build_recent_turn_view(...)`

当前 recent turn 会重建成：

- `user_view`
  - 对应当步 observation
- `assistant_view`
  - 对应结构化的 `Actions / State changes / Outcome`
- `action_keys`
  - 暴露本轮可见动作键

这条边界的意义是：

- recent 既服务于 prompt 重放；
- 也服务于 recall overlap suppression；
- 所以 recent 不能只剩下一段“给模型看的字符串”。

## 8. Recent Maintenance

当前 recent 的维护入口在：

- [consolidator.py](/home/grayg/socitwin/backend/app/memory/consolidator.py)
  - `Consolidator.maintain(...)`

它当前的处理顺序是：

1. 新 `StepSegment` 进入 `recent.segments`
2. 同步登记 `step_action_episodes`
3. 如果 recent 超出约束：
   - 按最老 step 逐步驱逐
4. 被驱逐的 step 进入 compressed 分流
5. 最后再检查 compressed 是否超预算

当前 recent 的双约束是：

- `recent_step_cap`
- `recent_budget_ratio`

也就是说：

- 不是简单保最近 N 步；
- 也不是直到最后才整体爆掉再硬截。

## 9. Evicted Step Routing

当前被 recent 驱逐的 step，不是统一变成一段纯文本。

当前分流规则是：

- 有 memory-worthy action
  - 进入 `ActionSummaryBlock`
- 没有 memory-worthy action
  - 进入 `HeartbeatRange`

对应代码主要在：

- [working_memory.py](/home/grayg/socitwin/backend/app/memory/working_memory.py)
  - `build_action_summary_block(...)`
  - `is_memory_worthy_action_episode(...)`
- [consolidator.py](/home/grayg/socitwin/backend/app/memory/consolidator.py)
  - `_consolidate_evicted_segment(...)`

## 10. Compressed Layer

当前 compressed 由两种对象组成：

- `ActionSummaryBlock`
- `HeartbeatRange`

### 10.1 ActionSummaryBlock

`ActionSummaryBlock` 负责保留：

- memory-worthy actions
- target 摘要
- local context digest
- authored excerpt
- state changes
- significance
- source action keys

它不是任意文本拼接，而是围绕 `ActionItem` 组织的结构化摘要块。

### 10.2 HeartbeatRange

`HeartbeatRange` 负责保留：

- 连续若干步里“没有可进入动作摘要块的记忆事件”
- 但仍然需要保住时间连续性和少量背景 digest

它不是动作事实替代品，而是背景连续性的保底。

## 11. Compressed Budget Enforcement

当前 compressed 的预算维护仍由 `Consolidator` 统一负责。

顺序是：

1. 先尝试 merge 最老 heartbeats
2. 再尝试 merge 最老 action blocks
3. 再 drop 最老 heartbeat
4. 最后才 drop 最老 action block

这里仍然保留了一个明确倾向：

- 优先保住动作块；
- heartbeat 更容易被合并和牺牲。

## 12. Recall Overlap Hook

当前 short-term 层还承担一个重要职责：

- 为 recall overlap suppression 提供稳定边界

对应逻辑位于：

- [working_memory.py](/home/grayg/socitwin/backend/app/memory/working_memory.py)
  - `build_recall_overlap_state_from_views(...)`
- [prompt_assembler.py](/home/grayg/socitwin/backend/app/memory/prompt_assembler.py)

当前它会基于：

- recent action keys
- recent step ids
- compressed action keys
- compressed conservative step ids

去过滤 recall candidates。

因此 recent / compressed 的结构不仅影响短期记忆保留，也直接影响 recall 是否会被 suppress。

## 13. Current Accepted Boundaries

当前 short-term 主链里需要明确接受的边界包括：

- recent 是结构化 step contract，不是原始 chat history replay；
- compressed 不是完整事实层，只是中程背景摘要层；
- heartbeat 只负责保住连续性，不替代动作事实；
- recall overlap suppression 当前依赖 recent/compressed 视图，不是独立的第三套历史语义。

## 14. Related Docs

- 当前整体实现：
  - [current-architecture.md](./current-architecture.md)
- observation 事实边界：
  - [observation-and-evidence.md](./observation-and-evidence.md)
- long-term 与 recall：
  - [longterm-and-recall.md](./longterm-and-recall.md)
