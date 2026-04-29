# Minimal Memory Instrumentation Design

- Date: 2026-04-29
- Scope: 不改变记忆行为的前提下，补齐 runtime query、visible object、action target 和 episode 写入之间的审计字段
- Related audits:
  - [prompt-trace-audit-20260429.md](./prompt-trace-audit-20260429.md)
  - [summary-topic-audit-20260429.md](./summary-topic-audit-20260429.md)
  - [runtime-query-trace-replay-20260429.md](./runtime-query-trace-replay-20260429.md)
  - [action-episode-field-audit-20260429.md](./action-episode-field-audit-20260429.md)

## 1. 目标

本设计只补 instrumentation，不改 recall 行为、不改 prompt 内容、不改 long-term document、不改 evaluation 判定。

目标是让下一轮真实运行 trace 能回答：

- runtime recall query 来自哪个 visible object；
- query 来源对象在当前 prompt-visible list 中排第几；
- action target 在当前 prompt-visible list 中排第几；
- query 来源对象与 action target 是否一致；
- 不一致时至少能标记是不同 visible object、no target、not visible target 还是未知；
- self-authored visible object 是否存在，但没有成为 query basis；
- injected memory 是否进入了 query-target mismatch 的 action step。

这一步的原则是：先让系统可审计，再决定是否重构 retrieval、episode schema 或 long-term document。

## 2. 现有可插入点

### 2.1 Pre-action recall trace

`ContextSocialAgent._perform_action_by_llm_action_v1()` 在模型调用前已经有：

- `artifact.prompt_visible_snapshot`
- `perception.topic`
- `perception.semantic_anchors`
- `recall_preparation.query_source`
- `recall_preparation.query_text`
- `recall_preparation.gate_reason_flags`
- recalled candidates

并写入 `_last_internal_trace`：

- `last_recall_gate`
- `last_recall_gate_reason_flags`
- `last_recall_query_source`
- `last_recall_query_text`
- `last_recall_candidate_items`
- overlap/filter/selection 相关字段

这是 query source instrumentation 的主切入点。

### 2.2 Post-action target evidence

`ContextSocialAgent._build_step_records()` 在模型返回后构造：

- perception record metadata；
- decision record metadata；
- action result record metadata。

这里已有：

- `prompt_visible_snapshot`
- `action_evidence`
- `tool_args`
- `tool_result`
- `state_changes`

这是 target rank、query-target alignment、tool result summary 的主切入点。

### 2.3 Audit artifact assembly

`evaluation_harness._build_real_scenario_step_audit_entry()` 已经把每个 agent 的：

- `memory_debug`
- `prompt_visible_snapshot`
- `last_action_episodes`

写入 `step_audit.jsonl`。

`_episode_audit_records_from_step()` 再从 step audit 展开 `episode_audit.jsonl`。

因此可以选择两种实现方式：

1. runtime 写入字段，audit 直接透出；
2. audit 阶段根据 `memory_debug + prompt_visible_snapshot + episode.payload` 派生字段。

本设计建议两者结合：能在 runtime 明确知道的字段在 runtime 写入，纯审计推断字段可先在 evaluation harness 派生。

## 3. 最小字段集

### 3.1 Query Source Trace

建议添加到 `memory_debug` / `_last_internal_trace`：

| 字段 | 类型 | 来源 | 说明 |
| --- | --- | --- | --- |
| `last_recall_query_text_source_field` | string | recall request 构造逻辑 | 初期可为 `topic` / `semantic_anchors` / `entities` / `recent_episode_summary` |
| `last_recall_query_source_object_kind` | string | prompt visible snapshot 匹配 | `post` / `group` / `group_message` / `unknown` |
| `last_recall_query_source_object_id` | scalar/null | prompt visible snapshot 匹配 | query text 对应的 visible object id |
| `last_recall_query_source_object_rank` | int/null | prompt visible snapshot 匹配 | 1-based rank |
| `last_recall_query_source_summary` | string | visible object summary | 与 query text 匹配的对象摘要 |
| `last_recall_self_authored_visible_object_ids` | list | prompt visible snapshot | 当前 observation 中 self-authored objects |

短期匹配规则：

- 如果 `query_source == "distilled_topic"` 且 query text 等于某个 post summary，则取第一个匹配 post；
- 如果等于 group summary，则取第一个匹配 group；
- 如果 query text 由 anchors 拼接，暂时不拆对象，`query_source_object_kind="multiple_or_structured"`；
- 如果无法匹配，标记 `unknown`，不要猜。

### 3.2 Target Trace

建议添加到 `action_evidence` metadata：

