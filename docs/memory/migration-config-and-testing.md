# Memory Migration Config And Testing

- Status: active
- Audience: migration implementers, reviewers, AI tools
- Role: define config migration, test migration, and validation order

## 1. Config Migration Principle

当前推荐策略已经确定为：

- 第一阶段采用兼容层；
- 不在主链恢复前强行全面改名。

原因很直接：

- 旧仓库的文档、测试、运行经验都绑定在 `OASIS_*` / `OASIS_V1_*` 这一套命名上；
- 如果迁移第一步就全面换名，只会引入大量纯命名噪音；
- 当前更重要的是先把两模式主链恢复起来。

## 2. Current Config Gap

### 2.1 Old repo config families

旧仓库实际依赖的 memory 配置面包括：

- `OASIS_MEMORY_MODE`
- `OASIS_MODEL_*`
- `OASIS_CONTEXT_TOKEN_LIMIT`
- `OASIS_LONGTERM_*`
- `OASIS_V1_OBS_*`
- `OASIS_V1_RECALL_*`
- `OASIS_V1_SUMMARY_*`
- `OASIS_V1_PROVIDER_*`

### 2.2 New repo config families

新仓库当前 `Settings` 只覆盖了较轻的一层：

- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OASIS_DEFAULT_MODEL`
- `OASIS_DEFAULT_PLATFORM`
- metrics / simulation 基础配置

缺口在于：

- 没有 memory mode
- 没有 context window / budget / reserve
- 没有 long-term backend / embedding 配置
- 没有 recall / summary / observation preset
- 没有 provider failure matcher / recovery config

截至当前迁移进度，这个缺口已经部分收口：

- 已接入：
  - `OASIS_MEMORY_MODE`
  - `OASIS_CONTEXT_TOKEN_LIMIT`
  - `OASIS_LONGTERM_*` 的最小正式落点
  - `OASIS_V1_OBS_*`
  - `OASIS_V1_RECENT_* / COMPRESSED_* / RECALL_BUDGET_RATIO / GENERATION_RESERVE_TOKENS`
- 仍未完整接入：
  - `OASIS_V1_RECALL_*` 其余细项
  - `OASIS_V1_SUMMARY_*`
  - `OASIS_V1_PROVIDER_*` 的旧仓库完整兼容面

这意味着当前新仓库已经具备让 `action_v1` 跑起来的最小配置面，但还没有把旧仓库全部调参表面一次性恢复。

另一个必须明确的事实是：

- 新仓库当前 `ModelConfig.max_tokens`
  - 实际更接近“生成输出上限”
- 旧仓库 `OASIS_CONTEXT_TOKEN_LIMIT`
  - 才是上下文预算语义

这两者迁移时不能混用。

## 3. Recommended Config Landing

### 3.1 Keep existing app settings as the outer shell

新仓库当前的：

- [`backend/app/core/config.py`](/home/grayg/socitwin/backend/app/core/config.py)

仍然作为统一 env 入口。

### 3.2 Add memory compatibility mapping

建议新增：

- `backend/app/memory/config.py`

承担两层职责：

1. 定义 memory runtime settings / preset dataclass；
2. 把旧仓库 env 命名映射进新仓库内部 config。

推荐形态：

- `app.core.config.Settings`
  - 只负责原始 env 读取
- `app.memory.config`
  - 负责兼容解析、默认值、preset 归一

### 3.3 Config migration order

建议按下面顺序接入：

1. `OASIS_MEMORY_MODE`
2. `OASIS_MODEL_*` + `OASIS_CONTEXT_TOKEN_LIMIT`
3. `OASIS_LONGTERM_*`
4. `OASIS_V1_OBS_*`
5. `OASIS_V1_RECALL_*`
6. `OASIS_V1_SUMMARY_*`
7. `OASIS_V1_PROVIDER_*`

当前实际状态是：

- 前 4 类已开始落地
- 第 5~7 类仍应继续按“先需要、再补齐”的顺序推进

原因：

- 前三类决定模式能否跑；
- 中三类决定 `action_v1` 质量；
- 最后一类决定异常与恢复是否可诊断。

此外，`SimulationConfig` 也需要补一层 mode-aware 配置承载，否则：

- `upstream`
- `action_v1`

无法在新仓库 API -> service -> manager 链路中显式分流。

## 4. Testing Migration Principle

测试不是迁完代码再补，而是迁移对象本身的一部分。

当前建议是：

- 先恢复“必须保住的验证能力”；
- 再决定旧测试是直接迁，还是保留语义后重写。

## 5. Test Surface Mapping

### 5.1 New repo current test starting point

新仓库当前主要的 API / E2E 脚本是：

- [`backend/tests/e2e/e2e_simulation_test.py`](/home/grayg/socitwin/backend/tests/e2e/e2e_simulation_test.py)

它更偏：

- API 层
- 端到端基本运行

它还不是 memory-aware test surface。

并且它已经把：

- 配置模拟
- 激活 topic
- 执行 step

串成了一个完整 API smoke，所以后续 memory-aware 测试不应该推翻这条链，而应在它之上补更细的验证层。

### 5.2 Old repo tests to preserve

#### A. First migrate as module tests

这些应尽量优先恢复：

- `test_observation_shaper.py`
- `test_prompt_assembler.py`
- `test_consolidator.py`
- `test_recall_planner.py`
- `test_runtime_failures.py`

原因：

- 模块边界清晰；
- 和新仓库目录重组兼容性高；
- 能最快为 `action_v1` 主链提供回归保护。

#### B. Migrate after runtime skeleton exists

- `test_context_integration.py`
- `test_memory_evaluation_harness.py`

这两类依赖整体 runtime 入口，必须等：

- `memory/runtime.py`
- `memory/agent.py`
- `OASISManager` 的 mode-aware 接线

先存在，才能迁。

截至当前迁移进度，manager 级 smoke 已经开始恢复，当前已覆盖：

- `action_v1` 在 `manual` source 下的 `initialize()`
- `action_v1` 在 `manual` source 下的 `step()` 假环境 smoke
- `action_v1` 在 `template` source 下的 `initialize()` smoke
- `action_v1` 在 `file` source 下的显式拒绝

这意味着现在已经不只是模块单测通过，而是：

- `SimulationConfig -> OASISManager -> MemoryRuntimeFacade -> agent/env` 这条新仓库主链已开始有回归保护

但要注意，当前仍然只是非联网 smoke，不是完整真实 provider / OASIS runtime 集成验证。

#### C. Keep validation target, postpone code port

- 旧引擎壳专用 demo / legacy tests

这类测试先保留“要验证什么”，不急着复制旧代码。

## 6. Validation Order

迁移实施时，验证顺序建议固定为：

1. `upstream` mode 能初始化、能 step、行为不被 memory 路径污染；
2. `action_v1` mode 能初始化、能 step；
3. observation shaping 与 prompt assembly 的关键单测恢复；
4. short-term recent / compressed 演化单测恢复；
5. long-term write / retrieve / recall gate 单测恢复；
6. action_v1 integration 跑通；
7. system evaluation harness 重新接回。

当前实际进度已推进到：

- 1~5 已有基础覆盖
- 6 正在从 manager-level smoke 往更真实的 integration 推进
- 7 已开始迁回最小 harness 脚手架，当前覆盖 `preflight + deterministic + real-smoke + 最小 real-scenarios`

这个顺序不能反过来。尤其不能在：

- runtime skeleton 还没稳；
- `upstream` 还没显式隔离；

的前提下就急着接 recall 和大规模评测。

### 6.1 Current evaluation harness baseline

截至当前迁移进度，新仓库已经有第一版评测入口：

- 模块：
  - `backend/app/memory/evaluation_harness.py`
- 测试：
  - `backend/tests/memory/evaluation/test_memory_evaluation_harness.py`

它当前已恢复：

- `preflight`
- `deterministic`
- `real-smoke`
- `real-scenarios`
- `real-longwindow`

并且已经具备这些最小能力：

- 写出 `config.json`
- 写出 `events.jsonl`
- 写出 `summary.json`
- 写出 `README.md`
- 跑通一个最小 deterministic observation fidelity probe
- 跑通一个最小 deterministic recall trigger probe
- 跑通一个最小 `action_v1` 真实初始化/step smoke 入口
- 对 OpenAI-compatible embedding 服务做 preflight 探测

当前已验证的最新状态：

- `real-smoke` 已在新仓库中实际跑通 1-agent / 1-step 的 `action_v1` 主链；
- 真实 smoke 过程中暴露出的 `RedditMemoryAdapter.format_action_fact` 迁移缺口已修复，并补了独立单测；
- OpenAI-compatible embedding preflight 仍然依赖当前环境是否能从 WSL 访问到对应服务地址，不能把它和 heuristic-backed real-smoke 的可运行性混为一谈。

当前不能把它误读成“旧仓库 harness 已完整迁回”。当前 `real-scenarios` 已恢复：

- `VAL-LTM-05 real_self_action_retrievability`
- `VAL-RCL-08 real_continuity_recall_probe`
- `VAL-RCL-09 real_empty_observation_recall_suppression`

并且 `real-longwindow` 已恢复：

- `VAL-RCL-10 real_longwindow_recall_injection`

但 `comparison` 仍需后续迁入。

当前已验证的最新结果：

- `embedding preflight` 已可通过本地 Ollama `http://127.0.0.1:11434/v1` 跑通，`nomic-embed-text:latest` 的 `embedding_dim=768`；
- `real-scenarios` 现在已可跑通 2-agent / 3-step 的 `action_v1 + Chroma + OpenAI-compatible embedding`；
- 当前新仓库最新一轮真实场景结果：
  - `VAL-LTM-05`: `pass`
    - `hit_at_1=1.0`
    - `hit_at_3=1.0`
    - `recall_at_3=1.0`
    - `mrr=1.0`
    - `cross_agent_top3_count=0`
    - `actual_persisted_action_episode_count=2`
  - `VAL-RCL-08`: `pass`
  - `VAL-RCL-09`: `pass`
