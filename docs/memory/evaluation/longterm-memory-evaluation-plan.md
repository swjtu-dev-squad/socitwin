# Long-Term Memory Evaluation Plan

- Status: draft implementation plan
- Audience: implementers, evaluators, experiment/report authors
- Doc role: define the evaluation target, layers, first-phase scope, and reporting position for `action_v1`

## 1. Goal

长期记忆评测不能只回答“有没有召回”，而要拆开回答五个问题：

1. 写入层：应该进入长期层的 `ActionEpisode` 有没有被正确持久化。
2. 检索层：需要回忆时，目标历史事件能否被检到。
3. 门控层：系统是否在正确时机触发 recall，而不是乱查或漏查。
4. 注入层：检到的长期记忆是否真的进入 prompt。
5. 行为层：进入 prompt 的长期记忆是否改善行为连续性和社交一致性。

第一阶段重点不是直接证明行为完全变好，而是先建立可解释、可复测的工程指标。

## 2. Ground Truth And Query Scope

当前长期记忆的最小评测单位是一个具体历史动作事件：

```text
(agent_id, step_id, action_index)
```

因此第一阶段主指标应优先采用 exact episode hit，而不是宽泛的“语义相关”。

这样做的原因是：

- 可以准确判断是否检到了目标 `ActionEpisode`；
- 可以发现同主题但非目标事件的混淆；
- 可以验证按 agent 过滤后的检索边界是否仍然可靠。

但当前实现已经暴露出一个关键边界：不同测试口径的 query 来源不同。

- `VAL-LTM-05 real_self_action_retrievability`
  - query 从目标 `ActionEpisode` 自身字段反推；
  - 主要回答“这条已经写入的 episode 在给定自身线索时能不能被查回”；
  - 应解释为 `episode self-retrievability`。
- runtime recall
  - query 来自当前 observation 的 `topic / semantic_anchors / entities / recent_episodes`；
  - 当前实现中最常见的是第一条可见 post/group 的 `summary`；
  - 主要回答“真实运行中当前看到的内容能不能唤起相关历史”。

因此 exact episode hit 仍有价值，但不能单独代表完整 runtime recall 质量。B 级后续需要补 runtime-query replay，把真实 `last_recall_query_text` 和相关历史集合一起评估。

## 3. Evaluation Layers

### 3.1 Retrieval Benchmark

目标：验证正确历史事件能否被检到。

推荐先复用：

- `real-scenarios`
- `VAL-LTM-05`
- `VAL-RCL-08`

核心输出：

- exact episode Hit@3 / Recall@3 口径；
- exact episode Hit@1；
- MRR；
- cross-agent contamination guardrail。

注意：

- `real-scenarios` 中的部分 probe 是 retrieve-only，不执行 prompt assembly。
- retrieve-only 命中不能汇报成“模型实际用上了记忆”。
- 当前 `VAL-LTM-05` 是 self-retrievability，不等于 runtime recall。
- B 级缺口是 runtime-query replay：使用真实运行中的 recall query，评估是否找回与当前 observation 相关的历史 episode。

### 3.2 Gate And Injection Benchmark

目标：验证该不该查、查到了有没有真的进入 prompt。

推荐先复用：

- `VAL-RCL-09`
- `VAL-RCL-10`
- prompt assembler 的 overlap / budget debug 字段。

核心输出：

- gate success；
- false trigger；
- recalled -> injected conversion；
- overlap / budget stop reason。

注意：

- 当前可直接拿到 trace 级 injection 统计。
- 严格的 target episode injection success 仍需要补更细的事件关联。

### 3.3 Behavioral Benchmark

目标：验证长期记忆是否改善最终行为。

这一层最接近最终价值，但第一阶段不建议作为硬门槛。

原因：

- 受主模型随机性影响大；
- 受平台 observation 噪声影响大；
- 单看结果难定位问题到底出在 episode、embedding、rerank、gate、budget 还是模型行为。

行为级 benchmark 应作为第二阶段增强。

## 4. First-Phase KPI Set

第一阶段建议正式汇报下面这组核心指标：

- `Episode Self-Retrievability Hit@3`
- `Episode Self-Retrievability Hit@1`
- `Episode Self-Retrievability MRR`
- `Cross-Agent Contamination Rate`
- `Recall Injection Trace Rate`

这些指标分别回答：

- 给目标 episode 自身线索时，能否查回目标历史；
- 目标 episode 是否已经排第一；
- self-retrievability 的平均排序位置是否足够靠前；
- agent 过滤是否仍然可靠；
- 长期记忆有没有进入 prompt。

如果需要对外使用“召回率”这个词，建议写成：

```text
Episode Self-Retrievability Recall@3 (Exact Episode Hit@3)
```

并明确说明它是单目标 episode top-3 命中率，不是传统多相关文档 Recall@K。

`@3` 作为当前可用 KPI 的原因是：当前 recall 默认检索 top-3 候选，后续 prompt assembly 也是基于候选集合继续做 overlap 和 budget 裁决；因此 `@3` 更接近“目标历史是否进入可用候选集”。`@1` 更严格，适合衡量排序尖锐度，所以作为正式辅助 KPI 保留。

该 KPI 的限制必须同时汇报：

- 它来自 episode-derived probe query；
- 它不代表真实 runtime query 下的相关召回率；
- runtime-query related retrieval 是 B 级下一步待补指标。

## 5. First-Phase Non-Goals

第一阶段不建议做：

- 不可解释的单一总分；
- 大规模人工行为判读；
- 把 `recalled_count` 直接当长期记忆能力；
- 把当前检索路径描述成纯 embedding 召回；
- 为了追求漂亮指标而绕过 `RecallPlanner` gate。

## 6. Reporting Position

推荐汇报口径：

- 当前 `socitwin` 的长期记忆以 `ActionEpisode` 为结构化持久化单元。
- recall 主链被拆成 gate、retrieval、injection 三个可观测阶段。
- 当前已实现的 B 级核心指标是 `Episode Self-Retrievability Recall@3 (Exact Episode Hit@3)`、Hit@1、MRR、agent 过滤回归防线和 injection trace rate。
- runtime query 主要来自当前 observation summary，相关召回质量仍需要 runtime-query replay 补测。
- 行为级连续性测试会作为第二阶段增强，不直接替代检索和注入指标。

避免汇报口径：

- “召回率高，所以 agent 行为已经稳定。”
- “embedding 命中率高，所以长期记忆系统没有问题。”
- “recalled_count 增加，所以模型真实使用了长期记忆。”
