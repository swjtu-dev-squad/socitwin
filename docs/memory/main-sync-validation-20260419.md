# Main Sync Validation 2026-04-19

- Status: active validation record
- Audience: reviewers, implementers, PR authors
- Doc role: record the validation results after merging `origin/main` into `integration/memory-migration-main-sync`

## 1. Purpose

本文档记录 2026-04-19 这轮 `origin/main` 同步后的验证结果。

重点回答：

1. 合并后哪些主线已经被实际验证；
2. 哪些验证是自动化测试，哪些是真实接口联调；
3. 当前还有哪些环境阻塞项；
4. 哪些问题是已知但非阻塞。

## 2. Target Branch

- branch: `integration/memory-migration-main-sync`
- merge commit: `169e5dc`

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

### 3.3 Diff Hygiene

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

### 5.1 Official E2E Script

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
- 当前本地缺少：
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

## 6. Environment Blockers

当前唯一明确的环境阻塞项是：

- 缺少 dataset 数据库：
  - `backend/data/datasets/oasis_datasets.db`

它影响的是真实 dataset topic 路线，包括：

- `GET /api/topics?...`
- `POST /api/topics/{topic_id}/activate`
- 依赖 dataset topic 的官方 E2E 脚本

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

## 8. Current Conclusion

截至 2026-04-19，这轮 `origin/main` 同步后的整合分支可以做如下判断：

- 非 dataset 的核心主线已经通过：
  - 自动化测试
  - 前端类型检查与构建
  - 真实接口联调
  - 短链路 E2E
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
- 当前未完成真实 E2E 的只剩 dataset topic 路线，而阻塞原因是本地缺数据集库，不是 merge 已知破坏。

## 9. Recommended Next Step

后续建议二选一：

1. 补齐 `oasis_datasets.db`，把 dataset topic 路线和官方 E2E 补跑完整；
2. 直接进入 PR/合并准备，把本页作为测试结论引用。