- `real-longwindow` 当前已恢复为基于 `memory debug snapshot` 的真实长窗口注入验证：
  - 自动汇总 `recall_injected_count`
  - 自动汇总 `recall_injected_trace_count`
  - 自动汇总 `recall_recalled_not_injected_trace_count`
  - 自动汇总 `used_recall_step_ids`
  - 自动汇总 `avg_prompt_tokens / max_prompt_tokens`
  - 自动汇总 `shortterm recent/compressed` 保留指标
- 当前新仓库首轮真实长窗口结果：
  - `VAL-RCL-10`: `fail`
  - `actual_persisted_action_episode_count=5`
  - `recall_gate_true_count=10`
  - `recall_recalled_trace_count=9`
  - `recall_injected_count=0`
  - `recall_injected_trace_count=0`
  - 这说明 `real-longwindow` phase 已恢复并能稳定暴露问题，但当前 action_v1 在新仓库里仍存在“召回命中但未注入”的运行现状。

## 7. Frontend And Status Notes

前端不是第一阶段阻塞项，但测试与状态面需要保留最小可扩展性。

当前建议：

- 第一阶段只恢复后端 memory trace 的结构化输出；
- 主要通过单独的 monitor/debug 接口暴露；
- 不把大块 memory 内部状态继续堆进 `SimulationStatus`；
- 不要求立刻完成前端展示；
- 但不要把状态结构设计成未来难以暴露 memory snapshot / retrieval trace。

