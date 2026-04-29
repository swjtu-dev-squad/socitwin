# ActionEpisode Field Audit

- Date: 2026-04-29
- Scope: `ActionEpisode` 字段定义、构建、序列化、长期检索文档、working memory 压缩和 S1 episode audit 字段分布
- Related plan: [audit-master-plan-20260428.md](./audit-master-plan-20260428.md)
- Depends on:
  - [prompt-trace-audit-20260429.md](./prompt-trace-audit-20260429.md)
  - [summary-topic-audit-20260429.md](./summary-topic-audit-20260429.md)
  - [runtime-query-trace-replay-20260429.md](./runtime-query-trace-replay-20260429.md)

## 1. 审查结论

`ActionEpisode` 当前已经捕获了很多有价值的行为事实，特别是：

- action 名称和原始 action fact；
- action target 的 type/id/snapshot；
- target 是否在 prompt 中可见；
- execution status；
- state changes；
- authored content。

但它的问题也很集中：字段没有按生命周期和职责分层，导致 pre-action recall 信号、post-action target evidence、long-term retrieval index、debug trace 被压在同一个扁平 schema 里。

最关键的问题不是字段“多”，而是字段的语义边界不清：

- `topic` 看起来像 episode 主题，实际是 pre-action perception 的 first-visible-post excerpt；
- `query_source` 只记录 query 类别，不记录真实 query text 或 query 来源对象；
- `target_snapshot` 是最强事实字段，但没有 target rank、query-target alignment、target 与 query source 的关系；
- `summary_text` 和 `metadata` 在当前 action episode payload 中始终为空；
- `action_significance` 影响 working memory 压缩，但不影响 long-term 持久化；
- `outcome` 是 step 级或最终响应级文本，不是严格的 per-action outcome。

因此后续重构不应先删字段，而应先把 `ActionEpisode` 拆成更清楚的事实层：identity、pre-action context、action command、target evidence、execution result、retrieval/index metadata、debug trace。

## 2. 当前代码事实

### 2.1 字段定义

`backend/app/memory/episodic_memory.py` 中 `ActionEpisode` 字段包括：

| 字段组 | 字段 |
| --- | --- |
| identity/order | `agent_id`, `step_id`, `action_index`, `timestamp`, `platform` |
| action command | `action_name`, `action_category`, `action_fact` |
| target evidence | `target_type`, `target_id`, `target_snapshot`, `target_visible_in_prompt`, `target_resolution_status`, `local_context` |
| generated content | `authored_content` |
| execution result | `execution_status`, `state_changes`, `outcome`, `idle_step_gap` |
| recall/context | `topic`, `query_source` |
| indexing/control | `evidence_quality`, `degraded_evidence`, `action_significance` |

`to_payload()` 额外写入：

- `memory_kind = "action_episode"`
- `summary_text = ""`
- `metadata = {}`

### 2.2 构建链路

`PlatformMemoryAdapter.build_action_episodes()` 从 `StepSegment` 中读取：

- decision record:
  - `action_name`
  - `action`
  - `tool_call_id`
  - fallback action evidence
- action result record:
  - action evidence
  - `state_changes`
- perception record:
  - `topic`
  - semantic anchors indirectly used by legacy `EpisodeRecord`
- final/action result/decision records:
  - `outcome`

每个 action episode 都调用 `extract_topic(segment)`。这意味着同一步多个 action 会共享同一个 `topic`，即使它们指向不同 target。

### 2.3 序列化和长期文档

`longterm._normalize_action_episode_payload()` 要求 23 个 required keys，但 `action_fact`、`target_id`、`evidence_quality`、`degraded_evidence`、`summary_text`、`metadata` 不在 required set 里，虽然 normalize 后会写入。

`longterm._episode_document()` 写入：

- `Action`
- `Action name`
- `Action category`
- `Topic`
- `Target`
- `Context`
- `Authored content`
- `State changes`
- `Outcome`
- `Significance`
- `Execution status`
- `Target resolution`
- `Evidence quality`
- `Summary`

rerank 权重中：

- `target_snapshot`: 5
- `action_fact`: 5
- `topic`: 4
- `authored_content`: 4
- `local_context`: 3
- `outcome`: 2
- `state_changes`: 1

因此 `topic` 不只是记录字段，它会参与长期检索排序。

### 2.4 working memory 与 prompt 消费

`working_memory.build_action_item()` 从 `ActionEpisode` 生成压缩条目，主要使用：

