# Observation And Evidence

- Status: active working spec
- Audience: implementers, reviewers, AI tools
- Doc role: describe the current observation shaping chain and evidence boundary in `action_v1`

## 1. Purpose

本文档只讨论 `action_v1` 的 observation 与 evidence 主链。

重点回答：

- 当前 observation 从哪里来；
- 怎么被压缩、裁决、变成 prompt-visible snapshot；
- `ActionEvidence` 允许依赖哪些事实，不允许依赖哪些事实。

## 2. Current Observation Scope

当前 `action_v1` 的 observation 主轴只有两块：

- `posts`
- `groups`

对应代码入口在：

- [environment.py](/home/grayg/socitwin/backend/app/memory/environment.py)
  - `ActionV1SocialEnvironment.to_text_prompt()`

它当前只读取：

- `refresh()`
- `listen_from_group()`

并组织成：

- `posts_payload`
- `groups_payload`

这意味着当前 prompt-visible observation 家族主要是：

- `post`
- `comment`
- `group`
- `group_message`

当前没有独立的 `user` object family 直接进入 observation 主链。

## 3. Observation Artifact

当前 observation 主链的核心中间产物是 `ObservationArtifact`，定义在：

- [observation_shaper.py](/home/grayg/socitwin/backend/app/memory/observation_shaper.py)

它包含：

- `observation_prompt`
- `prompt_visible_snapshot`
- `render_stats`
- `source_snapshot_kind`
- `visible_payload`

当前这条边界很重要：

- `observation_prompt` 和 `prompt_visible_snapshot` 来自同一份最终 `visible_payload`；
- `prompt_visible_snapshot` 不是从 raw payload 另外再推一套平行事实；
- `source_snapshot_kind` 当前固定为 `prompt_visible_snapshot`，明确表示后续事实链依赖的是 prompt 可见快照。

## 4. Current Shaping Order

当前 `ObservationShaper.shape()` 的主链是固定的四层：

1. `raw guard pass`
2. `long-text hard cap`
3. `interaction shrink`
4. `physical fallback`

对应代码仍在：

- [observation_shaper.py](/home/grayg/socitwin/backend/app/memory/observation_shaper.py)

### 4.1 Raw Guard Pass

这一层先不主动切顶层 `posts/groups`，而是先用宽松 guard 处理最容易膨胀的部分：

- `groups_count_guard`
- `comments_total_guard`
- `messages_total_guard`

它的角色不是常态压缩，而是第一层保险丝。

### 4.2 Long-Text Hard Cap

第二层只处理极端长文本：

- `post_text_cap_chars`
- `comment_text_cap_chars`
- `message_text_cap_chars`

当前语义应理解为：

- 这是极端长文本保险丝；
- 不是默认对所有 observation 做摘要化重写。

### 4.3 Interaction Shrink

如果 observation 仍然超预算，当前主退化层是 interaction shrink。

它重点继续收缩：

- comments
- messages

这也是当前 observation 里最主要的 token 膨胀源。

### 4.4 Physical Fallback

如果 interaction shrink 后仍超过 observation hard budget，就进入 physical fallback。

这时会退化成更强的 sample/count 表示，例如：

- 少量 post sample
- 少量 group sample
- 少量 joined group id sample
- 少量 message sample

因此 physical fallback 不再是假装“还保留完整环境”，而是显式进入低保真可运行状态。

## 5. Render Stats

当前 `render_stats` 至少会暴露这些关键维度：

- `selected_*_count`
- `omitted_*_count`
- `truncated_field_count`
- `raw_guard_*_trimmed`
- `interaction_shrink_rounds`
- `final_shaping_stage`
- `observation_prompt_tokens`

它的作用不是单纯统计 token，而是帮助后续判断：

- 本轮信息损失主要发生在哪一层；
- 是 comments/messages 被缩掉了，还是已经进入 physical fallback；
- 后续 episode/recall 的语义损失更可能来自哪里。

