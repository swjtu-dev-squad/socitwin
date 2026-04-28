# Audit And Validation

- Status: active register
- Audience: implementers, reviewers, fidelity auditors
- Doc role: track current memory risks, validation expectations, and follow-up corrections in `socitwin`

## 1. Purpose

本文档是当前新仓库记忆路线的审查台账。

它不负责重复讲完整架构，而负责回答：

- 当前哪些风险最值得继续盯；
- 文档和实现不一致时怎么记；
- 每次修正后最少要补什么验证；
- 哪些问题已经确认，哪些仍在开放状态。

## 2. Audit Principles

当前审查仍然默认遵守三条原则：

- 以保真度为中心，而不是以链路存在为中心
- 以当前系统完整能力模型为准，而不是只看最小 smoke
- 审查清单保持开放，不能把新风险埋在零散讨论里

## 3. Validation Framework

当前验证仍然按三层理解：

1. 功能正确性验证
2. 语义 / 行为合理性验证
3. 效果与性能评估

这三层都重要，不能因为链路能跑通就默认语义已经正确。

系统级运行入口见：

- [testing-and-evaluation.md](./testing-and-evaluation.md)

场景目录见：

- [validation-scenarios.md](./validation-scenarios.md)

## 4. Status Model

当前活动条目统一使用：

- `open`
  - 风险已确认，仍需继续审查或补验证
- `resolved`
  - 当前轮代码/文档修正已完成，但仍可保留回归要求
- `needs-code-check`
  - 还不能先下结论，需继续核代码或运行结果
- `doc-drift`
  - 当前主要问题是文档与实现漂移，不是已确认行为错误

## 5. Register Maintenance Rule

后续维护这份台账时，统一按下面规则更新：

- 每个活动问题只保留一个主条目编号
- 代码修复完成时，不直接删除条目
- 发现只是文档落后时，标记为 `doc-drift`
- 还不能确认风险是否真实存在时，标记为 `needs-code-check`

## 6. Validation Record Format

每次做 memory 主链相关修正，建议在对应条目下补最小记录：

- 日期
- 变更范围
- 验证场景
- 结果
  - `pass / partial / fail`
- 证据入口
- 剩余风险

## 7. Current Audit Focus

当前优先关注以下风险簇：

- observation fidelity
- short-term maintenance fidelity
- long-term write fidelity
- recall fidelity
- budget recovery fidelity
- 测试口径与指标可读性

## 8. Active Register

### `AUD-OBS-01` Observation 主链压缩传播风险

- 状态：`open`
- 风险：
  - 长文本 hard cap 或 interaction shrink 后，主体语义可能在 observation 阶段就被抹掉；
  - 且压缩后的 snapshot 会继续流向 perception、episode、recall。
- 当前代码锚点：
  - [observation_shaper.py](/home/grayg/socitwin/backend/app/memory/observation_shaper.py)
  - [observation_semantics.py](/home/grayg/socitwin/backend/app/memory/observation_semantics.py)
- 最小验证：
  - `VAL-OBS-01`
  - `VAL-OBS-02`
- 证据入口：
  - `render_stats.final_shaping_stage`
  - `prompt_visible_snapshot`
  - `ActionEpisode.target_snapshot`

### `AUD-OBS-02` Group / Message 在强退化阶段的保真

- 状态：`open`
- 风险：
  - group 与 group message 在 interaction shrink / physical fallback 下可能退化成计数或 sample；
  - 这会影响群体语境、动作目标解析和后续 recall。
- 当前代码锚点：
  - [observation_shaper.py](/home/grayg/socitwin/backend/app/memory/observation_shaper.py)
  - [action_evidence.py](/home/grayg/socitwin/backend/app/memory/action_evidence.py)
- 最小验证：
  - `VAL-OBS-03`
- 证据入口：
  - `visible_payload.groups`
  - `prompt_visible_snapshot.groups`
  - `target_resolution_status`
  - `degraded_evidence`

### `AUD-STM-01` Recent / Compressed 维护是否破坏近端连续性

- 状态：`open`
- 风险：
  - recent eviction、compressed merge、heartbeat drop 如果过于激进，可能会损伤近中程行为连续性。
- 当前代码锚点：
  - [consolidator.py](/home/grayg/socitwin/backend/app/memory/consolidator.py)
  - [working_memory.py](/home/grayg/socitwin/backend/app/memory/working_memory.py)
  - [memory_rendering.py](/home/grayg/socitwin/backend/app/memory/memory_rendering.py)
- 最小验证：
  - `VAL-STM-01`
  - `VAL-STM-02`
  - `VAL-STM-03`
- 证据入口：
  - `recent.segments`
  - `compressed.action_blocks`
  - `compressed.heartbeat_ranges`
  - `source_action_keys`
  - `covered_step_ids`

### `AUD-LTM-01` Long-Term 写入可信度边界

- 状态：`resolved`
- 风险：
  - `hallucinated` 或 `invalid_target` episode 如果被错误持久化，会直接污染长期层。
