# Memory Migration Module Mapping

- Status: active
- Audience: migration implementers, reviewers, AI tools
- Role: map old `oasis-dashboard` memory modules to the new `socitwin` file layout

## 1. Mapping Principle

本页只回答一个问题：

- 旧仓库的每个 memory 主模块，在新仓库里应该落到哪里；
- 是直接迁、适配后迁，还是需要按新架构重写。

迁移原则：

- 优先迁“语义 contract”，不是机械保留旧文件名；
- 只有在新仓库职责边界仍然成立时，才直接复用旧实现；
- 凡是和旧引擎壳、旧 dashboard 入口强耦合的部分，都按新仓库 runtime 重写。

## 2. Runtime Entry And Wiring

### 2.1 Old runtime entry

旧仓库的顶层入口主要是：

- `/home/grayg/oasis-dashboard/oasis_dashboard/real_oasis_engine_v3.py`

它承担了：

- 模式解析
- 模型 runtime 装配
- long-term backend 装配
- agent 构造分流

### 2.2 New runtime entry

新仓库对应的接入中心应是：

- [`backend/app/core/oasis_manager.py`](/home/grayg/socitwin/backend/app/core/oasis_manager.py)

但不建议把 memory 主链直接塞回 `core/`。推荐形态是：

- `core/oasis_manager.py`
  - 负责接入与调度
- `backend/app/memory/runtime.py`
  - 负责两模式 runtime facade
- `backend/app/memory/agent.py`
  - 负责 `upstream` / `action_v1` agent wiring

### 2.3 Current source-type asymmetry

当前新仓库里三种 agent source 的技术形态并不对称：

- `template`
  - 由 `socitwin` 自己生成 profile，并逐个创建 agent
- `manual`
  - 由 `socitwin` 自己读取配置，并逐个创建 agent
- `file`
  - `upstream` 仍借用 OASIS 上游 `generate_twitter_agent_graph(...)` / `generate_reddit_agent_graph(...)`
  - `action_v1` 已改为在新仓库内解析 file profile，再复用 `_build_social_agent(...)`

这意味着：

- `template/manual` 可以自然切入 `memory/agent.py`
- `file` 在 `action_v1` 下也已经纳入了新仓库自己的 agent builder
- 但 `upstream` 与 `action_v1` 在 file source 下仍保持不同实现路径

因此迁移阶段必须明确：

- `upstream` 可继续沿用上游 graph generator
- `action_v1` 不应回退到原生 `SocialAgent`
- `action_v1` 的 file parser 至少应兼容：
  - 上游原生 Twitter CSV
  - 上游原生 Reddit JSON
  - 新仓库文档中整理过的统一字段子集

## 3. Old -> New Module Mapping

### 3.1 First-wave modules

这些模块决定能否先把 `action_v1` 主链在新仓库里立起来。

| 旧模块 | 当前职责 | 新位置建议 | 迁移方式 | 前置条件 |
|---|---|---|---|---|
| `real_oasis_engine_v3.py` | 模式分流、模型 runtime、long-term 装配 | `backend/app/core/oasis_manager.py` + `backend/app/memory/runtime.py` | 拆分重写 | 两模式边界已冻结 |
| `context/config.py` | runtime settings / preset / budget surface | `backend/app/memory/config.py` | 适配后迁 | 新仓库 settings 兼容层 |
| `context/llm.py` | shared model runtime、context limit / generation limit 分离、token counter 解析 | 当前主要散落在 `backend/app/core/oasis_manager.py` | 尚未完整迁回 | 旧仓库的独立模型 runtime 包装没有以同等形态恢复 |
| `context/agent.py` | agent 接线、bounded memory、action_v1 runtime 挂载 | `backend/app/memory/agent.py` | 适配后迁 | `memory/runtime.py` 骨架 |
| `context/environment.py` | observation 获取与发布 | `backend/app/memory/environment.py` | 适配后迁 | `agent.py` 和 runtime facade |
| `context/observation_shaper.py` | observation 压缩与 fallback | `backend/app/memory/observation_shaper.py` | 优先迁语义 | `memory/config.py` |
| `context/prompt_assembler.py` | observation / recent / compressed / recall prompt 裁决 | `backend/app/memory/prompt_assembler.py` | 优先迁语义 | `working_memory.py`、`recall_planner.py` |

