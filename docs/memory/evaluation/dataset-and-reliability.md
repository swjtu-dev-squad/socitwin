# Evaluation Dataset And Reliability

- Status: draft reliability plan
- Audience: implementers, evaluators, experiment/report authors
- Doc role: define how memory evaluation datasets are built, labeled, and made reliable under LLM/social-simulation uncertainty

## 1. Problem

长期记忆指标本身只回答“怎么评分”。

但对于 `socitwin`，更关键的问题是：

- 题目从哪里来；
- 正确答案怎么标；
- 大模型输出每次不一样时，结果怎么解释；
- 社交模拟路径不同导致 episode 不同，是否会让指标失去可比性。

如果这些问题不处理，`ltm_exact_hit_at_3`、MRR、injection rate 这些指标即使定义正确，也可能因为测试样本不稳定而难以解释。

因此评测体系必须把测试分成不同稳定性层级，而不是把所有东西都当成同一种 E2E 测试。

## 2. Core Design Principle

当前评测的目标不是替现有实现找一个最好看的分数，而是在贴合当前实现的前提下，把现有实现的问题拆出来。

每个测试设计都必须同时满足两类要求：

- 实现贴合性：测试使用的输入、query、候选、ground truth 和运行链路，必须能对应当前系统真实会产生的结构与行为。
- 缺陷暴露性：测试不能只验证 happy path，还要能暴露 episode 低质、query 过粗、候选偏置、embedding/rerank 混淆、agent filter 失效、prompt 注入被挡住等问题。

如果一个测试完全脱离当前实现，它很难解释当前系统；如果一个测试完全迁就当前实现，它又会掩盖当前系统的缺陷。A/B/C 三层评测都必须在这两者之间保持平衡。

## 3. Three Evaluation Levels

当前建议把长期记忆评测分成三个稳定性层级。

这里的 `A / B / C` 更准确地应理解为：

- `A-level deterministic benchmark`
- `B-level real-run replay benchmark`
- `C-level stochastic behavioral benchmark`

它们不是互斥类别，而是服务于不同稳定性和解释性需求的评测层。

### 3.1 Class A: Sanity And Deterministic Benchmark

这类测试用于在 B/C 级之前建立稳定底座。

当前 A 级包含两类能力，但不再单独拆成第四个层级：

- sanity / connectivity
  - preflight；
  - embedding / Chroma 可用性；
  - 最小真实 action_v1 step；
  - episode 写入和 debug trace 可读性。
- deterministic component checks
  - 不让主模型参与；
  - 使用人工构造或确定性构造的 payload、query 和 memory state；
  - 直接测试 memory 子系统。

适合覆盖：

- long-term write / payload normalization；
- embedding + rerank；
- exact episode hit；
- agent filter；
- recall gate；
- overlap suppression；
- recall / prompt budget stop reason。

这类测试的目标是：

- 每次运行结果稳定；
- 能进 CI 或轻量回归；
- 出错时能定位到具体模块。

它不回答“真实模拟里 agent 行为是否变好”，但它回答“记忆机制本身有没有稳定工作”。

当前实现状态：

- `preflight` 已覆盖依赖和 embedding preflight；
- `deterministic` 已覆盖 observation shaping 和一条 strong-signal recall trigger；
- `real-smoke` 已覆盖最小真实 action_v1 链路；
- 完整 controlled episode benchmark 还没有落地，暂时作为 future / optional，而不是当前主线阻塞项。

### 3.2 Class B: Real-Run Episode Replay

这类测试允许前面先跑一次真实 `action_v1` simulation，但评分不直接依赖“每次模拟产生完全一样的社交轨迹”。

流程是：

1. 真实运行 simulation。
2. 从 long-term store 中抽取已经产生的 `ActionEpisode`。
3. 以这些真实 episode 或真实 runtime query 为评测对象。
4. 回查当前 recall / retrieval 路径。
5. 统计 self-retrievability、runtime-query related retrieval、gate、injection 等指标。

