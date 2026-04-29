# Config And Runtime

- Status: active working reference
- Audience: implementers, operators, reviewers
- Doc role: explain the current memory-related config surfaces and runtime resolution in `socitwin`

## 1. Purpose

本文档说明当前新仓库里与记忆系统相关的配置入口和运行时语义。

重点回答：

- 模式从哪里选；
- 模型上下文预算和生成预算从哪里来；
- `action_v1` 的 preset 从哪里读；
- 长期记忆后端和 embedding 如何配置。

## 2. Current Config Layers

当前记忆相关配置主要分两层：

### 2.1 Application Settings Layer

入口在：

- [backend/app/core/config.py](/home/grayg/socitwin/backend/app/core/config.py)

这一层负责：

- 全局 settings
- `.env` 读取
- provider API key
- OASIS 基础运行参数
- long-term backend 基础入口

### 2.2 Memory Runtime Layer

入口在：

- [backend/app/memory/config.py](/home/grayg/socitwin/backend/app/memory/config.py)

这一层负责：

- `MemoryMode`
- `ActionV1RuntimeSettings`
- observation / working memory / recall / summary / provider runtime presets
- 旧仓库 `OASIS_V1_*` 兼容 env override

## 3. Mode Selection

当前模式选择有两个输入面：

1. API / runtime config
   - `SimulationConfig.memory_mode`
2. settings fallback
   - `OASIS_MEMORY_MODE`

最终解析入口在：

- [memory/config.py](/home/grayg/socitwin/backend/app/memory/config.py)
  - `resolve_memory_runtime_config(...)`

当前规则是：

- 显式 `SimulationConfig.memory_mode` 优先；
- 否则退回 `OASIS_MEMORY_MODE`；
- 当前允许值只有：
  - `upstream`
  - `action_v1`

## 4. Model Runtime Inputs

当前模型 runtime 输入主要来自：

- [backend/app/models/simulation.py](/home/grayg/socitwin/backend/app/models/simulation.py)
  - `ModelConfig`
- [backend/app/core/oasis_manager.py](/home/grayg/socitwin/backend/app/core/oasis_manager.py)
  - `_create_model(...)`

当前主要字段包括：

- `model_platform`
- `model_type`
- `temperature`
- `max_tokens`

截至 DeepSeek 当前官方文档，项目侧 DeepSeek 默认模型应使用：

- `model_platform=DEEPSEEK`
- `model_type=deepseek-v4-flash`

旧别名 `deepseek-chat` / `deepseek-reasoner` 仍有兼容映射，但官方文档已标注后续弃用；新代码和示例不应继续依赖旧别名。

这里要明确两个不同语义：

- `max_tokens`
  - 当前主要对应生成上限；
- `OASIS_CONTEXT_TOKEN_LIMIT`
  - 当前对应上下文预算上限。

两者不能混成一个值。

## 5. Current Context / Generation Budget Semantics

当前 `action_v1` 的预算有两个关键来源：

### 5.1 Context Limit

来源：

- `OASIS_CONTEXT_TOKEN_LIMIT`

在 `OASISManager._build_action_v1_runtime_settings(...)` 中，会被写入：

- `ActionV1RuntimeSettings.context_token_limit`

它进一步决定：

- `observation_target_budget`
- `observation_hard_budget`
- `effective_prompt_budget`

### 5.2 Generation Reserve

来源：

- `SimulationConfig.llm_config.max_tokens`

当前它会先被拿来初始化：

- `WorkingMemoryBudgetConfig.generation_reserve_tokens`

然后再允许被：

- `OASIS_V1_GENERATION_RESERVE_TOKENS`

覆盖。

这条边界当前需要按代码事实理解：

- 默认情况下，generation reserve 取自本轮 LLM config 的 `max_tokens`；
- 如果设置了兼容 env override，则以 override 为准。

## 6. Current Runtime Packaging Boundary

旧仓库里更完整的模型 runtime 包装，主要集中在：

- `context/llm.py`

当前新仓库没有按一比一方式重建一个独立 `memory/llm.py`。

当前实际语义是分散承载的：

- [oasis_manager.py](/home/grayg/socitwin/backend/app/core/oasis_manager.py)
  - model 创建
  - `context_token_limit` / generation 输入接线
  - long-term backend build
