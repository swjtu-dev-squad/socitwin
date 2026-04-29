# Prompt Trace 审查记录

- 日期：2026-04-29
- 所属计划：[audit-master-plan-20260428.md](./audit-master-plan-20260428.md)
- 阶段：A，模型交互与 prompt 事实边界
- 样本来源：
  - `backend/test-results/memory-eval/b-level-v05-s1-post-linked-final-20260426/artifacts/real-scenarios/step_audit.jsonl`
  - `backend/test-results/memory-eval/b-level-v05-s1-post-linked-final-20260426/artifacts/real-scenarios/episode_audit.jsonl`
- 目标：先确认模型每一步实际收到什么、recall 如何进入 prompt、哪些字段只是内部 metadata。本文只做第一轮 trace 审查，不进入实现修改。

## 1. 文档架构对齐

当前整理后的 audit 文档层级已经明确：

- `docs/memory/audit/audit-master-plan-20260428.md`
  - 唯一总计划。
  - 定义审查目标、阶段顺序、优先级和 memory contract 方向。
- `docs/memory/audit/implementation-audit-checklist-20260428.md`
  - 从属实现检查清单。
  - 可以补充问题簇、模块 checklist、字段使用率和验证回路。
  - 不能单独改变总计划的审查顺序。

因此本轮按 master plan 的阶段 A 继续：先看 prompt trace，再决定 `summary`、query、episode、retrieval 等底层模块怎么审查。这个顺序很关键，因为如果不先确认模型实际看到什么，后续很容易继续围绕已有字段做机械修补。

## 2. 当前代码事实

模型输入构造链路在 `ContextSocialAgent._perform_action_by_llm_action_v1()` 中：

1. `env.to_text_prompt()` 获取当前 observation。
2. `ObservationPolicy.build_perception_envelope()` 从 `prompt_visible_snapshot` 派生 `topic / semantic_anchors / entities`。
3. `RecallPlanner.prepare()` 用 perception 和 memory state 检索长期记忆。
4. `PromptAssembler.assemble()` 选择 recent / compressed / recall，组装最终 `openai_messages`。
5. `_astep_with_assembled_messages()` 调模型并执行工具。
6. `_record_step_memory_contract()` 再把结果写回 `StepSegment` / `ActionEpisode`。

代码锚点：

- `backend/app/memory/agent.py:308`
  - step 主链入口。
- `backend/app/memory/agent.py:331`
  - perception 从 observation artifact 派生。
- `backend/app/memory/agent.py:339`
  - recall prepare。
- `backend/app/memory/agent.py:366`
  - prompt assembly。
- `backend/app/memory/agent.py:427`
  - assembled messages 进入模型调用。
- `backend/app/memory/prompt_assembler.py:69`
  - 当前 observation 被包装成最终 user message。
- `backend/app/memory/prompt_assembler.py:113`
  - recent / compressed 视图构造。
- `backend/app/memory/prompt_assembler.py:156`
  - recall overlap filtering。
- `backend/app/memory/prompt_assembler.py:186`
  - recall note 预算选择。
- `backend/app/memory/retrieval_policy.py:26`
  - topic 非空时直接成为 runtime recall query。
- `backend/app/memory/observation_policy.py:41`
  - topic 来自 snapshot topics 的第一个元素。

这说明：当前 prompt 主链虽然有 recent、compressed、recall 三层，但 recall query 的上游仍主要受 `topic` 控制，而 `topic` 又来自第一条可见 post 的 summary。

## 3. Trace 1：Step 3，检索成功但全部被 overlap 过滤

样本：S1，official step 3，三个 agent 都出现相同模式。

### 3.1 可见 observation

对三个 agent，当前可见 post 基本是：

| post_id | summary |
| --- | --- |
| 6 | `One thing that bothers me about "meritocratic" elite pipelines: they often select for people who are great at navigat...` |
| 7 | `One lesson I keep coming back to: no single system produces ideal leaders. Singapore's structured pipelines give deep...` |

