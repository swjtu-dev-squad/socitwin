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

## 2. Three Evaluation Classes

当前建议把长期记忆评测分成三类。

### 2.1 Class A: Deterministic Component Benchmark

这类测试不让主模型参与。

它使用人工构造的 `ActionEpisode` 和 probe query，直接测试 memory 子系统。

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

### 2.2 Class B: Real-Run Episode Replay

这类测试允许前面先跑一次真实 `action_v1` simulation，但评分不直接依赖“每次模拟产生完全一样的社交轨迹”。

流程是：

1. 真实运行 simulation。
2. 从 long-term store 中抽取已经产生的 `ActionEpisode`。
3. 以这些真实 episode 为 ground truth，自动构造 probe query / probe snapshot。
4. 回查当前 recall / retrieval 路径。
5. 统计 exact hit、MRR、gate、injection 等指标。

它的稳定性来自：

- ground truth 来自本次真实运行实际写入的 episode；
- 评分目标是“已写入的历史能否被回查”，不是要求每次产生同一条历史。

这类测试最适合当前第一阶段主 KPI。

### 2.3 Class C: Stochastic Behavioral Scenario

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

## 3. Dataset Design

## 3.1 Controlled Episode Dataset

第一阶段应补一套小型 controlled dataset。

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

## 3.2 Real-Run Episode Dataset

真实运行数据不应该要求每次生成同一批 episode。

更合适的方式是按运行结果动态建数据集：

1. 运行结束后扫描 persisted `ActionEpisode`。
2. 过滤掉没有足够语义内容的 episode。
3. 为可用 episode 构造 query。
4. 用 episode key 作为 ground truth。
5. 记录样本数量和被过滤原因。

这类数据集每次可能不同，但指标仍然可解释，因为每次评分都针对本次实际产生的 episode。

必须记录：

- persisted episode count；
- usable probe count；
- skipped episode count；
- skipped reasons；
- action type distribution；
- agent distribution。

否则如果某次指标很低，很难判断是系统差，还是这次真实运行没有产生足够可测样本。

## 3.3 Behavioral Scenario Dataset

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

## 4. Ground Truth Rules

## 4.1 Retrieval Ground Truth

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

## 4.2 Gate Ground Truth

gate 层 ground truth 分两类：

- positive probe：明确包含 topic / anchor / entity / self-authored 等 recall 信号；
- negative probe：空 observation、弱 observation、或与历史无关的 observation。

positive probe 的成功条件是 gate 打开。

negative probe 的成功条件是 gate 不打开，或不产生 retrieval。

## 4.3 Injection Ground Truth

第一阶段只做 trace 级注入：

- 有 recalled trace；
- 有 injected trace；
- 统计 recalled -> injected conversion。

这不能严格证明目标 episode 被注入。

严格 target-level injection 需要后续补：

- recalled candidate episode key；
- injected item episode key；
- prompt-visible recall note 中对应的 episode key。

## 4.4 Behavioral Ground Truth

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

## 5. Randomness Control

## 5.1 What Can Be Fixed

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

## 5.2 What Cannot Be Fully Fixed

即使固定配置，真实模拟仍可能变化：

- LLM 输出非确定；
- 社交平台状态随前序动作改变；
- 多 agent 交互会放大早期差异；
- observation 和 action chain 会发生路径偏移。

因此真实 E2E 行为结果不能按单次运行下结论。

## 5.3 Reporting Rule

对于 Class C 行为级测试，报告时应至少包含：

- run count；
- mean；
- min / max；
- standard deviation or variance；
- failed run examples；
- blocked / invalid run count。

对于 Class A 和 Class B，可以使用单次结果作为回归信号，但仍应记录样本数。

## 6. Failure Attribution

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

## 7. First-Phase Recommendation

当前第一阶段建议采用：

- Class A 的 controlled episode benchmark 作为稳定回归底座；
- Class B 的 real-run episode replay 作为真实系统主 KPI 来源；
- Class C 的 behavioral scenario 暂时只作为观察和后续设计，不作为硬门槛。

第一阶段最小落地顺序：

1. 先完成 `summary.json` 的 `memory_kpis` 聚合。
2. 为 real-run replay 增加样本质量统计。
3. 增加 controlled episode dataset 的设计和 fixture。
4. 再考虑是否把 controlled benchmark 接入 CI。
5. 最后再设计多次运行的行为级 benchmark。

## 8. Open Questions

后续需要确认：

- controlled episode fixture 放在 `backend/tests/memory/evaluation/fixtures/` 是否合适；
- 第一版 controlled dataset 是手写 JSON，还是用 Python factory 生成；
- 行为级场景是否采用人工判读，还是后续接入 LLM-as-judge；
- 同一行为场景至少跑几次才足够汇报趋势。
