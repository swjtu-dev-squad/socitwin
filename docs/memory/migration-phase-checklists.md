# Memory Migration Phase Checklists

- Status: active
- Audience: migration implementers, reviewers, AI tools
- Role: turn migration analysis into executable phase checklists

## 1. Usage

本页不是讨论“为什么”，而是约束“怎么做”。

每个 phase 都包含四类信息：

- 目标
- 代码任务
- 验证项
- 禁止事项

后续真正开始迁代码时，应按 phase 顺序推进，而不是跨阶段混做。

## 2. Phase 0: Freeze Scope

### Goal

冻结迁移边界，避免实施过程中模式、目录、测试目标来回漂移。

### Tasks

- 确认新仓库只保留两模式：
  - `upstream`
  - `action_v1`
- 确认 `baseline` 只保留文档历史说明
- 确认 memory 子系统目录：
  - `backend/app/memory/`
- 确认迁移第一优先级：
  - 后端主链
  - memory 主链
  - 测试主链
  - 文档主链

### Validation

- 迁移计划文档与当前决策一致
- 不再有把 `baseline` 作为新仓库运行模式的计划项

### Do Not

- 不在这一步开始复制旧代码
- 不在这一步讨论前端完整联动

## 3. Phase 1: Build Runtime Skeleton

### Goal

在新仓库建立 memory runtime 的承载骨架，但先不一次塞满全部 action_v1 能力。

### Tasks

- 新建 `backend/app/memory/`
- 新建：
  - `backend/app/memory/__init__.py`
  - `backend/app/memory/config.py`
  - `backend/app/memory/runtime.py`
  - `backend/app/memory/agent.py`
- 在 `backend/app/models/simulation.py` 中增加 mode-aware 配置承载
- 在 `backend/app/core/config.py` 与 `backend/app/memory/config.py` 间建立兼容 env 解析层
- 重构 `backend/app/core/oasis_manager.py`
  - 把当前 model / agent / env 构造链拆成可被 runtime facade 接管的函数

建议的最小实现顺序：

1. 在 `SimulationConfig` 中新增 `memory_mode`
   - 默认 `upstream`
2. 创建 `MemoryMode` 枚举与 runtime facade 空壳
3. 让 `OASISManager.initialize()` 先通过 runtime facade 构造：
   - model
   - agent graph
   - env
4. 保持当前实际行为仍等价于原生路径

### Validation

- 新仓库可以显式解析 memory mode
- `OASISManager` 不再把所有模式逻辑硬编码在单一路径里
- 代码仍可导入，原始基础运行不被破坏
- `memory_mode=upstream` 下当前行为与迁移前尽量等价

### Do Not

- 不在这一步引入 observation shaping、working memory、recall 细节
- 不在这一步接前端状态

## 4. Phase 2: Restore Clean Upstream

### Goal

把当前“近似原生路径”显式固化成 `upstream`，并保证后续 action_v1 不会污染它。

### Tasks

- 在 runtime facade 中接入 `upstream` mode
- 恢复原生 agent/model/env 走法
- 确保 `upstream` 不依赖：
  - working memory
  - prompt assembler
  - long-term store
  - recall planner
- 补最小 `upstream` 验证

### Validation

- `upstream` 可配置、可初始化、可 step
- `upstream` 路径不读 action_v1 专属 config
- `upstream` 状态输出不出现伪 memory 字段

### Do Not

- 不为了复用而把 action_v1 的内部对象挂到 `upstream`

## 5. Phase 3: Port Action_V1 Core Loop

### Goal

恢复 `action_v1` 的主链，但按依赖顺序接入，不并行乱迁。

### Tasks

#### 3.1 Observation chain

- 迁 `environment.py`
- 迁 `observation_shaper.py`
- 恢复 prompt-visible snapshot contract

#### 3.2 Episodic chain

- 迁 `action_capabilities.py`
- 迁 `action_significance.py`
- 迁 `action_evidence.py`
- 迁 `episodic_memory.py`

#### 3.3 Short-term chain

- 迁 `working_memory.py`
- 迁 `memory_rendering.py`
- 迁 `consolidator.py`

#### 3.4 Prompt chain

- 迁 `prompt_assembler.py`
- 恢复 observation / recent / compressed / recall 裁决

#### 3.5 Long-term chain

- 迁 `longterm.py`
- 迁 `retrieval_policy.py`
- 迁 `recall_planner.py`

#### 3.6 Failure / budget chain

- 迁 `tokens.py`
- 迁 `runtime_failures.py`
- 接 provider / budget recovery 语义

### Validation

- `action_v1` 可初始化、可 step
- observation / recent / compressed / recall 主链能闭环
- topic activation 下的初始 post + refresh 也能进入新链路

### Do Not

- 不跳过 observation / episode contract 直接接 recall
- 不在 long-term 尚未落稳前就急着跑系统级评测

## 6. Phase 4: Restore Observability

### Goal

让新仓库重新具备 memory-aware 的状态输出、trace 和调试能力。

### Tasks

- 设计 memory runtime snapshot 结构
- 设计独立的 memory monitor/debug 接口
- 将必要状态挂到：
  - memory runtime snapshot 读取面
  - monitor/debug 接口
  - 测试 harness
- 明确哪些 trace 仅供测试，哪些适合对外暴露

建议至少恢复的状态面：

- 当前 mode
- observation shaping stage
- recent/compressed retained summary
- recall gate / recalled / injected summary
- prompt token / budget summary
- runtime failure summary

### Validation

- 不依赖前端，也能通过后端状态读取 memory 关键运行信息
- 后续 harness 不需要通过脆弱日志文本反推关键状态
- `/api/sim/status` 仍保持模拟总状态角色，不被 action_v1 内部 trace 污染

### Do Not

- 不把完整内部对象直接原样暴露给 API

## 7. Phase 5: Restore Tests

### Goal

恢复 memory 主链的回归保护和评测能力。

### Tasks

#### 5.1 Module tests

- observation shaper
- prompt assembler
- consolidator
- recall planner
- runtime failures

#### 5.2 Integration tests

- mode wiring
- topic activation + observation ingestion
- action_v1 step loop
- persist / recall injection

#### 5.3 Evaluation harness

- 迁入或重写 memory evaluation harness
- 恢复：
  - deterministic
  - real-smoke
  - real-scenarios
  - real-longwindow

### Validation

- `upstream` 与 `action_v1` 都有独立验证路径
- action_v1 的记忆主链关键行为有结构化测试覆盖

### Do Not

- 不只保留单个 API E2E 脚本就视为测试已恢复

## 8. Phase 6: Rewrite Docs And Roll Into Mainline

### Goal

把迁移后的新仓库事实写成新的权威文档，并清理迁移期临时说明。

### Tasks

- 根据新仓库实际实现重写 memory 架构文档
- 迁入必要的测试说明和指标口径
- 归档旧 baseline 历史说明
- 清理只服务于迁移过程、已完成使命的计划文档

### Validation

- 新仓库文档能独立解释：
  - 两模式边界
  - action_v1 主链
  - 配置面
  - 测试面

## 9. Current Stop Conditions

下面这些情况一旦遇到，应暂停实施，先复核计划：

- 新仓库重构进一步改变了 `OASISManager` 的职责边界
- 新仓库引入了新的 agent runtime 抽象，导致 `memory/runtime.py` 归属需重判
- API / status 模型已经被其他人改动，和计划假设明显不符
- `camel-oasis` 或 OASIS 版本差异导致旧 memory contract 无法直接成立
