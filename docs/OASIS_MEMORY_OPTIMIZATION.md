# OASIS 记忆优化架构说明

## 1. 文档目的

本文档说明当前项目在 OASIS 与 CAMEL 之上实现的记忆与上下文优化架构。

这不是阶段性进度汇报，也不是 issue 摘要。本文档的目标是作为一篇正式技术文档，系统解释以下内容：

- 为什么需要进行记忆优化；
- 当前 memory/context 优化架构由哪些部分组成；
- 当前实现如何接入 OASIS 与 CAMEL；
- 已完成的能力边界是什么；
- 当前方案对模拟保真度的影响是什么；
- 如何在本地运行、验证和排查问题；
- 后续从 P1 到 P2 的合理演进路线是什么。

本文档的读者包括：

- 代码审查人员；
- 后续继续开发该模块的工程师；
- 需要理解当前系统行为边界的研究人员或汇报人员。

---

## 2. 问题背景

### 2.1 原始问题

在默认的 OASIS + CAMEL 执行路径中，记忆膨胀问题主要来自以下链路：

1. `SocialAgent.perform_action_by_llm()` 每一步都会调用环境对象，将当前平台状态序列化为文本 observation。
2. 上游 `SocialEnvironment` 会把推荐帖子、群组状态等内容直接转为文本。帖子部分在 OASIS 原始实现中使用了带缩进的 JSON 序列化。
3. CAMEL `ChatAgent.astep()` 在推理前会先把当前 user observation 写入 memory，推理后再追加 assistant 与工具调用相关记录。
4. 这些记录会随着步数持续累积，最终导致 context token 不断增大。

在长期模拟场景中，这会产生两类问题：

- **Observation 膨胀**：单步 observation 文本本身过大；
- **Memory 膨胀**：历史 observation、assistant 输出和工具调用记录不断积累。

其直接后果包括：

- prompt/context 迅速接近模型上下文上限；
- memory 检索和 context 构造越来越慢；
- 长步数下 step latency 明显恶化；
- 最终可能出现请求失败、输出漂移或长期行为失真。

### 2.2 为什么不能直接修改上游代码

本项目中的 OASIS 通过依赖包安装在 `.venv` 中，属于外部依赖。

因此本项目的优化必须满足“零侵入”要求：

- 不修改 `.venv` 中的 OASIS/CAMEL 源码；
- 所有优化必须通过项目侧代码实现；
- 主要技术手段包括：
  - 子类继承；
  - 依赖注入；
  - 包装器；
  - 运行时配置控制。

---

## 3. 设计目标与阶段划分

当前架构按照三个阶段推进。

## 3.1 P0：短中程止血与可观测

P0 的目标不是直接解决长期模拟，而是让系统先完成第一层止血：

- 上下文预算必须可靠且显式；
- 当前 observation 不能轻易被写入阶段切碎；
- observation 文本体积需要压缩；
- 系统必须具备足够的运行时观测能力。

P0 完成后，系统应达到：

- 短中程运行更稳定；
- 不容易因为 context 配置问题立即失败；
- 后续 P1/P2 的分析具备数据基础。

## 3.2 P1：长期模拟基础可运行

P1 的目标是让系统进入“长期模拟意义上的基本可运行”状态。

它至少要解决：

- 异常 memory 膨胀；
- 无意义 memory 污染；
- 长步数下明显失控的退化；
- 从“很快出错”转向“能够继续运行且问题可分析”。

## 3.3 P2：长期记忆能力演进

P2 的目标是在 P1 的基础上引入真正的长期记忆能力：

- 让系统不再只依赖线性 chat history；
- 支持按语义或事件召回较早历史；
- 更好地维持长程行为连续性。

---

## 4. 设计原则

### 4.1 零侵入

所有优化都在项目代码中完成。上游 OASIS 和 CAMEL 的源码保持不变。

### 4.2 显式预算优于依赖后端默认值

模型输出预算与短期上下文预算是两个不同概念，必须分开控制。

当前方案明确区分：

- generation max tokens；
- declared context window；
- short-term memory context token limit。

### 4.3 优先保护当前 observation

当前步的 observation 是最关键的短期输入。

因此架构优先保证：

- 当前 observation 尽量整体保留；
- 老历史优先掉出上下文；
- 避免因为剩余预算不足而把当前 observation 提前切成碎片。

