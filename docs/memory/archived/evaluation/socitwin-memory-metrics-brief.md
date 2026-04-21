# Socitwin 长期记忆评测说明（面向当前实现与后续任务）

## 1. 文档目的

本文档用于帮助项目成员、Codex 和后续协作者快速理解：

1. `socitwin` 当前长期记忆架构的实现状态是什么；
2. 行业里 RAG / 检索增强系统常用哪些评测指标；
3. 这些指标映射到 `socitwin` 当前场景时分别代表什么；
4. 为什么当前主 KPI 更适合用 `@3` 而不是只用 `@1`；
5. 后续长期记忆评测应如何落地到现有 `evaluation_harness` 与文档体系中。

本文档不是通用 RAG 教程，而是**结合当前仓库代码事实**整理的说明。

---

## 2. 当前系统现状：`socitwin` 的长期记忆不是普通文档 RAG

### 2.1 当前运行模式

当前仓库运行态只保留两种 memory mode：

- `upstream`
- `action_v1`

其中：

- `upstream` 主要保留原始 OASIS 路线；
- `action_v1` 是当前项目自己的新记忆架构主线；
- 运行态没有独立 `baseline`。

### 2.2 当前长期记忆主单位

`action_v1` 的长期记忆主单位不是整段 chat history，也不是任意摘要文本，而是：

- `ActionEpisode`

它是围绕“动作事件”组织的结构化长期记忆单元，至少包含：

- `agent_id`
- `step_id`
- `action_index`
- `action_name`
- `action_category`
- `action_fact`
- `target_type`
- `target_id`
- `target_snapshot`
- `target_visible_in_prompt`
- `target_resolution_status`
- `execution_status`
- `local_context`
- `authored_content`
- `state_changes`
- `outcome`
- `topic`
- `query_source`
- `evidence_quality`
- `degraded_evidence`
- `action_significance`

因此，当前长期记忆评测的本质不是：

- “用户问题相关文档是否被召回”

而是：

- “某个应该被回忆到的历史行为事件 `ActionEpisode` 是否被正确检索回来”

### 2.3 当前长期记忆写入时机

长期记忆不是等 recent eviction 后才写入。
当前顺序是：

1. 当前 step 结束；
2. 构造 `StepSegment`；
3. 由 platform adapter 生成 `ActionEpisode`；
4. 过滤掉不应持久化的 episode；
5. 立即写入 long-term store；
6. 再由 consolidator 维护 short-term。

这意味着：

- long-term 与 short-term 已解耦；
- 长期记忆评测应单独考察“写入质量”；
- 不能把长期记忆问题与 recent eviction 混为一谈。

### 2.4 当前 recall 不是“检到就直接用”

当前 recall 至少分成三层：

1. **gate**：决定当前 observation 是否需要 recall；
2. **retrieval**：去长期层检索候选 episode；
3. **injection**：候选 episode 经过 overlap suppression 和 budget 裁决后，是否真正进入 prompt。

因此必须明确区分：

- 没有打开 gate；
- 打开 gate 但没检到；
- 检到了但没注入；
- 注入了但行为仍未改善。

这也是后续评测不能只看单一“召回率”的根本原因。

---

## 3. 行业里 RAG / 检索增强系统常用的评测指标

下面先用通俗方式解释常见指标，再考虑它们在 `socitwin` 中的具体含义。

### 3.1 Hit@K

含义：

> 正确答案是否出现在前 K 个结果中。

例如：

- `Hit@1`：正确结果必须排第 1；
- `Hit@3`：正确结果只要出现在前 3 个结果里即可。

优点：

- 好理解；
- 非常适合做 first-line KPI；
- 容易向导师或非检索背景成员解释。

局限：

- 只看“有没有进入前 K”；
- 不区分排第 1 和排第 3 的差别。

### 3.2 Recall@K

含义：

> 所有相关项中，有多少被前 K 个结果覆盖到了。

在很多实际任务里，如果每个 query 对应一个唯一正确目标，那么：

- `Recall@K`
- `Hit@K`

数值与含义会非常接近。