- 当前代码锚点：
  - [agent.py](/home/grayg/socitwin/backend/app/memory/agent.py)
  - [episodic_memory.py](/home/grayg/socitwin/backend/app/memory/episodic_memory.py)
- 当前结论：
  - `hallucinated` 和 `invalid_target` 当前不会进入长期层；
  - long-term write timing 已经和 recent eviction 解耦。
- 最小回归：
  - `VAL-LTM-01`
  - `VAL-LTM-02`

### `AUD-LTM-02` 事件化覆盖与 `state_changes` 质量

- 状态：`open`
- 风险：
  - 若核心社交动作的 `state_changes` 长期为空或配对错误，会削弱长期层的工程价值和后续 recall 质量。
- 当前代码锚点：
  - [episodic_memory.py](/home/grayg/socitwin/backend/app/memory/episodic_memory.py)
  - [agent.py](/home/grayg/socitwin/backend/app/memory/agent.py)
- 最小验证：
  - `VAL-LTM-03`
  - `VAL-LTM-04`
- 证据入口：
  - `ACTION_RESULT.metadata.state_changes`
  - `ActionEpisode.state_changes`

### `AUD-RCL-01` Recall Gate / Overlap / Injection Fidelity

- 状态：`open`
- 风险：
  - recall 可能在错误时机触发、被 overlap 过强抑制，或在 retrieval 成功后仍无法进入 prompt。
- 当前代码锚点：
  - [recall_planner.py](/home/grayg/socitwin/backend/app/memory/recall_planner.py)
  - [prompt_assembler.py](/home/grayg/socitwin/backend/app/memory/prompt_assembler.py)
  - [working_memory.py](/home/grayg/socitwin/backend/app/memory/working_memory.py)
- 最小验证：
  - `VAL-RCL-02`
  - `VAL-RCL-03`
  - `VAL-RCL-04`
  - `VAL-RCL-05`
  - `VAL-RCL-10`
- 证据入口：
  - `gate_reason_flags`
  - `recall_overlap_filtered_count`
  - `recall_selection_stop_reason`
  - injected / recalled trace

### `AUD-RCL-02` Long-Term 检索命中与召回质量

- 状态：`open`
- 风险：
  - long-term 检索可能能命中，但命中的是同主题相似样本而不是真正目标 episode；
  - 也可能因为 embedding/排序质量不足，导致真实可回忆性不稳定。
- 当前代码锚点：
  - [longterm.py](/home/grayg/socitwin/backend/app/memory/longterm.py)
  - [recall_planner.py](/home/grayg/socitwin/backend/app/memory/recall_planner.py)
  - [evaluation_harness.py](/home/grayg/socitwin/backend/app/memory/evaluation_harness.py)
- 最小验证：
  - `VAL-LTM-05`
  - `VAL-RCL-08`
  - `VAL-RCL-09`
- 证据入口：
  - `hit@k`
  - `MRR`
  - candidate list
  - cross-agent mismatch

### `AUD-BGT-01` Budget Recovery 是否破坏主链层级

- 状态：`open`
- 风险：
  - base prompt 过预算、provider overflow 或 budget recovery 失败时，可能破坏当前 observation / recent / recall 的优先级关系。
- 当前代码锚点：
  - [budget_recovery.py](/home/grayg/socitwin/backend/app/memory/budget_recovery.py)
  - [runtime_failures.py](/home/grayg/socitwin/backend/app/memory/runtime_failures.py)
  - [prompt_assembler.py](/home/grayg/socitwin/backend/app/memory/prompt_assembler.py)
- 最小验证：
  - `VAL-BGT-01`
  - `VAL-BGT-02`
  - `VAL-RCL-05`
- 证据入口：
  - `assembly_failure_reason`
  - `budget_status`
  - `last_runtime_failure_category`
  - `last_runtime_failure_stage`

### `AUD-TST-01` 测试与调试指标是否足够可读

- 状态：`open`
- 风险：
  - 即使主链本身可用，如果 token、recall、observation shaping、short-term retention 等关键指标输出不稳定或难读，后续调试和汇报都会失真。
- 当前代码锚点：
  - [evaluation_harness.py](/home/grayg/socitwin/backend/app/memory/evaluation_harness.py)
  - [oasis_manager.py](/home/grayg/socitwin/backend/app/core/oasis_manager.py)
- 最小验证：
  - `VAL-MET-01`
- 证据入口：
  - `/api/sim/memory`
  - harness `summary.json`
  - harness `events.jsonl`

## 9. Current Policy

当前采取的策略仍然是：

- 先把风险显式化；
- 再逐步校正；
- 已修正的问题保留回归要求，不直接抹掉痕迹。

## 10. Related Docs

- 当前架构：
  - [current-architecture.md](./current-architecture.md)
- 场景目录：
  - [validation-scenarios.md](./validation-scenarios.md)
- 测试与 harness：
  - [testing-and-evaluation.md](./testing-and-evaluation.md)
