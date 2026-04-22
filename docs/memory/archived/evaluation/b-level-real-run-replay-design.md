# B-Level Real-Run Replay Design Notes

- Status: draft working note
- Audience: implementers, evaluators, experiment/report authors, Codex collaborators
- Doc role: consolidate current discussion around the B-level evaluation design problem, clarify its goal and boundary, and propose a pragmatic first-phase design

## 1. Naming Clarification

这里的 `Class A / B / C` 更准确地应理解为**评测层级**或**稳定性层级**，而不是互斥的“类别”。

原因是：

- A 级强调确定性与可回归；
- B 级强调真实运行主链上的 episode replay；
- C 级强调高随机性的行为效果观察；
- 三者服务于不同稳定性和解释性需求，可以并行存在，不是三选一。

因此后续文档里更推荐写成：

- `A-level deterministic benchmark`
- `B-level real-run replay benchmark`
- `C-level stochastic behavioral benchmark`

## 2. Problem Restatement

当前 B 级评测的基本思路是：

1. 先运行一段真实的 `action_v1` simulation；
2. 从本次运行的 long-term store 中取出真实 `ActionEpisode`；
3. 用这些真实 episode 构造 probe；
4. 回查当前 retrieval / gate / injection 主链；
5. 统计 exact hit、MRR、gate、injection 等指标。

这个方向本身没有问题，它也是当前最适合作为第一阶段真实系统主 KPI 来源的层级。

但真正困难的地方不在“怎么算分”，而在：

- 这段 simulation 的**启动场景怎么定**；
- 运行轨迹存在模型随机性时，**结果怎么解释**；
- 如何避免 B 级测试退化成“测某一次 run 的运气”；
- 如何在工作量有限的情况下，做到尽量稳妥、客观、可复测。

## 3. B-Level Is Not Open-World E2E

B 级测试最容易被误解成：

> 随便开一个真实 simulation，跑完之后看看记忆指标是多少。

这个理解过于宽松，也会让 benchmark 失去可比性。

更准确的定位应该是：

> **B 级是半受控的真实运行 replay benchmark。**

也就是说：

- 它使用真实模型、真实 observation、真实 `ActionEpisode` 写入、真实 recall 主链；
- 但它不应当使用完全开放的、无控制的随机 simulation 作为输入分布来源；
- 它的目标不是证明“系统在所有社交模拟中都表现一致”，而是证明：
  - 在一组固定设计的、能稳定产生关键记忆风险的真实运行场景中，
  - 系统写入的历史事件能否被后续 recall 主链稳定回查。

这个定位非常关键。它能把 B 级和：

- A 级的纯确定性 fixture benchmark 区分开；
- C 级的高随机行为结果观察区分开。

## 4. What B-Level Should Actually Measure

B 级测试不应该承担“所有长期记忆价值”的证明任务。

更适合它的，是下面三类问题：

### 4.1 写入后可回查性

给定本次真实运行里已经持久化的 `ActionEpisode`，后续 probe 是否能把目标 episode 检回来。

这是 B 级最核心的检索层目标。

### 4.2 真实主链上的 gate / retrieval / injection

B 级测试不只看纯检索，还要看：

- 正信号 observation 下 recall gate 是否打开；
- 空/弱 observation 下 gate 是否被抑制；
- recalled candidate 是否在真实 prompt assembly 中被注入；
- overlap 和 budget 是否阻断。

### 4.3 真实运行中的 agent filter guardrail

在社交模拟里，一个非常重要的问题是：

- 会不会把别的 agent 的记忆召回成自己的记忆。

因此 B 级必须把 cross-agent contamination 视为核心 guardrail，而不是附带统计。

## 5. What B-Level Should NOT Try To Prove In Phase 1

第一阶段的 B 级测试，不应该试图直接证明：

- agent 长期行为已经“稳定”；
- 所有场景下都能维持一致的人设；
- recall 注入一定改善最终行为；
- 在开放世界模拟里具备普适、统一、成熟的 benchmark 结论。

这些更适合放到 C 级去逐步观察。

如果 B 级一上来就承担这些目标，结果会非常难解释，也会直接放大随机性问题。

## 6. The Core Design Tension

B 级测试面临两个天然张力：

### 6.1 稳定 vs 真实

- 如果场景太开放，episode 分布不可控，结果容易像抽样噪声；
- 如果场景太人工，虽然稳定，但又失去真实系统 replay 的意义。

### 6.2 多样 vs 可维护

- 如果只测一个很保守的固定场景，无法覆盖不同记忆风险；
- 如果设计大量复杂场景，工作量、运行成本和结果波动都会迅速上升。

因此 B 级最合理的路线不是“一个场景解决所有问题”，也不是“追求类似 3DMark 那样大而全的测试矩阵”，而是：

