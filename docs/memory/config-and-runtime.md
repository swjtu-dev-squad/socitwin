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

## 6. Upstream Runtime Config

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

## 7. Action_V1 Runtime Settings

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

## 8. Observation Preset Surface

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

## 9. Working Memory Preset Surface

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

## 10. Recall / Summary / Provider Preset Surface

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

## 11. Long-Term Backend Surface

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

## 12. Current `.env` Entry

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

## 13. Current Operational Guidance

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

## 14. Related Docs

- 当前整体实现：
  - [current-architecture.md](./current-architecture.md)
- observation 主链：
  - [observation-and-evidence.md](./observation-and-evidence.md)
- short-term：
  - [prompt-and-shortterm.md](./prompt-and-shortterm.md)
- long-term 与 recall：
  - [longterm-and-recall.md](./longterm-and-recall.md)
- testing 与评测：
  - [testing-and-evaluation.md](./testing-and-evaluation.md)