- [memory/config.py](/home/grayg/socitwin/backend/app/memory/config.py)
  - mode-aware runtime settings
  - preset / env override 归一
- [agent.py](/home/grayg/socitwin/backend/app/memory/agent.py)
  - upstream / action_v1 agent wiring
  - token counter fallback 的实际消费

当前应把这件事理解成：

- 旧仓库 `context/llm.py` 的“独立包装形式”没有原样迁回；
- 但迁移主链所需的 runtime 语义已经基本恢复；
- 这不属于本轮迁移完成态的阻塞项。

只有在后续真的出现下面这些需求时，才值得再抽一个更小、更明确的 runtime helper：

- pooled/shared runtime 需要统一约束
- 多 backend 的 runtime 一致性再次变成维护痛点
- 分散实现开始显著增加调试和配置成本

## 7. Upstream Runtime Config

`upstream` 当前只消费较少的配置面：

- `OASIS_MEMORY_MODE`
- `OASIS_CONTEXT_TOKEN_LIMIT`
- 模型 platform/type/temperature/max_tokens

它不会消费：

- observation shaping preset
- working memory preset
- recall preset
- summary preset
- provider runtime preset

但它当前仍会通过项目侧 helper 把 `context_token_limit` 接到 chat history memory 上，所以它不是完全“无配置”的原始隐式路径。

这里还要明确一个已经修正过的参数语义边界：

- `SimulationConfig.llm_config.max_tokens`
  - 当前仍应理解为生成输出上限；
- 它不能被重新解释成 upstream chat history 的上下文上限。

原因是：

- CAMEL backend 在某些路径下会优先读取 model config 里的 `max_tokens`；
- 如果不额外修正，upstream chat history 的 context creator 会被错误压到这个生成上限上；
- 当前项目侧已经显式把 upstream chat history memory 的上下文限制接回：
  - `OASIS_CONTEXT_TOKEN_LIMIT`

因此当前应按下面语义读：

- `max_tokens`
  - 生成输出预算
- `OASIS_CONTEXT_TOKEN_LIMIT`
  - 上下文预算

这不是把 upstream 改造成 `action_v1`，而是防止项目侧参数语义串线。

## 8. Action_V1 Runtime Settings

`action_v1` 当前的完整 runtime settings 由：

- [oasis_manager.py](/home/grayg/socitwin/backend/app/core/oasis_manager.py)
  - `_build_action_v1_runtime_settings(...)`

统一构造。

它当前会装配：

- `token_counter`
- `system_message`
- `context_token_limit`
- `observation_preset`
- `summary_preset`
- `working_memory_budget`
- `recall_preset`
- `longterm_sidecar`
- `provider_runtime_preset`
- `token_counter_mode`
- `context_window_source`
- `model_backend_family`

当前 token counter 的规则是：

- 优先使用 model backend 自带 token counter；
- 拿不到时退回：
  - `HeuristicUnicodeTokenCounter`

## 9. Observation Preset Surface

当前 observation 兼容 env 面包括：

- `OASIS_V1_OBS_GROUPS_COUNT_GUARD`
- `OASIS_V1_OBS_COMMENTS_TOTAL_GUARD`
- `OASIS_V1_OBS_MESSAGES_TOTAL_GUARD`
- `OASIS_V1_OBS_POST_TEXT_CAP_CHARS`
- `OASIS_V1_OBS_COMMENT_TEXT_CAP_CHARS`
- `OASIS_V1_OBS_MESSAGE_TEXT_CAP_CHARS`
- `OASIS_V1_OBS_PHYSICAL_FALLBACK_*`
- `OASIS_V1_OBS_TARGET_RATIO`
- `OASIS_V1_OBS_HARD_RATIO`

当前入口在：

- [memory/config.py](/home/grayg/socitwin/backend/app/memory/config.py)
  - `apply_observation_env_overrides(...)`

## 10. Working Memory Preset Surface

当前 short-term 预算相关 env 包括：

- `OASIS_V1_RECENT_BUDGET_RATIO`
- `OASIS_V1_COMPRESSED_BUDGET_RATIO`
- `OASIS_V1_RECALL_BUDGET_RATIO`
- `OASIS_V1_RECENT_STEP_CAP`
- `OASIS_V1_COMPRESSED_BLOCK_CAP`
- `OASIS_V1_COMPRESSED_MERGE_TRIGGER_RATIO`
- `OASIS_V1_GENERATION_RESERVE_TOKENS`

