# Validation Scenarios

- Status: active reference
- Audience: implementers, reviewers, evaluators
- Doc role: scenario catalog for current memory-route regression and fidelity validation

## 1. Purpose

本页不重新定义架构，也不替代测试计划。

它负责回答：

- memory 主链应该用哪些场景去验证；
- 每类场景最少看哪些证据；
- 这些场景和审查台账里的哪些 `AUD-*` 条目对应。

## 2. How To Use

当前建议按下面顺序使用：

1. 先在 [audit-and-validation.md](./audit-and-validation.md) 找目标 `AUD-*`
2. 再在本页找对应 `VAL-*` 场景
3. 修代码后至少补一条场景级验证记录
4. 系统级自动化运行入口再回到 [testing-and-evaluation.md](./testing-and-evaluation.md)

## 3. Evidence Checklist

大多数场景至少要抽样查看这些证据之一：

- `render_stats`
- `last_prompt_visible_snapshot`
- `last_prompt_assembly_result`
- `last_internal_trace`
- `persisted_action_episode_ids`
- long-term store payload
- `last_runtime_failure_category`
- `last_runtime_failure_stage`
- harness `events.jsonl`
- harness `summary.json`

## 4. Current Automatically Covered Set

当前 harness 或单测已经明确覆盖了第一批场景：

- `VAL-OBS-01`
- `VAL-OBS-03`
- `VAL-LTM-01`
- `VAL-LTM-02`
- `VAL-RCL-02`
- `VAL-RCL-06`
- `VAL-RCL-07`
- `VAL-BGT-01`
- `VAL-LTM-05`
- `VAL-RCL-08`
- `VAL-RCL-09`
- `VAL-RCL-10`

这不代表所有这些场景都已经有完整行为级人工判读。
当前更准确的说法是：

- 结构化验证和第一版真实 probe 已存在；
- 更长窗口、更强语义判读仍需要继续积累。

## 5. Scenario Set

### `VAL-OBS-01` 长文本帖子保真

- 关联审查项：
  - `AUD-OBS-01`
- 目标：
  - 检查长 post 在 hard cap / interaction shrink / fallback 后，主体语义是否仍能沿 snapshot -> episode -> recall 链保留下来。
- 最少检查：
  - `render_stats.final_shaping_stage`
  - `truncated_field_count`
  - `prompt_visible_snapshot.posts`
  - `ActionEpisode.target_snapshot`

### `VAL-OBS-02` 长评论与评论区保真

- 关联审查项：
  - `AUD-OBS-01`
- 目标：
  - 检查 comment 被压缩后，comment target 的局部语义和 parent post 关系是否仍可用于动作与记忆构造。
- 最少检查：
  - comment summary
  - `ActionEvidence.local_context.parent_post`
  - `ActionItem.target_summary`

### `VAL-OBS-03` Group 强退化阶段对照

- 关联审查项：
  - `AUD-OBS-02`
- 目标：
  - 对照 group 在 `raw_fit / interaction_reduced / physical_fallback` 下的保留形态。
- 最少检查：
  - `visible_payload.groups`
  - `prompt_visible_snapshot.groups`
  - `target_resolution_status`
  - `degraded_evidence`

### `VAL-STM-01` Recent 驱逐与短期连续性

- 关联审查项：
  - `AUD-STM-01`
- 目标：
  - 检查 recent 是否按 step 原子粒度和 count + token 双约束推进，而不是到最后临时爆掉再截。
- 最少检查：
  - `recent.segments`
  - evicted step ids
  - recent token 变化

### `VAL-STM-02` Compressed Merge 与 Heartbeat 演化

- 关联审查项：
  - `AUD-STM-01`
- 目标：
  - 检查 recent eviction 后，`ActionSummaryBlock` / `HeartbeatRange` 的生成、merge、drop 顺序是否符合当前设计。
- 最少检查：
  - `compressed.action_blocks`
  - `compressed.heartbeat_ranges`
  - `source_action_keys`
  - `covered_step_ids`