它的稳定性来自：

- ground truth 来自本次真实运行实际写入的 episode；
- 评分目标是“已写入的历史能否被回查”，不是要求每次产生同一条历史。

这类测试最适合当前第一阶段主 KPI。

但需要特别强调：

- B 级不是开放世界随机 simulation 的一次性跑分；
- 更合理的定位是半受控的真实 replay benchmark；
- 它应使用真实主链，但尽量固定输入分布。
- 当前已实现的 `VAL-LTM-05` 属于 episode self-retrievability：query 从目标 `ActionEpisode` 自身字段反推，不等于真实 runtime recall。
- B 级下一步需要补 runtime-query replay：使用真实运行中的 `last_recall_query_text`，评估它是否能找回与当前 observation 相关的历史。

### 3.3 Class C: Stochastic Behavioral Scenario

这类测试真正关心 agent 后续行为是否更连续、更一致。

它必须接受大模型和社交模拟的不确定性。

适合覆盖：

- agent 是否记得自己曾经发过某内容；
- 后续行为是否延续历史关系；
- 是否避免自我记忆错乱；
- 是否避免目标对象错位；
- 是否因为 recall 注入而减少矛盾行为。

这类测试不能只跑一次就下结论。

更合理的做法是：

- 固定 topic、agent config、step count、memory mode；
- 尽量降低 temperature 或使用稳定模型配置；
- 同一场景跑多次；
- 报告均值、方差、最差值和失败样本；
- 把行为结果作为趋势证据，而不是第一阶段硬门槛。

## 4. Dataset Design

## 4.0 Current Fact vs Target Design

当前代码事实与目标设计需要分开理解。

当前 `evaluation_harness.py` 中的 `real-scenarios / real-longwindow`：

- 已支持固定 `scenario_pack`，也仍保留不传 pack 时的 template agent 调试入口；
- S1/S2 v0 pack 使用 fixture JSON 和 manual agents；
- 已有 agent count、step count、timeout、probe limit 等参数；
- 还没有 pack 级多次运行聚合；
- 还没有严格 usable probe validity gate；
- 还没有 runtime-query replay 指标。

因此：

- 当前代码里已经有 B-level v0 固定输入和 episode self-retrievability；
- run/pack/overall 聚合仍属于目标设计；
- runtime-query replay 是当前 B 级最关键缺口。

后续建议把 B 级拆成两步：

- `B-level v0`：固定输入、样本质量统计、episode self-retrievability；
- `B-level v0.5`：补 runtime-query replay；
- `B-level v1`：再考虑多次运行和 run/pack/overall 聚合。

## 4.1 Controlled Episode Dataset

controlled dataset 仍有价值，但当前不作为 B 级之前的主线阻塞项。

保留它的理由：

- 稳定比较 embedding / rerank 改动；
- 做 agent filter 回归；
- 构造 same-agent near-duplicate 和 cross-agent hard negatives；
- 在 CI 中提供小型防回归底座。

暂缓它的理由：

- 当前最急的问题来自真实运行中的 query 与 episode 写入不匹配；
- controlled fixture 容易变成理想化数据，不能暴露 observation summary query 的真实问题；
- 当前测试体系已经偏重，继续加大型 controlled benchmark 会增加维护成本。

因此第一阶段只保留设计，不要求立即实现。

建议规模：

- 20 到 50 个 `ActionEpisode`；
- 每个 episode 配 1 到 3 个 probe；
- 覆盖主要动作类型和风险边界。

建议覆盖：

- self post；
- comment；
- follow；
- group message；
- same-topic similar episodes；
- same-agent near-duplicate episodes；
- cross-agent similar topic episodes；
- invalid / non-persistable action boundary。

其中需要特别强调两类 hard negatives：

- same-agent near-duplicate episodes；
- cross-agent similar topic episodes。

前者更适合测试 retrieval ambiguity 与 rerank；后者更适合作为 agent filter guardrail。