其中 Open Politics Advocate 看到 post 6 时，`self_authored=true`；Pragmatic Reformer 看到 post 7 时，`self_authored=true`。但当前 `relation_anchor` 仍是 `unknown`，所以 self-authored 信息没有成为显式 prompt 标签，也没有成为这一轮 gate 的触发原因。

### 3.2 Runtime recall

三个 agent 的 recall query 都是第一条 post 的 summary：

```text
One thing that bothers me about "meritocratic" elite pipelines: they often select for people who are great at navigat...
```

gate flags：

- `topic_trigger=true`
- `anchor_trigger=true`
- `recent_action_trigger=false`
- `self_authored_trigger=false`

结果：

- `recalled=2`
- `injected=0`
- `overlap_filtered=2`
- `selected_recent=[1,2]`

### 3.3 最终动作与写入

Institutional Comparer：

- `quote_post(post_id=6)`
- `like_post(post_id=7)`

Open Politics Advocate：

- `quote_post(post_id=7)`

Pragmatic Reformer：

- `quote_post(post_id=6)`

这一步暴露的事实：

- 检索不是完全失效，能召回 2 条。
- 但召回候选都和 selected recent 重叠，所以没有进入 prompt。
- 对模型来说，本步真正可用的历史主要来自 recent step 1 和 2，而不是 long-term recall note。
- `self_authored` 在 snapshot 中存在，但没有成为显式可见事实，也没有触发 recall。

### 3.4 初步判断

这里不能简单说 recall 无用，因为 recent 已经覆盖了相同历史。真正的问题是：系统目前缺少一个清晰的解释层，告诉我们“long-term recall 为什么没必要进入 prompt”。如果没有 `overlap_filtered` 字段，`recalled=2 / injected=0` 很容易被误读成 recall 注入失败。

后续设计要求：

- prompt trace 必须区分 retrieved、overlap-filtered、budget-filtered、injected。
- self-authored 信息如果对行为有意义，就不应只留在内部 snapshot。
- query 不应只等于第一条 post summary，否则在多 post observation 中，模型实际要处理的 post 7 被 query 降级为次要内容。

## 4. Trace 2：Step 8，长期记忆进入 prompt，但仍由第一条 post 控制 query

样本：S1，official step 8，Pragmatic Reformer。

### 4.1 可见 observation

可见 posts：

| post_id | author | summary |
| --- | --- | --- |
| 6 | user 1 | `One thing that bothers me about "meritocratic" elite pipelines...` |
| 9 | user 1 | `User 1 quoted a post from User 2. Quote content: I respect the nuance...` |
| 13 | user 1 | `Another angle on the elite pipeline problem...` |
| 15 | user 0 | `User 0 quoted a post from User 1. Quote content: This debate highlights...` |

### 4.2 Runtime recall

query 仍是第一条 post 6 的 summary：

```text
One thing that bothers me about "meritocratic" elite pipelines: they often select for people who are great at navigat...
```

memory selection：

- `recalled=3`
- `injected=1`
- `overlap_filtered=2`
- `selected_recent=[5,6,7]`
- `selected_compressed=["action_block:1","action_block:2","action_block:3","action_block:4"]`
- selected recall step：`4`

被注入的 long-term memory 是：

- Step 4 action 0
- `like_post(post_id=6)`
- state change：`liked_post:6`
- target summary：post 6 的截断 summary

### 4.3 最终动作与写入

本步动作：

- `like_post(post_id=15)`，成功，写入 `liked_post:15`
- `like_post(post_id=13)`，失败，但仍持久化，`state_changes=[]`

这一步暴露的事实：

- recall 确实可以进入 prompt。
- 但进入 prompt 的是“过去 like 过 post 6”，而本轮模型实际动作是 like post 15 和 post 13。
- query 由 post 6 控制，虽然当前 observation 里 post 13 / 15 也很重要。
- recall note 是否帮助了模型避免重复、保持连续性，当前无法判断。

### 4.4 初步判断

这一步体现了当前设计的核心偏差：系统把“当前看到的第一条 post”当成 recall intent，但模型真正的行动可能面向后续 post。对于多 post feed，runtime query 应该能表达：

