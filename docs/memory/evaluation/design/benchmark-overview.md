# Memory Evaluation Benchmark Overview

- Status: active benchmark design
- Audience: implementers, evaluators, report authors
- Doc role: consolidated evaluation target, KPI contract, scenario plan, and reporting boundaries for `action_v1`

## 1. Purpose

本文档合并原先分散在下面几份文档里的核心内容：

- `longterm-memory-evaluation-plan.md`
- `metrics.md`
- `scenarios.md`

合并后的职责是回答：

1. 当前长期记忆评估到底测什么；
2. 指标如何定义，哪些指标可以正式汇报；
3. 真实运行、受控 benchmark、行为级场景之间如何分层；
4. S1/S2/B-level 的结果应该如何解释。

更细的数据集、ground truth 和随机性控制见：

- [dataset-and-reliability.md](./dataset-and-reliability.md)

具体 harness 运行方式见：

- [../runtime/testing-and-evaluation.md](../runtime/testing-and-evaluation.md)

## 2. Evaluation Target

长期记忆评测不能只回答“有没有召回”，而要拆开回答五个问题：

1. 写入层：应该进入长期层的 `ActionEpisode` 有没有被正确持久化。
2. 检索层：需要回忆时，目标历史事件能否被检到。
3. 门控层：系统是否在正确时机触发 recall，而不是乱查或漏查。
4. 注入层：检到的长期记忆是否真的进入 prompt。
5. 行为层：进入 prompt 的长期记忆是否改善行为连续性和社交一致性。

第一阶段重点不是证明行为完全变好，而是建立可解释、可复测的工程指标。

当前最小 ground truth 单元是一个具体历史动作事件：

```text
(agent_id, step_id, action_index)
```

这让评测可以准确判断：

- 是否查回目标 `ActionEpisode`；
- 是否混淆了同主题但非目标事件；
- 是否保持了 agent 隔离。

## 3. Query Scope Boundary

当前至少存在两种 query，不能混用解释。

### 3.1 Runtime Recall Query

真实 simulation 中由当前 observation 感知结果生成，路径是：

```text
topic -> semantic_anchors -> entities -> recent_episodes
```

当前最常见的 query 来源是第一条可见 post/group 的 `summary`。它主要回答：

```text
当前我看到了什么环境线索，因此应该从长期记忆中唤起哪些过去经历。
```

### 3.2 Evaluation Probe Query

`VAL-LTM-05 real_self_action_retrievability` 从目标 `ActionEpisode` 自身字段反推 query，包括动作名、动作类别、state changes、target snapshot、local context、authored content 和 topic。

它主要回答：

```text
这条已经写入的 episode 在给定自身线索时，能不能被查回。
```

因此 `VAL-LTM-05` 的 Hit@K / MRR 是 episode self-retrievability，不等价于真实 runtime recall，也不等价于 prompt injection。

当前已补 `VAL-RCL-11 post_linked_final_lookup`，用真实 observation 中每个可见 post 的 `summary` 出题，评估 final-store post-linked lookup。完整 `last_recall_query_text` trace replay 仍是后续缺口。

## 4. Evaluation Layers

### 4.1 A-Level Deterministic Checks

目标：建立稳定底座，可进入轻量回归。

当前覆盖：

- `preflight`
- `deterministic`
- `real-smoke`
- module / integration tests

适合验证：

- payload normalization；
- long-term write；
- agent filter；
- recall gate；
- overlap suppression；
- budget stop reason。

它不回答“真实模拟中 agent 行为是否变好”，但能判断 memory 子系统是否稳定工作。

### 4.2 B-Level Real-Run Replay

目标：真实跑一段 `action_v1` simulation，再对本次实际产生的 `ActionEpisode` 和 observation trace 做回查。

当前主线：

- `VAL-LTM-05`：episode self-retrievability；
- `VAL-RCL-11`：post-linked final lookup；
- `VAL-RCL-08/09`：retrieve-only recall sanity；
- `VAL-RCL-10`：长窗口 trace-level injection。

