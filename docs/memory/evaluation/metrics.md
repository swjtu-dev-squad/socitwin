# Long-Term Memory Metrics

- Status: active metric contract
- Audience: implementers, evaluators, report authors
- Doc role: define KPI meaning, source fields, and current implementation gaps

## 1. Metric Principles

第一阶段指标必须满足三个条件：

- 能从当前代码或小范围 summary 聚合中稳定得到；
- 能定位问题所在层级；
- 能解释给非实现者听。

因此本页把指标分成：

- `v1`：当前最值得优先落地或已接近可直接落地；
- `v1.1`：需要小幅补字段或补聚合；
- `future`：适合后续行为级评测。

## 2. Primary Metrics

| Metric | Stage | Definition | Current source | Status |
| --- | --- | --- | --- | --- |
| `ltm_exact_hit_at_3` | episode self-retrievability | episode-derived query 下，目标 `(agent_id, step_id, action_index)` 出现在 top-3 candidate 的比例 | `VAL-LTM-05` event metrics `hit_at_3` | `v1` |
| `ltm_exact_hit_at_1` | episode self-retrievability ranking | episode-derived query 下，目标 episode 是否排在 top-1 | `VAL-LTM-05` event metrics `hit_at_1` | `v1` |
| `ltm_mrr` | episode self-retrievability | episode-derived query 下，目标 episode first hit rank 的倒数均值 | `VAL-LTM-05` event metrics `mrr` | `v1` |
| `cross_agent_contamination_rate` | retrieval safety | top-k candidate 中错误 `agent_id` 的比例；正常路径应接近或等于 0 | `cross_agent_top3_count / top3_candidate_slot_count` | `v1` |
| `recall_gate_success_rate` | gate | 需要 recall 的正例 probe 中 gate 打开的比例 | `VAL-RCL-08` event metrics `gate_decision` | `v1` |
| `false_recall_trigger_rate` | gate | 不需要 recall 的负例 probe 中 gate 被错误打开的比例 | `VAL-RCL-09` event metrics `gate_decision/retrieval_attempted/recalled_count` | `v1` |
| `recall_injection_trace_rate` | injection | 真实长窗口中出现 injected recall trace 的 agent/trace 比例 | `real-longwindow` metrics `recall_injected_trace_count` | `v1` |
| `runtime_query_related_hit_at_3` | runtime retrieval | 真实 runtime query 下，top-3 是否包含与当前 observation 相关的历史 episode | 尚未实现 | `v1.1` |
| `target_episode_injection_success_rate` | injection | retrieval 命中目标 episode 后，该目标 episode 最终进入 prompt 的比例 | 需要关联 target episode 与 injected step ids | `future` |

## 3. Common Retrieval Metrics In This Project

### 3.1 `Hit@K`

通用含义是：正确目标是否出现在前 K 个结果中。

映射到 `socitwin` 时，正确目标不是普通文本块，而是一个目标 `ActionEpisode`：

```text
(agent_id, step_id, action_index)
```

所以 `Hit@3` 的实际含义是：目标历史动作事件是否进入 top-3 candidates。

### 3.2 `Recall@K`

通用含义是：所有相关项中有多少被前 K 个结果覆盖。

当前第一阶段 probe 通常是单目标 episode，因此 `Recall@K` 与 `Hit@K` 在数值上非常接近。为了避免概念误用，内部字段使用 `ltm_exact_hit_at_k`，文档展示名使用 `Episode Self-Retrievability Recall@3 (Exact Episode Hit@3)`。

### 3.3 `Precision@K`

通用含义是：前 K 个结果中有多少是真正相关的。

当前第一阶段不把它设为主指标，原因是当前更关心：

- 目标历史事件是否被找回；
- 目标是否排得足够靠前；
- agent 过滤是否可靠；
- 检到后是否进入 prompt。

如果后续 controlled benchmark 引入多相关 episode，可以再补 `Precision@K` 或 nDCG。

### 3.4 `MRR`

`MRR` 衡量目标 episode 平均排得有多靠前。

它补足 `Hit@3` 的盲点：如果目标总是排第 3，`Hit@3` 仍然很好看，但排序质量仍有明显优化空间。

## 4. Naming Notes

### 4.0 Query Scope

当前评测中至少存在两种 query，不应混用解释：

- runtime recall query：真实 simulation 中由当前 observation 的 `topic / semantic_anchors / entities / recent_episodes` 构建，用于决定本步要不要查长期记忆、查什么；
- evaluation probe query：`VAL-LTM-05` 从目标 `ActionEpisode` 的动作名、动作类别、state changes、target snapshot、local context、authored content 和 topic 构造 action-aware self-retrieval query，用于检查“这条已写入 episode 是否能被查回”。

因此 `VAL-LTM-05` 的 Hit@K / MRR 是 episode self-retrievability 指标，不等价于真实 prompt injection 效果。真实 runtime gate + retrieval 应看 `VAL-RCL-08`，真实 injected trace 应看长窗口 `VAL-RCL-10` 或 run audit 中的 memory debug trace。

