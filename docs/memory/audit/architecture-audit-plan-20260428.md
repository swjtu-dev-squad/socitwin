# 记忆架构审查概况与计划

- 日期：2026-04-28
- 分支：`eval/memory-performance-evaluation`
- 范围：`action_v1` 记忆主链、当前 B-level 评估结果、后续分模块审查计划
- 参考结果：
  - `docs/memory/evaluation/results/b-level-post-linked-results-20260426.md`
  - `backend/test-results/memory-eval/b-level-v05-s1-post-linked-final-20260426`
  - `backend/test-results/memory-eval/b-level-v05-s2-post-linked-final-20260426`

## 1. 本轮审查目标

本轮不是直接做局部修补，而是先回答：

1. 当前记忆系统在真实 simulation 中实际如何存、查、注入、影响模型输入。
2. 当前评测结果到底证明了什么，哪些结论不能过度外推。
3. 哪些实现是明显机械式接线，后续需要从模拟底层原则重新设计。
4. 后续应该按什么顺序做更细的模块级审查。

当前结论先按代码事实整理，不把现有实现预设为合理设计。

## 2. 当前主链概况

`action_v1` 当前运行链可以概括为：

```text
OASIS action.refresh/listen_from_group
  -> ObservationShaper
  -> prompt_visible_snapshot
  -> DefaultObservationPolicy
  -> RecallPlanner
  -> PromptAssembler
  -> model tool calls
  -> ActionEvidence
  -> StepSegment / ActionEpisode
  -> Chroma long-term store
  -> later recall note injection
```

关键代码入口：

- `backend/app/memory/environment.py`
  - `ActionV1SocialEnvironment.to_text_prompt()` 只主动读取 posts 和 groups。
- `backend/app/memory/observation_shaper.py`
  - observation 预算控制、裁剪、fallback。
- `backend/app/memory/observation_semantics.py`
  - `summary`、`topic`、`semantic_anchors` 的静态抽取。
- `backend/app/memory/recall_planner.py`
  - recall gate 和 runtime retrieval。
- `backend/app/memory/prompt_assembler.py`
  - recent、compressed、recall 与当前 observation 的 prompt 组装。
- `backend/app/memory/action_evidence.py`
  - tool call 到结构化目标证据。
- `backend/app/memory/episodic_memory.py`
  - `StepSegment` / `ActionEpisode` 构造。
- `backend/app/memory/longterm.py`
  - `_episode_document()`、Chroma 写入、rerank。
- `backend/app/memory/evaluation_harness.py`
  - 当前 B-level retrieval probe 和结果报告。

## 3. 当前评测结果怎么读

本轮 B-level 结果证明的事情比较有限，但有价值：

- 长期记忆写入链路能在真实模拟中工作。
  - S1 写入 74 条 `ActionEpisode`。
  - S2 写入 80 条 `ActionEpisode`。
- agent 过滤在本轮样本中没有暴露跨 agent 污染。
  - S1 / S2 的 cross-agent top-3 都是 0。
- self-retrievability 的 top-3 基本可用。
  - S1 Hit@3 = 0.9054。
  - S2 Hit@3 = 0.9000。
- post-linked final lookup 能暴露同 agent 内错目标。
  - S1 same-agent wrong-target = 24。
  - S2 same-agent wrong-target = 3。

这些结果不能证明：

- runtime recall query 在真实每一步都能命中正确记忆；
- 检索到的记忆真的进入了 prompt；
- 进入 prompt 的记忆真的改变了模型行为；
- 当前 `summary/topic/action/outcome` 设计已经合理。

当前最清楚的风险是：系统已经能“查到相似历史”，但不一定能“查到结构上正确的历史”。这和当前实现高度一致：弱动作如 `like_post` / `repost` 主要依赖 target summary 和低权重 state changes，而 `quote_post` / `create_post` 带有更多自然语言内容，更容易在 embedding 和 token-overlap rerank 中胜出。

## 4. 已确认的粗糙实现点