### 3.3 Precision@K

含义：

> 前 K 个结果中，有多少是真正相关的。

它更适合：

- 一个 query 对应多个相关结果；
- 需要关注前 K 列表整体“纯度”的任务。

### 3.4 MRR（Mean Reciprocal Rank）

含义：

> 正确答案平均排得有多靠前。

规则：

- 正确结果排第 1，得分 `1`；
- 排第 2，得分 `1/2`；
- 排第 3，得分 `1/3`；
- 没命中，得分 `0`。

最后对所有 query 取平均。

优点：

- 能补足 `Hit@K` 的不足；
- 不仅看“有没有检到”，还看“排得靠不靠前”；
- 很适合做排序质量辅助指标。

### 3.5 nDCG / MAP

这类指标更适合：

- 一个 query 对应多个相关项；
- 相关性还存在等级差异；
- 希望整体评估排序序列质量。

对于当前 `socitwin` 第一阶段长期记忆评测，它们不是最优先，因为当前更重要的是先验证：

- 关键目标记忆是否能被找回；
- 排序是否大体合理；
- 是否发生跨 agent 污染；
- recall 是否真正进入 prompt。

### 3.6 生成 / 使用层指标

RAG 还常看另一类指标：

- Faithfulness
- Groundedness
- Answer correctness
- Task success

这些更偏向“下游模型最终有没有用对检索结果”。

对 `socitwin` 来说，这类指标对应的是：

- 行为连续性；
- 自我行为记忆是否正确；
- 是否把别人的历史记忆当成自己的；
- recall 是否真正进入 prompt 并影响后续动作。

---

## 4. 这些指标映射到 `socitwin` 里分别代表什么

### 4.1 `Hit@K / Recall@K`

在 `socitwin` 当前场景里，它们应理解为：

> 当前 probe / observation 所需要的目标 `ActionEpisode`，是否出现在长期记忆检索结果的 top-K 中。

注意：

- 这里的检索对象不是文档，而是结构化动作事件；
- 这里的“正确目标”不是模糊相关文本，而是目标 episode key；
- 当前 harness 中的真实 probe 已经是按 `agent_id + step_id + action_index` 的 episode key 来做命中判断。

### 4.2 `MRR`

在 `socitwin` 里，`MRR` 代表：

> 正确历史行为事件平均排得有多靠前。

它能帮助回答：

- 系统是不是虽然能检回来，但总排在第 3；
- 排名第 1 的是不是经常被相似但不正确的 episode 占据；
- 当前排序能力是否足以支撑后续 prompt injection。

### 4.3 `Precision@K`

在当前阶段，`Precision@K` 不是主指标。

原因是：

- 当前任务更关注“关键目标记忆是否被检回”；
- 在社交模拟场景里，真正高价值的风险不是一般性噪声，而是**跨 agent 污染**。

因此在当前项目中，比 `Precision@K` 更有价值的替代项是：

- `Cross-Agent Contamination Rate`
- 或现有 harness 中的 `cross_agent_top3_count`

### 4.4 生成 / 使用层指标

在 `socitwin` 中，它们应被改写为：

- recall 是否被触发得正确；
- 检索结果是否真正被注入 prompt；
- recall 注入后，agent 是否体现出更合理的行为连续性；
- 是否避免了自我记忆错乱、目标对象错位和跨 agent 串忆。

---

## 5. `socitwin` 当前代码里已经实现了哪些相关指标

当前 `backend/app/memory/evaluation_harness.py` 中，真实 probe 已经实现了如下 retrieval 指标：

- `hit_at_1`
- `hit_at_3`
- `recall_at_3`
- `mrr`
- `cross_agent_top3_count`

其核心打分逻辑当前是：

- 用 `agent_id + step_id + action_index` 组成 episode key；
- 检查目标 key 是否出现在 top-1 / top-3；
- 记录第一命中 rank；
- 计算 reciprocal rank；
- 统计 top-3 内跨 agent 结果数量。

当前 `VAL-LTM-05 real_self_action_retrievability` 的通过条件是：

