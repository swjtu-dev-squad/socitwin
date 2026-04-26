# Action V1 Memory Whitebox Flow

- Status: active audit baseline
- Audience: implementers, evaluators, future agents
- Doc role: explain how `action_v1` simulation, memory writing, retrieval, and evaluation probes actually work

## 1. Why This Exists

长期记忆评测不能把当前架构当成黑盒。

在解释 Hit@K、MRR、cross-agent contamination 之前，必须先回答：

- agent 在真实 simulation 中到底看到了什么；
- observation 如何被转成 `topic / semantic_anchors / entities`；
- tool call 如何被解析成结构化 `ActionEvidence`；
- `ActionEvidence` 如何变成 `ActionEpisode`；
- `ActionEpisode` 实际写入长期记忆的 document 是什么；
- runtime recall query 和 evaluation probe query 是否相同；
- 检索返回后如何 rerank、过滤、注入 prompt。

本页记录当前代码事实，不把现有实现预设为正确设计。

## 2. Runtime Query vs Evaluation Probe Query

当前有两条不同 query 路径。

### 2.1 Runtime recall query

真实模拟中，recall query 在每个 agent step 内由当前 observation 感知结果生成：

Code path:

- `ContextSocialAgent._perform_action_by_llm_action_v1()`
- `DefaultObservationPolicy.build_perception_envelope()`
- `RecallPlanner.prepare()`
- `RetrievalPolicy.build_request()`

构建优先级：

1. `topic`
2. `semantic_anchors`
3. `entities`
4. `recent_episodes`

语义是：

> 当前我看到了什么环境线索，因此应该从长期记忆中唤起哪些过去经历。

### 2.2 Evaluation probe query

`real-scenarios` 的 `VAL-LTM-05 real_self_action_retrievability` 不使用 runtime query。它从已写入的目标 `ActionEpisode` 反向构造 probe query：

Code path:

- `_build_real_self_action_retrievability_event()`
- `_self_retrieval_query_from_episode()`

当前 query 不是简单取第一个非空字段，而是按动作类型和长期记忆 document 的实际形态构造。它会优先保留：

1. `action_name / action_category`
2. `state_changes`
3. `target_snapshot` 中的目标摘要和目标 id
4. `local_context` 中的 parent post / group 摘要
5. `authored_content`
6. `topic`

`summary_text` 当前不是有效的 `ActionEpisode` 摘要字段，不再作为 self-retrieval query 的优先来源。

语义是：

> 如果拿这条目标 episode 自身携带的文本线索去查，能否把同一个 `(agent_id, step_id, action_index)` 找回来。

### 2.3 Why They Differ

这两条 query 的测试目标不同：

- runtime query 测“真实运行时，当前环境能不能触发合适 recall”；
- evaluation probe query 测“已经写入的 episode 是否具备可检索性”。

因此二者不同不是天然错误，但必须显式标注。否则 `VAL-LTM-05` 的 Hit@K 会被误读成真实 simulation 中的 recall 效果。

当前结论：

- `VAL-LTM-05` 是 retrieve-only / self-retrievability 指标，不等价于真实 prompt injection。
- `VAL-RCL-08` 更接近 runtime gate + retrieval，因为它会调用 `RecallPlanner.prepare()`。
- 长窗口 `real-longwindow` 才能观察实际 injected trace。

## 3. Observation to Perception

### 3.1 Raw observation source

`action_v1` 的 observation 由 `ActionV1SocialEnvironment.to_text_prompt()` 生成。

当前只主动读取：

- `posts_payload = action.refresh()`
- `groups_payload = action.listen_from_group()`

然后交给 `ObservationShaper.shape()`。

followers / follows 在 `render_observation_prompt()` 中为空字符串，不进入当前 `action_v1` observation 主链。

### 3.2 Observation shaping

`ObservationShaper` 的职责是让 observation 在预算内可渲染，同时产出两种结构：

- `observation_prompt`：给模型看的文本；
- `prompt_visible_snapshot`：给记忆系统做结构化解析的快照。

主要阶段：

1. `raw guards`
   - 对 groups 总数、comments 总数、messages 总数设置宽松保险丝；
   - 这是防止上游返回集合过大，不是常态压缩目标。