### `VAL-STM-03` Evicted Step 分流边界

- 关联审查项：
  - `AUD-STM-01`
- 目标：
  - 检查 evicted step 在离开 recent 时，是否仍遵守：
    - 有 memory-worthy action -> `ActionSummaryBlock`
    - 无 memory-worthy action -> `HeartbeatRange`
- 最少检查：
  - `compressed.action_blocks`
  - `compressed.heartbeat_ranges`
  - `source_action_keys`

### `VAL-LTM-01` Persistable / Non-persistable 对照

- 关联审查项：
  - `AUD-LTM-01`
- 目标：
  - 验证 `ActionEpisode` 在 `success / failed / hallucinated / invalid_target` 下的持久化边界。
- 最少检查：
  - `persisted_action_episode_ids`
  - long-term store payload
  - `execution_status`
  - `target_resolution_status`

### `VAL-LTM-02` Observation -> Episode 传递

- 关联审查项：
  - `AUD-OBS-01`
  - `AUD-LTM-01`
- 目标：
  - 检查 prompt-visible snapshot 中的目标与局部上下文，是否正确进入 `ActionEvidence` 和 `ActionEpisode`。
- 最少检查：
  - `prompt_visible_snapshot`
  - `ActionEvidence.target_snapshot`
  - `ActionEvidence.local_context`
  - `ActionEpisode.target_snapshot`

### `VAL-LTM-03` 核心动作事件化覆盖

- 关联审查项：
  - `AUD-LTM-02`
- 目标：
  - 检查核心社交动作是否能产生稳定 `state_changes`，失败动作不会被误记成已改变世界。
- 最少检查：
  - `StepRecordKind.ACTION_RESULT.metadata.state_changes`
  - `ActionEpisode.state_changes`
  - `tool_result.success`

### `VAL-LTM-04` 多动作 Result 配对

- 关联审查项：
  - `AUD-LTM-02`
- 目标：
  - 检查一步多个动作时，result 顺序漂移不会污染 `ActionEpisode` 配对。
- 最少检查：
  - `tool_call_id`
  - `decision_records`
  - `action_result_records`
  - `ActionEpisode.state_changes`

### `VAL-LTM-05` 真实自我行为写入与可检索性

- 关联审查项：
  - `AUD-RCL-02`
- 目标：
  - 检查真实运行写入后的 episode，能否在 long-term store 中被按自身语义回查命中。
- 最少检查：
  - real-scenarios 事件结果
  - `hit@k`
  - `MRR`
  - cross-agent mismatch

### `VAL-RCL-01` Recall 负例

- 关联审查项：
  - `AUD-RCL-01`
- 目标：
  - 没发生过的行为不能被伪造召回；弱线索 observation 不应无条件触发 recall。
- 最少检查：
  - gate decision
  - retrieved candidates
  - selected recall items

### `VAL-RCL-02` 强信号 Recall Trigger

- 关联审查项：
  - `AUD-RCL-01`
- 目标：
  - 强 topic/anchor/entity/self-authored 信号出现时，gate 与 retrieval 应可被触发。
- 最少检查：
  - `gate_reason_flags`
  - recalled count
  - recalled step ids

### `VAL-RCL-03` Repeated Query / Cooldown 抑制

- 关联审查项：
  - `AUD-RCL-01`
- 目标：
  - 检查 repeated query 和 cooldown 是否按当前规则生效。
- 最少检查：
  - `gate_reason_flags.repeated_query_blocked`
  - `gate_reason_flags.cooldown_blocked`

### `VAL-RCL-04` Recall Overlap Suppression

- 关联审查项：
  - `AUD-RCL-01`
- 目标：
  - 检查已被 recent/compressed 明确覆盖的 recall candidates 是否会被合理 suppress。
- 最少检查：
  - `recall_overlap_filtered_count`
  - `recall_overlap_filtered_step_ids`
  - `recall_selection_stop_reason`

### `VAL-RCL-05` Recall Budget / Prompt Budget Stop