- `hit_at_3 >= 0.8`

而不是 `hit_at_1`。

此外，当前 harness 还实现了：

### 5.1 gate / retrieval probe

- `VAL-RCL-08 real_continuity_recall_probe`
  - 验证在有相关 observation 时，gate 是否打开，检索是否命中；
  - 这是 retrieve-only probe，不执行 prompt assemble。

- `VAL-RCL-09 real_empty_observation_recall_suppression`
  - 验证在空/弱 observation 下，gate 和 retrieval 是否被正确抑制；
  - 同样是 retrieve-only probe。

### 5.2 injection / long-window 指标

`real-longwindow` 当前会统计：

- `recall_gate_true_count`
- `recall_recalled_trace_count`
- `recall_recalled_not_injected_trace_count`
- `recall_injected_count`
- `recall_injected_trace_count`
- `recall_overlap_filtered_count`
- `recall_selection_stop_reason_counts`
- `used_recall_step_ids`

因此，当前仓库已经具备：

- 检索命中评测的基础；
- gate 层评测的基础；
- injection 层评测的基础；
- 行为级 trace 观察的基础。

缺的不是“从零开始做评测”，而是：

- 统一口径；
- 收敛出正式 KPI；
- 在文档和 summary 中把指标层级讲清楚。

---

## 6. 为什么当前主 KPI 更适合用 `@3` 而不是只用 `@1`

这是当前讨论里的核心问题。

### 6.1 结论

当前更合理的做法是：

- **主 KPI：`LTM Retrieval Recall@3` / `Hit@3`**
- **辅助 KPI：`Hit@1` + `MRR`**

而不是：

- 只用 `Hit@1`
- 或只用 `Hit@3`

### 6.2 为什么不用 `@1` 直接做主 KPI

`@1` 的要求是：

> 正确目标 episode 必须排第 1。

它确实更严格，但对当前工程阶段存在几个问题。

#### 原因 A：它与当前 recall 工作方式不完全匹配

当前系统不是只取 top-1 就结束，而是：

1. 先检索一个候选集合；
2. 再交给 prompt assembler 做 overlap suppression 和 budget 裁决；
3. 最终决定哪些 recall items 真正进入 prompt。

当前 recall preset 的默认 `retrieval_limit` 就是 `3`，真实 probe 里也按 `limit=3` 检索。

因此，对当前实现来说，真正更接近“系统可用候选集”的，是 top-3 而不是 top-1。

#### 原因 B：`@1` 对当前阶段过于苛刻，且较脆弱

你们当前检索对象是结构化历史行为事件。现实中经常会出现：

- 同 topic
- 同 target
- 同 agent
- 甚至非常相似的 authored content

在这种情况下，正确 episode 可能排第 2，而一个高度相似 episode 排第 1。

从 `@1` 看，这个 query 完全失败；
但从“长期记忆是否已被带回可用候选集”的角度看，它并不等于彻底失败。

#### 原因 C：当前更需要先验证“能不能找回来”，再进一步优化“是不是总排第一”

对于第一阶段长期记忆能力评估，最重要的问题通常是：

> 系统能否在需要回忆时，把正确历史事件带回候选集合。

这更接近 `@3` 的含义。

而“是否总排第一”更适合作为第二层优化目标。

### 6.3 为什么 `@3` 更适合做主 KPI

`@3` 更适合作为当前主 KPI，有三个原因。

#### 原因 A：与当前实现一致

当前代码里：

- retrieval limit 是 3；
- probe 已实现 `hit_at_3`；
- `VAL-LTM-05` 当前通过阈值就是 `hit_at_3 >= 0.8`。

因此 `@3` 不是空想出来的，而是已经与当前 harness 和 recall 候选规模保持一致。

#### 原因 B：更接近“候选可用性”而不是“极限排序能力”

对当前系统来说，检索不是终点，而是给后续 recall injection 提供候选池。

所以：

- `@1` 更像“排序尖锐度”；
- `@3` 更像“候选可用性”。

而当前第一阶段更优先验证的是后者。