- `action_fact`
- `target_type`
- `target_id`
- `target_snapshot.summary`
- `local_context`
- `authored_content`
- `state_changes`
- `execution_status`
- `target_resolution_status`
- `evidence_quality`
- `degraded_evidence`
- `action_significance`

`is_memory_worthy_action_episode()` 只把 medium/high significance 且非 hallucinated 的 action 纳入 compressed working memory。

但 long-term persistence 的过滤逻辑不同：`_partition_persistable_action_episodes()` 只排除：

- `execution_status == hallucinated`
- `target_resolution_status == invalid_target`

所以 low significance 的 likes 会进入 long-term store，但通常不会进入 compressed working memory。

## 3. S1 episode audit 字段分布

数据来源：

`backend/test-results/memory-eval/b-level-v05-s1-post-linked-final-20260426/artifacts/real-scenarios/episode_audit.jsonl`

总量：

| 指标 | 数值 |
| --- | ---: |
| episode audit records | 74 |
| persisted records | 74 |
| non-persisted records | 0 |

按 action：

| action | count |
| --- | ---: |
| `create_post` | 19 |
| `like_post` | 27 |
| `quote_post` | 18 |
| `repost` | 7 |
| `follow` | 3 |

按 category：

| category | count |
| --- | ---: |
| `authored_content` | 19 |
| `content_preference` | 27 |
| `content_propagation` | 25 |
| `relationship_change` | 3 |

按 significance：

| significance | count |
| --- | ---: |
| high | 37 |
| medium | 10 |
| low | 27 |

按 execution/resolution：

| field | value | count |
| --- | --- | ---: |
| `execution_status` | success | 65 |
| `execution_status` | failed | 9 |
| `target_resolution_status` | visible_in_prompt | 52 |
| `target_resolution_status` | not_visible_in_prompt | 22 |

关键字段空值：

| 字段 | 空值数 |
| --- | ---: |
| `summary_text` | 74 |
| `metadata` | 74 |
| `authored_content` | 37 |
| `target_snapshot` | 22 |
| `topic` | 7 |
| `evidence_quality` | 22 |

query/topic 对齐：

| 指标 | 数值 |
| --- | ---: |
| `query_source=distilled_topic` | 67 |
| `query_source=structured_event_query` | 7 |
| `topic == target_snapshot.summary` | 11 |
| `topic != target_snapshot.summary` 且二者非空 | 41 |

解释：

- 19 个 `create_post` 没有 target snapshot，但都有 authored content，这是合理的；
- 3 个 `follow` 的 target type 是 `user`，target snapshot 为空，resolution 是 `not_visible_in_prompt`，但 execution 是 success；
- 9 个 failed action 都是 visible target、空 state changes，仍被 persisted；
- 27 个 low significance likes 全部 persisted；
- `summary_text` 和 `metadata` 对 action episode 没有实际内容。

## 4. 字段职责审查

### 4.1 应保留为核心行为事实的字段

这些字段直接回答“agent 在哪一步做了什么”：

- `agent_id`
- `step_id`
- `action_index`
- `timestamp`
- `platform`
- `action_name`
- `action_fact`
- `authored_content`
- `state_changes`
- `execution_status`

其中 `action_fact` 目前是最接近原始模型工具调用的可读表示，应继续保留。后续可以考虑补充结构化 `tool_args`，但不应用字符串解析替代它。

### 4.2 应保留但需要增强 contract 的 target 字段

这些字段是当前 schema 里最有价值的事实证据：

- `target_type`
- `target_id`
- `target_snapshot`
- `target_visible_in_prompt`
- `target_resolution_status`
- `local_context`
- `evidence_quality`
- `degraded_evidence`

问题是它们只证明“目标是什么、是否可见”，没有记录“目标在模型输入中的相对位置”和“目标与 recall query 的关系”。

建议新增：

- `target_visible_rank`
- `target_prompt_object_key`
- `target_summary_source_field`
- `target_relation_to_query_source`
- `target_relation_to_self_authored_objects`

对于 `follow` 这类 user target，当前 target snapshot 为空，说明 visible snapshot 对 user 对象没有一等结构。后续至少需要从 visible posts/comments 反推：

- `user_id`
- `user_name` 或可读 label；
- user 出现在哪些 visible objects 中；
- follow 的依据对象。

否则 relationship memory 会只有 `followed_user:2` 这种稀疏事实，无法解释 agent 为什么关注这个人。

