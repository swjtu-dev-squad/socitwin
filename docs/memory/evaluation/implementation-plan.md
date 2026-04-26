# Memory Evaluation Implementation Plan

- Status: Phase 1, B-level v0 fixed replay, and B-level v0.5 post-linked final lookup implemented
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
- `VAL-RCL-11`

第一阶段目标不是重写 harness，而是在现有事件基础上补 summary 级指标。该部分已完成。

当前实现状态应按下面理解：

- A-level sanity / deterministic
  - `preflight`、`deterministic`、`real-smoke` 已具备；
  - 完整 controlled episode benchmark 暂缓，不作为当前主线阻塞项。
- B-level v0
  - 固定 S1/S2 scenario pack、manual agents、seed warm-up、probe limit、审计材料已经具备；
  - `VAL-LTM-05` 当前是 episode self-retrievability。
- B-level v0.5
  - `VAL-RCL-11` 已按每个可见 post summary 生成 query；
  - 它评估 final-store post-linked memory lookup，不把 `post_id` 放入检索文本。
- B-level 缺口
  - 尚未实现完整 `last_recall_query_text` trace replay；
  - 尚未实现 author-based relationship recall 和 group recall；
  - 不能只用 `VAL-LTM-05` 代表真实 runtime recall 质量。
- C-level
  - 行为级场景尚未开始；
  - `real-longwindow` 当前只作为 trace-level injection 证据。

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

Status: implemented for Phase 1 KPI output; upgraded to Chinese human-readable report.

在 harness 的 `README.md` 输出中增加：

- KPI 摘要；
- 哪些 phase 没跑；
- 哪些指标不可用；
- retrieve-only 与 full-path 的口径说明。
- real-scenarios 样本覆盖、动作分布、按动作类型命中率和未命中样例。

目标是让人类和 AI 都能快速读懂测试结果。

当前 README 已输出：

- 中文运行概览和读法说明；
- 中文总览指标表；
- 中文不可用指标说明；
- real-scenarios 样本覆盖和 probe limit；
- Episode Self-Retrievability 的按动作类型 Hit@1 / Hit@3 / MRR / miss count；
- Post-Linked Final Lookup 的 post probe 覆盖、Hit@1 / Hit@3 / MRR、诊断分布和样例；
- 前若干条 top-3 未命中样例；
- exact episode hit 与传统 Recall@K 的差异说明
- trace-level injection 与目标 episode 注入成功的差异说明
- retrieve-only probe 与 full-path injection 的差异说明

当前 real-scenarios 还会在 run 目录下输出过程审计材料：

- `artifacts/real-scenarios/step_audit.jsonl`
  - 逐步记录 `step_result`、`memory_debug`、每个 agent 本步生成的 `ActionEpisode`。
- `artifacts/real-scenarios/episode_audit.jsonl`
  - 逐条记录 `ActionEpisode` payload、是否被持久化、评测 probe query、写入长期记忆时使用的 document 文本。
- `artifacts/real-scenarios/audit_summary.json`
  - 汇总 step 数、episode 数、动作分布、重复 probe query 情况和 LTM 指标。
- `artifacts/real-scenarios/sqlite_trace_summary.json`
  - 记录 OASIS `trace` 表摘要，并复制 `simulation.db` 方便后续人工排查。

这些审计材料的定位是先判断模拟过程和记忆形成是否正常，再解释抽象指标。

## 4. Phase 3: B-Level v0 Reliability Upgrade

Status: implemented for fixed-input self-retrievability; post-linked final lookup implemented; full query trace replay pending.

当前优先把 `real-scenarios / real-longwindow` 收口成可解释的 `B-level v0`。这一步不是完整 benchmark 平台，也不是行为级评测。

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
- `scenario_pack_id`
- `scenario_pack_purpose`
- `raw_real_probe_candidate_count`
- `warmup_excluded_probe_candidate_count`

当前已新增第一版固定输入入口：

- fixture: `backend/tests/memory/evaluation/fixtures/b_level_real_run_packs.json`
- CLI: `--scenario-pack`
- CLI: `--scenario-probe-limit`，默认 `0` 表示全量候选；正式评测默认不抽样，只有调试时才建议传入正数限制 probe 数量。
- agent source: fixture agents -> `manual_config`
- seed post: `ManualAction(CREATE_POST)` warm-up，`count_towards_budget=False`
- refresh: seed 后对全部 agent 执行 `REFRESH` warm-up，`count_towards_budget=False`
- replay candidate 来源：从 Chroma collection 全量枚举已存 `ActionEpisode` payload，再排除 warm-up 后已存在的 persisted episode keys，避免 seed 环境污染正式长期记忆检索 KPI。
- self-retrieval query：按动作类型和 `_episode_document()` 的实际字段构造，不再使用旧的通用字段顺序，也不把空置的 `summary_text` 当作优先 query 来源。

已内置两个 v0 packs：

- `s1_stable_single_topic`
  - 目标：稳定单话题，观察基础 Hit@1 / Hit@3 / MRR；
  - 解释口径：重点看是否稳定产生 persisted / usable probes，不应按强干扰场景解释。
