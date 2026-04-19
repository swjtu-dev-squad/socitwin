# Main Sync Validation 2026-04-19

- Status: active validation record
- Audience: reviewers, implementers, PR authors
- Doc role: record the validation results after merging `origin/main` into `integration/memory-migration-main-sync`

## 1. Purpose

本文档记录 2026-04-19 这轮 `origin/main` 同步后的验证结果，以及随后完成的 PR 准备检查收口结果。

重点回答：

1. 合并后哪些主线已经被实际验证；
2. 哪些验证是自动化测试，哪些是真实接口联调；
3. 当前还有哪些环境阻塞项；
4. 哪些问题是已知但非阻塞。

## 2. Target Branch

- branch: `integration/memory-migration-main-sync`
- merge commit: `169e5dc`
- PR-prep commits:
  - `19b236d` `Prepare branch for PR checks`
  - `3400031` `Tighten runtime error naming`

## 3. Automated Checks

### 3.1 Backend

运行：

```bash
uv run pytest tests/memory tests/unit/test_settings.py tests/e2e/test_config_endpoint.py
```

结果：

- `99 passed, 3 warnings`

补充运行：

```bash
uv run pytest tests/memory/integration/test_memory_debug_api.py
```

结果：

- `1 passed`

已覆盖的重点包括：

- memory unit / integration / evaluation
- `OASISManager` memory wiring
- `/api/sim/config`
- `/api/sim/memory`
- `/api/sim/agents/monitor`
- settings/config surface

### 3.2 Frontend

运行：

```bash
pnpm --dir frontend exec tsc --noEmit
pnpm --dir frontend build
```

结果：

- TypeScript 检查通过
- 生产构建通过

备注：

- build 仍有大 bundle warning，但这是性能优化项，不是功能阻塞项。

### 3.3 PR Gate Re-Run

在完成 main sync 之后，又额外按 GitHub Actions 的实际门槛完整复跑了：

```bash
uv run pyright app/
uv run ruff check . --ignore=E501
pnpm run format:check
pnpm run build
```

结果：

- 后端 `pyright` 通过
- 后端 `ruff` 通过
- 前端 `format:check` 通过
- 前端 `build` 通过

说明：

- 本轮为 PR 准备而做的格式、lint、类型修正没有引入新的阻塞项
- 当前分支已经满足仓库 CI 的硬门槛

### 3.4 Diff Hygiene

运行：

```bash
git diff --check --cached
```

结果：

- 通过

## 4. Real API Smoke

真实联调统一使用当前分支自己的独立实例：

```text
http://127.0.0.1:8001
```

这样可以避免误测到机器上已有的其他 `8000` 服务。

### 4.1 Action_V1 Mainline

已验证链路：

- `POST /api/sim/reset`
- `POST /api/sim/config`
- `GET /api/sim/status`
- `GET /api/sim/memory`
- `POST /api/sim/step`
- `GET /api/sim/status`
- `GET /api/sim/memory`
- `GET /api/sim/agents/monitor`

结果：

- 配置成功
- `memory_mode=action_v1`
- step 成功执行
- step 后 `current_step=1`
- `memory.longterm_enabled=true`
- monitor 返回真实 graph / agents / memory 数据

### 4.2 Upstream Mainline

已验证链路：

- `POST /api/sim/reset`
- `POST /api/sim/config`
- `POST /api/sim/step`
- `GET /api/sim/status`
- `GET /api/sim/memory`
- `GET /api/sim/agents/monitor`

结果：

- 配置成功
- `memory_mode=upstream`
- step 成功执行
- `memory.longterm_enabled=false`
- monitor 中 `simulation.memoryMode=upstream`

### 4.3 Manual Agent Source

已验证：

- `agent_source.source_type=manual`
- 两个手工 agent 配置成功进入仿真
- step 成功执行

结果：

- `status.agents` 中返回的 `name / user_name / description / interests` 与手工配置一致