入口在：

- `apply_working_memory_env_overrides(...)`

## 11. Recall / Summary / Provider Preset Surface

当前 recall 相关 env 包括：

- `OASIS_V1_RECALL_LIMIT`
- `OASIS_V1_RECALL_COOLDOWN_STEPS`
- `OASIS_V1_RECALL_MIN_TRIGGER_ENTITY_COUNT`
- `OASIS_V1_RECALL_ALLOW_TOPIC_TRIGGER`
- `OASIS_V1_RECALL_ALLOW_ANCHOR_TRIGGER`
- `OASIS_V1_RECALL_ALLOW_RECENT_ACTION_TRIGGER`
- `OASIS_V1_RECALL_ALLOW_SELF_AUTHORED_TRIGGER`
- `OASIS_V1_RECALL_DENY_REPEATED_QUERY_WITHIN_STEPS`
- `OASIS_V1_RECALL_MAX_REASON_TRACE_CHARS`

summary 相关 env 包括：

- `OASIS_V1_SUMMARY_MAX_ACTION_ITEMS_PER_BLOCK`
- `OASIS_V1_SUMMARY_MAX_ACTION_ITEMS_PER_RECENT_TURN`
- `OASIS_V1_SUMMARY_MAX_TARGET_SUMMARY_CHARS`
- `OASIS_V1_SUMMARY_MAX_LOCAL_CONTEXT_CHARS`
- `OASIS_V1_SUMMARY_MAX_OUTCOME_DIGEST_CHARS`
- `OASIS_V1_SUMMARY_COMPRESSED_NOTE_TITLE`
- `OASIS_V1_SUMMARY_RECALL_NOTE_TITLE`

provider runtime 相关 env 包括：

- `OASIS_V1_PROVIDER_ERROR_MATCHERS_FILE`
- `OASIS_V1_PROVIDER_NATIVE_OVERFLOW_TIERS`
- `OASIS_V1_PROVIDER_HEURISTIC_OVERFLOW_TIERS`
- `OASIS_V1_PROVIDER_COUNTER_UNCERTAINTY_RESERVE_POLICY`
- `OASIS_V1_PROVIDER_MAX_BUDGET_RETRIES`

这些入口都仍然位于：

- [memory/config.py](/home/grayg/socitwin/backend/app/memory/config.py)

## 12. Long-Term Backend Surface

长期记忆后端当前主要由 settings 层控制：

- `OASIS_LONGTERM_ENABLED`
- `OASIS_LONGTERM_CHROMA_PATH`
- `OASIS_LONGTERM_COLLECTION_PREFIX`
- `OASIS_LONGTERM_EMBEDDING_BACKEND`
- `OASIS_LONGTERM_EMBEDDING_MODEL`
- `OASIS_LONGTERM_EMBEDDING_API_KEY`
- `OASIS_LONGTERM_EMBEDDING_BASE_URL`
- `OASIS_LONGTERM_DELETE_COLLECTION_ON_CLOSE`

对应实现入口在：

- [oasis_manager.py](/home/grayg/socitwin/backend/app/core/oasis_manager.py)
  - `_get_action_v1_longterm_store(...)`

当前 collection name 规则是：

- `OASIS_LONGTERM_COLLECTION_PREFIX + "_" + db_path.stem`

这意味着每个 simulation db 会对应一个独立 collection 名。

## 13. Current `.env` Entry

当前示例配置在：

- [backend/.env.example](/home/grayg/socitwin/backend/.env.example)

它已经明确保留了两层词汇：

- 新仓库 settings 词汇
  - 例如 `OASIS_MEMORY_MODE`
  - `OASIS_CONTEXT_TOKEN_LIMIT`
  - `OASIS_LONGTERM_*`
- 旧仓库兼容词汇
  - `OASIS_V1_*`

当前这样做的目的不是永久保留双词汇体系，而是：

- 先让迁移不需要立刻重开一套全新命名；
- 等正式文档和运行面稳定后，再决定是否继续收敛命名。

## 14. Current Operational Guidance

当前如果只是想把主链跑起来，最关键的配置是：

