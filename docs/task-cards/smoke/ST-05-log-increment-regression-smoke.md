# 任务卡：ST-05 WebSocket 增量日志与去重回归 Smoke Test

- **状态**：Ready
- **优先级**：P0
- **类型**：Smoke Test / Regression / 日志链路
- **负责人**：
- **协作人**：
- **创建日期**：2026-03-17
- **关联 Issue**：#13
- **关联代码**：`src/lib/socket.ts`, `src/lib/store.ts`, `server.ts`
- **预期产出**：`step` vs `total_logs` vs `new_logs` 表格、日志页截图

---

## 1. 背景与目标

Issue #13 记录了一个已修复的 bug：后端将全量历史日志误作为 `new_logs` 返回，导致前端重复回放。本任务的目标是回归验证该 bug 未复现，并确保 WebSocket 日志链路的增量语义正确，即每次 `step` 只追加**新的**日志。

## 2. 范围

### In Scope
- 单步执行后的日志增量语义
- WebSocket `new_log` 事件
- Store `addLog` 逻辑
- Logs 页面基础观察
- 日志数量回归检查

### Out of Scope
- 群聊复杂消息流
- 图谱级传播恢复
- 历史日志分页优化

## 3. 执行步骤

**Step 1：启动最小模拟**

使用 1 agent，执行 5 次 `step`。

**Step 2：逐步记录**

每一步记录：
- `step` 编号
- 当前总日志数 (`store.logs.length`)
- 本步新增日志数 (来自 `new_log` payload)
- 新增日志摘要
- 是否出现与前一步相同的 `CREATE_POST` / `LIKE` 记录

**Step 3：核对事件流**

确认 `new_log` 只表示“本轮新增”，而不是历史重放。

## 4. 通过标准 (Gate)

- [ ] 连续 5 次 step 后，日志只追加本轮新增项。
- [ ] 不再出现 Issue #13 所述的重复回放现象。
- [ ] 前端日志总数与实际新增事件一致。
- [ ] 刷新页面后不会把旧日志再次当新日志插入。

## 5. 失败标准

- 同一日志被多次注入。
- 同一步出现历史回放。
- 日志数异常倍增。
- 前端展示与后端实际 trace 不一致。

## 6. 证据要求

- `step` vs `total_logs` vs `new_logs` 表格
- 日志页截图
- 后端返回 `new_log` 样例
- 若失败，附重复日志对比样例

---

## Gate

- [ ] 能按文档步骤复现
- [ ] 证据完整
- [ ] 结论明确（Pass / Fail / Blocked）
- [ ] 若 Fail，已给出定位方向
- [ ] 若涉及代码修改，已单独提交 commit
