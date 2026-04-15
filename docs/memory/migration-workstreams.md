# Memory Migration Workstreams

- Status: active
- Audience: migration implementers, reviewers, AI tools
- Role: define migration scope, phase order, and file-level workstreams

## 1. Migration Scope

当前迁移范围分为五类：

### 1.1 Runtime code

- mode wiring
- shared model runtime
- observation shaping
- prompt-visible snapshot
- action evidence
- short-term working memory
- long-term persistence / retrieval / suppression
- runtime failure recovery

### 1.2 Config surfaces

- memory mode config
- model runtime config
- long-term backend config
- observation / budget / recall / summary preset
- tracing / test harness config

### 1.3 Tests

- module tests
- integration tests
- system evaluation harness
- long-window / retrieval / comparison scenarios

### 1.4 Docs

- architecture facts
- mode boundaries
- observation / budget / recall / episode contracts
- test plan and result interpretation

### 1.5 Interface contracts

- internal backend contracts
- future monitor/debug API contracts for memory state
- frontend memory placeholder compatibility

## 1.6 Refactor posture during migration

本轮迁移不是纯复制，也不是语义重开。

工作姿态应固定为：

- 保留主 contract
- 清理结构债
- 禁止路线语义重开

详细边界见：

- [`migration-refactor-principles.md`](./migration-refactor-principles.md)

## 1.7 Current Execution State

当前实际执行状态应理解为：

- 新仓库的 memory runtime 骨架已建立
- `upstream` 已显式化，不再只是隐式默认路径
- `action_v1` 的核心模块已迁入 `backend/app/memory/`
- 新一轮实施重点不再是“继续搬模块”，而是：
  - 把已迁模块真正接入新仓库 runtime 主链
  - 验证 `template/manual` 可跑
  - 保持 `file` 在 `action_v1` 下显式未迁移
  - 逐步恢复 monitor/debug/test harness

## 2. First-Wave File Candidates

第一波最值得优先迁移或重写的闭环是：

1. `context/config.py`
2. `context/agent.py`
3. `context/environment.py`
4. `context/observation_shaper.py`
5. `context/working_memory.py`
6. `context/consolidator.py`
7. `context/prompt_assembler.py`

这些模块先落稳，后面的：

- `action_evidence.py`
- `episodic_memory.py`
- `longterm.py`
- `recall_planner.py`
- `retrieval_policy.py`
- `runtime_failures.py`

才有稳定承载面。

## 2.1 Proposed New Memory Package Layout

当前建议的新仓库记忆目录布局如下：

- `backend/app/memory/__init__.py`
  - 对外导出 memory runtime 的主入口。
- `backend/app/memory/config.py`
  - 承载 mode、runtime settings、observation / budget / recall preset。
- `backend/app/memory/runtime.py`
  - 提供 mode-aware facade；
  - 负责根据 `upstream / action_v1` 返回对应 wiring。
- `backend/app/memory/agent.py`
  - 承载 `upstream` 与 `action_v1` agent 接线。
- `backend/app/memory/environment.py`
  - observation 获取与发布路径。
- `backend/app/memory/observation_shaper.py`
  - observation 压缩与 fallback。
- `backend/app/memory/action_evidence.py`
  - prompt-visible snapshot -> action evidence。
- `backend/app/memory/working_memory.py`
  - recent / compressed 结构定义。
- `backend/app/memory/consolidator.py`
  - recent -> compressed 演化。
- `backend/app/memory/prompt_assembler.py`
  - prompt 装配与预算裁决。
- `backend/app/memory/episodic_memory.py`
  - `ActionEpisode`、`HeartbeatRange` 等结构。
- `backend/app/memory/longterm.py`
  - long-term backend 与 embedding 路径。
- `backend/app/memory/recall_planner.py`
  - recall gate 与注入准备。
- `backend/app/memory/retrieval_policy.py`
  - 检索排序与 suppression。
- `backend/app/memory/runtime_failures.py`
  - overflow / provider failure / budget recovery。