| 字段 | 类型 | 来源 | 说明 |
| --- | --- | --- | --- |
| `target_visible_rank` | int/null | prompt visible snapshot | target 在同类 visible objects 中的 1-based rank |
| `target_prompt_object_kind` | string | action evidence | `post` / `comment` / `group` / `user` / empty |
| `target_prompt_object_id` | scalar/null | action evidence | 等于 target id |
| `target_summary_source_field` | string | target snapshot | 初期可为 `summary` / `content` / `group_name` / empty |
| `target_was_self_authored` | bool/null | target snapshot | target 是否 self-authored |

短期只需要 post target 的 rank 准确。comment/group/user 可以先填 null，但保留字段。

### 3.3 Alignment Trace

建议在 audit 层派生，先不写入核心 runtime schema：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `query_target_alignment` | string | `same_object` / `different_visible_object` / `no_action_target` / `target_not_visible` / `unknown_query_source` / `unknown` |
| `query_target_same_summary` | bool | query source summary 是否等于 target summary |
| `query_source_was_self_authored` | bool/null | query source object 是否 self-authored |
| `target_rank_vs_query_rank_delta` | int/null | target rank - query source rank |
| `injected_during_mismatch` | bool | mismatch 且 `last_injected_count > 0` |

这里建议放在 `last_action_episodes[*].trace_alignment` 或 `episode_audit` 顶层派生字段里，而不是立刻塞进 `ActionEpisode.payload`。

## 4. 派生规则

### 4.1 visible object index

需要一个纯函数从 `prompt_visible_snapshot` 构造 index。

建议输出结构：

```text
visible_object_index:
  posts:
    - kind=post
      id=<post_id>
      rank=1
      summary=<summary>
      self_authored=<bool>
      user_id=<user_id>
  comments:
    - kind=comment
      id=<comment_id>
      parent_post_id=<post_id>
      rank=<within flattened comments>
      summary=<summary>
      self_authored=<bool>
  groups:
    - kind=group
      id=<group_id>
      rank=1
      summary=<summary>
      self_authored=<bool>
  group_messages:
    - kind=group_message
      id=<message_id>
      group_id=<group_id>
      rank=<within flattened messages>
      summary=<summary>
      self_authored=<bool>
```

初期不需要存完整 index 到 trace，只需要用它计算 query source 和 target rank。

### 4.2 query source object matching

输入：

- `query_source`
- `query_text`
- `prompt_visible_snapshot`

规则：

1. 如果 `query_text` 为空：返回 empty source。
2. 如果 `query_source == "distilled_topic"`：
   - 先按 post summary exact match；
   - 再按 group summary exact match；
   - 匹配成功后记录 kind/id/rank/summary/self_authored；
   - 多个 exact match 时取 rank 最小，并记录 `ambiguous_match_count`。
3. 如果 `query_source == "structured_event_query"`：
   - 初期只记录 `query_text_source_field="semantic_anchors_or_entities"`；
   - 不强行解析 anchor 字符串。
4. 如果 `query_source == "recent_episodic_summary"`：
   - 记录 `query_text_source_field="recent_episode_summary"`；
   - source object 留空。

这里使用 exact match 是有意的：它避免把审计工具变成新的语义推断系统。

### 4.3 target rank matching

输入：

- `action_evidence.target_type`
- `action_evidence.target_id`
- `prompt_visible_snapshot`

规则：

1. `target_type == "post"`：在 flattened visible posts 中按 `post_id` 找 rank。
2. `target_type == "comment"`：在 visible comments 中按 `comment_id` 找 rank，同时记录 parent post id。
3. `target_type == "group"`：在 visible groups 中按 `group_id` 找 rank。
4. `target_type == "user"`：初期不算 visible rank；后续可以从 visible posts/comments/messages 的 author/sender 反推。
5. no target action，例如 `create_post`：`target_visible_rank=null`，alignment 使用 `no_action_target`。

### 4.4 query-target alignment

输入：

- query source object；
- target evidence；
- target rank；
- memory debug injection counts。

规则：

| 条件 | alignment |
| --- | --- |
| action 无 target | `no_action_target` |
| query source object unknown | `unknown_query_source` |
| target 不在 prompt visible snapshot | `target_not_visible` |
| kind/id 相同 | `same_object` |
| query source 和 target 都 visible 但 kind/id 不同 | `different_visible_object` |
| 其他 | `unknown` |

扩展字段：

- `query_target_same_summary = query_summary == target_summary`
- `target_rank_vs_query_rank_delta = target_rank - query_rank`
- `injected_during_mismatch = alignment != same_object and last_injected_count > 0`

## 5. 建议实现切入点

### 5.1 新增纯工具模块

建议新增：

`backend/app/memory/trace_alignment.py`

职责：

- 构建 visible object index；
- match query source object；
- compute target rank；
- compute query-target alignment。

这个模块不依赖 LLM、不访问 store、不改变 runtime 行为。它只接受 dict，返回 dict，适合单元测试。

核心函数：