2. `long text cap`
   - 对 post / comment / group message 的极长文本做字符级裁剪。
3. `interaction shrink`
   - 如果仍超预算，优先减少 comments / messages 总量。
4. `physical fallback`
   - 最后保底，输出极小 sample/count 结构，避免 simulation 中断。

### 3.3 prompt-visible snapshot

`build_prompt_visible_snapshot()` 把可见 payload 转成统一语义对象。

Post snapshot 主要字段：

| Field | Source | Meaning | Used by |
| --- | --- | --- | --- |
| `object_kind` | fixed `"post"` | 对象类型 | evidence / anchors |
| `post_id` | upstream post | OASIS post id | target resolution / entities |
| `user_id` | upstream post | 作者 id | self-authored / entities |
| `self_authored` | `user_id == current_agent_id` | 是否当前 agent 自己写的 | recall trigger / identity audit |
| `summary` | `content_summary` or `content` clipped to 120 chars | prompt-visible 文本摘要 | topic / anchors / target document |
| `evidence_quality` | content quality heuristic | normal / degraded / omitted / missing | ActionEpisode document |
| `degraded_evidence` | content quality heuristic | 是否降级证据 | rerank penalty / diagnostics |
| `comments` | visible comments | prompt-visible comment list | local context / anchors |

Comment snapshot 主要字段：

| Field | Source | Meaning | Used by |
| --- | --- | --- | --- |
| `comment_id` | upstream comment | comment id | target resolution / entities |
| `post_id` | comment or parent post | 所属 post | target context |
| `user_id` | upstream comment | 作者 id | self-authored / entities |
| `self_authored` | `user_id == current_agent_id` | 是否当前 agent 自己写的 | identity / recall trigger |
| `summary` | comment content clipped to 96 chars | comment 文本摘要 | anchors / target document |
| `evidence_quality` | content quality heuristic | 证据质量 | diagnostics |

Group snapshot 主要字段：

| Field | Source | Meaning | Used by |
| --- | --- | --- | --- |
| `group_id` | upstream group id | group id | target resolution / entities |
| `summary` | group name clipped to 48 chars | group 名称摘要 | topic / anchors |
| `joined_group_ids` | upstream joined groups | 当前加入群组 id | group fallback target |
| `messages` | visible group messages | 群消息对象列表 | anchors / local context |

Group message snapshot 主要字段：

| Field | Source | Meaning | Used by |
| --- | --- | --- | --- |
| `message_id` | upstream message | message id | entities |
| `group_id` | upstream message | 所属 group | local context |
| `user_id` | upstream message sender | 发送者 | entities / self-authored |
| `summary` | message content clipped to 96 chars | 群消息摘要 | anchors |

### 3.4 Perception fields

`DefaultObservationPolicy.build_perception_envelope()` 从 `prompt_visible_snapshot` 静态抽取三个核心字段。

#### `topic`

来源：

- `extract_topics_from_snapshot()`
- 先遍历 posts，取每个 post 的 `summary`
- 再遍历 all_groups，取每个 group 的 `summary`
- `topic = topics[0] if topics else ""`

作用：

- runtime recall query 的最高优先级来源；
- step perception record 的 `topic`；
- `ActionEpisode.topic`；
- long-term document 的 `Topic:` 行；
- compressed action block 的 topic。

当前风险：

- `topic` 经常等于第一条可见 post 摘要，不是真正经过模型或语义算法提炼的全局主题；
- 同一场景中第一条 seed post 长期可见时，runtime recall query 可能高度重复；
- 这会让 recall 更像“按当前首页第一条内容查记忆”，而不是“按 agent 当前意图查记忆”。

#### `semantic_anchors`

来源：

- `extract_semantic_anchors_from_snapshot()`
- post -> `post#{post_id}: {summary}`
- comment -> `comment#{comment_id}: {summary}`
- group -> `group#{group_id}: {summary}`
- group message -> `group_message#{message_id}: {summary}`

作用：

- 当 `topic` 为空时，作为 runtime recall query 的第二优先级；
- 写入 `StepRecord.metadata.semantic_anchors`；
- 被 compressed action block 保存为 anchors；
- 可用于解释当前 observation 中有哪些语义锚点。