更细的旧模块映射已经拆到：

- [`migration-module-mapping.md`](./migration-module-mapping.md)

这个布局的目标不是一开始就全部落完，而是先把未来模块归属固定住，避免迁到一半后目录再反复重排。

## 3. Recommended Phase Order

更适合直接执行的逐阶段 checklist 已拆到：

- [`migration-phase-checklists.md`](./migration-phase-checklists.md)

### Phase 0: freeze migration target

- 确认模式数量
- 确认 memory 模块目录
- 确认测试迁移原则

### Phase 1: create memory runtime skeleton

目标：在 `socitwin` 里先建立可承载 memory 主链的骨架。

建议动作：

- 新增 `backend/app/memory/`
- 建立 mode/config/runtime settings 基础模块
- 让 `OASISManager.initialize()` 开始走 mode-aware runtime facade

更具体的第一阶段文件级任务建议：

- 在 `backend/app/memory/` 新建：
  - `__init__.py`
  - `config.py`
  - `runtime.py`
  - `agent.py`
- 在 `backend/app/core/oasis_manager.py` 中：
  - 把当前原生 agent/model/env 构造链抽成可被 memory runtime facade 接管的函数；
  - 不直接在第一阶段塞入全部 action_v1 逻辑。
- 在 `backend/app/models/simulation.py` 中：
  - 增加 mode-aware 配置模型。
- 在 `backend/app/core/config.py` 中：
  - 增加 memory 相关设置入口或兼容映射层。

第一阶段四个新文件的最小职责建议固定为：

- `memory/__init__.py`
  - 只暴露 runtime facade 与核心配置入口；
  - 不做大而全导出。
- `memory/config.py`
  - 定义 `MemoryMode`；
  - 定义最小 runtime settings / compatibility parse；
  - 不在第一阶段塞入全部 V1 preset 细节。
- `memory/runtime.py`
  - 提供 mode-aware runtime facade；
  - 暂时先支持 `upstream` 显式化和 `action_v1` 占位装配；
  - 负责对 `OASISManager` 暴露统一构造接口。
- `memory/agent.py`
  - 只承载 mode-aware agent construction；
  - Phase 1 先恢复 `upstream` 的干净接线，不急着把 action_v1 全量迁入。

第一阶段交付结果应该明确为：

- 新仓库能显式选择 `upstream` / `action_v1`
- `upstream` 仍走原生路径
- `action_v1` 的 runtime 壳已存在，但先不要求整条能力链一次到位
- memory 配置入口已经能读旧仓库 env 家族
- `SimulationConfig` 已能显式携带 `memory_mode`

### Phase 2: restore explicit upstream mode

目标：把当前近似原生路径显式化为 `upstream`。

建议动作：

- 增加 `upstream` mode wiring
- 补最小 upstream 配置与测试
- 确保后续 action_v1 接入不污染 upstream

这一阶段的完成标准是：

- `SimulationConfig` 或其下游 runtime config 已能显式传 mode
- `OASISManager` 对 `upstream` 的构造链没有 memory side effect
- 后续 `action_v1` 接线不需要再修改 `upstream` 逻辑

### Phase 3: port action_v1 mainline

推荐顺序：

1. observation shaping + prompt-visible snapshot
2. action evidence + episode derivation
3. working memory + consolidator
4. prompt assembler + budget semantics
5. long-term persistence
6. recall planner + retrieval policy + suppression
7. runtime failure recovery

### Phase 4: migrate tests and traces

- 先迁关键 module tests
- 再迁 integration tests
- 最后迁 system evaluation harness

推荐测试落点：

- `backend/tests/memory/unit/`
- `backend/tests/memory/integration/`
- `backend/tests/memory/evaluation/`

不建议把 memory tests 全堆进单个 E2E 脚本体系里。
当前已经统一到：

- `backend/tests/e2e/`
- `backend/tests/memory/unit/`
- `backend/tests/memory/integration/`
- `backend/tests/memory/evaluation/`

### Phase 5: rewrite and migrate docs

