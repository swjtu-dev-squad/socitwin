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
| `ltm_exact_hit_at_3` | retrieval | 目标 `(agent_id, step_id, action_index)` 出现在 top-3 candidate 的比例 | `real-scenarios` event metrics `hit_at_3` | `v1` |
| `ltm_exact_hit_at_1` | retrieval ranking | 目标 episode 是否排在 top-1 | `real-scenarios` event metrics `hit_at_1` | `v1` |
| `ltm_mrr` | retrieval | 目标 episode first hit rank 的倒数均值 | `real-scenarios` event metrics `mrr` | `v1` |
| `cross_agent_contamination_rate` | retrieval safety | top-k candidate 中错误 `agent_id` 的比例；正常路径应接近或等于 0 | `cross_agent_top3_count / top3_candidate_slot_count` | `v1` |
| `recall_gate_success_rate` | gate | 需要 recall 的正例 probe 中 gate 打开的比例 | `VAL-RCL-08` event metrics `gate_decision` | `v1` |
| `false_recall_trigger_rate` | gate | 不需要 recall 的负例 probe 中 gate 被错误打开的比例 | `VAL-RCL-09` event metrics `gate_decision/retrieval_attempted/recalled_count` | `v1` |
| `recall_injection_trace_rate` | injection | 真实长窗口中出现 injected recall trace 的 agent/trace 比例 | `real-longwindow` metrics `recall_injected_trace_count` | `v1` |
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

当前第一阶段 probe 通常是单目标 episode，因此 `Recall@K` 与 `Hit@K` 在数值上非常接近。为了避免概念误用，内部字段使用 `ltm_exact_hit_at_k`，文档展示名使用 `LTM Retrieval Recall@3 (Exact Episode Hit@3)`。

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

### 4.1 `Recall@3` 与 `Hit@3`

当前 harness 的 `hit_at_3` 更准确地说是：

- 单目标 exact episode top-3 hit。

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
LTM Retrieval Recall@3 (Exact Episode Hit@3)
```

`@3` 是第一阶段主 KPI，因为当前 recall 默认取 top-3 候选，后续 prompt assembly 会继续在候选集上执行 overlap suppression 和 budget 裁决。`@1` 是正式辅助 KPI，用于判断排序是否已经足够尖锐。

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

## 6. Real Replay Reliability Fields

真实 simulation replay 的检索 KPI 必须同时报告样本基础，否则一次低样本运行容易被误读。

当前 `VAL-LTM-05 real_self_action_retrievability` 会输出：

- `real_probe_candidate_count`：从长期记忆中可回查到的候选 episode 数；
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
