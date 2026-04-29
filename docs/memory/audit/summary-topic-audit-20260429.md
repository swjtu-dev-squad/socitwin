# Summary/Topic Signal Audit

- Date: 2026-04-29
- Scope: `action_v1` 中 observation summary、perception topic、runtime recall query、`ActionEpisode.topic` 和 long-term document 的传播链路
- Related plan: [audit-master-plan-20260428.md](./audit-master-plan-20260428.md)
- Previous audit: [prompt-trace-audit-20260429.md](./prompt-trace-audit-20260429.md)

## 1. 审查结论

当前实现里，`summary` 不是语义摘要，而是固定字符数的 display excerpt；`topic` 也不是“本轮模型决策所围绕的主题”，而是可见对象列表里第一个 post/group 的 `summary`。

这两个字段随后被继续当成：

- runtime recall 的主查询文本；
- recall gate 的 topic trigger；
- `ActionEpisode.topic`；
- long-term document 的 `Topic` 字段；
- rerank scoring 的高权重字段。

因此当前系统的核心风险不是“摘要算法不够好”这么局部，而是一个显示层截断字段被复用成了语义索引、行为上下文和记忆检索意图。这个复用会让模型输入、动作目标和长期记忆写入之间产生系统性错位。

## 2. 当前代码事实

### 2.1 `summary` 的来源是硬截断

`backend/app/memory/observation_semantics.py` 中 `summarize_text()` 只做空白归一和固定长度截断：

- post prompt view: `content_summary = summarize_text(content, 120)`
- prompt visible snapshot: `summary = summarize_text(content_summary or content, 120)`
- comment summary: 96 chars
- group name summary: 48 chars
- group message summary: 96 chars

`observation_shaper.py` 的 budget recovery 也会先压缩 raw content，然后追加 `...[compacted from N chars]` 标记。随后 snapshot 构造又会在 `content_summary or content` 上二次生成 `summary`。也就是说 `summary` 可能是原文截断，也可能是已压缩文本的再次截断。

当前测试主要验证：

- `self_authored` 是否标记；
- `evidence_quality` 是否因 truncated/omitted 标记而降级；
- group/message 是否进入 snapshot。

测试没有验证 `summary` 是否能代表对象语义，也没有验证截断后的文本是否适合作为 recall query。

### 2.2 `topic` 的来源是第一个可见对象摘要

`DefaultObservationPolicy.build_perception_envelope()` 接收 `observation_prompt`，但当前默认策略直接 `del observation_prompt`，只读 `prompt_visible_snapshot`。

`extract_topics_from_snapshot()` 的逻辑是：

1. 遍历 snapshot posts；
2. 将每个 post 的 `summary` 加入 topics；
3. 遍历 groups；
4. 将 group 的 `summary` 加入 topics；
5. 去重后返回；
6. `topic = topics[0] if topics else ""`。

因此 `perception.topic` 的真实含义是：当前 snapshot 中第一个可见 post/group 的显示摘要。它不是模型看到的完整 observation prompt 的主题，不是模型实际关注对象，也不是 action target。

### 2.3 runtime recall 优先使用 `topic`

`RetrievalPolicy.build_request()` 中查询优先级是：

1. `topic` 非空时，直接返回 `query_source=distilled_topic`，`query_text=topic`；
2. 否则使用 semantic anchors；
3. 否则使用 entities；
4. 否则使用 recent episode summary。

`RecallPlanner._should_retrieve()` 中 `topic_trigger = allow_topic_trigger and bool(topic)`。在有任何可见 post/group summary 的情况下，topic trigger 很容易成为主触发条件，semantic anchors、entities、自写内容触发会被弱化成次级路径。

### 2.4 `ActionEpisode.topic` 继承同一个 topic

`PlatformMemoryAdapter.extract_topic()` 从 perception record metadata 里取第一个 `topic`。`build_action_episodes()` 对每个 action episode 写入：

- `target_snapshot`: 来自 action evidence，通常是 action 实际目标；
- `topic`: 来自 perception，也就是第一个可见对象 summary；
- `query_source`: 只要 topic 非空就是 `distilled_topic`。

如果模型实际 action target 不是第一个可见 post，就会出现同一个 episode 同时记录两个不同语义对象：

- `topic`: feed 第一个对象；
- `target_snapshot.summary`: 实际动作目标对象。

这不是字段命名的小问题，而是记忆事实边界不清：episode 的“上下文主题”和“动作目标”被写在一起，却没有说明二者是否一致。

### 2.5 long-term document 和 rerank 放大错位

`longterm._episode_document()` 会写入：

- `Topic: payload.topic`
- `Target: _target_document_text(payload)`
- `Context`
- `Authored content`
- `Outcome`
- `Summary`