### 4.4 File Agent Source

已验证：

- `agent_source.source_type=file`
- Twitter CSV 样例文件成功被解析
- step 成功执行

结果：

- `status.agents` 中返回的 `File Alice / file_alice` 与 `File Bob / file_bob`
- `current_step=1`
- `total_posts=2`

### 4.5 Controlled Agents

已验证：

- `POST /api/sim/agents/controlled`

结果：

- 成功添加 1 个受控 agent
- `status.agent_count` 和 monitor graph node count 同步增加

### 4.6 Metrics

已验证：

- `/api/metrics/summary`
- `/api/metrics/propagation`
- `/api/metrics/polarization`
- `/api/metrics/herd-effect`
- `/api/metrics/history`
- `/api/metrics/history/latest`

结果：

- 在未初始化模拟前会返回：
  - `503 Metrics manager not available`
- 在完成 `config + step` 后，上述接口全部正常返回

这说明：

- metrics 接口本身没有在合并中损坏
- 它依赖已有仿真上下文，这是当前预期行为

### 4.7 SSE Event Stream

已验证：

- `GET /api/sim/events`

在监听事件流后，再触发：

- `POST /api/sim/reset`
- `POST /api/sim/config`
- `POST /api/sim/step`

实际收到事件：

- `simulation_reset`
- `simulation_configured`
- `simulation_step_completed`

这说明 monitor 刷新依赖的事件流当前可用。

## 5. Short E2E

### 5.1 Official E2E Script With Missing Dataset

运行：

```bash
python backend/tests/e2e/e2e_simulation_test.py \
  --base-url http://127.0.0.1:8001 \
  --agent-count 2 \
  --max-steps 1 \
  --memory-mode action_v1 \
  --timeout 60 \
  --output-dir /tmp/socitwin-e2e-short \
  --no-verbose
```

结果：

- 失败

失败原因：

- 脚本固定要求先做 `topic activate`
- 当时本地缺少：
  - `backend/data/datasets/oasis_datasets.db`
- 因此卡在：
  - `Failed to activate topic: Dataset database not found`

### 5.2 Equivalent Short E2E Without Dataset Topic

已补跑一个去掉 `topic activate` 依赖的等价短链路：

- `reset -> config -> status -> step -> status -> memory -> monitor`

结果：

- `config_success=true`
- `step_success=true`
- `step_executed=1`
- `post_state=complete`
- `current_step=1`
- `total_posts=2`
- `memory_mode=action_v1`
- `longterm_enabled=true`
- `monitor_mode=action_v1`

这说明：

- 官方 E2E 当前的失败原因是 dataset 环境阻塞；
- 非 dataset 的短链路 E2E 已经跑通。

### 5.3 Official E2E Script With Dataset And Real Topic

后续已将 dataset 数据库补到后端默认目录：

- `backend/data/datasets/oasis_datasets.db`

并确认 `/api/topics` 已可正常返回 topic 列表。

随后再次运行官方脚本，但不再使用脚本内过时的默认 topic，而改用数据库中实际存在的 topic：

```bash
python backend/tests/e2e/e2e_simulation_test.py \
  --base-url http://127.0.0.1:8001 \
  --agent-count 2 \
  --max-steps 1 \
  --memory-mode action_v1 \
  --topic 2042552568010936455 \
  --timeout 120 \
  --output-dir /tmp/socitwin-e2e-short \
  --no-verbose
```

结果：

- 通过
- `Steps executed: 1`
- `Successful: 1`
- `Failed: 0`
- `Total time: 12.51s`
- `Posts created: 3`
- `Interactions: 9`

结果文件中的 memory 指标：

- `memory_mode = action_v1`
- `agent_count = 2`
- `context_token_limit = 16384`
- `generation_max_tokens = 1024`
- `total_recent_retained = 2`
- `total_compressed_retained = 0`
- `total_recall_injected = 0`
- `max_prompt_tokens = 423`
- `max_observation_tokens = 423`