- `s2_similar_topic_interference`
  - 目标：同主题、相似表达、不同 agent 的干扰；
  - 解释口径：重点看排序质量、MRR 和 cross-agent contamination，不应只用 S1 的简单通过/失败口径解释。

这一步的目标不是把 B 级做成完整 benchmark 平台，而是避免它继续停留在“随机 run 一次看看”。

当前必须明确：

- `VAL-LTM-05` 的 Hit@K / MRR 来自 episode-derived probe query；
- 它衡量 episode self-retrievability；
- 它不能单独代表真实 runtime query 下的召回质量。

### 4.1 2026-04-26 B-Level v0 18-Step Check

本轮使用固定 S1/S2 pack 跑了更长一点的 B-level v0 检查，用来验证样本覆盖和 episode self-retrievability 的当前状态。

有效结果目录：

- `backend/test-results/memory-eval/b-level-v0-s1-18step-timeout300-20260426`
- `backend/test-results/memory-eval/b-level-v0-s2-18step-20260426`

S1 初次 18-step run 触发 blocked，但 blocker reason 为空。结合运行方式判断主要风险是 `asyncio.wait_for(..., timeout=120)` 超时后 `TimeoutError` 字符串为空，说明当前超时诊断不够清晰。后续应把 timeout reason 显式写入报告，避免 blocked run 没有可读原因。

S1 valid rerun 结果：

- persisted episodes: 60
- raw candidates: 60
- usable probes: 60
- skipped probes: 0
- Hit@1: 0.7667
- Hit@3: 0.9667
- MRR: 0.8556
- cross-agent contamination: 0.0
- action distribution: `create_post=24`, `like_post=18`, `quote_post=14`, `follow=4`

S2 valid result：

- persisted episodes: 54
- raw candidates: 54
- usable probes: 54
- skipped probes: 0
- Hit@1: 0.8519
- Hit@3: 0.9444
- MRR: 0.8858
- cross-agent contamination: 0.0
- action distribution: `quote_post=23`, `create_post=23`, `like_post=8`

本轮结论：

- Chroma 全量枚举 candidate 的路线有效：两个有效 run 中 `persisted episode count == raw candidate count == usable probe count`，没有再出现旧版 bootstrap query 漏候选的问题。
- `create_post` 和 `quote_post` 的 episode self-retrievability 基本正常：两组 run 中这两类动作均为 Hit@1 / Hit@3 / MRR 全命中。
- `like_post` 仍是主要弱点：它自身 episode 语义稀薄，query 与目标 post / 同主题 quote 内容高度重叠，当前 rerank 容易把同一 agent 的 richer `quote_post` 排在 `like_post` 前面。
- 当前失败主要不是 cross-agent contamination：两个有效 run 的 contamination 都是 0，说明 agent filter 在本轮样本中没有暴露问题。
- `VAL-RCL-08/09` 仍只是 retrieve-only gate / recall sanity，不能替代真实 runtime query 下的相关召回评估。

仍未完成：

- 更严格的 usable probe validity gate；
- 多 run 汇总。
- 更完整的 runtime-query trace replay。

## 5. Phase 4: Post-Linked Final Lookup

Status: implemented as `VAL-RCL-11 post_linked_final_lookup`.

这是当前 B 级 v0.5 的主线补充，用来弥补 `VAL-LTM-05` 只做 episode self-retrievability 的问题。

目标：

- 使用真实运行中每个 agent 的 prompt-visible observation snapshot；
- 对 snapshot 中每个可见 post 各生成一条 query；
- 检索文本只使用该 post 的 `summary`，不把 `post_id` 放入 query；
- `post_id`、`source_author_id` 只用于 ground truth 和调试；
- 判断整场模拟结束后，能否用某个 agent 曾经看见过的帖子 summary，从该 agent 的最终长期记忆中找回与该帖子结构相关的动作事件。

为什么需要它：

- `VAL-LTM-05` 的 query 从目标 episode 自身字段反推；
- 两者不是同一个问题；
- 如果直接从数据库全量帖子出题，会混入 agent 从未见过、不应作为 recall 触发来源的帖子；
- post-linked lookup 通过真实 observation 中每个可见 post 的 `summary` 出题，再用结构化 `post_id` 关系定义正确答案，能在不向检索文本塞 id 的前提下得到更清晰的 ground truth。
- 该事件不复现某一步 runtime recall，不使用 `last_recall_query_text`，也不按 step 做时间过滤。

当前实现：

- `step_audit.jsonl` 已补充每个 agent 的 `prompt_visible_snapshot`；
- `VAL-RCL-11 post_linked_final_lookup` 从 official step 中提取每个可见 post；
- 对每个 post 用 `post.summary` 调用当前 Chroma 检索链路；
- 检索仍走 `longterm_store.retrieve_relevant(query_text, limit=3, agent_id=current_agent_id)`；
- agent filter、embedding、rerank 都沿用当前真实实现。

硬正确答案：