它的稳定性来自：

- ground truth 来自本次真实运行实际写入的 episode；
- 评分目标是“已写入的历史能否被回查”，不是要求每次产生完全相同的社交轨迹。

当前 B-level 不是开放世界随机 simulation 的一次性跑分，而是半受控真实 replay benchmark。

### 4.3 C-Level Behavioral Scenarios

目标：判断长期记忆是否改善最终行为。

适合覆盖：

- self-authored continuity；
- target/thread continuity；
- relationship continuity；
- group context continuity；
- contradiction reduction。

这类测试受主模型和社交模拟随机性影响最大，不应只跑一次就下结论。第一阶段只作为后续设计，不作为硬门槛。

## 5. Primary KPI Contract

第一阶段正式汇报下面这组指标。

| Metric | Stage | Definition | Source | Status |
| --- | --- | --- | --- | --- |
| `ltm_exact_hit_at_1` | episode self-retrievability ranking | episode-derived query 下，目标 episode 是否排在 top-1 | `VAL-LTM-05.hit_at_1` | `v1` |
| `ltm_exact_hit_at_3` | episode self-retrievability | episode-derived query 下，目标 `(agent_id, step_id, action_index)` 是否出现在 top-3 | `VAL-LTM-05.hit_at_3` | `v1` |
| `ltm_mrr` | episode self-retrievability | 目标 episode first hit rank 的倒数均值 | `VAL-LTM-05.mrr` | `v1` |
| `cross_agent_contamination_rate` | retrieval safety | top-k candidate 中错误 `agent_id` 的比例 | `cross_agent_top3_count / top3_candidate_slot_count` | `v1` |
| `recall_gate_success_rate` | gate | 正例 recall probe 中 gate 打开的比例 | `VAL-RCL-08.gate_decision` | `v1` |
| `false_recall_trigger_rate` | gate | 空/弱 observation 下 gate 被错误打开的比例 | `VAL-RCL-09` | `v1` |
| `recall_injection_trace_rate` | injection | 真实长窗口中 recalled trace 转成 injected trace 的比例 | `VAL-RCL-10` | `v1` |
| `runtime_query_related_hit_at_3` | runtime retrieval | 真实 runtime query 下，top-3 是否包含相关历史 episode | 尚未实现 | `v1.1` |
| `target_episode_injection_success_rate` | injection | retrieval 命中目标 episode 后，该目标 episode 是否进入 prompt | 需要 episode-key 关联 | `future` |

如果某个 phase 没跑，对应 summary KPI 使用 `null`，并在 `unavailable_metrics` 中说明缺失原因，不用 `0` 冒充真实结果。

## 6. Metric Semantics

### 6.1 Hit@K / Recall@K

通用 `Hit@K` 表示正确目标是否出现在前 K 个结果中。

在 `socitwin` 当前第一阶段，正确目标通常是单个 exact `ActionEpisode`，因此内部字段用：

```text
ltm_exact_hit_at_3
```

报告中可以写：

```text
Episode Self-Retrievability Recall@3 (Exact Episode Hit@3)
```

但必须说明：

- ground truth 是一个目标 `ActionEpisode`；
- 命中条件是 `(agent_id, step_id, action_index)` 精确匹配；
- 这个指标不是传统多相关文档 Recall@K；
- 它不是真实 runtime recall 成功率。

### 6.2 MRR

`MRR` 衡量目标 episode 平均排得多靠前。

它补足 `Hit@3` 的盲点：如果目标总是排第 3，`Hit@3` 仍然很好看，但排序质量仍有明显优化空间。

### 6.3 Cross-Agent Contamination

正常 recall 路径会按当前 `agent_id` 过滤长期记忆：

```text
RecallPlanner.prepare(...)
  -> longterm_store.retrieve_relevant(..., agent_id=agent_id)
  -> Chroma where: agent_id == current agent
```

因此 cross-agent contamination 是过滤边界回归防线，不是常规排序质量指标。

