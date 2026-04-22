# External Benchmark Survey For Memory Evaluation

- Status: draft survey note
- Audience: implementers, evaluators, experiment/report authors, Codex collaborators
- Doc role: summarize external benchmarks relevant to `socitwin` long-term memory evaluation, explain what can and cannot be borrowed, and define a realistic reference position for the current project

## 1. Survey Goal

这份调研不是为了找到一个可以直接照抄的 benchmark。

更现实的目标是：

- 看外部有没有成熟 benchmark 可以直接覆盖 `socitwin` 当前问题；
- 如果没有，判断应该借哪些 benchmark 的设计思想；
- 避免把 `socitwin` 的评测问题误简化成“普通 RAG top-k 检索”。

## 2. Overall Conclusion

当前没有发现一个已经被广泛接受、又能直接套到：

- **多 agent 社交模拟**
- **长期记忆写入与检索**
- **recall gate / injection**
- **后续行为连续性**

这一整套问题上的统一 benchmark。

更接近真实情况的是：外部 benchmark 分散在几条不同路线：

1. RAG / retrieval 组件评测；
2. 长上下文评测；
3. 长时对话记忆评测；
4. 记忆与行动耦合的 agent memory 评测。

因此，`socitwin` 更适合采用“分层 benchmark + 场景包 + 多次运行统计”的路线，而不是期待一个现成的、类似 3DMark 那样的大一统标准。

## 3. Most Relevant Benchmark Families

## 3.1 Long-Term Conversational Memory Benchmarks

### 3.1.1 LoCoMo

LoCoMo 是当前最值得参考的长时对话记忆 benchmark 之一。

它的特点是：

- 使用 very long-term conversations；
- 对话跨度很长，包含多 session；
- 任务不仅有问答，还有事件总结和多模态对话生成；
- 核心难点在于长期时间跨度下的事件、时间、因果和一致性理解。

对 `socitwin` 的启发：

- 记忆 benchmark 不应该只做简单 fact lookup；
- 应该考虑长期时间关系、事件连续性和跨 session 的一致性；
- “长时记忆能力”可以拆成多个子任务，而不是只压成一个 retrieval 分数。

局限：

- LoCoMo 更偏对话记忆；
- 它不包含社交平台环境中的 `memory-agent-environment loop`；
- 它不能直接评测 `ActionEpisode`、agent filter、recall injection 这些 `socitwin` 特有问题。

### 3.1.2 LongMemEval

LongMemEval 面向的是 chat assistant 的长期交互记忆。

其重要价值在于：

- 它明确提出长期记忆应该拆成多个核心能力；
- 包括信息提取、多 session 推理、时间推理、知识更新、以及 abstention；
- 它关注的不是普通长上下文，而是“随着长期交互逐步积累的 memory”。

对 `socitwin` 的启发：

- 长期记忆评测应该按能力维度拆开；
- B 级和未来 C 级中，应显式区分：
  - 信息提取类问题；
  - 时间与更新类问题；
  - 需要拒答/不该触发 recall 的负样本；
- memory benchmark 不必一开始就追求“统一总分”。

局限：

- 它针对的是 assistant-user 对话；
- 不是多 agent 社交模拟；
- 不包含 `agent_id` 过滤、cross-agent contamination 这种问题。

## 3.2 Agent Memory In Action Benchmarks

### 3.2.1 MemoryArena

MemoryArena 是当前外部调研中，和 `socitwin` 问题意识最接近的 benchmark。

它的重要观点是：

- 现有许多 memory benchmark 只评“记忆”，不评“记忆如何指导后续行动”；
- 另一些 benchmark 则评 action，但不真正要求长期记忆；
- 真实 agent 场景中，记忆获取与后续行动是耦合的。

因此 MemoryArena 强调：

- 多 session；
- memory-agent-environment loop；
- 任务之间存在真实依赖；
- 记忆必须在后续子任务中被使用。

对 `socitwin` 的启发非常直接：

- 不能把 B 级 exact hit 直接当成最终价值证明；
- 长期记忆评测最终仍然要走向“记忆是否参与后续行为”；
- `socitwin` 的 recall benchmark 应显式保留从：
  - gate
  - retrieval
  - injection
  - behavior
  这几层递进的评测结构。

局限：

- MemoryArena 当前任务域不是社交模拟；
- 它不提供可直接迁移到 `ActionEpisode` 的场景模板；
- 对第一阶段工程落地来说，更像“方法论参照”而不是可直接复用的数据集。

## 3.3 RAG / Retrieval Benchmarks

### 3.3.1 CRAG (Comprehensive RAG Benchmark)