- `DEEPSEEK_API_KEY`
- `OASIS_MEMORY_MODE`
- `OASIS_CONTEXT_TOKEN_LIMIT`
- `OASIS_LONGTERM_ENABLED`
- `OASIS_LONGTERM_EMBEDDING_BACKEND`
- 若用真实 embedding：
  - `OASIS_LONGTERM_EMBEDDING_MODEL`
  - `OASIS_LONGTERM_EMBEDDING_BASE_URL`
  - `OASIS_LONGTERM_EMBEDDING_API_KEY`（如需要）

当前如果只是本地跑结构和 fallback，可先用：

- `OASIS_MEMORY_MODE=action_v1`
- `OASIS_LONGTERM_EMBEDDING_BACKEND=heuristic`

当前如果要跑真实 recall / long-term 效果，更推荐：

- `OASIS_LONGTERM_EMBEDDING_BACKEND=openai_compatible`
- 配合 Chroma 跑真实 embedding

## 14.1 Current Embedding Runtime Decision

当前关于长期记忆 embedding 的运行判断，需要再明确一层：

- `upstream` 不依赖长期记忆 sidecar，也不依赖 embedding 服务；
- `action_v1` 如果启用了 long-term sidecar，并且 `OASIS_LONGTERM_EMBEDDING_BACKEND=openai_compatible`，
  就要求本地或远端 embedding 服务在启动时可用；
- 当前系统已经补了 preflight：
  - 如果 embedding 服务不可用，`action_v1` 应在初始化早期直接失败并返回明确报错；
  - 不再允许“接口卡住但页面无反馈”的状态。

当前 `openai_compatible` 路线下，会显式依赖：

- `OASIS_LONGTERM_EMBEDDING_MODEL`
- `OASIS_LONGTERM_EMBEDDING_BASE_URL`
- `OASIS_LONGTERM_EMBEDDING_API_KEY`（如需要）

其中 `OASIS_LONGTERM_EMBEDDING_MODEL` 的角色要理解成：

- 它不是“可有可无的展示字段”；
- 它决定本次 simulation 的 embedding 空间和 Chroma collection 语义。

## 14.2 Current Non-Choice: No Automatic Heuristic Fallback

当前已经明确不把 `openai_compatible -> heuristic` 作为自动回退策略。

原因不是实现做不到，而是工程和评测代价过高：

- `heuristic` 和真实 embedding 不在同一个向量空间；
- 同一条 simulation 中如果静默跨后端降级，会污染 recall 命中率和召回质量判断；
- Chroma collection、检索质量、测试报告解释都会变脏；
- 用户会误以为当前跑的是“真实 embedding”，但实际已经退化成 hash/heuristic。

因此当前结论是：

- 可以保留 `heuristic` 作为显式配置选项；
- 但不做自动兼容回退；
- `action_v1 + openai_compatible` 不可用时，应明确失败，而不是静默降级。

## 14.3 Next Reasonable Direction: Same-Backend Model Selection / Fallback

相比 heuristic 自动回退，更合理的下一步是：

- 仍固定 `OASIS_LONGTERM_EMBEDDING_BACKEND=openai_compatible`；
- 只在同一后端内部做模型选择与启动期回退；
- 一旦本次 simulation 选定某个 embedding model，就整局固定，不在运行中切换。

当前建议的方向是：

- 保留显式主配置：
  - `OASIS_LONGTERM_EMBEDDING_MODEL`
- 增加候选配置：
  - `OASIS_LONGTERM_EMBEDDING_MODEL_CANDIDATES`

预期语义是：

- 若显式指定了 `MODEL`，优先探测该模型；
- 若该模型不可用，再按 `MODEL_CANDIDATES` 顺序尝试；
- 若未显式指定 `MODEL`，则直接按候选顺序选第一个可用模型；
- 若候选都不可用，则明确启动失败。

这样做的边界更干净：

- 不跨 embedding backend；
- 不在运行中切换模型；
- 可以在状态页、测试报告、前端监控里暴露实际生效模型；
- 不会破坏同一 simulation 内部的向量空间一致性。

## 15. Related Docs

- 当前整体实现：
  - [current-architecture.md](./current-architecture.md)
- observation 主链：
  - [observation-and-evidence.md](./observation-and-evidence.md)
- short-term：
  - [prompt-and-shortterm.md](./prompt-and-shortterm.md)
- long-term 与 recall：
  - [longterm-and-recall.md](./longterm-and-recall.md)
- testing 与评测：
  - [testing-and-evaluation.md](./evaluation/testing-and-evaluation.md)