### 3.2 Working-memory modules

| 旧模块 | 当前职责 | 新位置建议 | 迁移方式 | 说明 |
|---|---|---|---|---|
| `context/working_memory.py` | recent / compressed 结构、block 构造 | `backend/app/memory/working_memory.py` | 优先迁语义 | 可较高保真迁入 |
| `context/consolidator.py` | recent -> compressed 维护 | `backend/app/memory/consolidator.py` | 优先迁语义 | 依赖 token counter / summary preset |
| `context/memory_rendering.py` | recent/action block/heartbeat 渲染 | `backend/app/memory/memory_rendering.py` | 适配后迁 | 与 assembler / consolidator 成套迁移 |

### 3.3 Action-to-episode modules

| 旧模块 | 当前职责 | 新位置建议 | 迁移方式 | 说明 |
|---|---|---|---|---|
| `context/action_evidence.py` | 从 prompt-visible snapshot 构造动作证据 | `backend/app/memory/action_evidence.py` | 优先迁语义 | 是 `ActionEpisode` 质量的前提 |
| `context/action_capabilities.py` | 动作类别、target 解析、authored content 提取 | `backend/app/memory/action_capabilities.py` | 优先迁语义 | 需要核对新仓库动作枚举命名 |
| `context/action_significance.py` | significance、memory_worthy、执行状态规范化 | `backend/app/memory/action_significance.py` | 适配后迁 | 与 `episodic_memory.py`、`consolidator.py` 配套 |
| `context/episodic_memory.py` | `StepSegment` / `ActionEpisode` / `HeartbeatRange` | `backend/app/memory/episodic_memory.py` | 优先迁语义 | 主数据 contract，尽量保持稳定 |

### 3.3.1 Special note on `context/agent.py`

旧仓库的 `context/agent.py` 不是一个薄薄的 wiring 文件，它同时承担了：

- bounded chat history mixin
- assistant `<think>` 清洗
- observation / episodic / recall / prompt assembler / runtime failure 的 agent 内部状态挂载

因此新仓库迁移时不能把它简单理解为“切换不同 agent class”。

更合理的拆法是：

- `memory/agent.py`
  - 只保留 mode-aware agent wiring 与必要 mixin
- `memory/runtime.py`
  - 持有更高层的 runtime 装配逻辑
- `memory/status.py` or equivalent
  - 负责把 agent 内部 trace 暴露出来

同时要注意：

- 旧仓库里的 `BaselineSocialAgent` 不再迁入运行主链；
- 只能迁出其中仍对 `upstream` / `action_v1` 有价值的通用辅助逻辑。

### 3.3.2 Special note on `context/llm.py`

旧仓库的 `context/llm.py` 不是普通 helper，它承担了：

- shared model runtime 构造
- `context_token_limit` 与 `generation_max_tokens` 的显式分离
- token counter 解析与 fallback
- pooled model 的一致性约束

当前新仓库没有一个等价的 `memory/llm.py`，而是由：

- `backend/app/core/oasis_manager.py`
  - 直接创建模型
- `backend/app/memory/agent.py`
  - 在 action_v1 运行时单独解析 token counter / context budget

这意味着当前迁移状态应理解为：

- memory 主链已经跑通；
- 但旧仓库那套更完整的“模型 runtime 包装层”并没有以独立模块完整迁回；
- 特别是 `context token limit` 与 `generation max tokens` 的语义分离，目前更多依赖：
  - `OASIS_CONTEXT_TOKEN_LIMIT`
  - `llm_config.max_tokens`
  - `action_v1` 内部预算

因此这一块应被视为：

- 已记录的剩余迁移差异；
- 后续需要继续核对是否要补成更接近旧仓库 `llm.py` 的统一 runtime 包装。

同时当前迁移边界也应明确：