每条样本至少需要标注：

```json
{
  "episode_key": ["agent-a", 7, 0],
  "expected_agent_id": "agent-a",
  "expected_step_id": 7,
  "expected_action_index": 0,
  "probe_text": "Ask about the earlier post on AI safety",
  "expected_hit": true,
  "negative_probe": false,
  "tags": ["self_post", "same_topic", "retrieval"]
}
```

注意：

- fixture 必须使用当前真实 `ActionEpisode` payload 结构；
- 不能引入当前系统没有的理想字段；
- probe 可以是人工写的，但命中判断必须基于 episode key。

## 4.2 Real-Run Episode Dataset

真实运行数据不应该要求每次生成同一批 episode。

更合适的方式是按运行结果动态建数据集：

1. 运行结束后从 Chroma collection 全量枚举已持久化的 `ActionEpisode` payload。
2. 过滤掉没有足够语义内容的 episode。
3. 为可用 episode 构造 episode-derived probe query，或收集真实 runtime query。
4. 对 episode-derived probe 使用 episode key 作为 ground truth。
5. 对 runtime query 使用 related episode set 作为更合理的 ground truth。
6. 记录样本数量和被过滤原因。

这类数据集每次可能不同，但指标仍然可解释，因为每次评分都针对本次实际产生的 episode。

当前需要区分两种 B 级问题：

- episode self-retrievability
  - 问：给这条 episode 自身线索，能不能查回自己；
  - 已由 `VAL-LTM-05` 覆盖；
  - ground truth 是 exact episode key。
- runtime-query related retrieval
  - 问：真实运行中当前 observation 产生的 query，能不能找回相关历史；
  - 当前尚未实现；
  - ground truth 不宜强制 single exact episode，应基于 query source post/topic/target 构造 related episode set。

必须记录：

- persisted episode count；
- usable probe count；
- skipped episode count；
- skipped reasons；
- action type distribution；
- agent distribution。

否则如果某次指标很低，很难判断是系统差，还是这次真实运行没有产生足够可测样本。

### 4.2.1 B-Level Input Control

B 级应尽量满足：

- observation 真实；
- `ActionEpisode` 写入实时发生；
- retrieval / gate / prompt assembly 走真实主链；
- 但输入分布固定设计，而不是完全开放随机。

第一阶段更稳妥的选择是：

- 固定 manual/file agent profiles；
- 固定 topic seed；
- 固定初始环境设置；
- 固定 step count；
- 固定 memory mode、embedding backend 和模型配置。

不建议第一阶段把开放随机 template agent generation 作为 B 级正式 benchmark 入口。

当前 `B-level v0` 已采用最小固定输入方案：

- 使用 fixture JSON 固化脱敏后的 scenario pack；
- 使用 `manual_config` 初始化固定 agents；
- 使用 seed post warm-up 启动环境；
- seed post 与 refresh 都不消耗正式 step budget；
- replay candidate 来自 Chroma 全量枚举，并会排除 warm-up 后已经存在的 persisted episode keys。

第一版 fixture 位于：

```text
backend/tests/memory/evaluation/fixtures/b_level_real_run_packs.json
```

其中：

- `s1_stable_single_topic` 用于稳定单话题 replay；
- `s2_similar_topic_interference` 用于相似话题干扰 replay。

需要注意：

- 固定 agents 和 seed 只能减少输入分布随机性，不能保证每次真实 LLM 运行产生完全相同的 episode；
- 因此每次仍必须报告 `persisted episode count`、`usable probe count`、`skipped reasons`；
- S1 和 S2 的解释口径不同，不能使用同一套简单阈值解释所有结果。

### 4.2.2 B-Level Scenario Packs

这里需要区分“已经有固定 pack”和“还没有完整 pack 平台”。

当前已经有第一版固定 pack：

- `s1_stable_single_topic`
- `s2_similar_topic_interference`

