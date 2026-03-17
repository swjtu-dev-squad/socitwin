# 任务卡：ST-05-FIX 单步执行日志增量读取修复与回归

- **状态**：Ready
- **优先级**：P0
- **类型**：Bug Fix / Regression / Backend Log Semantics
- **负责人**：后端负责人
- **协作人**：前端 store / smoke test 负责人
- **创建日期**：2026-03-17
- **关联 Issue**：#13
- **关联代码**：
  - `oasis_dashboard/real_oasis_engine_v3.py`
  - `server.ts`
  - `src/lib/socket.ts`
  - `src/lib/store.ts`
- **预期产出**：增量日志修复代码、回归测试、复测报告、ST-05 重新执行结果

---

## 1. 背景

Issue #13 已明确：当前单步执行后，后端会把 sqlite 中"最近若干条历史帖子/点赞"重新读出，并作为 `new_logs` 返回，前端则把这些日志当成"本轮新增日志"直接追加展示，导致 `CREATE_POST` 等记录重复回放。问题不在前端展示层，不在记忆架构本身，而在 Python 引擎日志读取策略。

当前 server 端 `/api/sim/step` 会把 `result.new_logs` 中的每条记录通过 `io.emit("new_log", ...)` 推给前端。前端 socket 收到 `new_log` 后，会直接调用 `addLog` 写入 store，因此后端如果把历史记录混进来，前端必然重复追加。

代码里 `_read_posts_table(self, cursor, tables)` 已存在，并且就是 post 表读取的关键入口。

## 2. 目标

修复日志读取语义，使 `new_logs` 严格表示**当前 step 新增的日志记录**，而不是"最近若干条历史记录"。

达成后应满足：
- 连续点击单步执行，不再重复显示旧帖子
- 同一 step 只返回本轮新增的 post / like 日志
- 无新增记录时，`new_logs=[]`
- reset 后增量水位线被正确重置
- 回归测试覆盖 post / like 的增量读取行为

## 3. 范围

### In Scope
- Python 引擎的 post / like 增量读取逻辑
- 引擎实例内游标状态维护
- initialize / reset 生命周期中的游标重置
- 回归测试
- ST-05 smoke 复测

### Out of Scope
- `/api/sim/logs` 历史日志接口重构（该接口面向"历史日志列表"，读取 trace 最近 500 条，是另一条语义）
- 传播图完整因果恢复
- group message 机制改造
- analytics 算法优化

## 4. 根因分析

**现象**：每次 step 后，通信日志重复显示旧 `CREATE_POST` 记录，5 步后重复率达 50%。

**真正根因**：`_get_real_agent_actions()` / `_read_posts_table()` 每次 step 后都从 sqlite 重新读取最近记录，而不是只读本 step 的新增记录；这些全量历史被直接包装成 `new_logs` 返回。

**影响链**：
```
后端误把历史当增量
→ server.ts 发出多个 new_log 事件
→ socket.ts 调 addLog 追加到 store
→ 日志页、传播速度、后续分析一起污染
```

## 5. 修改点

| 修改点 | 位置 | 说明 |
|---|---|---|
| A | `__init__` | 新增 `_last_seen_post_id = 0` 和 `_last_seen_like_id = 0` |
| B | `initialize()` | 成功后重置两个游标为 0 |
| C | `reset()` | 同步清零游标 |
| D | `_read_posts_table()` | 改为 `WHERE id > self._last_seen_post_id ORDER BY id ASC`，读后更新水位线 |
| E | `_read_likes_table()` | 同理改为增量读取（若 like 表存在） |
| F | `_get_real_agent_actions()` | 无新增时返回 `[]`，删除 fallback 假日志逻辑 |

## 6. 测试用例

| 用例 | 目的 | 预期 |
|---|---|---|
| T1 | 首次读取返回新增 post | 1 条日志，`_last_seen_post_id == 1` |
| T2 | 无新增时返回空数组 | `[]`，游标不变，无 fallback |
| T3 | 新增 post 时只返回新增 | 只返回 id=2，不返回 id=1 |
| T4 | like 表增量语义 | 同 T1/T2 逻辑 |
| T5 | reset 后游标清零 | 两个游标均为 0 |
| T6 | 真实 step 回归 | 5 步内 new_logs 无重复 |

## Gate

- [ ] `_last_seen_post_id` / `_last_seen_like_id` 已引入并在 initialize/reset 中正确重置
- [ ] `_read_posts_table()` 改为按主键增量读取
- [ ] `_read_likes_table()` 改为按主键增量读取（若 like 表存在）
- [ ] 无新增记录时 `new_logs=[]`
- [ ] 不再伪造 fallback 假日志
- [ ] 单元测试覆盖首次读取 / 无新增 / 新增后只返回增量 / reset 重置
- [ ] 真实 1-agent 5-step 复测通过
- [ ] ST-05 重新判定为 PASS
- [ ] 修复后补跑 ST-02 与 ST-04，无副作用
