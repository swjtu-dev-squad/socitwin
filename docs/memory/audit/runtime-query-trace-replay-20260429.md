# Runtime Query Trace Replay Audit

- Date: 2026-04-29
- Scope: B-level S1 `step_audit.jsonl` 中真实 runtime recall query 与本步 action target 的对齐情况
- Related plan: [audit-master-plan-20260428.md](./audit-master-plan-20260428.md)
- Depends on:
  - [prompt-trace-audit-20260429.md](./prompt-trace-audit-20260429.md)
  - [summary-topic-audit-20260429.md](./summary-topic-audit-20260429.md)

## 1. 目标

本审查不评估最终 long-term store 的命中率，而是复盘真实运行中每一步模型调用前的 retrieval query：

- runtime recall query 来自哪个可见对象；
- query 来源对象是否等于本步实际 action target；
- 如果不一致，错位是普通 feed 背景、同一讨论链背景，还是 self-authored/recent-action 信号被忽略；
- 这些错位如何影响后续 `ActionEpisode` 写入和 long-term retrieval。

这里的“replay”不是重新调用模型，而是在已有 trace 上复原 query/target 关系。

## 2. 数据来源与限制

数据来源：

`backend/test-results/memory-eval/b-level-v05-s1-post-linked-final-20260426/artifacts/real-scenarios/step_audit.jsonl`

辅助参考：

`backend/test-results/memory-eval/b-level-v05-s1-post-linked-final-20260426/artifacts/real-scenarios/episode_audit.jsonl`

当前 trace 的限制：

- 没有显式记录 `query_source_object_id`；
- 没有显式记录 `query_source_object_rank`；
- 没有记录 query 来源字段，只能从 `last_recall_query_text == visible_posts[0].summary` 推断；
- action evidence 有 `target_id` 和 `target_snapshot`，但没有记录 target 在 visible list 中的 rank；
- quote/repost 的原始引用关系没有结构化展开，只能从 summary 文本推断讨论链关系。

因此本文所有 query-source-object 结论都是基于现有 trace 的保守推断。

## 3. 总体统计

对 official steps 中所有 agent-step 做统计：

| 指标 | 数值 |
| --- | ---: |
| agent-step rows | 54 |
| nonempty runtime recall queries | 38 |
| query 等于第一个可见 post summary | 38 |
| post action count | 52 |
| action target 在 visible snapshot 中缺失 | 0 |
| action target 是第一个可见 post | 11 |
| action target 是第 2-5 个可见 post | 41 |
| 非第一个可见 post target 且发生 recall injection | 10 |

按 action 类型拆分：

| action | total | target rank = 1 | target rank > 1 |
| --- | ---: | ---: | ---: |
| `like_post` | 27 | 5 | 22 |
| `quote_post` | 18 | 6 | 12 |
| `repost` | 7 | 0 | 7 |

按 target rank 拆分：

| target rank in visible posts | count | injected actions |
| --- | ---: | ---: |
| 1 | 11 | 0 |
| 2 | 19 | 2 |
| 3 | 8 | 3 |
| 4 | 10 | 4 |
| 5 | 4 | 1 |

直接结论：

- 当前 S1 中，只要 runtime recall query 非空，它就完全由第一个可见 post summary 主导；
- 但模型大多数 post action 并不指向第一个可见 post；
- action evidence 本身没有缺目标，目标都在 visible snapshot 中；
- 错位发生在 recall query 构建阶段，而不是 action evidence 无法解析目标。

## 4. 关键错位模式

### 4.1 Feed-first query vs target-later action

最常见模式：

- visible posts 中第一个 post 被用作 `topic` 和 recall query；
- 模型实际行动指向第 2、3、4、5 个 post；
- episode 写入时 `topic` 仍然保留第一个 post summary；
- `target_snapshot.summary` 才记录真实 action target。

示例：

| step | agent | query source | action target | action |
| --- | --- | --- | --- | --- |
| 3 | Institutional Comparer | post 6 | post 7 | `like_post` |
| 4 | Institutional Comparer | post 6 | post 10 | `like_post` |
| 7 | Institutional Comparer | post 6 | post 10 | `quote_post` |
| 9 | Open Politics Advocate | post 6 | post 10 / 7 | `like_post` |

这种模式说明 retrieval query 不是模型选择目标后的意图表达，而只是 feed 排序的副产品。

### 4.2 同一讨论链背景，但 query 仍不够具体

有些错位不是完全无关。比如 post 6、7、9、10、13、15、18 仍围绕 elite pipeline/accountability 讨论链展开。此时第一个 post summary 可以算作宽泛背景，但不能代表模型实际回应的对象。

示例：