- 当前可见对象集合；
- 哪些对象和 recent/long-term 有结构关系；
- 哪些对象最可能成为行动目标；
- agent 是否已经对这些对象做过动作。

仅用第一条 post summary 查长期记忆，会让 recall 变成“首页第一条内容相关历史”，而不是“本轮决策相关历史”。

## 5. Trace 3：Step 12，query 与注入记忆语义错位

样本：S1，official step 12，Institutional Comparer。

### 5.1 可见 observation

可见 posts：

| post_id | author | summary |
| --- | --- | --- |
| 24 | user 2 | `The thread with User 1 has sharpened my thinking. Two things are clear to me now...` |
| 26 | user 1 | `User 1 quoted a post from User 2. Quote content: This is a really thoughtful synthesis...` |

### 5.2 Runtime recall

query：

```text
The thread with User 1 has sharpened my thinking. Two things are clear to me now: 1) Elite pipelines aren't inherentl...
```

memory selection：

- `recalled=3`
- `injected=1`
- `overlap_filtered=2`
- `selected_recent=[9,10,11]`
- selected recall step：`3`

被注入的 long-term memory：

- Step 3 `quote_post(post_id=6)`
- target summary：post 6 的 `One thing that bothers me...`
- authored content：关于 structured development 与 accountability 的长 quote
- reason trace 也是 post 6 的 summary，而不是当前 query 的 post 24 summary。

### 5.3 最终动作与写入

本步动作：

- `quote_post(post_id=26)`
- `like_post(post_id=26)`

写入时两个 episode 都使用：

- `topic = post 24 summary`
- `target_snapshot = post 26 summary`
- 同一个 step-level outcome

这一步暴露的事实：

- query 来自 post 24，但模型实际操作 post 26。
- 注入记忆来自 step 3 / post 6，不是当前目标 post 26，也不是 current query post 24。
- 写入 episode 时，`topic` 和 `target_snapshot` 分属不同 post；这在结构上允许，但后续检索会混合“当前 observation 第一主题”和“实际动作目标”。

### 5.4 初步判断

这是一个比 Step 8 更典型的底层问题：当前 `topic` 不是 agent 的行动意图，也不是目标对象语义，而是 observation 排序产物。一个 `ActionEpisode` 写入时同时包含：

- topic：第一条可见 post 的 summary；
- target：实际工具调用目标 post 的 summary；
- outcome：step 级文本；
- authored content：如果是 quote/create 才存在。

这会让长期记忆 document 成为多个语义源的混合物。后续用任意一个 summary 查询时，都可能召回同主题但非目标的 episode。

## 6. Trace 4：Step 17，self-authored 内容触发长期回忆但行为含义不清

样本：S1，official step 17，Institutional Comparer。

### 6.1 可见 observation

可见 posts：

| post_id | self_authored | summary |
| --- | --- | --- |
| 35 | true | `One aspect of structured pipelines that deserves more attention: the selection criteria themselves...` |
| 38 | true | `Another comparative insight worth noting: the most resilient governance systems I've studied...` |

### 6.2 Runtime recall

query：

```text
One aspect of structured pipelines that deserves more attention: the selection criteria themselves. Most elite pipeli...
```

memory selection：

- `recalled=3`
- `injected=2`
- `overlap_filtered=1`
- `selected_recent=[14,15,16]`
- `selected_compressed=["action_block:9","action_block:12","action_block:13"]`
- selected recall steps：`[6,3]`

被注入的长期记忆：

- Step 6 `quote_post(post_id=6)`
- Step 3 `quote_post(post_id=6)`

两条都围绕早期 post 6，而不是当前 self-authored post 35 / 38。

### 6.3 最终动作与写入

本步动作为 `create_post`，新发 post 40。写入 episode：

- `action_name=create_post`
- `target_type=""`
- `target_id=null`
- `target_resolution_status=not_visible_in_prompt`
- `topic=post 35 summary`
- `authored_content=新 post 的完整文本`

### 6.4 初步判断