- same agent；
- `episode.target_type == "post"` 且 `episode.target_id == source_post_id`；
- 或 `episode.local_context.parent_post.post_id == source_post_id`；
- 或当前可见帖子作者就是 agent 自己，且 episode 是 `create_post` 并包含 `created_post:{source_post_id}`。

第一版纳入硬指标的动作主要是 post-linked actions：

- `like_post` / `unlike_post`
- `dislike_post` / `undo_dislike_post`
- `report_post`
- `repost`
- `quote_post`
- `create_comment` on a visible parent post
- self-authored `create_post` re-hit

暂不纳入硬正确答案：

- `follow` / `unfollow` / `mute` / `unmute`；
- group actions；
- 只有主题相似但没有 post 结构关系的 episode。

原因是当前 query 只有帖子正文，不包含稳定 user-oriented 问题。用帖子正文要求系统找回“我关注过这个作者”或“我 mute 过这个作者”不够公平；这类关系记忆后续应单独设计 author-based recall 测试。

当前输出：

- `post_probe_count`
- `post_probe_with_ground_truth_count`
- `post_probe_without_ground_truth_count`
- `hit_at_1`
- `hit_at_3`
- `mrr`
- `self_authored_post_hit_at_3`
- `diagnosis_counts`
- `ground_truth_action_distribution`

解释口径：

- `post_probe_without_ground_truth_count` 不算 miss，它表示该 agent 的最终长期记忆中没有与当前可见帖子结构相关的可测答案；
- `same_agent_wrong_target` 说明检索到了同 agent 的历史，但不是当前 source post 的正确 episode；
- cross-agent 命中应继续接近 0，否则优先排查 agent filter。

仍未完成：

- 更完整的 runtime-query trace replay：直接读取 `last_recall_query_text`、gate、selected/injected 和 budget trace；
- author-based relationship recall；
- group-based recall；
- 多 run 聚合。

## 6. Optional: Controlled Benchmark

controlled benchmark 暂时不作为当前主线阻塞项，但保留为后续可选组件。

适合在下面情况启动：

- 准备调整 embedding / rerank，需要稳定对比；
- B 级显示问题集中在 retrieval/rerank，但真实运行噪声太大；
- 需要 CI 中固定防回归；
- 老师明确要求一个离线、可复现的召回率 benchmark。

候选 fixture：

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

## 7. Phase 5: B-Level v1 Scenario Packs

在 `B-level v0`、post-linked final lookup 和必要的 controlled benchmark 稳定之后，再补更完整固定 scenario packs：

- `S1 stable single-topic pack`
- `S2 similar-topic interference pack`
- `S3 group / multi-context pack`

这一阶段再考虑：

- run-level / pack-level / overall 三层聚合；
- pack 级多次运行；
- 正式 benchmark 结果汇总。

## 8. Phase 6: Behavioral Scenarios

行为级 benchmark 放到第二阶段之后。

前置条件：

- retrieval KPI 已稳定；
- injection 指标已可读；
- post-linked final lookup / 完整 query trace replay 已能解释真实查询质量；
- 已有足够真实运行日志用于设计判定规则。

行为级场景必须按随机实验处理。不能只跑一次就把结果解释成长期记忆能力结论；至少应记录 run count、均值、波动和失败样本。

## 9. Acceptance Criteria For Phase 1

Phase 1 完成时应满足：

- 在 `backend/` 目录执行 `uv run pytest tests/memory/evaluation/test_memory_evaluation_harness.py` 通过；
- 默认 summary 中存在 `memory_kpis`；
- 未运行 phase 的指标不会被错误写成 `0`；
- README 报告能解释指标含义；
- 文档与实际字段名一致。

已验证：

- 在 `backend/` 目录执行 `uv run pytest tests/memory/evaluation/test_memory_evaluation_harness.py`
- 在 `backend/` 目录执行 `uv run pyright app/`
- 在 `backend/` 目录执行 `uv run ruff check app tests/memory/evaluation/test_memory_evaluation_harness.py --ignore=E501`

B-level v0 已补充：

- real-run replay 的 `usable probe count`
- `skipped episode count`
- `skipped reasons`
- action / agent distribution

仍缺完整 query trace replay、author/group recall 和更严格的 usable probe validity gate。

## 10. Open Decisions

需要后续确认：

- controlled benchmark 是否仍有必要进入 CI，还是只作为后续手动评测入口；
- 行为级 benchmark 是否需要人工判读或 LLM-as-judge。
- 同一行为级场景至少跑几次才适合用于趋势汇报。
- 完整 `last_recall_query_text` trace replay 的 related episode set 第一版如何标注。

已确认：

- 内部字段使用 `ltm_exact_hit_at_3`；
- 文档展示名使用 `Episode Self-Retrievability Recall@3 (Exact Episode Hit@3)`；
- `@1` 作为正式辅助 KPI；
- `cross_agent_contamination_rate` 使用实际返回 top-k slot 作为分母；
- phase 未运行或样本不足时，summary 字段使用 `null` 并写入不可用原因。
- `B-level v0` 使用 fixture JSON + `manual_config` 作为固定 agent source。
- `VAL-LTM-05` 当前解释为 episode self-retrievability。