### 4.4 系统级保真度以 Oasis 完整能力模型为基准

当前 dashboard 只开放了少量动作，但 Oasis 本身支持远多于当前接入层的动作空间。

因此需要严格区分两件事：

- **接入层策略**：当前 dashboard 为了运行和展示而做的局部优化；
- **系统级原则**：整个 Oasis 框架在完整动作空间下的保真要求。

系统级上，任何可能成为：

- 动作目标；
- 交互对象；
- 长期状态依赖；

的信息，都不能被默认视为弱相关。

这条原则对以下场景都成立：

- Reddit / Twitter 默认平台；
- 后续开放更多 Oasis 原生动作；
- 自定义平台；
- 自定义算法；
- 自定义行为。

### 4.5 短期控制与长期记忆分层处理

P0 和早期 P1 的任务，是先把短期 memory 做稳、做可控、做可观测。

长期记忆应当建立在稳定的短期层之上，而不是在短期层不稳定时直接叠加复杂机制。

---

## 5. 当前架构总览

当前实现主要分布在：

- `oasis_dashboard/context/`
- `oasis_dashboard/real_oasis_engine_v3.py`

整体关系如下：

```text
┌──────────────────────────────────────────────────────────┐
│                    Dashboard / Frontend                 │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP / Socket
┌───────────────────────▼──────────────────────────────────┐
│                       server.ts                         │
│  启动 Python RPC，引导配置、转发控制命令、回传状态指标      │
└───────────────────────┬──────────────────────────────────┘
                        │ spawn
┌───────────────────────▼──────────────────────────────────┐
│                RealOASISEngineV3 (Python)               │
│  构建模型运行时、创建 agent、执行 step、汇总 context 指标    │
└───────────────────────┬──────────────────────────────────┘
                        │ inject
┌───────────────────────▼──────────────────────────────────┐
│                 ContextSocialAgent                      │
│  替换 env/memory，拦截 memory 写入，清理 assistant think     │
└───────────────────────┬──────────────────────────────────┘
                        │ uses
        ┌───────────────▼───────────────┐
        │    ContextSocialEnvironment   │
        │ observation 序列化与压缩       │
        └───────────────┬───────────────┘
                        │ uses
        ┌───────────────▼───────────────┐
        │   ContextChatHistoryMemory    │
        │ 修复 tool cleanup，管理短期历史 │
        └───────────────┬───────────────┘
                        │ uses
        ┌───────────────▼───────────────┐
        │ ScoreBasedContextCreator      │
        │ token 预算内构造最终上下文      │
        └───────────────────────────────┘
```

---

## 6. 模块组成说明

## 6.1 模型运行时层

相关文件：

- [llm.py](/home/grayg/oasis-dashboard/oasis_dashboard/context/llm.py)
- [config.py](/home/grayg/oasis-dashboard/oasis_dashboard/context/config.py)
- [tokens.py](/home/grayg/oasis-dashboard/oasis_dashboard/context/tokens.py)

这一层负责把模型接入显式化，核心目标是为 memory/context 管理提供稳定、可推导的预算基础。

### 6.1.1 `ModelRuntimeSpec`

`ModelRuntimeSpec` 用于描述一个模型后端的运行时参数，包括：

- `model_platform`
- `model_type`
- `url`
- `api_key`
- `generation_max_tokens`
- `declared_context_window`
- `context_token_limit`
- `token_counter`

### 6.1.2 `build_shared_model(...)`

该入口统一处理：

- 单模型后端；
- 同构模型池；
- `ModelManager(round_robin)` 封装；
- token counter 选择；
- context token limit 推导。

当前设计约束：

- 池化模型必须是同构的；
- 池内模型必须共享相同的平台、模型类型与 context budget；
- 否则直接报错，不允许混合。

### 6.1.3 `HeuristicUnicodeTokenCounter`

这是当前项目的离线安全 fallback token counter。

它的目标不是完全复刻 provider tokenizer，而是：

- 在本地环境下给出稳定近似；
- 支持 CAMEL 的 chunking API；
- 在缺乏后端 token counter 时仍可完成预算估算。

当前估算规则大致为：

- ASCII 按较低比例估算；
- CJK 字符按较高成本估算；
- 其他 Unicode 字符按更保守的成本估算。

---