### 4.1 Observation 不是语义理解，而是截断后的可见快照

`observation_semantics.summarize_text()` 只是空白归一化和固定字符数截断。post summary 默认 120 字符，comment / group message 更短。

直接影响：

- `target_snapshot.summary` 不是语义摘要；
- 评测里的 post-linked query 本质上也是截断正文；
- 长文本前 120 字符如果只是铺垫，后续关键立场会被丢掉；
- 相似主题场景下，不同帖子可能被截成高度相似的 query。

### 4.2 Runtime topic 取第一条可见 post summary

`DefaultObservationPolicy` 把 `extract_topics_from_snapshot()[0]` 作为 `topic`。而 `extract_topics_from_snapshot()` 先遍历 posts，把每个 post 的 summary 当 topic。

直接影响：

- recall query 经常等于首页第一条可见 post 的截断文本；
- 当前 agent 的行动意图、任务状态、刚才做过什么没有进入主 query；
- 当第一条 seed / 热门帖子长期存在时，query 高度重复；
- `topic_trigger` 容易变成“只要看到帖子就查库”的宽 gate。

### 4.3 `semantic_anchors` 和 `entities` 多数不是主 query

`RetrievalPolicy.build_request()` 的优先级是 topic -> anchors -> entities -> recent episodes。只要 topic 非空，anchors 和 entities 就不会进入 query 主体。

直接影响：

- post id / user id 对 exact continuity 有价值，但在语义检索主 query 中通常被绕过；
- anchors 目前更像 debug 信息，不是主要检索信号；
- entity trigger 默认阈值为 0，实际 gate 侧也不是主要机制。

### 4.4 `ActionEpisode` 字段很多，但语义层次不清

`ActionEpisode` 同时承载：

- 动作事实：`action_name/action_fact/action_category`
- 目标事实：`target_type/target_id/target_snapshot`
- 可见性和执行状态：`target_visible_in_prompt/target_resolution_status/execution_status`
- 上下文：`local_context/topic/query_source/outcome`
- 检索和压缩辅助：`state_changes/action_significance/evidence_quality/degraded_evidence/summary_text/metadata`

问题不是字段多本身，而是很多字段的来源、粒度和后续用途没有被设计成稳定 contract：

- `summary_text` 当前为空；
- `outcome` 是 step 级文本，不是 action 级 outcome；
- 多 action step 会共享同一个 `outcome`；
- `query_source` 常常只是 topic 是否为空的结果；
- `metadata` 为空，说明字段扩展面还没有被真实使用；
- relationship action 的 user target 缺少独立 user snapshot。

### 4.5 长期记忆 document 是静态模板，不是面向检索任务设计的事件表征

`longterm._episode_document()` 把 payload 拼成固定行：

- Action
- Action name
- Action category
- Topic
- Target
- Context
- Authored content
- State changes
- Outcome
- Significance
- Execution status
- Target resolution
- Evidence quality
- Summary

直接影响：

- 弱动作 document 文本短，容易被带 authored content 的动作压过；
- `state_changes` 权重低，但它对 like/repost/follow 这类动作是关键结构信号；
- `Outcome` 可能引入 step-level 噪声；
- document 没有根据 action type 做差异化检索表达；
- exact target continuity 主要靠 rerank token overlap，而不是一等检索约束。

### 4.6 Rerank 是 token overlap 加时间排序

`longterm._score_action_episode()` 对字段做 token overlap 加权，最后按 score 和 timestamp 降序排序。

直接影响：

- 同主题文本越丰富越占优；
- 相同或接近分数时偏向更新 episode；
- 对“我是否对这个具体 post 做过 like/repost/follow”的结构需求支持不足；
- 当前评测中 `quote_post` 压过 `like_post/repost` 是预期现象，不是偶然 bug。

### 4.7 Recall 注入和行为使用仍未被充分评估

B-level 的 `VAL-RCL-11` 是最终长期库检索，不复现 runtime step。`VAL-RCL-08/09` 是 retrieve-only probe，不执行 prompt assembly。