#### 原因 C：更稳健，更适合做趋势跟踪

如果一开始就用 `@1` 做唯一主 KPI：

- 指标波动会更大；
- 容易被相近 episode 竞争影响；
- 容易让团队过早把重点放到 rerank 微调，而不是整体长期记忆链路稳定性。

`@3` 更适合作为第一版主指标来观察：

- 当前长期记忆整体是否具备“被找回”的能力；
- 新改动是否让系统退化或改进；
- 真实 long-term store 是否开始可用。

---

## 7. 那为什么仍然有必要同时保留 `@1`

只用 `@3` 也不够。

### 7.1 `@3` 的局限

`@3` 的问题在于：

- 排第 1 算对；
- 排第 2 算对；
- 排第 3 也算对。

这会掩盖排序质量差异。

换句话说：

- 一个系统总把正确记忆排第 1；
- 另一个系统总把正确记忆排第 3；

它们的 `Hit@3` 可能一样，但显然前者更好。

### 7.2 `@1` 的价值

因此，`@1` 很适合作为辅助指标，用来回答：

- 正确记忆是否经常已经是第一名；
- 当前排序是否足够尖锐；
- 后续是否值得专门做 rerank / query formulation 优化。

### 7.3 `MRR` 的价值

`MRR` 则是 `@1` 与 `@3` 之间的补充：

- 它既保留了位置信息；
- 又不会像 `@1` 那样过于极端地把第 2、第 3 全算失败。

因此当前更合理的组合是：

- **主 KPI：`Hit@3` / `Recall@3`**
- **辅助指标：`Hit@1` + `MRR`**

---

## 8. 与导师沟通时可以直接使用的解释口径

下面是建议统一的回答方式。

### 8.1 当被问“你们为什么不用单一召回率”时

建议回答：

> 我们的长期记忆评测不是单一召回率，因为当前系统的 recall 分成 gate、retrieval 和 injection 三层。仅看检索命中率，无法区分“没打开 recall”“检索失败”“检索成功但未注入 prompt”这几类不同问题。因此我们采用分层评测：检索层看目标 `ActionEpisode` 能否被召回，注入层看 recall 是否真正进入 prompt，行为层再看 recall 是否改善 agent 行为连续性。

### 8.2 当被问“为什么主 KPI 用 @3，不用 @1”时

建议回答：

> 当前系统默认检索 top-3 候选，后续 prompt assembly 也是基于候选集合进一步裁决，因此 `@3` 更能反映“长期记忆是否已被带回可用候选集”。相比之下，`@1` 更严格，更适合衡量排序尖锐度，而不是当前阶段的候选可用性。因此我们把 `@3` 作为主 KPI，同时保留 `@1` 和 `MRR` 作为辅助排序指标。

### 8.3 当被问“那为什么不只看 @3”时

建议回答：

> 只看 `@3` 会掩盖排序质量差异。正确记忆排第 1 和排第 3 的 `@3` 分数相同，但显然后者仍有优化空间。所以我们同时保留 `@1` 和 `MRR`。其中 `@1` 用于观察是否已经能把最该用的记忆排到第一，`MRR` 用于连续刻画平均排序位置。

### 8.4 当被问“你们和普通 RAG 评测有什么不同”时

建议回答：

> 普通 RAG 评的是文档块检索，我们当前评的是结构化行为事件 `ActionEpisode` 的检索。普通 RAG 的下游通常是回答问题，而我们的下游是 agent 行为决策。因此我们除了看命中率，还必须看跨 agent 污染、recall 是否被 gate 正确触发、是否真正注入 prompt，以及是否改善后续行为连续性。

---

## 9. 当前建议采用的正式指标体系

### 9.1 主 KPI

建议把当前主 KPI 明确命名为：

- `LTM Retrieval Recall@3`

或更贴近当前实现：

- `Target ActionEpisode Hit@3`

这两者在当前单目标 probe 场景下含义非常接近。

### 9.2 辅助指标

建议同时保留：

- `Hit@1`
- `MRR`
- `Cross-Agent Contamination Rate`
- `Recall Injection Success Rate`
- `Recall Gate Success Rate`
- `False Recall Trigger Rate`