## 6. Prompt-Visible Snapshot

当前 prompt-visible snapshot 的构建入口在：

- [observation_semantics.py](/home/grayg/socitwin/backend/app/memory/observation_semantics.py)
  - `build_prompt_visible_snapshot(...)`

它当前会把最终 visible payload 结构化成：

- `posts`
  - post summary
  - nested comments
- `groups`
  - all groups
  - joined group ids
  - messages

并在局部对象上补充：

- `summary`
- `relation_anchor`
- `evidence_quality`
- `degraded_evidence`
- `self_authored`

这里要强调两个当前事实。

第一，`summary` 当前是静态、确定性的语义抽取，不是 LLM 自由摘要。  
第二，`self_authored` 已经进入 snapshot 元数据，但还没有成为 prompt 主链里的显式文本标签。

## 7. Perception Envelope

当前 `DefaultObservationPolicy` 负责从 prompt-visible snapshot 派生 perception envelope：

- `entities`
- `topic`
- `semantic_anchors`
- `topics`
- `snapshot`

代码入口在：

- [observation_policy.py](/home/grayg/socitwin/backend/app/memory/observation_policy.py)

当前这条链比较保守：

- 不使用模型做 perception 抽取；
- 主要依赖 snapshot 中已经存在的 summary / id / object family；
- 这让 perception 和 observation 事实边界仍然是可解释、可回放的。

## 8. ActionEvidence Boundary

当前 `ActionEvidenceBuilder` 的入口在：

- [action_evidence.py](/home/grayg/socitwin/backend/app/memory/action_evidence.py)

它会从：

- `prompt_visible_snapshot`
- `action_name`
- `tool_args`
- `tool_result`

构建：

- `target_type`
- `target_id`
- `target_snapshot`
- `target_visible_in_prompt`
- `target_resolution_status`
- `execution_status`
- `local_context`
- `authored_content`

这里最重要的边界是：

- `target_snapshot` 只能从当前 prompt-visible snapshot 里解析；
- 不能为了补齐信息去后验查库再伪造“模型当时看到过”的目标对象。

## 9. Current Resolution Semantics

`ActionEvidenceBuilder` 当前会把目标解析状态明确分成几类：

- `visible_in_prompt`
- `expired_target`
- `invalid_target`
- `not_visible_in_prompt`

并结合工具结果给出：

- `success`
- `failed`
- `hallucinated`

这条边界的价值在于：

- 区分“目标当时确实可见，但执行失败”
- 和“目标本来就不在当前 prompt 里，属于 hallucinated target”

这会继续影响：

- `ActionEpisode` 是否可持久化
- 后续 recall 是否应该信任这条 episode

## 10. Self-Authored: Current Actual Effect

当前 `self_authored` 的真实作用范围需要讲清楚。

现在它已经会出现在：

- prompt-visible snapshot
- target / local context 元数据

但它当前还不会直接变成：

- prompt 中显式的 `[Self-Authored]` 标签
- action significance 的直接输入
- retrieval scoring 的显式加权项

因此它现在更接近：

- 内部元数据
- 后续可继续利用的触发信息

而不是已经完整进入模型主决策链的“自我认知机制”。

## 11. Current Accepted Limitation

当前 observation/evidence 主链有一个必须接受的上游限制：

- 没有独立 `user` object family

这导致某些 relationship actions 当前通常只能稳定拿到：

- `target_id`

而不能保证总是拿到完整的：

- `target_snapshot(user)`

这个限制目前应归因于上游 observation 结构，而不是在 evidence 层用额外查库去“补齐”。

## 12. Related Docs

- 当前整体实现：
  - [current-architecture.md](./current-architecture.md)
- 模式原则：
  - [principles-and-modes.md](./principles-and-modes.md)
- 迁移期 observation 审查与实现细节：
  - [migration-workstreams.md](./archived/migration/migration-workstreams.md)
  - [migration-architecture-comparison.md](./archived/migration/migration-architecture-comparison.md)