rerank 权重里：

- `topic`: 4
- `target_snapshot`: 5
- `action_fact`: 5
- `authored_content`: 4

这意味着后续如果用第一个可见 post summary 做查询，系统会自然召回所有 `topic` 等于该 summary 的 episodes，即使这些 episodes 的实际 action target 是别的 post。这解释了前一轮 prompt trace 中出现的“query 指向 post A，action/target 指向 post B”的现象。

## 3. B-level S1 运行证据

基于：

`backend/test-results/memory-eval/b-level-v05-s1-post-linked-final-20260426/artifacts/real-scenarios/step_audit.jsonl`

对 official steps 做了轻量统计：

| 指标 | 数值 |
| --- | ---: |
| agent-step rows | 54 |
| nonempty runtime recall queries | 38 |
| query 等于第一个可见 post summary | 38 |
| post action count | 52 |
| post action target 等于第一个可见 post | 11 |
| rows with post action | 35 |
| 有 post action 且 query 来自第一个可见 post 的 rows | 29 |

这个结果说明：

- 非空 runtime recall query 当前完全由第一个可见 post summary 主导；
- 大多数 post action 的 target 并不是第一个可见 post；
- 所以 runtime recall query 与实际 action target 的错位是结构性结果，不是某几个测试样本偶然触发。

典型样例：

- step 3: query/episode topic 来自 post 6，但 action target 是 post 7；
- step 4: query/episode topic 来自 post 6，但 action target 是 post 10；
- step 6: query/episode topic 来自 post 6，但 action target 是 post 9、post 13；
- step 12 的 prompt trace 中也出现过 query 来自 post 24，但 action target 是 post 26。

## 4. 底层设计问题

### 4.1 一个字段承担了太多职责

当前 `summary` 同时承担：

- prompt 中节省 token 的显示文本；
- visible snapshot 的对象语义代理；
- semantic anchor 的内容；
- topic 抽取来源；
- runtime recall query 文本来源；
- action target snapshot 文本来源；
- long-term document 的检索字段；
- evaluation post-linked query 文本。

这些职责的底层要求不同：

| 职责 | 底层要求 |
| --- | --- |
| prompt display excerpt | 短、稳定、可读、省 token |
| object semantic identity | 能区分对象，保留核心论点和实体 |
| recall query | 与当前决策意图或目标对象相关 |
| action target evidence | 能证明模型动作指向哪个对象 |
| long-term document | 支持未来检索和事实回放 |
| evaluation query | 可复现、可解释、可判定 |

固定长度截断只能满足第一类需求，不能自然满足其余需求。

### 4.2 `topic` 的命名掩盖了真实语义

`topic` 在代码中的行为更接近 `first_visible_object_excerpt`。它没有经过：

- 对 observation prompt 的整体归纳；
- 对模型实际选择目标的绑定；
- 对 self-authored/recent action 关系的判断；
- 对 action capability 的意图分析；
- 对多个可见对象的优先级判定。

因此后续模块看见 `topic` 时，会误以为它是一个可靠的本轮上下文主题。

### 4.3 perception 没有利用模型真实输入边界

`DefaultObservationPolicy` 接收 `observation_prompt` 但忽略它。这导致 perception metadata 与模型实际收到的文字之间缺少一致性校验。

更底层的问题是：系统没有清楚区分三种输入事实：

- 模型实际收到的 prompt 文本；
- prompt 对应的结构化 visible snapshot；
- 用于检索/写库的语义投影。

当前第三者几乎直接由第二者的第一个 summary 派生。

### 4.4 action target 与 recall intent 没有契约

在模型调用前，系统不知道模型会选择哪个 target；但在模型调用后，系统已经知道 action evidence。当前 episode 写入时没有重新审视：

- runtime query source 是否与 action target 对齐；
- `topic` 是否应降级为 feed context；
- action target summary 是否应成为 episode 主索引；
- self-authored visible content 是否应成为 recall/episode 的更强信号；
- 多动作场景中不同 action 是否应拆分不同 query/document emphasis。

结果是 action episode 有事实字段，但没有“这个字段在检索语义上代表什么”的 contract。

## 5. 不建议立即做的修改

不建议直接把 `summarize_text()` 替换成 LLM summarization。

原因：

- 这会增加成本和不确定性，但不解决 `topic = topics[0]` 的契约错误；
- 如果 action target 和 query source 仍不绑定，更好的摘要只会让错位更隐蔽；
- 评估也会变得不稳定，因为 post-linked query 的文本来源会变成模型生成内容。

也不建议只微调 rerank 权重。

原因：