当前风险：

- anchor 是规则拼接，不是语义归纳；
- 如果 topic 总是存在，anchor 很少真正参与 runtime query；
- anchor 数量和顺序受 observation 排序影响。

#### `entities`

来源：

- `DefaultObservationPolicy._extract_entities_from_snapshot()`
- post -> `post:{post_id}`、`user:{user_id}`
- comment -> `comment:{comment_id}`、`user:{comment_user}`
- group -> `group:{group_id}`
- group message -> `group_message:{message_id}`、`group:{group_id}`、`user:{user_id}`

作用：

- 当 topic 和 anchors 都不可用时，作为 runtime recall query 的第三优先级；
- 参与 recall gate 的 entity trigger；
- 写入 perception record 的 metadata；
- 用于 heartbeat sampled entities。

当前风险：

- 默认 `min_trigger_entity_count = 0`，entity trigger 当前不是主要 gate；
- entity query 是 id 字符串拼接，语义检索价值有限；
- 对 exact target continuity 有潜在价值，但当前不是主 query 路径。

## 4. Tool Call to ActionEvidence

### 4.1 Input

模型执行后，`ContextSocialAgent._build_step_records()` 从 `ChatAgentResponse.info["tool_calls"]` 读取：

- `tool_name`
- `tool_args`
- `tool_result`
- `tool_call_id`

这些来自实际工具调用，不是 final assistant 文本。

### 4.2 ActionCapabilityRegistry

`ActionCapabilityRegistry` 定义每个动作的静态 contract：

| Field | Meaning |
| --- | --- |
| `eligible_for_longterm` | 这个动作是否有资格生成长期记忆 episode |
| `action_category` | 动作类别，如 authored_content / content_preference / relationship_change |
| `target_refs` | 从 tool args 的哪个字段解析目标对象 |
| `authored_content_key` | 从 tool args 的哪个字段提取 agent 自己写的文本 |
| `fallback_target_type` | 没有明确 target id 时的兜底 target type |

当前所有核心社交动作基本都 `eligible_for_longterm=True`，包括 `like_post` 这类弱语义动作。

### 4.3 ActionEvidence fields

`ActionEvidenceBuilder.build()` 把 tool call 解析成：

| Field | Source | Meaning | Later use |
| --- | --- | --- | --- |
| `action_name` | `tool_name` | 实际调用的工具名 | ActionEpisode.action_name |
| `eligible_for_longterm` | registry | 是否生成长期 episode | build_action_episodes 过滤 |
| `target_type` | registry + args | post / comment / user / group | target document / prompt note |
| `target_id` | tool args | 目标对象 id | target resolution / exact context |
| `target_snapshot` | prompt-visible snapshot lookup | 当步 prompt 中可见的目标对象摘要 | document / rerank / local context |
| `target_visible_in_prompt` | target_snapshot non-empty | 目标是否真的在 prompt 可见 | validity / diagnostics |
| `target_resolution_status` | target visible + tool result | visible_in_prompt / not_visible_in_prompt / invalid_target / expired_target | persist filter / document |
| `execution_status` | tool result | success / failed / hallucinated / unknown | persist filter / compressed memory |
| `local_context` | snapshot lookup | parent post / visible comments / group messages | document / prompt note |
| `authored_content` | registry authored content key | agent 本次自己写出的内容 | main retrieval signal |

当前重要边界：

- target snapshot 只从当步 `prompt_visible_snapshot` 找，找不到不代表工具一定失败；
- 如果 tool result 显式 not found 且 target 不可见，会标成 `invalid_target` / `hallucinated`；
- 如果工具成功但目标不在 prompt 中，会成为 `not_visible_in_prompt`，仍可能持久化；
- `state_changes` 不在 `ActionEvidence` 内生成，而是后续由 `PlatformMemoryAdapter.derive_state_changes()` 从 tool args/result 推导。

## 5. StepRecord and ActionEpisode Construction

### 5.1 StepRecord

每步会构造一个 `StepSegment`，其中包含多类 `StepRecord`：