- 不以“把旧 `context/llm.py` 原样补回”为目标；
- 只在它已经造成明确运行语义偏差或工程阻塞时，才考虑在新仓库里补一个更小的 model runtime helper；
- 该 helper 应服从新仓库当前目录与职责边界，而不是回退成旧仓库壳。

### 3.4 Long-term / recall modules

| 旧模块 | 当前职责 | 新位置建议 | 迁移方式 | 说明 |
|---|---|---|---|---|
| `context/longterm.py` | embedding、Chroma、episode write/read | `backend/app/memory/longterm.py` | 拆分适配 | 新仓库依赖和路径要重新接 |
| `context/retrieval_policy.py` | query 生成、结果格式化、reason trace | `backend/app/memory/retrieval_policy.py` | 优先迁语义 | 可先保持旧 contract |
| `context/recall_planner.py` | recall gate、query、注入准备、runtime state | `backend/app/memory/recall_planner.py` | 优先迁语义 | 是 `action_v1` 差异能力核心之一 |

### 3.5 Failure / recovery modules

| 旧模块 | 当前职责 | 新位置建议 | 迁移方式 | 说明 |
|---|---|---|---|---|
| `context/runtime_failures.py` | provider 错误归一化、budget exhausted 分类 | `backend/app/memory/runtime_failures.py` | 优先迁语义 | 新仓库要先恢复这层，避免 action_v1 失明 |
| `context/tokens.py` | token 计数与预算估算 | `backend/app/memory/tokens.py` | 适配后迁 | 需要核对新仓库模型调用链 |

## 4. New-Rewrite Modules

下面这些在新仓库里不适合简单复制旧实现，应该按新架构重写：

### 4.1 `memory/runtime.py`

这是新仓库专属的新文件，旧仓库没有完全同名、同职责的干净壳。

它需要承担：

- mode-aware runtime facade
- `upstream` / `action_v1` 装配分流
- 与 `OASISManager` 的最小耦合面

### 4.2 `memory/status.py` or equivalent

旧仓库的 memory trace 很多是通过测试 harness 和 runtime trace 分散暴露的。
新仓库至少需要一个统一出口，把这些信息组织给：

- 未来的 monitor/debug API
- 测试 harness

这部分不适合照搬旧文件，而应结合新仓库现有 `status` / `monitor` 形状来设计。

### 4.3 File-based agent graph builder

当前 `action_v1 + file` 已采用新的 file-based agent graph builder 思路落地。

它当前承担：

- 读取 Twitter CSV / Reddit JSON profile
- 在 `socitwin` 内部重建 `UserInfo`
- 调用新仓库自己的 mode-aware `_build_social_agent(...)`
- 最终生成 `AgentGraph`

这部分当前已经不再复用上游 `generate_*_agent_graph()` 作为 `action_v1` 的最终方案，因为那会持续绕开 `memory/runtime.py` 和 `memory/agent.py`。

## 5. Minimal Frontend Contract Notes

前端当前不是迁移第一优先级，但需要知道边界。

当前事实：

- 前端已有 memory/retrieval 占位类型：
  - [`frontend/src/lib/agentMonitorTypes.ts`](/home/grayg/socitwin/frontend/src/lib/agentMonitorTypes.ts)
- 当前后端并没有真实提供对口 memory snapshot / retrieval status

迁移阶段建议：

- 第一阶段不实现完整前端联动；
- 只保证后端 memory monitor/debug 输出未来可挂接；
- 不把前端占位当成阻塞项。

## 6. Immediate Deliverables

基于当前映射，第一波可执行交付物应是：

1. `backend/app/memory/` 目录骨架；
2. `memory/config.py` 与兼容 env 映射；
3. `memory/runtime.py` 与 `memory/agent.py`；
4. `OASISManager` 改造成 mode-aware 接入点；
5. `upstream` 显式化且不受 `action_v1` 污染；
6. 在此基础上再接 observation -> working memory -> recall 主链。

当前还应额外记住一个迁移现实：

- 第一波真正的“可运行主线”应定义为：
  - `upstream`：`template/manual/file`
  - `action_v1`：`template/manual/file`