如果它明显大于 0，应优先排查 agent filter，而不是先调 embedding / rerank。

### 6.4 Injection Trace

当前可稳定拿到的是 trace 级注入信息：

- `last_injected_count`
- `last_injected_step_ids`
- `recall_injected_trace_count`

它能说明长期记忆是否进入 prompt，但不能严格证明“目标 episode 被注入”。严格 target-level injection 需要后续补 episode-key 关联。

## 7. Diagnostic Metrics

辅助诊断字段包括：

| Metric | Meaning | Useful for |
| --- | --- | --- |
| `persisted_action_episode_count` | 当前运行真实写入的 action episode 数量 | 判断是否有足够样本 |
| `invalid_persist_rate` | 无效 episode 被错误持久化比例 | 防止长期层污染 |
| `retrieved_to_injected_conversion_rate` | recalled 到 injected 的转化比例 | 判断 prompt assembly / budget 是否阻断 |
| `overlap_filtered_rate` | recall candidate 被 overlap suppression 过滤比例 | 判断 recent/compressed 是否已覆盖 |
| `prompt_budget_block_rate` | 因总 prompt budget 不能注入的比例 | 判断上下文预算压力 |
| `recall_budget_block_rate` | 因 recall budget 不能注入的比例 | 判断 recall 局部预算是否过紧 |

真实 replay 还必须报告样本基础：

- `real_probe_candidate_count`
- `probe_attempt_limit`
- `usable_probe_count`
- `skipped_probe_count`
- `skipped_probe_reason_counts`
- `candidate_action_name_distribution`
- `candidate_agent_distribution`
- `usable_probe_action_name_distribution`
- `usable_probe_agent_distribution`

否则一次低样本运行容易被误读。

## 8. Post-Linked Final Lookup

`VAL-RCL-11 post_linked_final_lookup` 是当前 B-level v0.5 的 observation-summary 检索测试。

query 生成规则：

```text
query_text = visible_post.summary
```

`post_id` 不进入检索文本，只用于 final-store ground truth 和调试。

它测的是：

```text
给定 agent A 曾经在 observation 中看见过 post P，
整场模拟结束后，能否用 P 的 summary 从 A 的长期记忆中找回 A 与 P 相关的动作事件。
```

硬正确答案只接受结构化 post 关系：

- `episode.target_type == "post"` 且 `episode.target_id == source_post_id`；
- 或 `episode.local_context.parent_post.post_id == source_post_id`；
- 或 self-authored 可见 post 对应 `create_post` 的 `created_post:{source_post_id}`。

核心字段：

- `post_probe_count`
- `post_probe_with_ground_truth_count`
- `post_probe_without_ground_truth_count`
- `hit_at_1`
- `hit_at_3`
- `mrr`
- `self_authored_post_hit_at_3`
- `diagnosis_counts`
- `ground_truth_action_distribution`

`post_probe_without_ground_truth_count` 不算 miss，它表示当前 agent 的最终长期记忆中没有与该可见 post 结构相关的可测答案。

## 9. Scenario Groups

### 9.1 Real-Run Episode Replay

流程：

1. 真实运行一段 `action_v1` simulation。
2. 从 long-term store 中抽取真实 `ActionEpisode`。
3. 为 episode 构造 episode-derived probe query，或收集真实 runtime query。
4. 回查当前 recall / retrieval 路径。
5. 统计 self-retrievability、MRR、cross-agent contamination、gate、injection 等指标。

优点：

- 最接近真实系统；
- 能覆盖真实 episode 构造质量；
- 可复用现有 `real-scenarios`。

缺点：

- 受主模型随机性影响；
- episode 分布不可完全控制；
- 不适合作为唯一回归集。

### 9.2 Controlled Episode Benchmark

当前不作为主线阻塞项，但适合后续稳定回归。

流程：

