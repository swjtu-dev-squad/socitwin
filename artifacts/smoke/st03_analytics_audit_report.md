# ST-03 Analytics 真数据/假数据甄别 Smoke — 结果报告

**执行时间**：2026-03-17  
**结论**：✅ PASS — 无指标伪装成真实数据

## 审计配置

运行了 1 agent / reddit / AI / 5 steps 的真实仿真，在有真实数据的情况下审计各指标的数据来源。

## 指标数据来源审计表

| 指标 | 数据类型 | 可追溯 | 当前值 | 数据来源 |
|---|---|---|---|---|
| 群体极化率 | REAL（引擎计算） | ✅ | 16.0%（本次 reset 后为 0%） | Python `PolarizationAnalyzer` → `/api/sim/status.polarization` |
| 信息传播速度 | DERIVED（派生） | ✅ | 前端计算 posts/s | `history[]` 相邻 `totalPosts` 差值 / 时间差 |
| 从众效应指数 | NOT_IMPLEMENTED | — | **Coming Soon** | 无（前端诚实标注） |
| A/B 测试偏差 | NOT_IMPLEMENTED | — | **Coming Soon** | 无（前端诚实标注） |
| 意见分布（极左/中立/极右） | HARDCODED_ZERO | — | `[0, 0, 0]` | 硬编码 0，有 TODO 注释 |
| 群体极化演化趋势图 | REAL | ✅ | 5 个数据点 | WebSocket `stats_update` → `store.history` |

## 数据类型统计

| 类型 | 数量 | 说明 |
|---|---|---|
| REAL（真实引擎数据） | 2 | 极化率、趋势图 |
| DERIVED（真实数据派生） | 1 | 信息传播速度 |
| NOT_IMPLEMENTED（诚实标注） | 2 | 从众效应、A/B 偏差 |
| HARDCODED_ZERO（诚实零值） | 1 | 意见分布 |
| **FAKE_REAL（伪装真实）** | **0** | **无** |

## 通过标准检查

- [✅] 无指标伪装成真实数据（FAKE_REAL = 0）
- [✅] 未实现指标明确标注 "Coming Soon"，不显示假数值
- [✅] 硬编码零值有 TODO 注释，不误导用户
- [✅] 极化率数据来源可追溯到 Python 引擎
- [✅] 趋势图数据来源可追溯到 WebSocket 事件流

## 发现与建议

**正面发现**：相比 Issue #2 描述的旧版本（存在硬编码假数据），当前代码已经做了较好的清理。未实现的指标都诚实地标注了 "Coming Soon"，不再用随机数或固定值伪装。

**待改进点**：

1. **极化率在 reset 后为 0**：`/api/sim/reset` 后 `polarization` 归零，但新的 config 完成后 polarization 应该重新初始化。目前 5 步后极化率为 0.0%（本次测试），与之前 ST-02 测试的 16% 不一致，可能与 reset 时机有关。

2. **意见分布缺失**：`opinionDistribution` 全为 0，需要 agent 具备 ideology 属性后才能计算。建议在 Issue #23（社交智能体基础属性）中明确包含 ideology 字段。

3. **信息传播速度精度**：1 agent 场景下每步只产生 1 条帖子，速度计算结果为 0 msg/s，这是正常现象，但建议在 UI 上加注"需要多 agent 才有意义"的提示。
