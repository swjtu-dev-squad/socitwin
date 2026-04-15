# Memory Migration Architecture Comparison

- Status: active
- Audience: migration implementers, reviewers, AI tools
- Role: compare old `oasis-dashboard` memory system with current `socitwin` architecture

## 1. Repositories Compared

### Old repo

- Path: `/home/grayg/oasis-dashboard`
- Main memory docs:
  - `docs/memory/current-architecture.md`
  - `docs/memory/v1-principles-and-modes.md`
  - `docs/memory/config-surfaces.md`
  - `docs/memory/system-test-plan.md`
- Main memory code:
  - `oasis_dashboard/real_oasis_engine_v3.py`
  - `oasis_dashboard/context/*.py`
  - `oasis_dashboard/memory_evaluation_harness.py`
  - `tests/test_*`

### New repo

- Path: `/home/grayg/socitwin`
- Main backend code:
  - `backend/main.py`
  - `backend/app/api/*.py`
  - `backend/app/services/*.py`
  - `backend/app/core/oasis_manager.py`
- Current tests:
  - `backend/tests/e2e/e2e_simulation_test.py`
  - `backend/tests/e2e/run_tests.sh`

## 2. Old Repo Runtime Facts

旧仓库的记忆系统已经形成完整的运行主链：

- `real_oasis_engine_v3.py`
  - 负责模式选择、共享模型 runtime、上下文窗口解析、long-term backend 装配。
- `context/agent.py`
  - 负责三模式 agent 接线。
- `context/environment.py`
  - 负责 `action_v1` 的 observation 获取与发布。
- `context/observation_shaper.py`
  - 负责 observation guard、long-text cap、interaction shrink、physical fallback。
- `context/action_evidence.py`
  - 负责动作证据构造。
- `context/working_memory.py`
  - 负责 recent / compressed 结构。
- `context/consolidator.py`
  - 负责 recent -> compressed 演化。
- `context/prompt_assembler.py`
  - 负责 observation / recent / compressed / recall 的统一 prompt 裁决。
- `context/episodic_memory.py` + `context/longterm.py`
  - 负责 `ActionEpisode` 和长期层。
- `context/recall_planner.py` + `context/retrieval_policy.py`
  - 负责 recall gate、检索、排序和 suppression。
- `memory_evaluation_harness.py`
  - 负责系统级评测。

### 2.1 Old repo mode wiring

旧仓库三模式从引擎层就开始分线：

- `upstream`
  - 原生 `SocialAgent`
- `baseline`
  - `BaselineSocialAgent`
  - bounded chat history + 必要运行时修复
- `action_v1`
  - `ContextSocialAgent`
  - 注入 runtime settings、memory state、assembler、consolidator、recall planner、long-term store

这意味着旧仓库迁出的核心资产不是某一个 long-term 模块，而是：

- 引擎层 runtime 解析
- agent 层 wiring
- memory 主链模块
- 系统级测试与文档

## 3. Current Socitwin Runtime Facts

新仓库当前仍是更接近原生 OASIS 的服务层结构：

- `backend/app/api/simulation.py`
  - 提供 REST 控制接口。
- `backend/app/services/simulation_service.py`
  - 构造 `LLMAction()` / `ManualAction()`；
  - step 后更新数据库派生统计和现有指标。
- `backend/app/core/oasis_manager.py`
  - 负责模型创建、agent graph 创建、`oasis.make(...)`、`env.step(...)`、状态机。
- `backend/app/services/topic_service.py`
  - 负责主题激活、初始贴文与 refresh。

### 3.1 Current model creation semantics

当前新仓库的模型创建主要发生在：

- [`backend/app/core/oasis_manager.py`](/home/grayg/socitwin/backend/app/core/oasis_manager.py)

实际链路是：

- `SimulationConfig.llm_config`
- `ModelConfig.max_tokens`
- `ChatGPTConfig(max_tokens=...)`
- `ModelFactory.create(...)`

当前问题是：