### 9.3 各指标职责

- `@3`：回答“有没有把记忆找回来”
- `@1`：回答“是不是已经排第一”
- `MRR`：回答“平均排得有多靠前”
- `Cross-Agent`：回答“有没有串别人的记忆”
- `Injection Success`：回答“找回来后有没有真正被用上”
- `Gate Success / False Trigger`：回答“是否在正确时机触发 recall”

---

## 10. 当前与后续任务建议

### 10.1 当前已经可以做的事

基于现有代码，已经可以：

1. 把当前真实 probe 的 `hit_at_1 / hit_at_3 / recall_at_3 / mrr / cross_agent_top3_count` 提升为正式 summary 字段；
2. 把 `real-longwindow` 的 injection 指标加入统一 summary；
3. 在文档中正式固定：
   - 主 KPI 用 `@3`
   - `@1 + MRR` 作为辅助排序指标。

### 10.2 后续应继续补的内容

1. **统一 summary 输出结构**
   - 把 retrieval / gate / injection / behavior 四层指标收口到 `summary.json` 中。

2. **补行为级 benchmark**
   - 当前 retrieve-only probe 已有基础；
   - 下一步应增加“检索 -> 注入 -> 行为结果”的完整闭环场景。

3. **正式引入跨 agent 污染率**
   - 这项非常适合体现社交模拟长期记忆与通用 QA-RAG 的差异；
   - 应从附带统计提升为正式指标。

4. **进一步区分排序问题与候选召回问题**
   - 当 `@3` 高但 `@1` 低时，主要说明 rerank / query formulation 仍有优化空间；
   - 当 `@3` 也低时，更可能是长期记忆写入或检索主链本身存在问题。

---

## 11. 当前共识（供后续协作时默认采用）

当前团队在长期记忆评测上的共识应整理为：

1. `socitwin` 当前评测对象不是一般文档，而是结构化历史行为事件 `ActionEpisode`；
2. 当前 recall 评测必须分层看：gate、retrieval、injection、behavior；
3. 单一“召回率”不足以解释当前系统表现；
4. 当前主 KPI 更适合用 `@3`，因为它与当前 recall 候选规模和系统使用方式一致；
5. 仍然必须同时保留 `@1` 和 `MRR`，以避免 `@3` 掩盖排序质量差异；
6. 与普通 RAG 相比，`socitwin` 更应强调：
   - 跨 agent 污染
   - recall 注入有效性
   - 行为连续性

---

## 12. 参考代码与文档锚点（便于 Codex 继续跟进）

建议后续阅读顺序：

### 正式文档

- `docs/memory/current-architecture.md`
- `docs/memory/longterm-and-recall.md`
- `docs/memory/testing-and-evaluation.md`
- `docs/memory/validation-scenarios.md`
- `docs/memory/audit-and-validation.md`

### 核心实现

- `backend/app/memory/episodic_memory.py`
- `backend/app/memory/longterm.py`
- `backend/app/memory/recall_planner.py`
- `backend/app/memory/prompt_assembler.py`
- `backend/app/memory/working_memory.py`
- `backend/app/memory/evaluation_harness.py`
- `backend/app/memory/agent.py`
- `backend/app/core/oasis_manager.py`

### 测试锚点

- `backend/tests/memory/evaluation/test_memory_evaluation_harness.py`

---

## 13. 一句话总结

当前 `socitwin` 的长期记忆评测，不应被表述为“普通 RAG 召回率评测”，而应表述为：

> 面向结构化历史行为事件 `ActionEpisode` 的分层记忆评测。

在这一前提下，当前阶段最合理的指标组合是：

- **主 KPI：`Hit@3 / Recall@3`**
- **辅助排序指标：`Hit@1 + MRR`**
- **配套风险指标：`Cross-Agent Contamination`、`Injection Success`、`Gate Success`**

这套口径既符合行业里对检索质量的常见表达方式，也符合当前 `socitwin` 代码实现与后续优化目标。