## 6.2 运行时设置层

相关文件：

- [config.py](/home/grayg/oasis-dashboard/oasis_dashboard/context/config.py)

`ContextRuntimeSettings` 将每个 agent 的短期记忆控制参数组织成统一对象，包括：

- token counter；
- system message；
- context token limit；
- observation soft limit；
- observation hard limit；
- `memory_window_size`；
- observation wrapper；
- compression 配置。

### 6.2.1 验证机制

`ContextRuntimeSettings.validate()` 会在初始化时检查：

- 当前 system prompt 是否已经过大；
- 最小有界 observation 形态是否仍能放进 hard limit。

这样可以尽早发现：

- context limit 配置过小；
- 当前平台 preset 与预算不匹配；
- 配置错误导致的启动即失败。

---

## 6.3 Observation 序列化层

相关文件：

- [environment.py](/home/grayg/oasis-dashboard/oasis_dashboard/context/environment.py)

`ContextSocialEnvironment` 负责接管 observation 的序列化与压缩。

### 6.3.1 目标

这一层的目标是：

- 保留上游 prompt scaffold；
- 压缩 observation 表示；
- 在预算压力下提供受控降级；
- 对当前运行时输出压缩统计信息。

### 6.3.2 当前处理流程

当前 observation 处理流程如下：

```text
refresh/listen_from_group
        │
        ▼
紧凑 Unicode JSON
        │
        ├─ 若 soft limit 内：直接返回
        │
        ▼
长文本截断（head-tail）
        │
        ▼
超长文本占位符替换
        │
        ▼
接入层局部摘要（comments/groups）
        │
        ▼
返回 observation prompt
```

### 6.3.3 当前压缩策略

当前实现包含 4 个阶段：

1. **紧凑 Unicode JSON**
   - 使用紧凑 JSON；
   - 禁止 Unicode 转义膨胀。

2. **长文本截断**
   - 对长文本采用 head-tail 截断；
   - 尽量保留首尾语义。

3. **占位符替换**
   - 对极长文本替换为简洁占位符；
   - 限制单字段对上下文预算的破坏。

4. **局部接入层摘要**
   - 当前仅对 dashboard 运行时不可操作的 comments/groups 做摘要；
   - 这是 deployment-specific 策略，不是系统级默认语义。

### 6.3.4 关于系统级保真度的修正

这里必须特别说明：

- 当前 comments/groups 的摘要逻辑，只是为了当前 dashboard 运行路径服务；
- 它不能被视为“Oasis 系统中 comments/groups 天然弱相关”的结论；
- 在完整 Oasis 动作空间下，comments/groups/follows/search results/trend/group messages 等都可能成为重要决策对象。

因此，后续系统级方案不能继续依赖“当前动作集没开，所以可以默认摘要”的思路。

---

## 6.4 Agent 注入层

相关文件：

- [agent.py](/home/grayg/oasis-dashboard/oasis_dashboard/context/agent.py)

`ContextSocialAgent` 是当前项目实现“零侵入接管”的核心入口。

### 6.4.1 它做了什么

它在保留上游 `SocialAgent` 主流程的前提下，完成以下工作：

- post-init 替换 environment；
- post-init 替换 memory；
- 保证 system message 仍保留在 memory 中；
- 拦截 `update_memory()`；
- 在 assistant message 写入前去掉 `<think>...</think>`。

### 6.4.2 为什么要拦截 `update_memory()`

CAMEL 原始 `ChatAgent.update_memory()` 是按“当前剩余预算”决定是否 chunk。

这会导致一个问题：

- 当前 observation 本身可能完全合法；
- 但因为旧历史已经占了很多预算；
- observation 会被切成多个 chunk 写入 memory。

这对保真度的危害很大，因为：

- observation 语义被切碎；
- 如果 observation 中包含结构化信息，后续理解会明显变差。

当前项目的策略是：

- 只要“system + 当前消息”整体还能放进 `context_token_limit`；
- 就整条写入；
- 让更老的历史在 `get_context()` 阶段掉出上下文，而不是先破坏当前 observation。

### 6.4.3 为什么要清理 assistant `<think>`

在一些本地推理后端中，assistant 输出会把 `<think>...</think>` 直接放进 `content`。

这部分内容：

- 不参与实际动作执行；
- 不应该成为长期行为记忆；
- 但会显著增加短期上下文消耗。