| Kind | Source | Meaning |
| --- | --- | --- |
| `PERCEPTION` | assembled user message + perception metadata | 本步看到的 observation 和 recall 使用情况 |
| `DECISION` | each tool call | 模型实际选择的动作 |
| `ACTION_RESULT` | each tool result | 工具执行结果和 state changes |
| `FINAL_OUTCOME` | assistant final text | 模型对本步结果的文字说明 |
| `REASONING_NOISE` | stripped think block | 被清理的推理噪声标记 |

### 5.2 Pairing decision and result

`PlatformMemoryAdapter.build_action_episodes()` 遍历 `decision_records`。

匹配 action result 的方式：

1. 优先用 `tool_call_id` 找对应 `ACTION_RESULT`；
2. 如果没有 `tool_call_id`，退回 index 对齐。

这是必要兼容，但也是敏感边界：多 tool call 场景下，如果 `tool_call_id` 缺失且顺序错位，episode 的 result / state_changes 可能配错。

### 5.3 ActionEpisode fields

| Field | Source | Meaning | Used by |
| --- | --- | --- | --- |
| `memory_kind` | fixed | 固定为 `action_episode` | payload validation |
| `agent_id` | segment | 当前 agent | Chroma where filter / ground truth |
| `step_id` | segment | agent 本地 step id | exact hit / overlap filter |
| `action_index` | decision index | 本步第几个动作 | exact hit / overlap filter |
| `timestamp` | step timestamp | 写入时间 | rerank tie-break |
| `platform` | user_info.recsys_type | twitter / reddit | document / prompt note |
| `action_name` | tool name | 动作名 | document / prompt note / metrics |
| `action_category` | registry | 动作类别 | document / diagnostics |
| `action_fact` | formatted tool args | 可读动作事实，如 `quote_post(post_id=...)` | document / prompt note / rerank |
| `target_type` | evidence | 目标类型 | document / debug |
| `target_id` | evidence | 目标 id | document / debug |
| `target_snapshot` | evidence | prompt-visible 目标摘要 | document / rerank / prompt note |
| `target_visible_in_prompt` | evidence | 目标是否当步可见 | diagnostics |
| `target_resolution_status` | evidence | 目标解析状态 | persist filter / document |
| `execution_status` | evidence | 工具执行状态 | persist filter / compressed memory |
| `local_context` | evidence | parent post / visible comments / group context | document / prompt note |
| `authored_content` | evidence | agent 自己生成的文本 | strongest retrieval signal |
| `state_changes` | adapter | liked / followed / created 等状态变化 | document / prompt note |
| `outcome` | final assistant text fallback tool result | 本步文字结果 | document / compressed memory |
| `idle_step_gap` | previous persistable action step | 距离上个可持久动作的空转步数 | prompt note |
| `topic` | perception topic | 当前 observation 第一主题 | document / query source |
| `query_source` | adapter | topic / structured / recent source 标记 | validation |
| `action_significance` | static rule | high / medium / low | compressed memory-worthy |
| `evidence_quality` | target snapshot | target 文本证据质量 | document / diagnostics |
| `degraded_evidence` | target snapshot | target 是否降级 | rerank penalty |
| `summary_text` | currently empty | 预留摘要字段 | probe fallback / document |
| `metadata` | currently empty | 预留扩展字段 | future |

当前重要边界：

- `outcome` 是 step-level final assistant 文本，不一定是一条 action 的精确 outcome；
- `summary_text` 当前基本为空，因此 probe fallback 到它通常没有作用；
- `like_post` 等弱动作没有 `authored_content`，其可检索性主要依赖 `target_snapshot / state_changes / action_fact`；
- `action_significance=low` 不阻止长期持久化，只影响 recent 退场后是否进入 compressed action block。

## 6. Persisting ActionEpisode to Long-Term Memory

### 6.1 Persist filter

`ContextSocialAgent._partition_persistable_action_episodes()` 会过滤：

- `execution_status == hallucinated`
- `target_resolution_status == invalid_target`

其他 episode，包括 `failed`、`not_visible_in_prompt`、`low significance`，当前仍可能写入长期记忆。

### 6.2 Payload normalization

写入前：

1. `ActionEpisode.to_payload()`
2. `episode_to_payload()`
3. `_normalize_action_episode_payload()`

作用：