它们可以通过 `real-scenarios --scenario-pack ...` 运行，并且已经是 B-level v0 的正式固定输入来源。

当前还没有的是更完整的 pack 平台能力：

- pack 级多次运行；
- run / pack / overall 聚合；
- pack 间横向对比报告；
- 更严格的 validity gate；
- 更多场景类型。

推荐后续演进方向是继续保留并增强现有 S1/S2，再补 S3：

- `S1 stable single-topic pack`
  - 加强多 run 聚合和基础 exact hit / Hit@1 / MRR 报告；
- `S2 similar-topic interference pack`
  - 加强 runtime-query replay、same-agent hard negatives 和 cross-agent guardrail；
- `S3 group / multi-context pack`
  - group message、thread、local context continuity。

其中 `S2` 不能只做跨 agent 相似内容，还必须包含同 agent 的近似历史；否则只是在测 agent filter，而没有真正测 retrieval 歧义。

### 4.2.3 B-Level Validity Gate

B 级结果不能只报命中率，还必须加样本有效性门槛。

每次 run 至少应记录：

- persisted episode count；
- usable probe count；
- skipped episode count；
- skipped reasons；
- action type distribution；
- agent distribution。

如果 usable probe 数低于预设下限，该 run 应标记为：

- `blocked`
  或
- `invalid_for_reporting`

避免把“没有产生足够可测样本”误解释成“memory retrieval 差”。

## 4.3 Behavioral Scenario Dataset

行为级数据集应尽量使用固定场景模板。

每个场景至少定义：

- 初始 topic；
- agent profiles；
- 目标历史事件类型；
- 后续触发 observation 的条件；
- 期望行为；
- 反例行为；
- 判定方式。

示例：

```text
Scenario: self-authored continuity
Seed event: agent A writes a post supporting policy X.
Trigger: later observation shows related debate about policy X.
Expected behavior: agent A references or remains consistent with its earlier stance.
Failure examples: agent A treats its own earlier content as unfamiliar, contradicts it without context, or recalls another agent's stance as its own.
```

行为级评分可以先半自动：

- 结构化日志先筛出是否 recall 注入；
- 再人工或后续 LLM judge 判读行为是否合理。

第一阶段不建议把它放进硬门槛。

## 5. Ground Truth Rules

## 5.1 Retrieval Ground Truth

retrieval 层 ground truth 使用：

```text
(agent_id, step_id, action_index)
```

命中条件：

- top-k candidate 中存在完全相同 episode key。

不应使用：

- 主题相似；
- 文本相似；
- 同一个 target 但不是同一个 action；
- 同一个 agent 但不同 step 的近似行为。

这些可以作为诊断信息，但不能替代 exact hit。

## 5.2 Gate Ground Truth

gate 层 ground truth 分两类：

- positive probe：明确包含 topic / anchor / entity / self-authored 等 recall 信号；
- negative probe：空 observation、弱 observation、或与历史无关的 observation。

positive probe 的成功条件是 gate 打开。

negative probe 的成功条件是 gate 不打开，或不产生 retrieval。

## 5.3 Injection Ground Truth

第一阶段只做 trace 级注入：

- 有 recalled trace；
- 有 injected trace；
- 统计 recalled -> injected conversion。

这不能严格证明目标 episode 被注入。

严格 target-level injection 需要后续补：

- recalled candidate episode key；
- injected item episode key；
- prompt-visible recall note 中对应的 episode key。

## 5.4 Behavioral Ground Truth

行为级 ground truth 不应只写成“看起来合理”。

至少要定义：

- 期望行为集合；
- 明确失败行为集合；
- 不可判定条件；
- 是否需要人工复核。

行为级结果应报告：

- success rate；
- uncertain rate；
- contradiction rate；
- representative failures。

## 6. Randomness Control

## 6.1 What Can Be Fixed

应尽量固定：

- model config；
- temperature；
- agent config；
- topic；
- step count；
- memory mode；
- embedding backend；
- dataset fixture version。