CRAG 强调的是：

- 真实 QA 任务是动态且异质的；
- 问题存在领域、流行度、时间动态性、复杂度差异；
- 简单的 RAG 配置并不能自动解决真实性和鲁棒性问题。

对 `socitwin` 的启发：

- B 级测试中的 scenario pack 不应只做单一 easiest case；
- 应覆盖不同 episode 分布和 retrieval 难度；
- 应考虑“时间动态”和“近似但错误”的情况，而不是只测清晰唯一目标。

### 3.3.2 BRIGHT

BRIGHT 的核心特点是：

- 它不是普通 information-seeking retrieval；
- 它专门评 reasoning-intensive retrieval；
- 关注的是“表面上不明显匹配，但实际上需要推理才能找出正确文档”的检索。

对 `socitwin` 的启发：

- probe 不应只使用最容易的显式关键词；
- 应该设计一些需要依靠 target、local context、action relation 才能定位的回查；
- 这对于 `ActionEpisode` 检索尤其重要，因为 episode 的正确命中往往不只是 topic matching。

### 3.3.3 MIRAGE

MIRAGE 的价值在于：

- 它不满足于只给一个总分；
- 它试图把 retrieval 与 generation 的交互拆细；
- 强调噪声、误导上下文、上下文未被正确利用等评测维度。

对 `socitwin` 的启发：

- 检到不等于用到；
- recalled 不等于 injected；
- injected 也不等于行为已改善；
- 因此必须把 retrieve-only、injection trace、behavior effect 分层汇报。

## 3.4 Long-Context Benchmarks

### 3.4.1 LongBench

LongBench 是长上下文 benchmark 的代表之一。

它的作用在于：

- 测模型在长文本、多任务场景中的长上下文理解能力；
- 覆盖单文档问答、多文档问答、总结、few-shot、synthetic task、code 等。

对 `socitwin` 的启发：

- 它提醒我们“上下文很长”本身就是一个独立压力源；
- 若未来需要评 observation / prompt 预算压力下 recall 是否仍可用，可以借它的“多任务长上下文压力测试”思路。

局限：

- 它测的是长上下文理解，不是长期 memory architecture；
- 它不直接评 recall gate、episode retrieval、agent filter、injection。

### 3.4.2 RULER

RULER 更像长上下文能力的 synthetic stress benchmark。

它的价值在于：

- 不只做简单 needle-in-a-haystack；
- 还覆盖 retrieval、multi-hop tracing、aggregation、question answering 等 synthetic 长上下文任务；
- 重点回答“模型宣称的 context size，实际能不能真正有效使用”。

对 `socitwin` 的启发：

- 若未来需要做长窗口高压测试，可以借 RULER 的“synthetic controllable pressure”思路；
- 尤其适合后续为 recall / prompt budget 设计 controlled pressure tests。

局限：

- 它仍是 long-context benchmark；
- 不是长期社交记忆 benchmark；
- 更适合作为压力测试思想来源，而不是 B 级主 benchmark 的骨架。

## 4. What These Benchmarks Tell Us About `socitwin`

## 4.1 There Is No Single Standard Benchmark To Copy

外部 benchmark 的现状说明：

- 对通用 RAG，有较成熟的 retrieval 指标体系；
- 对长上下文，有成熟的 long-context benchmark；
- 对长时对话记忆，也已有比较明确的 benchmark 方向；
- 但对“多 agent 社交模拟 + 长期记忆写入/检索 + recall 主链 + 后续行为连续性”这一组合问题，
  目前并没有一个现成的、统一的 benchmark 可直接照抄。

因此 `socitwin` 采用 A/B/C 三个评测层级，本身就是合理的。

## 4.2 The Most Useful External Idea Is Layered Evaluation

外部 benchmark 最值得借鉴的共同点，不是某个具体数据集，而是：

- 它们都不会只用一个单一分数解释完整系统；
- 更好的 benchmark 倾向于把能力拆层；
- 复杂系统尤其需要把 retrieval、memory use、behavioral effect 分开。

这和 `socitwin` 当前：

- 写入层；
- 检索层；
- gate 层；
- 注入层；
- 行为层；

这样的拆分方式是一致的。

## 4.3 B-Level Should Learn More From MemoryArena Than From Plain RAG Benchmarks

如果只从“B 级真实 replay benchmark 应该怎么设计”这个问题出发，最有参考价值的不是普通 RAG leaderboard，而是：

- LoCoMo / LongMemEval：告诉我们长期记忆题目应该怎么拆能力；
- MemoryArena：提醒我们不能把 memory 和 action 分开理解。