### 4.3 `topic` 应降级为 pre-action feed context

当前 `topic` 的真实来源是 perception record 的 `topic`，而该值来自 first visible post/group summary。

它不应被解释为：

- action episode 的主题；
- action target 的主题；
- 模型实际关注点；
- retrieval query 的语义意图。

更合理的短期处理：

- 保留旧 `topic` 兼容；
- 在文档和 debug view 中标明它是 `pre_action_feed_topic` 或 `first_visible_object_excerpt`；
- long-term document 中不要把它与 `Target` 放在同一主事实层；
- rerank 中降低它作为主匹配信号的地位，或者改成 background context 字段。

### 4.4 `query_source` 信息严重不足

`query_source` 目前只有：

- `distilled_topic`
- `structured_event_query`
- `recent_episodic_summary`

它没有记录：

- 本步真实 `last_recall_query_text`；
- query 来源对象；
- query 来源对象 rank；
- query 来源字段；
- recall gate reason flags；
- recalled/injected step ids；
- overlap-filtered 信息；
- query 与 action target 是否一致。

这导致 episode 只能说“当时用了 distilled_topic”，不能解释“这个 action 是否是在某条被召回记忆影响下产生的”。

建议把 pre-action recall trace 拆成结构字段，例如：

```text
recall_context:
  query_source
  query_text
  query_basis
  query_source_object_kind
  query_source_object_id
  query_source_object_rank
  gate_reason_flags
  recalled_count
  injected_count
  injected_step_ids
```

再在 action episode 层记录：

```text
query_target_alignment:
  same_object | different_visible_object | no_target | unknown
```

### 4.5 `outcome` 不是 per-action outcome

`extract_outcome(segment)` 优先取 final outcome record，其次 action result record，最后 decision record。多 action step 中每个 action episode 会共享同一个 outcome。

S1 中一些 failed like 的 outcome 是模型自然语言最终响应或后续 action 结果，例如：

- failed `like_post(post_id=10)` 的 outcome 可能是 `{'success': True, 'post_id': 22}`，这是另一个 action 的 create/quote result；
- failed likes 的 `state_changes` 为空，但 outcome 文本仍可能描述整体意图。

因此 `outcome` 更准确地说是 `step_outcome_digest`，不是 `action_result`。

建议拆分：

- `tool_result_summary`: 当前 action tool result；
- `action_state_changes`: 当前 action result 的 state changes；
- `step_final_response`: 本轮模型最终自然语言；
- `step_outcome_digest`: 可读摘要。

### 4.6 `action_significance` 同时承担策略与解释

`action_significance` 由静态规则推断：

- authored/quote with content: high；
- repost/follow: medium；
- like: low。

它目前用于 working memory 压缩筛选，但不用于 long-term persistence。S1 中 27 个 low significance `like_post` 全部 persisted。

这未必错误：likes 可以是偏好记忆，对社交模拟有价值。但它说明当前系统缺少更细的 storage/indexing policy：

- low significance action 是否进入 long-term；
- 是否降低 retrieval 权重；
- 是否只作为 preference signal；
- 是否应该聚合成 preference profile，而不是每条都作为独立 episode；
- failed low-significance action 是否应长期保留。

### 4.7 `summary_text` 与 `metadata` 当前是空壳

所有 S1 action episode 中：

- `summary_text` 为空；
- `metadata` 为空。

这两个字段可能是为未来扩展预留的，但当前会制造误导：

- long-term document 会尝试写 `Summary`，但通常没有内容；
- debug view 会展示 `summary_text`，但没有审查价值；
- metadata 没有承载 query trace、schema version、alignment 或 source info。

建议短期不要删除，而是明确用途：

- `summary_text`: 如果保留，应成为 episode-level human-readable digest，而不是永远空；
- `metadata`: 如果保留，应放 schema/version/debug trace，不应无限制塞业务事实。

## 5. 当前 schema 的底层问题

### 5.1 扁平字段混合了 pre-action 与 post-action

`topic` 和 `query_source` 是模型行动前的 recall context；`target_snapshot` 和 `state_changes` 是模型行动后的 evidence/result。

它们放在同一层时，会让下游误以为：

- topic 与 target 是同一语义对象；
- query source 与 action 目标天然相关；
- outcome 是当前 action 的结果；
- significance 是记忆价值的唯一标准。

这正是前两轮审查中看到的 query-target mismatch 的字段层根源。

### 5.2 长期检索文档没有区分主事实与背景事实