- 检查 required fields；
- 统一类型，如 `step_id -> int`、`timestamp -> float`、`agent_id -> str`；
- 限制 `query_source` 只能是允许值；
- 通过 JSON roundtrip 保证 payload 可序列化。

### 6.3 Document conversion

Chroma 不直接 embed 整个 JSON，而是先用 `_episode_document()` 转成文本 document。

当前 document 行包括：

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

转换目的：

- 向 embedding 提供更稳定的文本输入；
- 让结构化字段以可检索文本形式出现；
- 保留 payload 原文用于 exact key、debug、prompt rendering。

当前风险：

- document 是静态模板，不是模型摘要；
- `Outcome` 可能是 step-level；
- 弱动作虽然有 `State changes` 和 `Action`，但如果 query 只用 topic，仍可能被同主题强文本淹没。

### 6.4 Chroma payload sidecar

`SidecarChromaStorage` 会把复杂 payload 序列化到 `episode_payload_json`，因为 Chroma metadata 对复杂嵌套结构支持有限。

实际存入：

- vector: `_episode_document(payload)` 的 embedding；
- id: payload JSON 的 sha256；
- payload: 扁平字段 + `episode_payload_json`。

读取时再反序列化回完整 payload。

## 7. Retrieval, Matching, and Rerank

### 7.1 Runtime retrieval

`RecallPlanner.prepare()` 调用：

```text
longterm_store.retrieve_relevant(
  request.query_text,
  limit=request.limit,
  agent_id=current_agent_id
)
```

因此正常 runtime recall 会按当前 agent 过滤。

### 7.2 Chroma query

`ChromaLongtermStore.retrieve_relevant()` 执行：

1. embed normalized query；
2. Chroma vector search，`top_k = max(limit, limit * 3)`；
3. 如果有 `agent_id`，传入 `where: agent_id == current agent`；
4. payload 反序列化；
5. field-aware rerank；
6. 返回前 `limit` 条。

### 7.3 What is matched

第一阶段匹配分两层：

1. embedding 层匹配 query 和 `_episode_document(payload)`；
2. rerank 层用 query token 与 payload 字段做规则打分。

rerank 字段权重：

| Field | Weight |
| --- | ---: |
| `action_name` | 5 |
| `action_fact` | 5 |
| `target_snapshot` | 5 |
| `topic` | 4 |
| `authored_content` | 4 |
| `local_context` | 3 |
| `action_category` | 2 |
| `outcome` | 2 |
| `state_changes` | 1 |

如果完整 query 子串出现在字段文本中，该字段额外加倍权重。

当前风险：

- query 如果只是 topic，很多同主题 episode 都会得分；
- timestamp 作为并列排序项偏向更新 episode；
- `state_changes` 权重低，对 like/follow 这类动作的“我做过这个动作”区分力弱；
- `degraded_evidence=True` 会扣分。

## 8. Recall Gate and Runtime Filters

### 8.1 Recall gate

`RecallPlanner._should_retrieve()` 根据 request 和当前状态判断是否查库。

触发条件：

| Trigger | Source | Meaning |
| --- | --- | --- |
| `topic_trigger` | `topic` non-empty | 当前 observation 有主题文本 |
| `anchor_trigger` | `semantic_anchors` non-empty | 当前 observation 有结构化语义锚点 |
| `recent_action_trigger` | 当前 snapshot 命中 recent action target refs | 近期动作目标再次出现 |
| `self_authored_trigger` | snapshot 中有 self-authored 内容 | 自己写过的对象再次出现 |
| `entity_trigger` | entity 数达到阈值 | id 型实体足够多 |

阻断条件：

- repeated query 在 `deny_repeated_query_within_steps` 内重复；
- cooldown 内且没有 strong trigger。

当前风险：

- `topic_trigger=True` 且 topic 很容易存在，会让 gate 偏宽；
- repeated query 会抑制重复查，但也可能掩盖“当前 observation 长期没变化”的场景；
- self-authored trigger 当前是辅助触发，不等于完整自我认知机制。

### 8.2 Overlap suppression

检索到 candidates 后，`PromptAssembler` 会先根据 selected recent / compressed 构造 overlap state。

过滤逻辑：

