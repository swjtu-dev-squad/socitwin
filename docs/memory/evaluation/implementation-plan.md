# Memory Evaluation Implementation Plan

- Status: Phase 1 implemented; Phase 3+ pending
- Audience: implementers
- Doc role: define concrete implementation steps for the first usable evaluation KPI output

## 1. Current Position

当前仓库已经有 evaluation harness 和真实场景 probe，并已补上第一阶段 summary 级 KPI 输出。

现有可复用基础：

- `backend/app/memory/evaluation_harness.py`
- `backend/tests/memory/evaluation/test_memory_evaluation_harness.py`
- `real-scenarios`
- `real-longwindow`
- `VAL-LTM-05`
- `VAL-RCL-08`
- `VAL-RCL-09`
- `VAL-RCL-10`

第一阶段目标不是重写 harness，而是在现有事件基础上补 summary 级指标。该部分已完成；后续重点转向 `B-level v0` 的样本可靠性收口。

测试可靠性原则见：

- [dataset-and-reliability.md](./dataset-and-reliability.md)

## 2. Phase 1: Summary KPI Aggregation

Status: implemented.

### Task 1: Add `memory_kpis`

在 `summary.json` 中新增：

```json
{
  "memory_kpis": {
    "ltm_exact_hit_at_1": null,
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
- summary 同时输出 `memory_kpi_sources` 和 `unavailable_metrics`。

### Task 2: Aggregate Retrieval Metrics

从 `VAL-LTM-05 real_self_action_retrievability` 聚合：

- `hit_at_1` -> `ltm_exact_hit_at_1`
- `hit_at_3` -> `ltm_exact_hit_at_3`
- `mrr` -> `ltm_mrr`
- `cross_agent_top3_count` + top3 slot count -> `cross_agent_contamination_rate`

如果当前 event 缺 top3 slot count，需要在 per-query score 中补：

- `retrieved_top3_count`

当前已补充：

- per-query `retrieved_top3_count`
- summary `top3_candidate_slot_count`
- summary `cross_agent_contamination_rate`

`cross_agent_contamination_rate` 是 agent filter 回归防线。正常 recall 路径已经按当前 `agent_id` 过滤长期记忆；如果该指标明显大于 0，应优先排查过滤参数传递或向量库 where filter，而不是把它解释成普通排序噪声。

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
if recall_recalled_trace_count > 0:
  recall_injection_trace_rate =
    recall_injected_trace_count / recall_recalled_trace_count
else:
  recall_injection_trace_rate = null
```

注意：

- 这是 trace 级指标；
- 不是严格 target episode injection success。
- 如果没有 recalled trace 样本，应输出 `null` 并写入不可用原因，不要输出 `0`。

## 3. Phase 2: Readable Report

Status: implemented for Phase 1 KPI output.

在 harness 的 `README.md` 输出中增加：

- KPI 摘要；
- 哪些 phase 没跑；
- 哪些指标不可用；
- retrieve-only 与 full-path 的口径说明。

目标是让人类和 AI 都能快速读懂测试结果。

当前 README 已输出：

- `Memory KPIs`
- `Unavailable Metrics`
- exact episode hit 与传统 Recall@K 的差异说明
- trace-level injection 与目标 episode 注入成功的差异说明
- retrieve-only probe 与 full-path injection 的差异说明

## 4. Phase 3: B-Level v0 Reliability Upgrade

Status: partially implemented.

在进入 controlled benchmark 和完整 scenario pack 之前，先把当前 `real-scenarios / real-longwindow` 收口成可解释的 `B-level v0`。

建议补充：

- 固定输入来源：
  - 优先改为 `file` 或 `manual` agent profiles；
- 固定 topic / 初始环境；
- usable probe count；
- skipped episode count；
- skipped reasons；
- action type distribution；
- agent distribution；
- usable probe validity gate。

当前已补充到 `VAL-LTM-05` 及共享 base metrics：

- `probe_attempt_limit`
- `usable_probe_count`
- `skipped_probe_count`
- `skipped_probe_reason_counts`
- `candidate_action_name_distribution`
- `candidate_agent_distribution`
- `usable_probe_action_name_distribution`
- `usable_probe_agent_distribution`

这一步的目标不是把 B 级做成完整 benchmark 平台，而是避免它继续停留在“随机 run 一次看看”。

仍未完成：

- 固定 `file` / `manual` agent profiles；
- 固定 topic / 初始环境；
- 更严格的 usable probe validity gate；
- 多 run 汇总。

## 5. Phase 4: Controlled Benchmark

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

第一版 controlled benchmark 的职责是提供确定性回归底座，不替代真实 simulation。它应覆盖 retrieval、rerank、agent filter、negative probe 等可控边界。

其中应优先加入：

- same-agent near-duplicate hard negatives；
- cross-agent guardrail cases；
- invalid persist boundary；
- negative probes。

## 6. Phase 5: B-Level v1 Scenario Packs

在 `B-level v0` 和 controlled benchmark 稳定之后，再补固定 scenario packs：

- `S1 stable single-topic pack`
- `S2 similar-topic interference pack`
- `S3 group / multi-context pack`

这一阶段再考虑：

- run-level / pack-level / overall 三层聚合；
- pack 级多次运行；
- 正式 benchmark 结果汇总。

## 7. Phase 6: Behavioral Scenarios

行为级 benchmark 放到第二阶段之后。

前置条件：

- retrieval KPI 已稳定；
- injection 指标已可读；
- controlled benchmark 可复现；
- 已有足够真实运行日志用于设计判定规则。

行为级场景必须按随机实验处理。不能只跑一次就把结果解释成长期记忆能力结论；至少应记录 run count、均值、波动和失败样本。

## 8. Acceptance Criteria For Phase 1

Phase 1 完成时应满足：

- `uv run pytest backend/tests/memory/evaluation/test_memory_evaluation_harness.py` 通过；
- 默认 summary 中存在 `memory_kpis`；
- 未运行 phase 的指标不会被错误写成 `0`；
- README 报告能解释指标含义；
- 文档与实际字段名一致。

已验证：

- `uv run pytest tests/memory/evaluation/test_memory_evaluation_harness.py`
- `uv run pyright app/`
- `uv run ruff check app tests/memory/evaluation/test_memory_evaluation_harness.py --ignore=E501`

Phase 3 已开始补充：

- real-run replay 的 `usable probe count`
- `skipped episode count`
- `skipped reasons`
- action / agent distribution

## 9. Open Decisions

需要后续确认：

- controlled benchmark 是否进入 CI，还是只作为手动评测入口；
- 行为级 benchmark 是否需要人工判读或 LLM-as-judge。
- 同一行为级场景至少跑几次才适合用于趋势汇报。
- `B-level v0` 使用 `file` 还是 `manual` 作为固定 agent source。

已确认：

- 内部字段使用 `ltm_exact_hit_at_3`；
- 文档展示名使用 `LTM Retrieval Recall@3 (Exact Episode Hit@3)`；
- `@1` 作为正式辅助 KPI；
- `cross_agent_contamination_rate` 使用实际返回 top-k slot 作为分母；
- phase 未运行或样本不足时，summary 字段使用 `null` 并写入不可用原因。