`longterm._episode_document()` 将 `Topic`、`Target`、`Authored content`、`Outcome` 都平铺为同等级文本。rerank 又对 `topic` 给了较高权重。

如果 `Topic` 只是 first-visible-post excerpt，它就不应与 action target 竞争主检索地位。

建议长期文档分段：

- Primary action fact；
- Primary target evidence；
- Authored content；
- Execution result；
- Pre-action feed context；
- Recall trace/debug context。

### 5.3 失败动作持久化策略过粗

当前只排除 hallucinated 和 invalid target。S1 中 9 个 failed action 都被 persisted。

这可能有两种合理解释：

- agent 曾尝试重复点赞，失败本身也是行为事实；
- failed action 对后续模拟帮助有限，进入长期检索会引入噪声。

当前系统没有字段或策略区分这两者。至少需要：

- failure reason；
- tool result summary；
- whether state changed；
- whether failure is due duplicate/no-op；
- whether eligible for long-term recall。

## 6. 建议的目标 schema 分层

短期不必一次重构到位，但应按下面概念重新审查字段。

### 6.1 `ActionIdentity`

```text
agent_id
step_id
action_index
timestamp
platform
schema_version
```

### 6.2 `ActionCommand`

```text
action_name
action_category
action_fact
tool_args
authored_content
```

### 6.3 `TargetEvidence`

```text
target_type
target_id
target_snapshot
target_visible_in_prompt
target_visible_rank
target_resolution_status
local_context
evidence_quality
degraded_evidence
```

### 6.4 `ExecutionResult`

```text
execution_status
tool_result_summary
state_changes
failure_reason
no_op_reason
```

### 6.5 `PreActionContext`

```text
feed_context_excerpt
visible_object_count
self_authored_visible_object_ids
semantic_anchors
```

### 6.6 `RecallTrace`

```text
query_source
query_text
query_basis
query_source_object_id
query_source_object_rank
gate_reason_flags
recalled_step_ids
injected_step_ids
overlap_filtered_step_ids
```

### 6.7 `Alignment`

```text
query_target_alignment
target_relation_to_query_source
target_relation_to_self_authored
target_relation_to_recent_actions
```

### 6.8 `IndexingPolicy`

```text
action_significance
memory_worthiness
longterm_persisted
working_memory_eligible
retrieval_weight_profile
```

## 7. 推荐的最小改造顺序

### Step 1: 只补 instrumentation 字段

先不要删除旧字段。优先补：

- `target_visible_rank`
- `query_text`
- `query_source_object_id`
- `query_source_object_rank`
- `query_target_alignment`
- `tool_result_summary`
- `failure_reason`

这些字段能直接支撑下一轮 runtime replay 和 post-linked wrong-target 分析。

### Step 2: 改 debug/evaluation，不改 retrieval 行为

让 `episode_audit.jsonl` 显示：

- topic vs target summary；
- query text vs target summary；
- target rank；
- injected memories；
- failure/no-op reason。

这样可以先建立评估事实边界。

### Step 3: 调整 long-term document 分段

在不改变 payload schema 的情况下，先调整 `_episode_document()` 输出层级：

- 将 target/action/authored content 放前面；
- 将 `topic` 改名为 `Pre-action feed context`；
- 将 execution/failure 与 debug trace 放后面。

这是低风险但能减少 retrieval 混淆的改动。

### Step 4: 再决定字段删减或 schema version

等 trace 能证明哪些字段确实无用，再考虑：

- `summary_text` 是否填充或删除；
- `metadata` 是否只放 schema/debug；
- `topic` 是否迁移为 `pre_action_feed_context`;
- `query_source` 是否迁移进 `recall_trace`。

## 8. 与后续审查的关系

本审查支持两个后续方向：

1. Long-term document/retrieval 审查：
   - 重点看 `Topic` 和 `Target` 在 embedding/rerank 中的权重与分段；
   - 判断 likes、failed/no-op actions 是否应以独立 episode 进入长期检索。
2. Recall gate/injection 审查：
   - 重点看 `query_source`、`query_text`、injected memories 与 action target 是否建立 alignment；
   - 判断当前 `topic_trigger` 是否遮蔽 self-authored/recent-action 信号。

当前阶段建议先做最小 instrumentation，而不是直接大规模 schema migration。否则很容易在没有足够 trace 的情况下，把字段从“粗糙但可审计”改成“看起来更清楚但仍无法验证”。