> 用少量固定场景包，覆盖不同的**记忆风险维度**。

## 7. Diversity Should Be Defined By Memory Risk, Not Topic Variety

B 级测试里的“多样性”不应泛泛理解成：

- 换更多 topic；
- 换更多随机 agent；
- 换更多题材。

对长期记忆系统来说，更有意义的多样性是**记忆风险覆盖**。

建议把多样性定义成下面几类维度：

### 7.1 Action Type Coverage

至少覆盖：

- `create_post`
- `create_comment`
- `follow` / relation action
- `send_to_group` / group message

因为这些动作在 `ActionEpisode` 中的 target、local context、probe 线索和后续 recall 方式不同。

### 7.2 Retrieval Ambiguity Coverage

至少覆盖：

- 唯一、清晰的 episode；
- 同 agent 的近似 episode；
- 不同 agent 但同 topic 的近似 episode。

这一维直接决定：

- exact episode hit 是否有意义；
- rerank 是否能分辨近似历史；
- agent filter 是否可靠。

### 7.3 Trigger Coverage

至少覆盖：

- topic trigger；
- anchor / entity trigger；
- self-authored trigger；
- negative probe（不应触发 recall）。

### 7.4 Memory Pressure Coverage

至少覆盖：

- 低压力短 run；
- 中等压力、有一定历史积累的 run。

第一阶段不建议追求极端长窗口或高压极限，但也不应永远只测最容易的轻负载情况。

### 7.5 Social Topology Coverage

至少覆盖：

- 自己发帖后回查；
- 评论链上下文；
- 群组 / 群消息上下文。

## 8. Recommended First-Phase Scenario Packs

第一阶段建议不要用“一个固定启动场景”，而是做 **3 个固定 scenario packs**。

### 8.1 Pack S1: Stable Single-Topic Pack

目标：最基础、最稳的 replay benchmark。

建议特征：

- 固定 agent profiles；
- 固定单 topic；
- 低 temperature 或尽量稳定的模型配置；
- 2 到 3 个 agent；
- 8 到 12 steps；
- 重点产生 `self post`、`comment` 等常见 episode。

主要作用：

- 作为最基础的 B 级 regression pack；
- 观察 exact hit / Hit@1 / Hit@3 / MRR；
- 观察 usable probe 数量是否稳定。

### 8.2 Pack S2: Similar-Topic Interference Pack

目标：专门检验 retrieval ambiguity 与 cross-agent contamination。

建议特征：

- 多个 agent 对同一 topic 发表相似但不完全相同的内容；
- 存在同 topic、不同 step、不同 agent 的近似 episode；
- 仍然使用固定场景模板，不引入开放式随机 agent 生成。

主要作用：

- 检验 exact episode hit；
- 检验近似但非目标历史是否被错误排前；
- 检验 `agent_id` 过滤是否发生回归。

### 8.3 Pack S3: Group / Multi-Context Pack

目标：检验 group message、thread context、local context continuity。

建议特征：

- 固定 group 相关触发；
- 有 group message、comment thread、relation action 的混合 episode；
- run 稍长，但仍控制在中等长度。

主要作用：

- 检验 group / message episode 回查；
- 检验 target continuity；
- 检验 local context 是否为 probe 和 recall 提供有效线索。

## 9. Startup Configuration Principles

### 9.1 Do Not Use Open Random Agent Generation

B 级 benchmark 不建议使用开放式 template 随机生成人设作为主要入口。

原因：

- 它会把额外随机性引入 episode 分布；
- 使 run 间差异更多反映 agent generator 的波动，而不是 memory 主链的质量；
- 让失败分析变得更困难。

更稳妥的方式是：

- 使用固定 manual/file agent profiles；
- 使用固定 topic seed；
- 使用固定初始环境设置；
- 使用固定 step count；
- 使用固定 memory mode、embedding backend、模型配置。

### 9.2 Use Real Main Path, But Fixed Inputs

B 级场景应满足：

- observation 是真实的；
- `ActionEpisode` 写入是实时发生的；
- retrieval / gate / prompt assembly 走真实主链；
- 但场景输入分布（agent、topic、初始环境）是固定设计的。

## 10. How To Handle Randomness

### 10.1 B-Level Should Not Require Identical Social Trajectories

B 级测试不应要求：

- 每次都生成同一批 episode；
- 每个 agent 都做完全相同的动作；
- 社交轨迹逐步逐帧一致。

如果用这个标准，B 级测试几乎必然失败。

### 10.2 What B-Level Should Require Instead

B 级测试更合理的要求是：

- 在同一固定 scenario pack 下，
- 能持续产生**足够数量的可测 episode**，
- 并且相关 retrieval / gate / injection 指标在统计上可解释。

也就是说：

