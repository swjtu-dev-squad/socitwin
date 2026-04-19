# Memory Migration Refactor Principles

- Status: active
- Audience: migration implementers, reviewers, AI tools
- Role: define what kind of refactor is allowed during migration, and what must remain stable

## 1. Why This Page Exists

这次工作虽然名义上是把旧仓库的记忆系统迁到新仓库，但对记忆子系统本身来说，它同时也是一次新的工程化落地。

如果不提前把边界写清楚，实施时很容易走向两种坏结果：

- 机械迁移
  - 只是把旧代码整坨搬过去；
  - 把旧仓库里已经形成的结构债、兼容壳、职责混杂继续原样带入新仓库。
- 失控重构
  - 借迁移名义重新打开大量已经多轮审查过的核心语义问题；
  - 让迁移期再次演变成一轮新的路线级重构。

因此，本轮迁移需要明确采用：

- 保留主 contract
- 允许结构清污
- 禁止语义重开

的策略。

## 2. Core Position

本轮迁移不是“第三次重新设计记忆路线”。

本轮迁移的定位应是：

- 在新仓库中重新落地当前已经多轮审查与修正后的记忆主链；
- 同时借新架构清理旧仓库中不再值得继续背负的结构债；
- 让新仓库中的记忆子系统以更干净、可维护、可继续演进的形态重新开始。

换句话说：

- 这次迁移对记忆子系统来说，允许小幅重构；
- 但这个“小幅重构”主要是结构层面的，不是路线语义层面的。

## 3. What Must Stay Stable

下面这些应被视为当前记忆系统已经稳定下来的主 contract，迁移时原则上保真落地，不应借机重新设计：

### 3.1 Observation fact boundary

- `observation -> prompt-visible snapshot`

这是当前所有后续 memory 语义的上游事实边界。迁移时应保留这一主线，而不是重新改回“直接从任意原始 observation 文本里反推”。

### 3.2 Action-centered memory contract

- `ActionEvidence -> ActionEpisode`

这是当前长期记忆和 recall 主链的核心 contract。迁移时应保留动作中心事件化，而不是重新退回泛化、松散的 step summary 主导模式。

### 3.3 Short-term two-layer structure

- `recent`
- `compressed`

这二层结构已经是当前短期记忆的主表示，不应在迁移期再重新发明第三套短期主结构。

### 3.4 Unified prompt assembly role

- `observation`
- `recent`
- `compressed`
- `recall`

由 `PromptAssembler` 统一裁决，这一角色边界应保持稳定。

### 3.5 Long-term write / recall mainline

- `ActionEpisode` 持久化
- recall gate
- recall 注入 side-context

这是当前 action_v1 的主价值所在，迁移时应视为主链，而不是可有可无的外挂。

### 3.6 Failure / recovery as an explicit layer

- runtime failure normalization
- budget recovery
- provider overflow handling

这层已经证明有工程价值，迁移时不应再把它打回零散异常处理。

## 4. What May Be Cleaned Up During Migration

下面这些属于迁移时允许顺手清理的结构债，且建议主动清理。

### 4.1 Baseline runtime residue

新仓库已确定只保留：

- `upstream`
- `action_v1`

因此旧仓库中所有只为 `baseline` 继续存在的运行级结构，不应继续带入新仓库。

`baseline` 只保留历史文档说明，不再保留运行主链。

### 4.2 Overloaded `agent.py`

旧仓库 `context/agent.py` 同时承担了：

- agent wiring
- bounded memory mixin
- action_v1 runtime 状态挂载
- recall / assembler / consolidator 初始化
- 内部 trace 字段承载

这属于典型的“能跑但不干净”的历史产物。迁移时允许并建议拆开：

- `memory/agent.py`
  - 保留 agent wiring 与必要 mixin
- `memory/runtime.py`
  - 承担 runtime 装配
- `memory/status.py` 或同类模块
  - 承担 memory trace / snapshot 输出

### 4.3 Overloaded `config.py`

旧仓库 `context/config.py` 已经承载过多职责：

- preset 定义
- runtime settings
- env 解析
- budget 校验
- provider matcher preset

迁移时允许把这些职责拆分得更清楚，至少在逻辑上分层：

- outer settings shell
- memory preset definitions
- compatibility parsing / normalization

### 4.4 Large umbrella exports

旧仓库 `context/__init__.py` 这种几乎导出整个子系统的总出口，不建议继续延续。

新仓库应尽量避免：

- 大而全的 barrel export
- 模块边界模糊
- 后续循环依赖风险继续放大

### 4.5 Transitional aliases and compatibility shells

凡是旧重构过程中留下来的：

- 兼容别名
- 过渡属性
- 仅用于旧壳接线的包装层

如果在新仓库不再必要，应直接清掉，不应为了“迁起来省事”而继续背着。

### 4.6 Non-primary backends as first-class runtime paths

当前工程落地以：

- Chroma

为主。

因此迁移时不应继续把：

- InMemory store

当成正式主线路径去维护。它如果保留，应更偏：

- test helper
- debug fallback

而不是正式运行主链。

### 4.7 Scattered memory status fields

旧仓库很多 internal trace 直接挂在 agent 私有字段上，这是旧工程形态下的务实方案，但不是新仓库里最干净的终态。

迁移时允许把这些状态：

- 统一收口
- 形成结构化 memory snapshot / runtime trace 出口

## 5. What Must Not Be Reopened During Migration

下面这些问题虽然未来仍可继续优化，但本轮迁移不应借机重开。

### 5.1 Budget tree redesign

不在迁移期重新发明整套：

- budget tree
- reserve policy
- ratio semantics

当前预算设计若有问题，应记录并在迁移后专项处理，而不是在迁移主链尚未稳定时边迁边改。

### 5.2 Observation strategy redesign

不在迁移期重新发明 observation 压缩主策略，例如：

- 重新改压缩层级
- 重新设计 snapshot 上游结构
- 重新扩大 object family

### 5.3 Short-term architecture redesign

不在迁移期重新推翻：

- recent / compressed

这套主结构。

### 5.4 Recall algorithm redesign

不在迁移期重写：

- recall gate
- overlap suppression
- retrieval ranking 主体逻辑

除非出现明确迁移阻塞 bug。

### 5.5 Model-in-the-loop redesign

不在迁移期重新打开这些路线级议题：

- 事件化是否引入模型参与
- 超长文本是否改成模型提炼
- recall rerank 是否换成模型驱动

这些属于后续增强项，不属于迁移主链。

## 6. Migration Implementation Guideline

迁移实施时，应始终按下面这条判断顺序做取舍：

1. 这个改动是在保住当前主 contract 吗？
2. 这个改动是在清理旧结构债吗？
3. 这个改动会不会重新打开已经审过的路线语义？

只有前两项成立、第三项不成立时，才属于本轮允许的“小幅重构”。

## 7. Practical Interpretation

本轮迁移对记忆子系统的正确理解应是：

- 不是简单复制；
- 也不是借壳重来；
- 而是在新仓库里把当前已经形成的记忆主链，以更干净的结构重新落地。

因此，这次迁移的目标不是“最大程度保留旧文件长相”，而是：

- 最大程度保留已审定的语义主线；
- 最大程度清掉不值得继续带入新仓库的历史结构。