CRAG / BRIGHT / MIRAGE 的贡献更多体现在：

- 如何设计 retrieval 难度；
- 如何引入 hard negatives；
- 如何避免把 easiest case 当成 benchmark 全貌；
- 如何拆 retrieval 与 downstream use。

## 5. Practical Borrowing Strategy For `socitwin`

基于上述调研，`socitwin` 最适合采用的借鉴策略是：

### 5.1 Borrow From LoCoMo / LongMemEval

借：

- 长时记忆不应只测 fact lookup；
- 题目应按能力维度拆分；
- 应显式区分 temporal / update / multi-session style memory demand。

不直接照搬：

- 对话数据集；
- chat assistant 任务格式。

### 5.2 Borrow From MemoryArena

借：

- 记忆与后续行动耦合的评测立场；
- 多阶段任务依赖 memory 的思想；
- 不把高 retrieval 分数直接视为 agent memory 成功。

不直接照搬：

- 具体任务域；
- 环境和工具链。

### 5.3 Borrow From CRAG / BRIGHT / MIRAGE

借：

- retrieval 难度设计；
- hard negatives；
- 动态与更新问题；
- 组件级指标拆解；
- 噪声和误导性上下文分析。

不直接照搬：

- 通用 QA 的 benchmark 形式；
- 以知识问答为核心的 ground truth 定义。

### 5.4 Borrow From LongBench / RULER

借：

- 后续长窗口与高压条件下的压力测试设计思路；
- synthetic controllable pressure 的构造方法。

不直接照搬：

- 把 long-context benchmark 直接当作 long-term memory benchmark。

## 6. Implications For Current B-Level Design

这次调研反过来支持了一个更明确的结论：

> **B 级不应该被设计成“开放世界随机 simulation 的一次性分数”，而应该被设计成固定场景包下、基于真实运行产生 episode 的 replay 主 KPI 层。**

这个口径与：

- 外部 benchmark 生态现状；
- MemoryArena 对 memory-in-action 的强调；
- LoCoMo / LongMemEval 对长期记忆题型拆分的启发；
- CRAG / BRIGHT / MIRAGE 对 retrieval 复杂性的强调；

是相容的。

换句话说，外部调研并没有推翻当前 `socitwin` 文档路线，反而说明：

- A/B/C 分层是合理的；
- B 级应进一步强化“半受控 + 场景包 + 多次复跑统计”；
- C 级行为 benchmark 可以晚一点做，但方向应当保留。

## 7. Recommended Position In Reports

推荐对外口径：

- `socitwin` 当前不直接套用单一现成 benchmark，因为外部尚无统一覆盖“多 agent 社交模拟长期记忆”的成熟标准；
- 我们参考了长时对话记忆、agent memory、RAG 检索和长上下文 benchmark 的设计思想；
- 最终采用分层评测：
  - A 级提供确定性回归底座；
  - B 级提供真实主链上的 replay 主 KPI；
  - C 级作为后续行为效果增强层；
- 这比把所有结论压成一个总分更适合当前系统复杂度。

## 8. Suggested Next Documentation Step

建议在 `docs/memory/evaluation/` 下新增一个文档，例如：

- `external-benchmark-survey.md`

并在其中明确写出：

- 哪些 benchmark 是“方法论参照”；
- 哪些 benchmark 只能作为局部压力测试参照；
- 为什么 `socitwin` 需要自己的 B 级 replay benchmark，而不是直接套某个现成 leaderboards。

## 9. Reference List

下面是本次调研中最值得保留的参考入口：

### Long-term conversational memory

- LoCoMo (ACL Anthology)
  - https://aclanthology.org/2024.acl-long.747/
- LongMemEval
  - https://web.cs.ucla.edu/~kwchang/bibliography/wu2025longmemeval/

### Agent memory / memory-in-action

- MemoryArena project page
  - https://memoryarena.github.io/
- MemoryArena publication page
  - https://digitaleconomy.stanford.edu/publication/memoryarena-benchmarking-agent-memory-in-interdependent-multi-session-agentic-tasks/

### RAG / retrieval benchmark

- CRAG
  - https://huggingface.co/papers/2406.04744
  - https://researchportal.hkust.edu.hk/en/publications/crag-comprehensive-rag-benchmark-2/
- BRIGHT
  - https://brightbenchmark.github.io/
  - https://huggingface.co/papers/2407.12883
- MIRAGE
  - https://huggingface.co/papers/2504.17137

### Long-context benchmark

- LongBench
  - https://aclanthology.org/2024.acl-long.172/
- RULER
  - https://github.com/NVIDIA/RULER