如果主模型或 provider 不支持完全 deterministic seed，也要把配置记录进结果文件。

## 6.2 What Cannot Be Fully Fixed

即使固定配置，真实模拟仍可能变化：

- LLM 输出非确定；
- 社交平台状态随前序动作改变；
- 多 agent 交互会放大早期差异；
- observation 和 action chain 会发生路径偏移。

因此真实 E2E 行为结果不能按单次运行下结论。

## 6.3 Reporting Rule

对于 Class C 行为级测试，报告时应至少包含：

- run count；
- mean；
- min / max；
- standard deviation or variance；
- failed run examples；
- blocked / invalid run count。

对于 Class A 和 Class B，可以使用单次结果作为回归信号，但仍应记录样本数。

对于 B 级正式汇报，更推荐：

- 每个固定 pack 至少跑 3 次；
- 若波动明显，再补到 5 次；
- 第一阶段不建议直接上 10 次以上重跑。

并采用三层聚合：

- run-level
- pack-level
- overall B-level summary

## 7. Failure Attribution

当指标失败时，不应直接归因于“长期记忆差”。

建议按下面顺序排查：

1. 是否产生了足够 episode；
2. episode 是否被正确持久化；
3. query 是否能表达目标 episode；
4. gate 是否打开；
5. retrieval 是否命中；
6. agent filter 是否异常；
7. overlap suppression 是否过滤；
8. recall budget / prompt budget 是否阻断；
9. recall 是否注入；
10. 模型是否在行为上使用了注入记忆。

不同失败点对应不同修复方向。

## 8. First-Phase Recommendation

当前第一阶段建议采用：

- Class A 的 sanity / deterministic checks 作为连通性与确定性前置底座；
- Class B 的 fixed-input real-run replay 作为真实系统主 KPI 来源；
- Class C 的 behavioral scenario 暂时只作为观察和后续设计，不作为硬门槛。

更具体地说：

- 当前 `B-level v0` 已有 S1 / S2 固定输入 pack；
- `B-level v0` 的已实现重点是固定输入、样本质量统计、episode self-retrievability；
- 当前最关键缺口不是继续扩场景，而是补 runtime-query replay；
- 多次运行聚合和 controlled benchmark 都应作为后续增强。

第一阶段最小落地顺序：

1. 先完成 `summary.json` 的 `memory_kpis` 聚合。
2. 为 real-run replay 增加样本质量统计。
3. 固化 S1 / S2 fixed-input replay，并观察 usable probe 与 skipped reasons。
4. 补 runtime-query replay，使用真实运行中的 recall query 评估相关历史是否能被找回。
5. 再考虑是否需要 controlled benchmark 或多次运行的行为级 benchmark。

## 9. Open Questions

后续需要确认：

- controlled episode fixture 放在 `backend/tests/memory/evaluation/fixtures/` 是否合适；
- 第一版 controlled dataset 是手写 JSON，还是用 Python factory 生成；
- 行为级场景是否采用人工判读，还是后续接入 LLM-as-judge；
- 同一行为场景至少跑几次才足够汇报趋势。

## 10. External Benchmark References

外部 benchmark 更适合作为方法论来源，而不是直接照抄的数据集。

当前最有价值的借鉴点是：

- `LoCoMo / LongMemEval`
  - 提醒长期记忆应按能力维度拆分，而不是只做 fact lookup；
- `MemoryArena`
  - 强调记忆与后续行动耦合，提醒 B 级 exact hit 不是最终价值证明；
- `CRAG / BRIGHT / MIRAGE`
  - 提供 retrieval 难度设计、hard negatives、组件拆分的思路；
- `LongBench / RULER`
  - 提供后续长窗口和高压压力测试的思路。

不应直接照搬的部分是：

- 通用 QA-RAG 的数据集格式；
- 以 assistant 对话为中心的任务定义；
- 把 long-context benchmark 直接当作 long-term memory benchmark。