- rerank 是下游补救；
- 当前问题在写入前已经发生：episode 同时携带了错位的 topic 和 target；
- 权重调小 `topic` 可能缓解误召回，但不会让 runtime recall 更贴近模型决策。

## 6. 建议的分步修正方向

### Step 1: 先增加可观测性，不改行为

在 step audit / episode audit 中补充以下字段：

- `query_source_object_kind`
- `query_source_object_id`
- `query_source_object_rank`
- `query_text_source_field`
- `query_target_alignment`
- `first_visible_post_id`
- `action_target_id`
- `self_authored_visible_object_ids`

目标是让每次 runtime recall 都能回答：

- query 来自哪个可见对象？
- query 来自该对象的哪个字段？
- action 实际指向哪个对象？
- 二者是否一致？
- 如果不一致，是否至少属于 parent/quote/comment 上下文关系？

### Step 2: 字段语义拆分

保留当前 display 行为，但不要继续让 `summary` 承担所有职责。可以先在 contract 和内部字段上拆成：

- `display_excerpt`: 给 prompt/UI/trace 阅读用；
- `object_text_evidence`: 结构化对象的可检索文本证据，允许包含 title/content/author/relation；
- `feed_context_excerpt`: 当前 observation 的背景对象摘要；
- `candidate_target_excerpt`: 可被 action 指向的对象摘要；
- `action_target_excerpt`: action evidence 确认后的目标摘要；
- `recall_query_text`: 本次 retrieval 使用的显式查询文本；
- `recall_query_basis`: 查询基于 topic、anchor、self-authored、recent-action 还是 explicit target。

第一步可以只新增字段和 trace，不急着删旧字段。

### Step 3: 重新定义 `topic`

短期内建议把内部含义从“第一个 post summary”改为更明确的 contract：

- `feed_focus`: observation feed 的前景对象或前几个对象；
- `decision_context`: 模型行动前可见上下文；
- `action_target_context`: 动作目标确认后的上下文；
- `distilled_topic`: 只有在真正执行归纳逻辑后才使用这个名字。

如果暂时不改代码，也应在文档和 audit 中明确：当前 `topic` 不是真 topic，而是 first visible object excerpt。

### Step 4: runtime recall query 不再默认只取 `topic`

候选策略：

- 多 query basis：first visible object、self-authored visible objects、recent action targets、high-salience anchors 分别生成候选；
- gate 与 query 分离：topic 可以触发 recall，但 query 文本不一定等于 topic；
- 对 self-authored visible 内容设专门路径，因为这是模拟中“我曾经说过什么/做过什么”的核心记忆需求；
- 对 post-linked 测试场景保留 deterministic query，但标明它测的是 object-linked retrieval，不代表 runtime recall query。

### Step 5: episode 写入以 action target 为主索引

`ActionEpisode` 的 long-term document 应该优先表达：

- agent 做了什么；
- 对哪个对象做；
- 目标对象当时如何呈现在 prompt 中；
- 这个动作与哪些 observation context 有关；
- runtime recall 当时用了什么 query；
- query 与 target 是否一致。

`topic` 可以作为 feed background，但不应在没有对齐检查的情况下成为 episode 的主检索语义。

## 7. 对测试架构的影响

当前 post-linked final lookup 使用 post summary 做 query，能够暴露长期记忆对对象文本的检索能力，但它不等价于 runtime recall 能力。

后续测试应拆成三类：

- object-linked retrieval: 给定可见对象文本，检索与该对象相关的长期记忆；
- runtime recall replay: 复现某一步真实 `last_recall_query_text`，检查 recall/injection 是否合理；
- action-target retrieval: 给定 action target 的对象文本，检查是否能找回该动作 episode。

其中 runtime recall replay 必须额外记录 query-source-object 与 action target 的 alignment，否则无法判断“召回错”是 long-term retrieval 的问题，还是 query 本身已经偏离了模型行为目标。

## 8. 下一步审查建议

下一步不应直接重构 summary 生成，而应按 master plan 的短期优先级继续做 runtime query trace replay：

1. 在现有 S1 trace 上列出所有 `query != action target summary` 的 episode；
2. 区分三类错位：
   - query object 与 action target 完全无关；
   - query object 是 parent/quote/source context；
   - query object 是同一 discussion thread 的背景对象；
3. 对每类错位判断是否应由 retrieval、episode schema、prompt assembly 或 action evidence 修正；
4. 再进入 `ActionEpisode` 字段审查，决定哪些字段是主事实、哪些只是调试冗余。

这个顺序比直接改摘要更稳，因为它先澄清系统底层 contract：记忆到底应该帮助模型记住“看到过什么”、还是“对什么行动过”、还是“我曾经怎么参与过某个对象/话题”。