- step 8，Open Politics Advocate：
  - query source: post 6；
  - target: post 18；
  - target summary: `User 2 quoted a post from User 2...`；
  - action: `quote_post(post_id=18, ...)`。

这类场景下，如果召回目标是“找回与整个讨论主题相关的旧记忆”，post 6 query 可能还能工作；但如果召回目标是“帮助模型回应当前 target post”，query 就过宽，容易召回早期背景而不是目标对象或最近互动。

底层问题是系统没有区分：

- discussion-level memory；
- object-linked memory；
- action-target memory；
- self-continuity memory。

### 4.3 Self-authored visible object 被弱化

step 8 的 Institutional Comparer：

- visible posts:
  - post 6: other-authored，第一个可见 post；
  - post 15: self-authored，第二个可见 post；
- query: post 6 summary；
- action:
  - like post 6；
  - create new post，内容延续自己的观点。

step 17 的 Institutional Comparer：

- visible posts:
  - post 35: self-authored；
  - post 38: self-authored；
- query: post 35 summary；
- injected: 2；
- action: create post 40。

这里 query 恰好来自 self-authored first post，但 trace 不能说明系统是因为 `self_authored` 触发，还是只是因为它排在第一位。当前 query/gate trace 只暴露 `topic_trigger` 等 flags，没有记录 self-authored object 是否进入 query basis。

这会影响记忆架构的一个核心需求：社交模拟中的 agent continuity 很多时候不是“看到一个主题”，而是“我曾经说过什么、我刚才如何参与、我是否在延续自己的立场”。当前 self-authored 只是 snapshot 属性，还没有成为 query 构建的一等输入。

### 4.4 Injection 可能被错 query 牵引

非第一个可见 post target 且发生 injection 的动作共有 10 个。

典型样例：

| step | agent | query source | target | injected step ids |
| --- | --- | --- | --- | --- |
| 8 | Pragmatic Reformer | post 6 | post 15 / 13 | [4] |
| 12 | Institutional Comparer | post 24 | post 26 | [3] |
| 14 | Pragmatic Reformer | post 6 | post 25 / 27 | [3] |
| 15 | Open Politics Advocate | post 7 | post 27 | [3] |
| 17 | Pragmatic Reformer | post 6 | post 38 | [3] |

这类场景最需要审查，因为 memory injection 已经进入模型 prompt。即使注入内容没有明显错误，也无法确认它服务的是当前 action target，还是被第一个可见 post 的背景 query 牵引。

这里应避免简单判断“injection 错了”。更准确的判断是：当前 trace 缺少 alignment 信息，所以无法判定 injection 是否对模型决策有正向帮助。

## 5. 代表性 replay

### 5.1 Step 8, Pragmatic Reformer

可见 posts：

1. post 6: `One thing that bothers me about "meritocratic" elite pipelines...`
2. post 9: `User 1 quoted a post from User 2...`
3. post 13: `Another angle on the elite pipeline problem...`
4. post 15: `User 0 quoted a post from User 1...`

runtime:

- query: post 6 summary；
- recalled step ids: `[3, 7, 4]`；
- injected step ids: `[4]`。

actions:

- `like_post(post_id=15)`；
- `like_post(post_id=13)`。

判断：

- target 都可见，不存在 evidence 缺失；
- target rank 是 4 和 3；
- query 是 discussion background，不是 action target；
- injection 可能与早期 post 6 相关，但不一定服务 post 15/post 13。

### 5.2 Step 12, Institutional Comparer

可见 posts：

1. post 24: `The thread with User 1 has sharpened my thinking...`
2. post 26: `User 1 quoted a post from User 2...`

runtime:

- query: post 24 summary；
- recalled step ids: `[11, 7, 3]`；
- injected step ids: `[3]`。

actions:

- `quote_post(post_id=26, ...)`；
- `like_post(post_id=26)`。

判断：

- 这是最清晰的 target mismatch；
- query 来源是第一个可见 post；
- 模型实际回应的是第二个可见 post；
- episode 写入后，`topic=post24 summary`，`target_snapshot.summary=post26 summary`；
- 后续用 post24 query 检索时可能找回这条 action episode，但这条 episode 的实际动作对象是 post26。

### 5.3 Step 17, Pragmatic Reformer

可见 posts：

1. post 6: `One thing that bothers me about "meritocratic" elite pipelines...`
2. post 25: `User 0 quoted a post from User 2...`
3. post 26: `User 1 quoted a post from User 2...`
4. post 38: `Another comparative insight worth noting...`
5. post 39: self-authored design challenge

runtime:

- query: post 6 summary；
- recalled step ids: `[3, 9, 10]`；
- injected step ids: `[3]`。

actions:

- `like_post(post_id=38)`；
- `quote_post(post_id=38, ...)`。

判断：

- target rank 是 4；
- visible snapshot 中还有 self-authored post 39，但 query 没有体现；
- model quote content 明确提到 `post 39` 的设计挑战；
- 当前 recall query 没有捕捉这个自我连续性信号。

这说明仅用 first visible post summary 会错过“模型即将把当前目标与自己的近期表达连接起来”的场景。

## 6. 对当前实现的判断

### 6.1 retrieval query 的事实边界过早确定

当前 recall 发生在模型 action 之前，这是合理的：记忆应该在模型决策前进入 prompt。

但当前 query 由 `perception.topic` 单点决定，而 `perception.topic` 又等于第一个可见对象摘要。这相当于在模型尚未决策前，用 feed 排序替代了“本步可能需要哪些记忆”的判断。

更合理的底层模型是：

- 模型决策前：系统只能生成候选 recall intents；
- 模型决策后：action evidence 可以回填真实 target alignment；
- episode 写入时：必须同时保留 pre-action recall basis 和 post-action target evidence；
- 评估时：不能把 pre-action query 命中与 post-action target 命中混为一类。

### 6.2 `topic_trigger` 太容易遮蔽其他触发

只要有第一个可见 post summary，`topic_trigger` 就成立。这样会让：

- self-authored trigger；
- recent action rehit；
- anchor trigger；
- entity trigger；
- target候选对象；

在实际 query 构造上都变成次要路径。

这不只是 gate 策略问题，因为 `RetrievalPolicy.build_request()` 会在 topic 非空时直接返回，不再组合 anchors/entities。

### 6.3 ActionEpisode 记录了目标，但没有记录错位关系

当前 `ActionEpisode` 已经有 target evidence：

- `target_type`
- `target_id`
- `target_snapshot`
- `target_visible_in_prompt`
- `target_resolution_status`

但缺少：

- `query_source_object_id`
- `query_source_object_rank`
- `query_target_alignment`
- `target_visible_rank`
- `query_basis`
- `target_relation_to_query_source`

所以事后看 episode 时，只能发现 `topic` 和 `target_snapshot` 不同，却无法判断这是合理背景、父子引用、同 thread，还是 query 构造错误。

## 7. 对测试结果的解释边界

B-level S1 的 final lookup KPI 不能直接说明 runtime recall 行为是合理的。

原因：

- final lookup 用最终 long-term store 做检索；
- post-linked query 使用可见 post summary；
- runtime recall query 使用当步 `last_recall_query_text`；
- 但 runtime query 当前固定来自 first visible post，不一定是本步 action target；
- 所以 final lookup 的高命中可能代表 object text 在最终库中可检索，不代表模型运行时被注入了正确目标相关记忆。

这也解释了为什么已有报告里 `ltm_exact_hit_at_3` 可以较高，但 prompt trace 仍出现 post-linked wrong-target 风险。

## 8. 建议的最小仪表化

下一轮不要先改 retrieval 行为，先补 trace 字段。

建议在 `build_perception_envelope` 或 recall preparation 阶段记录：

- `query_source_object_kind`
- `query_source_object_id`
- `query_source_object_rank`
- `query_text_source_field`
- `query_text_source_value`
- `topic_candidates`
- `anchor_candidates`
- `self_authored_candidates`

建议在 action episode 写入阶段记录：

- `target_visible_rank`
- `query_target_alignment`
- `query_target_relation`
- `query_source_summary`
- `target_summary`
- `target_was_self_authored`
- `query_source_was_self_authored`

`query_target_relation` 可以先用保守枚举：

- `same_object`
- `different_visible_object`
- `same_author`
- `self_authored_query_source`
- `self_authored_target`
- `unknown_relation`

后续如果 quote/comment/repost 关系结构化了，再扩展：

- `target_quotes_query_source`
- `query_source_quotes_target`
- `same_thread`
- `parent_child`

## 9. 下一步

下一步建议进入 `ActionEpisode` 字段审查，但不要先删字段。

审查重点应是：

1. 哪些字段是行为事实；
2. 哪些字段是 retrieval/indexing signal；
3. 哪些字段只是 debug trace；
4. 哪些字段当前命名暗示了错误语义；
5. 哪些字段需要从单值改成结构化多候选；
6. 哪些字段应该在 pre-action 和 post-action 两个阶段分别记录。

这一步完成后，再决定是否重构：

- `PerceptionEnvelope`
- `RetrievalPolicy.build_request`
- `ActionEpisode`
- long-term document builder
- B-level runtime replay evaluator

否则直接修改 query 生成，很可能只是把 first-visible-post 偏差换成另一个未经验证的启发式。