```python
def build_visible_object_index(prompt_visible_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    ...

def infer_query_source_trace(
    *,
    query_source: str,
    query_text: str,
    prompt_visible_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    ...

def infer_target_trace(
    *,
    action_evidence: Mapping[str, Any],
    prompt_visible_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    ...

def infer_query_target_alignment(
    *,
    query_trace: Mapping[str, Any],
    target_trace: Mapping[str, Any],
    target_type: str,
    target_id: Any,
    target_snapshot: Mapping[str, Any],
    injected_count: int,
) -> dict[str, Any]:
    ...
```

### 5.2 Runtime trace 接入

在 `ContextSocialAgent._perform_action_by_llm_action_v1()` 中，`recall_preparation` 生成后、写 `_last_internal_trace` 前，调用：

```text
infer_query_source_trace(
  query_source=recall_preparation.query_source,
  query_text=recall_preparation.query_text,
  prompt_visible_snapshot=artifact.prompt_visible_snapshot,
)
```

将结果展开到 `_last_internal_trace` 的 `last_recall_*` 字段中。

这样 `get_action_v1_memory_debug_info()` 和 `OASISManager.get_memory_debug_info()` 会自然透出，不需要新增 API。

### 5.3 Action evidence 接入

在 `ActionEvidenceBuilder.build()` 中，target snapshot 构造后，计算 target trace。

短期可以只在 metadata dict 中增加：

- `target_visible_rank`
- `target_prompt_object_kind`
- `target_prompt_object_id`
- `target_summary_source_field`
- `target_was_self_authored`

这会随 `action_evidence.to_metadata_dict()` 进入 decision/action result records，随后可被 `ActionEpisode` 或 evaluation harness 使用。

### 5.4 Audit 派生接入

在 `_build_real_scenario_step_audit_entry()` 中，对每个 `last_action_episode` 派生：

```text
trace_alignment:
  query_target_alignment
  query_target_same_summary
  query_source_was_self_authored
  target_rank_vs_query_rank_delta
  injected_during_mismatch
```

这一步可以只写到 audit artifact，不写回 payload。

优势：

- 不影响 long-term store；
- 不改变 episode payload schema；
- 不影响现有测试和线上 debug schema；
- 便于先验证字段是否有效。

## 6. 测试建议

只加 unit tests，不跑完整 simulation。

### 6.1 `trace_alignment` 单元测试

覆盖：

- first post query exact match；
- second post target rank；
- query source post 与 target post same object；
- query source post 与 target post different visible object；
- `create_post` no target；
- user target 初期 rank null；
- ambiguous summary match 记录 match count；
- empty query 返回 unknown/empty。

### 6.2 `ActionEvidenceBuilder` 单元测试

在现有 `test_action_evidence.py` 上补：

- post target rank；
- comment target rank 和 parent id；
- group target rank；
- user target rank 为空但不报错。

### 6.3 Evaluation harness 单元测试

在已有 memory evaluation harness tests 上补一个小 fixture：

- step entry 有 first post query；
- action episode target 是 second post；
- 派生 `query_target_alignment=different_visible_object`；
- `target_rank_vs_query_rank_delta=1`；
- `injected_during_mismatch` 根据 memory_debug count 判断。

## 7. 不在本轮做的事

本轮不做：

- 不改 `RetrievalPolicy.build_request()` 的 query 策略；
- 不改 `RecallPlanner` gate 逻辑；
- 不改 `ActionEpisode` payload required keys；
- 不改 long-term document；
- 不改 post-linked final lookup 判定；
- 不加入 LLM summarization；
- 不用 fuzzy semantic matching 判断 query 与 target 的相关性。

这些都需要等 instrumentation 跑出新 trace 后再做。

## 8. 验收标准

一次最小实现完成后，新的 S1 运行 artifacts 应能直接回答：

1. 每个 agent-step 的 runtime query 是否来自 first visible post；
2. 每个 action target 的 visible rank；
3. 每个 action episode 的 query-target alignment；
4. mismatch 且 injection 发生的 episode 列表；
5. self-authored visible objects 是否存在但未参与 query；
6. `episode_audit.jsonl` 是否能不靠手写 jq 就定位 wrong-target recall cases。

建议新 artifact 中至少能生成这些聚合指标：

```text
runtime_query_source_rank_distribution
action_target_rank_distribution
query_target_alignment_distribution
mismatch_with_injection_count
self_authored_visible_but_query_not_self_count
```

这些指标会直接支撑下一阶段 Long-Term Document/Retrieval 审查。

## 9. 后续顺序

推荐顺序：

1. 实现 `trace_alignment.py` 纯函数和单元测试；
2. 将 query source trace 加入 `_last_internal_trace`；
3. 将 target trace 加入 `action_evidence` metadata；
4. 在 evaluation harness 中输出 `trace_alignment`；
5. 跑一轮小规模 S1 或已有 B-level scenario；
6. 基于新 artifact 再审查 long-term document 与 rerank。

这个顺序保持最小行为风险，同时能快速验证前几轮审查提出的关键假设。