因此当前方案会在 assistant message 入 memory 前先清理这部分内容。

---

## 6.5 短期记忆层

相关文件：

- [memory.py](/home/grayg/oasis-dashboard/oasis_dashboard/context/memory.py)

`ContextChatHistoryMemory` 是项目侧短期记忆包装器。

### 6.5.1 设计目标

它的主要目标不是重写整套 CAMEL memory，而是：

- 保持与 CAMEL `ChatHistoryMemory` 兼容；
- 修复已确认的 cleanup 缺陷；
- 把当前短期历史控制在可分析的边界内。

### 6.5.2 已修复的问题

项目已确认上游 `clean_tool_calls()` 存在以下问题：

- 清理后直接重新 `save()`；
- 但不先 `clear()` storage；
- 导致历史重复追加；
- 还会漏删 assistant 的 function-calling placeholder。

项目侧包装器当前修复为：

- 删除 function/tool record；
- 删除 assistant tool-call placeholder；
- `clear()` 后再 `save()`；
- 避免重复堆积。

这一步是当前 P1 前半段最关键的修复之一。

---

## 6.6 引擎接入层

相关文件：

- [real_oasis_engine_v3.py](/home/grayg/oasis-dashboard/oasis_dashboard/real_oasis_engine_v3.py)

这是 dashboard 与 Python 模拟侧的总接入点。

### 6.6.1 主要职责

它负责：

- 构造 resolved model runtime；
- 构造 `ContextRuntimeSettings`；
- 创建 `ContextSocialAgent`；
- 为当前 dashboard 选择运行时 action 子集；
- 在每一步后汇总 `context_metrics`。

### 6.6.2 当前 `context_metrics`

当前会汇总的指标包括：

- 压缩前后 observation 字符数；
- 截断字段数；
- 占位符字段数；
- comments/groups 摘要数量；
- 平均/最大 context token；
- 平均/最大 memory record 数；
- `get_context()` / `retrieve()` 耗时；
- `system/user/assistant/function/tool/assistant_fn` 各类 record 数量。

这些指标是当前排查问题的基础。

没有这些指标，就无法区分：

- 异常 memory 膨胀；
- 正常线性积累；
- 模型慢；
- memory 检索慢；
- observation 过大。

---

## 7. 当前运行链路说明

完整运行链路如下：

```text
前端页面操作
    │
    ▼
server.ts 接收请求
    │
    ▼
启动 / 调用 real_oasis_engine_v3.py --rpc
    │
    ▼
初始化模型运行时与 agent
    │
    ▼
OASIS 环境 step()
    │
    ├─ 平台更新推荐表
    ├─ agent 获取 observation
    ├─ ContextSocialEnvironment 压缩 observation
    ├─ ContextSocialAgent 调用 CAMEL
    ├─ memory 写入经 ContextSocialAgent 拦截
    ├─ tool call cleanup 经 ContextChatHistoryMemory 修复
    └─ 汇总 context_metrics
```

这一链路里有两层保护：

### 7.1 写入阶段保护

目标：

- 不要让当前 observation 在进入 memory 前就被 chunk 切碎。

### 7.2 上下文构造阶段保护

目标：

- 在 `memory.get_context()` 时，让 CAMEL 在 token 预算内优先保 system 和新历史；
- 让旧历史逐步掉出上下文。

这两层必须区分。

如果只看“context 被截断”，很容易误以为所有问题都一样。实际上：

- 写入阶段切碎 observation，是更危险的破坏；
- 构造阶段丢掉老历史，是当前可接受但仍需继续优化的行为。

---

## 8. 当前阶段已解决的问题

## 8.1 P0 已解决的问题

P0 当前已解决：

1. **上下文预算不可靠**
   - 引入显式 `context_token_limit`；
   - generation budget 与 context budget 分离。

2. **Observation 表示膨胀**
   - 去掉 pretty JSON；
   - 禁止无意义 Unicode 转义放大；
   - observation 体积显著降低。

3. **Observation 写入阶段被切碎**
   - 通过 agent 层拦截，避免当前 observation 因剩余预算不足而提前 chunk。

4. **缺少运行时观测**
   - 增加 context / memory / retrieve / get_context 等指标。

P0 完成后的意义是：