- 这里只有“单次生成输出上限”语义；
- 还没有旧仓库那种显式的：
  - context token limit
  - token counter mode
  - generation reserve
  - provider overflow matcher

也就是说，新仓库当前还没有建立“上下文预算”和“生成长度”这两件事的分层语义。

### 3.2 Current topic activation chain

新仓库的主题激活不是静态配置行为，而是直接进入运行主链：

- [`backend/app/services/topic_service.py`](/home/grayg/socitwin/backend/app/services/topic_service.py)

它会主动执行：

- `CREATE_POST`
- 全员 `REFRESH`

这意味着主题激活会直接影响：

- 初始 observation
- agent 第一步可见环境
- 后续 action_v1 的 episode 写入

因此迁移时不能只盯 `step(auto)` 主链，也必须把 topic activation 视为 memory ingestion 的前置入口。

### 3.3 Current status / monitor chain

新仓库当前的状态输出主要在：

- [`backend/app/services/simulation_service.py`](/home/grayg/socitwin/backend/app/services/simulation_service.py)

当前 `get_status()` 主要返回：

- 模拟状态
- agent 基础画像
- 数据库派生统计
- metrics summary

但在迁移早期它还没有：

- memory runtime snapshot
- recall / retrieval trace
- prompt / context token status

这意味着如果迁移只恢复运行，不同时恢复最小 memory status 出口，后续测试和前端调试都会缺观测面。

当前迁移方向已经进一步确定为：

- `/api/sim/status`
  - 继续保留为模拟总状态接口；
- memory trace / recall / budget / debug snapshot
  - 走单独 monitor/debug 接口。

### 3.4 Current missing layers

当前新仓库仍未完全恢复旧记忆系统中的这些层：

- 旧仓库 `context/llm.py` 对应的更完整模型 runtime 包装
- 更稳定的真实 provider 级 comparison 长跑验证

而下面这些层已经开始恢复，不再应被视为“完全缺失”：

- memory mode
- mode-aware runtime facade
- observation shaping
- prompt-visible snapshot
- short-term working memory
- prompt assembler
- long-term persistence / recall
- budget recovery
- memory debug snapshot
- `/api/sim/memory` monitor/debug 接口
- memory evaluation harness

此外还有一个容易混淆的缺口：

- 前端已经有 memory / retrieval 占位类型；
- 但后端当前没有真实对口结构；
- 所以前端不是当前阻塞项，但后端 monitor/debug 设计不能把未来 memory 暴露路径堵死。

### 3.5 Current step chain

当前新仓库自动 step 主链基本是：

- API
- `SimulationService._build_actions()`
- `LLMAction()`
- `OASISManager.step()`
- `env.step(actions)`

对 `upstream` 而言，这条链仍主要沿用原生 OASIS + CAMEL 默认路径。

对 `action_v1` 而言，当前已经有专门一层接管：

- observation shaping
- prompt-visible snapshot
- prompt assembly
- episodic write
- recall preparation / injection
- memory debug snapshot

因此当前真正需要继续迁或继续收口的，不再是“有没有 memory runtime”，而是：

- `file` source 已切入 `action_v1` 自建 parser / builder，但仍只完成 parser / builder 单测级验证；
- 旧配置兼容面已经补到 runtime settings 层，但 provider overflow / budget reserve 语义没有借迁移重开；
- comparison 的真实 provider 级运行与分析口径还没完全收口。

## 4. Core Gap

两边的本质差异不是“功能数量不同”，而是控制层级不同。

旧仓库：

- 已经把上下文组装与记忆控制从默认 chat history 中拿出来。

新仓库：

- `upstream` 仍主要交给原生 OASIS + CAMEL 默认路径；
- `action_v1` 已重新建立独立 memory runtime，但还存在少量未迁移边界与配置缺口。

因此当前阶段的核心问题已经从“要不要建立 memory runtime”变成了：

- 还有哪些旧 contract 没有迁完整；
- 哪些验证链已经恢复、哪些还只是较重的按需验证；
- 哪些质量问题应留到迁移后单独审查。

## 5. Insertion Point Assessment

### 5.1 Not the API layer