1. 人工构造 20 到 50 个 `ActionEpisode` payload。
2. 覆盖 post、comment、follow、group message 等核心动作。
3. 每个 episode 配 1 到 3 个 probe query。
4. 直接写入 long-term store 后执行 retrieval benchmark。

优点：

- 可复现；
- 适合比较 embedding / rerank 调整；
- 适合 CI 或轻量回归。

必须包含：

- same-agent near-duplicate hard negatives；
- cross-agent similar-topic guardrail cases；
- negative probes；
- invalid / non-persistable 边界。

### 9.3 Behavioral Scenario Runs

流程：

1. 固定 topic、agent config、step count 和 memory mode。
2. 同一场景重复运行多次。
3. 记录 recall 是否注入、行为是否连续、是否出现矛盾或自我记忆错乱。
4. 报告均值、波动和失败样本。

第一阶段只做观察和后续设计，不作为硬门槛。

## 10. B-Level Evolution

当前路线：

- `B-level v0`
  - 使用固定 S1/S2 scenario pack；
  - 已补 usable probe 统计和 skipped reasons；
  - 主指标是 episode self-retrievability。
- `B-level v0.5`
  - 已补 post-linked final lookup；
  - 使用真实 observation 中每个可见 post 的 `summary` 出题。
- `B-level v1`
  - 后续补完整 `last_recall_query_text` trace replay、多 run 聚合、更多 scenario packs 或 controlled benchmark。

当前固定输入 pack：

- `s1_stable_single_topic`
  - 来源：脱敏改写后的 `Singapore's Elite Leader Path vs UK's Political Rise`；
  - 目标：稳定产生 post/comment 类 `ActionEpisode`；
  - 重点指标：persisted episode count、usable probe count、Hit@1、Hit@3、MRR。
- `s2_similar_topic_interference`
  - 来源：脱敏改写后的 `Ben Judah Proposes Anglo-Gaullist Overhaul for Britain`；
  - 目标：保留同主题、相似表达、不同 agent 的结构；
  - 重点指标：Hit@1、Hit@3、MRR、cross-agent contamination、same-agent wrong target。

运行示例：

```bash
uv run python -m app.memory.evaluation_harness \
  --phase real-scenarios \
  --scenario-pack s1_stable_single_topic \
  --scenario-steps 10
```

`--scenario-probe-limit` 默认 `0`，表示全量覆盖候选 episode。正式评测建议保持默认全量；只有调试速度或成本压力很大时，才手动传入正数做抽样。

## 11. Future Scenario Candidates

后续可补：

- `S3 group / multi-context pack`
  - group message、thread、local context continuity。
- self-authored continuity
  - agent 是否记得自己曾经发过/评论过某内容。
- target continuity
  - 后续再次遇到同一 post / comment thread 时，是否能关联历史目标。
- group context continuity
  - 群组、群消息、群组语境是否形成连续记忆。
- invalid action pollution
  - invalid target、hallucinated action、失败 tool result 不污染长期层。
- multi-action step pairing
  - 一步多动作时 result / outcome 是否被错配。
- cross-agent similar topic
  - 主要用于 agent filter guardrail；同时必须补 same-agent near-duplicate，否则无法充分测试排序歧义。

## 12. Reporting Position

推荐汇报口径：

- 当前 `socitwin` 的长期记忆以 `ActionEpisode` 为结构化持久化单元。
- recall 主链被拆成 gate、retrieval、injection 三个可观测阶段。
- 当前 B 级核心指标是 `Episode Self-Retrievability Recall@3 (Exact Episode Hit@3)`、Hit@1、MRR、agent 过滤回归防线和 injection trace rate。
- runtime query 主要来自当前 observation summary；当前已用 `VAL-RCL-11` 先覆盖 final-store post-linked lookup。
- 行为级连续性测试会作为第二阶段增强，不直接替代检索和注入指标。

避免汇报口径：

- “召回率高，所以 agent 行为已经稳定。”
- “embedding 命中率高，所以长期记忆系统没有问题。”
- “recalled_count 增加，所以模型真实使用了长期记忆。”