- 系统不再容易在短中程下快速因 context 问题失败；
- 后续问题分析具备了明确数据支撑。

## 8.2 P1 前半段已解决的问题

P1 当前已解决：

1. **tool-call cleanup 异常膨胀**
   - 修复 tool cleanup 重复追加历史的问题；
   - 修复 assistant function placeholder 残留问题。

2. **assistant `<think>` 污染 memory**
   - assistant `<think>` 在写入 memory 前被清理；
   - 真实 Ollama / Qwen 验证已确认该策略有效。

修复后的结果是：

- `tool/function/assistant_fn` 不再异常增长；
- memory 增长已经从异常膨胀恢复为正常线性积累；
- context token 消耗明显下降。

---

## 9. 当前仍未解决的问题

当前剩余的核心问题已经很明确：

**正常的 user / assistant 历史轮次线性积累。**

这意味着：

- 系统已经不会像之前一样很快失控；
- 但随着步数增加，短期 chat history 仍然持续变长；
- 当 token 预算被填满时，CAMEL 的 `ScoreBasedContextCreator` 会开始丢弃较旧历史；
- 系统虽然还能继续运行，但长期行为连续性会下降。

因此当前状态可以概括为：

- 异常增长已被控制；
- “长模拟不容易立刻中断”这一最低要求已经接近满足；
- 但“长期模拟意义上的基本跑通”尚未完成；
- P1 的后半段仍需处理线性积累问题。

---

## 10. 当前保真度边界

## 10.1 当前保真度目标

当前方案追求的是：

- **实体级保真**优先；
- 不追求逐字逐句的全文保真。

### 10.1.1 当前可以接受的压缩

当前可接受的压缩包括：

- pretty JSON 改为紧凑 JSON；
- 长文本截断；
- 极长文本占位符替换；
- assistant `<think>` 清理；
- tool bookkeeping 去噪。

### 10.1.2 不能默认视为弱相关的信息

以下内容不能被系统级默认视为弱相关：

- posts；
- comments；
- user relations；
- search results；
- trend results；
- group interaction state；
- 任何未来可能成为动作目标的 observation 元素。

### 10.1.3 当前 comments/groups 摘要策略的正确定位

必须明确：

- 当前对 comments/groups 的摘要，只是当前 dashboard 接入层为了跑通和展示而做的局部策略；
- 它不能被上升为整个 Oasis memory 优化的默认原则；
- 后续系统级方案必须以 Oasis 完整动作空间与平台能力模型为准。

---

## 11. 环境变量与运行配置指南

当前实现把模型运行时配置显式化了。这是因为 memory 控制现在依赖于：

- 明确的模型服务地址；
- 明确的上下文窗口；
- 明确的短期 memory context budget；
- 明确的生成长度预算。

## 11.1 关键环境变量

当前最重要的环境变量包括：

| 变量名 | 作用 | 当前建议 |
|--------|------|----------|
| `OASIS_MODEL_URL` | 模型服务地址 | 本地 Ollama 场景建议显式设置 |
| `OASIS_MODEL_CONTEXT_WINDOW` | 声明模型上下文窗口 | 建议显式设置 |
| `OASIS_CONTEXT_TOKEN_LIMIT` | 短期 memory / context 预算 | 建议显式设置 |
| `OASIS_MODEL_GENERATION_MAX_TOKENS` | 单次输出预算 | 建议显式设置 |
| `OASIS_CONTEXT_WINDOW_SIZE` | 可选硬滑窗 | 默认不启用 |

### 11.1.1 为什么 `OASIS_MODEL_URL` 尤其重要

当前本地 Ollama 路径中，如果不显式设置 URL，底层 CAMEL 可能触发不稳定的本地启动与 fallback 逻辑。

这会导致：

- 模型请求未正确打到本地 Ollama；
- 甚至错误回退到 OpenAI 兼容端点；
- 进而出现认证错误。

因此当前本地开发建议将 `OASIS_MODEL_URL` 视为最关键配置。

## 11.2 本地 Ollama 推荐启动方式

### 11.2.1 启动 Ollama 模型

```bash
ollama run qwen3:8b
```

### 11.2.2 启动 dashboard 前设置环境变量