这里可以看到系统确实能把较远历史注入 prompt，但行为层解释仍不充分：

- 当前 observation 明确出现两个 self-authored posts。
- recall 注入的是早期 quote 过 post 6 的历史。
- 模型最后继续 create_post，可能是合理的线程延续，也可能只是模型按当前 feed 自行发挥。

现有 trace 无法回答：

- 模型是否知道 post 35/38 是自己发的；
- 注入的 step 3/6 是否影响了新 post 40；
- 是否应该召回“我最近自己发过 post 35/38”，而不是更早的 post 6 quote 历史。

这说明 self-authored 不能只作为内部 bool。若它要服务模拟行为，就必须进入 prompt-visible 事实或成为独立 recall task。

## 7. 阶段 A 结论

### 7.1 已确认事实

1. 当前模型最终输入由 system、compressed、recent、optional recall note、current observation user turn 组成。current observation 是最终 user turn，recall 不是 observation。
2. Runtime recall query 主要被 `topic` 控制，而 topic 当前是第一条可见 post summary。
3. 多 post feed 中，query 来源 post 和实际 action target post 经常不同。
4. long-term retrieval 经常成功，但 injected 数量受 overlap suppression 影响很大。
5. 有些远程记忆能进入 prompt，但现有 trace 不能证明模型行为真的使用了这些记忆。
6. self-authored 信息在 snapshot 中存在，但当前没有稳定成为 prompt 显式事实。
7. `ActionEpisode.topic`、`target_snapshot`、`outcome`、`authored_content` 可能来自不同语义层，写入后形成混合检索文档。

### 7.2 设计约束

后续重构不应从“怎么提高 Hit@3”开始，而应先满足这些约束：

1. **当前 observation 与 memory side-context 必须保持事实边界。**
   - recall note 不能伪装成当前环境。
   - recent/compressed/recall 需要能解释来源、时间和动作粒度。
2. **runtime query 必须表达决策相关性，而不只是第一条可见内容。**
   - 对多 post feed，需要至少区分 feed-level topic、object-level target candidates 和 self-authored objects。
3. **self-authored 必须有明确产品语义。**
   - 如果它要影响行为，就应显式进入模型可见上下文或成为独立 recall trigger/task。
4. **long-term memory 注入必须可解释。**
   - retrieved、filtered、selected、injected 四个阶段都应进入 trace。
5. **ActionEpisode 写入应区分 perception context 和 action target。**
   - `topic` 不应被当成 action 的语义摘要。
   - target summary 不应被第一条 post summary 淹没。
6. **行为验证要晚于 prompt trace。**
   - 先证明记忆以正确形态进入 prompt，再谈它是否改善行为。

## 8. 对后续阶段的影响

下一步可以进入 master plan 的短期优先项 2 和 3，但仍要小步推进：

1. **先做 `summary` / `topic` 的实现级审查。**
   - 目标不是立刻改成 LLM 摘要，而是先证明它在 prompt、query、episode、document 中如何传播。
2. **再做 runtime `last_recall_query_text` trace replay。**
   - 用真实 step 的 query，而不是 self-retrieval query，评估当前检索是否能找回本轮真正相关的 action target。
3. **然后才审查 weak action 的 wrong-target 归因。**
   - 因为 Step 8/12 已经显示：wrong target 不只来自 rerank，也来自 query 本身没有表达实际 action target。

## 9. 建议新增验证口径

为了避免继续只看链路是否能跑，建议后续评测至少补三个 trace 级指标：

| 指标 | 含义 |
| --- | --- |
| `query_source_object_rank` | runtime query 来自当前 observation 第几个对象；用于暴露第一条 post 依赖。 |
| `query_target_alignment` | query 来源对象是否等于本步实际 action target；用于评估 query 是否表达决策目标。 |
| `self_authored_visible_in_prompt` | self-authored 对象是否以模型可见文本形式出现，而不只是内部 snapshot bool。 |

这些指标比直接调 rerank 权重更底层，因为它们回答的是模型和记忆系统是否在围绕同一个对象说话。
