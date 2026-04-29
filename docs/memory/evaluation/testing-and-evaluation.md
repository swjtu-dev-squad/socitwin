# Testing And Evaluation

- Status: active working reference
- Audience: implementers, reviewers, evaluators
- Doc role: explain the current testing layers, evaluation harness, and acceptance reading in `socitwin`

## 1. Purpose

本文档回答四件事：

1. 当前 memory 测试代码分几层；
2. 各层分别覆盖什么；
3. 系统级 harness 怎么跑、结果怎么看；
4. 当前哪些内容已经恢复，哪些仍属于后续按需验证。

## 2. Current Test Layout

当前记忆测试主要落在：

- [backend/tests/memory/unit](/home/grayg/socitwin/backend/tests/memory/unit)
- [backend/tests/memory/integration](/home/grayg/socitwin/backend/tests/memory/integration)
- [backend/tests/memory/evaluation](/home/grayg/socitwin/backend/tests/memory/evaluation)

这三层之外，真实 provider 级长跑和更重的 E2E 结果会落到：

- `backend/test-results/memory-eval/`
- `docs/memory/evaluation/` 下的专项测试记录文档

## 3. Layer A: Unit Tests

`unit` 层当前主要覆盖 memory 主链中的结构化模块边界。

代表性文件包括：

- `test_budget_recovery.py`
- `test_observation_policy.py`
- `test_observation_semantics.py`
- `test_observation_shaper.py`
- `test_prompt_assembler.py`
- `test_consolidator.py`
- `test_recall_planner.py`
- `test_retrieval_policy.py`
- `test_runtime_failures.py`
- `test_working_memory.py`
- `test_action_evidence.py`
- `test_episodic_memory.py`
- `test_longterm.py`
- `test_memory_config.py`
- `test_memory_runtime.py`
- `test_oasis_manager_memory.py`

它们主要回答：

- observation 主链是否按预期退化
- prompt assembly 是否按预算和重叠规则裁决
- short-term 是否按 step contract 维护
- recall gate / overlap suppression 是否保持结构正确
- runtime failure / budget recovery 是否能走对降级路径

## 4. Layer B: Integration Tests

`integration` 层当前重点覆盖：

- manager 级 memory debug 聚合
- API 输出合同
- monitor/detail 所需的 memory 数据汇总

当前代表性文件：

- [test_memory_debug_api.py](/home/grayg/socitwin/backend/tests/memory/integration/test_memory_debug_api.py)
- [test_agent_monitor_api.py](/home/grayg/socitwin/backend/tests/memory/integration/test_agent_monitor_api.py)

这层的目标不是验证全部语义质量，而是验证：

- memory debug 接口是否还通
- monitor/detail 聚合是否还能拿到关键字段
- `upstream` / `action_v1` 的 runtime 状态是否能被稳定读取

## 5. Layer C: Evaluation Harness

系统级评测入口当前是：

- [evaluation_harness.py](/home/grayg/socitwin/backend/app/memory/evaluation_harness.py)

单测覆盖在：

- [test_memory_evaluation_harness.py](/home/grayg/socitwin/backend/tests/memory/evaluation/test_memory_evaluation_harness.py)

当前 CLI 入口是：

```bash
uv run python -m app.memory.evaluation_harness
```

默认 phase：

- `preflight`
- `deterministic`

默认结果目录：

```text
backend/test-results/memory-eval/<run_id>/
```

每轮当前至少会产出：

- `config.json`
- `events.jsonl`
- `summary.json`
- `README.md`

## 6. Current Harness Phases

当前 harness 已支持这些 phase：

- `preflight`
  - 检查基础依赖、embedding 路径和环境可用性。
- `deterministic`
  - 不依赖真实主模型，验证 observation / episode / recall / budget 主链的结构闭环。
- `real-smoke`
  - 跑最小真实 `action_v1` 链路，确认 initialize/step 能走通。