### 4.1 `Recall@3` 与 `Hit@3`

当前 harness 的 `hit_at_3` 更准确地说是：

- episode-derived query 下的单目标 exact episode top-3 hit。

如果对外汇报为 `Recall@3`，必须说明：

- ground truth 是一个目标 `ActionEpisode`；
- 命中条件是 `(agent_id, step_id, action_index)` 精确匹配；
- 这个指标不是传统多相关文档检索里的宽泛 Recall@K。

推荐内部字段用：

```text
ltm_exact_hit_at_3
```

报告中可写：

```text
Episode Self-Retrievability Recall@3 (Exact Episode Hit@3)
```

`@3` 是第一阶段主 KPI，因为当前 recall 默认取 top-3 候选，后续 prompt assembly 会继续在候选集上执行 overlap suppression 和 budget 裁决。`@1` 是正式辅助 KPI，用于判断排序是否已经足够尖锐。

这个指标不应单独写成“真实 runtime recall 召回率”。真实 runtime query 下的相关召回需要 `runtime_query_related_hit_at_3` 或同类指标补充。

### 4.2 Cross-Agent Contamination

正常 recall 路径会按当前 `agent_id` 过滤长期记忆：

- `RecallPlanner.prepare()` 调用 `longterm_store.retrieve_relevant(..., agent_id=agent_id)`；
- `ChromaLongtermStore.retrieve_relevant()` 会传入 `where: agent_id == current agent`；
- 单测已经覆盖 recall planner 和 Chroma store 的 agent filter。

因此 cross-agent contamination 不应被理解成“预期会经常出现的质量指标”，而应被理解成过滤边界的回归防线。

当前 summary 已按第一版定义聚合为：

```text
cross_agent_contamination_rate =
  cross_agent_top3_count / top3_candidate_slot_count
```

其中 `top3_candidate_slot_count` 应按实际返回 candidate 数累计，而不是简单使用 `query_count * 3`，避免候选不足时低估污染率。

正常情况下该指标应接近或等于 0。一旦明显大于 0，应优先排查 agent filter 是否失效，而不是把它当成普通 rerank 质量问题。

### 4.3 Injection Success

当前可稳定拿到的是 trace 级注入信息：

- `last_injected_count`
- `last_injected_step_ids`
- `recall_injected_count`
- `recall_injected_trace_count`

这能说明长期记忆是否进入 prompt，但还不能严格证明“目标 episode 被注入”。

所以第一阶段建议先汇报：

```text
recall_injection_trace_rate
```

严格的：

```text
target_episode_injection_success_rate
```

留到后续补事件关联。

## 5. Diagnostic Metrics

| Metric | Meaning | Useful for |
| --- | --- | --- |
| `persisted_action_episode_count` | 当前运行真实写入的 action episode 数量 | 判断是否有足够样本 |
| `invalid_persist_rate` | 无效 episode 被错误持久化比例 | 防止长期层污染 |
| `retrieved_to_injected_conversion_rate` | recalled 到 injected 的转化比例 | 判断 prompt assembly / budget 是否阻断 |
| `overlap_filtered_rate` | recall candidate 被 overlap suppression 过滤比例 | 判断 recent/compressed 是否已覆盖 |
| `prompt_budget_block_rate` | 因总 prompt budget 不能注入的比例 | 判断上下文预算压力 |
| `recall_budget_block_rate` | 因 recall budget 不能注入的比例 | 判断 recall 局部预算是否过紧 |

### 5.1 Post-Based Runtime Replay Metrics

`VAL-RCL-11 post_based_runtime_replay` 是当前 B-level v0.5 的 observation-summary 检索测试。

它的 query 生成规则是：

```text
query_text = visible_post.summary
```

其中 `post_id` 不进入检索文本，只用于判定 ground truth 和调试。

核心字段：

- `post_probe_count`：本轮从所有 official step 的 prompt-visible snapshot 中生成的 post query 总数。
- `post_probe_with_ground_truth_count`：存在结构化正确答案的 post query 数。
- `post_probe_without_ground_truth_count`：没有历史相关 episode 的 post query 数；这类不算 miss。
- `runtime_first_post_with_ground_truth_count`：第一个可见 post 中有正确答案的 query 数，更接近当前真实 runtime query 覆盖范围。
- `non_first_post_with_ground_truth_count`：非第一个可见 post 中有正确答案的 query 数，用于暴露当前 runtime 只查第一个 post 的覆盖缺陷。
- `hit_at_1` / `hit_at_3` / `mrr`：只在有 ground truth 的 post query 上计算。
- `runtime_first_post_hit_at_3`：第一个 post 子集的 Hit@3。
- `non_first_post_hit_at_3`：非第一个 post 子集的 Hit@3。
- `self_authored_post_hit_at_3`：可见帖子作者就是当前 agent，且有对应 `create_post` 历史 episode 时的 Hit@3。
- `diagnosis_counts`：按 `hit`、`no_ground_truth`、`same_agent_wrong_target`、`cross_agent` 等诊断分类计数。
- `ground_truth_action_distribution`：正确答案 episode 的动作类型分布。

