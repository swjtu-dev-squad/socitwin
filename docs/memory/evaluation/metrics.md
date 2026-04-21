# Long-Term Memory Metrics

- Status: draft metric contract
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
| `ltm_mrr` | retrieval | 目标 episode first hit rank 的倒数均值 | `real-scenarios` event metrics `mrr` | `v1` |
| `cross_agent_contamination_rate` | retrieval safety | top-k candidate 中错误 `agent_id` 的比例 | 当前已有 `cross_agent_retrieved_count` / `cross_agent_top3_count`，还需 summary rate | `v1.1` |
| `recall_gate_success_rate` | gate | 需要 recall 的正例 probe 中 gate 打开的比例 | `gate_decision` / `last_recall_gate` | `v1.1` |
| `false_recall_trigger_rate` | gate | 不需要 recall 的负例 probe 中 gate 被错误打开的比例 | `VAL-RCL-09` / empty observation probe | `v1.1` |
| `recall_injection_trace_rate` | injection | 真实长窗口中出现 injected recall trace 的 agent/trace 比例 | `real-longwindow` metrics `recall_injected_trace_count` | `v1` |
| `target_episode_injection_success_rate` | injection | retrieval 命中目标 episode 后，该目标 episode 最终进入 prompt 的比例 | 需要关联 target episode 与 injected step ids | `future` |

## 3. Naming Notes

### 3.1 `Recall@3` 与 `Hit@3`

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
LTM Retrieval Recall@3 / Exact Episode Hit@3
```

### 3.2 Cross-Agent Contamination

当前代码已经统计了 top-3 中跨 agent 的数量，但还没有统一 rate。

建议第一版定义为：

```text
cross_agent_contamination_rate =
  cross_agent_top3_count / top3_candidate_slot_count
```

其中 `top3_candidate_slot_count` 应按实际返回 candidate 数累计，而不是简单使用 `query_count * 3`，避免候选不足时低估污染率。

### 3.3 Injection Success

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

## 4. Diagnostic Metrics

| Metric | Meaning | Useful for |
| --- | --- | --- |
| `persisted_action_episode_count` | 当前运行真实写入的 action episode 数量 | 判断是否有足够样本 |
| `invalid_persist_rate` | 无效 episode 被错误持久化比例 | 防止长期层污染 |
| `retrieved_to_injected_conversion_rate` | recalled 到 injected 的转化比例 | 判断 prompt assembly / budget 是否阻断 |
| `overlap_filtered_rate` | recall candidate 被 overlap suppression 过滤比例 | 判断 recent/compressed 是否已覆盖 |
| `prompt_budget_block_rate` | 因总 prompt budget 不能注入的比例 | 判断上下文预算压力 |
| `recall_budget_block_rate` | 因 recall budget 不能注入的比例 | 判断 recall 局部预算是否过紧 |

## 5. Minimum Summary Output

第一阶段建议在 `summary.json` 增加：

```json
{
  "memory_kpis": {
    "ltm_exact_hit_at_3": 0.84,
    "ltm_mrr": 0.71,
    "cross_agent_contamination_rate": 0.08,
    "recall_gate_success_rate": 0.88,
    "false_recall_trigger_rate": 0.06,
    "recall_injection_trace_rate": 0.73
  }
}
```

如果某个 phase 没跑，对应字段应使用 `null` 或放入 `unavailable_metrics` 说明，不要用 `0` 冒充真实结果。