这说明：

- dataset 路线本身已经可用；
- 官方 E2E 脚本的真实阻塞点已经从“缺 dataset”变成“默认 topic 过时”；
- 在使用真实存在的 topic 时，官方短 E2E 可以正常完成。

### 5.4 Live UI Smoke On Shared 8000 Instance

为确认前端“社交网络监控”页面与当前后端实例的实际联动状态，又直接在用户已启动的 `http://127.0.0.1:8000` 实例上进行了可视化短跑：

- `memory_mode = action_v1`
- `agent_count = 2`
- `topic = 2042552568010936455`
- 计划 10 轮，在第 5 轮前由人工中止

运行过程中确认页面可观测，且后端状态正常推进。中止后再次读取状态：

- `current_step = 5`
- `total_posts = 6`
- `total_interactions = 23`

对应 memory 指标：

- `max_recent = 3`
- `max_compressed = 2`
- `max_recalled = 3`
- `max_injected = 0`

这说明：

- 页面监控链与当前后端实例状态是一致的；
- `recent -> compressed` 的短程流转已经在真实运行里出现；
- recall 已开始触发统计，但在该短窗口中尚未注入到 prompt。

## 6. Environment Blockers

当前已经不存在“dataset 缺失”这一类基础环境阻塞。

当前剩余的环境/数据层注意事项是：

- 官方 E2E 脚本默认 topic `climate_change_debate` 与当前 dataset 内容不匹配；
- 因此在当前数据集上运行官方脚本时，需要显式传入真实存在的 topic id。

这不是系统功能损坏，而是测试默认值过时。

## 7. Known Non-Blocking Issues

### 7.1 OASIS Twitter Refresh Runtime Log

真实运行时仍可见日志：

```text
social.twitter - ERROR - list index out of range
```

当前观察到：

- 它没有阻断 step 完成；
- `status / memory / monitor / metrics` 仍会正常返回；
- 更像上游 OASIS 的运行时边界噪音或潜在 bug。

当前结论：

- 需要后续单独审查；
- 但不作为这轮 main sync 的阻塞项。

### 7.2 Frontend Bundle Size Warning

`pnpm --dir frontend build` 仍会提示 chunk 较大。

当前结论：

- 性能优化项；
- 非功能阻塞项。

### 7.3 Official E2E Default Topic Drift

当前官方 E2E 脚本默认使用：

- `climate_change_debate`

但这不是当前 dataset 中的真实 topic。

当前结论：

- 脚本本身未损坏；
- 但默认 topic 示例值需要后续更新到 dataset-backed 真实 topic，或补成“先 list topics 再选用第一个可用 topic”的逻辑。

## 8. Current Conclusion

截至 2026-04-19，这轮 `origin/main` 同步后的整合分支可以做如下判断：

- 非 dataset 的核心主线已经通过：
  - 自动化测试
  - 前端类型检查与构建
  - 真实接口联调
  - 短链路 E2E
- dataset topic 路线也已通过：
  - `/api/topics` 列表可用
  - `topic activate` 可用
  - 官方短 E2E 在真实 topic id 下可跑通
- 已真实验证通过的能力包括：
  - `upstream`
  - `action_v1`
  - `manual agent source`
  - `file agent source`
  - `controlled agents`
  - `metrics`
  - `memory debug`
  - `agent monitor`
  - `SSE /events`
- 当前分支也已经通过仓库 CI 所要求的本地门槛：
  - `pyright`
  - `ruff`
  - `frontend format:check`
  - `frontend build`
- 当前没有发现“main sync 或 PR 准备过程改坏记忆主链”的证据。

## 9. Recommended Next Step

后续建议二选一：

1. 更新官方 E2E 脚本中的默认 topic 示例值，避免未来在新数据集下再次因过时默认值误判；
2. 直接进入 PR/合并准备，把本页作为 main sync 验证与 PR 准备测试结论引用。