- `real-scenarios`
  - 基于真实运行后的 episode 做 recall / retrieval probe。
- `real-longwindow`
  - 跑更长窗口，观察 recall 是否真的进入 prompt。
- `comparison`
  - 当前保留为两模式短对比能力，但不作为本轮迁移收尾阻塞项。

这里要特别区分：

- harness phase 已存在
- phase 已经成为当前高频、稳定、正式验收入口

这不是一回事。

当前判断是：

- `preflight / deterministic / real-smoke / real-scenarios / real-longwindow`
  - 已经是当前主线可用能力
- `comparison`
  - 代码和单测层已恢复
  - 但真实 provider 级稳定长跑仍属于后续按需验证

## 7. Current Acceptance Reading

当前读测试状态时，应分三层理解：

### 7.1 已恢复的测试代码主链

这部分现在可以认为主体已经回来了：

- module tests
- integration tests
- evaluation harness

### 7.2 已恢复但不应夸大解释的系统验证

下面这些已经能跑，但不能过度解读：

- `real-smoke`
  - 证明链路能跑通，不证明长期行为质量已经稳定。
- `real-scenarios`
  - 更偏真实 retrieval probe，不等于最终 agent 行为判读。
- `real-longwindow`
  - 可以观察 recall 注入与长期运行，但仍不等于完整效果评审。

### 7.3 当前不纳入迁移收尾阻塞项的测试

- 真实 provider 级稳定 `comparison` 长跑

它现在仍有价值，但属于后续按需评测，不应继续和“迁移是否完成”混在一起。

## 8. Common Commands

跑 memory unit/integration/evaluation 单测：

```bash
uv run pytest backend/tests/memory
```

只跑 evaluation harness 单测：

```bash
uv run pytest backend/tests/memory/evaluation/test_memory_evaluation_harness.py
```

跑默认 harness：

```bash
uv run python -m app.memory.evaluation_harness
```

只跑确定性 phase：

```bash
uv run python -m app.memory.evaluation_harness --phase deterministic
```

跑真实 smoke：

```bash
uv run python -m app.memory.evaluation_harness \
  --phase preflight \
  --phase real-smoke
```

跑真实长窗口：

```bash
uv run python -m app.memory.evaluation_harness \
  --phase preflight \
  --phase real-longwindow
```

## 9. Result Reading

当前 harness 结果至少要结合下面几类文件读：

- `summary.json`
  - 适合快速汇总和 AI 读取
- `events.jsonl`
  - 适合逐事件核查
- 结果目录下 `README.md`
  - 当前的人类可读摘要

当前解释结果时要注意：

- `pass`
  - 该事件按当前验证口径通过
- `fail`
  - 该事件在当前口径下失败
- `blocked`
  - 外部环境不可用或前置条件不满足
  - 不应直接解释为 memory 主链行为失败

## 10. Current Gap

当前测试主链最大的剩余问题已经不再是“没有测试代码”，也不再是“缺正式骨架文档”，而是：

- 还需要继续把常用指标、字段含义和结果解释沉淀得更稳定；
- 还需要随着真实运行结果继续补场景记录和验证证据；
- 还需要把迁移期测试说明里仍然有价值的经验持续收回正式文档。

也就是说，当前测试主链的剩余工作主要是：

- 口径细化
- 结果沉淀
- 场景扩充

而不是从零补测试代码，或继续把测试说明主要堆在迁移文档里。

## 11. Related Docs

- 当前整体实现：
  - [current-architecture.md](../current-architecture.md)
- 模式与边界：
  - [principles-and-modes.md](../principles-and-modes.md)
- 长期记忆测评方案：
  - [README.md](./README.md)
- 文档迁移计划：
  - [migration-documentation-plan.md](../archived/migration/migration-documentation-plan.md)
- 迁移期测试/配置记录：
  - [migration-config-and-testing.md](../archived/migration/migration-config-and-testing.md)
