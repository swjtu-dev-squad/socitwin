# R2-05 API-only / 单进程数据库约束 Smoke Test 报告

| 属性 | 值 |
|---|---|
| **执行时间** | 2026-03-17 |
| **结论** | ✅ PASS（5/5 gates） |
| **关联 Issue** | 无（第一轮遗留观察） |

---

## 执行结果

### Gate 验收

| 验收项 | 状态 |
|---|---|
| CLI smoke 使用独立 fixture 数据库 | ✅ PASS |
| Dashboard 使用与 CLI 分离的数据库 | ✅ PASS |
| R2 轮次全程无 disk I/O error | ✅ PASS |
| Dashboard 交互通过 API 完成 | ✅ PASS |
| 并发 API 调用无错误 | ✅ PASS |

**总体结论：✅ PASS — 单进程写入约束已在当前架构中自然满足。**

---

## 约束验证详情

### (1) CLI smoke 使用独立数据库

`context_smoke.py` 默认参数：

```python
parser.add_argument("--db-path", default="/tmp/oasis-context-smoke.db")
```

CLI smoke 工具使用 `/tmp/oasis-context-smoke.db`，与 Dashboard 运行时数据库完全隔离。

### (2) Dashboard 使用独立数据库

`real_oasis_engine_v3.py` 默认参数：

```python
db_path: str = "./oasis_simulation.db"
```

Dashboard 使用项目目录下的 `oasis_simulation.db`，与 `/tmp` 路径的 CLI 数据库互不干扰。

### (3) R2 轮次全程 API-only

本轮所有 smoke 测试脚本（`run_r2_01_v2.py`、`run_r2_04.py`、`run_st05_websocket_test.py`）均通过 `http://localhost:3000` HTTP API 与引擎交互，无任何脚本直接写入运行中的 `oasis_simulation.db`。

### (4) 并发 API 调用稳定

3 次快速连续 API 调用均返回 HTTP 200，无超时、无 I/O 错误。

---

## 工程约束文档（固化）

以下约束已在本轮验证中确认，应写入团队开发规范：

> **单进程写入原则**
>
> 1. `oasis_simulation.db` 在 `pnpm dev` 运行期间由 Python RPC 进程独占写入，任何外部脚本不得直接连接该数据库。
> 2. 所有仿真交互（初始化、step、reset、日志读取）必须通过 `http://localhost:3000/api/sim/*` API 完成。
> 3. 离线脚本（如 `context_smoke.py`）必须使用独立的 fixture 数据库（如 `/tmp/oasis-context-smoke.db`），不得复用 Dashboard 运行时数据库。
> 4. 如需读取 Dashboard 运行时数据，应通过 `/api/sim/logs`、`/api/sim/status`、`/api/sim/history` 等 API 端点，而非直接查询 SQLite 文件。

---

## 产出物

| 文件 | 说明 |
|---|---|
| `r2_05_db_constraint.md` | 本报告 |
| `r2_05_results.json` | Gate 验收 JSON 结果 |