- `backend/app/api/simulation.py`
  - 只适合做 HTTP 封装；
  - 不适合直接承载记忆运行主链。

### 5.2 Not only the service layer

- `backend/app/services/simulation_service.py`
  - 可以承载 mode-aware orchestration、状态输出、测试 hook；
  - 但它不负责 agent 构造，也不掌握 observation / prompt 细节；
  - 不是最深插入点。

### 5.3 Primary insertion point: OASISManager

- `backend/app/core/oasis_manager.py`
  - 当前负责：
    - model 构造
    - agent graph 构造
    - env 初始化
    - step 执行
  - 它最接近旧仓库 `real_oasis_engine_v3.py` 的职责位置；
  - 因此应作为新 memory runtime 的第一层接入点。

### 5.4 Recommended target shape

当前推荐形态：

- `core/oasis_manager.py`
  - 作为接入中心；
  - 调用 mode-aware memory runtime。
- `memory/*`
  - 承载 observation / working memory / long-term / recall 等主链模块。
- `services/simulation_service.py`
  - 负责把 memory-aware 状态和结果组织给外层。

## 6. Config Surface Gap

旧仓库已有完整 memory 配置面：

- `OASIS_MEMORY_MODE`
- `OASIS_MODEL_*`
- `OASIS_CONTEXT_TOKEN_LIMIT`
- `OASIS_LONGTERM_*`
- `OASIS_V1_OBS_*`
- `OASIS_V1_RECALL_*`
- `OASIS_V1_SUMMARY_*`
- `OASIS_V1_PROVIDER_*`

迁移早期的新仓库确实只有较轻的一层：

- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OASIS_DEFAULT_MODEL`
- `OASIS_DEFAULT_PLATFORM`
- metrics 相关配置

当前迁移后的状态已经进一步推进到：

- `backend/app/core/config.py` 已显式承载：
  - `OASIS_MEMORY_MODE`
  - `OASIS_CONTEXT_TOKEN_LIMIT`
  - `OASIS_LONGTERM_*`
- `backend/app/memory/config.py` 已显式承载：
  - observation preset
  - summary preset
  - working-memory budget
  - recall preset
  - provider runtime preset

但旧仓库的完整 env 兼容面还没有全部接回：

- `OASIS_V1_OBS_*` 与 working-memory 关键 budget env 已兼容；
- `OASIS_V1_RECALL_*` / `OASIS_V1_SUMMARY_*` / `OASIS_V1_PROVIDER_*` 现在也已接入 `action_v1` runtime settings；
- 但这轮恢复的是配置承载层，不代表旧仓库预算与 provider overflow 语义整套照搬回来了。

并且 `SimulationConfig.llm_config.max_tokens` 在实际语义上更接近：

- generation max tokens

而不是：

- context window limit

这个差异如果不在迁移时明确，会导致后续把旧仓库的预算树错误挂到当前的 `ModelConfig.max_tokens` 上。

这意味着新仓库迁移时需要新增一整层 memory-aware config surface，而不是做零散补丁。

## 7. Test Surface Gap

旧仓库已有三层测试资产：

- 单测
  - observation / prompt assembly / consolidator / recall / runtime failures
- 集成测
  - context integration / metrics integration
- 系统级评测
  - memory evaluation harness

迁移早期的新仓库主要只有 API 级 E2E：

- `backend/tests/e2e/e2e_simulation_test.py`
- `backend/tests/e2e/run_tests.sh`

其特点是：

- 更偏 API smoke；
- 会配置模拟、激活 topic、跑若干 step；
- 但没有 memory-aware assertions；
- 也没有独立的 module/integration/evaluation 分层。

当前迁移后的状态已经推进到：

- `backend/tests/memory/unit/`
- `backend/tests/memory/integration/`
- `backend/tests/memory/evaluation/`

也就是说，memory-aware 的 unit / integration / evaluation 分层已经恢复。

当前真正剩下的测试缺口主要是：

- `comparison` 的真实 provider 级稳定长跑验证；
- 更完整的配置兼容面回归测试。