- 先写新仓库的“当前事实”
- 再写“目标规范”
- 再补测试方案与结果口径

## 4. Testing Migration Strategy

### Layer A: module tests

- observation shaping
- working memory
- consolidator
- prompt assembler
- recall planner
- long-term backend adapter

### Layer B: integration tests

- mode wiring
- topic activation + observation ingestion
- action_v1 step loop
- persistence + recall injection
- API config + status behavior

### Layer C: system evaluation

- deterministic validation
- real-smoke
- real-scenarios
- real-longwindow
- comparison

当前建议：

- 不直接把旧测试整坨复制进新仓库；
- 先恢复“必须保住的验证能力”；
- 再决定哪些旧测试脚本直接迁，哪些保留语义目标后重写。

## 4.1 Current Test Mapping Recommendation

建议将旧测试资产分成三类：

### A. 优先直接迁语义

- `test_observation_shaper.py`
- `test_prompt_assembler.py`
- `test_consolidator.py`
- `test_recall_planner.py`
- `test_runtime_failures.py`

这些测试对应的模块边界清晰，最适合作为新仓库第一批 module tests。

### B. 需要适配后再迁

- `test_context_integration.py`
- `test_memory_evaluation_harness.py`

这些测试依赖旧仓库整体 runtime 入口，不能直接复制，但其验证目标必须保留。

### C. 暂时不先迁代码，只保留验证目标

- 旧仓库中只服务于旧 dashboard 引擎壳的 demo / legacy test

这部分可以等新仓库主链稳定后再决定是否需要恢复。

## 5. Documentation Strategy

建议迁移方式：

- 保留：
  - 架构原则
  - 模式职责
  - observation / budget / recall / episode 契约
  - 测试口径和指标定义
- 重写：
  - 新仓库代码入口
  - 新仓库配置入口
  - 新仓库实施阶段说明
- 归档：
  - `baseline` 历史讨论
  - 只服务于旧目录结构的旧叙述

## 6. Open Work Items

- 继续细查 `oasis_manager.py` 与模型/agent 构造链，压实 memory runtime facade 的具体接线方式；
- 继续把旧仓库各 memory 模块映射到新仓库 `backend/app/memory/` 下的文件级任务清单；
- 明确 memory 配置命名是否继续沿用 `OASIS_MODEL_*` / `OASIS_V1_*`；
- 明确 system evaluation harness 在新仓库中的落点。

当前新增的细化页面：

- [`migration-module-mapping.md`](./migration-module-mapping.md)
- [`migration-config-and-testing.md`](./migration-config-and-testing.md)

## 7. Config Naming Options

当前新旧仓库的配置命名风格明显不同：

- 旧仓库：
  - `OASIS_MODEL_*`
  - `OASIS_CONTEXT_TOKEN_LIMIT`
  - `OASIS_LONGTERM_*`
  - `OASIS_V1_*`
- 新仓库：
  - `DEEPSEEK_API_KEY`
  - `OPENAI_API_KEY`
  - `OASIS_DEFAULT_MODEL`
  - 轻量 `Settings`

迁移时有两个主要方案。

### Option A: 全面改成新命名风格

优点：

- 新仓库风格统一。

风险：

- 旧测试脚本、旧文档、旧运行经验都要一起重写；
- 迁移成本高；
- 早期更容易因为命名改动引入无意义问题。

### Option B: 保留旧 memory config 作为兼容层

做法：

- 新仓库 `Settings` 增加对旧 memory env 的兼容读取；
- 内部统一映射成新的 settings 对象；
- 外部先允许继续使用旧的 `OASIS_MODEL_*` / `OASIS_V1_*`。

优点：

- 迁移成本低；
- 旧文档和旧测试更容易平移；
- 更适合第一阶段快速恢复主链。

风险：

- 新仓库短期内会存在两套命名风格并存。

### Current recommendation

当前更推荐 `Option B`：

- 第一阶段先保留旧 memory env 作为兼容层；
- 等 memory 主链稳定后，再评估是否统一收口配置命名。
