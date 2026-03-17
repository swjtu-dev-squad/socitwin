# 任务卡：R3-02 极化动态性 Smoke Test

| 属性 | 值 |
|---|---|
| **状态** | Ready |
| **优先级** | P0 |
| **类型** | Smoke Test / Polarization Dynamics Validation |
| **负责人** | @分析负责人 |
| **协作人** | @引擎负责人 |
| **关联 Issue** | #2, #22, #24 |

---

## 1. 背景

当前极化分析器并不是静态常量生成器。测试代码已经表明它具备：

- 基于新帖子增量分析 `_get_new_posts()`
- `last_analyzed_post_id` 水位推进
- 历史平均值降级 `_get_historical_fallback()`

这说明“极化恒定”更可能是输入太少或分析器始终吃到同一批数据，而不是分析器根本没设计动态更新。

因此，R3-02 的目标不是再猜，而是基于 R3-01 的高产出场景，验证极化值是否真正开始变化。

## 2. 目标

验证在非空行为场景下：

- 极化值不再恒定；
- 每步 analyzer 能看到新增帖子或 recent fallback；
- 极化波动与内容变化存在基本对应关系；
- 前后端展示与分析器输出一致。

## 3. 范围

| In Scope | Out of Scope |
|---|---|
| analyzer 输入/输出调试 | 群体意识形态建模重构 |
| `last_analyzed_post_id` | 传播图因果分析 |
| polarization trace | 推荐算法联动 |
| Analytics 页面中的 polarization trend | |

## 4. 前置条件

- R3-01 至少一组配置通过。
- `totalPosts` 能在 20 步内达到非空增长。
- step 阶段 analyzer 调试日志已开启。

## 5. 执行步骤

**(1) 跑 R3-01 配置 B**

使用多主题配置，确保有尽可能多的新帖子。

**(2) 启用 analyzer 调试日志**

要求日志至少输出：

- `current_step`
- `new_posts_count`
- `last_analyzed_post_id`
- `fallback` 是否触发
- `polarization` result

**(3) 导出极化 trace**

每步记录：

- `step`
- `totalPosts`
- `polarization`
- `new_posts_count`
- `fallback_used`

**(4) 前端核对**

在 Analytics 页面核对：

- Polarization Trend 曲线
- hover 数值
- 是否与后端 trace 一致

## 6. 建议调试字段

如果你们还没打这些日志，建议输出：

```
[pol] step=7 total_posts=12 new_posts=2 last_id=12 fallback=false polarization=0.34
```

## 7. 通过标准 (Gate)

- [ ] 20 步内极化值至少出现 3 个不同数值
- [ ] analyzer 日志显示多步有 `new_posts > 0` 或 recent fallback 合理触发
- [ ] `last_analyzed_post_id` 随帖子增长推进
- [ ] 前端 polarization trend 与后端 trace 一致
- [ ] 不再是全程固定常数

## 8. 失败标准

- 极化值全程恒定
- analyzer 一直读不到新增帖子
- 前端与后端数值不一致
- 只有 fallback，没有真实新帖分析

## 9. 证据要求

- `artifacts/smoke/r3_02_polarization_report.md`
- `artifacts/smoke/r3_02_polarization_trace.csv`
- `artifacts/smoke/r3_02_analyzer_debug.log`
- Analytics 页面截图

## 10. 备注

这张卡要回答的不是“极化模块有没有代码”，而是：
当系统真的开始说话时，极化会不会跟着动。