- 关联审查项：
  - `AUD-BGT-01`
- 目标：
  - 区分 recall 未注入是因为 overlap、recall budget 还是整体 prompt budget。
- 最少检查：
  - `recall_selection_stop_reason`
  - `recall_selection_stop_tokens`
  - `recall_selection_budget`

### `VAL-RCL-06` Side-Context 语义边界

- 关联审查项：
  - `AUD-RCL-01`
- 目标：
  - 检查 recall 进入 prompt 时仍以 note / side-context 形式存在，不伪装成当前 observation。
- 最少检查：
  - recall note render
  - assembled prompt structure

### `VAL-RCL-07` 空长期层 / 无后端边界

- 关联审查项：
  - `AUD-RCL-01`
- 目标：
  - 当 long-term 不可用或为空时，主链应退回正常 observation + short-term 路径，不制造伪 recall。
- 最少检查：
  - `clear_anchor`
  - recalled count
  - injected count

### `VAL-RCL-08` 真实行为连续性 Recall Probe

- 关联审查项：
  - `AUD-RCL-01`
- 目标：
  - 用真实运行后的 episode 构造相关 observation，检查 recall gate 和 retrieval 是否能把它带回候选。
- 最少检查：
  - real-scenarios probe 结果
  - gate decision
  - retrieved candidates
- 注意：
  - 当前是 retrieve-only probe，不执行 prompt assemble。

### `VAL-RCL-09` 空 Observation Recall Suppression

- 关联审查项：
  - `AUD-RCL-01`
- 目标：
  - 检查 long-term 非空时，空/弱 observation 不会仅因为长期层非空就触发 recall。
- 最少检查：
  - gate decision
  - recalled count
- 注意：
  - 当前也是 retrieve-only probe。

### `VAL-RCL-10` 长窗口真实 Recall 注入

- 关联审查项：
  - `AUD-RCL-01`
  - `AUD-BGT-01`
- 目标：
  - 在更长真实运行窗口下，检查 recall 是否真正进入 prompt，而不是只停留在 gate/retrieval。
- 最少检查：
  - `recall_gate_true_count`
  - `recall_recalled_trace_count`
  - `recall_injected_count`
  - `recall_overlap_filtered_count`
  - `trace_examples`

### `VAL-BGT-01` Base Prompt 过预算

- 关联审查项：
  - `AUD-BGT-01`
- 目标：
  - 检查 base prompt 自身超预算时，系统是否显式返回 `base_prompt_over_budget` 而不是静默乱截。
- 最少检查：
  - `assembly_failure_reason`
  - `budget_status`

### `VAL-BGT-02` Provider Overflow Recovery

- 关联审查项：
  - `AUD-BGT-01`
- 目标：
  - 检查 provider overflow / native overflow / heuristic overflow 是否进入统一 recovery 语义。
- 最少检查：
  - `last_runtime_failure_category`
  - `last_runtime_failure_stage`
  - recovery trace

### `VAL-MET-01` Runtime Metrics Readability

- 关联审查项：
  - `AUD-TST-01`
- 目标：
  - 检查 token、recall、observation shaping、short-term retention 等关键指标是否能稳定输出、可用于调试和测试。
- 最少检查：
  - `/api/sim/memory`
  - harness summary
  - monitor/detail memory fields

## 6. Current Priority

当前如果只做最少但高价值的持续回归，优先级建议是：

1. `VAL-OBS-01`
2. `VAL-STM-01`
3. `VAL-LTM-01`
4. `VAL-RCL-04`
5. `VAL-RCL-10`
6. `VAL-BGT-01`

这几项最直接对应：

- observation 是否压坏了
- short-term 是否维持住了
- long-term 是否写对了
- recall 是否被 overlap / budget 弄偏
- 主链是否在真实长窗口里还在工作

## 7. Related Docs

- 系统级运行入口和结果读取：
  - [testing-and-evaluation.md](./testing-and-evaluation.md)
- 当前审查台账：
  - [audit-and-validation.md](./audit-and-validation.md)
