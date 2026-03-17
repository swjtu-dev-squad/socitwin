# ST-05 WebSocket 增量日志与去重回归 Smoke — 结果报告

**执行时间**：2026-03-17  
**结论**：❌ FAIL — 旧 Bug 回归（Issue #13 未修复）

## 测试配置

| 参数 | 值 |
|---|---|
| platform | reddit |
| agentCount | 1 |
| topic | AI |
| steps | 5 |

## 每步日志快照

| step | 日志总条数 | 唯一内容条数 | 重复条数 | 重复率 |
|---|---|---|---|---|
| 1 | 2 | 2 | 0 | 0% |
| 2 | 3 | 3 | 0 | 0% |
| 3 | 4 | 3 | 1 | 25% |
| 4 | 5 | 3 | 2 | 40% |
| 5 | 6 | 3 | 3 | **50%** |

## 通过标准检查

- [✅] 日志接口无 HTTP 错误
- [✅] 日志随步数有内容变化（总数从 2 增长到 6）
- [❌] 重复率 < 50%（实际 **50%**，触发 FAIL 阈值）

## Bug 根因分析

**Bug 位置**：`oasis_dashboard/real_oasis_engine_v3.py` → `_get_real_agent_actions()` → `_read_posts_table()`

**问题描述**：`_read_posts_table()` 每次调用都查询 `post` 表的全量历史记录（`ORDER BY post_id DESC LIMIT 50`），没有按当前 step 过滤。这意味着：

- Step 1：返回 1 条帖子（正常）
- Step 2：返回同一条帖子 + 1 条 refresh 日志（正常）
- Step 3 起：每次 step 都把同一条帖子重复追加进 new_logs，导致 `/api/sim/logs` 中出现重复内容

**与 Issue #13 的关系**：Issue #13 描述的是"单步执行时通信日志重复回放旧帖子，后端将全量历史误作为 new_logs 返回"，与本次发现完全一致，说明该 bug 在最新代码中**仍未修复**。

## 修复建议

在 `_get_real_agent_actions()` 中引入 `last_log_id` 水位线机制：

```python
# 在引擎初始化时
self._last_post_id = 0
self._last_like_id = 0

# 在 _read_posts_table 中
cursor.execute("""
    SELECT p.post_id, p.user_id, p.content, p.created_at, p.num_likes, u.user_name
    FROM post p
    LEFT JOIN user u ON p.user_id = u.user_id
    WHERE p.post_id > ?
    ORDER BY p.post_id ASC
    LIMIT 50
""", (self._last_post_id,))
rows = cursor.fetchall()
if rows:
    self._last_post_id = max(r[0] for r in rows)
```

这样每次只返回新增的帖子，而不是全量历史。

## 总结

ST-05 确认 Issue #13 描述的历史重复日志 bug **仍然存在**，重复率在 step 5 时达到 50%。该 bug 会污染前端日志面板的显示，并可能影响后续 Analytics 数据的准确性。建议在进行 ST-03/ST-04 之前先修复此 bug。