直接影响：

- 当前指标主要覆盖写入和最终检索；
- recall gate -> retrieval -> overlap -> injection -> model behavior 这一整条链还没有被完整追踪；
- `recall_injection_trace_rate` 在两轮报告中是 `n/a`。

## 5. 当前系统的底层设计缺口

这些问题不是改几个权重就能彻底解决的。

### 5.1 缺少明确的记忆对象模型

目前长期层几乎只围绕 `ActionEpisode`，但真实社交模拟至少需要区分：

- 我看见过什么内容；
- 我对什么内容做过什么；
- 我对谁建立了什么关系；
- 我自己发布过什么；
- 某个讨论线程的局部状态；
- 群组/社区上下文；
- agent 自身偏好和长期立场变化。

当前把这些都塞进动作 episode，会导致字段臃肿、检索目标混杂。

### 5.2 缺少从模型交互角度定义的 memory contract

模型真正需要的是：

- 当前环境中哪些对象和我过去有关；
- 我过去对它们做过什么；
- 是否需要避免重复动作；
- 我之前表达过什么立场；
- 现在的动作是否要保持连续性或纠正过去状态。

当前实现更多是在 tool call 后记录“发生了什么”，但没有先定义“下一次模型决策时需要什么样的记忆提示”。

### 5.3 缺少检索任务分型

现在大多数 recall 都走单一路径：构造 query text -> vector search -> token rerank。

但不同任务应当分开：

- exact object recall：当前 post/user/group 是否和过去 episode 有结构关联。
- semantic stance recall：类似话题下我过去表达过什么观点。
- relationship recall：我是否 follow/mute/join 过某对象。
- self-authored recall：当前可见内容是否是我自己发过/评论过的。
- thread continuity recall：当前讨论线程是否延续过去互动。

这些任务不应该全部用第一条 post summary 去查。

### 5.4 缺少行为级闭环

当前记忆系统更像“可检索日志”，还没有充分验证它是否能改变模拟行为：

- 是否减少重复 like/follow；
- 是否让 agent 在同一 thread 中保持立场连续；
- 是否让 agent 正确识别自己的历史发言；
- 是否避免把别人说过的话误认为自己说过；
- 是否在群组场景中保持 membership 和上下文连续。

## 6. 建议的审查顺序

### 阶段 A：模型交互与 prompt 事实边界

目标：先确认模型每一步到底看到了什么，以及记忆内容如何插入 prompt。

审查点：

- `ActionV1SocialEnvironment.to_text_prompt()` 的 observation source 是否足够；
- `render_observation_prompt()` 的文本形态是否适合模型理解；
- recent / compressed / recall note 的角色顺序和语言是否清晰；
- recall note 是否可能被模型误解为当前 observation；
- self-authored 信息是否应该显式进入 prompt；
- action outcome alignment note 是否真的解决了 final text 噪声。

输出：

- 一份 prompt trace 审查文档；
- 至少 3 个真实 step 的完整 prompt 分析；
- 明确哪些字段是模型可见事实，哪些只是内部 metadata。

### 阶段 B：Observation / Perception 重审

目标：重新定义从平台状态到语义线索的转换。

审查点：

- `summary` 是否应该继续只是截断；
- `topic` 是否应该从第一条 post 改为结构化 query intent；
- `semantic_anchors` 是否应该成为主要 recall 输入之一；
- author/self/thread/group 信息是否需要独立对象族；
- observation shrink/fallback 后的 evidence_quality 是否足以影响后续持久化和检索；
- empty observation、refresh 失败、group-only 场景的语义边界。

输出：

- observation schema 问题清单；
- 当前字段保留/废弃/重命名建议；
- 新的 perception envelope 候选结构。

### 阶段 C：ActionEvidence / ActionEpisode 重构审查

目标：从“动作如何影响模拟状态”出发重审事件模型。

审查点：