- 允许 run 之间 episode 内容和分布有波动；
- 但不允许 benchmark 完全退化成不可解释的抽样噪声。

### 10.3 Recommended Run Policy

#### 开发 / PR 回归

- 每个 pack 跑 1 次；
- 主要用于看有没有明显回归；
- 不作为正式汇报结论。

#### 正式 benchmark / 汇报

- 每个 pack 跑 3 次起步；
- 如波动明显，再补到 5 次；
- 暂不建议第一阶段直接跑 10 次以上。

原因：

- 3 次足以初步观察稳定性；
- 5 次可以在必要时补强说服力；
- 时间成本仍可接受。

## 11. B-Level Should Be Short-to-Mid Length, Not Long-Horizon By Default

第一阶段的 B 级测试，不建议做成长跑主导。

原因：

- B 级目标是“产生真实 episode 并回查主链”；
- 不是“验证长期人生演化是否稳定”；
- run 太长会放大路径漂移、提高成本，也会让 episode 分布更难分析。

建议：

- S1：8 到 12 steps；
- S2：8 到 12 steps；
- S3：10 到 15 steps。

更长、更高随机性的场景留给后续 C 级去做。

## 12. Sample Quality Gate Is Mandatory

B 级测试非常容易出现这样的问题：

- 某次 run 的指标看起来很好；
- 但其实只产生了很少的 usable probe；
- 而且这些 probe 全是 easiest cases。

因此 B 级不能只输出 hit@3、MRR 等指标，还必须输出样本质量统计。

每次 run 至少应记录：

- persisted episode count；
- usable probe count；
- skipped episode count；
- skipped reasons；
- action type distribution；
- agent distribution。

### 12.1 Recommended Validity Gate

建议为每次 B 级 run 增加最低有效性门槛，例如：

- usable probe 数低于某下限，则该 run 标记为：
  - `blocked` 或
  - `invalid_for_reporting`

这样做的目的是避免：

- 用样本极少的一次 run 直接进入正式平均；
- 误把“episode 没产生出来”解释成“memory 检索差”。

## 13. Aggregation Rule

B 级结果不建议只做一个全局大平均。

更合理的汇总结构是三层：

### 13.1 Run-Level

每个 run 单独记录：

- Hit@1；
- Hit@3；
- MRR；
- cross-agent contamination；
- usable probe count；
- skipped count。

### 13.2 Pack-Level

对同一 pack 的多次 run 汇总：

- mean；
- min / max；
- variance 或 std（可选但推荐）；
- total usable probes；
- invalid runs count。

### 13.3 Overall B-Level Summary

最后再给 B 级一个总表，作为第一阶段主 KPI 汇报入口。

这样做的好处：

- 不会被单个大样本 run 淹没；
- 能看出某个 pack 是否特别不稳定；
- 更容易定位是哪个风险维度出问题。

## 14. Failure Attribution Order

B 级失败时，不应直接归因于“长期记忆差”。

建议按下面顺序排查：

1. 本次 run 是否产生了足够 episode；
2. episode 是否被正确持久化；
3. usable probe 构造是否合理；
4. gate 是否打开；
5. retrieval 是否 exact 命中；
6. agent filter 是否失效；
7. overlap suppression 是否过滤；
8. recall budget / prompt budget 是否阻断；
9. recall 是否注入；
10. 模型是否在行为上使用了注入记忆。

## 15. Practical Position For Phase 1

如果目标是“稳妥、务实、好实现”，那么第一阶段 B 级最推荐的做法是：

1. 不使用开放随机场景；
2. 使用 3 个固定 scenario packs；
3. 每个 pack 使用固定 manual/file agent profiles、固定 topic seed、固定 step count；
4. 正式汇报时每个 pack 跑 3 次起步；
5. 加入 usable probe 有效性门槛；
6. 按 run / pack / overall 三层汇总；
7. 把 B 级明确定位为“真实 replay 主 KPI 层”，不承担完整行为级结论。

## 16. Suggested Next Doc Change

最建议的后续文档动作是：

- 在 `docs/memory/evaluation/` 下单独增加一个 `b-level-scenario-pack-design.md`；
- 或在 `dataset-and-reliability.md` 中新增一节 `B-Level Scenario Pack Design`。

建议写死的内容包括：

- S1 / S2 / S3 的固定启动配置；
- 每个 pack 的覆盖风险维度；
- 每个 pack 的 run count；
- step count；
- 最低 usable probe 门槛；
- pack 级汇报口径。

## 17. One-Sentence Working Definition

推荐在后续文档里把 B 级定义写成：

> **B 级不是开放世界随机 simulation 的一次性分数，而是在固定场景包下，基于真实运行产生的 `ActionEpisode` 做 replay 回查的主 KPI 层。**