硬正确答案只接受结构化 post 关系：

- `episode.target_type == "post"` 且 `episode.target_id == source_post_id`；
- 或 `episode.local_context.parent_post.post_id == source_post_id`；
- 或 self-authored 可见 post 对应历史 `create_post` 的 `created_post:{source_post_id}`。

不纳入第一版硬正确答案：

- `follow` / `unfollow` / `mute` / `unmute`；
- group actions；
- 只有主题相似但没有 post 结构关系的 episode。

## 6. Real Replay Reliability Fields

真实 simulation replay 的检索 KPI 必须同时报告样本基础，否则一次低样本运行容易被误读。

当前 `VAL-LTM-05 real_self_action_retrievability` 会输出：

- `real_probe_candidate_count`：从 Chroma 全量枚举并排除 warm-up 后得到的候选 episode 数；
- `probe_attempt_limit`：本轮最多拿多少候选出题，当前默认 25，可通过 `--scenario-probe-limit` 调整；
- `usable_probe_count`：实际能构造 query 的 probe 数；
- `skipped_probe_count`：没有进入 probe 的候选数；
- `skipped_probe_reason_counts`：跳过原因，例如 `missing_query_text` 或 `outside_probe_limit`；
- `candidate_action_name_distribution`：候选池动作分布；
- `candidate_agent_distribution`：候选池 agent 分布；
- `usable_probe_action_name_distribution`：实际出题样本动作分布；
- `usable_probe_agent_distribution`：实际出题样本 agent 分布。

这些字段不直接等于记忆能力得分，但决定本轮结果是否有解释价值。

提高 `probe_attempt_limit` 后，`like_post` / `repost` 等弱语义动作可能显著拉低 exact episode hit。原因是当前 real-run replay 的 query 通常来自目标内容或 episode 摘要；对点赞、转发这类动作来说，目标正文可能与同一步的 quote/create 或同主题历史高度相似，但缺少“我点赞/我转发了它”的动作语义。因此这类掉分需要拆开解释：

- 如果目标 episode 的 `agent_id` 被过滤正确，`cross_agent_contamination_rate` 仍为 0，说明 agent 隔离没有坏；
- 如果 miss 集中在 `like_post` / `repost`，优先视为 probe query 构造或弱动作 episode 语义不足问题；
- 如果 `create_post` / `comment` 也大量 miss，才更直接指向 embedding/rerank 或 episode document 质量问题。

## 7. Minimum Summary Output

第一阶段已在 `summary.json` 增加：

```json
{
  "memory_kpis": {
    "ltm_exact_hit_at_1": 0.62,
    "ltm_exact_hit_at_3": 0.84,
    "ltm_mrr": 0.71,
    "cross_agent_contamination_rate": 0.0,
    "recall_gate_success_rate": 0.88,
    "false_recall_trigger_rate": 0.06,
    "recall_injection_trace_rate": 0.73
  }
}
```

如果某个 phase 没跑，对应字段使用 `null`，并在 `unavailable_metrics` 中说明缺失原因，不用 `0` 冒充真实结果。

同时输出：

- `memory_kpi_sources`：记录每个 KPI 对应的 event name；
- `unavailable_metrics`：记录不可用指标、原因、所需 event 和所需 metric；
- run 目录下的 `README.md`：输出中文 KPI 摘要、指标解释、样本覆盖、按动作类型命中率、未命中样例、不可用指标和 retrieve-only / injection 口径说明。

当前 `events.jsonl` 的 `VAL-LTM-05.evidence.per_query` 会保留逐条 probe 的关键过程证据：

- `query_text`：本条 probe 实际用于检索的文本；
- `expected_key / expected_episode`：目标 episode 的精确 key 和摘要；
- `retrieved_keys / retrieved_episodes`：top-k 返回候选的 key 和摘要；
- `retrieved_same_agent_flags / retrieved_same_step_flags`：辅助判断是跨 agent、同一步多动作，还是普通排序问题；
- `expected_action_name / retrieved_action_names`：辅助判断是否集中在 `like_post`、`repost` 等弱语义动作。

如果需要判断真实模拟和长期记忆形成过程是否正常，应优先查看 run 目录下的过程审计文件：

- `artifacts/real-scenarios/step_audit.jsonl`：每步的 `step_result`、`memory_debug`、agent 本步动作和记忆状态；
- `artifacts/real-scenarios/episode_audit.jsonl`：每条 `ActionEpisode` 的完整 payload、是否持久化、probe query、长期记忆 document；
- `artifacts/real-scenarios/audit_summary.json`：重复 query、episode 动作分布和 LTM 指标摘要；
- `artifacts/real-scenarios/simulation.db`：从临时目录复制出的 OASIS SQLite 数据库。

这些文件用于先回答“agent 到底做了什么、记忆到底写了什么”，再解释 Hit@K / MRR。