- 每类 action 的目标对象、状态变化、可见性、失败语义是否完整；
- `state_changes` 是否应升级为结构化对象，而不是字符串；
- `outcome` 是否需要 action-level digest；
- `target_snapshot` 是否应拆成 visible evidence 和 resolved object reference；
- `ActionEpisode` 是否应拆成 action event、content memory、relationship memory 等多个层级；
- 哪些字段当前只是调试残留或未来扩展占位。

输出：

- action event 字段矩阵；
- 当前冗余字段和缺失字段清单；
- `ActionEpisode v2` 或分层 memory object 草案。

### 阶段 D：Long-Term Document / Retrieval 设计审查

目标：把“检索什么”从单一语义搜索拆成多任务 retrieval。

审查点：

- `_episode_document()` 是否应按 action type 分模板；
- exact target/user/group/thread filter 是否应先于 embedding；
- weak action 是否需要结构优先的 rerank；
- timestamp tie-break 是否合理；
- post-linked lookup 中同 agent wrong-target 的根因样例；
- Chroma metadata / sidecar payload 是否足以支撑结构化过滤。

输出：

- failure case 分类报告；
- retrieval task taxonomy；
- rerank / filter 改造方案；
- 对 VAL-LTM-05 / VAL-RCL-11 的指标扩展建议。

### 阶段 E：Recall Gate / Injection / Behavior 闭环

目标：确认检索结果是否真的以正确形式影响模型决策。

审查点：

- topic-trigger 是否过宽；
- repeated-query block 是否掩盖环境重复但任务变化的情况；
- overlap suppression 是否过强或过弱；
- recalled > 0、injected = 0 的真实原因分布；
- recall note 中的措辞是否支持模型做正确行为；
- 是否能设计行为级回放：重复 like/follow、self-authored recognition、thread continuity。

输出：

- runtime recall trace replay 指标；
- `VAL-RCL-10` 补跑/补强计划；
- 行为级场景集草案。

### 阶段 F：测试架构反审

目标：让测试既能适配当前实现，又能暴露架构问题。

审查点：

- 哪些测试只证明“链路通”；
- 哪些测试能暴露语义设计错误；
- 哪些测试不应因为当前实现粗糙而放宽口径；
- 如何区分 final-store lookup、runtime recall、prompt injection、behavior effect；
- 如何降低单轮真实 LLM 随机性的解释风险。

输出：

- 测试分层矩阵；
- 当前 B-level 指标解释边界；
- 下一轮 C-level / behavior-level 场景定义。

## 7. 建议优先级

短期优先：

1. 做 prompt trace 审查，确认模型实际输入。
2. 做 post-linked wrong-target 样例归因，尤其是 `like_post/repost` 被 `quote_post` 压过。
3. 做 runtime `last_recall_query_text` trace replay，补齐 final-store lookup 与真实 recall 的差距。
4. 审查 `ActionEpisode` 字段，先列出冗余、混合粒度和必须结构化的字段。

中期优先：

1. 设计 memory object taxonomy，不再让 `ActionEpisode` 承担所有记忆类型。
2. 拆分 retrieval task：exact object、semantic stance、relationship、self-authored、thread continuity。
3. 重构 query construction，不再默认用第一条 post summary。
4. 为 weak action 引入结构优先检索和排序。

长期优先：

1. 建立行为级 benchmark。
2. 将 memory debug 与评测指标稳定接入前端/报告。
3. 对多轮真实场景做重复实验，报告均值和方差。

## 8. 下一份建议文档

建议下一步先写：

```text
docs/memory/prompt-trace-audit-20260428.md
```

它应从真实 `step_audit.jsonl` 和 `episode_audit.jsonl` 中选 3 到 5 个 step，逐步展示：

- 当前 observation prompt；
- prompt-visible snapshot；
- recall gate/query/candidates；
- selected recent/compressed/recall；
- 最终模型动作；
- 写入的 `ActionEpisode`；
- 这一步对后续 recall 的影响。

这一步最关键，因为后续所有架构重构都应从“模型到底看到了什么、需要什么”倒推，而不是继续围绕已有字段做机械修补。
