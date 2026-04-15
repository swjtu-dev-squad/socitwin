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

迁移早期的新仓库 `Settings` 只覆盖了较轻的一层：

- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OASIS_DEFAULT_MODEL`
- `OASIS_DEFAULT_PLATFORM`
- metrics / simulation 基础配置

当时缺口在于：

- 没有 memory mode
- 没有 context window / budget / reserve
- 没有 long-term backend / embedding 配置
- 没有 recall / summary / observation preset
- 没有 provider failure matcher / recovery config

截至当前迁移进度，这个缺口已经基本收口到 runtime settings 层：

- 已接入：
  - `OASIS_MEMORY_MODE`
  - `OASIS_CONTEXT_TOKEN_LIMIT`
  - `OASIS_LONGTERM_*` 的最小正式落点
  - `OASIS_V1_OBS_*`
  - `OASIS_V1_RECENT_* / COMPRESSED_* / RECALL_BUDGET_RATIO / GENERATION_RESERVE_TOKENS`
  - `OASIS_V1_RECALL_*`
  - `OASIS_V1_SUMMARY_*`
  - `OASIS_V1_PROVIDER_*`

当前更准确的表述应是：

- 旧仓库这三类 preset env 已经进入新仓库 `action_v1` runtime settings；
- `OASISManager._build_action_v1_runtime_settings()` 已真实吃到：
  - recall preset overrides
  - summary preset overrides
  - provider runtime preset overrides
- 但这不等于“旧仓库预算/overflow 语义整套回滚”；
  - 本轮恢复的是配置承载与接线；
  - 没有借迁移重新打开 budget tree / reserve policy / recall algorithm 设计。

这意味着当前新仓库已经具备让 `action_v1` 跑起来的主要配置面。
剩余重点不是“env 名称有没有落点”，而是后续是否需要恢复旧仓库 `context/llm.py` 那种更统一的模型 runtime 包装，以及是否要做更多真实 env 组合回归。

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

- 第 1~7 类已经都有新仓库落点；
- 第 5~7 类已经进入 `action_v1` runtime settings；
- 但 provider overflow / budget reserve 相关配置当前只恢复“配置承载与接线”，不等于把旧仓库预算语义整套重开或回滚。

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

- `test_budget_recovery.py`
- `test_observation_policy.py`
- `test_observation_semantics.py`
- `test_observation_shaper.py`
- `test_prompt_assembler.py`
- `test_consolidator.py`
- `test_retrieval_policy.py`
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
- `action_v1` 在 `file` source 下的 parser / builder 验证
- 旧仓库关键模块 contract 的新仓库单测覆盖：
  - `budget_recovery`
  - `observation_policy`
  - `observation_semantics`
  - `observation_shaper`
  - `prompt_assembler`
  - `consolidator`
  - `retrieval_policy`
  - `recall_planner`
  - `runtime_failures`

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
- 6 已从 manager-level smoke 推进到真实 `action_v1` integration / debug / evaluation 验证
- 7 已恢复：
  - `preflight`
  - `deterministic`
  - `real-smoke`
  - `real-scenarios`
  - `real-longwindow`
  - `comparison`（两模式代码/单测层）

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

并且两模式 `comparison` phase 已恢复到代码与单测层：

- 事件：
  - `upstream_short_comparison`
  - `action_v1_short_comparison`
- 指标口径：
  - `upstream` 侧重点是 chat-history 压力与 token-selection 诊断；
  - `action_v1` 侧重点是 short-term / long-term / recall 注入诊断。

当前还不能把 `comparison` 解读成“已稳定完成真实 provider 长跑验证”：

- 两模式 comparison 的 phase、parser、summary 和指标汇总已迁回；
- `action_v1` comparison 现在会先复用 embedding preflight；
  - 如果 embedding 服务不可达或 preflight 失败，应直接记为 `blocked`，而不是晚到真实长跑阶段再暴露环境问题；
- 但真实 provider 级 comparison 运行仍明显比 `real-scenarios` / `real-longwindow` 更重；
- 因此它当前更适合作为按需运行的较重 phase，而不是迁移阶段的默认高频验证入口。

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
  - 自动汇总 `recall_overlap_filtered_count`
  - 自动汇总 `recall_selection_stop_reason_counts`
  - 自动汇总 `used_recall_step_ids`
  - 自动汇总 `avg_prompt_tokens / max_prompt_tokens`
  - 自动汇总 `shortterm recent/compressed` 保留指标
- 当前新仓库已经得到两轮真实长窗口结果：
  - 8-step:
    - `VAL-RCL-10`: `fail`
    - `actual_persisted_action_episode_count=5`
    - `recall_gate_true_count=10`
    - `recall_recalled_trace_count=9`
    - `recall_injected_count=0`
    - `recall_injected_trace_count=0`
    - 结论：短窗口下主要是“已召回但未注入”。
  - 16-step:
    - `VAL-RCL-10`: `pass`
    - `actual_persisted_action_episode_count=25`
    - `recall_gate_true_count=21`
    - `recall_recalled_trace_count=21`
    - `recall_recalled_not_injected_trace_count=18`
    - `recall_injected_count=5`
    - `recall_injected_trace_count=3`
    - `recall_overlap_filtered_count=52`
    - `recall_selection_stop_reason_counts={"all_candidates_filtered_by_overlap": 18}`
    - 结论：预算本身不是首要瓶颈；在较长窗口下 recall 已开始真实注入，但大量候选仍被 overlap 过滤。

## 6.2 Recorded But Deferred Runtime Issue

当前已记录但暂不在迁移阶段继续深挖的问题：

- 长窗口 recall 在新仓库里已经确认不是“完全无法注入”；
- 当前更典型的运行现象是：
  - 短窗口下 recalled 已出现，但大量候选没有进入 injected；
  - 更长窗口下 injected 已出现，但 `all_candidates_filtered_by_overlap` 仍然大量存在。

这意味着当前问题应先理解为：

- 不是总 prompt 预算先撞墙；
- 更像是 short-term / overlap suppression 在当前参数下较强；
- 属于 `action_v1` 质量调优问题，而不是迁移主链未恢复的问题。

本轮迁移阶段对它的处理边界固定为：

- 先记录现象与指标；
- 保留当前 harness 诊断能力；
- 暂不在迁移阶段展开 recall overlap 策略调参或语义重构。

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

1. monitor/debug 接口是否需要第二层更细的 per-agent drill-down 输出；
2. topic activation 若后续需要解释性，可补 `environment_seed` / `experiment_injection` trace。

### 8.1 Topic activation memory boundary

当前已核对的新仓库事实是：

- topic activation 会主动调用 `OASISManager.step(...)`；
- 初始贴文使用 `ManualAction(ActionType.CREATE_POST)`；
- 后续刷新使用 `ManualAction(ActionType.REFRESH)`；
- OASIS 原生 `env.step(...)` 对 `ManualAction` 会调用 agent 的 `perform_action_by_data(...)`；
- 当前 `action_v1` 的 `ActionEvidence -> ActionEpisode -> long-term` 写入链只接在 `ContextSocialAgent.perform_action_by_llm()`。

因此当前语义边界是：

- topic activation 产生的 seed post / refresh 能进入平台数据库与后续 observation；
- 但它们不会作为 `action_v1` 的普通 LLM 决策步骤写入 `ActionEpisode`；
- 也不会以普通 agent 自主行为的形式进入 long-term recall 主链。

这不一定是错误，因为 topic activation 更像实验注入 / 环境初始化，而不是 agent 自主决策。
但它必须被显式记录，避免之后误以为“所有 step 都会进入 action_v1 记忆”。

后续可选处理路线：

- 保持当前行为：
  - topic activation 只作为环境种子；
  - 不污染 agent 自主行动记忆；
  - 这是当前迁移阶段风险最低的选择。
- 增加专门 trace：
  - 把 topic activation 作为 `environment_seed` / `experiment_injection` 记录到 memory debug；
  - 不写入普通 `ActionEpisode`；
  - 适合后续做可解释性和实验复现。
- 接入 action episode：
  - 需要为 `ManualAction` 补独立 evidence/outcome 构造；
  - 容易把“实验注入”和“agent 自主行为”混在一起；
  - 不建议在迁移阶段直接做。

当前已经按下面方向收口：

- `backend/tests/e2e/`
  - 保留 API / E2E smoke 脚本
- `backend/tests/memory/`
  - 承载 unit / integration / evaluation 分层测试
