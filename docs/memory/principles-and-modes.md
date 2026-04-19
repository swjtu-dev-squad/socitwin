# Memory Principles And Modes

- Status: active working spec
- Audience: implementers, reviewers, AI tools
- Doc role: define why the memory route exists and what `upstream` / `action_v1` each own

## 1. Purpose

本文档回答三件事：

1. 为什么 `socitwin` 需要这条记忆路线；
2. 当前两种模式分别承担什么职责；
3. 哪些边界属于应继续坚持的硬约束。

这里讲的是模式原则和架构边界，不是具体代码导读。
具体实现入口见 [current-architecture.md](./current-architecture.md)。

## 2. Why This Route Exists

这条路线最初不是为了“多加一个模块”，而是为了解决原始 OASIS + CAMEL 在线性 chat history 下的两个自然膨胀问题：

- observation 膨胀
  - 每轮平台环境会被展开成较重文本；
  - 帖子、评论、群组、消息会持续占用上下文。
- history 膨胀
  - 默认 chat history 会在每轮继续累积 observation、assistant 文本和工具相关记录。

这两个问题叠加后，会导致：

- prompt 更快逼近上下文上限
- 模型调用成本和延迟上升
- 长步数模拟逐渐失真
- 最终出现 overflow、强退化或行为不连续

因此当前路线的目标不是“完全不要 memory”，而是：

- 保留 OASIS 模拟主干；
- 把上下文裁决、短期维护、长期写入和 recall 从默认线性 history 中显式抽出来。

## 3. Project Constraint

当前项目对 OASIS 的一个硬约束仍然成立：

- OASIS 通过依赖包安装；
- 不应直接改上游源码。

所以所有记忆相关改造都必须通过项目侧实现完成，例如：

- mode-aware runtime wiring
- 子类和包装器
- 配置解析层
- 独立 memory 模块

这也是为什么 `upstream` 必须存在：

- 它用来保留原始 OASIS 路径作为参照；
- 同时避免把所有行为差异都误归因到新记忆主链。

## 4. Current Mode Set

当前新仓库只保留两个正式运行模式：

- `upstream`
- `action_v1`

`baseline` 的地位已经改变：

- 它曾经在旧仓库里有明确作用；
- 但在新仓库迁移中不再作为运行模式保留；
- 后续只保留历史说明，不继续承担正式模式职责。

## 5. Mode Responsibilities

### 5.1 `upstream`

`upstream` 的职责是：

- 保留原始 OASIS 主链作为参照；
- 明确显示“未接入 action_v1 主链时，系统是什么行为”；
- 为对照和回归提供干净基准。

它不负责：

- 验证新记忆架构
- 承载显式 short-term / long-term / recall 主链

### 5.2 `action_v1`

`action_v1` 的职责是：

- 成为当前唯一的新记忆架构主线；
- 用显式 observation shaping、working memory、ActionEpisode long-term 和 side-context recall 替代默认线性 history 裁决；
- 为后续记忆质量优化提供稳定承载面。

它不应该被重新弱化成：

- 半个 upstream
- baseline 的兼容分支
- 单纯“多一点 trace”的上游包装

## 6. Separation Principle

两模式的分离原则不是“绝对不共享任何代码”，而是：

- 共享中性基础设施
- 不共享语义主链

当前允许共享的内容主要是：

- model/runtime 创建入口
- context token limit 与 token counter 解析
- 基础配置兼容层
- manager 级状态与 debug 聚合

当前不应共享的内容主要是：

- observation shaping
- prompt assembly
- explicit working memory
- ActionEpisode long-term 主链
- recall gate / retrieval / injection

这条原则的目的不是形式上的独立，而是防止：

- `upstream` 被 `action_v1` 反向污染；
- `action_v1` 因兼容旧路径而继续背负多条语义分支。

## 7. Hard Boundaries Worth Preserving

下面这些边界当前应继续视为硬约束，而不是普通调参项。

### 7.1 Prompt-Visible Fact Boundary

`action_v1` 后续写入和回忆的事实边界，应继续建立在 prompt-visible snapshot 上。

这意味着：

- observation prompt 和 snapshot 必须同源；
- `target_snapshot` 不能通过后验查库伪造补全；
- degraded observation 应显式标记，而不是假装拿到了完整事实。

### 7.2 Single Prompt Assembly Authority

`PromptAssembler` 应继续作为单一 prompt 装配者。

不能重新回到：

- 多处各自压缩
- 最后一跳再做黑盒截断
- recent / compressed / recall 各自偷偷改写内容

### 7.3 Long-Term Primary Unit

长期记忆的主单位应继续是 `ActionEpisode`。

不应退回到：

- 整步纯文本摘要
- 原始 chat history 片段
- recall note 反向写回长期层

### 7.4 Recall Is Side-Context

recall 只应作为 side-context 进入 prompt。

它不能被重新解释成：

- 新 observation
- 新事实源
- 自动覆盖当前可见环境的强指令

### 7.5 Topic Activation Is Environment Seed

当前 `topic activation` 仍应视为环境种子，而不是普通 agent 自主行为。

因此当前接受的边界是：

- 它会进入平台环境，后续 observation 能看到；
- 但不进入普通 `ActionEpisode` 主链。

如果后续需要更强解释性，更合理的方向是单独 trace：

- `environment_seed`
- `experiment_injection`

而不是直接把它伪装成 agent 自主记忆事件。

## 8. Current Non-Goals

当前路线不试图在这一轮解决下面这些问题：

- 完整 persona / goal memory
- 完整 social graph memory
- 所有 OASIS 原始动作的同等事件化覆盖
- 最终版 embedding 路线比较
- `openai_compatible -> heuristic` 的自动兼容回退
- 完整 comparison 评测常态化
- 所有 memory 大文件的彻底工程拆分

这些事情都重要，但不应重新打断当前主线。

## 9. Current Judgment On Historical Baseline

关于旧仓库 `baseline`，当前应这样理解：

- 它在旧仓库阶段有真实价值；
- 但新仓库迁移目标已经收缩为：
  - 保留一个干净 `upstream`
  - 保留唯一的新架构模式 `action_v1`
- 因此 `baseline` 不再进入新仓库运行代码

后续文档里如果还需要提到它，只应出现在：

- 历史背景
- 迁移决策
- 旧测试结果解释

而不应再作为正式模式说明主体。

## 10. Current Maintenance Rule

后续维护两模式文档时，按下面规则处理：

- 代码事实变了：
  - 先更新 [current-architecture.md](./current-architecture.md)
- 模式边界或原则变了：
  - 更新本文档
- 只是迁移过程判断或历史对照变了：
  - 更新 `migration-*` 文档

## 11. Related Docs

- 当前实现与入口：
  - [current-architecture.md](./current-architecture.md)
- 文档迁移计划：
  - [migration-documentation-plan.md](./archived/migration/migration-documentation-plan.md)
- 迁移决策与历史边界：
  - [migration-decisions.md](./archived/migration/migration-decisions.md)