- 如果 recalled action 的 `(step_id, action_index)` 已在 recent 或 compressed 中出现，过滤；
- 如果 recalled step 被 heartbeat 或保守 compressed block 覆盖，过滤；
- 非 action episode 如果 step 已在 recent / compressed，过滤。

目的：

> 如果短期记忆已经覆盖同一事件，就不要再从长期记忆重复注入。

当前解释口径：

- 短窗口内 recalled 但 injected=0 可能是正常 overlap suppression；
- 只有 recent/compressed 已经退场后仍长期不注入，才需要优先怀疑 recall / budget / overlap 逻辑。

## 9. Prompt Injection

`PromptAssembler.assemble()` 生成最终消息顺序：

1. system message；
2. compressed notes；
3. recent historical turns；
4. recall note；
5. current observation user message。

Recall note 由 `RetrievalPolicy.format_results()` 渲染。

ActionEpisode 被注入时主要展示：

- step / action index / platform；
- `action_fact`；
- target summary；
- parent post 或 group context；
- state changes；
- outcome；
- idle gap。

当前风险：

- recall note 是 assistant message，不是 system message；
- 注入内容来自 payload 字段模板，不是模型摘要；
- 如果 `outcome` 是 step-level，可能给模型提供不够精确的单动作结果。

## 10. Short-Term Memory Interaction

### 10.1 Recent

每步 `StepSegment` 会进入 `memory_state.recent.segments`。

recent 保留受两类限制：

- `recent_step_cap`
- recent token budget

recent 渲染成历史 observation + actions，不是完整原始 chat history。

### 10.2 Compressed

当 recent 退场，`Consolidator` 会把 evicted segment 转成：

- `ActionSummaryBlock`：如果存在 memory-worthy action；
- `HeartbeatRange`：如果没有 memory-worthy action。

`memory_worthy` 由 `execution_status` 和 `action_significance` 决定：

- hallucinated 不 worthy；
- medium / high worthy；
- low 不 worthy。

因此：

- `create_post / create_comment / send_to_group / create_group` 通常进入 compressed action block；
- `quote_post` 有 authored content 时 high，否则 medium；
- `like_post` 等 low 动作会写长期记忆，但 recent 退场后通常只进入 heartbeat。

这意味着长期记忆和短期 compressed 的分流标准不同。

## 11. Current Audit Concerns

当前已确认的关键问题和风险：

1. runtime query 与 evaluation probe query 不同，必须在报告中显式分开。
2. runtime `topic` 静态取第一条 post/group summary，可能导致 query 重复和 topic 偏置。
3. `semantic_anchors` 和 `entities` 多数时候只是后备路径，实际触发权重需要用 trace 验证。
4. `ActionEvidence` 依赖 prompt-visible snapshot 解析目标，target 不可见但工具成功的情况需要单独解释。
5. `ActionEpisode.outcome` 是 step-level final text，不一定是单 action outcome。
6. 弱动作 `like/follow/repost` 的长期 document 有结构，但 evaluation probe query 如果退化成 topic，会测不出动作事实。
7. `state_changes` 对弱动作很关键，但 rerank 权重低。
8. long-term persist 比 compressed 更宽：low significance 动作会进长期层，但不一定进 compressed action block。
9. overlap suppression 在短窗口内会让 retrieved 不 injected，这不应被直接判为 recall 失败。

## 12. Immediate Evaluation Implications

后续指标解释应至少分三层：

1. `episode self-retrievability`
   - 使用 episode-derived probe query；
   - 主要检查写入 document 与索引质量；
   - 不等于真实 runtime recall。
2. `runtime gate + retrieval`
   - 使用 `RecallPlanner.prepare()`；
   - 检查当前 observation 是否能触发 query 和候选。
3. `full prompt injection`
   - 检查 retrieved candidate 是否经过 overlap / budget 后进入 prompt；
   - 需要长窗口或专门场景。

主 retrieval KPI 不应继续把所有动作混成一个分数解释。第一版更合理的拆法是：

- semantic authored actions：`create_post`、`quote_post`、`create_comment`、`send_to_group`；
- weak state actions：`like_post`、`follow`、`repost` 等单独作为诊断项。
