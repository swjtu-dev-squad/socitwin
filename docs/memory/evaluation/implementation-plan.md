# Memory Evaluation Implementation Plan

- Status: draft implementation checklist
- Audience: implementers
- Doc role: define concrete implementation steps for the first usable evaluation KPI output

## 1. Current Position

当前仓库已经有 evaluation harness 和真实场景 probe，但还缺统一 KPI 输出。

现有可复用基础：

- `backend/app/memory/evaluation_harness.py`
- `backend/tests/memory/evaluation/test_memory_evaluation_harness.py`
- `real-scenarios`
- `real-longwindow`
- `VAL-LTM-05`
- `VAL-RCL-08`
- `VAL-RCL-09`
- `VAL-RCL-10`

本轮目标不是重写 harness，而是在现有事件基础上补 summary 级指标。

## 2. Phase 1: Summary KPI Aggregation

### Task 1: Add `memory_kpis`

在 `summary.json` 中新增：

```json
{
  "memory_kpis": {
    "ltm_exact_hit_at_3": null,
    "ltm_mrr": null,
    "cross_agent_contamination_rate": null,
    "recall_gate_success_rate": null,
    "false_recall_trigger_rate": null,
    "recall_injection_trace_rate": null
  }
}
```

规则：

- phase 未运行时使用 `null`；
- 不用 `0` 表示缺失；
- 指标来源要能追溯到 event name。

### Task 2: Aggregate Retrieval Metrics

从 `VAL-LTM-05 real_self_action_retrievability` 聚合：

- `hit_at_3` -> `ltm_exact_hit_at_3`
- `mrr` -> `ltm_mrr`
- `cross_agent_top3_count` + top3 slot count -> `cross_agent_contamination_rate`

如果当前 event 缺 top3 slot count，需要在 per-query score 中补：

- `retrieved_top3_count`

### Task 3: Aggregate Gate Metrics

从 positive probe 和 negative probe 聚合：

- `VAL-RCL-08` 的 `gate_decision` -> positive gate success；
- `VAL-RCL-09` 的 gate decision / recalled count -> false recall trigger。

如果样本不足，应输出 `null` 并在 `unavailable_metrics` 解释原因。

### Task 4: Aggregate Injection Metrics

从 `VAL-RCL-10` 聚合：

- `recall_injected_trace_count`
- `recall_recalled_trace_count`
- `recall_recalled_not_injected_trace_count`
- `recall_overlap_filtered_count`
- `recall_selection_stop_reason_counts`

第一版指标：

```text
recall_injection_trace_rate =
  recall_injected_trace_count / max(1, recall_recalled_trace_count)
```

注意：

- 这是 trace 级指标；
- 不是严格 target episode injection success。

## 3. Phase 2: Readable Report

在 harness 的 `README.md` 输出中增加：

- KPI 摘要；
- 哪些 phase 没跑；
- 哪些指标不可用；
- retrieve-only 与 full-path 的口径说明。

目标是让人类和 AI 都能快速读懂测试结果。

## 4. Phase 3: Controlled Benchmark

新增小型受控 benchmark 前，需要先决定 fixture 放置位置。

建议候选：

- `backend/tests/memory/evaluation/fixtures/controlled_episodes.json`

第一版覆盖：

- self post；
- comment；
- follow；
- group message；
- cross-agent similar topic。

该阶段不依赖真实主模型，主要用于 embedding / rerank 回归。

## 5. Phase 4: Behavioral Scenarios

行为级 benchmark 放到第二阶段之后。

前置条件：

- retrieval KPI 已稳定；
- injection 指标已可读；
- controlled benchmark 可复现；
- 已有足够真实运行日志用于设计判定规则。

## 6. Acceptance Criteria For Phase 1

Phase 1 完成时应满足：

- `uv run pytest backend/tests/memory/evaluation/test_memory_evaluation_harness.py` 通过；
- 默认 summary 中存在 `memory_kpis`；
- 未运行 phase 的指标不会被错误写成 `0`；
- README 报告能解释指标含义；
- 文档与实际字段名一致。

## 7. Open Decisions

需要后续确认：

- 对外汇报时主名使用 `LTM Retrieval Recall@3` 还是 `Exact Episode Hit@3`；
- `cross_agent_contamination_rate` 分母使用实际 top-k slot 还是固定 `query_count * k`；
- controlled benchmark 是否进入 CI，还是只作为手动评测入口；
- 行为级 benchmark 是否需要人工判读或 LLM-as-judge。