### 7.1 Recommended first monitor/debug payload

第一版 monitor/debug 接口不追求完整，只要求足够支撑：

- runtime 排查
- memory 主链验证
- harness 读取

当前建议最小响应结构至少包含：

- simulation scope
  - `current_step`
  - `memory_mode`
  - `platform`
- runtime summary
  - `active_runtime`
  - `context_token_limit` if available
  - `generation_max_tokens` if available
- per-agent memory summary
  - `agent_id`
  - `recent_retained_step_count`
  - `compressed_retained_step_count`
  - `last_observation_stage`
  - `last_recall_gate`
  - `last_recalled_count`
  - `last_injected_count`
  - `last_runtime_failure_category`

截至当前迁移进度，这个最小 monitor/debug 接口已经以：

- `/api/sim/memory`

的形式落地到了新仓库后端，并保持与 `/api/sim/status` 分离。

同时已经补了第一条 API integration 覆盖：

- `backend/tests/memory/integration/test_memory_debug_api.py`

当前实际响应已经覆盖：

- simulation scope
  - `state`
  - `memory_mode`
  - `current_step`
  - `total_steps`
  - `platform`
- runtime summary
  - `context_token_limit`
  - `generation_max_tokens`
  - `longterm_enabled`
- per-agent memory summary
  - `recent_retained_step_count`
  - `recent_retained_step_ids`
  - `compressed_action_block_count`
  - `compressed_heartbeat_count`
  - `compressed_retained_step_count`
  - `total_retained_step_count`
  - `last_observation_stage`
  - `last_observation_prompt_tokens`
  - `last_prompt_tokens`
  - `last_recall_gate`
  - `last_recalled_count`
  - `last_injected_count`
  - `last_runtime_failure_category`
  - `last_runtime_failure_stage`
  - `last_prompt_budget_status`

第一阶段不要求暴露：

- 完整 prompt 文本
- 完整 recent/compressed 内容
- 完整 recall 文本内容

这些可以留给更后面的 debug 深化接口。

## 8. Immediate Next Checks

下一轮还需要继续核对并补进计划的内容：

1. topic activation 相关路径在 action_v1 下是否需要额外 trace / memory ingestion hook；
2. monitor/debug 接口是否需要第二层更细的 per-agent drill-down 输出。

当前已经按下面方向收口：

- `backend/tests/e2e/`
  - 保留 API / E2E smoke 脚本
- `backend/tests/memory/`
  - 承载 unit / integration / evaluation 分层测试