```bash
export OASIS_MODEL_URL=http://127.0.0.1:11434/v1
export OASIS_MODEL_CONTEXT_WINDOW=8192
export OASIS_CONTEXT_TOKEN_LIMIT=6144
export OASIS_MODEL_GENERATION_MAX_TOKENS=256
```

### 11.2.3 启动前后端服务

```bash
pnpm dev
```

---

## 12. 验证与测试指南

## 12.1 静态验证

建议至少执行：

```bash
.venv/bin/python -m py_compile oasis_dashboard/context/*.py oasis_dashboard/real_oasis_engine_v3.py oasis_dashboard/context_smoke.py tests/test_context_integration.py
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
pnpm lint
```

预期结果：

- Python 语法检查通过；
- Python 测试通过；
- TypeScript 类型检查通过。

## 12.2 CLI Smoke Test

当前项目提供了专门的 smoke runner：

- [context_smoke.py](/home/grayg/oasis-dashboard/oasis_dashboard/context_smoke.py)

### 12.2.1 运行示例

```bash
.venv/bin/python -m oasis_dashboard.context_smoke \
  --model-platform ollama \
  --model-type qwen3:8b \
  --agent-count 1 \
  --steps 5 \
  --platform reddit \
  --topic AI
```

### 12.2.2 结果解读

输出中重点关注：

- `context_avg`
- `context_max`
- `memory_avg`
- `retrieve_avg_ms`
- `user`
- `assistant`
- `assistant_fn`
- `function`
- `tool`

当前阶段的理想现象是：

- `assistant_fn/function/tool` 基本保持为 `0`；
- `memory_avg` 线性增长，而不是异常跳涨；
- `context_avg` 增长但不会很快导致系统报错。

## 12.3 Dashboard 联调验证

### 12.3.1 启动方式

```bash
pnpm dev
```

### 12.3.2 最小联调流程

建议验证顺序：

1. 打开 `http://localhost:3000`
2. 选择：
   - 平台：`REDDIT`
   - Agent 数：`1`
   - Topic：`AI`
3. 初始化模拟
4. 连续执行 `3 ~ 5` 次 step

### 12.3.3 观察点

检查以下现象：

- 页面是否报错或白屏；
- step 是否正常完成；
- Python 后端终端是否出现 traceback；
- 日志是否显示模型请求正常；
- 系统是否不像之前那样很快因 context 问题失败。

---

## 13. 后续演进方向

## 13.1 为什么不能继续单纯压 raw observation

继续依赖“删 section / 删细节”来换取空间，会越来越难满足系统级保真要求。

原因是：

- 当前 dashboard 只是最小接入层；
- Oasis 完整系统动作远比当前开放的动作更多；
- 未来 comments/groups/follows/search results/trend 等都可能成为关键决策对象。

因此，P1 后半段不应继续沿着“当前动作集下可以删谁”的方向推进。

## 13.2 更合理的下一步

当前更合理的路线是：

- 保留最近若干原始 short-term turns；
- 将更早的 `observation + action/result` 压缩为 episode / event 级记录；
- 让旧历史从“原始会话”转换为“结构化事件”；
- 后续再将这些事件记录接入长期记忆。

## 13.3 为什么不直接原样采用 `LongtermAgentMemory`

CAMEL 的 `LongtermAgentMemory` 可以作为参考，但不适合作为当前项目的直接落地方案。

原因是：

- 它默认会受到“最后一条 user message”影响；
- 而在 Oasis 中，这通常就是 observation prompt；
- 原始 observation prompt 不是理想的长期记忆检索单元。

更合适的长期记忆单元应该是：

- 事件摘要；
- 回合摘要；
- 状态变化摘要。

## 13.4 `window_size` 的角色

`window_size` 当前仍然保留，但它只是：

- 显式 emergency 开关；
- 不是正式长期方案。

只有在以下条件下，它才会成为合理组成部分：

- 旧历史已经被压缩；
- 或旧历史已经被迁移到长期记忆层。

否则它只是“更快忘掉旧历史”，不能单独解决长期模拟问题。

---

## 14. 当前结论

当前 memory 优化架构已经达到如下状态：

- P0 已基本完成；
- P1 前半段已完成；
- 当前主问题已经不再是异常膨胀；
- 当前剩余瓶颈是正常线性历史积累；
- 后续最合理的方向是 episode / event compaction，再进一步演进到长期记忆。

这就是当前版本的正式技术基线。

