# ST-02 初始化 → step → status 主链路 Smoke — 结果报告

**执行时间**：2026-03-17  
**模型**：openai / gpt-4.1-mini  
**服务**：Node.js tsx server.ts（localhost:3000）  
**结论**：✅ PASS

## API 调用序列

| 序号 | 接口 | 方法 | 结果 |
|---|---|---|---|
| 0 | `/api/sim/status` | GET | ✅ 返回初始状态，`oasis_ready: true` |
| 1 | `/api/sim/config` | POST | ✅ 1 agent / reddit / AI 初始化成功，耗时 1.54s |
| 2 | `/api/sim/status` | GET | ✅ `running=true`, `activeAgents=1` |
| 3~7 | `/api/sim/step` | POST×5 | ✅ 5 次全部成功 |
| 8 | `/api/sim/logs` | GET | ✅ 返回 6 条日志（⚠️ 含重复，见备注） |
| 9 | `/api/sim/status` | GET | ✅ 最终状态正常 |
| 10 | `/api/sim/reset` | POST | ✅ 重置成功 |
| 11 | `/api/sim/status` | GET | ✅ reset 后 `currentStep=0`, `running=false` |

## Step 执行趋势

| step_call | currentStep | totalPosts | polarization |
|---|---|---|---|
| 1 | 1 | 1 | 0.1600 |
| 2 | 2 | 1 | 0.1600 |
| 3 | 3 | 1 | 0.1600 |
| 4 | 4 | 1 | 0.1600 |
| 5 | 5 | 1 | 0.1600 |

## 通过标准检查

- [✅] 5 次 step 全部成功
- [✅] currentStep 单调递增（1 → 5）
- [✅] totalPosts 不倒退
- [✅] reset 后 currentStep 归零
- [✅] reset 后 running=false
- [✅] 无 API 错误（HTTP 4xx/5xx）

## 备注与发现

**⚠️ 日志重复问题（ST-05 预警）**：`/api/sim/logs` 返回 6 条日志，但唯一内容仅 3 条（重复率 50%）。每次 step 调用后，旧日志被重复追加，这正是 Issue #13 描述的历史重复日志 bug。该问题将在 ST-05 中专项验证。

**better-sqlite3 原生模块**：初始安装时未编译，需手动在 `node_modules/.pnpm/better-sqlite3@12.6.2/node_modules/better-sqlite3` 目录执行 `npm install` 编译原生绑定后，`/api/sim/logs` 才能正常工作。建议在 README 中补充此步骤。

**polarization 固定值**：5 个 step 的极化率均为 0.16，说明 1 agent 场景下极化率计算结果稳定（单 agent 无法产生极化差异，属正常现象）。
